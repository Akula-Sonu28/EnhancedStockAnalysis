"""QMST pick-layer quality gates (FQ/RK/VL floors on oracle watchlist)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class PickGateResult:
    allowed: bool
    status: str
    reasons: List[str] = field(default_factory=list)


def _f(val, default=0.0) -> float:
    try:
        v = float(val)
        return default if (np.isnan(v) or np.isinf(v)) else v
    except (TypeError, ValueError):
        return default


def _cfg(cfg, key: str, default):
    return getattr(cfg, key, default) if cfg is not None else default


def pick_gates_enabled(cfg=None, override: Optional[bool] = None) -> bool:
    if override is not None:
        return bool(override)
    return bool(_cfg(cfg, 'QMST_PICK_GATES_ENABLED', False))


def evaluate_pick_gates(
    row: Dict[str, Any],
    cfg=None,
    enabled: Optional[bool] = None,
) -> PickGateResult:
    """Return allowed=False when FQ/RK/VL floors fail (watchlist refinement)."""
    if not pick_gates_enabled(cfg, enabled):
        return PickGateResult(True, 'OFF', [])

    fq = _f(row.get('hybrid_fundamental_quality', row.get('FQ', 0)))
    rk = _f(row.get('hybrid_risk_adjustment', row.get('RK', 0)))
    vl = _f(row.get('hybrid_value', row.get('VL', 0)))

    fq_min = _f(_cfg(cfg, 'QMST_PICK_FQ_MIN', 48.0))
    rk_min = _f(_cfg(cfg, 'QMST_PICK_RK_MIN', 42.0))
    vl_min = _f(_cfg(cfg, 'QMST_PICK_VL_MIN', 45.0))
    vl_gate = bool(_cfg(cfg, 'QMST_PICK_VL_GATE', False))

    reasons: List[str] = []
    if fq_min > 0 and fq < fq_min:
        reasons.append(f'FQ {fq:.0f}<{fq_min:.0f}')
    if rk_min > 0 and rk < rk_min:
        reasons.append(f'RK {rk:.0f}<{rk_min:.0f}')
    if vl_gate and vl_min > 0 and vl < vl_min:
        reasons.append(f'VL {vl:.0f}<{vl_min:.0f}')

    if reasons:
        return PickGateResult(False, 'BLOCK', reasons)
    return PickGateResult(True, 'PASS', [])
