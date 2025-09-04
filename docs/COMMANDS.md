# 🚀 COMPLETE COMMAND REFERENCE v2.0.0 - ORGANIZED PROJECT
# ================================================================

## 📋 NEW ORGANIZED STRUCTURE - QUICK ACCESS

### 🎯 **SIMPLE ENTRY POINTS (RECOMMENDED)**
```bash
# Interactive mode (best for beginners)
python main.py --interactive

# Quick help and common commands
python main.py --help-quick

# Access interactive tools
python main.py --tools

# Direct analysis (same as enhanced version)
python main.py --risk-profile aggressive --focus-growth -n 10
```

### 🔧 **INTERACTIVE TOOLS**
```bash
# Command builder (guided setup)
python tools/command_builder.py

# Setup verification
python tools/verify_setup.py

# Investor guide with examples
python tools/investor_guide.py
```

### ⚡ **ORIGINAL INTERFACE (STILL WORKS)**
```bash
# All your existing commands work unchanged
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth
```

## 📊 ALL COMMAND LINE OPTIONS (UNCHANGED)

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

### 1. NEW SIMPLE INTERFACE COMMANDS

#### Quick Interactive Setup:
python main.py --interactive                    # Guided command building
python main.py --tools                         # Access all tools

#### Direct Analysis (Same Power, Simpler Interface):
python main.py --risk-profile aggressive --focus-growth -n 10
python main.py --risk-profile aggressive --focus-growth --focus-momentum
python main.py --risk-profile aggressive --min-volatility 20 -n 25
python main.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth
python main.py -s RELIANCE --risk-profile aggressive --focus-growth

### 2. ORIGINAL ENHANCED INTERFACE (ALL COMMANDS WORK)

#### Quick Tests (Fast Results - 2-5 minutes)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive -n 5
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --min-volatility 15 -n 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 20 -n 10

#### Growth-Focused Analysis
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 15
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 20
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 50

#### Momentum-Focused Analysis
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 15
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 25
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -n 30

#### Combined Growth + Momentum (MAXIMUM AGGRESSIVE)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 20
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum -n 100

#### Portfolio-Based Analysis (Different Portfolio Sizes)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 50000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 100000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 200000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 500000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 1000000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 500000

#### Single Stock Deep Analysis
python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive --focus-growth
python analyze_top200_stocks_enhanced.py -s TATAMOTORS --risk-profile aggressive --focus-momentum
python analyze_top200_stocks_enhanced.py -s HINDALCO --risk-profile aggressive --focus-growth --focus-momentum
python analyze_top200_stocks_enhanced.py -s ADANIPORTS --risk-profile aggressive --min-volatility 15
python analyze_top200_stocks_enhanced.py -s BHARTIARTL --risk-profile aggressive --focus-growth --portfolio-amount 100000

#### High-Volatility Hunting
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --min-volatility 25
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 30
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 25
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 20

#### Undervalued Aggressive Stocks
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only

#### Performance Optimized (Faster Execution)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -w 5 -b 10
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --skip-risk
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --top-10-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 50 -w 8

#### Custom Stock Lists
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -c data/templates/my_watchlist.csv
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -c data/templates/nifty50.csv
python analyze_top200_stocks_enhanced.py --risk-profile aggressive -c data/templates/custom_stocks.csv --min-volatility 15

## 🎯 RECOMMENDED COMBINATIONS BY INVESTOR TYPE (BOTH INTERFACES)

### 🔥 ULTRA-AGGRESSIVE DAY TRADER
# New interface:
python main.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 30
# Original interface:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 30

### 📈 GROWTH MOMENTUM INVESTOR
# New interface:
python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15
# Original interface:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15

### 💰 HIGH-VALUE PORTFOLIO BUILDER
# New interface:
python main.py --risk-profile aggressive --focus-growth --portfolio-amount 500000 --undervalued-only
# Original interface:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --portfolio-amount 500000 --undervalued-only

### ⚡ QUICK OPPORTUNITY SCANNER
# New interface:
python main.py --risk-profile aggressive --focus-momentum -n 20 -w 5
# Original interface:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum -n 20 -w 5

### 🎪 BALANCED HIGH-RISK APPROACH
# New interface:
python main.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 200000
# Original interface:
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 200000

## 🔍 SPECIALIZED ANALYSIS COMMANDS

### Market Segment Analysis:
python main.py --risk-profile aggressive --focus-growth -n 50 --undervalued-only
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20 -n 25

### Risk-Reward Optimization:
python main.py --risk-profile aggressive --focus-growth --min-volatility 10 --portfolio-amount 300000
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 10 --portfolio-amount 300000

### Technical Breakout Hunting:
python main.py --risk-profile aggressive --focus-momentum --min-volatility 20 --skip-risk
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20 --skip-risk

### Fundamental + Technical Combo:
python main.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only --min-volatility 12
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
# Start with: python main.py --interactive
# Or try: python main.py --risk-profile aggressive --focus-growth -n 10

### For Experienced Traders:
# New: python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15
# Original: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15

### For Large Portfolios (₹5L+):
# New: python main.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth
# Original: python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth

### For Day Trading:
# New: python main.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 20
# Original: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 20

### For Value + Growth Combo:
# New: python main.py --risk-profile aggressive --focus-growth --undervalued-only
# Original: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --undervalued-only

## ⚡ QUICK REFERENCE CHEAT SHEET

### Most Popular Commands (NEW INTERFACE):
# 1. Interactive: python main.py --interactive
# 2. Quick test: python main.py --risk-profile aggressive --focus-growth -n 10
# 3. Full analysis: python main.py --risk-profile aggressive --focus-growth --focus-momentum
# 4. High volatility: python main.py --risk-profile aggressive --min-volatility 20
# 5. Portfolio building: python main.py --portfolio-amount 500000 --risk-profile aggressive
# 6. Single stock: python main.py -s RELIANCE --risk-profile aggressive --focus-growth
# 7. Tools access: python main.py --tools

### Most Popular Commands (ORIGINAL INTERFACE):
# 1. Quick test: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10
# 2. Full analysis: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum
# 3. High volatility: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --min-volatility 20
# 4. Portfolio building: python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive
# 5. Single stock: python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive --focus-growth

### Interactive Tools:
# 1. Command builder: python tools/command_builder.py
# 2. Setup verification: python tools/verify_setup.py
# 3. Investor guide: python tools/investor_guide.py

## 🚀 READY TO START!

### Recommended First Steps:
# 1. Interactive mode: python main.py --interactive
# 2. Quick help: python main.py --help-quick
# 3. Tools menu: python main.py --tools
# 4. Quick test: python main.py --risk-profile aggressive --focus-growth -n 10

### File Locations:
# - Templates: data/templates/
# - Reports: data/exports/
# - Documentation: docs/
# - Tools: tools/

## 🎉 BOTH INTERFACES AVAILABLE!

### NEW ORGANIZED INTERFACE:
- ✅ Simple entry point: python main.py
- ✅ Interactive tools and guides
- ✅ Same powerful analysis features
- ✅ Professional project structure

### ORIGINAL ENHANCED INTERFACE:
- ✅ All existing commands work unchanged
- ✅ Full backward compatibility
- ✅ Direct access to enhanced analyzer
- ✅ No migration required

**Choose whichever interface you prefer - both give you the same powerful high-risk analysis capabilities! 🚀📈**
