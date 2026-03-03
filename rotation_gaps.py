"""
Capital Rotation Gap Analysis
Philosophy: Rotate capital FROM losers INTO winners. Capital loss is acceptable.
Goal: Identify what BLOCKS or SLOWS rotation in the current system.
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np

f = 'reports/Enhanced_Stock_Report_20260302_182808.xlsx'
pa = pd.read_excel(f, sheet_name='Portfolio Allocation')
cd = pd.read_excel(f, sheet_name='Complete Data')

invest_col = [c for c in pa.columns if 'INVEST' in str(c)][0]
my_val_col  = [c for c in pa.columns if 'MY_VALUE' in str(c)][0]

owned = pa[pa['I_OWN_IT?'] == True].copy()
owned['pnl_pct'] = owned['MY_PROFIT_%'] * 100
owned['pnl_rs']  = owned.apply(
    lambda r: r[my_val_col] - (r[my_val_col] / (1 + r['MY_PROFIT_%'])) if r['MY_PROFIT_%'] != -1 else -r[my_val_col], axis=1)

losers  = owned[owned['pnl_pct'] < 0].sort_values('pnl_pct')
winners = owned[owned['pnl_pct'] > 5].sort_values('pnl_pct', ascending=False)

# High-score un-owned stocks (rotation destinations)
sc_col = 'final_blended_score'
rsi_col = 'real_rsi'
win_pool = cd[~cd['symbol'].isin(owned['symbol'])].copy()
win_pool = win_pool.sort_values(sc_col, ascending=False)

SEP = '=' * 72
gaps = []

def gap(gid, sev, title, body):
    sym = {'CRITICAL': '[CRITICAL]', 'HIGH': '[HIGH]', 'MEDIUM': '[MEDIUM]', 'LOW': '[LOW]'}[sev]
    gaps.append((gid, sev, title))
    print('\n{} RT-{}: {}'.format(sym, gid, title))
    print(body)

# =============================================================================
# SECTION 1 — STUCK CAPITAL: Losers with no exit trigger
# =============================================================================
print(SEP)
print('SECTION 1 — STUCK CAPITAL  (Losers sitting with no rotation trigger)')
print(SEP)

print('\n  [All 13 losers — capital that should be rotating]:')
total_stuck = losers[my_val_col].sum()
for _, r in losers.iterrows():
    action_note = ''
    if r['ACTION'] == 'HOLD': action_note = '<<< STUCK — no exit trigger'
    elif r['ACTION'] == 'INCREASE': action_note = '<<< ANTI-ROTATION — adding MORE'
    elif r['ACTION'] == 'SELL': action_note = '--> exiting (good)'
    elif 'SWAP' in str(r['ACTION']): action_note = '--> swapping (good IF target wins)'
    elif 'SKIP' in str(r['ACTION']): action_note = '<<< STUCK — SKIP means nothing happens'
    print('    {:<13} {:>+6.2f}%  Rs {:>7,.0f}  Score={:>5.1f}  RSI={:>5.1f}  ML={:<8}  {}'.format(
        r['symbol'], r['pnl_pct'], r[my_val_col], r['SCORE'], r['RSI'], r['ML_SIGNAL'], action_note))

print('\n  Total capital stuck in losers: Rs {:,.0f}'.format(total_stuck))

# HOLDs that are losers — completely stuck
hold_losers = losers[losers['ACTION'] == 'HOLD']
gap('01', 'CRITICAL',
    '{} HOLD losers — Rs {:,.0f} has ZERO rotation trigger'.format(len(hold_losers), hold_losers[my_val_col].sum()),
    hold_losers[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'SCORE', 'RSI', '20D_CHANGE_%', 'ML_SIGNAL', 'EXIT_SCORE']].to_string(index=False) +
    '\n\n  ACTION=HOLD means the allocator decided: do nothing. No price exit. No time exit.\n  Capital stays in losers indefinitely. For a rotation investor this is the worst outcome.')

# INCREASE on losers — ANTI-rotation
inc_losers = losers[losers['ACTION'] == 'INCREASE']
gap('02', 'CRITICAL',
    '{} INCREASE on losers — system is sending MORE capital INTO losing positions'.format(len(inc_losers)),
    inc_losers[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'pnl_rs', 'SCORE', 'RSI', 'ML_SIGNAL', invest_col]].to_string(index=False) +
    '\n\n  BANKBARODA: -1.25% loss + RSI=73 (near top) + ML=SELL. System scores it 100 (FBS)\n  but wants to BUY MORE into a position already at a loss and at resistance.\n  UCOBANK: -3.47% loss + ML=BUY (good) but buying losers, not rotating to better stocks.\n\n  BUG in allocator: FBS=100 triggers INCREASE regardless of current position P/L.')

# IDBI SKIP with Rs 31,766 value — capital parked
idbi = losers[losers['symbol'] == 'IDBI']
gap('03', 'HIGH',
    'IDBI: SKIP action on Rs 31,766 value — capital parked with no rotation plan',
    idbi[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'SCORE', 'RSI', 'EXIT_SCORE', 'EXHAUSTION?', 'ML_SIGNAL']].to_string(index=False) +
    '\n\n  IDBI has EXIT_SCORE=45, EXHAUSTION=True, RSI=68.7 (near top).\n  System should say: EXIT and rotate. Instead it says: SKIP - WAIT.')

# =============================================================================
# SECTION 2 — ROTATION QUALITY: Are exits mapped to specific winners?
# =============================================================================
print('\n' + SEP)
print('SECTION 2 — ROTATION QUALITY  (Exits mapped to winners?)')
print(SEP)

print('\n  [Current exit-to-target mapping]:')
print('  {:<13} {:<30} {:<10} {}'.format('FROM', 'ACTION', 'VALUE', 'ROTATION TARGET?'))
print('  ' + '-' * 65)
exits = pa[pa['ACTION'].isin(['SELL', 'SWAP -> MAHABANK', 'SWAP -> ICICIPRULI'])]
total_freed = exits[my_val_col].sum()
for _, r in exits.iterrows():
    target = r['ACTION'].replace('SWAP -> ', '') if 'SWAP' in r['ACTION'] else 'UNSPECIFIED'
    target_score = ''
    if target != 'UNSPECIFIED':
        t = pa[pa['symbol'] == target]
        if len(t): target_score = 'Score={:.0f} RSI={:.0f}'.format(t['SCORE'].values[0], t['RSI'].values[0])
    print('  {:<13} {:<30} Rs {:>8,.0f}  -> {}'.format(
        r['symbol'], r['ACTION'], r[my_val_col], target_score if target_score else 'GENERAL POOL (no specific winner)'))

print('\n  Total freed capital: Rs {:,.0f}'.format(total_freed))

# SELL proceeds go to unspecified pool — not mapped to specific winners
sell_unspecified = exits[exits['ACTION'] == 'SELL']
gap('04', 'HIGH',
    'SELL proceeds (Rs {:,.0f}) go to unspecified pool — no rotation target assigned'.format(sell_unspecified[my_val_col].sum()),
    sell_unspecified[['symbol', 'ACTION', my_val_col, 'MY_PROFIT_%', 'SCORE', 'ML_SIGNAL', 'WHY']].to_string(index=False) +
    '\n\n  WHY = "REBALANCE - Better opportunities" is generic.\n  Rotation needs: FROM=BAJAJHLDNG -> TO=MAHABANK (with explicit score justification).\n  Without mapping, freed capital sits in wallet or gets mis-deployed.')

# Swap targets quality check
print('\n  [SWAP target quality — is the destination actually a winner?]:')
swap_rows = exits[exits['ACTION'].str.startswith('SWAP')]
for _, r in swap_rows.iterrows():
    target_name = r['ACTION'].replace('SWAP -> ', '')
    trow = pa[pa['symbol'] == target_name]
    if len(trow):
        t = trow.iloc[0]
        quality = []
        if t['RSI'] > 65: quality.append('RSI={:.0f} OVERBOUGHT'.format(t['RSI']))
        if t['ML_SIGNAL'] in ['SELL']: quality.append('ML=SELL')
        if t['RISK'] in ['HIGH', 'VERY HIGH']: quality.append('Risk={}'.format(t['RISK']))
        if t['20D_CHANGE_%'] < 0: quality.append('20D falling')
        status = ' | '.join(quality) if quality else 'CLEAN TARGET'
        print('    {} -> {} | Score={:.0f} RSI={:.1f} 20D={:+.1f}% | Issues: {}'.format(
            r['symbol'], target_name, t['SCORE'], t['RSI'], t['20D_CHANGE_%'], status))

gap('05', 'MEDIUM',
    'CASTROLIND swap target (MAHABANK) RSI=64, +17.3% in 20D — decent but not cheap entry',
    '  MAHABANK Score=100 is valid as rotation target (strong fundamental), but buying after\n  17% rally reduces rotation efficiency. No better-priced winner was evaluated.')

# =============================================================================
# SECTION 3 — WINNER POOL: Best available rotation targets NOT in portfolio
# =============================================================================
print('\n' + SEP)
print('SECTION 3 — WINNER POOL  (Top rotation targets available to enter)')
print(SEP)

print('\n  [Top 15 high-score stocks NOT currently owned — rotation candidates]:')
print('  {:<13} {:>6} {:>6} {:>8} {:>10} {:>10} {:>12} {}'.format(
    'SYMBOL', 'SCORE', 'RSI', 'ML', '20D%', 'PRICE', '52W_FROM_LOW%', 'SECTOR'))
for _, r in win_pool.head(20).iterrows():
    try:
        hi = float(r.get('52_week_high', r.get('52w_high', 0)))
        lo = float(r.get('52_week_low', r.get('52w_low', 0)))
        pr = float(r.get('current_price', 0))
        from_low = (pr - lo) / lo * 100 if lo > 0 else 0
        rsi_val = float(r.get(rsi_col, 0))
        rsi_flag = ' OB' if rsi_val > 68 else (' OK' if rsi_val < 58 else '')
        print('  {:<13} {:>6.1f} {:>6.1f}{} {:>8} {:>+10.1f}% {:>10.0f} {:>10.0f}%  {}'.format(
            r['symbol'], float(r[sc_col]), rsi_val, rsi_flag,
            r.get('ml_signal', '?'), float(r.get('20d_price_change', 0)),
            pr, from_low, str(r.get('sector', ''))[:20]))
    except: pass

# Count available low-RSI winners
good_rotation = win_pool[(win_pool[rsi_col] < 60) & (win_pool[sc_col] > 80)]
gap('06', 'MEDIUM',
    '{} high-score (>80) low-RSI (<60) stocks available but NOT in allocation plan'.format(len(good_rotation)),
    good_rotation[['symbol', sc_col, rsi_col, 'ml_signal', 'sector']].head(10).to_string(index=False) +
    '\n\n  The allocator only evaluates stocks already in its candidate list.\n  Winner pool is richer than what the current rotation plan taps into.')

# =============================================================================
# SECTION 4 — ROTATION BLOCKERS: Code-level bugs causing delays
# =============================================================================
print('\n' + SEP)
print('SECTION 4 — ROTATION BLOCKERS  (Code-level bugs that slow/block rotation)')
print(SEP)

gap('07', 'CRITICAL',
    'BUG: No "rotation_trigger_price" field — losers have no automatic exit level',
    '  Current logic: ACTION=HOLD with no price condition. Capital stays until next run.\n  Fix needed: Add stop_rotation_price = SUPPORT * 0.97 for every loser.\n  When price breaks below support, auto-trigger SELL and flag for rotation.\n  Without this, losers only get action on the next weekly analysis run.')

gap('08', 'CRITICAL',
    'BUG: INCREASE action ignores current position P/L — adds to losers',
    '  In analyze_top200_stocks_enhanced.py, INCREASE is triggered by score rank alone.\n  There is no check: "Is the current position at a loss?"\n  FBS=100 (BANKBARODA) -> INCREASE fires regardless of -1.25% current position loss.\n\n  Fix: Add guard: if i_own_it AND my_profit_pct < -2 AND ML != STRONG_BUY -> no INCREASE.')

gap('09', 'CRITICAL',
    'BUG: No ROTATION_TARGET column — SELL action has no destination winner',
    '  Current: SELL -> WHY = "REBALANCE". Capital freed but nowhere defined to put it.\n  BAJAJHLDNG freed Rs 83,928 -> the plan says nothing about which specific stock gets it.\n  A rotation investor needs: SELL_FROM + BUY_INTO as a linked pair.\n\n  Fix: Add "ROTATION_TARGET" column. When ACTION=SELL, populate with top-ranked\n  non-owned stock that has lowest RSI + highest score + correct sector.')

gap('10', 'HIGH',
    'BUG: WHEN_TO_ACT missing on 13 actionable stocks — rotation is timing-blind',
    '  SELL/SWAP/INCREASE/PRE-BREAKOUT on 13 stocks have no WHEN_TO_ACT.\n  Without timing, the rotation queue has no order of execution.\n  Question: Which loser exits FIRST and which winner enters FIRST?\n  System cannot answer this — rotation executes randomly or never.\n\n  Fix: Auto-populate WHEN_TO_ACT based on: RSI>70 -> "Within 2 days",\n  EXIT_SCORE>20 -> "Within 1 week", else "Within 2 weeks".')

gap('11', 'HIGH',
    'BUG: YESBANK tagged PRE-BREAKOUT (rotation destination) but is itself a loser',
    '  YESBANK: Pattern=BEARISH, RSI=28, 20D=-4.77%, BREAKOUT_%=0.\n  Rs 71,134 of rotation capital is destined to flow INTO a falling stock.\n  This negates the rotation: money leaves losers and enters another loser.\n\n  Fix: Block PRE-BREAKOUT if pattern_dominant_signal=bearish OR BREAKOUT_%=0.')

gap('12', 'HIGH',
    'BUG: ONGC PRE-BREAKOUT (rotation target) has RSI=69, up 13.7% in 20D',
    '  Rs 71,114 rotates into ONGC which has already made its move.\n  You are rotating capital into the TOP of a war-crude rally.\n  Ideal rotation timing: enter near SUPPORT (RSI 40-55), not near RESISTANCE.\n\n  Fix: Add entry_quality check: RSI>65 AND dist_from_support>8% -> downgrade to WATCHLIST.')

gap('13', 'MEDIUM',
    'BUG: IDBI SKIP+EXHAUSTION — Rs 31,766 is visible but locked with no rotation path',
    '  IDBI has EXIT_SCORE=45, EXHAUSTION=True, RSI=68.7 (near top), loss=-1.7%.\n  System should ROTATE OUT immediately. Instead: SKIP-WAIT.\n  The SKIP logic overrides all exit signals. Capital stays stuck.\n\n  Fix: If EXHAUSTION=True AND EXIT_SCORE>30 AND I_OWN_IT -> override SKIP with SELL+ROTATE.')

gap('14', 'MEDIUM',
    'BUG: Profitable stocks (SBIN +15.6%, INDIANB +7.7%) have no BOOK instruction',
    '  Profit booking creates rotation capital. Without booking, the rotation engine\n  has no self-funding mechanism — it relies on SELLs and fresh cash only.\n\n  Fix: Auto-set BOOK_%_IF_SELL = 0.25 when: pnl_pct > 10 OR (pnl_pct>5 AND RSI>65)\n  This auto-generates Rs 15,000-50,000 of rotation capital from existing winners.')

# =============================================================================
# SECTION 5 — ROTATION SCORE: How efficient is the current rotation plan?
# =============================================================================
print('\n' + SEP)
print('SECTION 5 — ROTATION EFFICIENCY SCORE')
print(SEP)

total_portfolio = owned[my_val_col].sum()
total_loser_val = losers[my_val_col].sum()
loser_rotating  = losers[losers['ACTION'].isin(['SELL', 'SWAP -> MAHABANK', 'SWAP -> ICICIPRULI'])][my_val_col].sum()
loser_stuck     = losers[losers['ACTION'] == 'HOLD'][my_val_col].sum()
loser_increasing= losers[losers['ACTION'] == 'INCREASE'][my_val_col].sum()
loser_parked    = losers[losers['ACTION'].str.contains('SKIP', na=False)][my_val_col].sum()

print('\n  [Rotation Efficiency Breakdown]:')
print('  Total portfolio value              : Rs {:>10,.0f}'.format(total_portfolio))
print('  Capital in losers                  : Rs {:>10,.0f}  ({:.1f}%)'.format(total_loser_val, total_loser_val/total_portfolio*100))
print()
print('  Of loser capital:')
print('    Being rotated (SELL/SWAP)        : Rs {:>10,.0f}  ({:.1f}% of loser capital)'.format(loser_rotating, loser_rotating/total_loser_val*100))
print('    STUCK (HOLD, no trigger)         : Rs {:>10,.0f}  ({:.1f}% of loser capital)'.format(loser_stuck, loser_stuck/total_loser_val*100))
print('    ANTI-ROTATED (INCREASE)          : Rs {:>10,.0f}  ({:.1f}% of loser capital)'.format(loser_increasing, loser_increasing/total_loser_val*100))
print('    PARKED (SKIP)                    : Rs {:>10,.0f}  ({:.1f}% of loser capital)'.format(loser_parked, loser_parked/total_loser_val*100))
print()

rotation_eff = loser_rotating / total_loser_val * 100
anti_rot     = (loser_stuck + loser_increasing + loser_parked) / total_loser_val * 100
print('  ROTATION EFFICIENCY SCORE         : {:.1f}%  (target: >70%)'.format(rotation_eff))
print('  ANTI-ROTATION SCORE               : {:.1f}%  (target: <20%)'.format(anti_rot))

if rotation_eff < 50:
    print('\n  VERDICT: System is BLOCKING rotation. More than half of loser capital has no exit.')
elif rotation_eff < 70:
    print('\n  VERDICT: Partial rotation. Significant loser capital still stuck.')
else:
    print('\n  VERDICT: Good rotation coverage.')

print('\n  [Where is freed capital going? Rotation TARGET quality]:')
new_buys = pa[pa['ACTION'].isin(['NEW POSITION', '🚀 PRE-BREAKOUT - BUY NOW'])].copy()
for _, r in new_buys.sort_values('SCORE', ascending=False).iterrows():
    alloc = r[invest_col]
    rsi_flag = ' OVERBOUGHT' if r['RSI'] > 67 else (' GOOD' if r['RSI'] < 58 else ' OK')
    bear_flag = ''
    pb = pa[pa['symbol'] == r['symbol']]
    if r['ACTION'] == '🚀 PRE-BREAKOUT - BUY NOW' and r.get('BREAKOUT_%', 0) == 0:
        bear_flag = ' NO-SETUP'
    print('    {:<13} Score={:>5.1f}  RSI={:>5.1f}{}{}  Rs {:>9,.0f}  Risk={}'.format(
        r['symbol'], r['SCORE'], r['RSI'], rsi_flag, bear_flag, alloc, r['RISK']))

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print('\n' + SEP)
print('FINAL GAP SUMMARY — Capital Rotation Investor')
print('Philosophy: Exit losers fast. Book winners partially. Rotate into better stocks.')
print(SEP)

sev_sym = {'CRITICAL': '[CRITICAL]', 'HIGH': '[HIGH]', 'MEDIUM': '[MEDIUM]'}
for gid, sev, title in gaps:
    print('  {} RT-{}: {}'.format(sev_sym[sev], gid, title))

print()
print('  Total: {} gaps  |  Critical: {}  |  High: {}  |  Medium: {}'.format(
    len(gaps),
    sum(1 for _, s, _ in gaps if s == 'CRITICAL'),
    sum(1 for _, s, _ in gaps if s == 'HIGH'),
    sum(1 for _, s, _ in gaps if s == 'MEDIUM')))

print()
print('  === ROTATION ACTION QUEUE (priority order) ===')
print('  1. EXIT FIRST (today/tomorrow):')
print('     - IDBI: EXIT now (EXHAUSTION=True, RSI=68.7, EXIT_SCORE=45) -> rotate to HDFCBANK')
print('     - BANKBARODA: STOP INCREASE. Set rotation trigger at RSI<60 -> rotate when it dips')
print('     - UCOBANK: Same — stop adding. ML=BUY so hold but no more capital in')
print()
print('  2. BOOK PROFIT to create rotation fuel:')
print('     - UNIONBANK: Book 30% NOW (RSI=72, +28.4%) -> Rs 15,177 freed for rotation')
print('     - SBIN: Book 25% (RSI=63, +15.6%) -> Rs ~9,750 freed for rotation')
print('     - INDIANB: Book 25% (RSI=68, +7.7%) -> Rs ~7,500 freed for rotation')
print()
print('  3. ROTATE INTO (in order of entry quality):')
print('     - HDFCBANK (Score=79.9, RSI=27.9 OVERSOLD, -5.2% in 20D) = BEST entry now')
print('     - ICICIPRULI (Score=89.6, RSI=56.7, BUY signal) = solid rotation target')
print('     - MAHABANK (Score=100, but RSI=64 and +17.3% — wait for RSI<55)')
print()
print('  4. DO NOT ROTATE INTO:')
print('     - YESBANK (bearish pattern + zero breakout setup)')
print('     - ONGC (RSI=69, already ran 14% — wait)')
print('     - BANKBARODA (RSI=73 + ML=SELL — wait for pullback to RSI<58)')
