"""QMST Path-1 loader: fq pick + turbo columns from historical_outcomes.csv."""

from __future__ import annotations

from datetime import date
from typing import Iterator, List, Optional

import pandas as pd

from config import get_config

from .path1_loader import DateSnapshot, Path1Loader


def enrich_snapshot_df(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Add fq_score, turbo_pass, watchlist flags for QMST backtest."""
    if cfg is None:
        cfg = get_config()
    from src.flow_quality_oracle import enrich_oracle_columns
    from src.turbo_entry import enrich_dataframe_with_turbo, evaluate_turbo_entry_gate

    out = enrich_oracle_columns(df.copy(), cfg)
    out = enrich_dataframe_with_turbo(out, cfg)
    out['picking_rank'] = pd.to_numeric(out['fq_score'], errors='coerce')
    out['score_engine'] = out['picking_rank']
    turbo_pass = []
    for _, row in out.iterrows():
        gate = evaluate_turbo_entry_gate(row.to_dict(), cfg, new_this_week=0)
        turbo_pass.append(bool(gate.allowed))
    out['turbo_pass'] = turbo_pass
    return out


def enrich_snapshots(
    snapshots: List[DateSnapshot],
    cfg=None,
    min_universe: int = 20,
) -> List[DateSnapshot]:
    """Oracle + turbo enrich an existing snapshot list (e.g. Path2 rescore)."""
    out: List[DateSnapshot] = []
    for snap in snapshots:
        df = enrich_snapshot_df(snap.df, cfg)
        df = df.dropna(subset=['score_engine', 'current_price'])
        if len(df) < min_universe:
            continue
        out.append(DateSnapshot(decision_date=snap.decision_date, df=df.reset_index(drop=True)))
    return out


class QmstLoader(Path1Loader):
    """Dense-window snapshots enriched with oracle pick + turbo entry fields.

    Ranking column ``score_engine`` is set to ``fq_score`` (QMST pick layer).
    Adds: fq_score, picking_rank, turbo_score, on_oracle_watchlist, turbo_pass.
    """

    def __init__(self, **kwargs):
        super().__init__(engine='v2', **kwargs)
        self._cfg = get_config()

    def iter_snapshots(
        self,
        start: Optional[date | str] = None,
        end: Optional[date | str] = None,
        min_universe: int = 20,
    ) -> Iterator[DateSnapshot]:
        for snap in super().iter_snapshots(start=start, end=end, min_universe=min_universe):
            df = enrich_snapshot_df(snap.df, self._cfg)
            df = df.dropna(subset=['score_engine', 'current_price'])
            if len(df) < min_universe:
                continue
            yield DateSnapshot(decision_date=snap.decision_date, df=df.reset_index(drop=True))
