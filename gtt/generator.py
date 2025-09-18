"""
GTT Order Generator
==================

Main class for generating GTT (Good Till Triggered) orders from portfolio holdings.
Creates two-leg GTT orders with support/resistance levels for automated trading.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import os
from pathlib import Path

from .config import GTTConfig
from .analyzer import GTTAnalyzer

class GTTOrderGenerator:
    """Generates GTT orders for portfolio holdings"""
    
    def __init__(self, holdings_data: pd.DataFrame, enhanced_report_data: pd.DataFrame, 
                 config: GTTConfig = None, buy_recommendations: List[Dict] = None,
                 consolidation_sells: List[Dict] = None, capital_rotation: List[Dict] = None,
                 profit_booking: List[Dict] = None):
        """Initialize GTT generator with all trading opportunities"""
        self.holdings = holdings_data.copy()
        self.buy_recommendations = buy_recommendations or []
        self.consolidation_sells = consolidation_sells or []
        self.capital_rotation = capital_rotation or []
        self.profit_booking = profit_booking or []
        self.config = config or GTTConfig()
        self.analyzer = GTTAnalyzer(enhanced_report_data)
        self.gtt_orders = []
        
        # Ensure required columns exist in holdings
        self._validate_holdings_data()
        
        # Process all trading opportunities
        self._process_buy_recommendations()
        self._process_consolidation_sells()
        self._process_capital_rotation()
        self._process_profit_booking()
    
    def _validate_holdings_data(self):
        """Validate and standardize holdings data columns"""
        required_columns = ['symbol', 'quantity', 'current_price']
        
        # Initialize flags for existing holdings (they are NOT buy recommendations)
        if 'is_buy_recommendation' not in self.holdings.columns:
            self.holdings['is_buy_recommendation'] = False
        if 'is_consolidation_sell' not in self.holdings.columns:
            self.holdings['is_consolidation_sell'] = False
        if 'is_rotation_sell' not in self.holdings.columns:
            self.holdings['is_rotation_sell'] = False
        if 'is_rotation_buy' not in self.holdings.columns:
            self.holdings['is_rotation_buy'] = False
        if 'is_profit_booking' not in self.holdings.columns:
            self.holdings['is_profit_booking'] = False
        if 'is_strengthen_buy' not in self.holdings.columns:
            self.holdings['is_strengthen_buy'] = False
        if 'strengthen_amount' not in self.holdings.columns:
            self.holdings['strengthen_amount'] = 0
        
        # Try to map common column variations
        column_mapping = {
            'Symbol': 'symbol',
            'SYMBOL': 'symbol', 
            'Stock': 'symbol',
            'Instrument': 'symbol',  # Added for holdings CSV format
            'Quantity': 'quantity',
            'QUANTITY': 'quantity',
            'Qty': 'quantity',
            'Qty.': 'quantity',      # Added for holdings CSV format
            'Current_Price': 'current_price',
            'Current Price': 'current_price',
            'Price': 'current_price',
            'LTP': 'current_price'
        }
        
        # Apply column mapping
        for old_name, new_name in column_mapping.items():
            if old_name in self.holdings.columns:
                self.holdings = self.holdings.rename(columns={old_name: new_name})
        
        # Check if we have required columns
        missing_columns = [col for col in required_columns if col not in self.holdings.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns in holdings data: {missing_columns}")
        
        # Clean symbol names
        self.holdings['symbol'] = self.holdings['symbol'].astype(str).str.strip().str.upper()
        
        # Ensure numeric columns
        self.holdings['quantity'] = pd.to_numeric(self.holdings['quantity'], errors='coerce')
        self.holdings['current_price'] = pd.to_numeric(self.holdings['current_price'], errors='coerce')
        
        # Remove invalid rows
        self.holdings = self.holdings.dropna(subset=['symbol', 'quantity', 'current_price'])
        self.holdings = self.holdings[
            (self.holdings['quantity'] > 0) & 
            (self.holdings['current_price'] > 0)
        ]
    
    def _process_buy_recommendations(self):
        """Convert buy recommendations into potential GTT buy orders"""
        if not self.buy_recommendations:
            return
            
        print(f"📈 Processing {len(self.buy_recommendations)} buy recommendations for GTT...")
        
        # Convert buy recommendations to holdings format for GTT processing
        buy_holdings = []
        for buy_rec in self.buy_recommendations:
            # Extract symbol and amount info from buy recommendation
            symbol = buy_rec.get('symbol', buy_rec.get('Stock', ''))
            amount = buy_rec.get('amount', buy_rec.get('Investment_Amount', buy_rec.get('suggested_amount', 0)))
            current_price = buy_rec.get('current_price', buy_rec.get('Current_Price', 0))
            
            if symbol and amount > 0 and current_price > 0:
                # Calculate quantity that can be bought
                quantity = int(amount / current_price)
                if quantity > 0:
                    buy_holdings.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'current_price': current_price,
                        'is_buy_recommendation': True  # Flag to identify buy recs
                    })
        
        if buy_holdings:
            # Add buy recommendations to holdings for GTT processing
            buy_df = pd.DataFrame(buy_holdings)
            self.holdings = pd.concat([self.holdings, buy_df], ignore_index=True)
            print(f"✅ Added {len(buy_holdings)} buy recommendations to GTT processing")
    
    def _process_consolidation_sells(self):
        """Convert consolidation sell recommendations into GTT sell orders"""
        if not self.consolidation_sells:
            return
            
        print(f"🗂️ Processing {len(self.consolidation_sells)} consolidation sell recommendations...")
        
        # Mark consolidation stocks for priority selling in existing holdings
        consolidation_symbols = []
        for sell_rec in self.consolidation_sells:
            symbol = sell_rec.get('symbol', sell_rec.get('Instrument', sell_rec.get('Stock', '')))
            if symbol:
                consolidation_symbols.append(symbol)
        
        # Flag existing holdings that are marked for consolidation
        self.holdings['is_consolidation_sell'] = self.holdings['symbol'].isin(consolidation_symbols)
        consolidation_count = self.holdings['is_consolidation_sell'].sum()
        
        if consolidation_count > 0:
            print(f"✅ Flagged {consolidation_count} holdings for consolidation selling")
    
    def _process_capital_rotation(self):
        """Convert capital rotation plan into GTT trading pairs"""
        if not self.capital_rotation:
            return
            
        print(f"🔄 Processing {len(self.capital_rotation)} capital rotation strategies...")
        
        # Extract rotation pairs (sell X, buy Y) and strengthening targets
        rotation_holdings = []
        for rotation in self.capital_rotation:
            # Check if this is a "strengthen" operation or traditional rotation
            action = rotation.get('action', rotation.get('type', ''))
            symbol = rotation.get('symbol', rotation.get('stock', ''))
            amount = rotation.get('amount', rotation.get('additional_amount', 0))
            
            if action and 'strengthen' in action.lower() and symbol:
                # This is a "strengthen existing holding" operation - add more shares
                if symbol in self.holdings['symbol'].values:
                    # Mark existing holding for additional buying (strengthening)
                    self.holdings.loc[self.holdings['symbol'] == symbol, 'is_strengthen_buy'] = True
                    self.holdings.loc[self.holdings['symbol'] == symbol, 'strengthen_amount'] = amount
                else:
                    # Add as new rotation buy target
                    current_price = rotation.get('current_price', 100)  # Default if not provided
                    quantity = max(1, int(amount / current_price)) if amount > 0 and current_price > 0 else 50
                    rotation_holdings.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'current_price': current_price,
                        'is_strengthen_buy': True,
                        'strengthen_amount': amount
                    })
            else:
                # Traditional rotation logic (sell X, buy Y)
                source_stock = rotation.get('Source_Stock', rotation.get('source_stock', ''))
                target_stocks = rotation.get('Target_Stocks', rotation.get('target_stocks', ''))
                
                if source_stock:
                    # Mark source for selling
                    self.holdings.loc[self.holdings['symbol'] == source_stock, 'is_rotation_sell'] = True
                
                # Target stocks to buy (parse comma-separated list)
                if target_stocks:
                    if isinstance(target_stocks, str):
                        target_list = [s.strip() for s in target_stocks.split(',')]
                    else:
                        target_list = [target_stocks] if target_stocks else []
                    
                    for target_symbol in target_list:
                        if target_symbol and target_symbol not in self.holdings['symbol'].values:
                            # Add rotation target as potential buy
                            rotation_holdings.append({
                                'symbol': target_symbol,
                                'quantity': 100,  # Default quantity for rotation
                                'current_price': 100,  # Will be updated from market data
                                'is_rotation_buy': True
                            })
        
        if rotation_holdings:
            # Add rotation targets to holdings for GTT processing
            rotation_df = pd.DataFrame(rotation_holdings)
            self.holdings = pd.concat([self.holdings, rotation_df], ignore_index=True)
            print(f"✅ Added {len(rotation_holdings)} rotation targets to GTT processing")
        
        # Count strengthening operations
        strengthen_count = self.holdings.get('is_strengthen_buy', pd.Series([])).sum()
        if strengthen_count > 0:
            print(f"✅ Flagged {strengthen_count} holdings for strengthening (additional buying)")
    
    def _process_profit_booking(self):
        """Mark stocks for profit booking with specific price targets"""
        if not self.profit_booking:
            return
            
        print(f"💰 Processing {len(self.profit_booking)} profit booking recommendations...")
        
        # Mark profit booking stocks with their target prices
        for profit_rec in self.profit_booking:
            symbol = profit_rec.get('instrument', profit_rec.get('symbol', ''))
            target_price = profit_rec.get('target_price', 0)
            
            if symbol and target_price > 0:
                # Find matching holding and add profit booking info
                mask = self.holdings['symbol'] == symbol
                if mask.any():
                    self.holdings.loc[mask, 'is_profit_booking'] = True
                    self.holdings.loc[mask, 'profit_target_price'] = target_price
        
        profit_count = self.holdings.get('is_profit_booking', pd.Series([])).sum()
        if profit_count > 0:
            print(f"✅ Flagged {profit_count} holdings for profit booking with price targets")
    
    def generate_gtt_orders(self) -> pd.DataFrame:
        """Generate GTT orders for all holdings"""
        
        print("🎯 GENERATING GTT ORDERS")
        print("=" * 50)
        
        gtt_orders = []
        
        for index, holding in self.holdings.iterrows():
            try:
                symbol = holding['symbol']
                quantity = int(holding['quantity'])
                current_price = float(holding['current_price'])
                
                print(f"\n📊 Processing {symbol}: {quantity} shares @ ₹{current_price:.2f}")
                
                # Get technical levels
                levels = self.analyzer.calculate_technical_levels(symbol, current_price)
                
                # Get recommendation context
                context = self.analyzer.get_stock_recommendation_context(symbol)
                
                # Generate orders based on recommendation
                orders = self._create_orders_for_holding(
                    symbol, quantity, current_price, levels, context, holding
                )
                
                gtt_orders.extend(orders)
                
            except Exception as e:
                print(f"❌ Error processing {symbol}: {e}")
                continue
        
        # Convert to DataFrame
        self.gtt_orders = pd.DataFrame(gtt_orders)
        
        if not self.gtt_orders.empty:
            self._validate_and_clean_orders()
        
        print(f"\n✅ Generated {len(self.gtt_orders)} GTT orders")
        return self.gtt_orders
    
    def _create_orders_for_holding(self, symbol: str, quantity: int, current_price: float, 
                                 levels: Dict, context: Dict, holding: pd.Series = None) -> List[Dict]:
        """Create GTT orders for a single holding or recommendation"""
        
        orders = []
        is_buy_rec = holding is not None and holding.get('is_buy_recommendation', False)
        is_consolidation_sell = holding is not None and holding.get('is_consolidation_sell', False)
        is_rotation_sell = holding is not None and holding.get('is_rotation_sell', False)
        is_rotation_buy = holding is not None and holding.get('is_rotation_buy', False)
        is_profit_booking = holding is not None and holding.get('is_profit_booking', False)
        is_strengthen_buy = holding is not None and holding.get('is_strengthen_buy', False)
        profit_target_price = holding.get('profit_target_price', 0) if holding is not None else 0
        strengthen_amount = holding.get('strengthen_amount', 0) if holding is not None else 0
        
        # Validate levels
        support = levels['support']
        resistance = levels['resistance']
        
        if not self.analyzer.validate_trigger_levels(support, resistance, current_price):
            print(f"⚠️ Invalid trigger levels for {symbol}, using defaults")
            support = current_price * 0.95
            resistance = current_price * 1.08
        
        # Determine order type based on purpose
        if is_buy_rec:
            # For buy recommendations, create ONLY single-leg BUY orders
            buy_order = {
                'type': 'single',  # Single-leg GTT for new purchases
                'status': self.config.default_status,
                'tradingsymbol': symbol,
                'exchange': self.config.default_exchange,
                'trigger_values': f"{current_price:.2f}",  # Single trigger price
                'transaction_type': 'BUY',
                'quantity': str(quantity),  # Single quantity, not split
                'last_price': current_price,
                'support_level': current_price,
                'resistance_level': current_price,
                'recommendation': context['recommendation'],
                'risk_category': context['risk'],
                'notes': f"Buy recommendation GTT - {context['context']}"
            }
            orders.append(buy_order)
            
        elif is_profit_booking and profit_target_price > 0:
            # For profit booking - sell at specific target prices with tight ranges
            sell_order = {
                'type': 'two-leg',
                'status': self.config.default_status,
                'tradingsymbol': symbol,
                'exchange': self.config.default_exchange,
                'trigger_values': f"{profit_target_price * 0.995:.2f}/{profit_target_price:.2f}",  # Very tight range
                'transaction_type': 'SELL',
                'quantity': f"{int(quantity * 0.5)}/{int(quantity * 0.3)}",  # Partial selling (50%+30%)
                'last_price': current_price,
                'support_level': profit_target_price * 0.995,
                'resistance_level': profit_target_price,
                'recommendation': 'PROFIT_BOOKING',
                'risk_category': 'PROFIT_PROTECTION',
                'notes': f"Profit booking at target ₹{profit_target_price:.2f}"
            }
            orders.append(sell_order)
            
        elif is_consolidation_sell:
            # For consolidation sells - aggressive sell orders to exit position
            sell_order = {
                'type': self.config.default_type,
                'status': self.config.default_status,
                'tradingsymbol': symbol,
                'exchange': self.config.default_exchange,
                'trigger_values': f"{current_price * 0.99:.2f}/{current_price * 1.02:.2f}",  # Tight range for quick exit
                'transaction_type': 'SELL',
                'quantity': f"{quantity}/{quantity}",  # Sell entire position
                'last_price': current_price,
                'support_level': current_price * 0.99,
                'resistance_level': current_price * 1.02,
                'recommendation': 'CONSOLIDATION_SELL',
                'risk_category': 'EXIT',
                'notes': f"Portfolio consolidation - Exit complete position"
            }
            orders.append(sell_order)
            
        elif is_rotation_sell:
            # For rotation sells - strategic exit for reinvestment
            sell_order = {
                'type': self.config.default_type,
                'status': self.config.default_status,
                'tradingsymbol': symbol,
                'exchange': self.config.default_exchange,
                'trigger_values': f"{resistance * 0.98:.2f}/{resistance:.2f}",  # Sell at good levels
                'transaction_type': 'SELL',
                'quantity': f"{quantity}/{quantity}",  # Sell entire position
                'last_price': current_price,
                'support_level': resistance * 0.98,
                'resistance_level': resistance,
                'recommendation': 'ROTATION_SELL',
                'risk_category': context['risk'],
                'notes': f"Capital rotation - Exit for strategic reallocation"
            }
            orders.append(sell_order)
            
        elif is_strengthen_buy:
            # For strengthen operations - additional buying of existing positions
            if strengthen_amount > 0:
                # Calculate quantity based on strengthen amount
                additional_qty = max(1, int(strengthen_amount / current_price))
            else:
                # Default additional quantity (20% of current holding)
                additional_qty = max(1, int(quantity * 0.2))
            
            strengthen_order = {
                'type': 'single',  # Single-leg BUY for strengthening
                'status': self.config.default_status,
                'tradingsymbol': symbol,
                'exchange': self.config.default_exchange,
                'trigger_values': f"{current_price * 0.98:.2f}",  # Buy on small dip
                'transaction_type': 'BUY',
                'quantity': str(additional_qty),
                'last_price': current_price,
                'support_level': current_price * 0.98,
                'resistance_level': current_price,
                'recommendation': 'STRENGTHEN_POSITION',
                'risk_category': context['risk'],
                'notes': f"Strengthen existing position - Add ₹{strengthen_amount:.0f} (approx {additional_qty} shares)"
            }
            orders.append(strengthen_order)

        elif is_rotation_buy:
            # For rotation buy targets - strategic entry
            buy_qty_1, buy_qty_2 = self.config.calculate_buy_quantities()
            
            buy_order = {
                'type': self.config.default_type,
                'status': self.config.default_status,
                'tradingsymbol': symbol,
                'exchange': self.config.default_exchange,
                'trigger_values': f"{current_price * 0.96:.2f}/{current_price * 0.93:.2f}",
                'transaction_type': 'BUY',
                'quantity': f"{buy_qty_1 * 2}/{buy_qty_2 * 2}",  # Larger quantities for rotation
                'last_price': current_price,
                'support_level': current_price * 0.96,
                'resistance_level': current_price * 0.93,
                'recommendation': 'ROTATION_BUY',
                'risk_category': context['risk'],
                'notes': f"Capital rotation target - Strategic entry"
            }
            orders.append(buy_order)
            
        else:
            # For existing holdings, create ONLY sell orders (two-leg: stop-loss/target)
            sell_qty_1, sell_qty_2 = self.config.calculate_sell_quantities(quantity)
            
            if sell_qty_1 > 0:
                sell_order = {
                    'type': 'two-leg',  # Two-leg for existing holdings (stop-loss + target)
                    'status': self.config.default_status,
                    'tradingsymbol': symbol,
                    'exchange': self.config.default_exchange,
                    'trigger_values': f"{support:.2f}/{resistance:.2f}",  # stop-loss/target
                    'transaction_type': 'SELL',
                    'quantity': f"{sell_qty_1}/{sell_qty_2 if sell_qty_2 > 0 else sell_qty_1}",
                    'last_price': current_price,
                    'support_level': support,
                    'resistance_level': resistance,
                    'recommendation': context['recommendation'],
                    'risk_category': context['risk'],
                    'notes': f"Holdings management - Stop loss: ₹{support:.2f}, Target: ₹{resistance:.2f}"
                }
                orders.append(sell_order)
            
            # NOTE: No BUY orders for existing holdings - only SELL orders for risk management
        
        return orders
    
    def _validate_and_clean_orders(self):
        """Validate and clean generated GTT orders"""
        
        # Remove orders with invalid data
        self.gtt_orders = self.gtt_orders.dropna(subset=['tradingsymbol', 'trigger_values', 'quantity'])
        
        # Sort by symbol
        self.gtt_orders = self.gtt_orders.sort_values('tradingsymbol').reset_index(drop=True)
        
        # Add order IDs
        self.gtt_orders['order_id'] = range(1, len(self.gtt_orders) + 1)
    
    def export_to_excel(self, output_path: str = None) -> str:
        """Export GTT orders to Excel format suitable for broker upload"""
        
        if self.gtt_orders.empty:
            raise ValueError("No GTT orders to export. Generate orders first.")
        
        # Create output path
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"reports/GTT_Orders_{timestamp}.xlsx"
        
        # Ensure directory exists
        dir_path = os.path.dirname(output_path)
        if dir_path:  # Only create directory if path is not empty
            os.makedirs(dir_path, exist_ok=True)
        
        # Prepare data for export (broker-compatible format)
        export_data = self.gtt_orders[[
            'type', 'status', 'tradingsymbol', 'exchange', 
            'trigger_values', 'transaction_type', 'quantity', 'last_price'
        ]].copy()
        
        # Create Excel file with multiple sheets
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # Main GTT Orders sheet
            export_data.to_excel(writer, sheet_name='GTT_Orders', index=False)
            
            # Detailed analysis sheet
            detailed_data = self.gtt_orders.copy()
            detailed_data.to_excel(writer, sheet_name='Detailed_Analysis', index=False)
            
            # Summary statistics
            summary_stats = self._generate_summary_stats()
            summary_stats.to_excel(writer, sheet_name='Summary', index=False)
        
        print(f"\n📁 GTT orders exported to: {output_path}")
        return output_path
    
    def _generate_summary_stats(self) -> pd.DataFrame:
        """Generate summary statistics for GTT orders"""
        
        stats = []
        
        # Overall statistics
        stats.append(['Total Orders', len(self.gtt_orders)])
        stats.append(['Buy Orders', len(self.gtt_orders[self.gtt_orders['transaction_type'] == 'BUY'])])
        stats.append(['Sell Orders', len(self.gtt_orders[self.gtt_orders['transaction_type'] == 'SELL'])])
        stats.append(['Unique Stocks', self.gtt_orders['tradingsymbol'].nunique()])
        
        # Risk distribution
        risk_dist = self.gtt_orders['risk_category'].value_counts()
        for risk, count in risk_dist.items():
            stats.append([f'{risk} Risk Stocks', count])
        
        # Recommendation distribution  
        rec_dist = self.gtt_orders['recommendation'].value_counts()
        for rec, count in rec_dist.items():
            stats.append([f'{rec} Recommendations', count])
        
        return pd.DataFrame(stats, columns=['Metric', 'Value'])
    
    def get_orders_summary(self) -> Dict:
        """Get summary of generated GTT orders"""
        
        if self.gtt_orders.empty:
            return {'total_orders': 0, 'message': 'No GTT orders generated'}
        
        summary = {
            'total_orders': len(self.gtt_orders),
            'buy_orders': len(self.gtt_orders[self.gtt_orders['transaction_type'] == 'BUY']),
            'sell_orders': len(self.gtt_orders[self.gtt_orders['transaction_type'] == 'SELL']),
            'unique_stocks': self.gtt_orders['tradingsymbol'].nunique(),
            'risk_distribution': self.gtt_orders['risk_category'].value_counts().to_dict(),
            'recommendation_distribution': self.gtt_orders['recommendation'].value_counts().to_dict()
        }
        
        return summary
    
    def print_orders_preview(self, max_rows: int = 10):
        """Print a preview of generated GTT orders"""
        
        if self.gtt_orders.empty:
            print("❌ No GTT orders to display")
            return
        
        print(f"\n🎯 GTT ORDERS PREVIEW (showing first {max_rows} orders)")
        print("=" * 80)
        
        # Show main columns
        preview_cols = ['tradingsymbol', 'transaction_type', 'trigger_values', 'quantity', 'last_price']
        preview_data = self.gtt_orders[preview_cols].head(max_rows)
        
        print(preview_data.to_string(index=False))
        
        if len(self.gtt_orders) > max_rows:
            print(f"\n... and {len(self.gtt_orders) - max_rows} more orders")
        
        # Show summary
        summary = self.get_orders_summary()
        print(f"\n📊 SUMMARY:")
        print(f"Total Orders: {summary['total_orders']}")
        print(f"Buy Orders: {summary['buy_orders']} | Sell Orders: {summary['sell_orders']}")
        print(f"Unique Stocks: {summary['unique_stocks']}")