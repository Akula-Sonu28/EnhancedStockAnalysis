"""CLI runner for Path 1 (high-fidelity) and Path 2 (medium-fidelity) backtests.

Usage:
    python3 -m backtest.runner path1 --capital 100000 --top-n 10 --rebalance weekly
    python3 -m backtest.runner path1 --capital 100000 --top-n 10 --engine v1
    python3 -m backtest.runner path2 --capital 100000 --top-n 10 --months 6 --rebalance weekly
    python3 -m backtest.runner compare --capital 100000 --top-n 10 --rebalance weekly

Path 1 reads data/historical_outcomes.csv directly (no re-scoring); the dense
window is auto-detected. Path 2 requires the re-scoring pipeline (see
backtest/data/path2_rescore.py) and is implemented as a stub for now — it
will be wired in Phase 11.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backtest.cooldown import resolve_policy
from backtest.engine import BacktestEngine, EngineConfig
from backtest.data.path1_loader import Path1Loader
from backtest.data.prices import PriceCache
from backtest.reports.writers import write_result, RESULTS_DIR


def _print_summary(label: str, result) -> None:
    print(f'\n{"=" * 76}\n  BACKTEST RESULT [{label}]  '
          f'engine={result.engine_label}  '
          f'{result.start_date} -> {result.end_date}\n{"=" * 76}')
    keys_order = [
        'initial_capital', 'final_equity',
        'total_return_pct', 'cagr_pct',
        'volatility_pct', 'sharpe', 'sortino', 'calmar',
        'max_drawdown_pct', 'max_dd_peak_date', 'max_dd_trough_date',
        'trades_total', 'trades_win_rate_pct',
        'avg_win_inr', 'avg_loss_inr', 'profit_factor',
        'turnover_pct_of_avg_eq', 'stcg_paid', 'ltcg_paid',
        'open_positions',
        'benchmark_total_return_pct', 'benchmark_cagr_pct',
        'benchmark_max_dd_pct', 'excess_return_pct',
    ]
    for k in keys_order:
        if k in result.summary:
            v = result.summary[k]
            if isinstance(v, float):
                print(f'  {k:32s}: {v:>14,.4f}')
            else:
                print(f'  {k:32s}: {v}')


def run_path1(args) -> int:
    loader = Path1Loader(engine=args.engine)
    dense_start, dense_end = loader.dense_window()
    if dense_start is None:
        print('ERROR: no dense v2 window found in historical_outcomes.csv')
        return 2

    start = max(dense_start, args.start) if args.start else dense_start
    end = min(dense_end, args.end) if args.end else dense_end

    snapshots = list(loader.iter_snapshots(
        start=start, end=end, min_universe=args.min_universe,
    ))
    if not snapshots:
        print(f'ERROR: no snapshots in window [{start} -> {end}] '
              f'with min_universe={args.min_universe}')
        return 2

    print(f'Path 1: engine={args.engine}, dense window {dense_start} -> {dense_end}')
    print(f'        running {start} -> {end}, {len(snapshots)} decision dates')

    cfg = _engine_config_from_args(args)

    engine = BacktestEngine(engine_label=args.engine, cfg=cfg)
    result = engine.run(snapshots)

    out_dir = write_result(result, mode='path1',
                           extra_meta={'cli_args': vars(args)})
    _print_summary('PATH 1', result)
    print(f'\n  Artifacts: {out_dir}')
    return 0


def run_path2(args) -> int:
    """Path 2: trailing N-month backtest.

    --engine v1: uses the v1 'score' column from historical_outcomes.csv
                 (populated back to 2023). Fast, no re-scoring needed.

    --engine v2: re-computes v2 components from raw OHLCV using the current
                 calibrated weights. ml_signal is suppressed (no historical
                 ML model). fundamentals/growth/value have zero v2 weight
                 so absent point-in-time data is irrelevant. Survivorship
                 bias: universe = today's Nifty 200.
    """
    months_back = args.months
    end = args.end or date.today()
    start = args.start or _months_before(end, months_back)

    if args.engine == 'v2':
        from backtest.data.path2_rescore import Path2Rescorer
        rescorer = Path2Rescorer()
        print(f'Path 2: engine=v2 (re-scored from OHLCV), '
              f'trailing {months_back}m window {start} -> {end}, '
              f'universe={len(rescorer.universe)} symbols')
        snapshots = rescorer.build_snapshots(start, end, cadence=args.rebalance)
    else:
        loader = Path1Loader(engine='v1')
        full_start, full_end = loader.v1_window()
        if full_start is None:
            print('ERROR: no v1 data window in historical_outcomes.csv')
            return 2
        start = max(full_start, start)
        end = min(full_end, end)
        print(f'Path 2: engine=v1 (from historical_outcomes.csv), '
              f'window {start} -> {end}')
        snapshots = list(loader.iter_snapshots(
            start=start, end=end, min_universe=args.min_universe,
        ))
    if not snapshots:
        print(f'ERROR: no snapshots in window [{start} -> {end}]')
        return 2

    print(f'Path 2: engine={args.engine}, trailing {months_back}m window '
          f'{start} -> {end}, {len(snapshots)} decision dates')

    cfg = _engine_config_from_args(args)
    engine = BacktestEngine(engine_label=args.engine, cfg=cfg)
    result = engine.run(snapshots)
    out_dir = write_result(result, mode='path2', extra_meta={'cli_args': vars(args)})
    _print_summary(f'PATH 2 ({months_back}m)', result)
    print(f'\n  Artifacts: {out_dir}')
    return 0


def _months_before(d: date, months: int) -> date:
    """Return d - months (calendar arithmetic; clamp day for short months)."""
    from calendar import monthrange
    y = d.year
    m = d.month - months
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


def run_compare(args) -> int:
    """Run both engines (v1 & v2) under identical conditions and emit a summary."""
    outputs = {}
    for engine in ('v1', 'v2'):
        a = argparse.Namespace(**vars(args))
        a.engine = engine
        loader = Path1Loader(engine=engine)
        ds, de = loader.dense_window()
        if ds is None:
            print(f'ERROR: no dense window for engine {engine}')
            return 2
        start = max(ds, args.start) if args.start else ds
        end = min(de, args.end) if args.end else de
        snaps = list(loader.iter_snapshots(start=start, end=end,
                                           min_universe=args.min_universe))
        if not snaps:
            print(f'ERROR: no snapshots for {engine}')
            return 2
        cfg = _engine_config_from_args(args)
        eng = BacktestEngine(engine_label=engine, cfg=cfg)
        res = eng.run(snaps)
        out_dir = write_result(res, mode='path1',
                               extra_meta={'cli_args': vars(args), 'pair': 'compare'})
        outputs[engine] = (res, out_dir)
        _print_summary(f'PATH 1 — {engine.upper()}', res)

    v1_res, _ = outputs['v1']
    v2_res, _ = outputs['v2']
    print(f'\n{"=" * 76}\n  HEAD-TO-HEAD\n{"=" * 76}')
    print(f'  v1 final: Rs {v1_res.summary["final_equity"]:>12,.0f}  '
          f'({v1_res.summary["total_return_pct"]:+.2f}%)')
    print(f'  v2 final: Rs {v2_res.summary["final_equity"]:>12,.0f}  '
          f'({v2_res.summary["total_return_pct"]:+.2f}%)')
    diff = v2_res.summary['final_equity'] - v1_res.summary['final_equity']
    print(f'  edge:     Rs {diff:>+12,.0f}  '
          f'({v2_res.summary["total_return_pct"] - v1_res.summary["total_return_pct"]:+.2f}pp)')
    return 0


def _engine_config_from_args(args) -> EngineConfig:
    cd = resolve_policy(getattr(args, 'cooldown', 'off'))
    return EngineConfig(
        initial_capital=args.capital,
        target_positions=args.top_n,
        max_positions=max(args.top_n + 5, args.top_n),
        sector_cap_pct=args.sector_cap,
        rebalance=args.rebalance,
        min_universe=args.min_universe,
        allow_rotation=not args.no_rotation,
        benchmark_symbol=args.benchmark,
        selection_mode=args.selection,
        min_entry_score=args.min_entry_score,
        cooldown_policy=cd,
    )


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument('--capital', type=float, default=100_000.0,
                   help='Initial capital (default Rs 1,00,000)')
    p.add_argument('--top-n', type=int, default=10,
                   help='Target number of concurrent positions')
    p.add_argument('--rebalance', choices=('daily', 'weekly', 'monthly'),
                   default='weekly')
    p.add_argument('--sector-cap', type=float, default=30.0,
                   help='Max %% of equity in any single sector (default 30)')
    p.add_argument('--min-universe', type=int, default=20,
                   help='Skip a date if fewer than this many eligible symbols')
    p.add_argument('--no-rotation', action='store_true',
                   help='Disable rotation gate (only buy into empty slots)')
    p.add_argument('--selection', choices=('rank', 'threshold'), default='rank',
                   help='rank: buy top-N by score (stress-test, default); '
                        'threshold: only buy when score >= BUY_THRESHOLD (production-faithful)')
    p.add_argument('--min-entry-score', type=float, default=45.0,
                   help='Floor for rank mode (default 45, ~HOLD level)')
    p.add_argument('--benchmark', default='^NSEI',
                   help='yfinance ticker for benchmark; empty/none to skip')
    p.add_argument('--start', type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                   default=None)
    p.add_argument('--end', type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                   default=None)
    p.add_argument('--cooldown', default='off',
                   help='Recent-buy cooldown policy (off, prod_5d, profit_5pct_5d, …); '
                        'run scripts/backtest_cooldown_comparison.py for grid')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Backtest engine for v2 scoring model')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('path1', help='High-fidelity 7-week backtest')
    p1.add_argument('--engine', choices=('v1', 'v2'), default='v2')
    _add_common(p1)

    p2 = sub.add_parser('path2', help='Medium-fidelity 6-month re-scoring backtest')
    p2.add_argument('--engine', choices=('v1', 'v2'), default='v2')
    p2.add_argument('--months', type=int, default=6)
    _add_common(p2)

    pc = sub.add_parser('compare', help='Run v1 and v2 head-to-head (path1)')
    _add_common(pc)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='[backtest] %(message)s')

    if args.cmd == 'path1':
        return run_path1(args)
    if args.cmd == 'path2':
        return run_path2(args)
    if args.cmd == 'compare':
        return run_compare(args)
    return 1


if __name__ == '__main__':
    sys.exit(main())
