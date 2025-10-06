#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Profit Booking Advisor - History-Aware System
===================================================
Tracks booking history to prevent over-booking across multiple runs.

Key Features:
- Remembers original quantities (baseline)
- Calculates cumulative bookings
- Recommends only remaining bookings needed
- Prevents going below minimum holdings
- Tracks booking sessions
"""

import sys
import io

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import glob
import os
from datetime import datetime
import json

class SmartProfitBookingAdvisor:
    def __init__(self):
        self.report_df = None
        self.portfolio_df = None
        self.latest_report = None
        self.booking_history_file = 'data/booking_history.json'
        self.booking_history = {}
        self.baseline_quantities = {}
        
    def load_booking_history(self):
        """Load booking history from JSON file"""
        try:
            if os.path.exists(self.booking_history_file):
                with open(self.booking_history_file, 'r') as f:
                    self.booking_history = json.load(f)
                print(f"✅ Loaded booking history: {len(self.booking_history)} stocks tracked")
            else:
                print("📝 No booking history found - creating new tracking")
                self.booking_history = {}
        except Exception as e:
            print(f"⚠️  Error loading history: {e}")
            self.booking_history = {}
    
    def save_booking_history(self):
        """Save booking history to JSON file"""
        try:
            os.makedirs('data', exist_ok=True)
            with open(self.booking_history_file, 'w') as f:
                json.dump(self.booking_history, f, indent=2)
            print(f"✅ Saved booking history: {len(self.booking_history)} stocks")
        except Exception as e:
            print(f"⚠️  Error saving history: {e}")
    
    def initialize_baseline(self, symbol, current_qty, current_price, avg_cost):
        """Initialize baseline for a stock if not already tracked"""
        if symbol not in self.booking_history:
            self.booking_history[symbol] = {
                'original_qty': current_qty,
                'current_qty': current_qty,
                'original_price': current_price,
                'avg_cost': avg_cost,
                'total_booked_qty': 0,
                'total_booked_pct': 0,
                'booking_sessions': [],
                'first_tracked': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            print(f"📝 Initialized tracking for {symbol}: {current_qty} shares")
        else:
            # Update current quantity
            old_qty = self.booking_history[symbol]['current_qty']
            self.booking_history[symbol]['current_qty'] = current_qty
            self.booking_history[symbol]['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # If quantity decreased, calculate what was booked
            if current_qty < old_qty:
                booked_this_session = old_qty - current_qty
                self.booking_history[symbol]['total_booked_qty'] += booked_this_session
                original = self.booking_history[symbol]['original_qty']
                self.booking_history[symbol]['total_booked_pct'] = (
                    self.booking_history[symbol]['total_booked_qty'] / original * 100
                )
                
                self.booking_history[symbol]['booking_sessions'].append({
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'qty_booked': booked_this_session,
                    'qty_remaining': current_qty,
                    'pct_booked': (booked_this_session / original * 100)
                })
                
                print(f"📉 Detected booking for {symbol}: -{booked_this_session} shares "
                      f"(Total booked: {self.booking_history[symbol]['total_booked_pct']:.1f}%)")
    
    def get_remaining_booking_target(self, symbol, target_pct):
        """Calculate how much more to book to reach target percentage"""
        if symbol not in self.booking_history:
            return target_pct
        
        already_booked_pct = self.booking_history[symbol]['total_booked_pct']
        remaining_pct = max(0, target_pct - already_booked_pct)
        
        return remaining_pct
    
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
        
        book_stocks = self.report_df[
            self.report_df['action_type'].astype(str).str.contains('BOOK', na=False, case=False)
        ].copy()
        
        return book_stocks
    
    def calculate_smart_booking_quantities(self, book_stocks):
        """Calculate booking quantities with history awareness"""
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
            
            current_price = stock.get('current_price', 0)
            avg_cost = stock.get('avg_cost', 0)
            
            # Initialize or update baseline
            self.initialize_baseline(symbol, current_qty, current_price, avg_cost)
            
            # Get target booking percentage from recommendation
            target_booking_pct = stock.get('profit_booking_pct', 30)
            if pd.isna(target_booking_pct):
                target_booking_pct = 30
            
            # Calculate remaining booking needed
            history = self.booking_history[symbol]
            original_qty = history['original_qty']
            already_booked_pct = history['total_booked_pct']
            already_booked_qty = history['total_booked_qty']
            
            # Calculate remaining booking target
            remaining_target_pct = max(0, target_booking_pct - already_booked_pct)
            remaining_qty_to_book = int(original_qty * (remaining_target_pct / 100))
            
            # Safety check: don't book more than current quantity
            remaining_qty_to_book = min(remaining_qty_to_book, current_qty)
            
            # Calculate what will remain after booking
            qty_after_booking = current_qty - remaining_qty_to_book
            
            # Calculate minimums based on ORIGINAL quantity
            min_holding_40_orig = int(original_qty * 0.40)
            min_holding_50_orig = int(original_qty * 0.50)
            
            # Check safety
            safe_40 = qty_after_booking >= min_holding_40_orig
            safe_50 = qty_after_booking >= min_holding_50_orig
            
            # Determine status
            if remaining_qty_to_book == 0:
                status = "✅ TARGET REACHED"
                recommended = "✅"
            elif not safe_40:
                status = "❌ UNSAFE"
                recommended = "❌"
                # Adjust to maintain 40% minimum
                remaining_qty_to_book = max(0, current_qty - min_holding_40_orig)
            elif not safe_50:
                status = "⚠️ CAUTION"
                recommended = "⚠️"
                # Suggest keeping 50%
                safe_booking = max(0, current_qty - min_holding_50_orig)
                if safe_booking < remaining_qty_to_book:
                    remaining_qty_to_book = safe_booking
            else:
                status = "✅ SAFE"
                recommended = "✅"
            
            results.append({
                'Symbol': symbol,
                'Company': stock.get('company_name', 'N/A'),
                'Original_Qty': original_qty,
                'Already_Booked_Qty': already_booked_qty,
                'Already_Booked_Pct': already_booked_pct,
                'Current_Qty': current_qty,
                'Target_Pct': target_booking_pct,
                'Remaining_Target': remaining_target_pct,
                'Book_Now': remaining_qty_to_book,
                'After_Booking': qty_after_booking,
                'Min_40%': min_holding_40_orig,
                'Min_50%': min_holding_50_orig,
                'Status': status,
                'Safe': recommended,
                'Current_Profit': stock.get('current_profit_pct', 0),
                'Reason': stock.get('profit_booking_reason', 'N/A'),
                'Current_Price': current_price,
                'Avg_Cost': avg_cost,
                'Current_Value': stock.get('current_value', 0),
                'Booking_Sessions': len(history['booking_sessions'])
            })
        
        return pd.DataFrame(results)
    
    def display_smart_summary(self, results_df):
        """Display smart booking summary with history"""
        if results_df.empty:
            print("\n✅ No profit booking recommendations found!")
            return
        
        print("\n" + "="*130)
        print(f"💰 SMART PROFIT BOOKING RECOMMENDATIONS (History-Aware)")
        print("="*130)
        
        # Separate into categories
        target_reached = results_df[results_df['Status'] == '✅ TARGET REACHED']
        need_booking = results_df[results_df['Book_Now'] > 0]
        
        if not target_reached.empty:
            print(f"\n✅ TARGET ALREADY REACHED ({len(target_reached)} stocks):")
            print("-" * 130)
            for _, row in target_reached.iterrows():
                print(f"   {row['Symbol']:12} : Already booked {row['Already_Booked_Pct']:.1f}% "
                      f"(Target: {row['Target_Pct']:.0f}%) - No further booking needed!")
        
        if not need_booking.empty:
            print(f"\n📊 NEED ADDITIONAL BOOKING ({len(need_booking)} stocks):")
            print("-" * 130)
            
            display_cols = ['Symbol', 'Company', 'Original_Qty', 'Already_Booked_Pct', 
                           'Current_Qty', 'Book_Now', 'After_Booking', 'Min_50%', 'Status']
            print(need_booking[display_cols].to_string(index=False))
            
            print("\n" + "="*130)
            print("📊 BOOKING STATISTICS")
            print("="*130)
            
            total_original = need_booking['Original_Qty'].sum()
            total_already_booked = need_booking['Already_Booked_Qty'].sum()
            total_to_book_now = need_booking['Book_Now'].sum()
            total_after = need_booking['After_Booking'].sum()
            
            print(f"📊 Original Total Holdings: {total_original:,} shares")
            print(f"📉 Already Booked: {total_already_booked:,} shares "
                  f"({total_already_booked/total_original*100:.1f}%)")
            print(f"📉 To Book Now: {total_to_book_now:,} shares "
                  f"({total_to_book_now/total_original*100:.1f}%)")
            print(f"📈 Will Remain: {total_after:,} shares "
                  f"({total_after/total_original*100:.1f}%)")
            
            # Check warnings
            caution = need_booking[need_booking['Status'].str.contains('CAUTION|UNSAFE', na=False)]
            if not caution.empty:
                print(f"\n⚠️  WARNING: {len(caution)} stocks need careful review:")
                for _, row in caution.iterrows():
                    print(f"   - {row['Symbol']}: Booking {row['Book_Now']} shares leaves "
                          f"{row['After_Booking']} (should keep ≥{row['Min_50%']})")
            
            print("="*130)
    
    def display_detailed_smart_recommendations(self, results_df):
        """Display detailed stock-by-stock recommendations with history"""
        need_booking = results_df[results_df['Book_Now'] > 0]
        
        if need_booking.empty:
            return
        
        print("\n" + "="*130)
        print("📋 DETAILED SMART RECOMMENDATIONS (History-Aware)")
        print("="*130)
        
        for idx, row in need_booking.iterrows():
            print(f"\n{idx+1}. {row['Symbol']} - {row['Company']}")
            print(f"   📊 Tracking History:")
            print(f"      • Original Holdings: {row['Original_Qty']} shares (baseline)")
            print(f"      • Already Booked: {row['Already_Booked_Qty']} shares ({row['Already_Booked_Pct']:.1f}%)")
            if row['Booking_Sessions'] > 0:
                print(f"      • Previous Sessions: {row['Booking_Sessions']} booking(s)")
            
            print(f"   💰 Current Status:")
            print(f"      • Current Holdings: {row['Current_Qty']} shares @ ₹{row['Current_Price']:.2f}")
            print(f"      • Current Profit: {row['Current_Profit']:.2f}% (Avg Cost: ₹{row['Avg_Cost']:.2f})")
            
            print(f"   🎯 Booking Plan:")
            print(f"      • Target: {row['Target_Pct']:.0f}% of original ({int(row['Original_Qty'] * row['Target_Pct']/100)} shares total)")
            print(f"      • Remaining to Book: {row['Book_Now']} shares (to reach target)")
            print(f"      • After This Booking: {row['After_Booking']} shares")
            
            print(f"   📈 Minimum Holdings (vs Original):")
            print(f"      • 40% Rule: {row['Min_40%']} shares")
            print(f"      • 50% Rule: {row['Min_50%']} shares (recommended)")
            
            print(f"   {row['Status']}")
            
            # Calculate profit impact
            if row['Book_Now'] > 0:
                book_value = row['Book_Now'] * row['Current_Price']
                profit_on_booking = row['Book_Now'] * (row['Current_Price'] - row['Avg_Cost'])
                print(f"   💵 If You Book {row['Book_Now']} Shares:")
                print(f"      • Sale Value: ₹{book_value:,.2f}")
                print(f"      • Profit Realized: ₹{profit_on_booking:,.2f}")
            
            print(f"   📝 Reason: {row['Reason']}")
    
    def generate_action_plan(self, results_df):
        """Generate smart action plan"""
        target_reached = results_df[results_df['Status'] == '✅ TARGET REACHED']
        safe_bookings = results_df[(results_df['Book_Now'] > 0) & (results_df['Status'] == '✅ SAFE')]
        caution_bookings = results_df[(results_df['Book_Now'] > 0) & (results_df['Status'].str.contains('CAUTION', na=False))]
        
        print("\n" + "="*130)
        print("🎯 SMART ACTION PLAN (History-Aware)")
        print("="*130)
        
        if not target_reached.empty:
            print(f"\n✅ NO ACTION NEEDED ({len(target_reached)} stocks) - Targets Already Reached:")
            print("   " + "-"*100)
            for _, row in target_reached.iterrows():
                print(f"   ✅ {row['Symbol']:12} : Target {row['Target_Pct']:.0f}% already booked "
                      f"({row['Already_Booked_Pct']:.1f}%) - Hold current {row['Current_Qty']} shares")
        
        if not safe_bookings.empty:
            print(f"\n1️⃣ PRIORITY 1: SAFE BOOKINGS ({len(safe_bookings)} stocks)")
            print("   " + "-"*100)
            for _, row in safe_bookings.iterrows():
                profit_value = row['Book_Now'] * (row['Current_Price'] - row['Avg_Cost'])
                cumulative_pct = row['Already_Booked_Pct'] + (row['Book_Now'] / row['Original_Qty'] * 100)
                print(f"   ✅ {row['Symbol']:12} : Book {row['Book_Now']:4} shares  ->  "
                      f"Profit: Rs.{profit_value:>10,.2f}  |  "
                      f"Progress: {row['Already_Booked_Pct']:.1f}% -> {cumulative_pct:.1f}% of target {row['Target_Pct']:.0f}%")
        
        if not caution_bookings.empty:
            print(f"\n2️⃣ PRIORITY 2: REVIEW CAREFULLY ({len(caution_bookings)} stocks)")
            print("   " + "-"*100)
            for _, row in caution_bookings.iterrows():
                print(f"   ⚠️  {row['Symbol']:12} : Book {row['Book_Now']:4} shares carefully  |  "
                      f"Will keep {row['After_Booking']} (min: {row['Min_50%']})")
        
        # Calculate totals
        total_profit = 0
        if not safe_bookings.empty:
            total_profit += safe_bookings.apply(
                lambda r: r['Book_Now'] * (r['Current_Price'] - r['Avg_Cost']), axis=1
            ).sum()
        if not caution_bookings.empty:
            total_profit += caution_bookings.apply(
                lambda r: r['Book_Now'] * (r['Current_Price'] - r['Avg_Cost']), axis=1
            ).sum()
        
        print("\n" + "="*130)
        print("💰 EXPECTED OUTCOMES (This Session)")
        print("="*130)
        print(f"💰 Total Profit to Realize: ₹{total_profit:,.2f}")
        print(f"📊 Stocks with Action: {len(safe_bookings) + len(caution_bookings)}")
        print(f"✅ Targets Reached: {len(target_reached)}")
        print("="*130)
    
    def run(self):
        """Main execution with smart history tracking"""
        print("\n" + "="*130)
        print("💰 SMART PROFIT BOOKING ADVISOR - History-Aware System")
        print("="*130)
        
        # Load booking history
        self.load_booking_history()
        
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
        
        # Calculate smart quantities
        results_df = self.calculate_smart_booking_quantities(book_stocks)
        
        # Display results
        self.display_smart_summary(results_df)
        self.display_detailed_smart_recommendations(results_df)
        self.generate_action_plan(results_df)
        
        # Save updated history
        self.save_booking_history()
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"reports/Smart_Profit_Booking_Plan_{timestamp}.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            results_df.to_excel(writer, sheet_name='Smart Booking Plan', index=False)
            book_stocks.to_excel(writer, sheet_name='Full Details', index=False)
            
            # Add history sheet
            history_df = pd.DataFrame([
                {
                    'Symbol': symbol,
                    'Original_Qty': data['original_qty'],
                    'Current_Qty': data['current_qty'],
                    'Total_Booked_Qty': data['total_booked_qty'],
                    'Total_Booked_Pct': data['total_booked_pct'],
                    'Sessions': len(data['booking_sessions']),
                    'First_Tracked': data['first_tracked'],
                    'Last_Updated': data['last_updated']
                }
                for symbol, data in self.booking_history.items()
            ])
            history_df.to_excel(writer, sheet_name='Booking History', index=False)
        
        print(f"\n📁 Detailed report saved: {output_file}")
        print(f"📁 Booking history saved: {self.booking_history_file}")
        print("="*130)

def main():
    advisor = SmartProfitBookingAdvisor()
    advisor.run()

if __name__ == '__main__':
    main()
