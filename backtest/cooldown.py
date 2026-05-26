"""Recent-buy cooldown for backtest engine (mirrors live Q127 / config)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

_BYPASS_TIERS = frozenset({
    'EMERGENCY', 'HARD_STOP', 'SOFT_STOP', 'THESIS_BREAK',
    'TRAILING_STOP', 'SCALE_OUT_20',
})


@dataclass(frozen=True)
class CooldownPolicy:
    name: str
    enabled: bool = False
    cooldown_days: int = 0
    profit_bypass_pct: Optional[float] = None
    trailing_bypass: bool = False
    scale_out_bypass: bool = False
    hard_stop_pct: float = -0.10
    v2_collapse: float = 30.0
    v2_streak: int = 2

    @staticmethod
    def disabled() -> CooldownPolicy:
        return CooldownPolicy(name='off', enabled=False)


def _cfg_defaults() -> tuple[float, float, int]:
    try:
        from config import get_config
        cfg = get_config()
        return (
            float(getattr(cfg, 'REGIME_FLIP_HARD_STOP_PCT', -0.10)),
            float(getattr(cfg, 'REGIME_FLIP_V2_COLLAPSE', 30.0)),
            int(getattr(cfg, 'REGIME_FLIP_V2_STREAK', 2)),
        )
    except Exception:
        return -0.10, 30.0, 2


def resolve_policy(name: str) -> CooldownPolicy:
    """Named policies for CLI / comparison grids."""
    key = (name or 'off').strip().lower()
    hard, v2_col, v2_str = _cfg_defaults()
    try:
        from config import get_config
        cfg = get_config()
        cd5 = int(getattr(cfg, 'REGIME_FLIP_COOLDOWN_DAYS', 5))
        cd7 = int(getattr(cfg, 'REGIME_FLIP_COOLDOWN_DAYS', 7))
        if hasattr(cfg, 'REGIME_FLIP_COOLDOWN_DAYS'):
            cd7 = max(cd5, 7) if cd5 < 7 else cd5
    except Exception:
        cd5, cd7 = 5, 7

    base = dict(hard_stop_pct=hard, v2_collapse=v2_col, v2_streak=v2_str)
    registry: dict[str, CooldownPolicy] = {
        'off': CooldownPolicy.disabled(),
        'prod_3d': CooldownPolicy(
            name='prod_3d', enabled=True, cooldown_days=3, **base,
        ),
        'prod_5d': CooldownPolicy(
            name='prod_5d', enabled=True, cooldown_days=cd5, **base,
        ),
        'prod_7d': CooldownPolicy(
            name='prod_7d', enabled=True, cooldown_days=7, **base,
        ),
        'profit_3pct_5d': CooldownPolicy(
            name='profit_3pct_5d', enabled=True, cooldown_days=cd5,
            profit_bypass_pct=0.03, **base,
        ),
        'profit_5pct_5d': CooldownPolicy(
            name='profit_5pct_5d', enabled=True, cooldown_days=cd5,
            profit_bypass_pct=0.05, **base,
        ),
        'profit_8pct_5d': CooldownPolicy(
            name='profit_8pct_5d', enabled=True, cooldown_days=cd5,
            profit_bypass_pct=0.08, **base,
        ),
        'profit_5pct_3d': CooldownPolicy(
            name='profit_5pct_3d', enabled=True, cooldown_days=3,
            profit_bypass_pct=0.05, **base,
        ),
        'profit_5pct_trail_5d': CooldownPolicy(
            name='profit_5pct_trail_5d', enabled=True, cooldown_days=cd5,
            profit_bypass_pct=0.05, trailing_bypass=True, scale_out_bypass=True,
            **base,
        ),
        'profit_3pct_trail_5d': CooldownPolicy(
            name='profit_3pct_trail_5d', enabled=True, cooldown_days=cd5,
            profit_bypass_pct=0.03, trailing_bypass=True, scale_out_bypass=True,
            **base,
        ),
    }
    if key not in registry:
        raise ValueError(f'Unknown cooldown policy {name!r}; choose from {sorted(registry)}')
    return registry[key]


def should_suppress_sell(
    *,
    policy: CooldownPolicy,
    entry_date: date,
    as_of: date,
    profit_pct: float,
    current_v2_score: float,
    current_regime: str,
    exit_reason: str = '',
    hard_stop_tier: str = 'NONE',
    score_history: Optional[list] = None,
) -> tuple[bool, str]:
    """Return (suppress, reason). True => block the sell (keep holding)."""
    if not policy.enabled:
        return False, ''

    days_since = (as_of - entry_date).days
    if days_since < 0 or days_since > policy.cooldown_days:
        return False, ''

    tier = str(hard_stop_tier or '').upper().strip()
    if tier in _BYPASS_TIERS:
        return False, ''

    reason_up = str(exit_reason or '').upper()
    if any(k in reason_up for k in (
        'EMERGENCY', 'STOP LOSS', 'THESIS BREAK', 'CIRCUIT BREAKER', 'CRISIS',
    )):
        return False, ''

    try:
        if float(profit_pct) <= policy.hard_stop_pct:
            return False, ''
    except (TypeError, ValueError):
        pass

    if policy.profit_bypass_pct is not None:
        try:
            if float(profit_pct) >= policy.profit_bypass_pct:
                return False, ''
        except (TypeError, ValueError):
            pass

    if policy.trailing_bypass and 'TRAILING' in reason_up:
        return False, ''

    if policy.scale_out_bypass and 'SCALE' in reason_up:
        return False, ''

    try:
        if current_v2_score is not None and float(current_v2_score) < policy.v2_collapse:
            hist = score_history or []
            consec = 0
            for sc in hist:
                try:
                    if float(sc) < policy.v2_collapse:
                        consec += 1
                        if consec >= policy.v2_streak:
                            return False, ''
                    else:
                        consec = 0
                except (TypeError, ValueError):
                    consec = 0
    except (TypeError, ValueError):
        pass

    regime = str(current_regime or '').upper().strip() or 'UNKNOWN'
    return True, (
        f'RECENT_BUY_COOLDOWN: entry {days_since}d ago, regime={regime}, '
        f'within {policy.cooldown_days}d hold window'
    )
