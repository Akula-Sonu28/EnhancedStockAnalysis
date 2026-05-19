"""Persist BacktestResult to disk: JSON summary, CSV ledger, equity curve, Excel."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..engine import BacktestResult


RESULTS_DIR = Path(__file__).resolve().parents[1] / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _new_run_id(engine_label: str, mode: str) -> str:
    return f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{mode}_{engine_label}'


def write_result(result: 'BacktestResult', mode: str,
                 base_dir: Path = RESULTS_DIR,
                 extra_meta: dict | None = None) -> Path:
    """Write summary.json, trades.csv, equity.csv, rebalances.csv, report.xlsx.

    Returns the run directory path.
    """
    if not result.run_id:
        result.run_id = _new_run_id(result.engine_label, mode)
    out_dir = Path(base_dir) / result.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = dict(result.summary)
    summary['run_id'] = result.run_id
    summary['mode'] = mode
    summary['engine_label'] = result.engine_label
    summary['start_date'] = result.start_date.isoformat()
    summary['end_date'] = result.end_date.isoformat()
    if extra_meta:
        summary.update(extra_meta)

    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=2, default=str))

    # Trades
    trades_df = pd.DataFrame(result.trades) if result.trades else pd.DataFrame()
    if not trades_df.empty:
        trades_df.to_csv(out_dir / 'trades.csv', index=False)

    # Equity
    eq = result.equity_curve.rename('equity').to_frame()
    eq.index.name = 'date'
    if result.benchmark_curve is not None:
        b = result.benchmark_curve.rename('benchmark')
        eq = eq.join(b, how='outer')
    eq = eq.sort_index().ffill()
    eq['drawdown_pct'] = (eq['equity'] / eq['equity'].cummax() - 1) * 100
    eq.to_csv(out_dir / 'equity.csv')

    # Rebalances
    if result.rebalance_log:
        pd.DataFrame(result.rebalance_log).to_csv(out_dir / 'rebalances.csv', index=False)

    # Final positions
    if result.final_positions:
        pd.DataFrame(result.final_positions).to_csv(out_dir / 'final_positions.csv', index=False)

    # Excel single-file report
    try:
        _write_excel(out_dir / 'report.xlsx', summary, trades_df, eq,
                     result.rebalance_log, result.final_positions)
    except Exception as e:
        logging.warning(f'[reports] excel write failed: {e}')

    return out_dir


def _write_excel(path: Path, summary: dict, trades_df: pd.DataFrame,
                 equity_df: pd.DataFrame, rebalance_log: list,
                 final_positions: list) -> None:
    """Single .xlsx with: Summary / Trades / Equity / Rebalances / Final Positions."""
    summary_rows = [{'metric': k, 'value': v} for k, v in summary.items()]
    summary_df = pd.DataFrame(summary_rows)

    engine = 'xlsxwriter'
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        engine = 'openpyxl'

    with pd.ExcelWriter(path, engine=engine) as w:
        summary_df.to_excel(w, sheet_name='Summary', index=False)
        if not trades_df.empty:
            trades_df.to_excel(w, sheet_name='Trades', index=False)
        equity_df.to_excel(w, sheet_name='Equity')
        if rebalance_log:
            pd.DataFrame(rebalance_log).to_excel(w, sheet_name='Rebalances', index=False)
        if final_positions:
            pd.DataFrame(final_positions).to_excel(w, sheet_name='Final Positions', index=False)
