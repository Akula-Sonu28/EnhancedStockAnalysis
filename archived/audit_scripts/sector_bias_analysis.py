#!/usr/bin/env python3
"""Sector bias analysis on the latest Enhanced Stock Report."""

import openpyxl
import statistics
from collections import defaultdict

REPORT = "reports/Enhanced_Stock_Report_20260318_175136.xlsx"

wb = openpyxl.load_workbook(REPORT, read_only=True, data_only=True)
ws = wb["Complete Data"]

headers = None
rows_data = []
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i == 0:
        headers = list(row)
        continue
    rows_data.append(dict(zip(headers, row)))
wb.close()

print(f"Loaded {len(rows_data)} stocks from '{REPORT}'")
print(f"Columns of interest found: sector, final_blended_score, overall_score, risk_adjusted_score")
print(f"  final_recommendation, portfolio_fit, portfolio_context_score, sentiment_adjustment_amount\n")

def safe_float(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

sector_data = defaultdict(list)
all_scores = []
all_sentiment_adj = []

for r in rows_data:
    sector = r.get("sector") or "Unknown"
    score = safe_float(r.get("final_blended_score")) or safe_float(r.get("overall_score")) or safe_float(r.get("risk_adjusted_score"))
    rec = str(r.get("final_recommendation") or "")
    pfit = str(r.get("portfolio_fit") or "")
    pctx = safe_float(r.get("portfolio_context_score"))
    sadj = safe_float(r.get("sentiment_adjustment_amount"))
    symbol = r.get("symbol") or "?"
    ras = safe_float(r.get("risk_adjusted_score"))
    hybrid = safe_float(r.get("hybrid_overall_score"))
    regime_adj = safe_float(r.get("regime_adjustment_amount"))
    volume_adj = safe_float(r.get("volume_adjustment_amount"))
    sector_perf_adj = safe_float(r.get("sector_performance_adj"))
    phase1_quality = safe_float(r.get("phase1_quality_adjustment"))
    phase1_ctx = safe_float(r.get("phase1_context_adjustment"))

    entry = {
        "symbol": symbol,
        "score": score,
        "rec": rec,
        "portfolio_fit": pfit,
        "portfolio_context_score": pctx,
        "sentiment_adj": sadj,
        "risk_adjusted_score": ras,
        "hybrid_score": hybrid,
        "regime_adj": regime_adj,
        "volume_adj": volume_adj,
        "sector_perf_adj": sector_perf_adj,
        "phase1_quality": phase1_quality,
        "phase1_ctx": phase1_ctx,
    }
    sector_data[sector].append(entry)
    if score is not None:
        all_scores.append(score)
    if sadj is not None:
        all_sentiment_adj.append(sadj)

global_mean = statistics.mean(all_scores) if all_scores else 0
global_median = statistics.median(all_scores) if all_scores else 0
global_stdev = statistics.stdev(all_scores) if len(all_scores) > 1 else 0

print("=" * 130)
print(f"GLOBAL STATS: Mean={global_mean:.1f}  Median={global_median:.1f}  StdDev={global_stdev:.1f}  N={len(all_scores)}")
print("=" * 130)

sector_stats = []
for sector, entries in sector_data.items():
    scores = [e["score"] for e in entries if e["score"] is not None]
    pctx_vals = [e["portfolio_context_score"] for e in entries if e["portfolio_context_score"] is not None]
    sadj_vals = [e["sentiment_adj"] for e in entries if e["sentiment_adj"] is not None]
    regime_vals = [e["regime_adj"] for e in entries if e["regime_adj"] is not None]
    vol_vals = [e["volume_adj"] for e in entries if e["volume_adj"] is not None]
    sec_perf_vals = [e["sector_perf_adj"] for e in entries if e["sector_perf_adj"] is not None]
    phase1q_vals = [e["phase1_quality"] for e in entries if e["phase1_quality"] is not None]
    hybrid_vals = [e["hybrid_score"] for e in entries if e["hybrid_score"] is not None]
    ras_vals = [e["risk_adjusted_score"] for e in entries if e["risk_adjusted_score"] is not None]

    recs = [e["rec"] for e in entries]
    buy_count = sum(1 for r in recs if "BUY" in r.upper() and "SELL" not in r.upper())
    strong_buy = sum(1 for r in recs if "STRONG BUY" in r.upper())
    hold_count = sum(1 for r in recs if "HOLD" in r.upper())
    sell_count = sum(1 for r in recs if "SELL" in r.upper())

    fits = set(e["portfolio_fit"] for e in entries)

    mean_s = statistics.mean(scores) if scores else 0
    median_s = statistics.median(scores) if scores else 0
    stdev_s = statistics.stdev(scores) if len(scores) > 1 else 0
    mean_pctx = statistics.mean(pctx_vals) if pctx_vals else 0
    mean_sadj = statistics.mean(sadj_vals) if sadj_vals else 0
    mean_regime = statistics.mean(regime_vals) if regime_vals else 0
    mean_vol = statistics.mean(vol_vals) if vol_vals else 0
    mean_sec_perf = statistics.mean(sec_perf_vals) if sec_perf_vals else 0
    mean_p1q = statistics.mean(phase1q_vals) if phase1q_vals else 0
    mean_hybrid = statistics.mean(hybrid_vals) if hybrid_vals else 0
    mean_ras = statistics.mean(ras_vals) if ras_vals else 0

    uniform_sadj = len(set(sadj_vals)) <= 1 if sadj_vals else True
    uniform_fit = len(fits) <= 1

    flags = []
    if mean_s > global_median + 10:
        flags.append(f"⚠️ POSITIVE BIAS (+{mean_s - global_median:.1f} above median)")
    if mean_s < global_median - 10:
        flags.append(f"⚠️ NEGATIVE BIAS ({mean_s - global_median:.1f} below median)")
    if uniform_fit and len(entries) > 1:
        flags.append(f"⚠️ UNIFORM portfolio_fit='{list(fits)[0]}'")
    if uniform_sadj and len(entries) > 1:
        flags.append(f"⚠️ UNIFORM sentiment_adj={sadj_vals[0] if sadj_vals else 'N/A'}")

    sector_stats.append({
        "sector": sector,
        "count": len(entries),
        "mean": mean_s,
        "median": median_s,
        "stdev": stdev_s,
        "buy": buy_count,
        "strong_buy": strong_buy,
        "hold": hold_count,
        "sell": sell_count,
        "mean_pctx": mean_pctx,
        "mean_sadj": mean_sadj,
        "mean_regime": mean_regime,
        "mean_vol_adj": mean_vol,
        "mean_sec_perf": mean_sec_perf,
        "mean_p1q": mean_p1q,
        "mean_hybrid": mean_hybrid,
        "mean_ras": mean_ras,
        "fits": fits,
        "uniform_fit": uniform_fit,
        "uniform_sadj": uniform_sadj,
        "flags": flags,
        "entries": entries,
    })

sector_stats.sort(key=lambda x: x["mean"], reverse=True)

# ── Summary table ──
print(f"\n{'Sector':<30} {'N':>3} {'Mean':>6} {'Med':>6} {'StDev':>6} {'BUY':>4} {'SBUY':>5} {'HOLD':>5} {'SELL':>5}  {'PCtx':>5} {'SAdj':>5} {'RegAdj':>6} {'VolAdj':>6} {'SecPf':>6} {'P1Q':>5} {'Hybrid':>6} {'RAS':>6}")
print("-" * 155)
for s in sector_stats:
    print(f"{s['sector']:<30} {s['count']:>3} {s['mean']:>6.1f} {s['median']:>6.1f} {s['stdev']:>6.1f} {s['buy']:>4} {s['strong_buy']:>5} {s['hold']:>5} {s['sell']:>5}  {s['mean_pctx']:>5.0f} {s['mean_sadj']:>5.1f} {s['mean_regime']:>6.1f} {s['mean_vol_adj']:>6.1f} {s['mean_sec_perf']:>6.1f} {s['mean_p1q']:>5.1f} {s['mean_hybrid']:>6.1f} {s['mean_ras']:>6.1f}")

# ── Flags ──
print("\n" + "=" * 130)
print("SECTOR BIAS FLAGS")
print("=" * 130)
flagged = False
for s in sector_stats:
    if s["flags"]:
        flagged = True
        print(f"\n  {s['sector']} (N={s['count']}, Mean={s['mean']:.1f}):")
        for f in s["flags"]:
            print(f"    {f}")
if not flagged:
    print("  No sectors flagged for bias.")

# ── Deep dive: top and bottom sectors ──
print("\n" + "=" * 130)
print("DEEP DIVE: TOP 3 AND BOTTOM 3 SECTORS BY MEAN SCORE")
print("=" * 130)
for s in sector_stats[:3] + sector_stats[-3:]:
    print(f"\n{'─' * 100}")
    print(f"  {s['sector']} — Mean={s['mean']:.1f}, Median={s['median']:.1f}, N={s['count']}")
    print(f"  Recommendations: BUY={s['buy']}, STRONG BUY={s['strong_buy']}, HOLD={s['hold']}, SELL={s['sell']}")
    print(f"  Avg portfolio_context_score={s['mean_pctx']:.1f}, Avg sentiment_adj={s['mean_sadj']:.2f}")
    print(f"  Avg regime_adj={s['mean_regime']:.2f}, Avg volume_adj={s['mean_vol_adj']:.2f}, Avg sector_perf_adj={s['mean_sec_perf']:.1f}")
    print(f"  Avg phase1_quality_adj={s['mean_p1q']:.1f}, Avg hybrid_score={s['mean_hybrid']:.1f}, Avg risk_adj_score={s['mean_ras']:.1f}")
    print(f"  Portfolio fits: {s['fits']}")
    print(f"  {'Symbol':<15} {'Score':>6} {'Hybrid':>7} {'RAS':>6} {'PCtx':>5} {'SAdj':>5} {'RegAdj':>6} {'VolAdj':>6} {'SecPf':>6} {'P1Q':>5}  {'Rec':<20} {'Fit':<12}")
    for e in sorted(s["entries"], key=lambda x: x["score"] or 0, reverse=True):
        sc = f"{e['score']:.1f}" if e['score'] else "N/A"
        hy = f"{e['hybrid_score']:.1f}" if e['hybrid_score'] else "N/A"
        ra = f"{e['risk_adjusted_score']:.1f}" if e['risk_adjusted_score'] else "N/A"
        pc = f"{e['portfolio_context_score']:.0f}" if e['portfolio_context_score'] is not None else "N/A"
        sa = f"{e['sentiment_adj']:.1f}" if e['sentiment_adj'] is not None else "N/A"
        rg = f"{e['regime_adj']:.1f}" if e['regime_adj'] is not None else "N/A"
        va = f"{e['volume_adj']:.1f}" if e['volume_adj'] is not None else "N/A"
        sp = f"{e['sector_perf_adj']:.1f}" if e['sector_perf_adj'] is not None else "N/A"
        p1 = f"{e['phase1_quality']:.1f}" if e['phase1_quality'] is not None else "N/A"
        print(f"  {e['symbol']:<15} {sc:>6} {hy:>7} {ra:>6} {pc:>5} {sa:>5} {rg:>6} {va:>6} {sp:>6} {p1:>5}  {e['rec']:<20} {e['portfolio_fit']:<12}")

# ── Cross-sector comparison of adjustment pipeline ──
print("\n" + "=" * 130)
print("ADJUSTMENT PIPELINE COMPARISON (sorted by mean final_blended_score)")
print("=" * 130)
print(f"{'Sector':<30} {'MeanScore':>9} {'AvgRegime':>10} {'AvgSent':>8} {'AvgVol':>8} {'AvgSecPf':>9} {'AvgP1Q':>7} {'AvgPCtx':>8}  {'TotalAdj':>9}")
print("-" * 120)
for s in sector_stats:
    total_adj = s["mean_regime"] + s["mean_sadj"] + s["mean_vol_adj"] + s["mean_sec_perf"] + s["mean_p1q"]
    print(f"{s['sector']:<30} {s['mean']:>9.1f} {s['mean_regime']:>10.2f} {s['mean_sadj']:>8.2f} {s['mean_vol_adj']:>8.2f} {s['mean_sec_perf']:>9.1f} {s['mean_p1q']:>7.1f} {s['mean_pctx']:>8.0f}  {total_adj:>9.2f}")

# ── Financial Services deep-dive ──
print("\n" + "=" * 130)
print("FINANCIAL SERVICES SPECIFIC ANALYSIS")
print("=" * 130)
fin_stat = next((s for s in sector_stats if "Financial" in s["sector"]), None)
if fin_stat:
    print(f"  Count: {fin_stat['count']}")
    print(f"  Mean score: {fin_stat['mean']:.1f} (Global median: {global_median:.1f}, Delta: {fin_stat['mean'] - global_median:+.1f})")
    print(f"  Buy rate: {fin_stat['buy']}/{fin_stat['count']} = {fin_stat['buy']/fin_stat['count']*100:.0f}%")
    print(f"  Portfolio fits: {fin_stat['fits']}")
    print(f"  Avg portfolio_context_score: {fin_stat['mean_pctx']:.1f}")
    print(f"  Avg sentiment_adj: {fin_stat['mean_sadj']:.2f}")
    print(f"  Avg regime_adj: {fin_stat['mean_regime']:.2f}")
    print(f"  Avg sector_perf_adj: {fin_stat['mean_sec_perf']:.1f}")
    
    non_fin_scores = [e["score"] for s2 in sector_stats if "Financial" not in s2["sector"] for e in s2["entries"] if e["score"] is not None]
    nf_mean = statistics.mean(non_fin_scores) if non_fin_scores else 0
    print(f"\n  Non-Financial mean score: {nf_mean:.1f}")
    print(f"  Financial vs Non-Financial gap: {fin_stat['mean'] - nf_mean:+.1f}")
else:
    print("  No 'Financial Services' sector found.")

print("\n" + "=" * 130)
print("SCORE DISTRIBUTION BY SECTOR (quintiles)")
print("=" * 130)
if all_scores:
    q20 = sorted(all_scores)[len(all_scores)//5]
    q40 = sorted(all_scores)[2*len(all_scores)//5]
    q60 = sorted(all_scores)[3*len(all_scores)//5]
    q80 = sorted(all_scores)[4*len(all_scores)//5]
    print(f"  Quintile boundaries: Q1<{q20:.1f}, Q2<{q40:.1f}, Q3<{q60:.1f}, Q4<{q80:.1f}, Q5>={q80:.1f}")
    print(f"\n  {'Sector':<30} {'Q1(low)':>8} {'Q2':>5} {'Q3':>5} {'Q4':>5} {'Q5(top)':>8}")
    print("  " + "-" * 65)
    for s in sector_stats:
        scores = sorted([e["score"] for e in s["entries"] if e["score"] is not None])
        q1 = sum(1 for x in scores if x < q20)
        q2c = sum(1 for x in scores if q20 <= x < q40)
        q3c = sum(1 for x in scores if q40 <= x < q60)
        q4c = sum(1 for x in scores if q60 <= x < q80)
        q5 = sum(1 for x in scores if x >= q80)
        print(f"  {s['sector']:<30} {q1:>8} {q2c:>5} {q3c:>5} {q4c:>5} {q5:>8}")

print("\nAnalysis complete.")
