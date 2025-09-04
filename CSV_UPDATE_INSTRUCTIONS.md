# 📋 CSV UPDATE INSTRUCTIONS

## 🎯 TO ADD MORE STOCKS TO YOUR ANALYSIS:

### Option 1: Update existing Nifty 200 file
1. Open: `data/nifty200_stocks.csv`
2. Add more rows with your preferred stocks
3. Format: Company Name,Industry,Symbol,Series,ISIN Code
4. Save the file

### Option 2: Create new CSV file
1. Create new file: `data/my_stocks.csv` 
2. Add header: Symbol (minimum required)
3. Add your stock symbols, one per line
4. Run with: `python main.py -c data/my_stocks.csv`

### Option 3: Use stock list template
1. Open: `stock_list_template.csv`
2. Add your symbols (one per line)
3. Save as new name: `my_500_stocks.csv`
4. Run with: `python main.py -c my_500_stocks.csv`

## 📊 CSV FORMAT OPTIONS:

### Simple Format (Symbol only):
```
Symbol
RELIANCE
TCS
HDFCBANK
...add your 500 stocks here...
```

### Full Format (with details):
```
Company Name,Industry,Symbol,Series,ISIN Code
Reliance Industries,Oil & Gas,RELIANCE,EQ,INE002A01018
Tata Consultancy Services,IT Services,TCS,EQ,INE467B01029
...add your stocks here...
```

## 🚀 AFTER UPDATING CSV:

1. The system will automatically detect the number of stocks
2. Run normally: `python main.py --risk-profile aggressive`
3. It will process ALL stocks in your CSV
4. Use -n flag only if you want to limit to fewer stocks

## 💡 PERFORMANCE TIPS:

- **50-100 stocks**: 10-15 minutes
- **200-300 stocks**: 25-40 minutes  
- **400-500 stocks**: 45-70 minutes
- **500+ stocks**: 60-90+ minutes

Consider running larger analyses overnight or during off-hours.

## ✅ YOU'RE ALL SET!

Update your CSV with desired stocks and the system will handle the rest!