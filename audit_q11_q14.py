#!/usr/bin/env python3
"""
Audit Q11–Q14: Sector bias, recommendation stability, zombie scores, BUY hit rate.
"""

import glob
import os
import sys
import numpy as np
import pandas as pd
from collections import Counter, defaultdict

REPORTS_DIR = "reports"
DATA_DIR = "data"

pd.set_option("display.max_rows", 200)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)
pd.set_option("display.float_format", lambda x: f"{x:.2f}")


def load_latest_report():
    files = glob.glob(os.path.join(REPORTS_DIR, "*.xlsx"))
    if not files:
        sys.exit("No .xlsx found in reports/")
    latest = max(files, key=os.path.getmtime)
    print(f"{'='*90}")
    print(f"LATEST REPORT: {os.path.basename(latest)}")
    print(f"{'='*90}\n")
    return latest


def q11_sector_bias(xlsx_path):
    print(f"\n{'#'*90}")
    print("Q11: ARE PE/PB THRESHOLDS CREATING IMPLICIT SECTOR BIAS IN THE HYBRID ENGINE?")
    print(f"{'#'*90}\n")

    df = pd.read_excel(xlsx_path, sheet_name="Complete Data", engine="openpyxl")

    fund_cols = [c for c in df.columns if "fundamental" in c.lower() or "h_fund" in c.lower()]
    print(f"Columns matching 'fundamental' or 'h_fund': {fund_cols}\n")

    score_col = None
    for candidate in ["fundamental_score", "FundamentalScore", "fundamental_score_final",
                       "fundamental_quality_score", "hybrid_fundamental_quality"]:
        if candidate in df.columns:
            score_col = candidate
            break
    if score_col is None:
        print("ERROR: No fundamental score column found.")
        return

    cols_needed = ["symbol", "sector", "pe_ratio", "pb_ratio", score_col]
    sub = df[cols_needed].copy()
    sub.rename(columns={score_col: "fund_score"}, inplace=True)

    for c in ["pe_ratio", "pb_ratio", "fund_score"]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")

    sub_clean = sub.dropna(subset=["sector"])

    sector_stats = (
        sub_clean.groupby("sector")
        .agg(
            avg_pe=("pe_ratio", "mean"),
            avg_pb=("pb_ratio", "mean"),
            avg_fund=("fund_score", "mean"),
            med_fund=("fund_score", "median"),
            count=("symbol", "count"),
        )
        .sort_values("avg_fund", ascending=False)
    )

    print("─" * 90)
    print(f"{'Sector':<30} {'Avg PE':>8} {'Avg PB':>8} {'Avg Fund Score':>15} {'Med Fund':>10} {'Count':>6}")
    print("─" * 90)
    for sector, row in sector_stats.iterrows():
        print(f"{str(sector):<30} {row['avg_pe']:>8.1f} {row['avg_pb']:>8.2f} "
              f"{row['avg_fund']:>15.2f} {row['med_fund']:>10.2f} {int(row['count']):>6}")
    print("─" * 90)

    # Low-PE sectors analysis
    low_pe_sectors = ["Financial Services", "Banking", "Energy", "Oil & Gas", "Utilities"]
    high_pe_sectors = ["Technology", "Information Technology", "Consumer Discretionary", "Healthcare"]

    present_low = [s for s in low_pe_sectors if s in sector_stats.index]
    present_high = [s for s in high_pe_sectors if s in sector_stats.index]

    if present_low and present_high:
        avg_fund_low_pe = sector_stats.loc[present_low, "avg_fund"].mean()
        avg_fund_high_pe = sector_stats.loc[present_high, "avg_fund"].mean()
        print(f"\n>>> Low-PE sectors ({', '.join(present_low)}):")
        print(f"    Average fundamental score: {avg_fund_low_pe:.2f}")
        print(f">>> High-PE sectors ({', '.join(present_high)}):")
        print(f"    Average fundamental score: {avg_fund_high_pe:.2f}")
        gap = avg_fund_low_pe - avg_fund_high_pe
        if gap > 3:
            print(f"\n  ⚠ BIAS DETECTED: Low-PE sectors score {gap:.1f} points HIGHER on fundamentals.")
            print("    PE/PB thresholds may be systematically favoring value sectors.")
        elif gap < -3:
            print(f"\n  ⚠ REVERSE BIAS: High-PE sectors score {abs(gap):.1f} points higher.")
        else:
            print(f"\n  ✓ Difference is modest ({gap:+.1f} pts) — no strong sector bias detected.")

    # Correlation: PE vs fundamental score
    valid = sub_clean.dropna(subset=["pe_ratio", "fund_score"])
    if len(valid) > 10:
        corr = valid["pe_ratio"].corr(valid["fund_score"])
        print(f"\n>>> Correlation (PE ratio vs fundamental_score): {corr:.4f}")
        if abs(corr) > 0.3:
            direction = "negatively" if corr < 0 else "positively"
            print(f"    ⚠ Moderate-to-strong correlation — PE is {direction} influencing fund scores.")
        else:
            print(f"    ✓ Weak correlation — PE alone isn't dominating fundamental scores.")

        corr_pb = valid["pb_ratio"].corr(valid["fund_score"]) if valid["pb_ratio"].notna().sum() > 10 else None
        if corr_pb is not None:
            print(f">>> Correlation (PB ratio vs fundamental_score): {corr_pb:.4f}")

    # Also show additional fund columns for reference
    extra_fund = [c for c in fund_cols if c != score_col and c not in ("fundamental_rating",
                  "fundamental_analysis", "fundamental_status")]
    if extra_fund:
        print(f"\nAdditional fundamental columns by sector (first 3):")
        for ec in extra_fund[:3]:
            df[ec] = pd.to_numeric(df[ec], errors="coerce")
            means = df.groupby("sector")[ec].mean().sort_values(ascending=False)
            print(f"\n  {ec}:")
            for s, v in means.head(8).items():
                print(f"    {s:<30} {v:.2f}")


def q12_recommendation_flipping(xlsx_path):
    print(f"\n\n{'#'*90}")
    print("Q12: IS THE RECOMMENDATION FLIPPING BETWEEN RUNS?")
    print(f"{'#'*90}\n")

    hist_path = os.path.join(DATA_DIR, "recommendation_history.csv")
    if not os.path.exists(hist_path):
        print("recommendation_history.csv not found.")
        return

    df = pd.read_csv(hist_path, parse_dates=["date"])
    print(f"Total records in recommendation_history.csv: {len(df)}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique dates (runs): {df['date'].dt.date.nunique()}")
    print(f"Unique symbols: {df['symbol'].nunique()}\n")

    df["run_date"] = df["date"].dt.date
    runs = sorted(df["run_date"].unique())
    print(f"Run dates: {runs}\n")

    if len(runs) < 2:
        print("Only one run found — cannot compare flipping.")
        # Still analyze within-day duplicates
        if len(runs) == 1:
            day_df = df[df["run_date"] == runs[0]]
            dupes = day_df.groupby("symbol").filter(lambda g: len(g) > 1)
            if not dupes.empty:
                print(f"Found {dupes['symbol'].nunique()} symbols with multiple entries on same day.")
                flip_count = 0
                flipper_list = []
                for sym, grp in dupes.groupby("symbol"):
                    actions = grp["action"].unique()
                    if len(actions) > 1:
                        flip_count += 1
                        flipper_list.append((sym, list(actions)))
                print(f"Of those, {flip_count} have different actions within the same day.\n")
                if flipper_list:
                    print("Flippers (same day):")
                    for sym, acts in flipper_list[:20]:
                        print(f"  {sym}: {' → '.join(acts)}")
        return

    # Compare last two runs
    last_run = runs[-1]
    prev_run = runs[-2]
    df_last = df[df["run_date"] == last_run].drop_duplicates(subset="symbol", keep="last")
    df_prev = df[df["run_date"] == prev_run].drop_duplicates(subset="symbol", keep="last")

    merged = df_prev.merge(df_last, on="symbol", suffixes=("_prev", "_last"))
    merged["flipped"] = merged["action_prev"] != merged["action_last"]

    flipped = merged[merged["flipped"]]
    print(f"Comparing: {prev_run} → {last_run}")
    print(f"Common stocks between runs: {len(merged)}")
    print(f"Stocks that changed recommendation: {len(flipped)} ({len(flipped)/max(len(merged),1)*100:.1f}%)\n")

    if not flipped.empty:
        print("Top 10 flippers:")
        print("─" * 80)
        print(f"{'Symbol':<15} {'Previous Action':<25} {'Latest Action':<25}")
        print("─" * 80)
        for _, row in flipped.head(10).iterrows():
            print(f"{row['symbol']:<15} {row['action_prev']:<25} {row['action_last']:<25}")
        print("─" * 80)

    # Multi-run flip analysis (if >2 runs)
    if len(runs) >= 3:
        print(f"\nMulti-run stability analysis (last {min(len(runs), 5)} runs):")
        recent_runs = runs[-5:]
        flip_counter = Counter()
        for sym in df["symbol"].unique():
            sym_df = df[df["symbol"] == sym].sort_values("date")
            sym_runs = sym_df.drop_duplicates(subset="run_date", keep="last")
            sym_runs = sym_runs[sym_runs["run_date"].isin(recent_runs)]
            if len(sym_runs) >= 2:
                actions = sym_runs["action"].tolist()
                flips = sum(1 for i in range(1, len(actions)) if actions[i] != actions[i - 1])
                if flips > 0:
                    flip_counter[sym] = flips

        if flip_counter:
            print(f"Stocks that flipped at least once: {len(flip_counter)}")
            print(f"\nTop 10 most unstable stocks:")
            for sym, flips in flip_counter.most_common(10):
                print(f"  {sym}: {flips} flips")
        else:
            print("No flipping detected across recent runs.")


def q13_zombie_scores(xlsx_path):
    print(f"\n\n{'#'*90}")
    print("Q13: ARE THERE 'ZOMBIE' SCORES — STOCKS THAT ALL LOOK THE SAME?")
    print(f"{'#'*90}\n")

    df = pd.read_excel(xlsx_path, sheet_name="Complete Data", engine="openpyxl")

    score_candidates = [
        ("overall_score", "Overall Score (final)"),
        ("final_blended_score", "Final Blended Score"),
        ("hybrid_overall_score", "Hybrid Overall Score"),
        ("optimized_score", "Optimized Score"),
        ("OverallScore", "OverallScore (original)"),
        ("corrected_overall_score", "Corrected Overall Score"),
        ("improved_overall_score", "Improved Overall Score"),
    ]

    for col, label in score_candidates:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 10:
            continue

        median_val = series.median()
        mean_val = series.mean()
        std_val = series.std()
        iqr = series.quantile(0.75) - series.quantile(0.25)
        total = len(series)

        within_2 = ((series >= median_val - 2) & (series <= median_val + 2)).sum()
        within_4 = ((series >= median_val - 4) & (series <= median_val + 4)).sum()
        within_5 = ((series >= median_val - 5) & (series <= median_val + 5)).sum()

        pct_2 = within_2 / total * 100
        pct_4 = within_4 / total * 100
        pct_5 = within_5 / total * 100

        print(f"─── {label} ({col}) ───")
        print(f"  N={total}, Mean={mean_val:.2f}, Median={median_val:.2f}, Std={std_val:.2f}, IQR={iqr:.2f}")
        print(f"  Range: [{series.min():.2f}, {series.max():.2f}]")
        print(f"  Scores within ±2 of median: {within_2}/{total} ({pct_2:.1f}%)")
        print(f"  Scores within ±4 of median: {within_4}/{total} ({pct_4:.1f}%)")
        print(f"  Scores within ±5 of median: {within_5}/{total} ({pct_5:.1f}%)")

        if pct_4 > 40:
            print(f"  ⚠ ZOMBIE ALERT: {pct_4:.0f}% of stocks are within ±4 pts — POOR differentiation!")
        elif pct_5 > 40:
            print(f"  ⚠ ZOMBIE CONCERN: {pct_5:.0f}% within ±5 pts — differentiation is marginal.")
        else:
            print(f"  ✓ Reasonable spread — scoring provides differentiation.")

        # Distribution buckets
        bins = [0, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        counts, _ = np.histogram(series, bins=bins)
        print(f"\n  Score distribution:")
        for i in range(len(bins) - 1):
            bar = "█" * int(counts[i] / max(max(counts), 1) * 40)
            print(f"    {bins[i]:>3}-{bins[i+1]:<3}: {counts[i]:>4}  {bar}")
        print()

    # Check if final recommendations are well-distributed
    if "final_recommendation" in df.columns:
        rec_dist = df["final_recommendation"].value_counts()
        print("Final Recommendation Distribution:")
        for rec, cnt in rec_dist.items():
            print(f"  {rec}: {cnt} ({cnt/len(df)*100:.1f}%)")
        print()


def q14_buy_hit_rate(xlsx_path):
    print(f"\n\n{'#'*90}")
    print("Q14: WHAT'S THE ACTUAL BUY HIT RATE FROM PAST RECOMMENDATIONS?")
    print(f"{'#'*90}\n")

    # Try Rec Performance sheet first
    try:
        perf_df = pd.read_excel(xlsx_path, sheet_name="Rec Performance", engine="openpyxl")
        print("=== From 'Rec Performance' Sheet ===\n")
        print(perf_df.to_string(index=False))
        print()
    except Exception as e:
        print(f"Could not read Rec Performance sheet: {e}\n")

    # Now deep-dive into recommendation_history.csv
    hist_path = os.path.join(DATA_DIR, "recommendation_history.csv")
    if not os.path.exists(hist_path):
        print("No recommendation_history.csv found.")
        return

    df = pd.read_csv(hist_path)
    print(f"\n=== From recommendation_history.csv ===\n")
    print(f"Total records: {len(df)}")
    print(f"Columns: {list(df.columns)}\n")

    buy_keywords = ["BUY", "STRONG BUY", "NEW POSITION"]
    df["is_buy"] = df["action"].str.upper().apply(
        lambda x: any(kw in str(x) for kw in buy_keywords) if pd.notna(x) else False
    )
    buys = df[df["is_buy"]].copy()
    print(f"Records with BUY-type action: {len(buys)}")

    return_cols = ["return_7d", "return_30d", "return_90d"]
    available_returns = [c for c in return_cols if c in df.columns]

    if not available_returns:
        print("No return columns (return_7d, return_30d, return_90d) found.")
        # Check price columns
        price_cols = [c for c in df.columns if "price" in c.lower()]
        print(f"Price-related columns: {price_cols}")
        if "price" in df.columns and "price_7d" in df.columns:
            buys["return_7d"] = (pd.to_numeric(buys["price_7d"], errors="coerce") -
                                 pd.to_numeric(buys["price"], errors="coerce")) / pd.to_numeric(buys["price"], errors="coerce") * 100
            available_returns.append("return_7d")
        if "price" in df.columns and "price_30d" in df.columns:
            buys["return_30d"] = (pd.to_numeric(buys["price_30d"], errors="coerce") -
                                  pd.to_numeric(buys["price"], errors="coerce")) / pd.to_numeric(buys["price"], errors="coerce") * 100
            available_returns.append("return_30d")
        if "price" in df.columns and "price_90d" in df.columns:
            buys["return_90d"] = (pd.to_numeric(buys["price_90d"], errors="coerce") -
                                  pd.to_numeric(buys["price"], errors="coerce")) / pd.to_numeric(buys["price"], errors="coerce") * 100
            available_returns.append("return_90d")

    if available_returns:
        for rc in available_returns:
            buys[rc] = pd.to_numeric(buys[rc], errors="coerce")

        print(f"\nReturn columns found: {available_returns}")
        print(f"\n{'─'*80}")
        print(f"{'Horizon':<12} {'N (has data)':>12} {'Avg Return %':>14} {'Median %':>10} "
              f"{'Win Rate %':>12} {'Avg Win %':>10} {'Avg Loss %':>12}")
        print(f"{'─'*80}")

        for rc in available_returns:
            valid = buys[rc].dropna()
            if len(valid) == 0:
                print(f"{rc:<12} {'0':>12} {'N/A':>14} {'N/A':>10} {'N/A':>12} {'N/A':>10} {'N/A':>12}")
                continue
            avg_ret = valid.mean()
            med_ret = valid.median()
            wins = (valid > 0).sum()
            losses = (valid <= 0).sum()
            win_rate = wins / len(valid) * 100
            avg_win = valid[valid > 0].mean() if wins > 0 else 0
            avg_loss = valid[valid <= 0].mean() if losses > 0 else 0

            print(f"{rc:<12} {len(valid):>12} {avg_ret:>14.2f} {med_ret:>10.2f} "
                  f"{win_rate:>12.1f} {avg_win:>10.2f} {avg_loss:>12.2f}")
        print(f"{'─'*80}")

        # Verdict
        for rc in available_returns:
            valid = buys[rc].dropna()
            if len(valid) > 0:
                avg = valid.mean()
                wr = (valid > 0).sum() / len(valid) * 100
                if avg <= 0:
                    print(f"\n  ⚠ {rc}: Average BUY return is NEGATIVE ({avg:.2f}%) — BUY signal may not be working.")
                elif wr < 50:
                    print(f"\n  ⚠ {rc}: Win rate below 50% ({wr:.1f}%) — more BUYs lose than win.")
                else:
                    print(f"\n  ✓ {rc}: Avg return {avg:.2f}%, win rate {wr:.1f}% — BUY signal appears functional.")
    else:
        print("\nNo return data available to assess BUY hit rate.")
        print("The price_7d/price_30d/price_90d columns appear empty — returns not yet tracked.")

    # Show sample of BUY records
    print(f"\nSample BUY records (first 10):")
    display_cols = ["date", "symbol", "action", "score", "price", "sector"]
    display_cols += [c for c in available_returns if c in buys.columns]
    avail_display = [c for c in display_cols if c in buys.columns]
    print(buys[avail_display].head(10).to_string(index=False))


def main():
    xlsx_path = load_latest_report()
    q11_sector_bias(xlsx_path)
    q12_recommendation_flipping(xlsx_path)
    q13_zombie_scores(xlsx_path)
    q14_buy_hit_rate(xlsx_path)

    print(f"\n\n{'='*90}")
    print("AUDIT Q11–Q14 COMPLETE")
    print(f"{'='*90}")


if __name__ == "__main__":
    main()
