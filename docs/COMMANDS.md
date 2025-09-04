# 🚀 COMPLETE COMMAND REFERENCE - HIGH-RISK STOCK ANALYSIS
# =========================================================

## 📋 ALL COMMAND LINE OPTIONS

### Basic Parameters:
# -s, --symbol SYMBOL          Analyze single stock (e.g., -s RELIANCE)
# -n, --num NUMBER             Number of stocks to analyze (default: 200)
# -w, --workers NUMBER         Max worker threads (default: 3)
# -b, --batch NUMBER           Batch size for processing (default: 5)
# -c, --csv PATH               Custom CSV file with stock symbols
# --portfolio-amount AMOUNT    Portfolio amount for allocation (default: ₹1,00,000)

### High-Risk Investor Options:
# --risk-profile PROFILE       conservative|moderate|aggressive (default: moderate)
# --focus-growth              Focus on high-growth momentum stocks
# --focus-momentum            Focus on technical momentum signals
# --min-volatility NUMBER     Minimum volatility threshold (default: 0.0)

### Additional Options:
# --skip-risk                 Skip risk analysis (faster execution)
# --undervalued-only          Focus only on undervalued stocks (score ≥65)
# --top-10-only              Show only TOP 10 categories (fast mode)
# --force                    Force fresh data (ignore cache)
# -e, --export PATH          Export stock list to CSV and exit

## 🔥 HIGH-RISK INVESTOR COMMANDS (ALL POSSIBILITIES)

### 1. QUICK TESTS (Fast Results - 2-5 minutes)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive -n 5
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --min-volatility 15 -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 20 -n 10

### 2. GROWTH-FOCUSED ANALYSIS
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 15
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 20
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 50

### 3. MOMENTUM-FOCUSED ANALYSIS
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 15
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 25
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -n 30

### 4. COMBINED GROWTH + MOMENTUM (MAXIMUM AGGRESSIVE)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 20
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum -n 100

### 5. PORTFOLIO-BASED ANALYSIS (Different Portfolio Sizes)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 50000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 100000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 200000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 500000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 1000000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 500000

### 6. SINGLE STOCK DEEP ANALYSIS
python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive --focus-growth
python analyze_top200_stocks_enhanced.py -s TATAMOTORS --risk-profile aggressive --focus-momentum
python analyze_top200_stocks_enhanced.py -s HINDALCO --risk-profile aggressive --focus-growth --focus-momentum
python analyze_top200_stocks_enhanced.py -s ADANIPORTS --risk-profile aggressive --min-volatility 15
python analyze_top200_stocks_enhanced.py -s BHARTIARTL --risk-profile aggressive --focus-growth --portfolio-amount 100000

### 7. HIGH-VOLATILITY HUNTING
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --min-volatility 25
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 30
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 25
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 20

### 8. UNDERVALUED AGGRESSIVE STOCKS
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only

### 9. PERFORMANCE OPTIMIZED (Faster Execution)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -w 5 -b 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --skip-risk
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --top-10-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 50 -w 8

### 10. CUSTOM STOCK LISTS
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -c my_watchlist.csv
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -c nifty50.csv
python analyze_top200_stocks_enhanced.py --risk-profile aggressive -c custom_stocks.csv --min-volatility 15

## 🎯 RECOMMENDED COMBINATIONS BY INVESTOR TYPE

### 🔥 ULTRA-AGGRESSIVE DAY TRADER
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 30

### 📈 GROWTH MOMENTUM INVESTOR
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15

### 💰 HIGH-VALUE PORTFOLIO BUILDER
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 500000 --undervalued-only

### ⚡ QUICK OPPORTUNITY SCANNER
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -n 20 -w 5

### 🎪 BALANCED HIGH-RISK APPROACH
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 200000

## 🔍 SPECIALIZED ANALYSIS COMMANDS

### Market Segment Analysis:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 50 --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20 -n 25

### Risk-Reward Optimization:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 10 --portfolio-amount 300000

### Technical Breakout Hunting:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20 --skip-risk

### Fundamental + Technical Combo:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only --min-volatility 12

## 📊 OUTPUT EXPECTATIONS BY COMMAND TYPE

### Quick Tests (-n 5-10): 
# - 2-5 minutes execution
# - TOP 10 categories with momentum scoring
# - Basic Excel report

### Full Analysis (default 200 stocks):
# - 15-25 minutes execution  
# - Comprehensive Excel with Trading Plans sheet
# - Portfolio allocation recommendations
# - Support/resistance levels for all stocks

### Single Stock Analysis (-s SYMBOL):
# - 30-60 seconds execution
# - Detailed individual stock report
# - Complete trading plan with entry/exit points
# - Risk-reward analysis

### Portfolio Analysis (--portfolio-amount):
# - Position sizing recommendations
# - Risk-adjusted allocation percentages
# - Diversification suggestions
# - Total portfolio risk assessment

## 💡 PRO TIPS FOR COMMAND SELECTION

### For Beginners:
# Start with: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10

### For Experienced Traders:
# Use: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15

### For Large Portfolios (₹5L+):
# Use: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 500000

### For Day Trading:
# Use: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 20

### For Value + Growth Combo:
# Use: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --undervalued-only

## ⚡ QUICK REFERENCE CHEAT SHEET

# Most Popular Commands:
# 1. Quick test: --risk-profile aggressive --focus-growth -n 10
# 2. Full analysis: --risk-profile aggressive --focus-growth --focus-momentum
# 3. High volatility: --risk-profile aggressive --min-volatility 20
# 4. Portfolio building: --portfolio-amount 500000 --risk-profile aggressive
# 5. Single stock: -s RELIANCE --risk-profile aggressive --focus-growth

## 🚀 READY TO START!
# Copy any command above and run it in your terminal
# All commands will generate Excel reports with trading plans
# Results include TOP 10 categories optimized for high-risk investing
