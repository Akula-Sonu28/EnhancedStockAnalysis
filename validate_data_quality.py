import pandas as pd, glob, warnings, numpy as np
warnings.filterwarnings('ignore')

xl = pd.read_excel(sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))[-1], sheet_name='Portfolio Allocation')
own = xl[xl['I_OWN_IT?']==True].copy()
all_s = xl.copy()

pass_count = 0
fail_count = 0
warn_count = 0

def chk(label, cond, msg='', warn=False):
    global pass_count, fail_count, warn_count
    if cond:
        print(f"  PASS  {label}")
        pass_count += 1
    else:
        tag = "WARN" if warn else "FAIL"
        print(f"  {tag}  {label}{(' | ' + msg) if msg else ''}")
        if warn: warn_count += 1
        else: fail_count += 1

def show_rows(df, cols):
    sub = [c for c in cols if c in df.columns]
    if len(df): print(df[sub].to_string(index=False))

print("=" * 70)
print("COLUMN COMPLETENESS & CONTRADICTION CHECK")
print(f"Report: {sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))[-1]}")
print(f"Total rows: {len(all_s)}  |  Owned: {len(own)}")
print("=" * 70)

# ── 1. REQUIRED COLUMNS EXIST ──────────────────────────────────────────
print("\n[1] REQUIRED COLUMNS EXIST")
required = ['symbol','ACTION','MY_PROFIT_%','STOP_LOSS','BOOK_%_IF_SELL',
            'WHEN_TO_ACT','ROTATION_TARGET','ROTATION_TRIGGER_PRICE',
            'RSI','ML_SIGNAL','SCORE','RISK','SUPPORT','RESISTANCE',
            'EXIT_SCORE','PRICE']
for c in required:
    chk(f"Column '{c}'", c in xl.columns)

# ── 2. CRITICAL NULL CHECKS (owned stocks) ────────────────────────────
print("\n[2] NULL / MISSING DATA (owned stocks only)")
chk("STOP_LOSS populated for all owned",
    own['STOP_LOSS'].notna().all(),
    f"Missing: {list(own[own['STOP_LOSS'].isna()]['symbol'])}")

chk("ACTION not null for any owned",
    own['ACTION'].notna().all(),
    f"Missing: {list(own[own['ACTION'].isna()]['symbol'])}")

chk("SCORE not null for any owned",
    own['SCORE'].notna().all(),
    f"Missing: {list(own[own['SCORE'].isna()]['symbol'])}")

chk("RSI not null for owned",
    own['RSI'].notna().all(),
    f"Missing: {list(own[own['RSI'].isna()]['symbol'])}")

chk("ML_SIGNAL not null for owned",
    own['ML_SIGNAL'].notna().all(),
    f"Missing: {list(own[own['ML_SIGNAL'].isna()]['symbol'])}")

chk("PRICE > 0 for all owned",
    (own['PRICE'].fillna(0) > 0).all(),
    f"Zero/null price: {list(own[own['PRICE'].fillna(0)<=0]['symbol'])}")

chk("SUPPORT > 0 for all owned",
    (own['SUPPORT'].fillna(0) > 0).all(),
    f"Missing support: {list(own[own['SUPPORT'].fillna(0)<=0]['symbol'])}")

# ── 3. STOP_LOSS LOGIC ────────────────────────────────────────────────
print("\n[3] STOP_LOSS LOGIC CONSISTENCY")
if 'STOP_LOSS' in own.columns and 'PRICE' in own.columns:
    # Stop-loss must be BELOW current price
    sl_above = own[(own['STOP_LOSS'].notna()) & (own['STOP_LOSS'] >= own['PRICE'])]
    chk("STOP_LOSS < PRICE for all owned",
        len(sl_above) == 0,
        f"SL >= Price: {list(sl_above['symbol'])}")
    # Stop-loss must be ABOVE zero
    sl_zero = own[(own['STOP_LOSS'].notna()) & (own['STOP_LOSS'] <= 0)]
    chk("STOP_LOSS > 0",
        len(sl_zero) == 0,
        f"Zero SL: {list(sl_zero['symbol'])}")
    # Stop-loss should be near support (~97%)
    if 'SUPPORT' in own.columns:
        sl_far = own[(own['STOP_LOSS'].notna()) & (own['SUPPORT']>0) &
                     (abs(own['STOP_LOSS'] - own['SUPPORT']*0.97) > own['SUPPORT']*0.05)]
        chk("STOP_LOSS within 5% of SUPPORT×0.97",
            len(sl_far) == 0,
            f"Outliers: {list(sl_far['symbol'])}", warn=True)

# ── 4. BOOKING LOGIC CONTRADICTIONS ──────────────────────────────────
print("\n[4] PROFIT BOOKING CONTRADICTIONS")
if 'BOOK_%_IF_SELL' in own.columns and 'MY_PROFIT_%' in own.columns:
    # No booking plan on stocks at a loss
    book_at_loss = own[(own['BOOK_%_IF_SELL'].notna()) & (own['BOOK_%_IF_SELL']>0) &
                       (own['MY_PROFIT_%'] < 0)]
    chk("No BOOK_%_IF_SELL on losing positions",
        len(book_at_loss) == 0,
        f"Loss + booking plan: {list(book_at_loss['symbol'])}")
    # Booking % must be between 0 and 1
    bad_pct = own[(own['BOOK_%_IF_SELL'].notna()) &
                  ((own['BOOK_%_IF_SELL'] <= 0) | (own['BOOK_%_IF_SELL'] > 1))]
    chk("BOOK_%_IF_SELL in range (0,1]",
        len(bad_pct) == 0,
        f"Out of range: {list(bad_pct[['symbol','BOOK_%_IF_SELL']].values)}")

# ── 5. ACTION vs ML CONTRADICTIONS ───────────────────────────────────
print("\n[5] ACTION vs ML_SIGNAL CONTRADICTIONS")
# INCREASE on ML=SELL (without STRONG_BUY override)
inc_ml_sell = own[(own['ACTION'].astype(str).str.upper()=='INCREASE') &
                  (own['ML_SIGNAL'].astype(str).str.upper()=='SELL')]
chk("No INCREASE where ML=SELL",
    len(inc_ml_sell) == 0,
    f"Conflict: {list(inc_ml_sell['symbol'])}", warn=True)

# SELL/SWAP on ML=HOLD/STRONG_BUY at a loss (loss crystallisation)
loss_sell_ml_hold = own[
    (own['ACTION'].astype(str).str.upper().str.contains('^SELL$')) &
    (own['MY_PROFIT_%'] < 0) &
    (own['ML_SIGNAL'].astype(str).str.upper().isin(['HOLD','STRONG_BUY']))
]
chk("No pure SELL on loss+ML=HOLD (MI-L04)",
    len(loss_sell_ml_hold) == 0,
    f"Violations: {list(loss_sell_ml_hold['symbol'])}")

# INCREASE on >2% loss
inc_big_loss = own[(own['ACTION'].astype(str).str.upper()=='INCREASE') &
                   (own['MY_PROFIT_%'] < -0.02)]
chk("No INCREASE on >2% loss positions (RT-08)",
    len(inc_big_loss) == 0,
    f"Violations: {list(inc_big_loss['symbol'])}")

# PRE-BREAKOUT on losing positions >2%
pb_loss = own[(own['ACTION'].astype(str).str.contains('PRE-BREAKOUT', na=False)) &
              (own['MY_PROFIT_%'] < -0.02)]
chk("No PRE-BREAKOUT on >2% loss (RT-08C)",
    len(pb_loss) == 0,
    f"Violations: {list(pb_loss['symbol'])}")

# ── 6. ACTION vs RSI CONTRADICTIONS ──────────────────────────────────
print("\n[6] ACTION vs RSI CONTRADICTIONS")
# INCREASE on overbought RSI>72
inc_overbought = own[(own['ACTION'].astype(str).str.upper()=='INCREASE') & (own['RSI']>72)]
chk("No INCREASE on RSI > 72",
    len(inc_overbought) == 0,
    f"Risky: {list(inc_overbought[['symbol','RSI']].values)}", warn=True)

# SKIP getting money allocated (GA-01)
if 'INVEST_\u20b9' in xl.columns:
    skip_funded = xl[(xl['ACTION'].astype(str).str.contains('SKIP', na=False)) &
                     (xl['INVEST_\u20b9'].fillna(0) > 0)]
    chk("SKIP actions get zero investment (GA-01)",
        len(skip_funded) == 0,
        f"SKIP with money: {list(skip_funded['symbol'])}")
else:
    print("  WARN  INVEST_Rs column not found — skipping GA-01 check")
    warn_count += 1

# ── 7. ROTATION TARGET QUALITY ───────────────────────────────────────
print("\n[7] ROTATION TARGET QUALITY")
rot = own[own['ROTATION_TARGET'].notna() & (own['ROTATION_TARGET'].astype(str).str.strip() != '')]
if len(rot):
    for _, r in rot.iterrows():
        tgt = r['ROTATION_TARGET']
        tgt_row = xl[xl['symbol'] == tgt]
        if len(tgt_row):
            tgt_risk = str(tgt_row['RISK'].values[0]).upper()
            tgt_rsi  = float(tgt_row['RSI'].values[0]) if 'RSI' in tgt_row.columns else 50
            bad_risk = tgt_risk in ('HIGH','VERY HIGH')
            overbought = tgt_rsi > 65
            chk(f"Rotation target {tgt} risk={tgt_risk} RSI={tgt_rsi:.0f}",
                not bad_risk and not overbought,
                f"Risk/RSI issue", warn=True)
        else:
            print(f"  WARN  Rotation target {tgt} not found in universe")
            warn_count += 1
else:
    print("  INFO  No rotation targets assigned in this run")

# ── 8. ROTATION_TRIGGER_PRICE LOGIC ──────────────────────────────────
print("\n[8] ROTATION_TRIGGER_PRICE LOGIC")
rtp = own[own['ROTATION_TRIGGER_PRICE'].notna()]
if len(rtp):
    # Must be below current price (trigger = price drops to this level, then rotate)
    rtp_above = rtp[rtp['ROTATION_TRIGGER_PRICE'] >= rtp['PRICE']]
    chk("ROTATION_TRIGGER_PRICE < PRICE",
        len(rtp_above) == 0,
        f"Above price: {list(rtp_above['symbol'])}")
    # Should match STOP_LOSS (both are support×0.97)
    if 'STOP_LOSS' in rtp.columns:
        rtp_mismatch = rtp[(rtp['STOP_LOSS'].notna()) &
                           (abs(rtp['ROTATION_TRIGGER_PRICE'] - rtp['STOP_LOSS']) > 1.0)]
        chk("ROTATION_TRIGGER_PRICE matches STOP_LOSS",
            len(rtp_mismatch) == 0,
            f"Mismatch: {list(rtp_mismatch['symbol'])}", warn=True)
else:
    print("  INFO  No ROTATION_TRIGGER_PRICE set (only for HOLD+loss stocks)")

# ── 9. WHEN_TO_ACT POPULATED FOR ACTIONABLE ──────────────────────────
print("\n[9] WHEN_TO_ACT COMPLETENESS")
actionable_kw = ['SELL','SWAP','INCREASE','PRE-BREAKOUT','BUY','NEW POSITION','BREAKOUT']
actionable = own[own['ACTION'].astype(str).apply(lambda x: any(k in x.upper() for k in actionable_kw))]
when_missing = actionable[actionable['WHEN_TO_ACT'].isna()]
chk(f"WHEN_TO_ACT filled for actionable stocks ({len(actionable)} stocks)",
    len(when_missing) == 0,
    f"Missing timing: {list(when_missing['symbol'])}", warn=True)

# ── 10. SCORE RANGE SANITY ────────────────────────────────────────────
print("\n[10] SCORE SANITY")
chk("All SCORE values 0–100",
    ((xl['SCORE'].dropna() >= 0) & (xl['SCORE'].dropna() <= 100)).all(),
    f"Out of range: {len(xl[(xl['SCORE']<0)|(xl['SCORE']>100)])} rows")
chk("All RSI values 0–100",
    ((xl['RSI'].dropna() >= 0) & (xl['RSI'].dropna() <= 100)).all(),
    f"Out of range: {len(xl[(xl['RSI']<0)|(xl['RSI']>100)])} rows")
if 'MY_PROFIT_%' in own.columns:
    extreme_pnl = own[own['MY_PROFIT_%'].abs() > 5.0]  # >500% gain/loss — likely data error
    chk("No extreme PnL values (>500%)",
        len(extreme_pnl) == 0,
        f"Suspect: {list(extreme_pnl[['symbol','MY_PROFIT_%']].values)}")

# ── FINAL SUMMARY ─────────────────────────────────────────────────────
total = pass_count + fail_count + warn_count
print("\n" + "=" * 70)
print(f"FINAL RESULT:  {pass_count} PASS  |  {warn_count} WARN  |  {fail_count} FAIL  |  {total} total checks")
if fail_count == 0 and warn_count == 0:
    print("  ALL CLEAR — data is consistent with no contradictions")
elif fail_count == 0:
    print(f"  NO CRITICAL FAILURES — {warn_count} minor warnings worth reviewing")
else:
    print(f"  {fail_count} CRITICAL ISSUES need fixing")
print("=" * 70)
