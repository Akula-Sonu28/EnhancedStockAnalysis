#!/usr/bin/env python3
"""
Quick Portfolio Merge - Generate corrected merged portfolio
============================================================
This script properly merges holdings and orders with correct quantity handling.

Key fixes:
- Holdings CSV already contains post-SELL quantities (don't double-deduct)
- Only apply BUY orders from today's transactions
- Properly track today's order activity
"""

from merge_holdings_orders import HoldingsOrdersMerger
from datetime import datetime
import os

def main():
    print("\n" + "="*80)
    print("PORTFOLIO MERGER - Corrected Quantity Tracking")
    print("="*80)
    
    # Find latest holdings and orders files
    holdings_file = 'Holding/holdings (6).csv'
    orders_file = 'Holding/orders (3).csv'
    
    if not os.path.exists(holdings_file):
        print(f"❌ Holdings file not found: {holdings_file}")
        return
    
    if not os.path.exists(orders_file):
        print(f"⚠️  Orders file not found: {orders_file} - continuing without orders")
        orders_file = None
    
    # Create merger
    merger = HoldingsOrdersMerger()
    
    # Load data
    print(f"\n📂 Loading holdings: {holdings_file}")
    if not merger.load_holdings_data(holdings_file):
        print("❌ Failed to load holdings data")
        return
    
    if orders_file:
        print(f"📂 Loading orders: {orders_file}")
        merger.load_orders_data(orders_file)
    
    # Merge data
    print("\n🔄 Merging data with corrected quantity logic...")
    print("   • SELL orders: Already reflected in holdings (skipped)")
    print("   • BUY orders: Added to current holdings")
    
    if not merger.merge_data():
        print("❌ Failed to merge data")
        return
    
    # Save output
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'reports/merged_portfolio_{timestamp}.xlsx'
    
    print(f"\n💾 Saving to: {output_file}")
    merger.merged_data.to_excel(output_file, index=False)
    print("✅ Saved successfully!")
    
    # Display summary
    print("\n" + "="*80)
    merger.print_summary()
    
    # Show key quantities
    df = merger.merged_data
    print("\n" + "="*80)
    print("KEY STOCK QUANTITIES")
    print("="*80)
    
    key_stocks = ['HDFCBANK', 'BAJAJHLDNG', 'CANBK', 'SBIN', 'AXISBANK']
    for stock in key_stocks:
        if stock in df['Instrument'].values:
            row = df[df['Instrument'] == stock].iloc[0]
            qty = row['Qty.']
            buy_today = row.get('Today_Buy_Qty', 0)
            sell_today = row.get('Today_Sell_Qty', 0)
            print(f"{stock:12} : {qty:6.0f} shares  (Today: +{buy_today:.0f} BUY, -{sell_today:.0f} SELL)")
    
    print("="*80)
    print(f"\n✅ Complete! Generated: {output_file}")
    print("="*80)

if __name__ == '__main__':
    main()
