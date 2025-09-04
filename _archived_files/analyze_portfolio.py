#!/usr/bin/env python3
"""
Portfolio Analysis for Your Holdings
Analyzes your specific portfolio holdings based on the comprehensive analysis data
"""

import sys
import pandas as pd
import os
import time
from datetime import datetime

# Add src directory to path
sys.path.append('src')

# Try to import required modules
try:
    from excel_exporter import ExcelReportGenerator
except ImportError:
    print("Warning: Could not import from excel_exporter, using fallback implementation")
    
    # Fallback implementation for report generation
    class ExcelReportGenerator:
        def __init__(self, output_dir="reports"):
            self.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)
        
        def generate_daily_report(self, df, filename=None):
            if filename is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
                filename = f"Portfolio_Report_{date_str}.xlsx"
                filename = os.path.join(self.output_dir, filename)
            
            # Create Excel writer with formatting
            writer = pd.ExcelWriter(filename, engine='openpyxl')
            
            # Write to Excel
            df.to_excel(writer, sheet_name='Portfolio Analysis', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Portfolio Analysis']
            
            # Save the workbook
            writer.close()
            
            return filename

def main():
    print("🔍 ANALYZING YOUR PORTFOLIO HOLDINGS")
    print("=" * 80)
    
    # Your portfolio holdings
    portfolio = [
        "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BDL", "BEL", 
        "CAMS", "CDSL", "CIPLA", "COALINDIA", "COFORGE", 
        "DMART", "ETERNAL", "HAL", "HDFCBANK", "HDFCLIFE", 
        "HEROMOTOCO", "HINDUNILVR", "ICICIBANK", "IDFCFIRSTB", "IEX", 
        "INFY", "ITBEES", "JIOFIN", "KOTAKBANK", "MAZDOCK", 
        "MOTILALOFS", "NESTLEIND", "ONGC", "POWERGRID", "SBICARD", 
        "SBIN", "SOUTHBANK", "TATAELXSI", "TCS", "UJJIVANSFB", 
        "WIPRO"
    ]
    
    # Clean stock symbols
    portfolio = [stock.upper().strip() for stock in portfolio]
    print(f"📊 Portfolio Size: {len(portfolio)} stocks")
    
    # Look for recent analysis files
    data_dir = "data"
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    print("\n🔍 Looking for recent analysis data...")
    
    # Try to find json file with analysis results
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json') and 'analysis' in f.lower()]
    json_files.sort(reverse=True)  # Most recent first
    
    if json_files:
        latest_json = os.path.join(data_dir, json_files[0])
        print(f"✅ Found analysis data: {latest_json}")
        
        try:
            df = pd.read_json(latest_json)
            print(f"✅ Loaded data for {len(df)} stocks")
        except:
            print("❌ Could not read JSON data, trying to find Excel files...")
            df = None
    else:
        print("⚠️ No JSON analysis files found, looking for Excel files...")
        df = None
    
    # If no JSON data, try Excel files
    if df is None:
        excel_files = [f for f in os.listdir(reports_dir) if f.endswith('.xlsx') and 'Report' in f]
        excel_files.sort(reverse=True)  # Most recent first
        
        if excel_files:
            latest_excel = os.path.join(reports_dir, excel_files[0])
            print(f"✅ Found Excel report: {latest_excel}")
            
            try:
                df = pd.read_excel(latest_excel)
                print(f"✅ Loaded data for {len(df)} stocks")
            except:
                print("❌ Could not read Excel data")
                return
        else:
            print("❌ No analysis data found. Please run the Top 200 analysis first.")
            return
    
    # Check if we have symbol column
    if 'symbol' not in df.columns:
        symbol_cols = [col for col in df.columns if 'symbol' in col.lower()]
        if symbol_cols:
            df = df.rename(columns={symbol_cols[0]: 'symbol'})
        else:
            print("❌ No symbol column found in data")
            return
    
    # Filter for portfolio holdings
    print("\n🔍 Filtering for your portfolio holdings...")
    portfolio_data = df[df['symbol'].str.upper().isin(portfolio)]
    
    if len(portfolio_data) == 0:
        print("❌ No data found for your portfolio holdings")
        return
    
    print(f"✅ Found data for {len(portfolio_data)}/{len(portfolio)} stocks")
    
    # Find missing stocks
    found_symbols = set(portfolio_data['symbol'].str.upper())
    missing_symbols = set(portfolio) - found_symbols
    
    if missing_symbols:
        print(f"⚠️ Missing data for {len(missing_symbols)} stocks: {', '.join(missing_symbols)}")
    
    # Add ranking column
    if 'overall_score_triple' in portfolio_data.columns:
        portfolio_data = portfolio_data.sort_values('overall_score_triple', ascending=False)
        portfolio_data['portfolio_rank'] = range(1, len(portfolio_data) + 1)
    elif 'overall_score' in portfolio_data.columns:
        portfolio_data = portfolio_data.sort_values('overall_score', ascending=False)
        portfolio_data['portfolio_rank'] = range(1, len(portfolio_data) + 1)
    
    # Generate portfolio report
    print("\n📊 GENERATING PORTFOLIO ANALYSIS REPORT")
    print("-" * 80)
    
    # Create timestamp for filename
    timestamp = datetime.now().strftime('%Y-%m-%d')
    filename = f"reports/Portfolio_Analysis_{timestamp}.xlsx"
    
    # Generate Excel report
    excel_generator = ExcelReportGenerator()
    report_file = excel_generator.generate_daily_report(portfolio_data, filename)
    
    print(f"\n✅ Portfolio analysis complete!")
    print(f"📊 Report saved: {report_file}")
    
    # Show portfolio summary
    print("\n📈 PORTFOLIO HOLDINGS SUMMARY")
    print("-" * 80)
    
    # Display top performers
    score_col = 'overall_score_triple' if 'overall_score_triple' in portfolio_data.columns else 'overall_score'
    if score_col in portfolio_data.columns:
        top_stocks = portfolio_data.nlargest(5, score_col)
        print("\n🏆 TOP PERFORMERS IN YOUR PORTFOLIO:")
        for idx, (_, row) in enumerate(top_stocks.iterrows(), 1):
            symbol = row['symbol']
            score = row[score_col]
            rec = row.get('final_recommendation', 'N/A') if 'final_recommendation' in row else row.get('recommendation', 'N/A')
            print(f"   {idx}. {symbol:<12}: Score {score:.1f} | {rec}")
    
    # Display stocks needing attention
    if score_col in portfolio_data.columns:
        bottom_stocks = portfolio_data.nsmallest(5, score_col)
        print("\n⚠️ HOLDINGS TO WATCH CLOSELY:")
        for idx, (_, row) in enumerate(bottom_stocks.iterrows(), 1):
            symbol = row['symbol']
            score = row[score_col]
            rec = row.get('final_recommendation', 'N/A') if 'final_recommendation' in row else row.get('recommendation', 'N/A')
            print(f"   {idx}. {symbol:<12}: Score {score:.1f} | {rec}")
    
    # Display sector distribution
    if 'sector' in portfolio_data.columns:
        sector_counts = portfolio_data['sector'].value_counts()
        print("\n🔍 SECTOR DISTRIBUTION:")
        for sector, count in sector_counts.items():
            percentage = (count / len(portfolio_data)) * 100
            print(f"   • {sector:<20}: {count:2d} stocks ({percentage:.1f}%)")
    
    # Display recommendation summary
    rec_col = 'final_recommendation' if 'final_recommendation' in portfolio_data.columns else 'recommendation'
    if rec_col in portfolio_data.columns:
        rec_counts = portfolio_data[rec_col].value_counts()
        print("\n📋 RECOMMENDATION SUMMARY:")
        for rec, count in rec_counts.items():
            percentage = (count / len(portfolio_data)) * 100
            print(f"   • {rec:<20}: {count:2d} stocks ({percentage:.1f}%)")
    
    print("\n🏁 PORTFOLIO ANALYSIS COMPLETE")

if __name__ == "__main__":
    main()
