#!/usr/bin/env python3
"""
Profit Booking Advisor - Integrated Portfolio Management
=========================================================
Analyzes profit booking recommendations and calculates optimal holding quantities.

Features:
- Shows all BOOK PROFITS recommendations
- Calculates minimum holding quantities (40-50% rule)
- Tracks current vs suggested quantities
- Provides tiered booking strategy
- Integrates with latest portfolio data
"""

import pandas as pd
import glob
import os
from datetime import datetime

class ProfitBookingAdvisor:
    def __init__(self):
        self.report_df = None
        self.portfolio_df = None
        self.latest_report = None
        
    def load_latest_report(self):
        """Load the latest enhanced stock report"""
        files = glob.glob('reports/Enhanced_Stock_Report_*.xlsx')
        if not files:
            print("❌ No enhanced reports found!")
            return False
        
        self.latest_report = max(files, key=os.path.getmtime)
        print(f"\n📊 Latest Report: {os.path.basename(self.latest_report)}")
        return True
    
    def load_portfolio_allocation(self):
        """Load portfolio allocation sheet"""
        try:
            self.report_df = pd.read_excel(self.latest_report, sheet_name='Portfolio Allocation')
            print(f"✅ Loaded Portfolio Allocation: {len(self.report_df)} stocks")
            return True
        except Exception as e:
            print(f"❌ Error loading Portfolio Allocation: {e}")
            return False
    
    def load_merged_portfolio(self):
        """Load merged portfolio with current holdings"""
        try:
            merged_files = glob.glob('reports/merged_portfolio_*.xlsx')
            if merged_files:
                latest_portfolio = max(merged_files, key=os.path.getmtime)
                self.portfolio_df = pd.read_excel(latest_portfolio)
                print(f"✅ Loaded Current Holdings: {os.path.basename(latest_portfolio)}")
                return True
            else:
                print("⚠️  No merged portfolio found - using report quantities")
                return False
        except Exception as e:
            print(f"⚠️  Could not load portfolio: {e}")
            return False
    
    def get_profit_booking_stocks(self):
        """Get all stocks with BOOK PROFITS recommendations"""
        if self.report_df is None:
            return None
        
        # Find stocks with BOOK in action_type
        book_stocks = self.report_df[
            self.report_df['action_type'].astype(str).str.contains('BOOK', na=False, case=False)
        ].copy()
        
        return book_stocks
    
    def calculate_booking_quantities(self, book_stocks):
        """Calculate how many shares to book and minimum to hold"""
        results = []
        
        for _, stock in book_stocks.iterrows():
            symbol = stock['symbol']
            
            # Get current quantity
            if self.portfolio_df is not None and symbol in self.portfolio_df['Instrument'].values:
                current_qty = int(self.portfolio_df[self.portfolio_df['Instrument']==symbol]['Qty.'].values[0])
            elif 'current_quantity' in stock and pd.notna(stock['current_quantity']):
                current_qty = int(stock['current_quantity'])
            else:
                current_qty = 0
            
            if current_qty == 0:
                continue
            
            # Get booking percentage from recommendation
            booking_pct = stock.get('profit_booking_pct', 30)
            if pd.isna(booking_pct):
                booking_pct = 30
            
            # Calculate quantities
            qty_to_book = int(current_qty * (booking_pct / 100))
            qty_remaining = current_qty - qty_to_book
            min_holding_40 = int(current_qty * 0.40)  # 40% minimum
            min_holding_50 = int(current_qty * 0.50)  # 50% minimum (recommended)
            
            # Determine if booking is safe
            safe_to_book = qty_remaining >= min_holding_40
            recommended_safe = qty_remaining >= min_holding_50
            
            results.append({
                'Symbol': symbol,
                'Company': stock.get('company_name', 'N/A'),
                'Current_Qty': current_qty,
                'Book_Pct': booking_pct,
                'Book_Qty': qty_to_book,
                'After_Booking': qty_remaining,
                'Min_40%': min_holding_40,
                'Min_50%': min_holding_50,
                'Safe': '✅' if safe_to_book else '⚠️',
                'Recommended': '✅' if recommended_safe else '⚠️',
                'Current_Profit': stock.get('current_profit_pct', 0),
                'Reason': stock.get('profit_booking_reason', 'N/A'),
                'Current_Price': stock.get('current_price', 0),
                'Avg_Cost': stock.get('avg_cost', 0),
                'Current_Value': stock.get('current_value', 0),
            })
        
        return pd.DataFrame(results)
    
    def display_profit_booking_summary(self, results_df):
        """Display comprehensive profit booking summary"""
        if results_df.empty:
            print("\n✅ No profit booking recommendations found!")
            return
        
        print("\n" + "="*120)
        print(f"💰 PROFIT BOOKING RECOMMENDATIONS ({len(results_df)} stocks)")
        print("="*120)
        
        # Display main summary
        display_cols = ['Symbol', 'Company', 'Current_Qty', 'Book_Pct', 'Book_Qty', 
                       'After_Booking', 'Min_50%', 'Recommended', 'Current_Profit']
        print(results_df[display_cols].to_string(index=False))
        
        print("\n" + "="*120)
        print("📊 SUMMARY STATISTICS")
        print("="*120)
        
        total_current_qty = results_df['Current_Qty'].sum()
        total_book_qty = results_df['Book_Qty'].sum()
        total_after_qty = results_df['After_Booking'].sum()
        avg_profit = results_df['Current_Profit'].mean()
        total_value = results_df['Current_Value'].sum()
        
        print(f"📊 Total Current Holdings: {total_current_qty:,} shares")
        print(f"📉 Total to Book: {total_book_qty:,} shares ({total_book_qty/total_current_qty*100:.1f}%)")
        print(f"📈 Total After Booking: {total_after_qty:,} shares ({total_after_qty/total_current_qty*100:.1f}%)")
        print(f"💰 Average Profit: {avg_profit:.2f}%")
        print(f"💵 Total Current Value: ₹{total_value:,.2f}")
        
        # Check safety
        unsafe = results_df[results_df['Recommended'] == '⚠️']
        if not unsafe.empty:
            print(f"\n⚠️  WARNING: {len(unsafe)} stocks will be below 50% minimum after booking:")
            for _, row in unsafe.iterrows():
                print(f"   - {row['Symbol']}: {row['After_Booking']} shares (< {row['Min_50%']} minimum)")
                print(f"     Suggestion: Book only {row['Current_Qty'] - row['Min_50%']} shares to maintain 50%")
        else:
            print(f"\n✅ All bookings maintain minimum 50% holdings - Safe to proceed!")
        
        print("="*120)
    
    def display_detailed_recommendations(self, results_df):
        """Display detailed stock-by-stock recommendations"""
        if results_df.empty:
            return
        
        print("\n" + "="*120)
        print("📋 DETAILED STOCK-BY-STOCK RECOMMENDATIONS")
        print("="*120)
        
        for idx, row in results_df.iterrows():
            print(f"\n{idx+1}. {row['Symbol']} - {row['Company']}")
            print(f"   📊 Current Holdings: {row['Current_Qty']} shares @ ₹{row['Current_Price']:.2f}")
            print(f"   💰 Current Profit: {row['Current_Profit']:.2f}% (Avg Cost: ₹{row['Avg_Cost']:.2f})")
            print(f"   📉 Recommended Action: BOOK {row['Book_Pct']:.0f}% = {row['Book_Qty']} shares")
            print(f"   📈 After Booking: {row['After_Booking']} shares remaining")
            print(f"   🎯 Minimum Holdings:")
            print(f"      • 40% Rule: {row['Min_40%']} shares (Conservative)")
            print(f"      • 50% Rule: {row['Min_50%']} shares (Recommended) {row['Recommended']}")
            print(f"   📝 Reason: {row['Reason']}")
            
            # Calculate value impact
            book_value = row['Book_Qty'] * row['Current_Price']
            profit_on_booking = row['Book_Qty'] * (row['Current_Price'] - row['Avg_Cost'])
            print(f"   💵 Booking Impact:")
            print(f"      • Sale Value: ₹{book_value:,.2f}")
            print(f"      • Profit Realized: ₹{profit_on_booking:,.2f}")
            
            # Provide specific advice
            if row['Recommended'] == '⚠️':
                safe_book = row['Current_Qty'] - row['Min_50%']
                print(f"   ⚠️  CAUTION: Recommended booking leaves only {row['After_Booking']} shares")
                print(f"      Suggestion: Book only {safe_book} shares to maintain 50% minimum")
            else:
                print(f"   ✅ SAFE: Booking maintains healthy position")
    
    def generate_action_plan(self, results_df):
        """Generate executable action plan"""
        if results_df.empty:
            return
        
        print("\n" + "="*120)
        print("🎯 YOUR ACTION PLAN")
        print("="*120)
        
        # Priority 1: Safe bookings (maintains 50%+)
        safe_bookings = results_df[results_df['Recommended'] == '✅']
        if not safe_bookings.empty:
            print("\n1️⃣ PRIORITY 1: SAFE PROFIT BOOKINGS (Maintains 50%+ holdings)")
            print("   " + "-"*80)
            for _, row in safe_bookings.iterrows():
                profit_value = row['Book_Qty'] * (row['Current_Price'] - row['Avg_Cost'])
                print(f"   ✅ {row['Symbol']:12} : Book {row['Book_Qty']:4} shares  →  Profit: ₹{profit_value:>10,.2f}  |  Keep: {row['After_Booking']} shares")
        
        # Priority 2: Caution bookings (below 50%)
        caution_bookings = results_df[results_df['Recommended'] == '⚠️']
        if not caution_bookings.empty:
            print("\n2️⃣ PRIORITY 2: CAREFUL BOOKINGS (Review quantities)")
            print("   " + "-"*80)
            for _, row in caution_bookings.iterrows():
                safe_qty = row['Current_Qty'] - row['Min_50%']
                print(f"   ⚠️  {row['Symbol']:12} : Book {safe_qty:4} shares (not {row['Book_Qty']})  |  Keep: {row['Min_50%']} shares (50% min)")
        
        # Summary
        total_safe_profit = safe_bookings.apply(
            lambda r: r['Book_Qty'] * (r['Current_Price'] - r['Avg_Cost']), axis=1
        ).sum() if not safe_bookings.empty else 0
        
        total_caution_profit = caution_bookings.apply(
            lambda r: (r['Current_Qty'] - r['Min_50%']) * (r['Current_Price'] - r['Avg_Cost']), axis=1
        ).sum() if not caution_bookings.empty else 0
        
        print("\n" + "="*120)
        print("💰 EXPECTED OUTCOMES")
        print("="*120)
        print(f"✅ Safe Bookings: ₹{total_safe_profit:,.2f} profit realized")
        if total_caution_profit > 0:
            print(f"⚠️  Adjusted Bookings: ₹{total_caution_profit:,.2f} profit realized (safer quantities)")
        print(f"🎯 Total Profit to Realize: ₹{total_safe_profit + total_caution_profit:,.2f}")
        print("="*120)
    
    def run(self):
        """Main execution"""
        print("\n" + "="*120)
        print("💰 PROFIT BOOKING ADVISOR - Portfolio Management System")
        print("="*120)
        
        # Load data
        if not self.load_latest_report():
            return
        
        if not self.load_portfolio_allocation():
            return
        
        self.load_merged_portfolio()
        
        # Get profit booking stocks
        book_stocks = self.get_profit_booking_stocks()
        if book_stocks is None or book_stocks.empty:
            print("\n✅ No profit booking recommendations found in current analysis!")
            return
        
        print(f"\n🎯 Found {len(book_stocks)} stocks with profit booking recommendations")
        
        # Calculate quantities
        results_df = self.calculate_booking_quantities(book_stocks)
        
        # Display results
        self.display_profit_booking_summary(results_df)
        self.display_detailed_recommendations(results_df)
        self.generate_action_plan(results_df)
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"reports/Profit_Booking_Plan_{timestamp}.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            results_df.to_excel(writer, sheet_name='Booking Plan', index=False)
            book_stocks.to_excel(writer, sheet_name='Full Details', index=False)
        
        print(f"\n📁 Detailed report saved: {output_file}")
        print("="*120)

def main():
    advisor = ProfitBookingAdvisor()
    advisor.run()

if __name__ == '__main__':
    main()
