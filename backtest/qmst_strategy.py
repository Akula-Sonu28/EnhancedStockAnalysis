"""QMST strategy adapter: VMQ exits (incl. day-3) + turbo entry."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

from config import get_config

from .strategy import Decision, StrategyAdapter


class QMSTStrategyAdapter(StrategyAdapter):
    """Pick/entry/exit doctrine for QMST backtests.

    Exits: VMQ hard/swing/trail + optional day-3/day-5 when VMQ_DAY3_ENABLED.
    Entries: ``evaluate_turbo_entry_gate`` via ``entry_allowed``.
    """

    def __init__(
        self,
        sleeve: str = 'TACTICAL',
        include_day3: Optional[bool] = None,
        pick_gates_enabled: Optional[bool] = None,
    ):
        super().__init__(sleeve=sleeve)
        self._cfg = get_config()
        if include_day3 is None:
            include_day3 = bool(getattr(self._cfg, 'VMQ_DAY3_ENABLED', False))
        self.include_day3 = include_day3
        self.pick_gates_enabled = pick_gates_enabled
        self.entries_blocked = 0
        self.entries_passed = 0
        self.pick_gates_blocked = 0
        self.vmq_day3_exits = 0
        self.vmq_day5_exits = 0

    def entry_allowed(self, row: Dict[str, Any]) -> bool:
        from src.qmst_pick_gates import evaluate_pick_gates

        pick = evaluate_pick_gates(row, self._cfg, enabled=self.pick_gates_enabled)
        if not pick.allowed:
            self.entries_blocked += 1
            self.pick_gates_blocked += 1
            return False
        if row.get('turbo_pass') is True:
            self.entries_passed += 1
            return True
        if row.get('turbo_pass') is False:
            self.entries_blocked += 1
            return False
        from src.turbo_entry import evaluate_turbo_entry_gate
        gate = evaluate_turbo_entry_gate(row, self._cfg, new_this_week=0)
        if gate.allowed:
            self.entries_passed += 1
        else:
            self.entries_blocked += 1
        return bool(gate.allowed)

    @staticmethod
    def _as_datetime(d) -> Optional[datetime]:
        if d is None:
            return None
        if isinstance(d, datetime):
            return d
        if isinstance(d, date):
            return datetime.combine(d, datetime.min.time())
        return pd.Timestamp(d).to_pydatetime()

    def _build_price_history(
        self,
        price_cache,
        symbol: str,
        entry_date: datetime,
        entry_price: float,
        as_of: datetime,
    ) -> pd.DataFrame:
        """Synthetic NEW POSITION + daily marks for VMQ day-3/5 checks."""
        if price_cache is None or entry_date is None or entry_price <= 0:
            return pd.DataFrame()
        start = entry_date.date() if hasattr(entry_date, 'date') else entry_date
        end = as_of.date() if hasattr(as_of, 'date') else as_of
        ohlcv = price_cache.get(
            symbol,
            start - timedelta(days=2),
            end + timedelta(days=1),
        )
        if ohlcv is None or ohlcv.empty:
            return pd.DataFrame([
                {
                    'symbol': symbol,
                    'date': entry_date,
                    'price': entry_price,
                    'action': 'NEW POSITION',
                },
            ])
        rows = [{
            'symbol': symbol,
            'date': pd.Timestamp(entry_date),
            'price': float(entry_price),
            'action': 'NEW POSITION',
        }]
        for ts, row in ohlcv.iterrows():
            px = float(row.get('Close', row.get('AdjClose', 0)) or 0)
            if px <= 0:
                continue
            rows.append({
                'symbol': symbol,
                'date': pd.Timestamp(ts),
                'price': px,
                'action': 'HOLD',
            })
        return pd.DataFrame(rows)

    def check_open_position(
        self,
        *,
        score: float,
        profit_pct: float,
        rsi: float = 50.0,
        pattern_signal: str = '',
        market_regime: str = '',
        peak_score: float = 0.0,
        peak_price: float = 0.0,
        current_price: float = 0.0,
        symbol: str = '',
        as_of=None,
        price_cache=None,
        entry_price: float = 0.0,
        entry_date=None,
        previous_exhaustion_score: float = 0.0,
        momentum_exhaustion_enabled: bool = True,
        turbo_score: Optional[float] = None,
        mtf_score: Optional[float] = None,
        vix_level: Optional[float] = None,
    ) -> Decision:
        from src.vmq_strategy import evaluate_holding_validation

        entry_dt = self._as_datetime(entry_date)
        as_of_dt = self._as_datetime(as_of)
        ep = entry_price if entry_price > 0 else current_price

        history_df = pd.DataFrame()
        if self.include_day3 and price_cache is not None and entry_dt and as_of_dt:
            history_df = self._build_price_history(
                price_cache, symbol, entry_dt, ep, as_of_dt,
            )

        override = evaluate_holding_validation(
            symbol,
            ep,
            entry_dt,
            current_price,
            profit_pct,
            history_df=history_df if not history_df.empty else None,
            cfg=self._cfg,
            sleeve=self.sleeve,
            as_of=as_of_dt,
            market_regime=market_regime,
            vix_level=vix_level,
            enable_day3_validation=self.include_day3,
            turbo_score=turbo_score,
            mtf_score=mtf_score,
        )
        if override:
            act, reason = override
            if 'DAY-3' in reason.upper():
                self.vmq_day3_exits += 1
            elif 'DAY-5' in reason.upper():
                self.vmq_day5_exits += 1
            qty_pct = 1.0 if act == 'SELL' else 0.5
            return Decision(
                symbol=symbol,
                action=act,
                qty_pct=qty_pct,
                reason=reason,
                score=score,
                hard_stop_tier='HARD_STOP' if 'HARD STOP' in reason.upper() else 'NONE',
            )
        return Decision(
            symbol=symbol,
            action='HOLD',
            qty_pct=0.0,
            reason=f'QMST hold: pick_rank={score:.1f}, pnl={profit_pct*100:.1f}%',
            score=score,
        )

    def should_rotate(self, **kwargs) -> bool:
        return False
