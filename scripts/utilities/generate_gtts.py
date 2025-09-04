#!/usr/bin/env python3
"""
GTT (Good Till Triggered) Recommendation Generator
Generates GTT recommendations for stock entries and exits
"""

import sys
import os
import logging
import argparse
import pandas as pd
import yfinance as yf
from datetime import datetime
import json

# Add src directory to path
sys.path.append('src')
sys.path.append('.')

# Import necessary analysis functions
from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis

class GTTRecommendationGenerator:
    """Generates GTT recommendations for stocks"""
    
    def __init__(self):
        self.setup_logging()
        self.recommendations = {
            'entry_gtts': [],
            'exit_gtts': []
        }
    
    def setup_logging(self):
        """Setup logging"""
        os.makedirs('reports', exist_ok=True)
        
        self.log_filename = f"reports/gtt_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_filename),
                logging.StreamHandler()
            ]
        )
        
        logging.info("GTT Recommendation Generator Initialized")
    
    def generate_gtt_for_stock(self, symbol, entry_mode=False, exit_mode=False, position_data=None):
        """
        Generate GTT for a single stock
        
        Args:
            symbol (str): Stock symbol
            entry_mode (bool): True if generating entry GTT
            exit_mode (bool): True if generating exit GTT
            position_data (dict): Position data if available
        """
        try:
            logging.info(f"Analyzing {symbol} for GTT recommendations")
            
            # Get market data
            ticker = yf.Ticker(f"{symbol}.NS")
            current_data = ticker.history(period="1d")
            
            if current_data.empty:
                logging.error(f"No market data found for {symbol}")
                return None
            
            current_price = current_data['Close'].iloc[-1]
            
            # Get technical analysis for support/resistance levels
            tech_data = get_short_term_technical_analysis(symbol, period_days=90)
            if not tech_data:
                logging.error(f"Technical analysis failed for {symbol}")
                return None
            
            # Get fundamental data
            fund_data = get_comprehensive_stock_data(symbol)
            
            # Process support/resistance levels
            support_levels = tech_data.get('support_levels', [])
            resistance_levels = tech_data.get('resistance_levels', [])
            
            # Convert from string if needed
            if isinstance(support_levels, str):
                support_levels = json.loads(support_levels.replace("'", "\""))
            if isinstance(resistance_levels, str):
                resistance_levels = json.loads(resistance_levels.replace("'", "\""))
            
            gtt_rec = {
                'symbol': symbol,
                'company_name': ticker.info.get('shortName', symbol) if hasattr(ticker, 'info') else symbol,
                'current_price': current_price,
                'analysis_date': datetime.now().strftime('%Y-%m-%d'),
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'rsi': tech_data.get('rsi', 0),
                'trend': tech_data.get('trend', 'Neutral'),
                'fundamental_score': fund_data.get('fundamental_score', 50) if fund_data else 50,
                'technical_score': tech_data.get('short_term_score', 50),
                'overall_score': 0
            }
            
            # Calculate overall score
            gtt_rec['overall_score'] = (gtt_rec['fundamental_score'] * 0.6) + (gtt_rec['technical_score'] * 0.4)
            
            # Add position data if available
            if position_data:
                gtt_rec.update({
                    'quantity': position_data.get('quantity', 0),
                    'buy_price': position_data.get('buy_price', 0),
                    'current_value': position_data.get('quantity', 0) * current_price,
                    'profit_loss': (position_data.get('quantity', 0) * 
                                   (current_price - position_data.get('buy_price', 0)))
                })
            
            # Generate GTT recommendations based on mode
            if entry_mode:
                self._generate_entry_gtt(gtt_rec)
            
            if exit_mode:
                self._generate_exit_gtt(gtt_rec)
            
            return gtt_rec
            
        except Exception as e:
            logging.error(f"Error generating GTT for {symbol}: {e}")
            return None
    
    def _generate_entry_gtt(self, gtt_rec):
        """Generate entry GTT recommendations"""
        try:
            current_price = gtt_rec['current_price']
            support_levels = gtt_rec['support_levels']
            
            entry_gtt = {
                'symbol': gtt_rec['symbol'],
                'company_name': gtt_rec['company_name'],
                'current_price': current_price,
                'overall_score': gtt_rec['overall_score'],
                'recommendation': 'WATCH',
                'gtt_type': 'ENTRY'
            }
            
            # Entry points based on support levels
            if support_levels:
                # Find support levels below current price
                lower_supports = [s for s in support_levels if s < current_price]
                if lower_supports:
                    # Nearest support as primary entry
                    entry_gtt['primary_entry'] = max(lower_supports)
                    entry_gtt['primary_entry_discount'] = ((entry_gtt['primary_entry'] / current_price) - 1) * 100
                    
                    # Further supports as secondary entries
                    further_supports = [s for s in lower_supports if s < entry_gtt['primary_entry']]
                    if further_supports:
                        entry_gtt['secondary_entry'] = max(further_supports)
                        entry_gtt['secondary_entry_discount'] = ((entry_gtt['secondary_entry'] / current_price) - 1) * 100
            
            # If no support levels found, use percentage-based entries
            if 'primary_entry' not in entry_gtt:
                entry_gtt['primary_entry'] = round(current_price * 0.95, 2)  # 5% below current
                entry_gtt['primary_entry_discount'] = -5.0
                entry_gtt['secondary_entry'] = round(current_price * 0.90, 2)  # 10% below current
                entry_gtt['secondary_entry_discount'] = -10.0
            
            # Set recommendation based on scores
            if gtt_rec['overall_score'] >= 75:
                entry_gtt['recommendation'] = 'STRONG BUY'
            elif gtt_rec['overall_score'] >= 65:
                entry_gtt['recommendation'] = 'BUY'
            elif gtt_rec['overall_score'] >= 55:
                entry_gtt['recommendation'] = 'ACCUMULATE'
            else:
                entry_gtt['recommendation'] = 'WATCH'
            
            self.recommendations['entry_gtts'].append(entry_gtt)
            
        except Exception as e:
            logging.error(f"Error generating entry GTT: {e}")
    
    def _generate_exit_gtt(self, gtt_rec):
        """Generate exit GTT recommendations"""
        try:
            current_price = gtt_rec['current_price']
            resistance_levels = gtt_rec['resistance_levels']
            buy_price = gtt_rec.get('buy_price', current_price * 0.9)  # Assume 10% below if no buy price
            
            exit_gtt = {
                'symbol': gtt_rec['symbol'],
                'company_name': gtt_rec['company_name'],
                'current_price': current_price,
                'buy_price': buy_price,
                'overall_score': gtt_rec['overall_score'],
                'recommendation': 'HOLD',
                'gtt_type': 'EXIT',
                'return_percent': ((current_price / buy_price) - 1) * 100
            }
            
            # Set targets based on resistance levels
            if resistance_levels:
                # Find resistance levels above current price
                higher_resistances = [r for r in resistance_levels if r > current_price]
                if higher_resistances:
                    # Nearest resistance as target 1
                    exit_gtt['target_1'] = min(higher_resistances)
                    exit_gtt['target_1_percent'] = ((exit_gtt['target_1'] / current_price) - 1) * 100
                    
                    # Further resistances as target 2
                    further_resistances = [r for r in higher_resistances if r > exit_gtt['target_1']]
                    if further_resistances:
                        exit_gtt['target_2'] = min(further_resistances)
                        exit_gtt['target_2_percent'] = ((exit_gtt['target_2'] / current_price) - 1) * 100
            
            # If no resistance levels found, use percentage-based targets
            if 'target_1' not in exit_gtt:
                exit_gtt['target_1'] = round(current_price * 1.05, 2)  # 5% above current
                exit_gtt['target_1_percent'] = 5.0
                exit_gtt['target_2'] = round(current_price * 1.10, 2)  # 10% above current
                exit_gtt['target_2_percent'] = 10.0
            
            # Set stop-loss based on support levels or percentages
            support_levels = gtt_rec['support_levels']
            if support_levels:
                lower_supports = [s for s in support_levels if s < current_price]
                if lower_supports:
                    exit_gtt['stop_loss'] = max(lower_supports)
            
            if 'stop_loss' not in exit_gtt:
                # Default stop loss 5% below current or at buy price, whichever is lower
                exit_gtt['stop_loss'] = max(round(current_price * 0.95, 2), buy_price * 0.92)
            
            exit_gtt['stop_loss_percent'] = ((exit_gtt['stop_loss'] / current_price) - 1) * 100
            
            # Set recommendation based on scores and current price vs buy price
            return_percent = exit_gtt['return_percent']
            
            if return_percent >= 20 or gtt_rec['overall_score'] <= 40:
                exit_gtt['recommendation'] = 'SELL'
            elif return_percent >= 10 or gtt_rec['overall_score'] <= 45:
                exit_gtt['recommendation'] = 'PARTIAL SELL'
            elif gtt_rec['overall_score'] >= 65:
                exit_gtt['recommendation'] = 'HOLD/ADD'
            else:
                exit_gtt['recommendation'] = 'HOLD'
            
            self.recommendations['exit_gtts'].append(exit_gtt)
            
        except Exception as e:
            logging.error(f"Error generating exit GTT: {e}")

    def process_stock_list(self, stock_list_file, entry_mode=True, exit_mode=False):
        """
        Process a list of stocks from CSV file
        
        Args:
            stock_list_file (str): Path to CSV file with stocks
            entry_mode (bool): Generate entry GTTs
            exit_mode (bool): Generate exit GTTs
        """
        try:
            stocks_df = pd.read_csv(stock_list_file)
            
            if 'Symbol' not in stocks_df.columns:
                logging.error(f"CSV file does not have 'Symbol' column")
                return False
            
            for _, row in stocks_df.iterrows():
                symbol = row['Symbol']
                
                # Extract position data if available for exit GTTs
                position_data = None
                if exit_mode and 'Buy Price' in stocks_df.columns:
                    position_data = {
                        'quantity': row['Quantity'] if 'Quantity' in stocks_df.columns else 1,
                        'buy_price': row['Buy Price']
                    }
                
                # Generate GTT recommendations
                self.generate_gtt_for_stock(symbol, entry_mode, exit_mode, position_data)
            
            logging.info(f"Processed {len(stocks_df)} stocks for GTT recommendations")
            return True
            
        except Exception as e:
            logging.error(f"Error processing stock list: {e}")
            return False
    
    def process_symbol_list(self, symbols, entry_mode=True, exit_mode=False):
        """
        Process a list of stock symbols
        
        Args:
            symbols (list): List of stock symbols
            entry_mode (bool): Generate entry GTTs
            exit_mode (bool): Generate exit GTTs
        """
        for symbol in symbols:
            self.generate_gtt_for_stock(symbol, entry_mode, exit_mode)
        
        logging.info(f"Processed {len(symbols)} symbols for GTT recommendations")
    
    def generate_report(self, output_file="reports/gtt_recommendations.xlsx"):
        """
        Generate Excel report with GTT recommendations
        """
        try:
            # Create Excel writer
            writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
            
            # Entry GTTs
            if self.recommendations['entry_gtts']:
                entry_df = pd.DataFrame(self.recommendations['entry_gtts'])
                entry_df.to_excel(writer, sheet_name='Entry GTTs', index=False)
            
            # Exit GTTs
            if self.recommendations['exit_gtts']:
                exit_df = pd.DataFrame(self.recommendations['exit_gtts'])
                exit_df.to_excel(writer, sheet_name='Exit GTTs', index=False)
            
            # Save Excel file
            writer.close()
            
            logging.info(f"Generated GTT recommendations report: {output_file}")
            print(f"Generated GTT recommendations report: {output_file}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating report: {e}")
            return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='GTT Recommendation Generator')
    parser.add_argument('--file', '-f', help='Path to CSV file with stock symbols')
    parser.add_argument('--symbols', '-s', nargs='+', help='Stock symbols to analyze')
    parser.add_argument('--entry', '-e', action='store_true', help='Generate entry GTTs')
    parser.add_argument('--exit', '-x', action='store_true', help='Generate exit GTTs')
    parser.add_argument('--output', '-o', help='Output file path for recommendations')
    
    args = parser.parse_args()
    
    # Default to entry mode if neither is specified
    if not args.entry and not args.exit:
        args.entry = True
    
    generator = GTTRecommendationGenerator()
    
    if args.file:
        generator.process_stock_list(args.file, args.entry, args.exit)
    elif args.symbols:
        generator.process_symbol_list(args.symbols, args.entry, args.exit)
    else:
        print("Please provide either a file with stock symbols or a list of symbols")
        parser.print_help()
        return
    
    # Generate report
    output_file = args.output if args.output else f"reports/gtt_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    generator.generate_report(output_file)


if __name__ == "__main__":
    main()
