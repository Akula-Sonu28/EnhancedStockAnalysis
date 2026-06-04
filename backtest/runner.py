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
from backtest.data.qmst_loader import QmstLoader, enrich_snapshots
from backtest.qmst_strategy import QMSTStrategyAdapter
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


def run_qmst(args) -> int:
    """QMST stack backtest: fq pick (top 20%) + turbo entry + VMQ exits."""
    from config import get_config
    _qcfg = get_config()
    if getattr(args, 'day3', False):
        include_day3 = True
    elif getattr(args, 'no_day3', False):
        include_day3 = False
    else:
        include_day3 = bool(getattr(_qcfg, 'VMQ_DAY3_ENABLED', False))
    if getattr(args, 'pick_gates', False):
        pick_gates = True
    else:
        pick_gates = bool(getattr(_qcfg, 'QMST_PICK_GATES_ENABLED', False))
    months = getattr(args, 'months', None)

    if months:
        end = args.end or date.today()
        start = args.start or _months_before(end, months)
        from backtest.data.path2_rescore import Path2Rescorer
        print(f'QMST rescore: trailing {months}m OHLCV window {start} -> {end}')
        rescorer = Path2Rescorer()
        raw = rescorer.build_snapshots(start, end, cadence=args.rebalance)
        snapshots = enrich_snapshots(raw, min_universe=args.min_universe)
        dense_start, dense_end = start, end
    else:
        loader = QmstLoader()
        dense_start, dense_end = loader.dense_window()
        if dense_start is None:
            print('ERROR: no dense hybrid window in historical_outcomes.csv')
            return 2
        start = max(dense_start, args.start) if args.start else dense_start
        end = min(dense_end, args.end) if args.end else dense_end
        snapshots = list(loader.iter_snapshots(
            start=start, end=end, min_universe=args.min_universe,
        ))

    if not snapshots:
        print(f'ERROR: no QMST snapshots in [{start} -> {end}]')
        return 2

    mode_label = f'{months}m rescore' if months else 'path1 dense'
    if include_day3:
        if getattr(_qcfg, 'VMQ_DAY3_REGIME_GATED', True):
            print('QMST: fq pick + turbo entry + VMQ exits + day-3/5 (regime-gated)')
        else:
            print('QMST: fq pick + turbo entry + VMQ exits + day-3/5 validation')
    else:
        print('QMST: fq pick + turbo entry + VMQ exits (day-3/5 OFF — production default)')
    if pick_gates:
        fq_min = getattr(_qcfg, 'QMST_PICK_FQ_MIN', 48.0)
        rk_min = getattr(_qcfg, 'QMST_PICK_RK_MIN', 42.0)
        print(f'      pick gates ON: FQ>={fq_min:.0f}, RK>={rk_min:.0f}')
    print(f'      mode={mode_label}, running {start} -> {end}, '
          f'{len(snapshots)} decision dates')

    cfg = _engine_config_from_args(args)
    cfg.rank_column = 'fq_score'
    cfg.watchlist_column = 'on_oracle_watchlist'
    cfg.require_turbo_pass = True
    cfg.apply_min_entry_score = False
    cfg.allow_rotation = False

    strategy = QMSTStrategyAdapter(include_day3=include_day3, pick_gates_enabled=pick_gates)
    engine = BacktestEngine(engine_label='qmst', cfg=cfg, strategy=strategy)
    result = engine.run(snapshots)

    result.summary['qmst_entries_passed'] = strategy.entries_passed
    result.summary['qmst_entries_blocked'] = strategy.entries_blocked
    result.summary['qmst_pick_gates_blocked'] = strategy.pick_gates_blocked
    result.summary['pick_gates_enabled'] = pick_gates
    result.summary['vmq_day3_exits'] = strategy.vmq_day3_exits
    result.summary['vmq_day5_exits'] = strategy.vmq_day5_exits
    result.summary['include_day3'] = include_day3
    result.summary['vmq_day3_enabled'] = bool(getattr(_qcfg, 'VMQ_DAY3_ENABLED', False))
    if include_day3:
        result.summary['vmq_day3_regime_gated'] = bool(
            getattr(_qcfg, 'VMQ_DAY3_REGIME_GATED', True)
        )
    else:
        result.summary['vmq_day3_regime_gated'] = False
    result.summary['months'] = months
    result.summary['strategy'] = 'QMST (fq pick + turbo + VMQ)'

    out_dir = write_result(result, mode='qmst', extra_meta={'cli_args': vars(args)})
    _print_summary('QMST', result)
    print(f'\n  Turbo entries passed (gate checks): {strategy.entries_passed}')
    print(f'  Turbo entries blocked:              {strategy.entries_blocked}')
    if include_day3:
        print(f'  VMQ day-3 exits:                    {strategy.vmq_day3_exits}')
        print(f'  VMQ day-5 exits:                    {strategy.vmq_day5_exits}')
    print(f'\n  Artifacts: {out_dir}')
    return 0


def _run_lvm_variant(
    args,
    *,
    score_mode: str,
    rank_column: str,
    eligible_column: str,
    strategy_label: str,
    write_mode: str,
) -> tuple[int, list]:
    """Run LVM-family backtest; returns (exit_code, list of BacktestResult)."""
    from backtest.lvm_snapshot_builder import LvmSnapshotBuilder
    from backtest.lvm_strategy import LVMStrategyAdapter

    months = getattr(args, 'months', 24) or 24
    end = args.end or date.today()
    start = args.start or _months_before(end, months)
    stop_pcts = [float(args.stop_pct)]
    if getattr(args, 'compare_stops', False):
        stop_pcts = [10.0, 15.0]

    pit_only = bool(getattr(args, 'pit_only', False)) and score_mode == 'quality_lvm'
    pit_tag = ' [real Screener only]' if pit_only else ''
    print(f'{strategy_label}: Nifty 200, {start} -> {end}, rebalance={args.rebalance}, '
          f'vol_mode={args.vol_mode}, score={score_mode}{pit_tag}')
    builder = LvmSnapshotBuilder(
        vol_mode=args.vol_mode, score_mode=score_mode, pit_only=pit_only,
    )
    if getattr(args, 'warmup', True):
        print(f'  Warming OHLCV for {len(builder.universe)} symbols...')
        ok = sum(1 for v in builder.warmup_prices(start, end).values() if v)
        print(f'  Price cache warmed: {ok}/{len(builder.universe)} symbols')

    snapshots = builder.build_snapshots(
        start, end, cadence=args.rebalance, use_cache=not args.no_cache,
    )
    if not snapshots:
        print(f'ERROR: no snapshots in [{start} -> {end}] ({score_mode})')
        return 2, []

    print(f'  Built {len(snapshots)} rebalance snapshots')
    results = []
    last_code = 0
    for stop in stop_pcts:
        cfg = _engine_config_from_args(args)
        cfg.rank_column = rank_column
        cfg.lvm_eligible_column = eligible_column
        cfg.apply_min_entry_score = False
        cfg.allow_rotation = False
        cfg.require_turbo_pass = False
        cfg.lvm_full_rebalance = True
        cfg.momentum_exhaustion_enabled = False
        cfg.monthly_cash_injection_inr = float(getattr(args, 'monthly_injection', 0) or 0)
        cfg.cooldown_policy = resolve_policy('off')

        strategy = LVMStrategyAdapter(stop_pct=stop)
        label = f'{write_mode}_stop{int(stop)}'
        engine = BacktestEngine(engine_label=label, cfg=cfg, strategy=strategy)
        result = engine.run(snapshots)

        result.summary['strategy'] = strategy_label
        result.summary['lvm_stop_pct'] = stop
        result.summary['vol_mode'] = args.vol_mode
        result.summary['score_mode'] = score_mode
        result.summary['pit_only'] = pit_only
        result.summary['universe'] = 'Nifty200'
        result.summary['months'] = months
        result.summary['lvm_stop_exits'] = strategy.stop_exits
        result.summary['monthly_injection_inr'] = cfg.monthly_cash_injection_inr

        out_dir = write_result(result, mode=write_mode, extra_meta={
            'cli_args': vars(args), 'stop_pct': stop, 'score_mode': score_mode,
        })
        _print_summary(f'{strategy_label} (-{stop:.0f}% stop)', result)
        print(f'\n  Stop-trigger exits: {strategy.stop_exits}')
        print(f'  Capital injected:   Rs {result.summary.get("capital_injected_inr", 0):,.0f}')
        print(f'  Artifacts: {out_dir}')
        print()
        results.append(result)
    return last_code, results


def run_lvm(args) -> int:
    """LowVol→Mom monthly backtest (Nifty 200, production ranker)."""
    code, _ = _run_lvm_variant(
        args,
        score_mode='lvm',
        rank_column='lowvol_mom_score',
        eligible_column='lowvol_mom_eligible',
        strategy_label='LowVol→Mom',
        write_mode='lvm',
    )
    return code


def run_quality_lvm(args) -> int:
    """Quality + LowVol→Mom monthly backtest (PIT Screener fundamentals)."""
    code, _ = _run_lvm_variant(
        args,
        score_mode='quality_lvm',
        rank_column='quality_lvm_score',
        eligible_column='quality_lvm_eligible',
        strategy_label='Quality+LowVol→Mom',
        write_mode='quality_lvm',
    )
    return code


def run_compare_lvm(args) -> int:
    """Head-to-head: current LVM vs Quality+LVM on identical window and stops."""
    if getattr(args, 'compare_stops', False):
        print('compare-lvm uses a single stop; ignoring --compare-stops')
        args.compare_stops = False

    code_a, res_a = _run_lvm_variant(
        args,
        score_mode='lvm',
        rank_column='lowvol_mom_score',
        eligible_column='lowvol_mom_eligible',
        strategy_label='LowVol→Mom',
        write_mode='lvm',
    )
    if code_a != 0:
        return code_a
    code_b, res_b = _run_lvm_variant(
        args,
        score_mode='quality_lvm',
        rank_column='quality_lvm_score',
        eligible_column='quality_lvm_eligible',
        strategy_label='Quality+LowVol→Mom',
        write_mode='quality_lvm',
    )
    if code_b != 0:
        return code_b

    if not res_a or not res_b:
        return 2

    base = res_a[-1]
    cand = res_b[-1]
    print(f'\n{"=" * 76}\n  LVM vs QUALITY+LVM\n{"=" * 76}')
    print(f'  Baseline final:  Rs {base.summary["final_equity"]:>12,.0f}  '
          f'({base.summary["total_return_pct"]:+.2f}%)')
    print(f'  Candidate final: Rs {cand.summary["final_equity"]:>12,.0f}  '
          f'({cand.summary["total_return_pct"]:+.2f}%)')
    diff = cand.summary['final_equity'] - base.summary['final_equity']
    print(f'  Edge:            Rs {diff:>+12,.0f}  '
          f'({cand.summary["total_return_pct"] - base.summary["total_return_pct"]:+.2f}pp)')
    print(f'  Baseline Sharpe: {base.summary.get("sharpe", 0):.3f}  '
          f'MaxDD: {base.summary.get("max_drawdown_pct", 0):.2f}%')
    print(f'  Candidate Sharpe:{cand.summary.get("sharpe", 0):.3f}  '
          f'MaxDD: {cand.summary.get("max_drawdown_pct", 0):.2f}%')
    bench_ex_a = base.summary.get('excess_return_pct')
    bench_ex_b = cand.summary.get('excess_return_pct')
    if bench_ex_a is not None and bench_ex_b is not None:
        print(f'  Excess vs Nifty: {bench_ex_a:+.2f}pp -> {bench_ex_b:+.2f}pp  '
              f'({bench_ex_b - bench_ex_a:+.2f}pp)')
    return 0


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

    pq = sub.add_parser(
        'qmst',
        help='QMST stack: fq pick (watchlist) + turbo entry + VMQ exits (path1 window)',
    )
    pq.add_argument(
        '--months', type=int, default=None,
        help='Trailing months via Path2 OHLCV rescore (omit for path1 dense window)',
    )
    pq.add_argument(
        '--no-day3', action='store_true',
        help='Force-disable VMQ day-3/day-5 validation exits in simulation',
    )
    pq.add_argument(
        '--day3', action='store_true',
        help='Force-enable VMQ day-3/day-5 (overrides VMQ_DAY3_ENABLED=false)',
    )
    pq.add_argument(
        '--pick-gates', action='store_true',
        help='Enable FQ/RK pick floors (overrides QMST_PICK_GATES_ENABLED=false)',
    )
    _add_common(pq)

    pl = sub.add_parser(
        'lvm',
        help='LowVol→Mom: Nifty 200, monthly rebalance, LVM stop (production ranker)',
    )
    pl.add_argument('--months', type=int, default=24,
                    help='Trailing months of history (default 24)')
    pl.add_argument('--stop-pct', type=float, default=10.0,
                    help='LVM stop loss magnitude in percent (default 10 => -10%%)')
    pl.add_argument('--compare-stops', action='store_true',
                    help='Run both -10%% and -15%% stops in one invocation')
    pl.add_argument('--monthly-injection', type=float, default=0.0,
                    help='INR cash added each rebalance after the first (e.g. 100000)')
    pl.add_argument('--vol-mode', choices=('12m', '6m'), default='12m',
                    help='12m: 252d vol in volatility_6m column; 6m: 20d vol proxy')
    pl.add_argument('--no-cache', action='store_true',
                    help='Rebuild LVM snapshot cache')
    pl.add_argument('--no-warmup', dest='warmup', action='store_false',
                    help='Skip OHLCV warmup (use existing price cache only)')
    _add_common(pl)
    pl.set_defaults(rebalance='monthly', capital=1_000_000.0, top_n=10)

    pql = sub.add_parser(
        'quality-lvm',
        help='Quality+LowVol→Mom: LVM with PIT quality filter (Screener fundamentals)',
    )
    pql.add_argument('--months', type=int, default=24)
    pql.add_argument('--stop-pct', type=float, default=10.0)
    pql.add_argument('--compare-stops', action='store_true')
    pql.add_argument('--monthly-injection', type=float, default=0.0)
    pql.add_argument('--vol-mode', choices=('12m', '6m'), default='12m')
    pql.add_argument('--no-cache', action='store_true')
    pql.add_argument('--no-warmup', dest='warmup', action='store_false')
    pql.add_argument('--pit-only', action='store_true',
                     help='Skip stocks without real Screener filing as of each date')
    _add_common(pql)
    pql.set_defaults(rebalance='monthly', capital=1_000_000.0, top_n=10)

    pcl = sub.add_parser(
        'compare-lvm',
        help='Head-to-head: LowVol→Mom vs Quality+LowVol→Mom (same window/stops)',
    )
    pcl.add_argument('--months', type=int, default=120)
    pcl.add_argument('--stop-pct', type=float, default=10.0)
    pcl.add_argument('--monthly-injection', type=float, default=0.0)
    pcl.add_argument('--vol-mode', choices=('12m', '6m'), default='12m')
    pcl.add_argument('--no-cache', action='store_true')
    pcl.add_argument('--no-warmup', dest='warmup', action='store_false')
    pcl.add_argument('--pit-only', action='store_true',
                     help='Quality leg: require real Screener filing (strict validation)')
    _add_common(pcl)
    pcl.set_defaults(rebalance='monthly', capital=1_000_000.0, top_n=10)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='[backtest] %(message)s')

    if args.cmd == 'path1':
        return run_path1(args)
    if args.cmd == 'path2':
        return run_path2(args)
    if args.cmd == 'compare':
        return run_compare(args)
    if args.cmd == 'qmst':
        return run_qmst(args)
    if args.cmd == 'lvm':
        return run_lvm(args)
    if args.cmd == 'quality-lvm':
        return run_quality_lvm(args)
    if args.cmd == 'compare-lvm':
        return run_compare_lvm(args)
    return 1


if __name__ == '__main__':
    sys.exit(main())
