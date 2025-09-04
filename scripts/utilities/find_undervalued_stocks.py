#!/usr/bin/env python3
"""
Find Fundamentally Strong and Undervalued Stocks
Analyzes the latest Stock Report to identify undervalued opportunities
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
import logging

def find_latest_report(reports_dir="reports"):
    """Find the most recent Stock Report"""
    pattern = os.path.join(reports_dir, "Stock_Report_*.xlsx")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def load_stock_data(report_path):
    """Load stock data from Excel report"""
    try:
        # First, check what sheets are available
        try:
            all_sheets = pd.read_excel(report_path, sheet_name=None)
            sheet_names = list(all_sheets.keys())
            print(f"📋 Available sheets: {sheet_names}")
        except Exception as e:
            print(f"⚠️ Could not read sheet names: {e}")
            sheet_names = [None]  # Try default sheet
        
        # Try different sheet names
        sheets_to_try = ['Summary', 'Fundamentals', 'Combined Score', 'summary', 'SUMMARY'] + sheet_names
        
        for sheet in sheets_to_try:
            try:
                df = pd.read_excel(report_path, sheet_name=sheet)
                print(f"📊 Trying sheet '{sheet}': {df.shape[0]} rows, {df.shape[1]} columns")
                print(f"   Columns: {list(df.columns)}")
                
                if len(df) > 0 and ('Symbol' in df.columns or 'symbol' in df.columns):
                    print(f"✅ Loaded data from '{sheet}' sheet: {len(df)} stocks")
                    return df
                elif len(df) > 0:
                    # Check if first few columns might contain symbol data
                    for col in df.columns[:3]:
                        if df[col].dtype == 'object' and any('RELIANCE' in str(val).upper() or 'TCS' in str(val).upper() or 'INFY' in str(val).upper() for val in df[col].head() if pd.notna(val)):
                            print(f"✅ Found symbol-like data in column '{col}', using this sheet")
                            df = df.rename(columns={col: 'Symbol'})
                            return df
            except Exception as e:
                print(f"❌ Error reading sheet '{sheet}': {e}")
                continue
        
        # If no specific sheet works, try the default sheet
        try:
            df = pd.read_excel(report_path)
            print(f"📊 Default sheet: {df.shape[0]} rows, {df.shape[1]} columns")
            print(f"   Columns: {list(df.columns)}")
            if len(df) > 0:
                print("✅ Using default sheet")
                # Try to find symbol column
                for col in df.columns:
                    if 'symbol' in col.lower() or col.lower() in ['ticker', 'stock', 'scrip']:
                        df = df.rename(columns={col: 'Symbol'})
                        break
                return df
        except Exception as e:
            print(f"❌ Error reading default sheet: {e}")
        
        print("❌ Could not load data from any sheet")
        return None
    except Exception as e:
        print(f"❌ Error loading report: {e}")
        return None

def identify_undervalued_stocks(df):
    """Identify fundamentally strong and undervalued stocks"""
    
    # Normalize column names for easier access
    df.columns = [col.strip() for col in df.columns]
    
    # Convert relevant columns to numeric
    numeric_cols = ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity', 'revenue_growth', 
                   'earnings_growth', 'dividend_yield', 'fundamental_score', 
                   'FundamentalScore', 'fundamental_score_final', 'current_price',
                   'market_cap', 'book_value', 'eps']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Get fundamental score (try different column names)
    fund_score_col = None
    for col in ['fundamental_score_final', 'FundamentalScore', 'fundamental_score']:
        if col in df.columns and not df[col].isna().all():
            fund_score_col = col
            break
    
    if fund_score_col is None:
        print("❌ No fundamental score column found")
        return pd.DataFrame()
    
    print(f"📊 Using fundamental score from: {fund_score_col}")
    
    # Define undervaluation criteria
    criteria = {
        'strong_fundamentals': df[fund_score_col] >= 65,
        'low_pe': (df.get('pe_ratio', np.inf) <= 15) & (df.get('pe_ratio', 0) > 0),
        'low_pb': (df.get('pb_ratio', np.inf) <= 2.5) & (df.get('pb_ratio', 0) > 0),
        'good_roe': df.get('roe', 0) >= 15,
        'healthy_debt': df.get('debt_to_equity', np.inf) <= 0.5,
        'growth': df.get('revenue_growth', -100) >= 5,
        'profitable': df.get('eps', 0) > 0
    }
    
    # Apply filters progressively
    results = []
    
    # 1. Fundamentally Strong stocks
    strong_funds = df[criteria['strong_fundamentals']].copy()
    if len(strong_funds) > 0:
        print(f"🟢 Fundamentally Strong (Score ≥65): {len(strong_funds)} stocks")
        
        # 2. Among strong, find undervalued
        undervalued_mask = (
            criteria['low_pe'] & 
            criteria['low_pb'] & 
            criteria['good_roe'] & 
            criteria['healthy_debt']
        )
        
        undervalued = df[criteria['strong_fundamentals'] & undervalued_mask].copy()
        
        if len(undervalued) > 0:
            print(f"💎 Undervalued & Strong: {len(undervalued)} stocks")
            
            # Calculate undervaluation score
            undervalued['undervaluation_score'] = (
                (15 / undervalued.get('pe_ratio', 15).clip(lower=1)) * 25 +  # PE component (25%)
                (2.5 / undervalued.get('pb_ratio', 2.5).clip(lower=0.1)) * 25 +  # PB component (25%)
                (undervalued.get('roe', 15) / 100) * 25 +  # ROE component (25%)
                (1 / (undervalued.get('debt_to_equity', 0.5).clip(lower=0.01) + 1)) * 25  # Debt component (25%)
            )
            
            # Sort by combined score (fundamental + undervaluation)
            undervalued['combined_score'] = (
                undervalued[fund_score_col] * 0.6 + 
                undervalued['undervaluation_score'] * 0.4
            )
            
            undervalued = undervalued.sort_values('combined_score', ascending=False)
            
            return undervalued
    
    # If no undervalued stocks found, return fundamentally strong ones
    if len(strong_funds) > 0:
        return strong_funds.sort_values(fund_score_col, ascending=False)
    
    return pd.DataFrame()

def display_results(undervalued_df, fund_score_col):
    """Display the results in a formatted manner"""
    
    if undervalued_df.empty:
        print("❌ No undervalued stocks found with the current criteria")
        return
    
    print(f"\n🎯 TOP UNDERVALUED & FUNDAMENTALLY STRONG STOCKS")
    print("=" * 80)
    
    # Key columns to display
    display_cols = ['symbol', 'company_name', fund_score_col, 'pe_ratio', 'pb_ratio', 
                   'roe', 'debt_to_equity', 'revenue_growth', 'current_price', 'final_recommendation']
    
    # Filter available columns
    available_cols = [col for col in display_cols if col in undervalued_df.columns]
    
    for idx, (_, stock) in enumerate(undervalued_df.head(10).iterrows(), 1):
        symbol = stock.get('symbol', stock.get('Symbol', 'N/A'))
        company = stock.get('company_name', stock.get('Company Name', symbol))
        fund_score = stock.get(fund_score_col, 0)
        pe = stock.get('pe_ratio', 'N/A')
        pb = stock.get('pb_ratio', 'N/A')
        roe = stock.get('roe', 'N/A')
        debt_eq = stock.get('debt_to_equity', 'N/A')
        growth = stock.get('revenue_growth', 'N/A')
        price = stock.get('current_price', 'N/A')
        recommendation = stock.get('final_recommendation', stock.get('Recommendation', 'N/A'))
        
        print(f"\n{idx:2d}. {symbol:<12} - {company}")
        print(f"    📊 Fundamental Score: {fund_score:.1f}")
        print(f"    💰 PE Ratio: {pe if pe == 'N/A' else f'{pe:.1f}'}")
        print(f"    📈 PB Ratio: {pb if pb == 'N/A' else f'{pb:.1f}'}")
        print(f"    🏆 ROE: {roe if roe == 'N/A' else f'{roe:.1f}%'}")
        print(f"    💳 Debt/Equity: {debt_eq if debt_eq == 'N/A' else f'{debt_eq:.2f}'}")
        print(f"    📈 Revenue Growth: {growth if growth == 'N/A' else f'{growth:.1f}%'}")
        print(f"    💵 Current Price: ₹{price if price == 'N/A' else f'{price:.2f}'}")
        print(f"    🎯 Recommendation: {recommendation}")
        
        if 'combined_score' in stock:
            print(f"    ⭐ Combined Score: {stock['combined_score']:.1f}")

def export_results(undervalued_df, output_file="reports/undervalued_stocks.csv"):
    """Export results to CSV"""
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        undervalued_df.to_csv(output_file, index=False)
        print(f"\n📁 Results exported to: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def main():
    """Main execution"""
    print("🔍 FINDING UNDERVALUED STOCKS")
    print("=" * 50)
    
    # Find latest report
    report_path = find_latest_report()
    if not report_path:
        print("❌ No Stock Report found in reports/ directory")
        print("   Run analyze_top200_stocks.py first to generate a report")
        return
    
    print(f"📊 Using report: {os.path.basename(report_path)}")
    
    # Load data
    df = load_stock_data(report_path)
    if df is None:
        return
    
    # Find undervalued stocks
    undervalued = identify_undervalued_stocks(df)
    
    # Get fund score column name
    fund_score_col = None
    for col in ['fundamental_score_final', 'FundamentalScore', 'fundamental_score']:
        if col in df.columns and not df[col].isna().all():
            fund_score_col = col
            break
    
    # Display results
    display_results(undervalued, fund_score_col)
    
    # Export results
    if not undervalued.empty:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_file = f"reports/undervalued_stocks_{timestamp}.csv"
        export_results(undervalued, export_file)
        
        # Summary stats
        print(f"\n📈 SUMMARY STATISTICS")
        print("-" * 30)
        print(f"Total stocks analyzed: {len(df)}")
        print(f"Fundamentally strong (≥65): {len(df[df[fund_score_col] >= 65]) if fund_score_col else 0}")
        print(f"Undervalued opportunities: {len(undervalued)}")
        
        if 'pe_ratio' in undervalued.columns:
            avg_pe = undervalued['pe_ratio'].mean()
            print(f"Average PE of undervalued: {avg_pe:.1f}")
        
        if 'pb_ratio' in undervalued.columns:
            avg_pb = undervalued['pb_ratio'].mean()
            print(f"Average PB of undervalued: {avg_pb:.1f}")

if __name__ == "__main__":
    main()
