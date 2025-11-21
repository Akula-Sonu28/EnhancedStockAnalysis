#!/usr/bin/env python3
"""Verify corrected portfolio quantities"""
from merge_holdings_orders import HoldingsOrdersMerger
import pandas as pd

# Create merger and load data
merger = HoldingsOrdersMerger()
merger.load_holdings_data('Holding/holdings (6).csv')
merger.load_orders_data('Holding/orders (3).csv')
merger.merge_data()

# Save corrected data
output_file = 'merged_portfolio_CORRECTED.xlsx'
merger.merged_data.to_excel(output_file, index=False)
print(f"\n✅ Saved corrected portfolio to: {output_file}")

# Display key stocks
print("\n" + "="*80)
print("CORRECTED QUANTITIES - KEY STOCKS")
print("="*80)

key_stocks = ['HDFCBANK', 'BAJAJHLDNG', 'CANBK', 'AXISBANK', 'UJJIVANSFB', 'ETERNAL']
df = merger.merged_data
key_df = df[df['Instrument'].isin(key_stocks)][['Instrument', 'Qty.', 'Today_Buy_Qty', 'Today_Sell_Qty', 'Net_Today_Orders', 'Avg. cost', 'LTP']]
print(key_df.to_string(index=False))

print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

# Check HDFCBANK
if 'HDFCBANK' in df['Instrument'].values:
    hdfcbank_qty = df[df['Instrument']=='HDFCBANK']['Qty.'].values[0]
    print(f"✅ HDFCBANK: {hdfcbank_qty} shares (Should be 31 after selling 5 from 36)")
    if hdfcbank_qty == 31:
        print("   ✓ CORRECT!")
    else:
        print(f"   ✗ WRONG! Should be 31, not {hdfcbank_qty}")

# Check BAJAJHLDNG
if 'BAJAJHLDNG' in df['Instrument'].values:
    bajaj_qty = df[df['Instrument']=='BAJAJHLDNG']['Qty.'].values[0]
    bajaj_buy = df[df['Instrument']=='BAJAJHLDNG']['Today_Buy_Qty'].values[0]
    print(f"\n✅ BAJAJHLDNG: {bajaj_qty} shares (Should be 2 after buying 1 more)")
    print(f"   Today's BUY: {bajaj_buy} share(s)")
    if bajaj_qty == 2:
        print("   ✓ CORRECT!")
    else:
        print(f"   ✗ WRONG! Should be 2, not {bajaj_qty}")

print("\n" + "="*80)
print(f"📊 Total stocks in portfolio: {len(df)}")
print(f"📊 Total current holdings qty: {df['Qty.'].sum():.0f}")
print(f"📊 Today's BUY transactions: {df['Today_Buy_Qty'].sum():.0f}")
print(f"📊 Today's SELL transactions: {df['Today_Sell_Qty'].sum():.0f}")
print("="*80)
