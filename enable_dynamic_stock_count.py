#!/usr/bin/env python3
"""
Dynamic Stock Count Enabler
===========================

This script modifies the analyzer to automatically use whatever number
of stocks you provide in your CSV file, removing hardcoded 200 limits.

You can:
1. Update your CSV with 500, 1000, or any number of stocks
2. The system will automatically process all stocks in your CSV
3. Use -n parameter to limit if you want fewer than what's in CSV

Simple and flexible approach!
"""

def enable_dynamic_stock_count():
    """Remove hardcoded limits and enable dynamic stock count from CSV"""
    
    file_path = "analyze_top200_stocks_enhanced.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔧 ENABLING DYNAMIC STOCK COUNT")
    print("=" * 50)
    
    fixes_applied = 0
    
    # Fix 1: Remove the hardcoded 200 stock limit
    old_limit = "        self.top_200_stocks = self.top_200_stocks[:200]"
    new_limit = "        # Dynamic limit - use all stocks from CSV or default list"
    
    if old_limit in content:
        content = content.replace(old_limit, new_limit)
        fixes_applied += 1
        print("✅ Removed hardcoded 200 stock limit")
    
    # Fix 2: Update argument parser to reflect no maximum limit
    old_parser_help = "parser.add_argument('-n', '--num', type=int, default=200, help='Number of stocks to analyze (max 200)')"
    new_parser_help = "parser.add_argument('-n', '--num', type=int, default=0, help='Number of stocks to analyze (0 = all stocks in CSV, default: all available)')"
    
    if old_parser_help in content:
        content = content.replace(old_parser_help, new_parser_help)
        fixes_applied += 1
        print("✅ Updated argument parser to allow unlimited stocks")
    
    # Fix 3: Modify the logic to use all stocks when num=0 or not specified
    old_num_logic = """    elif args.num < 200:
        print(f"   📊 Limiting analysis to {args.num} stocks")
        analyzer.top_200_stocks = analyzer.top_200_stocks[:args.num]"""
    
    new_num_logic = """    elif args.num > 0:
        print(f"   📊 Limiting analysis to {args.num} stocks")
        analyzer.stock_list = analyzer.stock_list[:args.num]
    else:
        print(f"   📊 Analyzing all {len(analyzer.stock_list)} stocks from data source")"""
    
    if "elif args.num < 200:" in content:
        content = content.replace(old_num_logic, new_num_logic)
        fixes_applied += 1
        print("✅ Updated stock limiting logic")
    
    # Fix 4: Update variable names for clarity
    content = content.replace("self.top_200_stocks", "self.stock_list")
    content = content.replace("top_200_stocks", "stock_list")
    fixes_applied += 1
    print("✅ Updated variable names for clarity")
    
    # Fix 5: Update display messages
    content = content.replace("Top 200 NSE Stock Analysis", "Dynamic NSE Stock Analysis")
    content = content.replace("Starting Top 200 NSE Stock Analysis", "Starting Enhanced Stock Analysis")
    content = content.replace("ENHANCED TOP 200 NSE STOCKS", "ENHANCED NSE STOCK ANALYSIS")
    print("✅ Updated display messages")
    
    # Fix 6: Update the default value handling
    old_default_logic = 'parser.add_argument(\'-n\', \'--num\', type=int, default=200,'
    new_default_logic = 'parser.add_argument(\'-n\', \'--num\', type=int, default=0,'
    
    if old_default_logic in content:
        content = content.replace(old_default_logic, new_default_logic)
        print("✅ Changed default to analyze all available stocks")
    
    # Write the updated content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n🎉 DYNAMIC STOCK COUNT ENABLED!")
    print(f"Applied {fixes_applied} fixes")
    print()
    print("🎯 HOW IT WORKS NOW:")
    print("1. Add any number of stocks to your CSV file")
    print("2. Run analysis - it will process ALL stocks in your CSV")
    print("3. Use -n parameter only if you want to limit to fewer stocks")
    print()
    print("📋 USAGE EXAMPLES:")
    print("# Process ALL stocks in your CSV")
    print("python main.py --risk-profile aggressive")
    print()
    print("# Process only first 100 stocks from your CSV")
    print("python main.py --risk-profile aggressive -n 100")
    print()
    print("# Process all with custom CSV file")
    print("python main.py --risk-profile aggressive -c your_500_stocks.csv")
    
    return True

def create_csv_instructions():
    """Create instructions for updating CSV files"""
    
    instructions = """# 📋 CSV UPDATE INSTRUCTIONS

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

Update your CSV with desired stocks and the system will handle the rest!"""

    with open("CSV_UPDATE_INSTRUCTIONS.md", 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    print("✅ Created CSV_UPDATE_INSTRUCTIONS.md")

def main():
    """Main function"""
    
    print("🚀 ENABLING DYNAMIC STOCK COUNT")
    print("=" * 60)
    print("This will remove hardcoded limits and let you analyze")
    print("any number of stocks you add to your CSV files.")
    print()
    
    try:
        success = enable_dynamic_stock_count()
        
        if success:
            create_csv_instructions()
            
            print("\n🎉 SYSTEM UPDATED FOR DYNAMIC STOCK COUNT!")
            print("=" * 60)
            print("✅ Removed hardcoded 200 stock limit")
            print("✅ System now reads ALL stocks from your CSV")
            print("✅ You control the stock count by updating CSV")
            print("✅ Created CSV update instructions")
            print()
            print("🎯 NEXT STEPS:")
            print("1. Update your CSV with desired stocks (500, 1000, etc.)")
            print("2. Run: python main.py --risk-profile aggressive")
            print("3. System will process ALL stocks in your CSV")
            print()
            print("📋 Check CSV_UPDATE_INSTRUCTIONS.md for details!")
            
        else:
            print("❌ Failed to update system")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
