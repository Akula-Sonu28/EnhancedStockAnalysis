# ⚡ QUICK COMMANDS - ORGANIZED STOCK ANALYSIS v2.0.0
# ========================================================

## 🚀 INSTANT ACCESS COMMANDS

### 📋 **GETTING STARTED (30 seconds)**
```bash
# Interactive setup (best for beginners)
python main.py --interactive

# Quick help menu
python main.py

# Tools and utilities menu
python main.py --tools

# Quick command help
python main.py --help-quick
```

### 🔧 **INTERACTIVE TOOLS (1-2 minutes)**
```bash
# Build commands interactively
python tools/command_builder.py

# Verify all features work
python tools/verify_setup.py

# Interactive investor guide
python tools/investor_guide.py

# Run project organization script
python organize_project.py
```

## ⚡ LIGHTNING-FAST ANALYSIS (2-5 minutes)

### 🔥 **AGGRESSIVE QUICK TESTS**
```bash
# Ultra-fast 5 stocks
python main.py --risk-profile aggressive -n 5

# Quick growth test
python main.py --risk-profile aggressive --focus-growth -n 10

# Quick momentum test  
python main.py --risk-profile aggressive --focus-momentum -n 10

# Quick combined test
python main.py --risk-profile aggressive --focus-growth --focus-momentum -n 10

# High-volatility quick scan
python main.py --risk-profile aggressive --min-volatility 20 -n 10
```

### ⚡ **SINGLE STOCK INSTANT ANALYSIS (30 seconds)**
```bash
# Any stock with aggressive settings
python main.py -s RELIANCE --risk-profile aggressive --focus-growth
python main.py -s TATAMOTORS --risk-profile aggressive --focus-momentum
python main.py -s HINDALCO --risk-profile aggressive --focus-growth --focus-momentum
python main.py -s ADANIPORTS --risk-profile aggressive --min-volatility 15
python main.py -s BHARTIARTL --risk-profile aggressive
python main.py -s INFY --risk-profile aggressive --focus-growth
python main.py -s WIPRO --risk-profile aggressive --focus-momentum
python main.py -s TCS --risk-profile aggressive --portfolio-amount 100000
```

## 🎯 MEDIUM-SPEED ANALYSIS (5-10 minutes)

### 📈 **GROWTH-FOCUSED COMMANDS**
```bash
# Standard growth analysis
python main.py --risk-profile aggressive --focus-growth -n 25

# Growth with volatility filter
python main.py --risk-profile aggressive --focus-growth --min-volatility 15 -n 25

# Undervalued growth stocks
python main.py --risk-profile aggressive --focus-growth --undervalued-only -n 30

# Growth portfolio builder
python main.py --risk-profile aggressive --focus-growth --portfolio-amount 200000 -n 30
```

### ⚡ **MOMENTUM-FOCUSED COMMANDS**
```bash
# Standard momentum analysis
python main.py --risk-profile aggressive --focus-momentum -n 25

# High-volatility momentum
python main.py --risk-profile aggressive --focus-momentum --min-volatility 20 -n 25

# Momentum breakout scanner
python main.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 20

# Technical momentum analysis
python main.py --risk-profile aggressive --focus-momentum --skip-risk -n 30
```

### 🎪 **COMBINED POWER COMMANDS**
```bash
# Balanced aggressive approach
python main.py --risk-profile aggressive --focus-growth --focus-momentum -n 25

# High-volatility combined
python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15 -n 25

# Portfolio-focused combined
python main.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 300000 -n 30
```

## 🚀 FULL POWER ANALYSIS (15-25 minutes)

### 💰 **PORTFOLIO BUILDERS**
```bash
# Small portfolio (₹1 lakh)
python main.py --portfolio-amount 100000 --risk-profile aggressive --focus-growth

# Medium portfolio (₹3 lakhs)
python main.py --portfolio-amount 300000 --risk-profile aggressive --focus-growth --focus-momentum

# Large portfolio (₹5 lakhs)
python main.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth

# Premium portfolio (₹10 lakhs+)
python main.py --portfolio-amount 1000000 --risk-profile aggressive --focus-growth --focus-momentum
```

### 🔥 **MAXIMUM AGGRESSIVE ANALYSIS**
```bash
# Full aggressive growth
python main.py --risk-profile aggressive --focus-growth

# Full aggressive momentum
python main.py --risk-profile aggressive --focus-momentum

# Maximum aggressive (both)
python main.py --risk-profile aggressive --focus-growth --focus-momentum

# High-volatility full scan
python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15

# Undervalued aggressive stocks
python main.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only
```

## 🌪️ VOLATILITY HUNTERS

### 📊 **BY VOLATILITY LEVEL**
```bash
# Medium volatility (≥10%)
python main.py --risk-profile aggressive --min-volatility 10 -n 30

# High volatility (≥15%)  
python main.py --risk-profile aggressive --min-volatility 15 -n 25

# Very high volatility (≥20%)
python main.py --risk-profile aggressive --min-volatility 20 -n 20

# Extreme volatility (≥25%)
python main.py --risk-profile aggressive --min-volatility 25 -n 15

# Ultra-extreme volatility (≥30%)
python main.py --risk-profile aggressive --min-volatility 30 -n 10
```

### ⚡ **VOLATILITY + FOCUS COMBINATIONS**
```bash
# Growth + High volatility
python main.py --risk-profile aggressive --focus-growth --min-volatility 20 -n 20

# Momentum + High volatility  
python main.py --risk-profile aggressive --focus-momentum --min-volatility 20 -n 20

# Both + Medium volatility
python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15 -n 25
```

## 🎯 TRADER-SPECIFIC QUICK COMMANDS

### 🔥 **DAY TRADER SETUP**
```bash
# High-frequency scanner
python main.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 15

# Quick breakout finder
python main.py --risk-profile aggressive --focus-momentum --min-volatility 30 -n 10

# Technical momentum only
python main.py --risk-profile aggressive --focus-momentum --skip-risk -n 20
```

### 📈 **SWING TRADER SETUP**
```bash
# Growth momentum combo
python main.py --risk-profile aggressive --focus-growth --focus-momentum -n 30

# Medium-term growth
python main.py --risk-profile aggressive --focus-growth --min-volatility 15 -n 25

# Value + momentum mix
python main.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only -n 25
```

### 💰 **INVESTOR SETUP**
```bash
# Growth investing
python main.py --risk-profile aggressive --focus-growth --portfolio-amount 500000

# Long-term aggressive
python main.py --risk-profile aggressive --focus-growth --undervalued-only --portfolio-amount 300000

# Diversified aggressive
python main.py --risk-profile aggressive --focus-growth --focus-momentum --portfolio-amount 500000
```

## 🛠️ PERFORMANCE-OPTIMIZED COMMANDS

### ⚡ **SPEED-FOCUSED**
```bash
# Maximum workers
python main.py --risk-profile aggressive --focus-growth -n 50 -w 8 -b 15

# Skip detailed risk analysis
python main.py --risk-profile aggressive --focus-momentum --skip-risk -n 40

# TOP 10 only (instant results)
python main.py --risk-profile aggressive --top-10-only

# Force fresh data
python main.py --risk-profile aggressive --focus-growth --force -n 20
```

### 🎯 **TARGETED ANALYSIS**
```bash
# Undervalued focus only
python main.py --risk-profile aggressive --undervalued-only -n 50

# High-performance batch
python main.py --risk-profile aggressive --focus-growth -n 30 -w 6 -b 10

# Quick portfolio scan
python main.py --risk-profile aggressive --portfolio-amount 200000 --skip-risk -n 30
```

## 📁 FILE & TEMPLATE QUICK ACCESS

### 📊 **CUSTOM LISTS**
```bash
# Use custom stock list
python main.py --risk-profile aggressive -c data/templates/my_watchlist.csv

# Nifty 50 focus
python main.py --risk-profile aggressive -c data/templates/nifty50.csv --focus-growth

# Small-cap focus
python main.py --risk-profile aggressive -c data/templates/smallcap.csv --min-volatility 20

# Export default list and exit
python main.py -e data/templates/my_export.csv
```

### 📋 **TEMPLATE MANAGEMENT**
```bash
# Copy templates to working directory
copy "data\templates\stock_list_template.csv" "my_stocks.csv"
copy "data\templates\portfolio_template.csv" "my_portfolio.csv"

# Use copied templates
python main.py --risk-profile aggressive -c my_stocks.csv --focus-growth
```

## 🔄 ORIGINAL INTERFACE QUICK COMMANDS

### ⚡ **FOR USERS WHO PREFER ORIGINAL**
```bash
# Quick aggressive test
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10

# Full analysis
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum

# Single stock
python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive --focus-growth

# Portfolio
python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive

# High volatility
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --min-volatility 20 -n 25
```

## 🎪 SPECIAL SITUATION COMMANDS

### 📊 **MARKET CONDITIONS**
```bash
# Bull market aggressive
python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 10

# Volatile market scanner
python main.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 20

# Correction opportunity finder
python main.py --risk-profile aggressive --focus-growth --undervalued-only --min-volatility 15

# Breakout preparation
python main.py --risk-profile aggressive --focus-momentum --skip-risk -n 30
```

### 💡 **RESEARCH & DISCOVERY**
```bash
# New opportunity scanner
python main.py --risk-profile aggressive --focus-growth --min-volatility 20 -n 40

# Hidden gem finder
python main.py --risk-profile aggressive --undervalued-only --min-volatility 15 -n 50

# Momentum breakout alerts
python main.py --risk-profile aggressive --focus-momentum --min-volatility 30 -n 15
```

## 🎯 ONE-LINER POWER COMMANDS

### 🔥 **MOST POPULAR (COPY-PASTE READY)**
```bash
# The Ultimate Aggressive Command
python main.py --risk-profile aggressive --focus-growth --focus-momentum --min-volatility 15 --portfolio-amount 500000

# Day Trader Special
python main.py --risk-profile aggressive --focus-momentum --min-volatility 25 -n 15 -w 5

# Growth Investor Special  
python main.py --risk-profile aggressive --focus-growth --undervalued-only --portfolio-amount 300000

# Quick Opportunity Scanner
python main.py --risk-profile aggressive --focus-growth --focus-momentum -n 20 -w 5

# High-Volatility Hunter
python main.py --risk-profile aggressive --min-volatility 20 --focus-momentum -n 25

# Portfolio Builder Supreme
python main.py --portfolio-amount 1000000 --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only
```

## ⏱️ EXECUTION TIME REFERENCE

### ⚡ **Lightning Fast (30 seconds - 2 minutes)**
- Single stock analysis (`-s SYMBOL`)
- Interactive tools (`python main.py --tools`)
- TOP 10 only (`--top-10-only`)
- Ultra-quick tests (`-n 5`)

### 🚀 **Quick (2-5 minutes)**  
- Small batch analysis (`-n 10-15`)
- Skip risk analysis (`--skip-risk`)
- High worker count (`-w 8`)

### ⚡ **Medium (5-10 minutes)**
- Medium batch analysis (`-n 25-30`)
- Standard settings
- Portfolio analysis with moderate data

### 🎯 **Full Power (15-25 minutes)**
- Full 200 stock analysis  
- Complete portfolio optimization
- Comprehensive Excel reports

## 🚀 GETTING STARTED CHECKLIST

### ✅ **First Time Setup (2 minutes)**
```bash
1. python main.py --tools                    # Access tools menu
2. Select option 2 (Setup Verification)      # Verify everything works
3. python main.py --interactive              # Try interactive mode
4. python main.py --risk-profile aggressive -n 5  # Quick test
```

### ✅ **Daily Usage Pattern**
```bash
1. python main.py --risk-profile aggressive --focus-growth -n 10     # Morning scan
2. python main.py -s [STOCK] --risk-profile aggressive               # Individual analysis  
3. python main.py --risk-profile aggressive --focus-momentum -n 20   # Momentum check
4. python main.py --portfolio-amount [AMOUNT] --risk-profile aggressive  # Portfolio review
```

## 🎉 READY TO DOMINATE THE MARKETS!

**Pick any command above and start your high-risk high-reward stock analysis journey! Every command is optimized for aggressive investors seeking maximum returns! 🚀📈💰**

---

*All commands generate professional Excel reports with trading plans, support/resistance levels, and portfolio recommendations!*
