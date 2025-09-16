# 🚀 QUICK COMMANDS REFERENCE

## 💼 PORTFOLIO ANALYSIS
```bash
# Quick daily check with enhanced sell signals
python portfolio_analysis.py

# Full analysis with trading sheet + sell targets
python portfolio_analysis.py --funds 114129.60 --excel

# Demo enhanced features
python demo_enhanced_portfolio.py

# Custom funds amount
python portfolio_analysis.py --funds 200000 --excel
```

## 🏦 STOCK ANALYSIS  
```bash
# Interactive mode (guided setup)
python main.py --interactive

# Analyze top 200 stocks (auto-runs comparison)
python analyze_top200_stocks_enhanced.py

# Compare latest two reports manually
python compare_reports.py

# Analyze specific stock
python analyze_top200_stocks_enhanced.py -s RELIANCE

# Analyze limited stocks (faster)
python analyze_top200_stocks_enhanced.py -n 50
```

## 📊 OUTPUT FILES
- **Trading Sheet**: `reports/portfolio/Portfolio_Analysis_*.xlsx`
- **Stock Analysis**: `reports/Enhanced_Stock_Report_*.xlsx`  
- **Your Holdings**: `Holding/holdings (17).csv`

## 🎯 TRADING SIGNALS
- **🟢 STRONG BUY**: Buy at support level (S1)
- **🔴 SELL**: Sell at resistance (R1) or stop-loss
- **💰 PROFIT BOOKING**: Book profits at target levels
- **RSI < 30**: Oversold (Buy) | **RSI > 70**: Overbought (Sell)

## ⚡ VS CODE TASKS
`Ctrl+Shift+P` → "Tasks: Run Task" → Select:
- "Run main.py" - Main analysis
- "Run Stock Analysis (Top 200)" - Full stock scan
- "Analyze Single Stock" - Individual stock analysis

---
**💡 TIP**: Run `python portfolio_analysis.py --excel` weekly for complete trading insights!