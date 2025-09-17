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
python portfolio_analysis.py --execute-sells    # Execute sell recommendations
python portfolio_analysis.py --execute-buys     # Execute top 5 buy recommendations
python portfolio_analysis.py --execute-all-buys # Execute all buy recommendations
python portfolio_analysis.py --funds 50000      # Set available funds
python portfolio_analysis.py --funds 114130 --excel 
```

### 3. Stock Analysis
```
python analyze_top200_stocks_enhanced.py        # All 200 stocks
python analyze_top200_stocks_enhanced.py -n 50  # Fast 50 stocks
python analyze_top200_stocks_enhanced.py -s RELIANCE  # Single stock
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
- **Stock Analysis** → Top 200 stock technical ratings
- **Comparison** → Compare different analysis reports
- **Interactive** → User-friendly guided menus

**Ready to use! 🎉**