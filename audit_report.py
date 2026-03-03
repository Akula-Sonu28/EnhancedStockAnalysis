"""audit_report.py — Automated data quality audit on latest Portfolio Allocation sheet"""
import pandas as pd, glob, warnings, numpy as np
warnings.filterwarnings('ignore')

f = sorted([x for x in glob.glob("reports/*.xlsx") if "~" not in x])[-1]
df = pd.read_excel(f, sheet_name="Portfolio Allocation")
# Handle both UTF-8 ₹ and Windows-1252 Γé╣ encoding of the rupee symbol
df.rename(columns={c: c.replace("₹", "Rs").replace("Γé╣", "Rs") for c in df.columns}, inplace=True)

print("=" * 60)
print("DATA QUALITY AUDIT")
print(f"Report : {f.split(chr(92))[-1]}")
print(f"Stocks : {len(df)}")
print("=" * 60)

issues = []

def syms(mask):
    return df[mask]["symbol"].tolist()

def bad_col(subset, col, label):
    if col not in subset.columns:
        return
    m = subset[col].isna() | (pd.to_numeric(subset[col], errors="coerce").fillna(0) == 0)
    bad = subset[m]
    if len(bad):
        issues.append((label, bad["symbol"].tolist()))

# ── Numeric helpers ───────────────────────────────────────────────
df["_price"] = pd.to_numeric(df["PRICE"],     errors="coerce")
df["_score"] = pd.to_numeric(df["SCORE"],     errors="coerce")
df["_sup"]   = pd.to_numeric(df["SUPPORT"],   errors="coerce").fillna(0)
df["_res"]   = pd.to_numeric(df["RESISTANCE"],errors="coerce").fillna(0)
df["_sl"]    = pd.to_numeric(df["STOP_LOSS"], errors="coerce").fillna(0)
df["_rsi"]   = pd.to_numeric(df["RSI"],       errors="coerce")
df["_pnl"]   = pd.to_numeric(df["MY_PROFIT_%"], errors="coerce")
df["_sh"]    = pd.to_numeric(df["MY_SHARES"], errors="coerce").fillna(0)
# Use INVEST_Rs after rename; fallback to zero Series if column missing
_inv_col = "INVEST_Rs" if "INVEST_Rs" in df.columns else None
df["_inv"]   = pd.to_numeric(df[_inv_col] if _inv_col else pd.Series(0, index=df.index), errors="coerce").fillna(0)
df["_bsh"]   = pd.to_numeric(df["BUY_SHARES"],errors="coerce").fillna(0)
df["_fs"]    = pd.to_numeric(df["FUND_SCORE"],errors="coerce").fillna(0)
df["_ms"]    = pd.to_numeric(df["MOM_SCORE"], errors="coerce").fillna(0)
df["_vs"]    = pd.to_numeric(df["VALUE_SCORE"],errors="coerce").fillna(0)

owned     = df[df["_sh"] > 0]
buy_mask  = df["ACTION"].str.contains("PRE-BREAKOUT|NEW POSITION|INCREASE|BUY", na=False, case=False) & ~df["ACTION"].str.contains("SMALL ENTRY", na=False, case=False)
buy_df    = df[buy_mask]
sell_mask = df["ACTION"].str.contains("SELL|SWAP", na=False, case=False)
sell_df   = df[sell_mask]
act_mask  = df["ACTION"].str.contains("PRE-BREAKOUT|NEW POSITION|SELL|SWAP|INCREASE", na=False, case=False)

# 1. PRICE = 0 or NaN for any stock
bad = df[df["_price"].isna() | (df["_price"] == 0)]
if len(bad): issues.append(("[1] PRICE missing/zero", bad["symbol"].tolist()))

# 2. SCORE = 0 or NaN
bad = df[df["_score"].isna() | (df["_score"] == 0)]
if len(bad): issues.append(("[2] SCORE missing/zero", bad["symbol"].tolist()))

# 3. Owned stocks missing STOP_LOSS
bad = owned[owned["_sl"] == 0]
if len(bad): issues.append(("[3] OWNED: STOP_LOSS missing", bad["symbol"].tolist()))

# 4. Owned stocks with RSI = 0 or NaN
bad = owned[owned["_rsi"].isna() | (owned["_rsi"] == 0)]
if len(bad): issues.append(("[4] OWNED: RSI missing/zero", bad["symbol"].tolist()))

# 5. Owned stocks missing SUPPORT
bad = owned[owned["_sup"] == 0]
if len(bad): issues.append(("[5] OWNED: SUPPORT = 0", bad["symbol"].tolist()))

# 6. Owned stocks missing RESISTANCE
bad = owned[owned["_res"] == 0]
if len(bad): issues.append(("[6] OWNED: RESISTANCE = 0", bad["symbol"].tolist()))

# 7. BUY stocks where BUY_SHARES > 0 but INVEST is 0 (calc error, not budget-constrained unfunded)
bad = buy_df[(buy_df["_bsh"] > 0) & (buy_df["_inv"] == 0)]
if len(bad): issues.append(("[7] BUY: BUY_SHARES>0 but INVEST_Rs=0 (calc error)", bad["symbol"].tolist()))
# 7b. Unfunded buys: recommended but budget ran out (informational, not an error)
unfunded = buy_df[(buy_df["_bsh"] == 0) & (buy_df["_inv"] == 0)]
if len(unfunded): issues.append(("[7b] INFO: Unfunded BUY recs (budget ran out - not an error)", unfunded["symbol"].tolist()))

# 8. BUY stocks FUNDED (INVEST > 0) but BUY_SHARES still 0 (price-calc bug)
bad = buy_df[(buy_df["_inv"] > 0) & (buy_df["_bsh"] == 0)]
if len(bad): issues.append(("[8] BUY: INVEST>0 but BUY_SHARES=0 (share-calc bug)", bad["symbol"].tolist()))

# 9. BUY stocks missing STOP_LOSS
bad = buy_df[buy_df["_sl"] == 0]
if len(bad): issues.append(("[9] BUY: STOP_LOSS missing", bad["symbol"].tolist()))

# 10. SUPPORT > PRICE (impossible)
bad = df[(df["_sup"] > 0) & (df["_price"] > 0) & (df["_sup"] > df["_price"])]
if len(bad): issues.append(("[10] SUPPORT > PRICE", bad[["symbol","_sup","_price"]].values.tolist()))

# 11. RESISTANCE < PRICE (impossible)
bad = df[(df["_res"] > 0) & (df["_price"] > 0) & (df["_res"] < df["_price"])]
if len(bad): issues.append(("[11] RESISTANCE < PRICE", bad[["symbol","_res","_price"]].values.tolist()))

# 12. STOP_LOSS >= PRICE (useless — should always be below price)
bad = df[(df["_sl"] > 0) & (df["_price"] > 0) & (df["_sl"] >= df["_price"])]
if len(bad): issues.append(("[12] STOP_LOSS >= PRICE", bad[["symbol","_sl","_price"]].values.tolist()))

# 13. RSI out of 0-100
bad = df[df["_rsi"].notna() & ((df["_rsi"] < 0) | (df["_rsi"] > 100))]
if len(bad): issues.append(("[13] RSI out of range 0-100", bad[["symbol","_rsi"]].values.tolist()))

# 14. SCORE out of 0-100
bad = df[df["_score"].notna() & ((df["_score"] < 0) | (df["_score"] > 100))]
if len(bad): issues.append(("[14] SCORE out of range 0-100", bad[["symbol","_score"]].values.tolist()))

# 15. SELL/SWAP missing ROTATION_TARGET
if "ROTATION_TARGET" in df.columns:
    bad = sell_df[sell_df["ROTATION_TARGET"].isna() | (sell_df["ROTATION_TARGET"].astype(str).str.strip() == "")]
    if len(bad): issues.append(("[15] SELL/SWAP: ROTATION_TARGET missing", bad["symbol"].tolist()))

# 16. All component scores zero but total SCORE > 0
bad = df[(df["_fs"] == 0) & (df["_ms"] == 0) & (df["_vs"] == 0) & (df["_score"] > 0)]
if len(bad): issues.append(("[16] Zero FUND/MOM/VALUE scores but SCORE > 0", bad["symbol"].tolist()))

# 17. PnL out of plausible range (stored as decimal: >5 = >500%, <-1 = <-100%)
bad = df[df["_pnl"].notna() & ((df["_pnl"] > 5) | (df["_pnl"] < -1))]
if len(bad): issues.append(("[17] PNL out of range", [[r["symbol"], round(r["_pnl"]*100,1)] for _,r in bad.iterrows()]))

# 18. WHEN_TO_ACT missing for actionable stocks
if "WHEN_TO_ACT" in df.columns:
    bad = df[act_mask & (df["WHEN_TO_ACT"].isna() | (df["WHEN_TO_ACT"].astype(str).str.strip().isin(["", "nan"])))]
    if len(bad): issues.append(("[18] Actionable stocks missing WHEN_TO_ACT", bad["symbol"].tolist()))

# 19. PRE_BREAKOUT? flag=0 but ACTION says PRE-BREAKOUT
if "PRE_BREAKOUT?" in df.columns:
    pb_act = df[df["ACTION"].str.contains("PRE-BREAKOUT", na=False)]
    bad = pb_act[pd.to_numeric(pb_act["PRE_BREAKOUT?"], errors="coerce").fillna(0) == 0]
    if len(bad): issues.append(("[19] PRE_BREAKOUT flag=0 but action=PRE-BREAKOUT", bad["symbol"].tolist()))

# 20. SWAP stocks: rotation target points to self
if "ROTATION_TARGET" in df.columns:
    swap_df = df[df["ACTION"].str.contains("SWAP", na=False)]
    bad = swap_df[swap_df.apply(lambda r: str(r.get("ROTATION_TARGET","")).strip() == str(r["symbol"]).strip(), axis=1)]
    if len(bad): issues.append(("[20] SWAP: rotation target is same stock", bad["symbol"].tolist()))

# 21. MY_VALUE_Rs inconsistency: MY_SHARES > 0 but MY_VALUE = 0
if "MY_VALUE_Rs" in df.columns:
    df["_mv"] = pd.to_numeric(df["MY_VALUE_Rs"], errors="coerce").fillna(0)
    bad = df[(df["_sh"] > 0) & (df["_mv"] == 0)]
    if len(bad): issues.append(("[21] OWNED: MY_VALUE = 0 but MY_SHARES > 0", bad["symbol"].tolist()))

# 22. Non-owned stocks with non-zero MY_PROFIT
bad = df[(df["_sh"] == 0) & (df["_pnl"].notna()) & (df["_pnl"] != 0)]
if len(bad): issues.append(("[22] Not owned but MY_PROFIT != 0", bad["symbol"].tolist()))

# ── Print results ─────────────────────────────────────────────────
if not issues:
    print("\n  All 22 checks PASSED - No issues found!\n")
else:
    print(f"\n  Issues found: {len(issues)}\n")
    for label, detail in issues:
        print(f"  {label}")
        print(f"    -> {detail}")
        print()

print("=" * 60)
