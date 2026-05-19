"""Strategy adapter: score + position state -> action decision.

Imports `_evaluate_hard_stop` and `_should_rotate` from the production
analyzer so backtest behaviour cannot diverge from live.

The strategy is intentionally thin: it asks the engine "what's the score
for this symbol today, what's my P&L on this open position, what's the
regime" and returns a decision dict. The engine then translates decisions
into BUY/SELL orders via the executor.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Production imports — same code as the live engine.
from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer  # noqa: E402
from config import get_config  # noqa: E402


@dataclass
class Decision:
    symbol: str
    action: str               # 'BUY' | 'HOLD' | 'SELL' | 'REDUCE' | 'SKIP'
    qty_pct: float            # fraction of current position to act on (1.0 = all)
    reason: str
    score: float
    hard_stop_tier: str = 'NONE'


class StrategyAdapter:
    """Wraps production action logic for backtest use."""

    def __init__(self,
                 buy_threshold: Optional[float] = None,
                 sell_threshold: Optional[float] = None,
                 strong_buy_threshold: Optional[float] = None,
                 hold_threshold: Optional[float] = None,
                 trailing_stop_pct: Optional[float] = None,
                 trailing_stop_bear_pct: Optional[float] = None,
                 scale_out_profit_threshold: Optional[float] = None,
                 scale_out_v2_drop_pts: Optional[float] = None,
                 scale_out_fraction: Optional[float] = None,
                 sleeve: str = 'TACTICAL'):
        cfg = get_config()
        self.buy_thr = buy_threshold if buy_threshold is not None else cfg.BUY_THRESHOLD
        self.sell_thr = sell_threshold if sell_threshold is not None else cfg.SELL_THRESHOLD
        self.sb_thr = strong_buy_threshold if strong_buy_threshold is not None else cfg.STRONG_BUY_THRESHOLD
        self.hold_thr = hold_threshold if hold_threshold is not None else cfg.HOLD_THRESHOLD
        self.trail_pct = trailing_stop_pct if trailing_stop_pct is not None else cfg.TRAILING_STOP_PCT
        self.trail_bear_pct = trailing_stop_bear_pct if trailing_stop_bear_pct is not None else cfg.TRAILING_STOP_BEAR_PCT
        self.scale_out_profit = scale_out_profit_threshold if scale_out_profit_threshold is not None else cfg.SCALE_OUT_PROFIT_THRESHOLD
        self.scale_out_drop = scale_out_v2_drop_pts if scale_out_v2_drop_pts is not None else cfg.SCALE_OUT_V2_DROP_PTS
        self.scale_out_frac = scale_out_fraction if scale_out_fraction is not None else cfg.SCALE_OUT_FRACTION
        self.sleeve = sleeve
        self._cfg = cfg

    # --- Entry signal: score-based -------------------------------------

    def entry_signal(self, score: float) -> str:
        """Return 'STRONG_BUY' / 'BUY' / 'HOLD' / 'SELL' based on thresholds."""
        if score >= self.sb_thr:
            return 'STRONG_BUY'
        if score >= self.buy_thr:
            return 'BUY'
        if score >= self.hold_thr:
            return 'HOLD'
        return 'SELL'

    # --- Exit checks on an open position --------------------------------

    def check_open_position(self, *, score: float, profit_pct: float,
                            rsi: float = 50.0, pattern_signal: str = '',
                            market_regime: str = '',
                            peak_score: float = 0.0,
                            peak_price: float = 0.0,
                            current_price: float = 0.0) -> Decision:
        """Apply (in order):
            1. Hard-stop tier (EMERGENCY / HARD_STOP / SOFT_STOP / NONE)
            2. Trailing stop (peak * (1 - pct), bear pct in bear regime, only if in profit)
            3. Scale-out (Rule 5): profit >= 15% AND score dropped >= 10pts from peak
            4. Score threshold (SELL below sell_thr)
            5. Otherwise HOLD
        """
        # 1. Hard stop
        hs = EnhancedTop200StockAnalyzer._evaluate_hard_stop(
            profit_pct=profit_pct,
            score=score,
            rsi=rsi,
            pattern_signal=pattern_signal,
            cfg=self._cfg,
            sleeve=self.sleeve,
            market_regime=market_regime,
        )
        if hs['tier'] != 'NONE':
            qty_pct = (hs.get('book_pct', 100) or 100) / 100.0
            action = 'SELL' if qty_pct >= 1.0 else 'REDUCE'
            return Decision(symbol='', action=action, qty_pct=qty_pct,
                            reason=f"hard_stop:{hs['tier']} - {hs.get('reason','')}",
                            score=score, hard_stop_tier=hs['tier'])

        # 2. Trailing stop
        in_profit = profit_pct > 0
        if in_profit and peak_price > 0 and current_price > 0:
            trail = self.trail_bear_pct if str(market_regime).upper() in ('BEAR', 'BEARISH', 'VOLATILE') else self.trail_pct
            if trail > 0 and current_price <= peak_price * (1 - trail):
                return Decision(symbol='', action='SELL', qty_pct=1.0,
                                reason=f'trailing_stop: peak={peak_price:.2f}, '
                                       f'current={current_price:.2f}, trail={trail*100:.0f}%',
                                score=score)

        # 3. Scale-out (Rule 5)
        if peak_score > 0 and profit_pct >= self.scale_out_profit:
            score_drop = peak_score - score
            if score_drop >= self.scale_out_drop:
                return Decision(symbol='', action='REDUCE',
                                qty_pct=self.scale_out_frac,
                                reason=f'scale_out_20: profit {profit_pct*100:.1f}% '
                                       f'AND score dropped {score_drop:.1f}pts '
                                       f'(peak {peak_score:.1f} -> {score:.1f})',
                                score=score)

        # 4. Score-based sell
        if score < self.sell_thr:
            return Decision(symbol='', action='SELL', qty_pct=1.0,
                            reason=f'score {score:.1f} < SELL_THRESHOLD {self.sell_thr:.0f}',
                            score=score)

        return Decision(symbol='', action='HOLD', qty_pct=0.0,
                        reason=f'score {score:.1f}; no exit triggered',
                        score=score)

    # --- Rotation gate -------------------------------------------------

    def should_rotate(self, *, candidate_score: float, holding_score: float,
                      holding_rsi: float = 50.0,
                      holding_profit_pct: float = 0.0) -> bool:
        result = EnhancedTop200StockAnalyzer._should_rotate(
            holding_score=holding_score,
            candidate_score=candidate_score,
            holding_rsi=holding_rsi,
            holding_profit_pct=holding_profit_pct,
            cfg=self._cfg,
        )
        return bool(result.get('should_rotate', False))
