#!/usr/bin/env python3
"""Check Portfolio Allocation recommendations for BOOK PROFITS actions"""

import pandas as pd
import glob
import os

# Get latest report
files = glob.glob('reports/Enhanced_Stock_Report_*.xlsx')
latest = max(files, key=os.path.getmtime)
print(f"\n📊 Latest report: {os.path.basename(latest)}")

# Check available sheets
xl = pd.ExcelFile(latest)
print(f"\n📋 Available sheets:")
for sheet in xl.sheet_names:
    print(f"   - {sheet}")

# Look for Portfolio Allocation sheet (might have different name)
portfolio_sheets = [s for s in xl.sheet_names if 'portfolio' in s.lower() or 'allocation' in s.lower()]
print(f"\n📁 Portfolio-related sheets: {portfolio_sheets}")

if portfolio_sheets:
    sheet_name = portfolio_sheets[0]
    print(f"\n🔍 Reading: {sheet_name}")
    df = pd.read_excel(latest, sheet_name=sheet_name)
    
    print(f"\n📊 Available columns:")
    for col in df.columns:
        print(f"   - {col}")
    
    # Find BOOK PROFITS recommendations
    action_col = [c for c in df.columns if 'action' in c.lower()]
    if action_col:
        action_col_name = action_col[0]
        book_profits = df[df[action_col_name].astype(str).str.contains('BOOK', na=False, case=False)]
        
        if not book_profits.empty:
            print(f"\n{'='*100}")
            print(f"STOCKS WITH 'BOOK PROFITS' ACTION ({len(book_profits)} stocks)")
            print('='*100)
            
            # Display relevant columns
            display_cols = []
            for col in ['Symbol', 'Instrument', 'Action_Type', 'Action', 'Action_Reason', 
                       'Current_Holding_Qty', 'Qty', 'Current_Value', 'Profit_Loss', 'P&L', 'Return_Pct']:
                if col in df.columns:
                    display_cols.append(col)
            
            if display_cols:
                print(book_profits[display_cols].to_string(index=False))
            else:
                print(book_profits.to_string(index=False))
            
            print('='*100)
            
            # Calculate totals
            if 'Profit_Loss' in df.columns:
                total_profit = book_profits['Profit_Loss'].sum()
                print(f"\n💰 Total profit from BOOK PROFITS stocks: ₹{total_profit:,.2f}")
            elif 'P&L' in df.columns:
                total_profit = book_profits['P&L'].sum()
                print(f"\n💰 Total profit from BOOK PROFITS stocks: ₹{total_profit:,.2f}")
            
            if 'Return_Pct' in df.columns:
                avg_return = book_profits['Return_Pct'].mean()
                print(f"📈 Average return: {avg_return:.2f}%")
        else:
            print("\n✅ No BOOK PROFITS actions found in portfolio")
else:
    print("\n⚠️  No portfolio allocation sheet found")
