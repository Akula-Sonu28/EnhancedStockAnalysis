"""Backtest engine: daily event loop.

Flow at each decision date d:
    1. Mark portfolio to last-known close on day d.
    2. For every open position: ask strategy if we should EXIT / REDUCE
       (hard-stop, trailing, scale-out, score sell). If yes, queue a SELL
       fill at the next-day open after d.
    3. Compute candidate set from the date snapshot (eligible symbols this date).
    4. Rank candidates by score (engine-agnostic).
    5. For each open slot (max_positions - currently_held):
        a. Pick next-best candidate not already held.
        b. Check sector cap with current equity.
        c. Size to target weight (default equal-weight of `target_count`).
        d. Queue BUY fill at next-day open.
    6. Optionally: ROTATION — if a high-score candidate clears the rotation
       gate vs a weak holding, queue (SELL weak + BUY candidate).
    7. Apply queued fills. Record equity snapshot for the day.

The engine is deterministic given the same inputs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator, Optional

import numpy as np
import pandas as pd

from .costs import CostConfig, SlippageConfig, DEFAULT_COST, DEFAULT_SLIPPAGE
from .data.path1_loader import (
    Path1Loader, DateSnapshot,
    first_market_cap_lookup, first_sector_lookup,
)
from .data.prices import PriceCache
from .execution import Executor, ExecutionError
from .portfolio import Portfolio
from .cooldown import CooldownPolicy, should_suppress_sell
from .strategy import StrategyAdapter, Decision


# ----- Config ---------------------------------------------------------------

@dataclass
class EngineConfig:
    initial_capital: float = 100_000.0
    target_positions: int = 10
    max_positions: int = 15
    sector_cap_pct: float = 30.0
    rebalance: str = 'weekly'        # 'daily' | 'weekly' | 'monthly'
    min_universe: int = 20
    allow_rotation: bool = True
    cost_cfg: CostConfig = field(default_factory=lambda: DEFAULT_COST)
    slippage_cfg: SlippageConfig = field(default_factory=lambda: DEFAULT_SLIPPAGE)
    benchmark_symbol: Optional[str] = '^NSEI'   # Nifty 50; set None to skip

    # Stress-test selection mode:
    #   'threshold' (default-prod): only BUY when score >= BUY_THRESHOLD (~60 for v2).
    #                               Holds fewer than target if not enough BUY signals.
    #   'rank'                    : always BUY top-N by score per rebalance, as long
    #                               as the floor is met. Used to stress-test ranking.
    selection_mode: str = 'rank'
    min_entry_score: float = 45.0    # floor in rank mode (HOLD-ish)
    cooldown_policy: CooldownPolicy = field(
        default_factory=CooldownPolicy.disabled,
    )
    # When True, run exit checks on every NSE trading day (not only score snapshots).
    # Required for meaningful recent-buy cooldown simulation on weekly/biweekly cadence.
    daily_exit_checks: bool = True
    momentum_exhaustion_enabled: bool = True


# ----- Run output -----------------------------------------------------------

@dataclass
class BacktestResult:
    run_id: str
    engine_label: str           # 'v1' or 'v2'
    start_date: date
    end_date: date
    equity_curve: pd.Series     # indexed by date
    benchmark_curve: Optional[pd.Series]
    trades: list                # list of closed-trade dicts (portfolio.closed_trades)
    final_positions: list       # snapshot at run-end
    rebalance_log: list         # one row per rebalance attempt
    summary: dict               # filled by metrics.summarize


# ----- Helpers --------------------------------------------------------------

def _rebalance_dates(all_dates: list[date], cadence: str) -> list[date]:
    """Pick rebalance decision dates. all_dates is sorted unique trading dates."""
    if not all_dates:
        return []
    if cadence == 'daily':
        return list(all_dates)
    if cadence == 'weekly':
        # Approximate weekly = every Mon-equivalent: take first day-of-ISO-week.
        df = pd.DataFrame({'d': pd.to_datetime(all_dates)})
        df['iso_week'] = df['d'].dt.isocalendar().week
        df['iso_year'] = df['d'].dt.isocalendar().year
        picks = df.groupby(['iso_year', 'iso_week'])['d'].min()
        return [p.date() for p in picks.tolist()]
    if cadence == 'monthly':
        df = pd.DataFrame({'d': pd.to_datetime(all_dates)})
        df['ym'] = df['d'].dt.to_period('M')
        picks = df.groupby('ym')['d'].min()
        return [p.date() for p in picks.tolist()]
    raise ValueError(f'unknown cadence: {cadence}')


def _trading_calendar(price_cache: PriceCache, start: date, end: date) -> list[date]:
    """NSE trading days between start and end (weekday fallback if index missing)."""
    df = price_cache.get('^NSEI', start, end)
    if df is not None and not df.empty:
        return sorted({ts.date() for ts in df.index})
    days: list[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _sector_from_row(row: pd.Series, lookup: Optional[dict] = None) -> str:
    for col in ('sector', 'Sector', 'industry', 'Industry'):
        if col in row and pd.notna(row[col]):
            return str(row[col])
    if lookup is not None:
        sym = row.get('symbol')
        if sym is not None and str(sym) in lookup:
            return lookup[str(sym)]
    return 'Unknown'


# ----- Engine ---------------------------------------------------------------

class BacktestEngine:
    """Daily event-driven backtest engine."""

    def __init__(self, engine_label: str = 'v2', cfg: Optional[EngineConfig] = None,
                 price_cache: Optional[PriceCache] = None,
                 strategy: Optional[StrategyAdapter] = None):
        self.engine_label = engine_label
        self.cfg = cfg or EngineConfig()
        self.prices = price_cache or PriceCache()
        self.strategy = strategy or StrategyAdapter()
        self._mcap = first_market_cap_lookup()
        self._sector = first_sector_lookup()
        self.cooldown_suppressions = 0

    # ----- price + market cap lookups passed to Executor ------------------

    def _next_day_open(self, symbol: str, after: date) -> Optional[float]:
        return self.prices.next_trading_day_open(symbol, after)

    def _market_cap(self, symbol: str) -> Optional[float]:
        return self._mcap.get(symbol)

    # ----- main loop ------------------------------------------------------

    def _marks_for_day(
        self,
        d: date,
        portfolio: Portfolio,
        snap: Optional[DateSnapshot],
    ) -> tuple[dict[str, float], dict[str, float], str]:
        mark_prices: dict[str, float] = {}
        score_today: dict[str, float] = {}
        regime_today = ''
        if snap is not None:
            for _, row in snap.df.iterrows():
                sym = str(row['symbol'])
                if pd.notna(row.get('current_price')):
                    mark_prices[sym] = float(row['current_price'])
                if pd.notna(row.get('score_engine')):
                    score_today[sym] = float(row['score_engine'])
                if pd.notna(row.get('regime')) and not regime_today:
                    regime_today = str(row['regime'])
        for sym in list(portfolio.positions.keys()):
            if sym not in mark_prices:
                p = self.prices.last_close_at_or_before(sym, d)
                if p is not None:
                    mark_prices[sym] = p
        for sym, pos in portfolio.positions.items():
            sc = score_today.get(sym)
            pos.mark(mark_prices.get(sym, pos.last_mark_price), sc)
        return mark_prices, score_today, regime_today

    def _execute_exits(
        self,
        portfolio: Portfolio,
        executor: Executor,
        d: date,
        mark_prices: dict[str, float],
        score_today: dict[str, float],
        regime_today: str,
    ) -> int:
        """Run exit/reduce checks; return count of sell attempts (incl. blocked)."""
        attempts = 0
        exit_decisions: list[tuple[str, Decision]] = []
        for sym, pos in list(portfolio.positions.items()):
            price = mark_prices.get(sym, pos.last_mark_price or pos.avg_cost)
            profit_pct = pos.unrealized_pl_pct(price)
            sc = score_today.get(sym, pos.last_score)
            dec = self.strategy.check_open_position(
                score=sc,
                profit_pct=profit_pct,
                rsi=50.0,
                pattern_signal='',
                market_regime=regime_today,
                peak_score=pos.peak_score,
                peak_price=pos.peak_price,
                current_price=price,
                symbol=sym,
                as_of=d,
                price_cache=self.prices,
                entry_price=pos.avg_cost,
                previous_exhaustion_score=pos.last_exhaustion_score,
                momentum_exhaustion_enabled=self.cfg.momentum_exhaustion_enabled,
            )
            if dec.exhaustion_score > 0:
                pos.last_exhaustion_score = dec.exhaustion_score
            elif dec.action == 'HOLD':
                pos.last_exhaustion_score = max(0.0, pos.last_exhaustion_score * 0.85)
            if dec.action in ('SELL', 'REDUCE'):
                dec.symbol = sym
                exit_decisions.append((sym, dec))

        for sym, dec in exit_decisions:
            pos = portfolio.positions.get(sym)
            if pos is None:
                continue
            attempts += 1
            price = mark_prices.get(sym, pos.last_mark_price or pos.avg_cost)
            profit_pct = pos.unrealized_pl_pct(price)
            sc = score_today.get(sym, pos.last_score)
            if self._cooldown_blocks_exit(
                pos, d, profit_pct, sc, regime_today, dec,
            ):
                continue
            qty_to_sell = max(1, int(round(pos.qty * dec.qty_pct)))
            qty_to_sell = min(qty_to_sell, pos.qty)
            try:
                fill = executor.submit(
                    symbol=sym, side='SELL', qty=qty_to_sell,
                    decision_date=d,
                    fill_date=self._estimate_fill_date(sym, d),
                    reason=dec.reason,
                )
                portfolio.apply_sell_fill(fill, reason=dec.reason)
            except ExecutionError as e:
                logging.warning(f'[engine] sell failed {sym} on {d}: {e}')
        return attempts

    def run(self, snapshots: list[DateSnapshot]) -> BacktestResult:
        if not snapshots:
            raise ValueError('no snapshots to backtest over')
        snapshots = sorted(snapshots, key=lambda s: s.decision_date)
        snap_map = {s.decision_date: s for s in snapshots}
        snap_dates = [s.decision_date for s in snapshots]

        if self.cfg.daily_exit_checks:
            all_days = _trading_calendar(
                self.prices, snap_dates[0], snap_dates[-1],
            )
            all_days = sorted(set(all_days) | set(snap_dates))
        else:
            all_days = snap_dates

        rebal_dates = set(_rebalance_dates(snap_dates, self.cfg.rebalance))

        portfolio = Portfolio(
            initial_capital=self.cfg.initial_capital,
            cost_cfg=self.cfg.cost_cfg,
            sector_cap_pct=self.cfg.sector_cap_pct,
            max_positions=self.cfg.max_positions,
        )
        executor = Executor(
            next_day_open=self._next_day_open,
            market_cap_crores=self._market_cap,
            cost_cfg=self.cfg.cost_cfg,
            slippage_cfg=self.cfg.slippage_cfg,
        )

        equity_curve: dict[date, float] = {}
        rebalance_log: list[dict] = []
        last_regime = 'SIDEWAYS'

        for d in all_days:
            snap = snap_map.get(d)
            is_rebal = d in rebal_dates
            mark_prices, score_today, regime_today = self._marks_for_day(
                d, portfolio, snap,
            )
            if regime_today:
                last_regime = regime_today
            elif not regime_today:
                regime_today = last_regime

            exit_attempts = self._execute_exits(
                portfolio, executor, d, mark_prices, score_today, regime_today,
            )

            # --- ENTRY on rebalance dates (snapshot required) -------------
            new_buys: list[tuple[str, str, float, float]] = []
            if snap is not None and is_rebal:
                candidates = snap.df.copy()
                candidates = candidates.sort_values('score_engine', ascending=False)
                held = set(portfolio.positions.keys())
                slots = self.cfg.target_positions - portfolio.open_position_count()

                # ROTATION first: try to swap weak holdings with stronger candidates
                if self.cfg.allow_rotation and slots <= 0:
                    self._consider_rotation(
                        portfolio, executor, candidates, score_today,
                        mark_prices, d, regime_today, rebalance_log,
                    )

                # Fill remaining slots
                eq_now = portfolio.equity(mark_prices)
                slots = self.cfg.target_positions - portfolio.open_position_count()
                # Reserve 1.5% buffer for slippage + Indian charges (~0.6-0.8%
                # per round-trip + slippage up to ~50bps). This prevents the
                # last buy in a rebalance from overdrawing cash.
                per_slot_inr = (eq_now / self.cfg.target_positions * 0.985
                                if eq_now > 0 else 0.0)
                bought_count = 0
                for _, c in candidates.iterrows():
                    if slots <= 0:
                        break
                    sym = str(c['symbol'])
                    if sym in held:
                        continue
                    sc = float(c['score_engine'])
                    if self.cfg.selection_mode == 'threshold':
                        if self.strategy.entry_signal(sc) not in ('BUY', 'STRONG_BUY'):
                            continue
                    else:  # 'rank'
                        if sc < self.cfg.min_entry_score:
                            continue
                    if pd.isna(c.get('current_price')) or c['current_price'] <= 0:
                        continue
                    next_open = self._next_day_open(sym, d)
                    if next_open is None or next_open <= 0:
                        continue
                    # Cap qty to BOTH per-slot allocation AND available cash
                    # (with a small extra buffer for charges).
                    qty_by_slot = int(per_slot_inr // next_open) if next_open > 0 else 0
                    qty_by_cash = int((portfolio.cash * 0.99) // next_open) if next_open > 0 else 0
                    qty = max(0, min(qty_by_slot, qty_by_cash))
                    if qty <= 0:
                        continue
                    sector = _sector_from_row(c, self._sector)
                    intended_invest = qty * next_open
                    if not portfolio.can_add_sector(sector, mark_prices, intended_invest):
                        continue
                    try:
                        fill = executor.submit(
                            symbol=sym, side='BUY', qty=qty,
                            decision_date=d,
                            fill_date=self._estimate_fill_date(sym, d),
                            reason=f'entry: score={sc:.1f} ({self.strategy.entry_signal(sc)})',
                        )
                        portfolio.apply_buy_fill(fill, sector=sector, entry_score=sc)
                        new_buys.append((sym, sector, sc, qty * fill.fill_price))
                        held.add(sym)
                        slots -= 1
                        bought_count += 1
                    except ExecutionError as e:
                        logging.warning(f'[engine] buy failed {sym} on {d}: {e}')

                rebalance_log.append({
                    'date': str(d),
                    'universe_n': int(len(candidates)),
                    'held_pre': len(held) - bought_count,
                    'bought': bought_count,
                    'sold': exit_attempts,
                    'cash_pct': portfolio.cash_pct(mark_prices),
                })

            equity_curve[d] = portfolio.equity(mark_prices)

        # --- Final state --------------------------------------------------
        equity_series = pd.Series(equity_curve).sort_index()
        equity_series.index = pd.to_datetime(equity_series.index)

        benchmark_series = self._load_benchmark(
            equity_series.index.min().date(),
            equity_series.index.max().date(),
        ) if self.cfg.benchmark_symbol else None

        # Close out remaining open positions at the last available close
        # for fair comparison (the "final equity" already includes these
        # at mark price; we do not force-sell — the user can choose to).

        final_positions = [
            {
                'symbol': pos.symbol,
                'sector': pos.sector,
                'qty': pos.qty,
                'avg_cost': round(pos.avg_cost, 4),
                'last_mark': round(pos.last_mark_price, 4),
                'unrealized_pl_pct': round(pos.unrealized_pl_pct(pos.last_mark_price) * 100, 4),
                'entry_date': pos.entry_date.isoformat(),
                'entry_score': round(pos.entry_score, 2),
                'peak_score': round(pos.peak_score, 2),
                'last_score': round(pos.last_score, 2),
            }
            for pos in portfolio.positions.values()
        ]

        from .metrics import summarize
        summary = summarize(
            equity=equity_series,
            trades=portfolio.closed_trades,
            initial_capital=self.cfg.initial_capital,
            benchmark=benchmark_series,
        )
        summary['stcg_paid'] = round(portfolio.gains.stcg_paid, 2)
        summary['ltcg_paid'] = round(portfolio.gains.ltcg_paid, 2)
        summary['open_positions'] = len(final_positions)
        summary['cooldown_suppressions'] = self.cooldown_suppressions
        summary['cooldown_policy'] = self.cfg.cooldown_policy.name

        return BacktestResult(
            run_id='', engine_label=self.engine_label,
            start_date=equity_series.index.min().date(),
            end_date=equity_series.index.max().date(),
            equity_curve=equity_series,
            benchmark_curve=benchmark_series,
            trades=portfolio.closed_trades,
            final_positions=final_positions,
            rebalance_log=rebalance_log,
            summary=summary,
        )

    # ----- internals ------------------------------------------------------

    def _cooldown_blocks_exit(
        self,
        pos,
        as_of: date,
        profit_pct: float,
        score: float,
        regime: str,
        dec: Decision,
    ) -> bool:
        """True when cooldown suppresses this sell/reduce."""
        policy = self.cfg.cooldown_policy
        if not policy.enabled:
            return False
        suppress, _reason = should_suppress_sell(
            policy=policy,
            entry_date=pos.entry_date,
            as_of=as_of,
            profit_pct=profit_pct,
            current_v2_score=score,
            current_regime=regime,
            exit_reason=dec.reason,
            hard_stop_tier=dec.hard_stop_tier,
            score_history=[score],
        )
        if suppress:
            self.cooldown_suppressions += 1
        return suppress

    def _estimate_fill_date(self, symbol: str, decision_date: date) -> date:
        """Best estimate of the actual next trading day (used purely for
        ledger labelling and capital-gains holding period)."""
        # We could query the prices cache; for the ledger we accept
        # decision + 1 calendar day as a robust approximation.
        return decision_date + timedelta(days=1)

    def _consider_rotation(self, portfolio: Portfolio, executor: Executor,
                           candidates: pd.DataFrame, score_today: dict,
                           mark_prices: dict, decision_date: date,
                           regime: str, rebalance_log: list) -> None:
        """Try to swap the weakest holding for a stronger un-held candidate."""
        if portfolio.open_position_count() == 0:
            return
        # Pick the weakest holding
        weakest = min(portfolio.positions.values(),
                      key=lambda p: score_today.get(p.symbol, p.last_score))
        weak_score = score_today.get(weakest.symbol, weakest.last_score)
        held = set(portfolio.positions.keys())
        for _, c in candidates.iterrows():
            sym = str(c['symbol'])
            if sym in held:
                continue
            sc = float(c['score_engine'])
            profit_pct = weakest.unrealized_pl_pct(
                mark_prices.get(weakest.symbol, weakest.last_mark_price or weakest.avg_cost)
            )
            if not self.strategy.should_rotate(
                candidate_score=sc, holding_score=weak_score,
                holding_rsi=50.0, holding_profit_pct=profit_pct,
            ):
                continue
            rot_dec = Decision(
                symbol=weakest.symbol, action='SELL', qty_pct=1.0,
                reason=f'rotation: {weakest.symbol}({weak_score:.1f}) -> {sym}({sc:.1f})',
                score=weak_score,
            )
            if self._cooldown_blocks_exit(
                weakest, decision_date, profit_pct, weak_score, regime, rot_dec,
            ):
                continue
            # Execute the rotation: sell weak, buy new
            try:
                sell_fill = executor.submit(
                    symbol=weakest.symbol, side='SELL', qty=weakest.qty,
                    decision_date=decision_date,
                    fill_date=self._estimate_fill_date(weakest.symbol, decision_date),
                    reason=f'rotation: {weakest.symbol}({weak_score:.1f}) -> {sym}({sc:.1f})',
                )
                portfolio.apply_sell_fill(sell_fill, reason=sell_fill.reason)
                eq_now = portfolio.equity(mark_prices)
                per_slot = (eq_now / self.cfg.target_positions * 0.985
                            if eq_now > 0 else 0.0)
                next_open = self._next_day_open(sym, decision_date)
                if next_open is None or next_open <= 0:
                    return
                qty_by_slot = int(per_slot // next_open)
                qty_by_cash = int((portfolio.cash * 0.99) // next_open)
                qty = max(0, min(qty_by_slot, qty_by_cash))
                if qty <= 0:
                    return
                buy_fill = executor.submit(
                    symbol=sym, side='BUY', qty=qty,
                    decision_date=decision_date,
                    fill_date=self._estimate_fill_date(sym, decision_date),
                    reason=f'rotation: in from {weakest.symbol}',
                )
                portfolio.apply_buy_fill(
                    buy_fill, sector=_sector_from_row(c, self._sector), entry_score=sc,
                )
                rebalance_log.append({
                    'date': str(decision_date),
                    'event': 'rotation',
                    'out': weakest.symbol,
                    'in': sym,
                    'out_score': weak_score,
                    'in_score': sc,
                })
            except ExecutionError as e:
                logging.warning(f'[engine] rotation failed: {e}')
            return  # one rotation per rebalance

    def _load_benchmark(self, start: date, end: date) -> Optional[pd.Series]:
        """Nifty 50 (^NSEI) equity curve normalized to initial_capital."""
        sym = self.cfg.benchmark_symbol
        if not sym:
            return None
        try:
            import yfinance as yf
            df = yf.Ticker(sym).history(
                start=start.isoformat(), end=(end + timedelta(days=2)).isoformat(),
                auto_adjust=True,
            )
            if df is None or df.empty:
                return None
            close = df['Close'].dropna()
            close.index = pd.to_datetime(close.index).tz_localize(None)
            if close.empty:
                return None
            normalized = close / close.iloc[0] * self.cfg.initial_capital
            return normalized
        except Exception as e:
            logging.warning(f'[engine] benchmark fetch failed: {e}')
            return None
