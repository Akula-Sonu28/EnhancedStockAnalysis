#!/usr/bin/env python3
"""
Quick Undervalued Stocks Analysis
Analyzes existing reports to find undervalued opportunities
"""

import pandas as pd
import numpy as np
import os

def analyze_undervalued():
    """Find undervalued stocks from existing data"""
    
    # Try the September 1st report first
    report_files = [
        "reports/Stock_Report_2025-09-01.xlsx",
        "reports/Stock_Report_2025-09-01_1100.xlsx", 
        "reports/Stock_Report_2025-09-03.xlsx"
    ]
    
    df = None
    for report_file in report_files:
        if os.path.exists(report_file):
            try:
                print(f"📊 Trying to load: {report_file}")
                
                # Try different sheets
                for sheet in [None, 'Summary', 'Fundamentals', 'Combined Score']:
                    try:
                        temp_df = pd.read_excel(report_file, sheet_name=sheet)
                        if len(temp_df) > 0:
                            print(f"✅ Loaded {len(temp_df)} rows from {report_file}")
                            print(f"   Columns: {list(temp_df.columns)}")
                            df = temp_df
                            break
                    except:
                        continue
                        
                if df is not None:
                    break
                    
            except Exception as e:
                print(f"❌ Error with {report_file}: {e}")
                continue
    
    if df is None:
        print("❌ Could not load any report file")
        return
    
    print(f"\n📈 ANALYZING {len(df)} STOCKS FOR UNDERVALUATION")
    print("=" * 60)
    
    # Find symbol column
    symbol_col = None
    for col in df.columns:
        if 'symbol' in col.lower() or col.lower() in ['ticker', 'stock']:
            symbol_col = col
            break
    
    if symbol_col is None:
        symbol_col = df.columns[0]  # Use first column as symbol
        print(f"⚠️ Using first column '{symbol_col}' as symbol")
    
    # Find fundamental score
    fund_cols = [col for col in df.columns if 'fundamental' in col.lower() and 'score' in col.lower()]
    overall_cols = [col for col in df.columns if 'overall' in col.lower() and 'score' in col.lower()]
    
    # Ensure numeric columns
    numeric_cols = ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity', 'revenue_growth', 'current_price']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Apply undervaluation filters
    print("\n🔍 APPLYING UNDERVALUATION CRITERIA:")
    
    # 1. PE Ratio filter (< 15)
    if 'pe_ratio' in df.columns:
        pe_filter = (df['pe_ratio'] > 0) & (df['pe_ratio'] <= 15)
        pe_count = len(df[pe_filter])
        print(f"   📊 PE Ratio ≤ 15: {pe_count} stocks")
    else:
        pe_filter = pd.Series([True] * len(df))
        print("   ⚠️ PE Ratio data not available")
    
    # 2. PB Ratio filter (< 2.5)  
    if 'pb_ratio' in df.columns:
        pb_filter = (df['pb_ratio'] > 0) & (df['pb_ratio'] <= 2.5)
        pb_count = len(df[pb_filter])
        print(f"   📊 PB Ratio ≤ 2.5: {pb_count} stocks")
    else:
        pb_filter = pd.Series([True] * len(df))
        print("   ⚠️ PB Ratio data not available")
    
    # 3. ROE filter (> 15%)
    if 'roe' in df.columns:
        roe_filter = df['roe'] >= 15
        roe_count = len(df[roe_filter])
        print(f"   📊 ROE ≥ 15%: {roe_count} stocks")
    else:
        roe_filter = pd.Series([True] * len(df))
        print("   ⚠️ ROE data not available")
    
    # 4. Debt filter (< 0.5)
    if 'debt_to_equity' in df.columns:
        debt_filter = df['debt_to_equity'] <= 0.5
        debt_count = len(df[debt_filter])
        print(f"   📊 Debt/Equity ≤ 0.5: {debt_count} stocks")
    else:
        debt_filter = pd.Series([True] * len(df))
        print("   ⚠️ Debt/Equity data not available")
    
    # Combine filters
    undervalued_filter = pe_filter & pb_filter & roe_filter & debt_filter
    undervalued_stocks = df[undervalued_filter].copy()
    
    print(f"\n💎 FOUND {len(undervalued_stocks)} UNDERVALUED STOCKS")
    
    if len(undervalued_stocks) > 0:
        # Sort by fundamental score if available
        if fund_cols:
            sort_col = fund_cols[0]
            undervalued_stocks = undervalued_stocks.sort_values(sort_col, ascending=False)
        elif overall_cols:
            sort_col = overall_cols[0]
            undervalued_stocks = undervalued_stocks.sort_values(sort_col, ascending=False)
        
        print("\n🏆 TOP UNDERVALUED OPPORTUNITIES:")
        print("-" * 50)
        
        for idx, (_, stock) in enumerate(undervalued_stocks.head(10).iterrows(), 1):
            symbol = stock[symbol_col]
            
            # Get available data
            pe = stock.get('pe_ratio', 'N/A')
            pb = stock.get('pb_ratio', 'N/A')
            roe = stock.get('roe', 'N/A')
            debt = stock.get('debt_to_equity', 'N/A')
            price = stock.get('current_price', 'N/A')
            
            # Get score
            score = 'N/A'
            if fund_cols and fund_cols[0] in stock:
                score = stock[fund_cols[0]]
            elif overall_cols and overall_cols[0] in stock:
                score = stock[overall_cols[0]]
            
            print(f"\n{idx:2d}. {symbol}")
            print(f"    Score: {score}")
            print(f"    PE: {pe if pe == 'N/A' else f'{pe:.1f}'}")
            print(f"    PB: {pb if pb == 'N/A' else f'{pb:.1f}'}")
            print(f"    ROE: {roe if roe == 'N/A' else f'{roe:.1f}%'}")
            print(f"    Debt/Eq: {debt if debt == 'N/A' else f'{debt:.2f}'}")
            print(f"    Price: ₹{price if price == 'N/A' else f'{price:.2f}'}")
        
        # Export results
        try:
            os.makedirs('reports', exist_ok=True)
            output_file = 'reports/undervalued_analysis.csv'
            undervalued_stocks.to_csv(output_file, index=False)
            print(f"\n📁 Results saved to: {output_file}")
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    else:
        print("❌ No stocks meet all undervaluation criteria")
        print("   Consider relaxing some filters")
        
        # Show some alternatives with relaxed criteria
        relaxed_filter = pe_filter & pb_filter  # Just PE and PB
        relaxed_stocks = df[relaxed_filter]
        
        if len(relaxed_stocks) > 0:
            print(f"\n🔄 With relaxed criteria (PE + PB only): {len(relaxed_stocks)} stocks")

if __name__ == "__main__":
    analyze_undervalued()
