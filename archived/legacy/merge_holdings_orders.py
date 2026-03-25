#!/usr/bin/env python3
"""
Holdings and Orders Merger Tool
===============================

This script merges holdings and orders data to provide a comprehensive portfolio view.
It handles different data formats and creates a unified consolidated report.

Author: Stock Analysis System
Date: September 19, 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import json
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/holdings_orders_merge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HoldingsOrdersMerger:
    """
    Merges holdings and orders data into a unified portfolio view
    """
    
    def __init__(self):
        self.holdings_data = None
        self.orders_data = None
        self.merged_data = None
        self.stock_mapping = {}
        
        # Load stock symbol mapping from template
        self.load_stock_mapping()
    
    def load_stock_mapping(self):
        """Load stock symbol to company name mapping"""
        try:
            stock_template = pd.read_csv('stock_list_template.csv')
            for _, row in stock_template.iterrows():
                self.stock_mapping[row['Symbol']] = {
                    'company_name': row['Company Name'],
                    'industry': row['Industry'],
                    'series': row['Series'],
                    'isin': row['ISIN Code']
                }
            logger.info(f"Loaded {len(self.stock_mapping)} stock mappings")
        except Exception as e:
            logger.warning(f"Could not load stock mapping: {e}")
    
    def load_holdings_data(self, file_path):
        """Load holdings data from CSV file"""
        try:
            # Clean the CSV file path and read data
            self.holdings_data = pd.read_csv(file_path)
            
            # Clean column names (remove quotes and extra spaces)
            self.holdings_data.columns = self.holdings_data.columns.str.strip().str.replace('"', '')
            
            # Clean data values
            for col in self.holdings_data.columns:
                if self.holdings_data[col].dtype == 'object':
                    self.holdings_data[col] = self.holdings_data[col].astype(str).str.strip().str.replace('"', '')
            
            # Convert numeric columns
            numeric_columns = ['Qty.', 'Avg. cost', 'LTP', 'Invested', 'Cur. val', 'P&L', 'Net chg.', 'Day chg.']
            for col in numeric_columns:
                if col in self.holdings_data.columns:
                    self.holdings_data[col] = pd.to_numeric(self.holdings_data[col], errors='coerce')
            
            logger.info(f"Loaded holdings data: {len(self.holdings_data)} records")
            return True
            
        except Exception as e:
            logger.error(f"Error loading holdings data: {e}")
            return False
    
    def load_orders_data(self, file_path=None):
        """Load orders data from various possible sources"""
        orders_found = False
        
        # If specific file provided
        if file_path and os.path.exists(file_path):
            try:
                if file_path.endswith('.xlsx'):
                    self.orders_data = pd.read_excel(file_path)
                else:
                    self.orders_data = pd.read_csv(file_path)
                logger.info(f"Loaded orders from: {file_path}")
                orders_found = True
            except Exception as e:
                logger.error(f"Error loading orders from {file_path}: {e}")
        
        # Search for common order file patterns
        search_patterns = [
            'orders*.csv',
            'orders*.xlsx', 
            'trades*.csv',
            'trades*.xlsx',
            'transactions*.csv',
            'transactions*.xlsx',
            '*order*.csv',
            '*order*.xlsx'
        ]
        
        if not orders_found:
            for pattern in search_patterns:
                matching_files = list(Path('.').glob(pattern))
                if matching_files:
                    try:
                        file_path = matching_files[0]
                        if str(file_path).endswith('.xlsx'):
                            self.orders_data = pd.read_excel(file_path)
                        else:
                            self.orders_data = pd.read_csv(file_path)
                        logger.info(f"Found and loaded orders from: {file_path}")
                        orders_found = True
                        break
                    except Exception as e:
                        logger.warning(f"Could not load {file_path}: {e}")
        
        if not orders_found:
            logger.warning("No orders data found. Will work with holdings only.")
            # Create empty orders dataframe
            self.orders_data = pd.DataFrame(columns=['Symbol', 'Order_Type', 'Qty', 'Price', 'Date'])
        
        return orders_found
    
    def _detect_already_processed_orders(self, holdings_df):
        """Detect if orders have already been processed in the holdings file"""
        try:
            # Check for indicators that orders are already processed:
            # 1. SELL orders for stocks with 0 quantity in holdings
            # 2. BUY orders for stocks already in holdings (might be new purchases)
            
            type_col = 'Type' if 'Type' in self.orders_data.columns else 'Trans. type'
            sell_orders = self.orders_data[self.orders_data[type_col].str.upper() == 'SELL']
            
            processed_sells = 0
            for _, order in sell_orders.iterrows():
                symbol = order['Instrument']
                # If we have a SELL order for a stock with 0 quantity, it's likely already processed
                if symbol in holdings_df['Instrument'].values:
                    current_qty = holdings_df[holdings_df['Instrument'] == symbol]['Qty.'].iloc[0]
                    if current_qty == 0:
                        processed_sells += 1
            
            # IMPORTANT: Broker holdings CSV always contains CURRENT quantities (post-SELL)
            # We should ONLY apply BUY orders to avoid double-deduction
            logger.info("✅ Holdings CSV contains current quantities after sells (standard broker format)")
            logger.info("   Only BUY orders will be processed to prevent double-counting")
            return True  # Always treat SELL orders as already processed
            
        except Exception as e:
            logger.error(f"Error detecting processed orders: {e}")
            return True  # Default to safe mode: don't apply sells
    
    def _process_buy_sell_orders(self, holdings_df):
        """Process BUY and SELL orders to update holdings correctly"""
        try:
            # Check if SELL orders are already processed
            sells_already_processed = self._detect_already_processed_orders(holdings_df)
            
            # Create a copy of holdings
            updated_holdings = holdings_df.copy()
            
            # Check if orders data has the required columns
            type_col = None
            if 'Trans. type' in self.orders_data.columns:
                type_col = 'Trans. type'
            elif 'Type' in self.orders_data.columns:
                type_col = 'Type'
            elif 'Transaction Type' in self.orders_data.columns:
                type_col = 'Transaction Type'
            
            if type_col is None or 'Instrument' not in self.orders_data.columns:
                logger.warning("Orders data missing required columns for BUY/SELL processing")
                return None
            
            # Extract quantity from different possible formats
            qty_col = None
            if 'Qty.' in self.orders_data.columns:
                qty_col = 'Qty.'
            elif 'Quantity' in self.orders_data.columns:
                qty_col = 'Quantity'
            elif 'Qty' in self.orders_data.columns:
                qty_col = 'Qty'
            
            if qty_col is None:
                logger.warning("No quantity column found in orders data")
                return None
            
            # Process each order
            for _, order in self.orders_data.iterrows():
                symbol = order['Instrument']
                order_type = order[type_col].upper()
                
                # Extract quantity (handle formats like "6/6" or just "6")
                qty_str = str(order[qty_col])
                if '/' in qty_str:
                    qty = float(qty_str.split('/')[0])
                else:
                    qty = float(qty_str)
                
                # Process BUY orders - Add new stocks to holdings
                if order_type == 'BUY':
                    if symbol not in updated_holdings['Instrument'].values:
                        # Add new stock to holdings
                        price = float(order.get('Avg. price', 0))
                        new_holding = {
                            'Instrument': symbol,
                            'Qty.': qty,
                            'Avg. cost': price,
                            'LTP': price,  # Will be updated with current price
                            'Invested': qty * price,
                            'Cur. val': qty * price,  # Will be updated with current price
                            'P&L': 0,  # Will be calculated later
                            'Net chg.': 0,
                            'Day chg.': 0
                        }
                        # Add new row to holdings
                        new_row_df = pd.DataFrame([new_holding])
                        updated_holdings = pd.concat([updated_holdings, new_row_df], ignore_index=True)
                        logger.info(f"Added BUY order: {symbol} - {qty} shares at Rs.{price}")
                    else:
                        # Update existing holding (increase quantity)
                        idx = updated_holdings[updated_holdings['Instrument'] == symbol].index[0]
                        current_qty = updated_holdings.loc[idx, 'Qty.']
                        current_avg_cost = updated_holdings.loc[idx, 'Avg. cost']
                        current_invested = updated_holdings.loc[idx, 'Invested']
                        
                        new_price = float(order.get('Avg. price', current_avg_cost))
                        new_invested = qty * new_price
                        
                        # Calculate new average cost
                        total_invested = current_invested + new_invested
                        total_qty = current_qty + qty
                        new_avg_cost = total_invested / total_qty if total_qty > 0 else current_avg_cost
                        
                        # Update holdings
                        updated_holdings.loc[idx, 'Qty.'] = total_qty
                        updated_holdings.loc[idx, 'Avg. cost'] = new_avg_cost
                        updated_holdings.loc[idx, 'Invested'] = total_invested
                        logger.info(f"Updated BUY order: {symbol} - added {qty} shares, new total: {total_qty}")
                
                # Process SELL orders - Only if not already processed
                elif order_type == 'SELL' and not sells_already_processed:
                    if symbol in updated_holdings['Instrument'].values:
                        idx = updated_holdings[updated_holdings['Instrument'] == symbol].index[0]
                        current_qty = updated_holdings.loc[idx, 'Qty.']
                        
                        if qty >= current_qty:
                            # Sold all shares - remove from holdings
                            updated_holdings = updated_holdings.drop(idx).reset_index(drop=True)
                            logger.info(f"Removed SELL order: {symbol} - sold all {current_qty} shares")
                        else:
                            # Partial sale - reduce quantity
                            new_qty = current_qty - qty
                            current_avg_cost = updated_holdings.loc[idx, 'Avg. cost']
                            new_invested = new_qty * current_avg_cost
                            
                            updated_holdings.loc[idx, 'Qty.'] = new_qty
                            updated_holdings.loc[idx, 'Invested'] = new_invested
                            logger.info(f"Updated SELL order: {symbol} - sold {qty} shares, remaining: {new_qty}")
                    else:
                        logger.warning(f"SELL order for {symbol} but stock not in holdings")
                elif order_type == 'SELL' and sells_already_processed:
                    logger.info(f"Skipped SELL order: {symbol} - already processed in holdings")
            
            return updated_holdings
            
        except Exception as e:
            logger.error(f"Error processing BUY/SELL orders: {e}")
            return None
    
    def _calculate_order_statistics(self):
        """
        Calculate order statistics from today's orders CSV
        Note: Only shows TODAY's orders, not historical holdings
        """
        try:
            if self.orders_data is None or self.orders_data.empty:
                return None
            
            # Prepare orders data
            orders = self.orders_data.copy()
            
            # Extract quantity from different possible formats
            qty_col = None
            if 'Qty.' in orders.columns:
                qty_col = 'Qty.'
            elif 'Quantity' in orders.columns:
                qty_col = 'Quantity'
            elif 'Qty' in orders.columns:
                qty_col = 'Qty'
            
            if qty_col is None:
                return None
            
            # Extract quantity (handle formats like "6/6" or just "6")
            orders['Order_Qty'] = orders[qty_col].astype(str).str.split('/').str[0].astype(float)
            
            # Find the correct type column
            type_col = None
            if 'Trans. type' in orders.columns:
                type_col = 'Trans. type'
            elif 'Type' in orders.columns:
                type_col = 'Type'
            elif 'Transaction Type' in orders.columns:
                type_col = 'Transaction Type'
            
            if type_col is None:
                return None
                
            # Separate BUY and SELL orders (TODAY's orders only)
            buy_orders = orders[orders[type_col].str.upper() == 'BUY'].copy()
            sell_orders = orders[orders[type_col].str.upper() == 'SELL'].copy()
            
            logger.info(f"📊 Today's Orders: {len(buy_orders)} BUYs, {len(sell_orders)} SELLs")
            
            # Calculate statistics by instrument
            buy_stats = buy_orders.groupby('Instrument').agg({
                'Order_Qty': 'sum',
                'Avg. price': 'mean'
            }).rename(columns={'Order_Qty': 'Today_Buy_Qty', 'Avg. price': 'Avg_Buy_Price'})
            
            sell_stats = sell_orders.groupby('Instrument').agg({
                'Order_Qty': 'sum',
                'Avg. price': 'mean'
            }).rename(columns={'Order_Qty': 'Today_Sell_Qty', 'Avg. price': 'Avg_Sell_Price'})
            
            # Combine statistics
            order_stats = buy_stats.merge(sell_stats, on='Instrument', how='outer').fillna(0)
            order_stats['Net_Today_Orders'] = order_stats['Today_Buy_Qty'] - order_stats['Today_Sell_Qty']
            
            # Calculate weighted average price for today's orders
            order_stats['Avg_Order_Price'] = (
                (order_stats['Today_Buy_Qty'] * order_stats['Avg_Buy_Price'] + 
                 order_stats['Today_Sell_Qty'] * order_stats['Avg_Sell_Price']) / 
                (order_stats['Today_Buy_Qty'] + order_stats['Today_Sell_Qty'])
            ).fillna(0)
            
            # Reset index to make Instrument a column
            order_stats = order_stats.reset_index()
            
            return order_stats[['Instrument', 'Today_Buy_Qty', 'Today_Sell_Qty', 'Net_Today_Orders', 'Avg_Order_Price']]
            
        except Exception as e:
            logger.error(f"Error calculating order statistics: {e}")
            return None
    
    def merge_data(self):
        """Merge holdings and orders data with proper BUY/SELL transaction processing"""
        if self.holdings_data is None:
            logger.error("Holdings data not loaded")
            return False

        try:
            # Start with holdings data as base
            merged = self.holdings_data.copy()
            
            # Process orders data if available
            if self.orders_data is not None and not self.orders_data.empty:
                # Clean orders data columns
                self.orders_data.columns = self.orders_data.columns.str.strip().str.replace('"', '')
                
                # Clean data values
                for col in self.orders_data.columns:
                    if self.orders_data[col].dtype == 'object':
                        self.orders_data[col] = self.orders_data[col].astype(str).str.strip().str.replace('"', '')
                
                # Process BUY and SELL orders
                processed_holdings = self._process_buy_sell_orders(merged)
                if processed_holdings is not None:
                    merged = processed_holdings
                    logger.info("Applied BUY/SELL order adjustments to holdings")
            
            # Add company information from stock mapping
            merged['Company_Name'] = merged['Instrument'].map(
                lambda x: self.stock_mapping.get(x, {}).get('company_name', 'Unknown')
            )
            merged['Industry'] = merged['Instrument'].map(
                lambda x: self.stock_mapping.get(x, {}).get('industry', 'Unknown')
            )
            merged['Series'] = merged['Instrument'].map(
                lambda x: self.stock_mapping.get(x, {}).get('series', 'EQ')
            )
            merged['ISIN'] = merged['Instrument'].map(
                lambda x: self.stock_mapping.get(x, {}).get('isin', 'Unknown')
            )
            
            # Calculate additional metrics
            merged['Portfolio_Weight'] = (merged['Cur. val'] / merged['Cur. val'].sum() * 100).round(2)
            merged['Profit_Margin'] = ((merged['P&L'] / merged['Invested']) * 100).round(2)
            merged['Position_Size'] = merged['Cur. val'].round(2)
            
            # Add order statistics if orders data exists
            if self.orders_data is not None and not self.orders_data.empty:
                # Calculate order statistics for each stock (today's orders only)
                order_stats = self._calculate_order_statistics()
                if order_stats is not None:
                    merged = merged.merge(order_stats, on='Instrument', how='left')
                    # Fill NaN values for stocks without today's orders
                    order_columns = ['Today_Buy_Qty', 'Today_Sell_Qty', 'Net_Today_Orders', 'Avg_Order_Price']
                    for col in order_columns:
                        if col in merged.columns:
                            merged[col] = merged[col].fillna(0)
            else:
                merged['Today_Buy_Qty'] = 0
                merged['Today_Sell_Qty'] = 0
                merged['Net_Today_Orders'] = 0
                merged['Avg_Order_Price'] = 0
            
            # Reorder columns for better readability
            column_order = [
                'Instrument', 'Company_Name', 'Industry', 'Series', 'ISIN',
                'Qty.', 'Avg. cost', 'LTP', 'Invested', 'Cur. val', 'P&L',
                'Portfolio_Weight', 'Profit_Margin', 'Net chg.', 'Day chg.',
                'Today_Buy_Qty', 'Today_Sell_Qty', 'Net_Today_Orders', 'Avg_Order_Price', 'Position_Size'
            ]
            
            # Keep only existing columns
            available_columns = [col for col in column_order if col in merged.columns]
            merged = merged[available_columns]
            
            # Remove stocks with zero or negative quantity
            initial_count = len(merged)
            merged = merged[merged['Qty.'] > 0]
            removed_count = initial_count - len(merged)
            
            if removed_count > 0:
                logger.info(f"Removed {removed_count} stocks with zero/negative quantity")
                print(f"🧹 Removed {removed_count} stocks with zero quantity from portfolio")
            
            self.merged_data = merged
            logger.info("Successfully merged holdings and orders data")
            return True
            
        except Exception as e:
            logger.error(f"Error merging data: {e}")
            return False
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report"""
        if self.merged_data is None:
            logger.error("No merged data available")
            return None
        
        try:
            summary = {
                'portfolio_overview': {
                    'total_stocks': len(self.merged_data),
                    'total_invested': self.merged_data['Invested'].sum(),
                    'current_value': self.merged_data['Cur. val'].sum(),
                    'total_pnl': self.merged_data['P&L'].sum(),
                    'overall_return_pct': (self.merged_data['P&L'].sum() / 
                                         self.merged_data['Invested'].sum() * 100)
                },
                'top_performers': {
                    'by_absolute_gain': self.merged_data.nlargest(5, 'P&L')[
                        ['Instrument', 'Company_Name', 'P&L', 'Profit_Margin']
                    ].to_dict('records'),
                    'by_percentage_gain': self.merged_data.nlargest(5, 'Profit_Margin')[
                        ['Instrument', 'Company_Name', 'P&L', 'Profit_Margin']
                    ].to_dict('records')
                },
                'sector_allocation': self.merged_data.groupby('Industry').agg({
                    'Cur. val': 'sum',
                    'Portfolio_Weight': 'sum',
                    'P&L': 'sum'
                }).sort_values('Cur. val', ascending=False).to_dict(),
                'risk_analysis': {
                    'high_concentration_stocks': self.merged_data[
                        self.merged_data['Portfolio_Weight'] > 5
                    ][['Instrument', 'Company_Name', 'Portfolio_Weight']].to_dict('records'),
                    'loss_making_stocks': self.merged_data[
                        self.merged_data['P&L'] < 0
                    ][['Instrument', 'Company_Name', 'P&L', 'Profit_Margin']].to_dict('records')
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None
    
    def save_merged_data(self, output_file='merged_portfolio_data.xlsx'):
        """Save merged data to Excel file with multiple sheets"""
        if self.merged_data is None:
            logger.error("No merged data to save")
            return False
        
        try:
            # Create output directory if it doesn't exist
            os.makedirs('reports', exist_ok=True)
            
            output_path = f'reports/{output_file}'
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Main merged data
                self.merged_data.to_excel(writer, sheet_name='Merged_Portfolio', index=False)
                
                # Holdings only
                if self.holdings_data is not None:
                    self.holdings_data.to_excel(writer, sheet_name='Original_Holdings', index=False)
                
                # Orders only
                if self.orders_data is not None and not self.orders_data.empty:
                    self.orders_data.to_excel(writer, sheet_name='Orders_Data', index=False)
                
                # Summary statistics
                summary_stats = pd.DataFrame([{
                    'Metric': 'Total Stocks',
                    'Value': len(self.merged_data)
                }, {
                    'Metric': 'Total Invested (₹)',
                    'Value': self.merged_data['Invested'].sum()
                }, {
                    'Metric': 'Current Value (₹)',
                    'Value': self.merged_data['Cur. val'].sum()
                }, {
                    'Metric': 'Total P&L (₹)',
                    'Value': self.merged_data['P&L'].sum()
                }, {
                    'Metric': 'Overall Return (%)',
                    'Value': (self.merged_data['P&L'].sum() / self.merged_data['Invested'].sum() * 100)
                }])
                
                summary_stats.to_excel(writer, sheet_name='Summary_Stats', index=False)
                
                # Sector wise breakdown
                sector_summary = self.merged_data.groupby('Industry').agg({
                    'Cur. val': 'sum',
                    'Invested': 'sum',
                    'P&L': 'sum',
                    'Portfolio_Weight': 'sum'
                }).round(2)
                sector_summary.to_excel(writer, sheet_name='Sector_Breakdown')
            
            logger.info(f"Merged data saved to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving merged data: {e}")
            return False
    
    def print_summary(self):
        """Print a quick summary to console"""
        if self.merged_data is None:
            print("No merged data available")
            return
        
        print("\n" + "="*80)
        print("PORTFOLIO SUMMARY - HOLDINGS & ORDERS MERGED")
        print("="*80)
        
        total_invested = self.merged_data['Invested'].sum()
        current_value = self.merged_data['Cur. val'].sum()
        total_pnl = self.merged_data['P&L'].sum()
        
        print(f"Total Stocks: {len(self.merged_data)}")
        print(f"Total Invested: ₹{total_invested:,.2f}")
        print(f"Current Value: ₹{current_value:,.2f}")
        print(f"Total P&L: ₹{total_pnl:,.2f}")
        print(f"Overall Return: {(total_pnl/total_invested*100):+.2f}%")
        
        print(f"\nTop 5 Holdings by Value:")
        top_holdings = self.merged_data.nlargest(5, 'Cur. val')
        for _, stock in top_holdings.iterrows():
            print(f"  {stock['Instrument']}: ₹{stock['Cur. val']:,.0f} ({stock['Portfolio_Weight']:.1f}%)")
        
        print(f"\nTop 3 Gainers:")
        top_gainers = self.merged_data.nlargest(3, 'P&L')
        for _, stock in top_gainers.iterrows():
            print(f"  {stock['Instrument']}: ₹{stock['P&L']:+,.0f} ({stock['Profit_Margin']:+.1f}%)")
        
        if self.merged_data['P&L'].min() < 0:
            print(f"\nTop 3 Losers:")
            top_losers = self.merged_data.nsmallest(3, 'P&L')
            for _, stock in top_losers.iterrows():
                print(f"  {stock['Instrument']}: ₹{stock['P&L']:+,.0f} ({stock['Profit_Margin']:+.1f}%)")
        
        print("="*80)


def main():
    """Main execution function"""
    print("Holdings and Orders Merger Tool")
    print("="*40)
    
    merger = HoldingsOrdersMerger()
    
    # Load holdings data
    holdings_file = 'Holding/holdings (18).csv'
    if not os.path.exists(holdings_file):
        print(f"Holdings file not found: {holdings_file}")
        return
    
    if not merger.load_holdings_data(holdings_file):
        print("Failed to load holdings data")
        return
    
    # Load orders data (optional)
    orders_file = 'Holding/orders (8).csv'  # Updated to use the actual orders file
    merger.load_orders_data(orders_file)
    
    # Merge data
    if not merger.merge_data():
        print("Failed to merge data")
        return
    
    # Print summary
    merger.print_summary()
    
    # Save merged data
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'merged_portfolio_{timestamp}.xlsx'
    
    if merger.save_merged_data(output_file):
        print(f"\nMerged data saved to: reports/{output_file}")
    
    # Generate detailed report
    summary = merger.generate_summary_report()
    if summary:
        # Save JSON summary
        with open(f'reports/portfolio_summary_{timestamp}.json', 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"Detailed summary saved to: reports/portfolio_summary_{timestamp}.json")


if __name__ == "__main__":
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    
    main()