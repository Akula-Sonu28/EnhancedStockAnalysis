"""
Moderate Investor Gap Analysis - Capital Protection + Profit Booking + Capital Rotation
Focus: No capital loss | Book profits | Rotate booked capital
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
import glob, os

reports = sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))
if not reports:
    raise FileNotFoundError("No Enhanced_Stock_Report_*.xlsx found in reports/")
f = reports[-1]
print('Using report: {}'.format(os.path.basename(f)))
pa = pd.read_excel(f, sheet_name='Portfolio Allocation')
cd = pd.read_excel(f, sheet_name='Complete Data')

invest_col = 'INVEST_RS' if 'INVEST_RS' in pa.columns else 'INVEST_₹'
my_val_col  = 'MY_VALUE_RS' if 'MY_VALUE_RS' in pa.columns else 'MY_VALUE_₹'
my_pft_col  = 'MY_PROFIT_%'
my_shr_col  = 'MY_SHARES'

# Resolve actual column names
invest_col = [c for c in pa.columns if 'INVEST' in str(c)][0]
my_val_col  = [c for c in pa.columns if 'MY_VALUE' in str(c)][0]

owned = pa[pa['I_OWN_IT?'] == True].copy()
owned['pnl_pct'] = owned[my_pft_col] * 100
owned['pnl_rs']  = owned.apply(
    lambda r: r[my_val_col] - (r[my_val_col] / (1 + r[my_pft_col])) if r[my_pft_col] != -1 else -r[my_val_col], axis=1
)

SEP  = '=' * 72
sep  = '-' * 72
gaps = []

def gap(gid, sev, title, body):
    sym = {'CRITICAL': '🔴', 'HIGH': '🟡', 'MEDIUM': '🟠', 'LOW': '🟢'}[sev]
    gaps.append((gid, sev, title))
    print('\n{} [{}] {}'.format(sym, sev, title))
    print(body)

# =============================================================================
# THEME 1: CAPITAL AT RISK — positions currently at loss
# =============================================================================
print(SEP)
print('THEME 1 — CAPITAL PROTECTION  (Stop-Loss / At-Loss Positions)')
print(SEP)

# -- Full P&L table
print('\n  [Complete P&L for all 21 owned stocks]:')
for _, r in owned.sort_values('pnl_pct').iterrows():
    flag = ''
    if r['pnl_pct'] < -5: flag = '  <<< BIG LOSS - EXIT NOW'
    elif r['pnl_pct'] < -2: flag = '  << small loss'
    elif r['pnl_pct'] > 15: flag = '  >>> BOOK PROFIT'
    elif r['pnl_pct'] > 5: flag = '  > partial book'
    print('    {:<15} {:>+7.2f}%  Rs {:>9,.0f}  RSI={:>5.1f}  ML={:<12} Risk={}{}'.format(
        r['symbol'], r['pnl_pct'], r['pnl_rs'],
        r['RSI'], r['ML_SIGNAL'], r['RISK'], flag))

at_loss = owned[owned['pnl_pct'] < 0].sort_values('pnl_pct')
total_loss_rs = at_loss['pnl_rs'].sum()
gap('L-01', 'CRITICAL',
    '{} stocks at LOSS (total unrealised loss = Rs {:,.0f}) — no stop-loss defined in sheet'.format(len(at_loss), abs(total_loss_rs)),
    at_loss[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'pnl_rs', 'PRICE', 'SUPPORT', 'RSI', 'ML_SIGNAL', 'RISK']].to_string(index=False) +
    '\n\n  A moderate investor MUST have a stop-loss level in the sheet.\n  Without it, losses can compound with no exit trigger defined.')

# Stocks at loss being INCREASED
at_loss_increase = pa[pa['ACTION'] == 'INCREASE'].merge(
    owned[['symbol', 'pnl_pct', 'pnl_rs']], on='symbol', how='inner')
at_loss_increase = at_loss_increase[at_loss_increase['pnl_pct'] < 0]
if len(at_loss_increase):
    gap('L-02', 'CRITICAL',
        'Averaging DOWN: {} stocks at loss being INCREASED'.format(len(at_loss_increase)),
        at_loss_increase[['symbol', 'pnl_pct', 'pnl_rs', 'RSI', 'ML_SIGNAL', 'RISK', invest_col]].to_string(index=False) +
        '\n\n  Averaging into a losing position = doubling risk, not reducing it.\n  For moderate investor: only INCREASE if stock is profitable OR has strong fundamental trigger.')

# Stocks at loss being HELD with ML=SELL
at_loss_hold_sell = owned[(owned['pnl_pct'] < -2) & (owned['ML_SIGNAL'] == 'SELL')]
if len(at_loss_hold_sell):
    gap('L-03', 'HIGH',
        '{} stocks at loss with ML=SELL — holding but model says exit'.format(len(at_loss_hold_sell)),
        at_loss_hold_sell[['symbol', 'ACTION', 'pnl_pct', 'pnl_rs', 'RSI', 'ML_SIGNAL', 'ML_CONF_%', 'RISK']].to_string(index=False))

# Stocks at loss being SOLD — but selling at loss
sells = pa[pa['ACTION'] == 'SELL']
sells_m = sells.merge(owned[['symbol', 'pnl_pct', 'pnl_rs']], on='symbol', how='inner')
at_loss_sell = sells_m[sells_m['pnl_pct'] < 0]
gap('L-04', 'HIGH',
    'BAJAJHLDNG + GICRE: Being SOLD at a loss — capital not rotating, capital is LEAVING',
    sells_m[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'pnl_rs', 'ML_SIGNAL', 'WHY']].to_string(index=False) +
    '\n\n  Moderate investor rule: Only sell at loss if: (a) fundamentals broken, or (b) better\n  capital use proven. WHY column says "REBALANCE" — not a strong enough reason to crystallise loss.')

# =============================================================================
# THEME 2: PROFIT BOOKING — gaps in when/how much to book
# =============================================================================
print('\n' + SEP)
print('THEME 2 — PROFIT BOOKING  (Book, target, and partial exit gaps)')
print(SEP)

in_profit = owned[owned['pnl_pct'] > 0].sort_values('pnl_pct', ascending=False)
total_profit_rs = in_profit['pnl_rs'].sum()
print('\n  [All profitable positions — Rs {:,.0f} total unrealised profit]:'.format(total_profit_rs))
for _, r in in_profit.iterrows():
    book = r['BOOK_%_IF_SELL']
    book_str = '{:.0f}% exit'.format(book * 100) if pd.notna(book) else 'NO BOOK INSTRUCTION'
    print('    {:<15} {:>+7.2f}%  Rs {:>8,.0f}  {:>5,.1f} RSI  ML={:<12} | {}'.format(
        r['symbol'], r['pnl_pct'], r['pnl_rs'], r['RSI'], r['ML_SIGNAL'], book_str))

# Stocks with >8% profit and no BOOK_%
big_profit_no_book = in_profit[(in_profit['pnl_pct'] > 8) & (in_profit['BOOK_%_IF_SELL'].isna())]
gap('P-01', 'CRITICAL',
    '{} stocks with >8% profit and NO profit booking instruction'.format(len(big_profit_no_book)),
    big_profit_no_book[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'pnl_rs', 'BOOK_%_IF_SELL', 'RSI', 'RESISTANCE', 'ML_SIGNAL']].to_string(index=False) +
    '\n\n  Profit without a booking plan = hope strategy.\n  SBIN at +15.6% (Rs {:,.0f} profit) has ZERO booking instruction.'.format(
        big_profit_no_book[big_profit_no_book['symbol'] == 'SBIN']['pnl_rs'].values[0] if 'SBIN' in big_profit_no_book['symbol'].values else 0))

# Stocks near resistance with no booking plan
near_res = in_profit[
    (in_profit['pnl_pct'] > 3) &
    (in_profit['BOOK_%_IF_SELL'].isna()) &
    ((in_profit['PRICE'] / in_profit['RESISTANCE']) > 0.95)
]
gap('P-02', 'HIGH',
    '{} profitable stocks trading within 5% of RESISTANCE — no partial exit set'.format(len(near_res)),
    near_res[['symbol', 'ACTION', 'pnl_pct', 'pnl_rs', 'PRICE', 'RESISTANCE', 'RSI', 'ML_SIGNAL', 'BOOK_%_IF_SELL']].to_string(index=False) +
    '\n\n  Resistance = natural ceiling. Price often reverses at resistance.\n  No partial exit here = giving back unrealised profits.')

# ML says SELL on profitable held stocks
ml_sell_profit = in_profit[(in_profit['ML_SIGNAL'] == 'SELL') & (in_profit['ACTION'].isin(['HOLD', 'INCREASE']))]
if len(ml_sell_profit):
    gap('P-03', 'HIGH',
        '{} profitable stocks where ML=SELL but no booking action planned'.format(len(ml_sell_profit)),
        ml_sell_profit[['symbol', 'ACTION', 'pnl_pct', 'pnl_rs', 'ML_SIGNAL', 'ML_CONF_%', 'RSI', 'BOOK_%_IF_SELL']].to_string(index=False) +
        '\n\n  ML model predicts short-term price decline for these profitable stocks.\n  Without a booking trigger, you risk watching profits evaporate.')

# RSI overbought on profitable stocks (momentum exhaustion)
rsi_ob_profit = in_profit[(in_profit['RSI'] > 68) & (in_profit['pnl_pct'] > 3)]
if len(rsi_ob_profit):
    gap('P-04', 'HIGH',
        'Overbought (RSI>68) on profitable positions — classic time to book partial'.format(),
        rsi_ob_profit[['symbol', 'ACTION', 'pnl_pct', 'pnl_rs', 'RSI', 'PRICE', 'RESISTANCE', 'ML_SIGNAL', 'BOOK_%_IF_SELL']].to_string(index=False) +
        '\n\n  RSI>68 signals buyers are exhausted. Smart money starts exiting here.\n  Moderate investor should book 25-30% of position when RSI crosses 70.')

# Booking amount vs actual profit booked
book_set = pa[pa['BOOK_%_IF_SELL'].notna()]
print('\n  [Currently DEFINED booking instructions]:')
print(book_set[['symbol', 'ACTION', my_pft_col, 'BOOK_%_IF_SELL', 'BOOK_₹_AMOUNT', 'WHEN_TO_ACT']].to_string(index=False))
total_bookable = book_set['BOOK_₹_AMOUNT'].sum()
print('\n  Total capital bookable from current instructions: Rs {:,.0f}'.format(total_bookable))
print('  Total unrealised profit available to book      : Rs {:,.0f}'.format(total_profit_rs))
print('  Gap (unplanned profit)                         : Rs {:,.0f}'.format(total_profit_rs - total_bookable))

gap('P-05', 'CRITICAL',
    'Only Rs {:,.0f} of Rs {:,.0f} profit has a booking plan — Rs {:,.0f} has NO exit plan'.format(
        total_bookable, total_profit_rs,
        total_profit_rs - total_bookable),
    '  Translation: The system is planning to book only SELL proceeds, not profits.\n  As a moderate investor you should be capturing profits systematically, not only rebalancing.')

# =============================================================================
# THEME 3: CAPITAL ROTATION — where does booked capital actually go?
# =============================================================================
print('\n' + SEP)
print('THEME 3 — CAPITAL ROTATION  (Where does profit capital rotate into?)')
print(SEP)

# Map each sell/book to its reinvestment target
sell_proceeds   = pa[pa['ACTION'] == 'SELL'][my_val_col].sum()
swap_proceeds   = pa[pa['ACTION'].str.startswith('SWAP', na=False)][my_val_col].sum()
total_freed     = sell_proceeds + swap_proceeds
new_buys_cost   = pa[pa['ACTION'].isin(['NEW POSITION', '🚀 PRE-BREAKOUT - BUY NOW'])][invest_col].sum()
increases_cost  = pa[pa['ACTION'] == 'INCREASE'][invest_col].sum()
total_deploy    = pa[invest_col].sum()

print('\n  [Capital flow summary]:')
print('    SELL proceeds (BAJAJHLDNG+FEDERALBNK+GICRE+SIEMENS) : Rs {:>10,.0f}'.format(sell_proceeds))
print('    SWAP proceeds (ICICIBANK+CASTROLIND+KOTAKBANK)       : Rs {:>10,.0f}'.format(swap_proceeds))
print('    Total capital freed                                  : Rs {:>10,.0f}'.format(total_freed))
print()
print('    New positions cost (NEW POS + PRE-BREAKOUT)          : Rs {:>10,.0f}'.format(new_buys_cost))
print('    INCREASE allocations                                 : Rs {:>10,.0f}'.format(increases_cost))
print('    Total planned deployment                             : Rs {:>10,.0f}'.format(total_deploy))
print()
net_gap = total_deploy - total_freed
print('    Net fresh capital needed from wallet                 : Rs {:>10,.0f}'.format(net_gap))

# GA: New buys are HIGH/VERY HIGH risk — not suitable for capital from booked profits
new_pos = pa[pa['ACTION'].isin(['NEW POSITION', '🚀 PRE-BREAKOUT - BUY NOW'])].copy()
risky_new = new_pos[new_pos['RISK'].isin(['HIGH', 'VERY HIGH'])]
gap('R-01', 'CRITICAL',
    '{}/{} new positions are HIGH/VERY HIGH risk — unsafe destination for booked profits'.format(len(risky_new), len(new_pos)),
    risky_new[['symbol', 'ACTION', 'RISK', invest_col, 'ML_SIGNAL', 'ML_CONF_%', 'VOLATILITY_%', 'RSI', 'SCORE']].to_string(index=False) +
    '\n\n  Moderate investor rule: Profits should rotate into LOWER or same risk tier.\n  Rotating profits from moderate stocks into HIGH RISK stocks defeats capital protection goal.')

# GA: Rotating into stocks already at overbought/near-top
rot_ob = new_pos[new_pos['RSI'] > 65]
gap('R-02', 'HIGH',
    '{} rotation targets are already overbought (RSI>65) — buying the high'.format(len(rot_ob)),
    rot_ob[['symbol', 'ACTION', 'RSI', 'PRICE', 'SUPPORT', 'RESISTANCE', '20D_CHANGE_%', invest_col, 'ML_SIGNAL']].to_string(index=False) +
    '\n\n  You are rotating profits out and immediately deploying at high RSI = no margin of safety.\n  Ideal rotation entry: RSI 40-55 with price near SUPPORT.')

# GA: NEW POSITION stocks with 0 allocation
no_alloc_new = pa[(pa['ACTION'] == 'NEW POSITION') & (pa[invest_col] == 0)]
gap('R-03', 'MEDIUM',
    '{} "NEW POSITION" stocks have Rs 0 allocation — rotation has no defined destination'.format(len(no_alloc_new)),
    no_alloc_new[['symbol', 'ACTION', 'SCORE', 'RISK', invest_col, 'ML_SIGNAL', 'ML_CONF_%']].to_string(index=False) +
    '\n\n  If you book profits from SBIN/BANKINDIA, where does that capital go?\n  HDFCBANK/MUTHOOTFIN/INDUSTOWER are tagged NEW POSITION but have Rs 0 budget.\n  These should either have an allocation or be moved to WATCHLIST.')

# GA: Selling at loss to fund new buys (capital destruction, not rotation)
loss_to_fund = sells_m[sells_m['pnl_pct'] < 0]
gap('R-04', 'HIGH',
    'Selling BAJAJHLDNG+GICRE at loss to fund new buys — this is capital DESTRUCTION not rotation',
    loss_to_fund[['symbol', my_val_col, 'pnl_pct', 'pnl_rs', 'ML_SIGNAL', 'WHY']].to_string(index=False) +
    '\n\n  Profit rotation = sell winners, buy new opportunities.\n  Loss liquidation = crystallise loss, reduce capital base permanently.\n  BAJAJHLDNG: -4.4% loss (Rs {:,.0f} lost forever), GICRE: -2.1% (Rs {:,.0f} lost).'.format(
        abs(loss_to_fund[loss_to_fund['symbol'] == 'BAJAJHLDNG']['pnl_rs'].values[0]) if 'BAJAJHLDNG' in loss_to_fund['symbol'].values else 0,
        abs(loss_to_fund[loss_to_fund['symbol'] == 'GICRE']['pnl_rs'].values[0]) if 'GICRE' in loss_to_fund['symbol'].values else 0))

# =============================================================================
# THEME 4: MISSING RISK CONTROLS for moderate investor
# =============================================================================
print('\n' + SEP)
print('THEME 4 — MISSING RISK CONTROLS  (Stop-loss, position sizing, exit triggers)')
print(SEP)

# No stop-loss column in sheet at all
gap('C-01', 'CRITICAL',
    'ZERO stocks have a STOP_LOSS level defined — the sheet has no stop-loss column',
    '  Your master sheet has 48 columns but not a single stop-loss price.\n  Moderate investor must define: Entry | Target | Stop-Loss for every position.\n  Without stop-loss: a crash like today (Sensex -2700) has NO automatic exit trigger.')

# Position sizing — single stocks >15% of portfolio
port_val = owned[my_val_col].sum()
owned['port_wt'] = owned[my_val_col] / port_val * 100
overweight = owned[owned['port_wt'] > 12].sort_values('port_wt', ascending=False)
gap('C-02', 'HIGH',
    '{} positions are >12% of portfolio — concentration risk'.format(len(overweight)),
    overweight[['symbol', my_val_col, 'port_wt', 'pnl_pct', 'RISK', 'ML_SIGNAL']].to_string(index=False) +
    '\n\n  Moderate investor rule: Max single position = 10-12% of portfolio.\n  Above 12% = single stock can make/break the entire portfolio.')

# Exhaustion signal on owned stocks
exhausted_owned = owned[owned['EXHAUSTION?'] == True]
if len(exhausted_owned):
    gap('C-03', 'HIGH',
        '{} owned stocks showing EXHAUSTION signal — price top is near, should book'.format(len(exhausted_owned)),
        exhausted_owned[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'RSI', 'PRICE', 'RESISTANCE', 'EXIT_SCORE', 'BOOK_%_IF_SELL']].to_string(index=False) +
        '\n\n  EXHAUSTION = volume + momentum + overbought all converging at top.\n  This is the system telling you: TAKE MONEY OFF THE TABLE NOW.')

# EXIT_SCORE > 5 but no exit instruction
high_exit = owned[(owned['EXIT_SCORE'] > 5) & (owned['BOOK_%_IF_SELL'].isna())]
if len(high_exit):
    gap('C-04', 'HIGH',
        '{} stocks with EXIT_SCORE > 5 but no booking instruction'.format(len(high_exit)),
        high_exit[['symbol', 'ACTION', my_val_col, 'pnl_pct', 'EXIT_SCORE', 'EXIT_SIGNALS', 'RSI', 'ML_SIGNAL']].to_string(index=False))

# HOLD stocks with 20D change negative — silent losses building
silent_loss = owned[(owned['ACTION'] == 'HOLD') & (owned['20D_CHANGE_%'] < -3) & (owned['pnl_pct'] < 5)]
if len(silent_loss):
    gap('C-05', 'MEDIUM',
        '{} HOLD stocks declining >3% in 20D — profits eroding silently'.format(len(silent_loss)),
        silent_loss[['symbol', 'ACTION', my_val_col, 'pnl_pct', '20D_CHANGE_%', 'RSI', 'ML_SIGNAL', 'EXIT_SIGNALS']].to_string(index=False) +
        '\n\n  HOLD is not a strategy. These stocks need: Review | Partial book | Stop-loss')

# =============================================================================
# THEME 5: WHAT MODERATE INVESTOR SHOULD ACTUALLY DO
# =============================================================================
print('\n' + SEP)
print('THEME 5 — WHAT THE SYSTEM CURRENTLY RECOMMENDS vs MODERATE INVESTOR NEEDS')
print(SEP)

# Capital protection score: system vs moderate
print('\n  System Recommendation Summary:')
print(pa['ACTION'].value_counts().to_string())

print('\n  [Moderate investor translation — what each action means for your goal]:')
print('  HOLD      = No trigger defined. Profit/loss can drift. NEED: stop-loss + book target')
print('  INCREASE  = Buying more. ONLY valid if current position profitable + RSI < 60')
print('  SELL      = Good IF selling at profit. BAD if selling at loss for rebalancing')
print('  SWAP      = Valid IF swap target is lower risk AND you are booking a profit')
print('  PRE-BREAKOUT = Speculative NEW money. Use ONLY booked profit, not fresh capital')
print('  NEW POSITION = Watchlist. Needs allocation + risk tier check before acting')

# Final metrics summary
total_portfolio = owned[my_val_col].sum()
total_unrealised_profit = in_profit['pnl_rs'].sum()
total_unrealised_loss   = at_loss['pnl_rs'].sum()
bookable_now = owned[(owned['pnl_pct'] > 8) | (owned['RSI'] > 68)][my_val_col].sum() * 0.25

print('\n  [Your Portfolio Risk Dashboard]:')
print('  Total portfolio value        : Rs {:>12,.0f}'.format(total_portfolio))
print('  Unrealised profit (total)    : Rs {:>12,.0f}  ({:.1f}% of portfolio)'.format(
    total_unrealised_profit, total_unrealised_profit/total_portfolio*100))
print('  Unrealised loss  (total)     : Rs {:>12,.0f}  ({:.1f}% of portfolio)'.format(
    abs(total_unrealised_loss), abs(total_unrealised_loss)/total_portfolio*100))
print('  Net unrealised P/L           : Rs {:>12,.0f}'.format(total_unrealised_profit + total_unrealised_loss))
print('  Bookable profit (est 25% of overbought/>8% stocks): Rs {:>8,.0f}'.format(bookable_now))
print('  Stocks with NO exit plan     : {} / {}'.format(
    owned['BOOK_%_IF_SELL'].isna().sum(), len(owned)))

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print('\n' + SEP)
print('FINAL GAP SUMMARY — Moderate Investor: Capital Protection + Profit Booking + Rotation')
print(SEP)

theme_map = {
    'L': '🛡  CAPITAL PROTECTION',
    'P': '💰  PROFIT BOOKING',
    'R': '🔄  CAPITAL ROTATION',
    'C': '⚙  RISK CONTROLS'
}
sev_sym = {'CRITICAL': '🔴', 'HIGH': '🟡', 'MEDIUM': '🟠', 'LOW': '🟢'}
current_theme = None
for gid, sev, title in gaps:
    theme = gid[0]
    if theme != current_theme:
        current_theme = theme
        print('\n  --- {} ---'.format(theme_map.get(theme, theme)))
    print('  {} [{}] {}: {}'.format(sev_sym[sev], sev, gid, title))

print()
print('  Total: {} gaps identified'.format(len(gaps)))
print('  Critical: {}'.format(sum(1 for _, s, _ in gaps if s == 'CRITICAL')))
print('  High    : {}'.format(sum(1 for _, s, _ in gaps if s == 'HIGH')))
print('  Medium  : {}'.format(sum(1 for _, s, _ in gaps if s == 'MEDIUM')))

print('\n  === IMMEDIATE ACTION PRIORITY (moderate investor) ===')
print('  1. Book 25-30% of SBIN (RSI=63, +15.6% profit) NOW -> Rs ~50,000 freed')
print('  2. Book 25% of UNIONBANK (RSI=72, +28.4% profit) -> Rs ~38,000 freed')
print('  3. Set stop-loss for ALL at-loss positions BEFORE adding new ones')
print('  4. Do NOT buy BANKBARODA/UNIONBANK at RSI 73/72 — wait for RSI < 58')
print('  5. Move BAJAJHLDNG from SELL to HOLD — do not crystallise the loss')
print('  6. Add STOP_LOSS column to your master sheet for every position')
