#!/usr/bin/env python3
"""Scoring Engine Audit — answers Q1–Q5 about the hybrid scoring pipeline."""

import glob, os, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Load the most recent report ──────────────────────────────────────────────
files = glob.glob("reports/*.xlsx")
if not files:
    raise SystemExit("No .xlsx files found in reports/")
latest = max(files, key=os.path.getmtime)
print(f"📂 Using report: {latest}\n")

df = pd.read_excel(latest, sheet_name="Complete Data", engine="openpyxl")
print(f"   Rows: {len(df)}  |  Columns: {len(df.columns)}\n")

# Helper to safely get numeric series
def num(col):
    if col not in df.columns:
        return None
    return pd.to_numeric(df[col], errors="coerce")

# ═════════════════════════════════════════════════════════════════════════════
# Q1: Is risk_adjustment dominating the final score?
# ═════════════════════════════════════════════════════════════════════════════
print("=" * 80)
print("Q1: Is risk_adjustment dominating the final score?")
print("=" * 80)

hybrid_components = {
    "hybrid_fundamental_quality": "Fundamental",
    "hybrid_momentum_technical":  "Momentum/Tech",
    "hybrid_volume_strength":     "Volume",
    "hybrid_multi_timeframe":     "Multi-TF",
    "hybrid_ml_signal":           "ML Signal",
    "hybrid_risk_adjustment":     "Risk Adj",
    "hybrid_sector_multiplier":   "Sector Mult",
}

final_score_col = "overall_score"
final_scores = num(final_score_col)

stats_rows = []
corr_rows = []

for col, label in hybrid_components.items():
    s = num(col)
    if s is None:
        print(f"  ⚠ Column '{col}' not found")
        continue
    valid = s.dropna()
    if valid.empty:
        continue
    stats_rows.append({
        "Component": label,
        "Column": col,
        "Mean": valid.mean(),
        "Std": valid.std(),
        "Min": valid.min(),
        "Max": valid.max(),
        "Non-null": len(valid),
    })
    if final_scores is not None:
        mask = s.notna() & final_scores.notna()
        if mask.sum() > 5:
            corr = s[mask].corr(final_scores[mask])
            corr_rows.append({"Component": label, "Column": col, "Corr_with_overall": corr})

if stats_rows:
    stats_df = pd.DataFrame(stats_rows)
    print("\n  Component Statistics:")
    print(stats_df.to_string(index=False, float_format="{:.4f}".format))

if corr_rows:
    corr_df = pd.DataFrame(corr_rows).sort_values("Corr_with_overall", ascending=False)
    print("\n  Correlation with overall_score (sorted):")
    print(corr_df.to_string(index=False, float_format="{:.4f}".format))

    top = corr_df.iloc[0]
    print(f"\n  >>> Highest correlation: {top['Component']} = {top['Corr_with_overall']:.4f}")
    if "Risk" in top["Component"] and abs(top["Corr_with_overall"]) > 0.80:
        print("  >>> ⚠ YES — risk_adjustment is DOMINATING the final score (corr > 0.80)")
    elif "Risk" in top["Component"]:
        print(f"  >>> Risk_adj is top but corr={top['Corr_with_overall']:.2f} < 0.80 threshold — moderate influence")
    else:
        print(f"  >>> Risk_adj is NOT the dominant driver; {top['Component']} dominates.")

# Also check: risk_adjusted_score (col 391)
risk_adj_score = num("risk_adjusted_score")
if risk_adj_score is not None and final_scores is not None:
    mask = risk_adj_score.notna() & final_scores.notna()
    if mask.sum() > 5:
        c = risk_adj_score[mask].corr(final_scores[mask])
        print(f"\n  Additional: risk_adjusted_score ↔ overall_score corr = {c:.4f}")

# ═════════════════════════════════════════════════════════════════════════════
# Q2: Is score smoothing suppressing fresh signals?
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("Q2: Is score smoothing suppressing fresh signals?")
print("=" * 80)

smoothing_cols = {
    "score_smoothed":       "Smoothing applied?",
    "raw_blended_score":    "Raw blended score",
    "final_blended_score":  "Final blended score",
    "pre_adj_blended_score": "Pre-adj blended",
    "phase1_blended_score": "Phase1 blended",
}

for col, label in smoothing_cols.items():
    s = num(col)
    if s is not None:
        valid = s.dropna()
        print(f"  {label} ({col}): mean={valid.mean():.2f}, std={valid.std():.2f}, "
              f"min={valid.min():.2f}, max={valid.max():.2f}, count={len(valid)}")
    else:
        # might be boolean or string
        if col in df.columns:
            print(f"  {label} ({col}): {df[col].value_counts().to_dict()}")
        else:
            print(f"  ⚠ Column '{col}' not found")

raw = num("raw_blended_score")
final_blend = num("final_blended_score")
if raw is not None and final_blend is not None:
    diff = (final_blend - raw).dropna()
    big_diff = (diff.abs() > 5).sum()
    print(f"\n  Stocks where |final_blended - raw_blended| > 5 pts: {big_diff} / {len(diff)}")
    print(f"  Mean smoothing delta: {diff.mean():.2f}  |  Std: {diff.std():.2f}")
    if diff.mean() < -1:
        print("  >>> ⚠ Smoothing is PULLING scores DOWN on average (toward stale mean)")
    elif diff.mean() > 1:
        print("  >>> Smoothing is pushing scores UP on average")
    else:
        print("  >>> Smoothing effect is small on average")

# Also compare pre_adj vs final
pre_adj = num("pre_adj_blended_score")
if pre_adj is not None and final_blend is not None:
    adj_diff = (final_blend - pre_adj).dropna()
    big_adj = (adj_diff.abs() > 5).sum()
    print(f"\n  Stocks where |final_blended - pre_adj_blended| > 5 pts: {big_adj} / {len(adj_diff)}")

# Check score_smoothed flag
if "score_smoothed" in df.columns:
    smoothed_flag = df["score_smoothed"]
    if smoothed_flag.dtype == bool or set(smoothed_flag.dropna().unique()).issubset({True, False, 0, 1, "True", "False"}):
        n_smoothed = smoothed_flag.astype(str).str.lower().isin(["true", "1", "1.0"]).sum()
        print(f"\n  Stocks flagged as smoothed: {n_smoothed} / {len(df)}")

# ═════════════════════════════════════════════════════════════════════════════
# Q3: Are BUY/SELL thresholds well-calibrated?
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("Q3: Are BUY/SELL thresholds well-calibrated?")
print("=" * 80)

rec_col = "final_recommendation"
if rec_col not in df.columns:
    for c in ["corrected_recommendation", "phase2_recommendation", "original_recommendation"]:
        if c in df.columns:
            rec_col = c
            break

recs_raw = df[rec_col].astype(str).str.strip()
recs = recs_raw.str.upper()
scores = num("overall_score")

print(f"\n  Using recommendation column: {rec_col}")
print(f"\n  Recommendation Distribution:")
rec_counts = recs_raw.value_counts()
total = len(recs)
for r, cnt in rec_counts.items():
    pct = cnt / total * 100
    score_slice = scores[recs_raw == r].dropna()
    if len(score_slice) > 0:
        print(f"    {r:40s}: {cnt:4d} ({pct:5.1f}%)  | Score: mean={score_slice.mean():.1f}, "
              f"min={score_slice.min():.1f}, max={score_slice.max():.1f}, median={score_slice.median():.1f}")
    else:
        print(f"    {r:40s}: {cnt:4d} ({pct:5.1f}%)")

# Classify using substring matching (handles emoji prefixes, ML annotations)
sell_cats = recs.str.contains("SELL", na=False) | recs.str.contains("STRONG SELL", na=False)
buy_cats = recs.str.contains("BUY", na=False) | recs.str.contains("STRONG BUY", na=False)
hold_cats = recs.str.contains("HOLD", na=False)
weak_sell = recs.str.contains("WEAK SELL", na=False)
strong_sell = recs.str.contains("SELL", na=False) & ~weak_sell

# Reclassify: "WEAK SELL" separate from "SELL"/"STRONG SELL"
print(f"\n  Grouped classification (by substring):")
print(f"    Contains 'STRONG BUY': {recs.str.contains('STRONG BUY', na=False).sum()}")
print(f"    Contains 'BUY' (not ML annotation): {buy_cats.sum() - recs.str.contains('ML: BUY', na=False).sum()}")
n_ml_buy_annotation = ((recs.str.contains('ML: BUY', na=False)) & ~recs.str.contains('^.*BUY', na=False)).sum()
print(f"    Contains 'HOLD':       {hold_cats.sum()}")
print(f"    Contains 'WEAK SELL':  {weak_sell.sum()}")
print(f"    Contains 'SELL' (not WEAK): {strong_sell.sum()}")
print(f"    Contains 'STRONG SELL': {recs.str.contains('STRONG SELL', na=False).sum()}")

high_score_sell = df[sell_cats & (scores > 55)][["symbol", "overall_score", rec_col]].copy()
low_score_buy = df[buy_cats & (scores < 45)][["symbol", "overall_score", rec_col]].copy()
high_score_weak_sell = df[weak_sell & (scores > 55)][["symbol", "overall_score", rec_col]].copy()

print(f"\n  ⚠ Stocks with score > 55 getting any SELL (incl WEAK SELL): {len(high_score_sell)}")
if len(high_score_sell) > 0:
    print(high_score_sell.head(20).to_string(index=False))

print(f"\n  ⚠ Stocks with score > 55 specifically WEAK SELL: {len(high_score_weak_sell)}")

print(f"\n  ⚠ Stocks with score < 45 getting BUY/STRONG BUY: {len(low_score_buy)}")
if len(low_score_buy) > 0:
    print(low_score_buy.head(20).to_string(index=False))

# All sell-side (WEAK SELL + SELL + STRONG SELL) vs buy-side
all_sell_pct = sell_cats.sum() / total * 100
pure_sell_pct = strong_sell.sum() / total * 100
weak_sell_pct = weak_sell.sum() / total * 100
buy_pct = buy_cats.sum() / total * 100
hold_pct = hold_cats.sum() / total * 100

print(f"\n  BUY-side: {buy_pct:.1f}%  |  HOLD: {hold_pct:.1f}%  |  WEAK SELL: {weak_sell_pct:.1f}%  |  SELL/STRONG SELL: {pure_sell_pct:.1f}%")
print(f"  Total sell-side (incl WEAK SELL): {all_sell_pct:.1f}%")
if all_sell_pct > 60:
    print("  >>> ⚠ SELL-side > 60% — thresholds may be TOO HARSH")
elif all_sell_pct > 50:
    print("  >>> ⚠ SELL-side > 50% — thresholds skew bearish")
elif weak_sell_pct > 35:
    print("  >>> ⚠ WEAK SELL alone > 35% — many stocks in 'mildly negative' zone, engine skews cautious")
else:
    print("  >>> Threshold balance looks reasonable")

# ═════════════════════════════════════════════════════════════════════════════
# Q4: Is volume scoring unfairly penalizing certain stocks?
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("Q4: Is volume scoring unfairly penalizing certain stocks?")
print("=" * 80)

vol_cols = {
    "hybrid_volume_strength":   "Hybrid Volume",
    "volume_composite_score":   "Volume Composite",
    "volume_adjusted_score":    "Volume-Adjusted Score",
    "volume_score_contribution": "Volume Score Contrib",
    "volume_adjustment_amount": "Volume Adj Amount",
}

for col, label in vol_cols.items():
    s = num(col)
    if s is not None:
        v = s.dropna()
        print(f"  {label} ({col}): mean={v.mean():.2f}, std={v.std():.2f}, "
              f"min={v.min():.2f}, max={v.max():.2f}")

# Bottom 10 by hybrid_volume_strength
primary_vol = "hybrid_volume_strength"
if primary_vol not in df.columns:
    primary_vol = "volume_composite_score"

vol_s = num(primary_vol)
if vol_s is not None:
    show_cols = ["symbol", primary_vol, "overall_score", rec_col, "fundamental_score"]
    available = [c for c in show_cols if c in df.columns]
    bottom10 = df.nsmallest(10, primary_vol)[available].copy()
    print(f"\n  Bottom 10 stocks by {primary_vol}:")
    print(bottom10.to_string(index=False, float_format="{:.2f}".format))

    # Stocks with high overall_score but low volume
    vol_low = vol_s < vol_s.quantile(0.15)
    score_high = scores > scores.quantile(0.70)
    penalized = df[vol_low & score_high][available].copy()
    print(f"\n  Stocks with LOW volume (bottom 15%) but HIGH overall score (top 30%): {len(penalized)}")
    if len(penalized) > 0:
        print(penalized.to_string(index=False, float_format="{:.2f}".format))

# Volume adjustment direction
vol_adj = num("volume_adjustment_amount")
if vol_adj is not None:
    neg = (vol_adj < 0).sum()
    pos = (vol_adj > 0).sum()
    zero = (vol_adj == 0).sum()
    print(f"\n  Volume adjustment direction: negative={neg}, positive={pos}, zero={zero}")
    print(f"  Mean volume adjustment: {vol_adj.mean():.2f}")

# ═════════════════════════════════════════════════════════════════════════════
# Q5: Strong fundamentals getting SELL recommendations?
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("Q5: Are stocks with strong fundamentals getting SELL recommendations?")
print("=" * 80)

fund_cols = ["fundamental_score", "hybrid_fundamental_quality", "fundamental_score_final",
             "fundamental_quality_score"]

for col in fund_cols:
    s = num(col)
    if s is not None:
        v = s.dropna()
        print(f"  {col}: mean={v.mean():.2f}, std={v.std():.2f}, min={v.min():.2f}, max={v.max():.2f}")

# Primary: fundamental_score
fund = num("fundamental_score")
if fund is None:
    fund = num("hybrid_fundamental_quality")

if fund is not None:
    any_sell = recs.str.contains("SELL", na=False)
    strong_fund_sell = df[(fund > 70) & any_sell].copy()
    print(f"\n  Stocks with fundamental > 70 AND any SELL recommendation: {len(strong_fund_sell)}")

    breakdown_cols = ["symbol", "fundamental_score", "hybrid_fundamental_quality",
                      "hybrid_momentum_technical", "hybrid_volume_strength",
                      "hybrid_risk_adjustment", "hybrid_overall_score",
                      "overall_score", rec_col,
                      "volume_adjustment_amount", "sentiment_adjustment_amount",
                      "regime_adjustment_amount"]
    available_bc = [c for c in breakdown_cols if c in df.columns]

    if len(strong_fund_sell) > 0:
        print("\n  Full score breakdown for these stocks:")
        print(strong_fund_sell[available_bc].to_string(index=False, float_format="{:.2f}".format))
    else:
        print("  None found with fund > 70.")

    # Also check relaxed threshold
    strong_fund_sell_60 = df[(fund > 60) & any_sell].copy()
    print(f"\n  (Relaxed) Stocks with fundamental > 60 AND any SELL: {len(strong_fund_sell_60)}")
    if len(strong_fund_sell_60) > 0:
        print(strong_fund_sell_60[available_bc].head(20).to_string(index=False, float_format="{:.2f}".format))

# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"  Report: {latest}")
print(f"  Stocks analyzed: {len(df)}")
if corr_rows:
    top = pd.DataFrame(corr_rows).sort_values("Corr_with_overall", ascending=False).iloc[0]
    print(f"  Q1 Dominant component: {top['Component']} (corr={top['Corr_with_overall']:.3f})")
if raw is not None and final_blend is not None:
    diff = (final_blend - raw).dropna()
    print(f"  Q2 Smoothing impact: mean delta={diff.mean():.2f}, {(diff.abs()>5).sum()} stocks shifted >5pts")
print(f"  Q3 Recommendation split: BUY-side={buy_pct:.1f}%, HOLD={hold_pct:.1f}%, WEAK SELL={weak_sell_pct:.1f}%, SELL={pure_sell_pct:.1f}%")
if vol_adj is not None:
    print(f"  Q4 Volume penalty: {neg} stocks penalized, mean adj={vol_adj.mean():.2f}")
if fund is not None:
    any_sell_flag = recs.str.contains("SELL", na=False)
    n_bad = len(df[(fund > 70) & any_sell_flag])
    print(f"  Q5 Strong-fund SELL mismatches: {n_bad} stocks")
