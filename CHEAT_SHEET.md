# 📋 STOCK ANALYSIS CHEAT SHEET (SIMPLIFIED)

## 🚀 PYTHON COMMANDS ONLY

### 1. Main Analysis (❌ COMMENTED OUT - NOT NEEDED)
```
# python main.py                    # OBSOLETE - Use analyze.py instead
# python main.py --interactive      # OBSOLETE - Direct commands preferred
```

### 2. Portfolio Analysis (Sell/Buy Signals)
```
python portfolio_analysis.py                    # Full portfolio analysis
python portfolio_analysis.py --excel            # Generate Excel report
python portfolio_analysis.py --gtt              # Generate GTT orders (fast mode)
python portfolio_analysis.py --excel --gtt      # Excel report + GTT orders
python portfolio_analysis.py --fast --gtt       # Super fast GTT generation
python portfolio_analysis.py --no-trading-sheet # Skip trading sheet for speed
# COMMENTED OUT - TOO MANY EXECUTION OPTIONS
# python portfolio_analysis.py --execute-sells    # Execute sell recommendations
# python portfolio_analysis.py --execute-buys     # Execute top 5 buy recommendations
# python portfolio_analysis.py --execute-all-buys # Execute all buy recommendations
python portfolio_analysis.py --funds 114130 --excel --gtt  # Complete analysis with dynamic GTT orders
# COMMENTED OUT - OVERTHINKING PORTFOLIO SIZE
# python portfolio_analysis.py --target-min 20 --target-max 25  # Custom consolidation target (20-25 stocks)
# python portfolio_analysis.py --target-min 30 --target-max 40  # Larger portfolio target (30-40 stocks)
# python portfolio_analysis.py --funds 114130 --target-min 15 --target-max 20 --excel  # Aggressive consolidation
# python portfolio_analysis.py --funds 88780 --target-min 30 --target-max 40 --excel

```

### 3. Enhanced Stock Analysis with Risk-Based Portfolio Allocation
```
# Basic Analysis
python analyze_top200_stocks_enhanced.py        # All 200 stocks
python analyze_top200_stocks_enhanced.py -n 50  # Fast 50 stocks
python analyze_top200_stocks_enhanced.py -s RELIANCE  # Single stock

# Risk-Based Portfolio Allocation (NEW!)
python analyze_top200_stocks_enhanced.py --skip-risk --portfolio-amount 88311 --risk-profile balanced -b 10 -w 4

python analyze_top200_stocks_enhanced.py  --portfolio-amount 88311 --risk-profile balanced -b 20 -w 4


python analyze_top200_stocks_enhanced.py --portfolio-amount 88311 -n 33 --risk-profile aggressive -b 10 -w 2
python analyze_top200_stocks_enhanced.py --portfolio-amount 100000 --risk-profile moderate -n 50
python analyze_top200_stocks_enhanced.py --portfolio-amount 150000 --risk-profile balanced -n 40

# Portfolio Analysis with Current Holdings
python analyze_top200_stocks_enhanced.py --portfolio-amount 88311 -n 33 --risk-profile aggressive
python analyze_top200_stocks_enhanced.py --portfolio-amount 200000 --risk-profile moderate -n 100
python analyze_top200_stocks_enhanced.py --portfolio-amount 300000 --risk-profile balanced -n 150

# COMMENTED OUT - UNNECESSARY COMPLEXITY  
# python analyze_top200_stocks_enhanced.py -n 10 -b 5 -w 2    # TOO MANY TECHNICAL PARAMETERS
# python analyze_top200_stocks_enhanced.py -n 25 -b 10 -w 3   # USERS DON'T CARE ABOUT BATCHES
```

### 4. Report Comparison (❌ COMMENTED OUT - NOT ESSENTIAL)
```
# python compare_reports.py                        # NOT ESSENTIAL - Use Excel instead
# python compare_reports.py --console-only        # NOT ESSENTIAL
# python compare_reports.py --old report1.xlsx --new report2.xlsx  # NOT ESSENTIAL
```

### 5. Interactive Menu (❌ COMMENTED OUT - NOT NEEDED)
```
# python launcher.py               # NOT NEEDED - Direct commands preferred  
# python commands.py               # NOT NEEDED - Feature bloat
```

## 📊 KEY FILES
- **`portfolio.csv`** - Your current holdings
- **`reports/`** - All Excel output reports

## 🎯 WHAT EACH DOES
- **Main** → Basic comprehensive analysis
- **Portfolio** → Sell recommendations with prices + Buy suggestions  
- **Enhanced Stock Analysis** → Risk-based portfolio allocation with D/G/V classification
- **Comparison** → Compare different analysis reports
- **Interactive** → User-friendly guided menus

## 🎯 SIMPLIFIED APPROACH

### ✅ ONE Risk Profile (Keep it Simple)
- **Focus**: Just pick good stocks with high scores
- **Strategy**: Best stocks get higher allocation
- **Command**: `--funds AMOUNT --excel`

# COMMENTED OUT - OVERCOMPLICATED RISK PROFILES
# ### Aggressive (20-25 stocks)
# - **Focus**: 0% Defense, 50% Growth, 50% Value
# - **Strategy**: High-risk, high-reward concentrated portfolio
# - **Command**: `--risk-profile aggressive`
# 
# ### Moderate (25-30 stocks)  
# - **Focus**: 10% Defense, 40% Growth, 50% Value
# - **Strategy**: Balanced risk-return with slight value tilt
# - **Command**: `--risk-profile moderate`
# 
# ### Balanced (30-35 stocks)
# - **Focus**: 30% Defense, 30% Growth, 40% Value  
# - **Strategy**: Conservative diversified approach
# - **Command**: `--risk-profile balanced`

## 🏦 SIMPLIFIED ALLOCATION (NO COMPLEX LIMITS!)
The system now uses **EQUAL 5% MAX** allocation for all stocks:

### ✅ All Stocks: **5% max allocation**
- Simple and effective
- No complex market cap calculations
- Example: ₹100K portfolio = ₹5,000 max per stock

# COMMENTED OUT - OVERCOMPLICATED MARKET CAP LIMITS
# ### � Small Cap (< ₹5,000 crores): **3.5% max allocation**
# ### 🟡 Mid Cap (₹5,000 - ₹20,000 crores): **4% max allocation** 
# ### 🟢 Large Cap (₹20,000 - ₹50,000 crores): **5% max allocation**
# ### 🔵 Nifty 50 / Mega Cap (> ₹50,000 crores): **7% max allocation**

## 🔧 SIMPLIFIED PARAMETERS
- **`--funds`** → Available investment amount (₹) 
- **`--excel`** → Generate Excel report
- **`-n`** → Number of stocks to analyze (optional)

# COMMENTED OUT - OVERCOMPLICATED PARAMETERS
# - **`-b`** → Batch size for processing (USERS DON'T CARE)
# - **`-w`** → Number of worker threads (AUTO-OPTIMIZE)
# - **`--risk-profile`** → aggressive/moderate/balanced (TOO MANY OPTIONS)

## 📋 PORTFOLIO ACTIONS
- **KEEP** → Continue holding these stocks (with reinvestment amounts)
- **SELL** → Liquidate excess/poor performing holdings
- **BUY** → New investment opportunities

**Ready to use! 🎉**