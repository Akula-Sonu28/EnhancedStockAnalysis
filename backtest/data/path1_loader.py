"""Path 1 data loader: pull dense v2 score rows from historical_outcomes.csv.

The dense v2 window is the only place where every hybrid_* component plus
forward returns are populated. This loader filters that window, sorts by
date, and exposes per-date snapshots the engine can score.

It also synthesises score_v2 from the live calibrated weights, applied via
the same deviation-from-neutral formula that
scripts/walkforward_v2_validation._synthesise_v2_score uses, so the result
matches the live engine's score computation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_OUTCOMES = REPO_ROOT / 'data' / 'historical_outcomes.csv'
V2_WEIGHTS = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'

HYBRID_COMPONENTS = [
    'hybrid_fundamental_quality',
    'hybrid_momentum_technical',
    'hybrid_volume_strength',
    'hybrid_multi_timeframe',
    'hybrid_ml_signal',
    'hybrid_risk_adjustment',
    'hybrid_growth',
    'hybrid_value',
]

COMPONENT_TO_WEIGHT_KEY = {
    'hybrid_fundamental_quality': 'fundamental_quality',
    'hybrid_momentum_technical':  'momentum_technical',
    'hybrid_volume_strength':     'volume_strength',
    'hybrid_multi_timeframe':     'multi_timeframe',
    'hybrid_ml_signal':           'ml_signal',
    'hybrid_risk_adjustment':     'risk_adjustment',
    'hybrid_growth':              'growth',
    'hybrid_value':               'value',
}


def _synthesise_v2_score(df: pd.DataFrame, weights: dict) -> pd.Series:
    """Apply v2 weights to per-row hybrid_* components.

    Formula (deviation-from-neutral, matches walkforward_v2_validation):
        v2 = 50 + sum_i (component_i - 50) * weight_i

    Rows with no available components return NaN.
    """
    deviation = pd.Series(0.0, index=df.index)
    has_any = pd.Series(False, index=df.index)
    for col, wkey in COMPONENT_TO_WEIGHT_KEY.items():
        if col not in df.columns:
            continue
        w = float(weights.get(wkey, 0.0))
        if w == 0.0:
            continue
        comp = pd.to_numeric(df[col], errors='coerce')
        contrib = (comp - 50.0) * w
        has_any = has_any | comp.notna()
        deviation = deviation.add(contrib.fillna(0.0), fill_value=0.0)
    score = 50.0 + deviation
    score = score.clip(lower=0.0, upper=100.0)
    return score.where(has_any, other=np.nan)


def _synthesise_v1_score(df: pd.DataFrame) -> pd.Series:
    """v1's blended score is already in the `score` column of the source.
    Provided as a sibling helper so callers can request 'v1' uniformly."""
    if 'score' not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return pd.to_numeric(df['score'], errors='coerce')


# --- Public loader API ----------------------------------------------------

@dataclass
class DateSnapshot:
    """All eligible (symbol, score, components) for a single decision date."""
    decision_date: date
    df: pd.DataFrame   # one row per symbol; columns include score (engine-specific) and metadata


class Path1Loader:
    """Load dense v2 rows and expose them per decision date.

    Use as:
        loader = Path1Loader(engine='v2')
        for snap in loader.iter_snapshots(start='2026-03-17', end='2026-05-07'):
            ... # decide actions on snap.df
    """

    def __init__(self, engine: str = 'v2',
                 outcomes_path: Path = HISTORICAL_OUTCOMES,
                 weights_path: Path = V2_WEIGHTS):
        if engine not in ('v1', 'v2'):
            raise ValueError(f'engine must be v1 or v2, got {engine!r}')
        self.engine = engine
        self.outcomes_path = Path(outcomes_path)
        self.weights_path = Path(weights_path)
        self._df: Optional[pd.DataFrame] = None
        self._weights: Optional[dict] = None

    def _load_weights(self) -> dict:
        if self._weights is not None:
            return self._weights
        if not self.weights_path.exists():
            raise FileNotFoundError(f'v2 weights missing: {self.weights_path}')
        data = json.loads(self.weights_path.read_text())
        self._weights = data.get('weights') or {}
        return self._weights

    def _load_outcomes(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        df = pd.read_csv(self.outcomes_path, parse_dates=['date'])
        df = df.dropna(subset=['score'])
        for c in HYBRID_COMPONENTS + ['return_7d', 'return_30d', 'current_price']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        self._df = df
        return df

    def v1_window(self) -> tuple[Optional[date], Optional[date]]:
        """Window where v1 'score' + current_price are populated (broader than
        the v2 dense window — back to 2023 in this repo)."""
        df = self._load_outcomes()
        cols = [c for c in ('score', 'current_price') if c in df.columns]
        if not cols:
            return None, None
        sub = df.dropna(subset=cols)
        if sub.empty:
            return None, None
        return sub['date'].min().date(), sub['date'].max().date()

    def dense_window(self) -> tuple[Optional[date], Optional[date]]:
        """Return (start, end) of the densest v2 window where every
        core hybrid_* component is non-null AND current_price is available.

        Note: we deliberately do NOT require return_30d here — that column
        only matures 30+ days after a row's date, so requiring it would
        artificially shrink the window. The engine marks positions to
        current_price each day, so forward returns aren't needed for the
        backtest itself (only for the offline IC checks done elsewhere).
        """
        df = self._load_outcomes()
        cols = HYBRID_COMPONENTS[:6] + ['current_price']
        cols = [c for c in cols if c in df.columns]
        if not cols:
            return None, None
        dense = df.dropna(subset=cols)
        if dense.empty:
            return None, None
        return dense['date'].min().date(), dense['date'].max().date()

    def iter_snapshots(self, start: Optional[date | str] = None,
                       end: Optional[date | str] = None,
                       min_universe: int = 20) -> Iterator[DateSnapshot]:
        """Yield one DateSnapshot per decision date in [start, end].

        Each snapshot.df has at minimum: symbol, score (engine-specific),
        the per-component hybrid_* columns when available, current_price,
        regime, and any return_7d / return_30d on file.
        """
        df = self._load_outcomes().copy()
        if isinstance(start, str):
            start = pd.Timestamp(start).date()
        if isinstance(end, str):
            end = pd.Timestamp(end).date()
        if start is not None:
            df = df[df['date'] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df['date'] <= pd.Timestamp(end)]
        if df.empty:
            return

        if self.engine == 'v1':
            df['score_engine'] = _synthesise_v1_score(df)
        else:
            w = self._load_weights()
            df['score_engine'] = _synthesise_v2_score(df, w)
        df = df.dropna(subset=['score_engine'])

        for d, grp in df.groupby('date'):
            grp = grp.dropna(subset=['current_price'])
            if len(grp) < min_universe:
                continue
            yield DateSnapshot(decision_date=d.date(), df=grp.reset_index(drop=True))


def _load_complete_data() -> Optional[pd.DataFrame]:
    """Load the latest report's 'Complete Data' sheet, or None if unavailable."""
    rep_dir = REPO_ROOT / 'reports'
    reports = sorted(rep_dir.glob('Enhanced_Stock_Report_*.xlsx'))
    if not reports:
        return None
    latest = reports[-1]
    try:
        return pd.read_excel(latest, sheet_name='Complete Data')
    except Exception as e:
        logging.warning(f'[path1_loader] cannot read {latest}: {e}')
        return None


def first_market_cap_lookup() -> dict[str, float]:
    """Best-effort market cap (crores) per symbol, sourced from the latest
    Enhanced_Stock_Report Complete Data sheet. Used for slippage tier.

    Returns empty dict if no report is available; callers should fall back
    to a default tier (mid) in that case.
    """
    df = _load_complete_data()
    if df is None:
        return {}
    sym_col = next((c for c in df.columns if str(c).lower() == 'symbol'), None)
    mc_col = next((c for c in df.columns
                   if 'market' in str(c).lower() and 'cap' in str(c).lower()), None)
    if not sym_col or not mc_col:
        return {}
    out: dict[str, float] = {}
    for _, r in df.iterrows():
        s = str(r[sym_col]).strip()
        try:
            v = float(r[mc_col])
            if v > 0:
                out[s] = v
        except (TypeError, ValueError):
            continue
    return out


def first_sector_lookup() -> dict[str, str]:
    """Best-effort sector per symbol, sourced from the latest Enhanced_Stock_Report.

    Returns empty dict if no report or no sector column.
    """
    df = _load_complete_data()
    if df is None:
        return {}
    sym_col = next((c for c in df.columns if str(c).lower() == 'symbol'), None)
    sec_col = next((c for c in df.columns
                    if str(c).lower() in ('sector', 'industry')), None)
    if not sym_col or not sec_col:
        return {}
    out: dict[str, str] = {}
    for _, r in df.iterrows():
        s = str(r[sym_col]).strip()
        sec = r[sec_col]
        if pd.notna(sec):
            out[s] = str(sec).strip()
    return out
