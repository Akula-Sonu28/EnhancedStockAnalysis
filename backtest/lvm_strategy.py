"""LVM strategy adapter: per-stock %% stop only (no VMQ / hard-stop stack)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .strategy import Decision, StrategyAdapter


@dataclass
class LVMStrategyConfig:
    stop_pct: float = 10.0  # positive number, e.g. 10 => -10%% from entry


class LVMStrategyAdapter(StrategyAdapter):
    """Monthly LowVol→Mom: exit only on LVM stop or full rebalance sells."""

    def __init__(self, stop_pct: float = 10.0, sleeve: str = 'TACTICAL'):
        super().__init__(sleeve=sleeve)
        self.lvm = LVMStrategyConfig(stop_pct=abs(stop_pct))
        self.stop_exits = 0

    def check_open_position(self, *, score: float, profit_pct: float, **kwargs) -> Decision:
        threshold = -self.lvm.stop_pct / 100.0
        if profit_pct <= threshold:
            self.stop_exits += 1
            return Decision(
                symbol='',
                action='SELL',
                qty_pct=1.0,
                reason=f'LVM_STOP: {profit_pct * 100:.1f}% <= -{self.lvm.stop_pct:.0f}%',
                score=score,
            )
        return Decision(
            symbol='',
            action='HOLD',
            qty_pct=0.0,
            reason=f'LVM hold (PnL {profit_pct * 100:.1f}%)',
            score=score,
        )

    def should_rotate(self, **kwargs) -> bool:
        return False

    def entry_signal(self, score: float) -> str:
        return 'BUY'
