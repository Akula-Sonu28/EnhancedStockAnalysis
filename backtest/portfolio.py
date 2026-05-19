"""Portfolio state: cash, positions, sector caps, capital-gains accrual.

The portfolio is the single source of truth for "what do we own right now."
The engine calls into it for valuation, the strategy for "is this rotation
allowed by sector caps", and the reports module to dump positions to CSV.

Each `Position` accumulates its own peak price (for trailing stops, Rule 6b)
and peak score (for scale-out, Rule 5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .costs import (
    CostConfig, DEFAULT_COST,
    is_long_term, realized_gain, stcg_on, ltcg_on, indian_fy_of,
)
from .execution import Fill


@dataclass
class Position:
    symbol: str
    sector: str
    qty: int
    avg_cost: float                 # cost basis per share (rupees)
    entry_date: date
    entry_score: float
    peak_price: float = 0.0         # for trailing stop
    peak_score: float = 0.0         # for scale-out (Rule 5)
    last_score: float = 0.0
    last_mark_price: float = 0.0

    @property
    def cost_basis(self) -> float:
        return self.avg_cost * self.qty

    def mark(self, price: float, score: Optional[float] = None) -> None:
        """Update peak price/score trackers."""
        if price > 0:
            self.last_mark_price = price
            if price > self.peak_price:
                self.peak_price = price
        if score is not None:
            self.last_score = score
            if score > self.peak_score:
                self.peak_score = score

    def market_value(self, price: float) -> float:
        return price * self.qty

    def unrealized_pl(self, price: float) -> float:
        return (price - self.avg_cost) * self.qty

    def unrealized_pl_pct(self, price: float) -> float:
        if self.avg_cost <= 0:
            return 0.0
        return (price - self.avg_cost) / self.avg_cost


@dataclass
class CapitalGains:
    stcg_paid: float = 0.0
    ltcg_paid: float = 0.0
    fy_ltcg_running: dict = field(default_factory=dict)  # FY-start-iso -> running LTCG

    def get_running(self, exit_date: date) -> tuple[str, float]:
        fy_start, _ = indian_fy_of(exit_date)
        key = fy_start.isoformat()
        return key, self.fy_ltcg_running.get(key, 0.0)

    def update_running(self, key: str, new_total: float) -> None:
        self.fy_ltcg_running[key] = new_total


class Portfolio:
    """Mutable portfolio state."""

    def __init__(self,
                 initial_capital: float,
                 cost_cfg: CostConfig = DEFAULT_COST,
                 sector_cap_pct: float = 30.0,
                 max_positions: int = 25,
                 min_alloc_pct: float = 2.0):
        if initial_capital <= 0:
            raise ValueError('initial_capital must be positive')
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[dict] = []     # ledger rows (BUY+SELL paired)
        self.fills: list[Fill] = []             # raw leg log
        self.gains = CapitalGains()
        self.cost_cfg = cost_cfg
        self.sector_cap_pct = sector_cap_pct
        self.max_positions = max_positions
        self.min_alloc_pct = min_alloc_pct
        self._symbol_to_open_buy: dict[str, list[Fill]] = {}

    # --- Valuation ---------------------------------------------------------

    def equity(self, mark_prices: dict[str, float]) -> float:
        """Total equity = cash + sum(position market value)."""
        eq = self.cash
        for sym, pos in self.positions.items():
            p = mark_prices.get(sym, pos.last_mark_price or pos.avg_cost)
            eq += pos.market_value(p)
        return eq

    def sector_exposure_pct(self, mark_prices: dict[str, float],
                            equity_total: Optional[float] = None) -> dict[str, float]:
        if equity_total is None:
            equity_total = self.equity(mark_prices)
        if equity_total <= 0:
            return {}
        out: dict[str, float] = {}
        for sym, pos in self.positions.items():
            p = mark_prices.get(sym, pos.last_mark_price or pos.avg_cost)
            mv = pos.market_value(p)
            out[pos.sector] = out.get(pos.sector, 0.0) + (mv / equity_total * 100)
        return out

    # --- Mutation: fills come from the executor --------------------------

    def apply_buy_fill(self, fill: Fill, sector: str, entry_score: float) -> None:
        """Open a new position OR add to an existing one (FIFO cost basis)."""
        assert fill.side == 'BUY'
        if fill.cash_delta + self.cash < -1e-6:  # sanity
            raise ValueError(f'insufficient cash for BUY {fill.symbol}')
        self.cash += fill.cash_delta
        self.fills.append(fill)
        self._symbol_to_open_buy.setdefault(fill.symbol, []).append(fill)

        pos = self.positions.get(fill.symbol)
        if pos is None:
            pos = Position(
                symbol=fill.symbol,
                sector=sector,
                qty=fill.qty,
                avg_cost=fill.fill_price,
                entry_date=fill.fill_date,
                entry_score=entry_score,
                peak_price=fill.fill_price,
                peak_score=entry_score,
                last_score=entry_score,
                last_mark_price=fill.fill_price,
            )
            self.positions[fill.symbol] = pos
        else:
            total_cost = pos.avg_cost * pos.qty + fill.fill_price * fill.qty
            pos.qty += fill.qty
            pos.avg_cost = total_cost / pos.qty
            pos.peak_price = max(pos.peak_price, fill.fill_price)

    def apply_sell_fill(self, fill: Fill, reason: str = '') -> dict:
        """Close (fully or partially) and produce a ledger row.

        Returns the closed-trade dict for the ledger.
        """
        assert fill.side == 'SELL'
        pos = self.positions.get(fill.symbol)
        if pos is None or pos.qty <= 0:
            raise ValueError(f'no open position to sell for {fill.symbol}')
        if fill.qty > pos.qty:
            raise ValueError(
                f'oversell {fill.symbol}: have {pos.qty}, asked {fill.qty}'
            )

        self.cash += fill.cash_delta
        self.fills.append(fill)

        # Realised P&L is the SELL leg's fill_price vs the position's WEIGHTED
        # avg cost (FIFO would be different; we use weighted avg for simplicity
        # and to mirror what the production scaler does).
        gross_pl = (fill.fill_price - pos.avg_cost) * fill.qty
        entry_buy_charges = self._estimate_proportional_buy_charges(pos, fill.qty)
        net_pl_before_tax = gross_pl - entry_buy_charges - fill.charges['total']

        # Capital gains
        lt = is_long_term(pos.entry_date, fill.fill_date)
        if lt:
            fy_key, running = self.gains.get_running(fill.fill_date)
            tax, new_total = ltcg_on(net_pl_before_tax, running, self.cost_cfg)
            self.gains.update_running(fy_key, new_total)
            self.gains.ltcg_paid += tax
            tax_type = 'LTCG'
        else:
            tax = stcg_on(net_pl_before_tax, self.cost_cfg)
            self.gains.stcg_paid += tax
            tax_type = 'STCG'
        net_pl_after_tax = net_pl_before_tax - tax

        holding_days = (fill.fill_date - pos.entry_date).days
        row = {
            'symbol': fill.symbol,
            'sector': pos.sector,
            'entry_date': pos.entry_date.isoformat(),
            'exit_date': fill.fill_date.isoformat(),
            'holding_days': holding_days,
            'qty': fill.qty,
            'entry_price': round(pos.avg_cost, 4),
            'exit_price': round(fill.fill_price, 4),
            'gross_pl': round(gross_pl, 2),
            'entry_costs': round(entry_buy_charges, 2),
            'exit_costs': round(fill.charges['total'], 2),
            'tax_type': tax_type,
            'tax': round(tax, 2),
            'net_pl': round(net_pl_after_tax, 2),
            'net_return_pct': round(
                (fill.fill_price * fill.qty - pos.avg_cost * fill.qty
                 - entry_buy_charges - fill.charges['total'] - tax)
                / (pos.avg_cost * fill.qty) * 100, 4
            ) if pos.avg_cost > 0 else 0.0,
            'entry_score': round(pos.entry_score, 2),
            'peak_score': round(pos.peak_score, 2),
            'exit_score': round(pos.last_score, 2),
            'peak_price': round(pos.peak_price, 4),
            'exit_reason': reason,
            'slippage_bps': fill.slippage_bps,
        }
        self.closed_trades.append(row)

        # Position bookkeeping
        if fill.qty == pos.qty:
            del self.positions[fill.symbol]
        else:
            pos.qty -= fill.qty
            # avg_cost remains the same for the residual

        return row

    def _estimate_proportional_buy_charges(self, pos: Position, qty_sold: int) -> float:
        """Sum of buy-leg charges proportional to the qty being sold.

        We track each BUY fill in `_symbol_to_open_buy`; for partial closes
        we proportion by quantity. This is a deliberate approximation that
        is fine when avg cost is weighted.
        """
        history = self._symbol_to_open_buy.get(pos.symbol, [])
        if not history:
            return 0.0
        total_qty = sum(f.qty for f in history)
        if total_qty <= 0:
            return 0.0
        frac = qty_sold / total_qty
        return sum(f.charges['total'] for f in history) * frac

    # --- Sizing helpers ---------------------------------------------------

    def open_position_count(self) -> int:
        return len(self.positions)

    def can_open_new(self) -> bool:
        return self.open_position_count() < self.max_positions

    def can_add_sector(self, sector: str, mark_prices: dict[str, float],
                       intended_invest: float) -> bool:
        eq = self.equity(mark_prices)
        if eq <= 0:
            return True
        new_sector_pct = (self.sector_exposure_pct(mark_prices, eq).get(sector, 0)
                          + intended_invest / eq * 100)
        return new_sector_pct <= self.sector_cap_pct

    def cash_pct(self, mark_prices: dict[str, float]) -> float:
        eq = self.equity(mark_prices)
        if eq <= 0:
            return 100.0
        return self.cash / eq * 100
