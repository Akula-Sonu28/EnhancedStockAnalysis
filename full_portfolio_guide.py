import pandas as pd, glob, warnings
warnings.filterwarnings('ignore')
pd.set_option('display.width', 300)
pd.set_option('display.max_columns', 60)
pd.set_option('display.float_format', '{:.2f}'.format)

xl = pd.read_excel(sorted(glob.glob('reports/Enhanced_Stock_Report_*.xlsx'))[-1], sheet_name='Portfolio Allocation')
own = xl[xl['I_OWN_IT?']==True].copy()
not_own = xl[xl['I_OWN_IT?']!=True].copy()

val_col  = [c for c in own.columns if 'VALUE' in c.upper() and 'SCORE' not in c.upper()][0]
book_col = [c for c in own.columns if 'BOOK' in c.upper() and 'AMOUNT' in c.upper()][0] if any('BOOK' in c.upper() and 'AMOUNT' in c.upper() for c in own.columns) else None

print("=" * 120)
print("FULL PORTFOLIO ALLOCATION REPORT — ALL 51 COLUMNS EXPLAINED WITH YOUR ACTUAL DATA")
print("=" * 120)

# ── SECTION 1: OWNED STOCKS ──────────────────────────────────────────────────
print("\n" + "━"*120)
print("SECTION 1 ► YOUR 21 OWNED STOCKS — WHAT TO DO")
print("━"*120)

action_order = {'SWAP': 0, 'SELL': 1, 'BOOK_PROFIT': 2, 'INCREASE': 3, 'HOLD': 4, 'KEEP': 5, 'SKIP': 6}
own['_sort'] = own['ACTION'].astype(str).apply(lambda x: action_order.get(x.split()[0], 9))
own_sorted = own.sort_values('_sort')

for _, r in own_sorted.iterrows():
    sym    = r['symbol']
    act    = r['ACTION']
    when   = r.get('WHEN_TO_ACT', '')
    shares = int(r.get('MY_SHARES', 0) or 0)
    val    = float(r.get(val_col, 0) or 0)
    pnl    = float(r.get('MY_PROFIT_%', 0) or 0)
    price  = float(r.get('PRICE', 0) or 0)
    sl     = float(r.get('STOP_LOSS', 0) or 0)
    sup    = float(r.get('SUPPORT', 0) or 0)
    res    = float(r.get('RESISTANCE', 0) or 0)
    rsi    = float(r.get('RSI', 0) or 0)
    score  = float(r.get('SCORE', 0) or 0)
    ml     = str(r.get('ML_SIGNAL', ''))
    mlconf = float(r.get('ML_CONF_%', 0) or 0)
    risk   = str(r.get('RISK', ''))
    exit_s = float(r.get('EXIT_SCORE', 0) or 0)
    rot    = str(r.get('ROTATION_TARGET', '') or '')
    rtp    = r.get('ROTATION_TRIGGER_PRICE', None)
    bkpct  = r.get('BOOK_%_IF_SELL', None)
    bkamt  = float(r.get(book_col, 0) or 0) if book_col else 0
    why    = str(r.get('WHY', '') or '')
    exhst  = r.get('EXHAUSTION?', 0)
    
    pnl_rs = val * pnl / (1 + pnl) if (1 + pnl) != 0 else 0
    
    print(f"\n{'─'*120}")
    print(f"  {sym:<12} | {act:<30} | {when}")
    print(f"{'─'*120}")
    print(f"  📦 POSITION    : {shares} shares  ×  Rs {price:.2f}  =  Rs {val:,.0f}  |  P&L: {pnl:+.1%}  (Rs {pnl_rs:+,.0f})")
    print(f"  🛡 STOP-LOSS   : Rs {sl:.2f}  (support×0.97)  |  SUPPORT: Rs {sup:.2f}  |  RESISTANCE: Rs {res:.2f}")
    print(f"  📊 SCORES      : SCORE={score:.1f}  ML={ml} ({mlconf:.0f}% conf)  RSI={rsi:.1f}  RISK={risk}  EXIT_SCORE={exit_s:.0f}")
    
    if pd.notna(bkpct) and bkpct > 0:
        book_shares = int(shares * bkpct)
        print(f"  💰 BOOK PROFIT : Sell {bkpct:.0%} = {book_shares} shares = Rs {bkamt:,.0f}  |  Keep {100-int(bkpct*100)}%")
    
    if rot and rot not in ('nan', ''):
        print(f"  🔄 ROTATE TO   : {rot}")
    
    if pd.notna(rtp) and float(rtp) > 0:
        print(f"  ⚡ ROTATE TRIGGER: Rs {float(rtp):.2f}  (if price drops here → exit immediately and rotate)")
    
    if exhst == 1 or float(exit_s or 0) > 30:
        print(f"  ⚠️  EXHAUSTION  : EXIT_SCORE={exit_s:.0f} — selling pressure building!")
    
    print(f"  📝 REASON      : {why[:120]}")

# ── SECTION 2: NEW BUY CANDIDATES ────────────────────────────────────────────
print("\n\n" + "━"*120)
print("SECTION 2 ► NEW BUY CANDIDATES (stocks not yet owned but recommended)")
print("━"*120)

invest_col = [c for c in not_own.columns if 'INVEST' in c.upper()][0] if any('INVEST' in c.upper() for c in not_own.columns) else None
buy_shares_col = 'BUY_SHARES' if 'BUY_SHARES' in not_own.columns else None
actionable_kw = ['BUY', 'NEW POSITION', 'BREAKOUT', 'PRE-BREAKOUT', 'SWAP']
candidates = not_own[not_own['ACTION'].astype(str).apply(lambda x: any(k in x.upper() for k in actionable_kw))]
candidates = candidates.sort_values('SCORE', ascending=False)

for _, r in candidates.iterrows():
    sym    = r['symbol']
    act    = r['ACTION']
    when   = r.get('WHEN_TO_ACT', '')
    price  = float(r.get('PRICE', 0) or 0)
    invest = float(r.get(invest_col, 0) or 0) if invest_col else 0
    bsh    = int(r.get(buy_shares_col, 0) or 0) if buy_shares_col else 0
    score  = float(r.get('SCORE', 0) or 0)
    ml     = str(r.get('ML_SIGNAL', ''))
    rsi    = float(r.get('RSI', 0) or 0)
    risk   = str(r.get('RISK', ''))
    sl     = float(r.get('STOP_LOSS', 0) or 0)
    why    = str(r.get('WHY', '') or '')
    
    print(f"\n  {sym:<12} | {act:<30} | {when}")
    print(f"  💵 BUY         : {bsh} shares × Rs {price:.2f} = Rs {invest:,.0f}")
    print(f"  📊 QUALITY     : SCORE={score:.1f}  ML={ml}  RSI={rsi:.1f}  RISK={risk}")
    if sl > 0:
        print(f"  🛡 STOP-LOSS   : Rs {sl:.2f}  (set this immediately after buying)")
    print(f"  📝 REASON      : {why[:120]}")

# ── SECTION 3: PORTFOLIO SUMMARY ─────────────────────────────────────────────
print("\n\n" + "━"*120)
print("SECTION 3 ► PORTFOLIO SUMMARY")
print("━"*120)

total_val  = own[val_col].sum()
prof_stocks = own[own['MY_PROFIT_%'] > 0]
loss_stocks = own[own['MY_PROFIT_%'] < 0]
total_cost = own.apply(lambda r: float(r.get(val_col,0) or 0) / (1 + float(r.get('MY_PROFIT_%',0) or 0)) if (1+float(r.get('MY_PROFIT_%',0) or 0))!=0 else 0, axis=1).sum()
unrealised = total_val - total_cost

print(f"\n  Total portfolio value  : Rs {total_val:,.0f}")
print(f"  Total invested (cost)  : Rs {total_cost:,.0f}")
print(f"  Unrealised P&L         : Rs {unrealised:+,.0f}")
print(f"  Stocks in profit       : {len(prof_stocks)} stocks")
print(f"  Stocks in loss         : {len(loss_stocks)} stocks")
print()

# Action breakdown
print("  ACTION BREAKDOWN:")
for act_grp in ['SWAP', 'SELL', 'BOOK_PROFIT', 'INCREASE', 'HOLD', 'KEEP', 'SKIP']:
    grp = own[own['ACTION'].astype(str).str.startswith(act_grp)]
    if len(grp):
        val_sum = grp[val_col].sum()
        syms = ', '.join(grp['symbol'].tolist())
        print(f"    {act_grp:<15}: {len(grp)} stocks  Rs {val_sum:,.0f}  [{syms}]")

# Capital math
print()
sell_swap = own[own['ACTION'].astype(str).str.upper().str.contains('SELL|SWAP')]
freed = sell_swap[val_col].sum()
to_invest = candidates[invest_col].sum() if invest_col and len(candidates) else 0
net = freed - to_invest
print(f"  Capital FREED from SELL/SWAP : Rs {freed:,.0f}")
print(f"  Capital NEEDED for new buys  : Rs {to_invest:,.0f}")
print(f"  NET (freed - needed)         : Rs {net:+,.0f}  ({'surplus' if net>0 else 'need to add'})")

# ── SECTION 4: COLUMN DICTIONARY ─────────────────────────────────────────────
print("\n\n" + "━"*120)
print("SECTION 4 ► COMPLETE COLUMN DICTIONARY (all 51 columns explained)")
print("━"*120)

guide = [
    ("─── DECISION COLUMNS ───", "", ""),
    ("ACTION",             "Your exact instruction",                          "SWAP/SELL/HOLD/INCREASE/NEW POSITION/BOOK_PROFIT/SKIP"),
    ("WHEN_TO_ACT",        "How urgent — when to execute",                   "Within 2 days / 1 week / 2 weeks / 3 weeks"),
    ("WHY",                "Plain-English reason for the action",            "e.g. 'Upgrade to MAHABANK (Score +31.5)'"),
    ("─── INVESTMENT COLUMNS ───", "", ""),
    ("INVEST_Rs",          "Rupees to invest (new buys only)",               "Rs 66,009 = buy this much"),
    ("BUY_SHARES",         "Number of shares to buy",                        "101 shares @ Rs 653"),
    ("─── YOUR CURRENT POSITION ───", "", ""),
    ("MY_SHARES",          "Shares you currently hold",                      "33 shares of SBIN"),
    ("MY_VALUE_Rs",        "Current market value of your holding",           "Rs 39,009"),
    ("MY_PROFIT_%",        "Your % gain or loss since purchase",             "+15.6% = profit, -3.5% = loss"),
    ("─── PROFIT BOOKING ───", "", ""),
    ("BOOK_%_IF_SELL",     "What fraction of holding to book as profit",     "0.30 = sell 30%, keep 70%"),
    ("BOOK_Rs_AMOUNT",     "Exact rupees you receive if you book",           "Rs 15,178"),
    ("─── RISK CONTROLS ───", "", ""),
    ("STOP_LOSS",          "EXIT PRICE — sell if stock falls here",          "Rs 1007 for SBIN = exit if it falls to Rs 1007"),
    ("ROTATION_TARGET",    "Stock to buy after selling this one",            "ICICIPRULI — rotate SBIN proceeds here"),
    ("ROTATION_TRIGGER_PRICE", "Trigger HOLD→ROTATE when price hits this",  "Rs 118.89 for PNB = if PNB falls to 118 → rotate"),
    ("─── QUALITY & SCORES ───", "", ""),
    ("SCORE",              "Master hybrid score 0–100 (higher = better)",   ">70 = good, >85 = excellent"),
    ("RISK_SCORE",         "Risk-adjusted score",                            "SCORE penalised for high volatility"),
    ("V3_SCORE",           "Previous scoring model (for reference only)",   "Ignore — use SCORE column"),
    ("FUND_SCORE",         "Fundamentals quality (PE, ROE, Debt)",          "0–100, >70 = strong fundamentals"),
    ("MOM_SCORE",          "Momentum/technical strength",                   "0–100, >70 = strong trend"),
    ("VALUE_SCORE",        "Valuation — how cheap vs peers",                "0–100, >70 = undervalued"),
    ("─── ML AI SIGNAL ───", "", ""),
    ("ML_SIGNAL",          "AI model prediction: BUY / HOLD / SELL",        "Must AGREE with ACTION for high confidence trades"),
    ("ML_CONF_%",          "How confident the AI is in its prediction",     ">55% = trustworthy, <45% = uncertain"),
    ("ML_ADJ",             "Points the AI added/removed from SCORE",        "+5 = AI boosted score, -5 = AI lowered it"),
    ("─── TECHNICALS ───", "", ""),
    ("RSI",                "Relative Strength Index (momentum)",            "30-40=oversold/buy zone, 40-65=healthy, >70=overbought/sell"),
    ("PRICE",              "Current market price",                           "Live price at time of analysis"),
    ("SUPPORT",            "Price floor — stock tends to bounce here",       "STOP_LOSS is set at SUPPORT x 0.97"),
    ("RESISTANCE",         "Price ceiling — stock tends to reverse here",    "BOOK PROFIT when price nears RESISTANCE"),
    ("52W_HIGH",           "Highest price in last 52 weeks",                "If near this → overbought"),
    ("52W_LOW",            "Lowest price in last 52 weeks",                 "If near this → oversold/value zone"),
    ("20D_CHANGE_%",       "Price change over last 20 trading days",        "+15% = strong recent momentum"),
    ("VOLATILITY_%",       "Annual price swing %",                          "<20% = stable, 20-35% = moderate, >35% = high risk"),
    ("─── BREAKOUT SIGNALS ───", "", ""),
    ("PRE_BREAKOUT?",      "System detected a breakout setup forming",      "1=Yes (setup active), 0=No"),
    ("BREAKOUT_%",         "Probability the breakout will succeed",         ">70% = high confidence breakout"),
    ("SETUP_SIGNALS",      "Detailed technical signals behind the setup",   "e.g. 'RSI warning, strong support'"),
    ("─── EXIT / EXHAUSTION SIGNALS ───", "", ""),
    ("EXHAUSTION?",        "Stock is running out of momentum",              "1=Yes (consider selling), 0=No"),
    ("EXIT_SCORE",         "Strength of selling pressure (0-100)",          ">15=caution, >30=exit signal, >45=urgent exit"),
    ("EXIT_SIGNALS",       "Detailed reasons behind exit signal",           "e.g. 'upper wick rejection, bearish divergence'"),
    ("─── FUNDAMENTALS ───", "", ""),
    ("PE",                 "Price-to-Earnings ratio",                       "<15 = cheap, 15-25 = fair, >30 = expensive"),
    ("ROE_%",              "Return on Equity — management quality",         ">15% = good, >20% = excellent"),
    ("DEBT/EQUITY",        "Debt vs equity (lower = safer)",                "<1 = safe, >2 = risky (banks excluded)"),
    ("─── CLASSIFICATION ───", "", ""),
    ("RISK",               "Risk level: LOW / MODERATE / HIGH / VERY HIGH", "Stick to LOW and MODERATE for moderate investor"),
    ("sector",             "Industry sector",                                "Financial Services, Pharma, etc."),
    ("TYPE",               "CORE / OPPORTUNISTIC / SPECULATIVE",            "CORE = safe hold, SPECULATIVE = trade carefully"),
    ("RANK",               "Your stock's rank within your portfolio",        "1 = best performer, 21 = worst"),
    ("PORTFOLIO_%",        "This stock as % of your total portfolio",        "0.038 = 3.8% weight"),
    ("I_OWN_IT?",          "TRUE = you own it, FALSE = potential new buy",  "Use to filter view"),
    ("─── SCORE ADJUSTMENTS (how SCORE was built) ───", "", ""),
    ("SECTOR_ADJ",         "Sector performance vs Nifty — pts added/removed","+ = sector outperforming"),
    ("SENT_ADJ",           "News sentiment impact on score",                 "±5 pts max"),
    ("VOL_ADJ",            "Volume / institutional buying impact",           "±5 pts max"),
    ("PATTERN_ADJ",        "Chart pattern signal impact",                    "±4 pts max"),
]

for row in guide:
    col, desc, example = row
    if col.startswith('─'):
        print(f"\n  {col}")
    else:
        print(f"  {col:<28} → {desc:<52} | e.g. {example}")

print("\n" + "="*120)
print("END OF REPORT")
print("="*120)
