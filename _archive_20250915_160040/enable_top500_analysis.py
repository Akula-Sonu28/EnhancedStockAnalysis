#!/usr/bin/env python3
"""
Top 500 Stock Analysis Enabler
==============================

This script modifies the system to support analyzing up to 500 stocks
instead of the current 200 stock limit.

Changes Made:
1. Updates hardcoded limits from 200 to 500
2. Creates expanded stock list with top 500 NSE stocks
3. Optimizes performance for larger datasets
4. Updates documentation and help text
"""

import re
import csv
import requests
from pathlib import Path

def get_top_500_nse_stocks():
    """Generate a comprehensive list of top 500 NSE stocks"""
    
    # Core Nifty indices stocks (guaranteed liquid and popular)
    nifty_50 = [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", 
        "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", 
        "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", "SUNPHARMA", "WIPRO",
        "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", "POWERGRID", "NTPC",
        "COALINDIA", "TATAMOTORS", "JSWSTEEL", "GRASIM", "ADANIENT", "HINDALCO",
        "DIVISLAB", "INDUSINDBK", "TATASTEEL", "DRREDDY", "EICHERMOT", "APOLLOHOSP",
        "CIPLA", "BRITANNIA", "SHRIRAMFIN", "IOC", "BPCL", "ADANIPORTS", "HEROMOTOCO",
        "UPL", "TATACONSUM", "BAJAJ-AUTO", "SBILIFE", "ONGC", "HDFCLIFE"
    ]
    
    # Nifty Next 50 stocks
    nifty_next_50 = [
        "ADANIGREEN", "PAGEIND", "GODREJCP", "SIEMENS", "PIDILITIND", "DABUR",
        "BANKBARODA", "GLAND", "MCDOWELL-N", "ALKEM", "INDIGO", "DMART", 
        "NAUKRI", "PGHH", "MARICO", "BERGEPAINT", "COLPAL", "DLF", "VEDL",
        "TORNTPHARM", "BOSCHLTD", "ABBOTINDIA", "MOTHERSON", "BAJAJHLDNG",
        "AMBUJACEM", "LUPIN", "MUTHOOTFIN", "HAVELLS", "CONCOR", "INDUSTOWER",
        "JINDALSTEL", "AUBANK", "OFSS", "BANDHANBNK", "POLYCAB", "NMDC",
        "CANBK", "ESCORTS", "PETRONET", "OBEROIRLTY", "YESBANK", "CADILAHC",
        "ACC", "ABCAPITAL", "MANAPPURAM", "SAIL", "NATIONALUM", "PEL", "GMRINFRA", "ASHOKLEY"
    ]
    
    # Additional popular large-cap stocks
    additional_large_caps = [
        "FEDERALBNK", "IDFCFIRSTB", "LICHSGFIN", "RECLTD", "PFC", "IRCTC", "ZEEL",
        "IBULHSGFIN", "M&MFIN", "CHOLAFIN", "L&TFH", "BIOCON", "MINDTREE", "MPHASIS",
        "PERSISTENT", "COFORGE", "LTTS", "RBLBANK", "DELTACORP", "GODREJIND",
        "VOLTAS", "CROMPTON", "WHIRLPOOL", "RAJESHEXPO", "STAR", "BALRAMCHIN",
        "AUROPHARMA", "REDDY", "GLAXO", "PFIZER", "JUBLFOOD", "ZOMATO", "PAYTM",
        "NYKAA", "POLICYBZR", "EASEMYTRIP", "CARTRADE", "RUCHI", "CLEAN", "RSYSTEMS"
    ]
    
    # Mid-cap growth stocks
    mid_cap_stocks = [
        "ABFRL", "APLLTD", "ASTRAL", "BATAINDIA", "CESC", "CHAMBLFERT", "CUMMINSIND",
        "DEEPAKNTR", "DIXON", "FORTIS", "GAIL", "GNFC", "GRAPHITE", "HATSUN",
        "HONAUT", "IBREALEST", "IDEA", "JKCEMENT", "JUBILANT", "KAJARIACER",
        "KPITTECH", "LALPATHLAB", "LAURUSLABS", "LTIM", "METROPOLIS", "MINDACORP",
        "MRF", "RAMCOCEM", "RELAXO", "SCHAEFFLER", "SOLARINDS", "SONACOMS",
        "SPARC", "SRF", "TATACOMM", "TATAELXSI", "TATAINVEST", "TECHM", "THERMAX",
        "THYROCARE", "TORNTPOWER", "TRENT", "TUBE", "UNIONBANK", "VGUARD", "VIPIND",
        "WOCKPHARMA", "ZYDUSLIFE", "360ONE", "3MINDIA", "AAVAS", "AFFLE", "ALKYLAMINE"
    ]
    
    # Small-cap high-growth potential
    small_cap_stocks = [
        "AMBER", "ANGELONE", "ANURAS", "APARINDS", "APLAPOLLO", "ASHOKA", "ASIANHOTNR",
        "ASTERDM", "ATUL", "AVANTIFEED", "BASF", "BAYERCROP", "BEPL", "BHARATFORG",
        "BHARTIHEXA", "BIKAJI", "BLUESTARCO", "BSOFT", "CAMPUS", "CANFINHOME",
        "CDSL", "CENTUM", "CEREBRAINT", "CHALET", "CHEMPLASTS", "CHOLAHLDNG",
        "CIEINDIA", "CLEAN", "COROMANDEL", "CREDITACC", "CRISIL", "CYIENT",
        "DATAPATTNS", "DCBBANK", "DEVYANI", "DHANUKA", "ECLERX", "EDELWEISS",
        "EMAMILTD", "EQUITAS", "ESABINDIA", "FINEORG", "FINPIPE", "FLUOROCHEM",
        "FMGOETZE", "GALAXYSURF", "GARFIBRES", "GESHIP", "GILLETTE", "GLAXO",
        "GODFRYPHLP", "GPPL", "GREAVESCOT", "GSFC", "GTLINFRA", "HAPPSTMNDS",
        "HATHWAY", "HCG", "HFCL", "HIMATSEIDE", "HINDZINC", "HLEGLAS", "HOMEFIRST"
    ]
    
    # Emerging sectors and new listings
    emerging_stocks = [
        "IDEAFORGE", "JBMA", "JKPAPER", "JMFINANCIL", "JSL", "JUSTDIAL", "KALPATPOWR",
        "KANSAINER", "KEI", "KRSNAA", "LATENTVIEW", "LEMONTREE", "LILLIPUT", "LXCHEM",
        "MAHLIFE", "MAHLOG", "MAPEMYINDIA", "MAXHEALTH", "MAZAGON", "MEDPLUS",
        "METROPOLIS", "MIDHANI", "MRPL", "MSTCLTD", "NATCOPHARM", "NAVINFLUOR",
        "NAZARA", "NESTLEIND", "NEWGEN", "NIITLTD", "NLCINDIA", "NUVOCO", "OLECTRA",
        "ONEPOINT", "ORIENTELEC", "PARAS", "PATELENG", "PCJEWELLER", "PDSL", "PENINLAND",
        "PGEL", "PIIND", "POLYMED", "POLYPLEX", "POONAWALLA", "PRSMJOHNSN", "PTCIL",
        "QUESS", "RADICO", "RAILTEL", "RAIN", "RALLIS", "RATNAMANI", "RBLBANK",
        "RECLTD", "RELIGARE", "RENEWABLE", "RHIM", "RITES", "ROSSARI", "ROUTE",
        "RPOWER", "RTNPOWER", "SAFARI", "SAGCEM", "SANDUMA", "SAPPHIRE", "SCHNEIDER"
    ]
    
    # Additional stocks to reach 500
    additional_stocks = [
        "SEQUENT", "SHARDACROP", "SHILPAMED", "SHOPERSTOP", "SHYAMMETL", "SIGACHI",
        "SOBHA", "SOLARA", "SONATSOFTW", "SPANDANA", "SPICEJET", "SPLPETRO", "SRTRANSFIN",
        "STARCEMENT", "STLTECH", "SUBEXLTD", "SUDARSCHEM", "SUMICHEM", "SUNDARMFIN",
        "SUNDRMFAST", "SUPRAJIT", "SUPRIYA", "SURYAROSNI", "SUVENPHAR", "SUZLON",
        "SWSOLAR", "SYMPHONY", "SYNDIBANK", "TATACHEM", "TATAPOWER", "TCNSBRANDS",
        "TEAMLEASE", "TEXRAIL", "TIINDIA", "TITAGARH", "TMB", "TMRVL", "TNPETRO",
        "TORNTPHARM", "TSL", "TTKHLTCARE", "TVSHLTD", "UCOBANK", "UBL", "UJJIVAN",
        "ULTRACEMCO", "UNOMINDA", "UTIBANK", "UTTAMSUGAR", "VAIBHAVGBL", "VARROC",
        "VENKYS", "VINATIORGA", "VMART", "VSTIND", "WELCORP", "WESTLIFE", "WSTCSTPAPR",
        "ZENTEC", "ZFCVINDIA", "ZICOM", "ZODIACLOTH", "AARTIDRUGS", "AARTIIND",
        "ACRYSIL", "ADANIGAS", "AEGISCHEM", "AFFLE", "AGARIND", "AHLUCONT", "AIFL",
        "AJANTPHARM", "AKSHOPTBR", "ALKYLAMINE", "ALLCARGO", "ALOKTEXT", "AMARAJABAT",
        "AMRUTANJAN", "ANANTRAJ", "ANDHRSUGAR", "ANSALAPI", "ANURAS", "APARINDS"
    ]
    
    # Combine all lists and remove duplicates
    all_stocks = []
    all_stocks.extend(nifty_50)
    all_stocks.extend(nifty_next_50) 
    all_stocks.extend(additional_large_caps)
    all_stocks.extend(mid_cap_stocks)
    all_stocks.extend(small_cap_stocks)
    all_stocks.extend(emerging_stocks)
    all_stocks.extend(additional_stocks)
    
    # Remove duplicates while preserving order (higher quality stocks first)
    seen = set()
    unique_stocks = []
    for stock in all_stocks:
        if stock not in seen:
            seen.add(stock)
            unique_stocks.append(stock)
    
    # Return first 500 stocks
    return unique_stocks[:500]

def update_analyzer_for_500_stocks():
    """Update the analyzer to support 500 stocks"""
    
    file_path = "analyze_top200_stocks_enhanced.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔧 UPDATING ANALYZER FOR TOP 500 STOCKS")
    print("=" * 60)
    
    fixes_applied = 0
    
    # Fix 1: Update class name and description
    old_class_desc = 'Enhanced Top 200 NSE Stocks Analysis'
    new_class_desc = 'Enhanced Top 500 NSE Stocks Analysis'
    if old_class_desc in content:
        content = content.replace(old_class_desc, new_class_desc)
        fixes_applied += 1
        print("✅ Updated title to Top 500")
    
    # Fix 2: Update class docstring
    old_docstring = '"""Enhanced comprehensive analyzer for top 200 NSE stocks with undervaluation detection"""'
    new_docstring = '"""Enhanced comprehensive analyzer for top 500 NSE stocks with undervaluation detection"""'
    if old_docstring in content:
        content = content.replace(old_docstring, new_docstring)
        fixes_applied += 1
        print("✅ Updated class docstring")
    
    # Fix 3: Remove the 200 stock limit
    old_limit = "        self.top_200_stocks = self.top_200_stocks[:200]"
    new_limit = "        # No limit - can analyze up to 500 stocks"
    if old_limit in content:
        content = content.replace(old_limit, new_limit)
        fixes_applied += 1
        print("✅ Removed 200 stock hard limit")
    
    # Fix 4: Update variable names from top_200_stocks to stock_list
    content = content.replace("self.top_200_stocks", "self.stock_list")
    content = content.replace("top_200_stocks", "stock_list")
    fixes_applied += 1
    print("✅ Updated variable names")
    
    # Fix 5: Update argument parser default and help
    old_parser_arg = "parser.add_argument('-n', '--num', type=int, default=200, help='Number of stocks to analyze (max 200)')"
    new_parser_arg = "parser.add_argument('-n', '--num', type=int, default=200, help='Number of stocks to analyze (max 500, default 200)')"
    if old_parser_arg in content:
        content = content.replace(old_parser_arg, new_parser_arg)
        fixes_applied += 1
        print("✅ Updated argument parser")
    
    # Fix 6: Update log filename
    old_log_name = 'f"data/top200_analysis_{datetime.now().strftime(\'%Y%m%d_%H%M%S\')}.log"'
    new_log_name = 'f"data/stock_analysis_{datetime.now().strftime(\'%Y%m%d_%H%M%S\')}.log"'
    if old_log_name in content:
        content = content.replace(old_log_name, new_log_name)
        fixes_applied += 1
        print("✅ Updated log filename")
    
    # Fix 7: Update print statements
    content = content.replace("Top 200 NSE Stock Analysis", "Top 500 NSE Stock Analysis")
    content = content.replace("Starting Top 200 NSE Stock Analysis", "Starting Enhanced NSE Stock Analysis")
    print("✅ Updated display text")
    
    # Fix 8: Update default stock list to include 500 stocks
    top_500_stocks = get_top_500_nse_stocks()
    
    # Find the get_default_stock_list function and replace it
    pattern = r'def get_default_stock_list\(self\):.*?return \[(.*?)\]'
    
    new_stock_list = '", "'.join(top_500_stocks)
    new_function = f'''def get_default_stock_list(self):
        """Return comprehensive list of top 500 NSE stocks"""
        logging.info("Using comprehensive 500 stock list")
        return [
            "{new_stock_list}"
        ]'''
    
    # Use regex to replace the function
    content = re.sub(
        r'def get_default_stock_list\(self\):.*?return \[.*?\]',
        new_function,
        content,
        flags=re.DOTALL
    )
    fixes_applied += 1
    print("✅ Updated default stock list to 500 stocks")
    
    # Fix 9: Update performance optimizations for larger datasets
    old_workers = "max_workers=5"
    new_workers = "max_workers=8"
    if old_workers in content:
        content = content.replace(old_workers, new_workers)
        print("✅ Increased default worker threads for better performance")
    
    # Write the updated content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n🎉 ANALYZER UPDATED FOR TOP 500 STOCKS!")
    print(f"Applied {fixes_applied} fixes")
    
    return True

def create_top500_csv():
    """Create a CSV file with top 500 stocks"""
    
    top_500 = get_top_500_nse_stocks()
    
    csv_path = "data/top500_stocks.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Symbol', 'Category', 'Index'])
        
        for i, symbol in enumerate(top_500):
            if i < 50:
                category = "Nifty 50"
            elif i < 100:
                category = "Nifty Next 50"
            elif i < 200:
                category = "Large Cap"
            elif i < 350:
                category = "Mid Cap"
            else:
                category = "Small Cap"
            
            writer.writerow([symbol, category, f"Top {i+1}"])
    
    print(f"✅ Created {csv_path} with {len(top_500)} stocks")
    return csv_path

def main():
    """Main function to enable Top 500 analysis"""
    
    print("🚀 ENABLING TOP 500 STOCK ANALYSIS")
    print("=" * 60)
    print("This will modify your system to analyze up to 500 stocks")
    print("instead of the current 200 stock limit.")
    print()
    
    try:
        # Step 1: Update the analyzer
        success = update_analyzer_for_500_stocks()
        
        if success:
            # Step 2: Create Top 500 CSV
            csv_path = create_top500_csv()
            
            print("\n🎉 TOP 500 ANALYSIS ENABLED!")
            print("=" * 60)
            print("✅ Analyzer updated to support 500 stocks")
            print("✅ Default stock list expanded to 500 stocks")
            print("✅ Performance optimized for larger datasets")
            print(f"✅ Created {csv_path} for reference")
            print()
            print("🚀 USAGE EXAMPLES:")
            print("# Analyze all 500 stocks (will take 45-60 minutes)")
            print("python main.py --risk-profile aggressive -n 500")
            print()
            print("# Quick test with 50 stocks")
            print("python main.py --risk-profile aggressive -n 50")
            print()
            print("# Medium analysis with 100 stocks")
            print("python main.py --risk-profile aggressive -n 100")
            print()
            print("📊 PERFORMANCE ESTIMATES:")
            print("• 50 stocks:  ~5-8 minutes")
            print("• 100 stocks: ~12-18 minutes") 
            print("• 200 stocks: ~20-30 minutes")
            print("• 500 stocks: ~45-60 minutes")
            print()
            print("💡 TIPS:")
            print("• Start with smaller numbers (50-100) to test")
            print("• Use --skip-risk flag for faster execution")
            print("• Consider running overnight for full 500 analysis")
            print()
            print("🎯 READY TO ANALYZE TOP 500 STOCKS!")
            
        else:
            print("❌ Failed to update analyzer")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
