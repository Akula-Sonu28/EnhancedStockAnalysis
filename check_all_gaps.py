import pandas as pd, glob, warnings; warnings.filterwarnings('ignore')
xl = pd.read_excel(sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))[-1], sheet_name='Portfolio Allocation')
own = xl[xl['I_OWN_IT?']==True].copy()

print("=" * 60)
print("16-GAP VERIFICATION REPORT")
print("=" * 60)

# L-01 / C-01: STOP_LOSS column exists and populated
sl_count = own['STOP_LOSS'].notna().sum() if 'STOP_LOSS' in own.columns else 0
status = "PASS" if sl_count == len(own) else f"PARTIAL ({sl_count}/{len(own)})"
print(f"\nL-01 / C-01  No stop-loss column:          {status}")

# L-02: No INCREASE on losers >2%
bad_inc = own[(own['ACTION'].astype(str).str.upper()=='INCREASE') & (own['MY_PROFIT_%'] < -0.02)] if 'MY_PROFIT_%' in own.columns else pd.DataFrame()
status = "PASS" if len(bad_inc)==0 else f"FAIL ({len(bad_inc)} violations: {list(bad_inc['symbol'])})"
print(f"L-02         Averaging down into losers:    {status}")

# L-04: BAJAJHLDNG and GICRE not SELL at loss
bajaj_act = own[own['symbol']=='BAJAJHLDNG']['ACTION'].values[0] if len(own[own['symbol']=='BAJAJHLDNG']) else 'NOT FOUND'
gicre_act = own[own['symbol']=='GICRE']['ACTION'].values[0] if len(own[own['symbol']=='GICRE']) else 'NOT FOUND'
fail_l04 = [s for s,a in [('BAJAJHLDNG',bajaj_act),('GICRE',gicre_act)] if 'SELL' in str(a).upper() and 'SWAP' not in str(a).upper()]
status = "PASS" if not fail_l04 else f"FAIL {fail_l04}"
print(f"L-04         Selling losses (ML=HOLD):      {status}  [{bajaj_act} / {gicre_act}]")

# P-05 / P-01 / P-02 / P-03 / P-04: Booking plans
book_rows = own[own['BOOK_%_IF_SELL'].notna()] if 'BOOK_%_IF_SELL' in own.columns else pd.DataFrame()
profitable = own[own['MY_PROFIT_%'] > 0.0] if 'MY_PROFIT_%' in own.columns else pd.DataFrame()
print(f"\nP-01/02/03/04/05  Profit booking plan:     {len(book_rows)} stocks have booking plan")
if len(book_rows):
    for _, r in book_rows.iterrows():
        when = r.get('WHEN_TO_ACT', '')
        print(f"    {r['symbol']:<12} Book {r['BOOK_%_IF_SELL']:.0%}  PnL={r['MY_PROFIT_%']:+.1%}  {when}")
else:
    print("    No booking plans found!")

# R-01/R-02/R-03: Rotation targets quality-filtered
rot = own[own['ROTATION_TARGET'].notna() & (own['ROTATION_TARGET'].astype(str).str.strip() != '')] if 'ROTATION_TARGET' in own.columns else pd.DataFrame()
print(f"\nR-01/02/03   Rotation targets assigned:    {len(rot)} stocks")
for _, r in rot.iterrows():
    print(f"    {r['symbol']:<12} -> {r['ROTATION_TARGET']}")

# R-04: Selling only winners for rotation (not losers at a loss without protection)
loss_sells = own[(own['ACTION'].astype(str).str.upper().str.contains('SWAP|SELL')) & (own['MY_PROFIT_%'] < -0.05)] if 'MY_PROFIT_%' in own.columns else pd.DataFrame()
ml_guarded = loss_sells[loss_sells.get('ML_SIGNAL', pd.Series()).isin(['HOLD','STRONG_BUY'])] if len(loss_sells) else pd.DataFrame()
print(f"\nR-04         Loss rotation without ML guard: {len(loss_sells)-len(ml_guarded)} unprotected")

# C-03/C-04: EXHAUSTION surfaced and actioned
if 'EXIT_SCORE' in own.columns:
    exhaust = own[own['EXIT_SCORE'] > 30]
    print(f"\nC-03/C-04    EXIT_SCORE>30 stocks:         {len(exhaust)}")
    for _, r in exhaust.iterrows():
        act = r['ACTION']
        when = r.get('WHEN_TO_ACT', 'no timing')
        print(f"    {r['symbol']:<12} EXIT={r['EXIT_SCORE']:.0f}  ACTION={act}  WHEN={when}")
else:
    print("\nC-03/C-04    EXIT_SCORE column: NOT FOUND")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Owned stocks:          {len(own)}")
print(f"  With STOP_LOSS:        {sl_count}")
print(f"  With booking plan:     {len(book_rows)}")
print(f"  With rotation target:  {len(rot)}")
print(f"  INCREASE on losers:    {len(bad_inc)} (want 0)")
print(f"  BAJAJHLDNG action:     {bajaj_act}")
print(f"  GICRE action:          {gicre_act}")
