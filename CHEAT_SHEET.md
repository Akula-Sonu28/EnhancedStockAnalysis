# 📋 STOCK ANALYSIS CHEAT SHEET

## 🚀 PYTHON COMMANDS ONLY

### 1. Main Analysis
```
python main.py                    # Basic analysis
python main.py --interactive      # Interactive mode
```

### 2. Portfolio Analysis (Sell/Buy Signals)
```
python portfolio_analysis.py                    # Full portfolio analysis
python portfolio_analysis.py --excel            # Generate Excel report
python portfolio_analysis.py --gtt              # Generate GTT orders (fast mode)
python portfolio_analysis.py --excel --gtt      # Excel report + GTT orders
python portfolio_analysis.py --fast --gtt       # Super fast GTT generation
python portfolio_analysis.py --no-trading-sheet # Skip trading sheet for speed
python portfolio_analysis.py --execute-sells    # Execute sell recommendations
python portfolio_analysis.py --execute-buys     # Execute top 5 buy recommendations
python portfolio_analysis.py --execute-all-buys # Execute all buy recommendations
python portfolio_analysis.py --funds 114130 --excel --gtt  # Complete analysis with dynamic GTT orders
python portfolio_analysis.py --target-min 20 --target-max 25  # Custom consolidation target (20-25 stocks)
python portfolio_analysis.py --target-min 30 --target-max 40  # Larger portfolio target (30-40 stocks)
python portfolio_analysis.py --funds 114130 --target-min 15 --target-max 20 --excel  # Aggressive consolidation
python portfolio_analysis.py --funds 88780 --target-min 30 --target-max 40 --excel

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

# Fast Batch Processing
python analyze_top200_stocks_enhanced.py -n 10 -b 5 -w 2    # 10 stocks, batch=5, workers=2
python analyze_top200_stocks_enhanced.py -n 25 -b 10 -w 3   # 25 stocks, batch=10, workers=3
```

### 4. Report Comparison
```
python compare_reports.py                        # Compare latest two reports
python compare_reports.py --console-only        # Console output only
python compare_reports.py --old report1.xlsx --new report2.xlsx  # Specific files
```

### 5. Interactive Menu
```
python launcher.py               # Guided menu system
python commands.py               # Command hub
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

## 🎯 RISK PROFILES & PORTFOLIO SIZES

### Aggressive (20-25 stocks)
- **Focus**: 0% Defense, 50% Growth, 50% Value
- **Strategy**: High-risk, high-reward concentrated portfolio
- **Command**: `--risk-profile aggressive`

### Moderate (25-30 stocks)  
- **Focus**: 10% Defense, 40% Growth, 50% Value
- **Strategy**: Balanced risk-return with slight value tilt
- **Command**: `--risk-profile moderate`

### Balanced (30-35 stocks)
- **Focus**: 30% Defense, 30% Growth, 40% Value  
- **Strategy**: Conservative diversified approach
- **Command**: `--risk-profile balanced`

## 🏦 MARKET CAP-BASED ALLOCATION LIMITS (NEW!)
The system now uses intelligent allocation limits based on market capitalization:

### 🔵 Small Cap (< ₹5,000 crores): **3.5% max allocation**
- Higher risk, higher reward potential
- Limited to 3.5% of total portfolio per stock
- Example: ₹100K portfolio = ₹3,500 max per small cap stock

### 🟡 Mid Cap (₹5,000 - ₹20,000 crores): **4% max allocation** 
- Balanced risk-reward profile
- Limited to 4% of total portfolio per stock
- Example: ₹100K portfolio = ₹4,000 max per mid cap stock

### 🟢 Large Cap (₹20,000 - ₹50,000 crores): **5% max allocation**
- Stable, established companies
- Limited to 5% of total portfolio per stock  
- Example: ₹100K portfolio = ₹5,000 max per large cap stock

### 🔵 Nifty 50 / Mega Cap (> ₹50,000 crores): **7% max allocation**
- Highest quality, most liquid stocks
- Limited to 7% of total portfolio per stock
- Example: ₹100K portfolio = ₹7,000 max per Nifty 50 stock

## 🔧 COMMON PARAMETERS
- **`--portfolio-amount`** → Available investment amount (₹)
- **`-n`** → Number of stocks to analyze 
- **`-b`** → Batch size for processing
- **`-w`** → Number of worker threads
- **`--risk-profile`** → aggressive/moderate/balanced

## 📋 PORTFOLIO ACTIONS
- **KEEP** → Continue holding these stocks (with reinvestment amounts)
- **SELL** → Liquidate excess/poor performing holdings
- **BUY** → New investment opportunities

**Ready to use! 🎉**