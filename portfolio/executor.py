"""
Portfolio Execution Engine
Handles actual execution of buy/sell recommendations
"""

import pandas as pd
import os
from datetime import datetime
import logging


class PortfolioExecutor:
    """Executes portfolio recommendations by updating holdings"""
    
    def __init__(self, analyzer, insights):
        self.analyzer = analyzer
        self.insights = insights
        self.logger = logging.getLogger(__name__)
        
    def execute_buy_recommendations(self, execute_all=False, selected_symbols=None):
        """
        Execute buy recommendations by adding them to the portfolio
        
        Args:
            execute_all: Execute all buy recommendations
            selected_symbols: List of specific symbols to execute
            
        Returns:
            dict: Execution results
        """
        try:
            # Get buy recommendations
            buy_analysis = self.insights.analyze_buy_recommendations()
            recommendations = buy_analysis.get('top_buy_recommendations', [])
            
            if not recommendations:
                return {'success': False, 'message': 'No buy recommendations available'}
            
            # Filter recommendations based on selection
            if selected_symbols:
                recommendations = [r for r in recommendations if r['symbol'] in selected_symbols]
            elif not execute_all:
                # By default, execute top 5 recommendations
                recommendations = recommendations[:5]
            
            if not recommendations:
                return {'success': False, 'message': 'No matching recommendations found'}
            
            # Load current holdings
            holdings_data = self.analyzer.holdings_df.copy()
            
            # Get current prices from Enhanced Stock Report
            enhanced_data = self.analyzer.enhanced_report_df
            
            executed_buys = []
            total_investment = 0
            
            for rec in recommendations:
                symbol = rec['symbol']
                suggested_amount = rec.get('suggested_amount', rec.get('min_investment', 20000))
                
                # Get current price from Enhanced Stock Report
                current_price = self._get_current_price(symbol, enhanced_data)
                if not current_price:
                    continue
                
                # Calculate quantity to buy
                quantity = int(suggested_amount / current_price)
                actual_investment = quantity * current_price
                
                # Create new holding entry
                new_holding = {
                    'Instrument': symbol,
                    'Qty.': quantity,
                    'Avg. cost': current_price,
                    'LTP': current_price,
                    'Cur. val': actual_investment,
                    'P&L': 0.0,
                    'Net chg': 0.0,
                    'Day chg': 0.0
                }
                
                # Add to holdings
                holdings_data = pd.concat([holdings_data, pd.DataFrame([new_holding])], ignore_index=True)
                
                executed_buys.append({
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': current_price,
                    'investment': actual_investment,
                    'rationale': rec.get('rationale', 'Buy recommendation')
                })
                
                total_investment += actual_investment
                
                self.logger.info(f"Executed BUY: {symbol} - {quantity} shares @ ₹{current_price:.2f}")
            
            if executed_buys:
                # Save updated holdings
                success = self._save_updated_holdings(holdings_data)
                
                if success:
                    return {
                        'success': True,
                        'executed_buys': executed_buys,
                        'total_investment': total_investment,
                        'count': len(executed_buys),
                        'message': f'Successfully executed {len(executed_buys)} buy orders'
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Failed to save updated holdings'
                    }
            else:
                return {
                    'success': False,
                    'message': 'No buy orders could be executed'
                }
                
        except Exception as e:
            self.logger.error(f"Error executing buy recommendations: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def execute_sell_recommendations(self, execute_all=False, selected_symbols=None):
        """
        Execute sell recommendations by removing/reducing positions
        
        Args:
            execute_all: Execute all sell recommendations
            selected_symbols: List of specific symbols to execute
            
        Returns:
            dict: Execution results
        """
        try:
            # Get sell recommendations (both enhanced sells and consolidation sells)
            enhanced_sells = self.insights.get_enhanced_sell_recommendations()
            consolidation_analysis = self.analyzer.consolidation_engine.analyze_consolidation_opportunities()
            
            all_sells = []
            
            # Add enhanced sell recommendations
            immediate_sells = enhanced_sells.get('immediate_sells', [])
            profit_booking = enhanced_sells.get('profit_booking', [])
            
            all_sells.extend(immediate_sells)
            all_sells.extend(profit_booking)
            
            # Add consolidation sell recommendations
            if consolidation_analysis.get('action_needed', False):
                removal_candidates = consolidation_analysis.get('removal_candidates', [])
                for candidate in removal_candidates:
                    all_sells.append({
                        'symbol': candidate.get('symbol', ''),
                        'action': 'SELL',
                        'type': 'CONSOLIDATION',
                        'target_price': candidate.get('sell_signal', {}).get('target_price', 0),
                        'rationale': 'Portfolio consolidation'
                    })
            
            if not all_sells:
                return {'success': False, 'message': 'No sell recommendations available'}
            
            # Filter sells based on selection
            if selected_symbols:
                all_sells = [s for s in all_sells if s['symbol'] in selected_symbols]
            elif not execute_all:
                # By default, execute consolidation sells only
                all_sells = [s for s in all_sells if s.get('type') == 'CONSOLIDATION']
            
            if not all_sells:
                return {'success': False, 'message': 'No matching sell recommendations found'}
            
            # Load current holdings
            holdings_data = self.analyzer.holdings_df.copy()
            
            executed_sells = []
            total_proceeds = 0
            
            for sell in all_sells:
                symbol = sell['symbol']
                
                # Find the holding
                holding_row = holdings_data[holdings_data['Instrument'] == symbol]
                if holding_row.empty:
                    continue
                
                # Get holding details
                current_qty = holding_row.iloc[0]['Qty.']
                current_value = holding_row.iloc[0]['Cur. val']
                
                # For consolidation, sell entire position
                if sell.get('type') == 'CONSOLIDATION':
                    sell_qty = current_qty
                else:
                    # For other sells, use specified percentage or default to 100%
                    sell_percentage = sell.get('percentage', 100) / 100
                    sell_qty = int(current_qty * sell_percentage)
                
                if sell_qty > 0:
                    # Calculate proceeds
                    proceed_amount = (current_value / current_qty) * sell_qty
                    
                    executed_sells.append({
                        'symbol': symbol,
                        'quantity': sell_qty,
                        'proceeds': proceed_amount,
                        'type': sell.get('type', 'STANDARD'),
                        'rationale': sell.get('rationale', 'Sell recommendation')
                    })
                    
                    total_proceeds += proceed_amount
                    
                    # Remove or reduce the holding
                    if sell_qty >= current_qty:
                        # Remove entire holding
                        holdings_data = holdings_data[holdings_data['Instrument'] != symbol]
                    else:
                        # Reduce quantity
                        new_qty = current_qty - sell_qty
                        new_value = (current_value / current_qty) * new_qty
                        holdings_data.loc[holdings_data['Instrument'] == symbol, 'Qty.'] = new_qty
                        holdings_data.loc[holdings_data['Instrument'] == symbol, 'Cur. val'] = new_value
                    
                    self.logger.info(f"Executed SELL: {symbol} - {sell_qty} shares for ₹{proceed_amount:.2f}")
            
            if executed_sells:
                # Save updated holdings
                success = self._save_updated_holdings(holdings_data)
                
                if success:
                    return {
                        'success': True,
                        'executed_sells': executed_sells,
                        'total_proceeds': total_proceeds,
                        'count': len(executed_sells),
                        'message': f'Successfully executed {len(executed_sells)} sell orders'
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Failed to save updated holdings'
                    }
            else:
                return {
                    'success': False,
                    'message': 'No sell orders could be executed'
                }
                
        except Exception as e:
            self.logger.error(f"Error executing sell recommendations: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def _get_current_price(self, symbol, enhanced_data):
        """Get current price for a symbol from Enhanced Stock Report"""
        try:
            for sheet_name, sheet_data in enhanced_data.items():
                if isinstance(sheet_data, pd.DataFrame):
                    # Check different possible symbol column names
                    symbol_cols = ['Symbol', 'Instrument', 'Stock', 'Name']
                    price_cols = ['LTP', 'Current Price', 'Price', 'Close']
                    
                    for sym_col in symbol_cols:
                        if sym_col in sheet_data.columns:
                            matching_rows = sheet_data[sheet_data[sym_col] == symbol]
                            if not matching_rows.empty:
                                for price_col in price_cols:
                                    if price_col in sheet_data.columns:
                                        price = matching_rows.iloc[0][price_col]
                                        if pd.notna(price) and price > 0:
                                            return float(price)
            
            # If not found in enhanced data, return a default price (this should be replaced with real-time data)
            default_prices = {
                'UNIONBANK': 120.0,
                'DRREDDY': 5100.0,
                'YESBANK': 23.0,
                'MUTHOOTFIN': 2000.0,
                'INDUSTOWER': 340.0
            }
            
            return default_prices.get(symbol, 100.0)  # Default fallback
            
        except Exception as e:
            self.logger.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def _save_updated_holdings(self, holdings_data):
        """Save updated holdings to file"""
        try:
            # Create backup of current holdings
            original_file = self.analyzer.holdings_file
            backup_file = original_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            
            # Copy original to backup
            if os.path.exists(original_file):
                import shutil
                shutil.copy2(original_file, backup_file)
                self.logger.info(f"Created backup: {backup_file}")
            
            # Save updated holdings
            holdings_data.to_csv(original_file, index=False)
            self.logger.info(f"Updated holdings saved to: {original_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving holdings: {e}")
            return False
    
    def get_execution_summary(self):
        """Get summary of available executions"""
        try:
            # Get recommendations
            buy_analysis = self.insights.analyze_buy_recommendations()
            enhanced_sells = self.insights.get_enhanced_sell_recommendations()
            consolidation_analysis = self.analyzer.consolidation_engine.analyze_consolidation_opportunities()
            
            summary = {
                'buy_recommendations': len(buy_analysis.get('top_buy_recommendations', [])),
                'sell_recommendations': len(enhanced_sells.get('immediate_sells', [])) + len(enhanced_sells.get('profit_booking', [])),
                'consolidation_candidates': len(consolidation_analysis.get('removal_candidates', [])) if consolidation_analysis.get('action_needed') else 0,
                'available_funds': self.analyzer.available_funds
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting execution summary: {e}")
            return {}