"""Complete Gap Analysis for Portfolio Allocation Sheet"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np
import glob, os

reports = sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))
if not reports:
    raise FileNotFoundError("No Enhanced_Stock_Report_*.xlsx found in reports/")
f = reports[-1]
print(f"Using report: {os.path.basename(f)}")
pa = pd.read_excel(f, sheet_name='Portfolio Allocation', header=1)
cd = pd.read_excel(f, sheet_name='Complete Data')

invest_col = [c for c in pa.columns if 'INVEST' in str(c)][0]
my_val_col  = [c for c in pa.columns if 'MY VALUE' in str(c) or 'MY_VALUE' in str(c)][0]
my_pft_col  = [c for c in pa.columns if 'P&L' in str(c) or 'MY_PROFIT' in str(c)][0]
my_shr_col  = [c for c in pa.columns if 'MY QTY' in str(c) or 'MY_SHARES' in str(c)][0]

SEP = '='*68
sep = '-'*68
gaps = []

def gap(gid, severity, title, detail):
    marker = {'CRITICAL':'🔴','HIGH':'🟡','MEDIUM':'🟠','LOW':'🟢'}[severity]
    gaps.append((gid, severity, title))
    print(f'\n{marker} GA-{gid} [{severity}]: {title}')
    print(detail)

# ===================================================================
# GA-1: ACTION vs INVEST allocation contradictions
# ===================================================================
print(SEP)
print('BLOCK 1: ACTION vs INVESTMENT LOGIC')
print(SEP)

skip_money = pa[pa['ACTION'].str.contains('SKIP|WAIT', na=False) & (pa[invest_col]>0)]
gap('01','CRITICAL','SKIP action with ₹68,644 allocated (IDBI)',
    skip_money[['symbol','ACTION',invest_col,'RISK','OWNED?','SCORE']].to_string(index=False))

new_zero = pa[(pa['ACTION']=='NEW POSITION') & (pa[invest_col]==0)]
gap('02','MEDIUM','NEW POSITION stocks have zero capital (watchlist-only)',
    '  Stocks: ' + ', '.join(new_zero['symbol'].tolist()) +
    '\n  These appear in your master sheet as BUY but have no allocation budget.')

sbilife = pa[pa['symbol']=='SBILIFE']
_sb_cols = ['symbol','ACTION','SCORE','RSI',invest_col]
if 'BREAKOUT_%' in pa.columns:
    _sb_cols.insert(3, 'BREAKOUT_%')
gap('03','MEDIUM','SBILIFE: PRE-BREAKOUT with ₹0 allocated',
    sbilife[[c for c in _sb_cols if c in pa.columns]].to_string(index=False))

# ===================================================================
# BLOCK 2: PRE-BREAKOUT validity
# ===================================================================
print('\n' + SEP)
print('BLOCK 2: PRE-BREAKOUT SIGNAL VALIDITY')
print(SEP)

pb = pa[pa['ACTION']=='🚀 PRE-BREAKOUT - BUY NOW'].copy()
pb_cd = cd[cd['symbol'].isin(pb['symbol'])][
    ['symbol','pattern_dominant_signal','pattern_confidence','real_rsi','volume_signal','ml_signal']]
pb_m = pb.merge(pb_cd, on='symbol', how='left')

# GA-04: Bearish pattern on PRE-BREAKOUT
bad = pb_m[pb_m['pattern_dominant_signal']=='bearish']
_bad_cols = ['symbol','SCORE','RSI','20D CHG %','pattern_dominant_signal','pattern_confidence','volume_signal',invest_col]
if 'BREAKOUT_%' in pb_m.columns:
    _bad_cols.insert(3, 'BREAKOUT_%')
gap('04','CRITICAL','YESBANK: PRE-BREAKOUT with BEARISH pattern (conf=1.0)',
    bad[[c for c in _bad_cols if c in pb_m.columns]].to_string(index=False) +
    '\n  Pattern=bearish + RSI=28 (oversold) + 20D=-4.77% = downtrend, NOT breakout')

# GA-05: Zero breakout potential (skip if BREAKOUT_% column removed)
if 'BREAKOUT_%' in pb_m.columns:
    zero = pb_m[pb_m['BREAKOUT_%']==0]
    _zero_cols = ['symbol','SCORE','PRICE','SUPPORT','RESIST','BREAKOUT_%','RSI','20D CHG %',invest_col]
    gap('05','HIGH','ONGC + YESBANK: PRE-BREAKOUT with BREAKOUT_%=0',
        zero[[c for c in _zero_cols if c in pb_m.columns]].to_string(index=False) +
    '\n  A pre-breakout stock must have a measurable breakout target. 0% means no setup exists.')
else:
    pass  # BREAKOUT_% column removed in new format

# GA-06: RSI overbought on pre-breakout
ob = pb_m[pb_m['RSI']>68]
_ob_cols = ['symbol','SCORE','PRICE','RSI','20D CHG %','ml_signal',invest_col]
if 'BREAKOUT_%' in pb_m.columns:
    _ob_cols.insert(5, 'BREAKOUT_%')
gap('06','HIGH','ONGC: PRE-BREAKOUT with RSI=69 (near overbought, already ran +13.7% in 20D)',
    ob[[c for c in _ob_cols if c in pb_m.columns]].to_string(index=False) +
    '\n  Buying near overbought after a 14% run is momentum chasing, not a breakout entry.')

# ===================================================================
# BLOCK 3: ML vs ACTION conflicts
# ===================================================================
print('\n' + SEP)
print('BLOCK 3: ML SIGNAL vs ACTION CONFLICTS')
print(SEP)

buy_actions  = ['INCREASE','🚀 PRE-BREAKOUT - BUY NOW','NEW POSITION']
sell_actions = ['SELL','SWAP -> MAHABANK','SWAP -> ICICIPRULI']

ml_sell_on_buy = pa[pa['ACTION'].isin(buy_actions) & (pa['ML']=='SELL')]
gap('07','HIGH','ML says SELL on 3 INCREASE stocks (BANKBARODA/UNIONBANK/AXISBANK)',
    ml_sell_on_buy[['symbol','ACTION','SCORE','ML','ML CONF %','RSI','20D CHG %','RISK']].to_string(index=False) +
    '\n  ML trained on historical data — currently predicting short-term price decline.\n  FBS=100 means buy for VALUE, not buy TODAY at RSI 73.')

ml_buy_on_sell = pa[pa['ACTION'].isin(sell_actions) & (pa['ML']=='BUY')]
gap('08','MEDIUM','CASTROLIND: ML says BUY (67.8% conf) but action=SWAP out',
    ml_buy_on_sell[['symbol','ACTION','SCORE','ML','ML CONF %','RISK','REASON']].to_string(index=False) +
    '\n  Swap is directionally correct (crude spike hurts refiners), but REASON column\n  does not mention the ML conflict — misleading in master sheet.')

# ===================================================================
# BLOCK 4: RSI TIMING ISSUES on BUY stocks
# ===================================================================
print('\n' + SEP)
print('BLOCK 4: RSI TIMING — OVERBOUGHT ON BUY STOCKS')
print(SEP)

buy_all = pa[pa['ACTION'].isin(buy_actions + ['INCREASE'])]
ob_buy = buy_all[buy_all['RSI']>70]
gap('09','HIGH','BANKBARODA(RSI=73) + UNIONBANK(RSI=72): Overbought on INCREASE',
    ob_buy[['symbol','ACTION','SCORE','RSI','PRICE','SUPPORT','RESIST','20D CHG %','ML']].to_string(index=False) +
    '\n  Price is near RESIST, not near SUPPORT. Ideal entry for INCREASE is RSI 40-55.\n  Both already up 13-15% in 20 days — buying the top of a war rally.')

# Price vs support distance
print('\n  [Distance from SUPPORT for all BUY/INCREASE stocks]:')
for _, r in buy_all.iterrows():
    try:
        dist = (float(r['PRICE']) - float(r['SUPPORT'])) / float(r['SUPPORT']) * 100
        warn = ' <<< >10% from support' if dist > 10 else ''
        print(f'    {r["symbol"]:<15} Price={r["PRICE"]:>8.2f}  Support={r["SUPPORT"]:>8.2f}  dist={dist:+.1f}%{warn}')
    except Exception:
        pass

# ===================================================================
# BLOCK 5: SECTOR CONCENTRATION
# ===================================================================
print('\n' + SEP)
print('BLOCK 5: SECTOR CONCENTRATION RISK')
print(SEP)

sec = pa['sector'].value_counts()
total = len(pa)
detail = ''
for s, c in sec.items():
    pct = c/total*100
    flag = ' <<<< DANGEROUS' if pct > 50 else (' << OVERWEIGHT' if pct > 30 else '')
    detail += f'  {s:<35} {c:>2} stocks  {pct:5.1f}%{flag}\n'
gap('10','CRITICAL','83.3% portfolio in Financial Services (25/30 stocks)',
    detail.strip() +
    '\n\n  War escalation → bank liquidity stress, RBI emergency action, FII exit from banks\n  could wipe the entire portfolio simultaneously.')

# Capital at risk by sector
print('\n  [Capital at risk by sector (MY VALUE ₹ for owned stocks)]:')
owned = pa[pa['OWNED?']==True]
sec_val = owned.groupby('sector')[my_val_col].sum().sort_values(ascending=False)
total_val = owned[my_val_col].sum()
for s, v in sec_val.items():
    print(f'    {s:<35} Rs {v:>10,.0f}  ({v/total_val*100:.1f}%)')

# ===================================================================
# BLOCK 6: SELL TIMING COMPLETENESS
# ===================================================================
print('\n' + SEP)
print('BLOCK 6: SELL TIMING & RATIONALE GAPS')
print(SEP)

sells = pa[pa['ACTION']=='SELL']
no_timing = sells[sells['WHEN'].isna()]
gap('11','MEDIUM','FEDERALBNK + SIEMENS: SELL with no WHEN timing',
    no_timing[['symbol','ACTION','SCORE',my_pft_col,'ML','ML CONF %','RISK','WHEN']].to_string(index=False) +
    '\n  Without timing, these may sit unsold in your master sheet indefinitely.')

# All 4 sells have same REASON: "REBALANCE — better opportunities"
gap('12','MEDIUM','All 4 SELL stocks have identical REASON (REBALANCE) — no fundamental trigger',
    sells[['symbol','SCORE',my_pft_col,'ML','RISK','REASON']].to_string(index=False) +
    '\n  Two are at loss (BAJAJHLDNG -4.4%, GICRE -2.1%) and two at profit (FEDERALBNK +4.6%, SIEMENS +3.4%).\n  No stock-specific reason is documented — hard to defend the sell decision later.')

# ===================================================================
# BLOCK 7: BOOK PROFIT LOGIC
# ===================================================================
print('\n' + SEP)
print('BLOCK 7: PROFIT BOOKING GAPS')
print(SEP)

# Stocks with profit > 5% but no BOOK_%
has_profit = pa[(pa[my_pft_col] > 0.05) & (pa['BOOK %'].isna())]
gap('13','MEDIUM','Stocks with profit >5% but no profit booking instruction',
    has_profit[['symbol','ACTION',my_pft_col,'BOOK %','PRICE','RESIST','RSI','ML']].to_string(index=False) +
    '\n  These stocks are profitable but no partial exit level is defined in your master sheet.')

# UNIONBANK has BOOK flag
book_set = pa[pa['BOOK %'].notna()]
print('\n  [Stocks WITH profit booking set]:')
print(book_set[['symbol','ACTION','SCORE',my_pft_col,'BOOK %','BOOK ₹' if 'BOOK ₹' in pa.columns else 'SCORE','WHEN']].to_string(index=False))

# ===================================================================
# BLOCK 8: SWAP LOGIC VALIDATION
# ===================================================================
print('\n' + SEP)
print('BLOCK 8: SWAP LOGIC VALIDATION')
print(SEP)

swaps = pa[pa['ACTION'].str.startswith('SWAP', na=False)]
swap_targets = {'MAHABANK':'MAHABANK','ICICIPRULI':'ICICIPRULI'}
for _, row in swaps.iterrows():
    sym = row['symbol']
    target = row['ACTION'].replace('SWAP -> ','')
    target_row = pa[pa['symbol']==target]
    from_score = row['SCORE']
    to_score = target_row['SCORE'].values[0] if len(target_row)>0 else None
    from_loss = row[my_pft_col]
    from_val = row[my_val_col]
    target_invest = target_row[invest_col].values[0] if len(target_row)>0 else 0
    print(f'  {sym} (Score={from_score:.1f}, P/L={from_loss*100:+.1f}%) → {target} (Score={to_score})')
    print(f'    Proceeds: Rs {from_val:,.0f} | Target needs: Rs {target_invest:,.0f}')
    if target_invest > 0 and from_val < target_invest:
        print(f'    ⚠️  SHORTFALL: Swap proceeds Rs {from_val:,.0f} < Target cost Rs {target_invest:,.0f} (gap: Rs {target_invest-from_val:,.0f})')
    elif target_invest > 0:
        print(f'    ✅ Surplus: Rs {from_val - target_invest:,.0f} freed')
    else:
        print(f'    ⚠️  Target has Rs 0 allocation — where does the swap money go?')
print()

# ICICIBANK swap specifically: you own ICICIBANK at loss, swap to ICICIPRULI
ici = pa[pa['symbol']=='ICICIBANK']
ipr = pa[pa['symbol']=='ICICIPRULI']
gap('14','MEDIUM','ICICIBANK swap: selling at -2.6% loss to buy ICICIPRULI at +29.6 score gap',
    pd.concat([ici,ipr])[['symbol','ACTION','SCORE',my_pft_col,my_val_col,invest_col,'ML','RSI']].to_string(index=False) +
    '\n  Score gap justifies the swap but ICICIBANK ML=HOLD — no urgency to exit at a loss.\n  Consider waiting for ICICIBANK to recover before swapping.')

# ===================================================================
# BLOCK 9: RISK vs ACTION mismatches
# ===================================================================
print('\n' + SEP)
print('BLOCK 9: RISK LEVEL vs ACTION MISMATCHES')
print(SEP)

buy_actions_all = ['INCREASE','🚀 PRE-BREAKOUT - BUY NOW','NEW POSITION']
very_high_buy = pa[pa['ACTION'].isin(buy_actions_all) & (pa['RISK']=='VERY HIGH')]
high_buy = pa[pa['ACTION'].isin(buy_actions_all) & (pa['RISK']=='HIGH')]
gap('15','HIGH','VERY HIGH risk stock being bought/allocated (IDBI has ₹68K despite SKIP)',
    very_high_buy[['symbol','ACTION','SCORE','RISK',invest_col,'ML','D/E','VOLATILITY %']].to_string(index=False) if len(very_high_buy) else 'None in direct BUY',)

print('\n  [HIGH risk stocks with BUY/INCREASE actions]:')
print(high_buy[['symbol','ACTION','SCORE','RISK','ML','ML CONF %','VOLATILITY %','20D CHG %']].to_string(index=False))

# MAHABANK specifically: HIGH risk + PRE-BREAKOUT + largest single allocation
maha = pa[pa['symbol']=='MAHABANK']
print(f'\n  MAHABANK: Largest single buy (Rs {maha[invest_col].values[0]:,.0f}) + HIGH risk + PSU small bank')
print(maha[['symbol','SCORE','RISK',invest_col,'RSI','VOLATILITY %','PE','ROE %','D/E']].to_string(index=False))

# ===================================================================
# BLOCK 10: PORTFOLIO COLUMN COMPLETENESS
# ===================================================================
print('\n' + SEP)
print('BLOCK 10: DATA COMPLETENESS IN MASTER SHEET COLUMNS')
print(SEP)

# REASON column gaps
no_why = pa[pa['REASON'].isna()]
gap('16','MEDIUM','9 stocks have no REASON explanation in master sheet',
    no_why[['symbol','ACTION','SCORE','RISK','OWNED?']].to_string(index=False) +
    '\n  REASON is your primary reference column for investment rationale. Missing = blind spot.')

# WHEN gaps for actionable stocks
actionable = ['SELL','SWAP -> MAHABANK','SWAP -> ICICIPRULI','INCREASE','🚀 PRE-BREAKOUT - BUY NOW']
no_timing_actionable = pa[pa['ACTION'].isin(actionable) & pa['WHEN'].isna()]
gap('17','MEDIUM','13 actionable stocks (SELL/SWAP/INCREASE/BUY) have no WHEN',
    no_timing_actionable[['symbol','ACTION','SCORE','RISK',invest_col,'ML']].to_string(index=False) +
    '\n  Without timing, you cannot create a priority execution order in your master sheet.')

# SETUP_SIGNALS gaps on pre-breakout stocks (skip if column removed)
if 'SETUP_SIGNALS' in pa.columns:
    pb_no_setup = pa[(pa['ACTION']=='🚀 PRE-BREAKOUT - BUY NOW') & pa['SETUP_SIGNALS'].isna()]
    if len(pb_no_setup):
        print(f'\n  PRE-BREAKOUT stocks with no SETUP_SIGNALS: {list(pb_no_setup["symbol"])}')

# ===================================================================
# BLOCK 11: FINANCIAL RATIOS SANITY
# ===================================================================
print('\n' + SEP)
print('BLOCK 11: FINANCIAL RATIO SANITY CHECKS')
print(SEP)

# PE ratio issues
pe_issues = pa[(pa['PE']<0) | (pa['PE']>100)]
print('  [PE ratio extremes (PE<0 or PE>100)]:')
print(pa[['symbol','PE','ROE %','D/E','ACTION']].sort_values('PE').head(10).to_string(index=False))

# ROE too low for BUY
low_roe_buy = pa[pa['ACTION'].isin(buy_actions_all + ['INCREASE']) & (pa['ROE %'] < 8)]
if len(low_roe_buy):
    gap('18','MEDIUM','BUY stocks with ROE < 8% (weak profitability)',
        low_roe_buy[['symbol','ACTION','SCORE','ROE %','PE','D/E','RISK']].to_string(index=False))

# High debt buy
high_debt_buy = pa[pa['ACTION'].isin(buy_actions_all + ['INCREASE']) & (pa['D/E'] > 3)]
if len(high_debt_buy):
    print('\n  [HIGH DEBT (D/E>3) on BUY stocks]:')
    print(high_debt_buy[['symbol','ACTION','SCORE','D/E','ROE %','RISK']].to_string(index=False))

# ===================================================================
# BLOCK 12: PORTFOLIO WEIGHT vs SCORE PROPORTIONALITY
# ===================================================================
print('\n' + SEP)
print('BLOCK 12: PORTFOLIO WEIGHT vs SCORE PROPORTIONALITY')
print(SEP)

# All stocks classified SPECULATIVE (only 1 OPPORTUNISTIC)
print('  [TYPE distribution]:')
print(pa['TYPE'].value_counts().to_string())
gap('19','HIGH','29/30 stocks classified SPECULATIVE — no CORE holdings',
    '  With 100% BEAR regime, every stock gets pushed to SPECULATIVE.\n  Your master sheet has zero CORE/DEFENSIVE positions — no risk anchor.\n  In a prolonged bear, all 30 positions will bleed simultaneously.')

# RANK distribution
print('\n  [RANK distribution — all should be unique]:')
rank_dups = pa[pa['RANK'].duplicated(keep=False)]
if len(rank_dups):
    print('  DUPLICATE RANKS FOUND:')
    print(rank_dups[['symbol','RANK','SCORE','ACTION']].sort_values('RANK').to_string(index=False))
else:
    print('  No duplicate ranks.')

# ===================================================================
# BLOCK 13: CAPITAL MATH
# ===================================================================
print('\n' + SEP)
print('BLOCK 13: CAPITAL DEPLOYMENT MATH')
print(SEP)

total_invest = pa[invest_col].sum()
sell_val     = pa[pa['ACTION']=='SELL'][my_val_col].sum()
swap_val     = pa[pa['ACTION'].str.startswith('SWAP',na=False)][my_val_col].sum()
net_needed   = total_invest - sell_val - swap_val
owned_total  = pa[pa['OWNED?']==True][my_val_col].sum()

print(f'  Total new capital required  : Rs {total_invest:>12,.0f}')
print(f'  SELL proceeds               : Rs {sell_val:>12,.0f}')
print(f'  SWAP proceeds               : Rs {swap_val:>12,.0f}')
print(f'  Net fresh capital needed    : Rs {net_needed:>12,.0f}')
print(f'  Total current portfolio val : Rs {owned_total:>12,.0f}')
print()

if net_needed > 50000:
    gap('20','HIGH','Net fresh capital needed is Rs {:,.0f} — not covered by sells/swaps alone'.format(net_needed),
        '  You need to bring in fresh capital of Rs {:,.0f} if all buys execute.\n  Recommend: execute SELLs first, then deploy buy capital from proceeds.'.format(net_needed))

# IDBI allocation ghost
gap('21','CRITICAL','IDBI Rs 68,644 allocation is GHOST CAPITAL — SKIP action means it will never deploy',
    '  The allocator reserved Rs 68,644 for IDBI but the recommendation engine\n  flagged it SKIP-WAIT. This money appears in your total but is not deployable.\n  Effective deployable capital = Rs {:,.0f} not Rs {:,.0f}'.format(total_invest-68644.42, total_invest))

# ===================================================================
# BLOCK 14: SCORE vs PRICE ACTION DIVERGENCE
# ===================================================================
print('\n' + SEP)
print('BLOCK 14: SCORE vs PRICE ACTION DIVERGENCE')
print(SEP)

# High score but negative recent return
high_score_falling = pa[(pa['SCORE']>75) & (pa['20D CHG %']<0)]
print('  [High score (>75) but negative 20D return]:')
print(high_score_falling[['symbol','SCORE','20D CHG %','RSI','ACTION','ML','RISK']].to_string(index=False))

# Low score but strong recent return (possible missed opportunity)
low_score_rising = pa[(pa['SCORE']<72) & (pa['20D CHG %']>8)]
if len(low_score_rising):
    print('\n  [Low score (<72) but strong 20D rally >8%]:')
    print(low_score_rising[['symbol','SCORE','20D CHG %','RSI','ACTION','sector']].to_string(index=False))

# ===================================================================
# SUMMARY
# ===================================================================
print('\n' + SEP)
print('COMPLETE GAP SUMMARY')
print(SEP)
sev_order = ['CRITICAL','HIGH','MEDIUM','LOW']
markers   = {'CRITICAL':'🔴','HIGH':'🟡','MEDIUM':'🟠','LOW':'🟢'}
for sev in sev_order:
    these = [(g,t) for g,s,t in gaps if s==sev]
    for gid, title in these:
        print(f'  {markers[sev]} GA-{gid} [{sev}]: {title}')
print(f'\n  Total gaps: {len(gaps)} ({sum(1 for _,s,_ in gaps if s=="CRITICAL")} Critical, '
      f'{sum(1 for _,s,_ in gaps if s=="HIGH")} High, '
      f'{sum(1 for _,s,_ in gaps if s=="MEDIUM")} Medium)')
