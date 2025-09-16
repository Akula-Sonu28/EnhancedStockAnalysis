# 🚀 PORTFOLIO ANALYSIS CHEAT SHEET

## Quick Reference for Stock Analysis & Portfolio Management

---

## 📊 MAIN PORTFOLIO ANALYSIS COMMANDS

### 🎯 **Basic Portfolio Analysis**
```bash
# Quick overview (uses default funds: ₹114,129.60)
python portfolio_analysis.py

# Full analysis with custom funds
python portfolio_analysis.py --funds 150000

# Generate comprehensive Excel report with trading sheet
python portfolio_analysis.py --funds 114129.60 --excel

# Console + file output
python portfolio_analysis.py --funds 114129.60 --output both --excel

# Fast analysis without trading sheet (if you're in a hurry)
python portfolio_analysis.py --funds 114129.60 --no-trading-sheet --excel
```

---

## 🏦 STOCK ANALYSIS COMMANDS

### 🎯 **Enhanced Stock Report Generation**
```bash
# Interactive mode (guided command builder) 🎯
python main.py --interactive

# Analyze top 200 stocks (full analysis + auto-comparison)
python analyze_top200_stocks_enhanced.py

# Compare latest two Enhanced Stock Reports
python compare_reports.py

# Analyze specific number of stocks
python analyze_top200_stocks_enhanced.py -n 50

# Analyze single stock
python analyze_top200_stocks_enhanced.py -s RELIANCE

# Small batch with custom settings
python analyze_top200_stocks_enhanced.py -n 10 -b 5 -w 2
```

### 🎯 **Using VS Code Tasks (Recommended)**
```bash
# Run main portfolio analysis
Ctrl+Shift+P → "Tasks: Run Task" → "Run main.py"

# Analyze top 200 stocks
Ctrl+Shift+P → "Tasks: Run Task" → "Run Stock Analysis (Top 200)"

# Analyze single stock (HINDALCO example)
Ctrl+Shift+P → "Tasks: Run Task" → "Analyze Single Stock (HINDALCO)"

# Small batch analysis
Ctrl+Shift+P → "Tasks: Run Task" → "Analyze Small Batch (10 stocks)"
```

---

## 📁 FILE STRUCTURE & LOCATIONS

### 🎯 **Key Files & Directories**
```
📂 Your Portfolio System:
├── 📄 portfolio_analysis.py           # 🚀 MAIN PORTFOLIO ANALYZER
├── 📄 analyze_top200_stocks_enhanced.py  # 🏦 STOCK ANALYSIS ENGINE
├── 📄 config.py                       # ⚙️ System configuration
├── 📄 portfolio_config.py            # 🎯 Portfolio settings
│
├── 📂 portfolio/                      # 🎯 Portfolio analysis modules
│   ├── analyzer.py                   # Core analysis engine
│   ├── insights.py                   # Advanced insights
│   ├── reporter.py                   # Report generation + Trading Sheet
│   └── utils.py                      # Utility functions
│
├── 📂 Holding/                       # 💼 Your portfolio data
│   └── holdings (17).csv            # 📊 Current holdings
│
├── 📂 reports/                       # 📊 Generated reports
│   ├── Enhanced_Stock_Report_*.xlsx  # 🏦 Stock analysis reports
│   └── portfolio/                    # 🎯 Portfolio analysis reports
│       ├── Portfolio_Analysis_*.xlsx # 📊 Complete analysis + trading sheet
│       └── Portfolio_Analysis_*.txt  # 📄 Text reports
│
└── 📂 data/                          # 📈 Analysis data & logs
```

---

## 🎯 PORTFOLIO ANALYSIS FEATURES

### 📊 **What You Get in Each Analysis**

#### 🏦 **Standard Portfolio Report**
- 💰 Current P&L and returns
- 🏭 Sector allocation analysis
- ⚠️ Risk assessment and concentration analysis
- 💡 Buy/sell/hold recommendations
- 📈 Performance vs benchmarks
- 🎯 Portfolio health score (0-100)

#### 📊 **Trading Sheet (Excel)**
- 📈 **Support Levels (S1, S2)** - Where to buy
- 📉 **Resistance Levels (R1, R2)** - Where to sell
- 🛡️ **Stop Loss** - Risk management levels
- 🎯 **Target Prices (T1, T2)** - Profit booking levels
- 📊 **RSI Indicators** - Overbought/Oversold signals
- 🔄 **Entry/Exit Signals** - STRONG BUY, SELL, HOLD etc.
- 💰 **Cash Deployment Strategy** - What to buy with available funds
- 📈 **Technical Trend Analysis** - Bullish/Bearish indicators

---

## ⚙️ CONFIGURATION & CUSTOMIZATION

### 🎯 **Portfolio Settings** (`portfolio_config.py`)
```python
# Your investment parameters
DEFAULT_AVAILABLE_FUNDS = 114129.60    # Your available cash
LOSS_THRESHOLD = -10.0                  # Exit at -10% loss
PROFIT_BOOKING_THRESHOLD = 25.0         # Book profit at +25%
CONCENTRATION_LIMIT = 20.0              # Max 20% in single stock/sector

# Ideal sector allocation
TARGET_SECTOR_ALLOCATION = {
    'Financial Services': 25,  # Reduce from current 55.6%
    'IT': 20,
    'Consumer Goods': 15,
    # ... customize as needed
}
```

### 🎯 **System Settings** (`config.py`)
```python
# Performance settings
MAX_WORKERS = 3          # Parallel processing
BATCH_SIZE = 5          # Stocks per batch
TIMEOUT_SECONDS = 120   # Analysis timeout
```

---

## 🚨 QUICK ACTIONS BASED ON SIGNALS

### 📈 **Entry Signals**
```
🟢 STRONG BUY    → Buy immediately, stock is oversold at support
🟢 BUY           → Good entry point, consider adding
🟡 HOLD          → No action needed, monitor
🔴 SELL          → Exit position, stock overbought
🔴 PROFIT BOOKING → Book profits, strong gains achieved
```

### 📉 **Exit Signals**  
```
🚨 STOP LOSS     → Exit immediately, cut losses
💰 PROFIT BOOKING → Book profits, target achieved  
🔄 PARTIAL SELL  → Sell 50%, keep 50%
🟡 HOLD          → Continue holding
👀 MONITOR       → Watch closely for changes
```

### 📊 **RSI Signals**
```
RSI < 30    🟢 OVERSOLD     → Good buying opportunity
RSI 30-70   🟡 NEUTRAL     → No strong signal  
RSI > 70    🔴 OVERBOUGHT  → Consider selling
RSI > 80    🚨 VERY HIGH   → Strong sell signal
```

---

## 💡 USAGE PATTERNS & WORKFLOWS

### 🎯 **Daily Quick Check** (2 minutes)
```bash
python portfolio_analysis.py
# Review: Day P&L, immediate actions, top performers
```

### 🎯 **Weekly Full Analysis** (10 minutes)
```bash
python portfolio_analysis.py --funds 114129.60 --excel
# Review: Complete trading sheet, rebalancing, buy/sell decisions
```

### 🎯 **Monthly Deep Dive** (30 minutes)
```bash
# 1. Generate fresh stock analysis
python analyze_top200_stocks_enhanced.py

# 2. Complete portfolio analysis
python portfolio_analysis.py --funds [CURRENT_AMOUNT] --excel

# 3. Review and execute recommended actions
```

### 🎯 **Before Making Trades** 
```bash
# Always run fresh analysis before major decisions
python portfolio_analysis.py --funds [AVAILABLE_CASH] --excel
# Check: Entry/exit signals, support/resistance levels, RSI
```

---

## 🔧 TROUBLESHOOTING & TIPS

### 🎯 **Common Issues**
```bash
# If yfinance data fails
pip install --upgrade yfinance

# If Excel generation fails  
pip install openpyxl

# For permission errors
# Run PowerShell as Administrator

# For faster analysis (skip technical indicators)
python portfolio_analysis.py --no-trading-sheet
```

### 🎯 **File Management**
```bash
# Your files update automatically:
# - holdings (17).csv → Update with new holdings
# - Enhanced_Stock_Report_*.xlsx → Generated automatically
# - Portfolio_Analysis_*.xlsx → Your trading sheet

# Backup important files before major changes
# Clean old reports: reports/portfolio/ (keep latest)
```

---

## 📱 QUICK REFERENCE CARD

### 🎯 **Most Used Commands**
```bash
# Daily: Quick check
python portfolio_analysis.py

# Weekly: Full analysis + trading sheet  
python portfolio_analysis.py --funds 114129.60 --excel

# Monthly: Fresh stock analysis
python analyze_top200_stocks_enhanced.py
```

### 🎯 **Key Files to Monitor**
- 📊 `Holding/holdings (17).csv` - Your portfolio (update this)
- 📈 `reports/Enhanced_Stock_Report_*.xlsx` - Latest stock analysis 
- 🎯 `reports/portfolio/Portfolio_Analysis_*.xlsx` - Your trading sheet

### 🎯 **Critical Metrics to Watch**
- 🏆 Portfolio Health Score (Target: >80/100)
- ⚠️ Sector Concentration (Keep <30% per sector)  
- 💰 Available Cash Utilization (Deploy 80-90%)
- 📊 RSI levels (Buy <30, Sell >70)

---

**🎯 Remember**: Update your `holdings (17).csv` file regularly and run weekly analysis for best results!