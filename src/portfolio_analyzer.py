#!/usr/bin/env python3
"""
Portfolio Analyzer Module
Analyzes a portfolio of stocks and generates trading recommendations
including GTT (Good Till Triggered) opportunities
"""

import pandas as pd
import logging
from datetime import datetime
import os
import sys
import yfinance as yf
import json
import glob

# Ensure proper imports regardless of how this module is called
sys.path.append('src')
sys.path.append('.')

# Import the necessary analysis functions
from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis
from src.technical_analyzer import calculate_indicators, compute_technical_score


class PortfolioAnalyzer:
    """Analyzes a portfolio and generates trading recommendations"""

    def __init__(self, portfolio_file=None):
        """
        Initialize the portfolio analyzer
        
        Args:
            portfolio_file (str): Path to CSV file with portfolio data
        """
        self.setup_logging()
        self.results = []
        self.portfolio_data = None
        self.recommendations = {
            'buy': [],
            'sell': [],
            'hold': [],
            'gtt_opportunities': [],
            'existing_positions_gtt': []
        }
        
        # Default portfolio file path
        default_portfolio = "holdings.csv"
        
        if portfolio_file:
            if os.path.exists(portfolio_file):
                self.load_portfolio(portfolio_file)
            else:
                logging.warning(f"Portfolio file not found: {portfolio_file}")
        elif os.path.exists(default_portfolio):
            logging.info(f"Using default portfolio file: {default_portfolio}")
            self.load_portfolio(default_portfolio)
        else:
            logging.warning("No portfolio file provided or default file not found")
            
    def setup_logging(self):
        """Setup logging for portfolio analysis"""
        os.makedirs('reports', exist_ok=True)
        
        self.log_filename = f"reports/portfolio_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_filename),
                logging.StreamHandler()
            ]
        )
        
        logging.info("Portfolio Analysis Initialized")
            
    def load_portfolio(self, file_path):
        """
        Load portfolio data from a CSV file and merge with orders if available
        
        Supports standard format:
        Symbol,Company Name,Quantity,Buy Price,Current Price,Date Purchased
        
        Also supports Zerodha Holdings export format:
        Instrument,Qty.,Avg. cost,LTP,Invested,Cur. val,P&L,Net chg.,Day chg.
        
        Additionally checks for orders files in the same directory and merges them:
        - orders.csv or orders (X).csv files containing recent transactions
        """
        try:
            logging.info(f"Loading portfolio from: {file_path}")
            df = pd.read_csv(file_path)
            
            # Check if the file is in Zerodha format
            zerodha_format = 'Instrument' in df.columns and 'Qty.' in df.columns
            
            # Convert Zerodha format to our standard format if needed
            if zerodha_format:
                logging.info("Detected Zerodha holdings format, converting...")
                # Create a new DataFrame with our standard format
                self.portfolio_data = pd.DataFrame()
                
                # Map Zerodha columns to our columns
                self.portfolio_data['Symbol'] = df['Instrument']
                self.portfolio_data['Quantity'] = df['Qty.'].astype(float)
                self.portfolio_data['Buy Price'] = df['Avg. cost'].astype(float)
                self.portfolio_data['Current Price'] = df['LTP'].astype(float)
                
                # Handle numeric columns with appropriate error handling
                try:
                    self.portfolio_data['Invested'] = pd.to_numeric(df['Invested'], errors='coerce')
                    self.portfolio_data['Current Value'] = pd.to_numeric(df['Cur. val'], errors='coerce')
                    self.portfolio_data['Profit/Loss'] = pd.to_numeric(df['P&L'], errors='coerce')
                    self.portfolio_data['Percent Change'] = pd.to_numeric(df['Net chg.'], errors='coerce')
                except Exception as e:
                    logging.warning(f"Error converting numeric columns: {e}, using calculated values instead")
                    # Calculate these values manually if conversion fails
                    self.portfolio_data['Invested'] = self.portfolio_data['Quantity'] * self.portfolio_data['Buy Price']
                    self.portfolio_data['Current Value'] = self.portfolio_data['Quantity'] * self.portfolio_data['Current Price']
                    self.portfolio_data['Profit/Loss'] = self.portfolio_data['Current Value'] - self.portfolio_data['Invested']
                    self.portfolio_data['Percent Change'] = (self.portfolio_data['Profit/Loss'] / self.portfolio_data['Invested']) * 100
                
                self.portfolio_data['Company Name'] = df['Instrument']  # Using Symbol as Company Name as it's not provided
                self.portfolio_data['Date Purchased'] = None  # Not provided in Zerodha export
            else:
                # Standard format
                self.portfolio_data = df
                
                # Validate required columns for standard format
                required_cols = ['Symbol', 'Quantity', 'Buy Price']
                missing = [col for col in required_cols if col not in self.portfolio_data.columns]
                
                if missing:
                    logging.error(f"Missing required columns in portfolio file: {missing}")
                    return False
                    
                # Add any missing columns with default values
                if 'Current Price' not in self.portfolio_data.columns:
                    self.portfolio_data['Current Price'] = None
                    
                if 'Company Name' not in self.portfolio_data.columns:
                    self.portfolio_data['Company Name'] = self.portfolio_data['Symbol']
                    
                if 'Date Purchased' not in self.portfolio_data.columns:
                    self.portfolio_data['Date Purchased'] = None
                    
                # Calculate investment metrics if not present
                if 'Invested' not in self.portfolio_data.columns:
                    self.portfolio_data['Invested'] = self.portfolio_data['Quantity'] * self.portfolio_data['Buy Price']
                    
                if 'Current Price' in self.portfolio_data.columns and not pd.isna(self.portfolio_data['Current Price']).all():
                    if 'Current Value' not in self.portfolio_data.columns:
                        self.portfolio_data['Current Value'] = self.portfolio_data['Quantity'] * self.portfolio_data['Current Price']
                    
                    if 'Profit/Loss' not in self.portfolio_data.columns:
                        self.portfolio_data['Profit/Loss'] = self.portfolio_data['Current Value'] - self.portfolio_data['Invested']
                        
                    if 'Percent Change' not in self.portfolio_data.columns:
                        self.portfolio_data['Percent Change'] = (self.portfolio_data['Profit/Loss'] / self.portfolio_data['Invested']) * 100
                
            # Remove any rows with zero quantity
            self.portfolio_data = self.portfolio_data[self.portfolio_data['Quantity'] > 0].reset_index(drop=True)
            
            # Check for and merge orders files
            self._merge_orders_with_holdings(file_path)
                
            logging.info(f"Final portfolio loaded with {len(self.portfolio_data)} positions")
            return True
            
        except Exception as e:
            logging.error(f"Error loading portfolio: {e}")
            return False

    def _merge_orders_with_holdings(self, holdings_file_path):
        """
        Check for orders files in the same directory as holdings and merge them
        """
        try:
            import glob
            
            # Get the directory of the holdings file
            holdings_dir = os.path.dirname(holdings_file_path) if os.path.dirname(holdings_file_path) else "."
            
            # Look for orders files (orders.csv or orders (X).csv)
            orders_patterns = [
                os.path.join(holdings_dir, "orders.csv"),
                os.path.join(holdings_dir, "orders (*.csv"),
                os.path.join(holdings_dir, "orders*.csv")
            ]
            
            orders_files = []
            for pattern in orders_patterns:
                orders_files.extend(glob.glob(pattern))
            
            if not orders_files:
                logging.info("No orders files found to merge")
                return
            
            # Use the most recent orders file
            latest_orders_file = max(orders_files, key=os.path.getmtime)
            logging.info(f"Found orders file: {latest_orders_file}")
            
            # Load and process orders
            orders_df = pd.read_csv(latest_orders_file)
            
            # Check if it's Zerodha orders format
            if 'Instrument' in orders_df.columns and 'Type' in orders_df.columns:
                processed_orders = self._process_zerodha_orders(orders_df)
                
                if not processed_orders.empty:
                    # Merge orders with existing holdings
                    original_count = len(self.portfolio_data)
                    self.portfolio_data = self._merge_orders_into_portfolio(processed_orders)
                    
                    new_count = len(self.portfolio_data)
                    logging.info(f"Merged {len(processed_orders)} orders. Portfolio updated: {original_count} → {new_count} positions")
                    print(f"✅ Merged orders from {os.path.basename(latest_orders_file)}")
                    print(f"   📊 Portfolio positions updated: {original_count} → {new_count}")
                else:
                    logging.info("No valid completed orders found to merge")
            else:
                logging.warning(f"Unknown orders file format in {latest_orders_file}")
                
        except Exception as e:
            logging.error(f"Error merging orders with holdings: {e}")
            print(f"⚠️ Could not merge orders: {e}")

    def _process_zerodha_orders(self, orders_df):
        """
        Process Zerodha orders file to extract completed transactions
        """
        try:
            # Filter for completed orders only
            completed_orders = orders_df[orders_df['Status'] == 'COMPLETE'].copy()
            
            if completed_orders.empty:
                return pd.DataFrame()
            
            # Extract quantity (handle "28/28" format)
            completed_orders['Executed_Qty'] = completed_orders['Qty.'].apply(
                lambda x: float(str(x).split('/')[0]) if '/' in str(x) else float(x)
            )
            
            # Group by instrument and transaction type, sum quantities
            order_summary = completed_orders.groupby(['Instrument', 'Type']).agg({
                'Executed_Qty': 'sum',
                'Avg. price': 'mean'  # Average price across multiple orders
            }).reset_index()
            
            # Calculate net position changes
            net_changes = []
            for instrument in order_summary['Instrument'].unique():
                instrument_orders = order_summary[order_summary['Instrument'] == instrument]
                
                buy_qty = instrument_orders[instrument_orders['Type'] == 'BUY']['Executed_Qty'].sum()
                sell_qty = instrument_orders[instrument_orders['Type'] == 'SELL']['Executed_Qty'].sum()
                net_qty_change = buy_qty - sell_qty
                
                if net_qty_change != 0:
                    # Determine the effective transaction
                    if net_qty_change > 0:
                        # Net buying
                        avg_price = instrument_orders[instrument_orders['Type'] == 'BUY']['Avg. price'].mean()
                        transaction_type = 'BUY'
                        quantity = net_qty_change
                    else:
                        # Net selling
                        avg_price = instrument_orders[instrument_orders['Type'] == 'SELL']['Avg. price'].mean()
                        transaction_type = 'SELL'
                        quantity = abs(net_qty_change)
                    
                    net_changes.append({
                        'Symbol': instrument,
                        'Transaction_Type': transaction_type,
                        'Quantity': quantity,
                        'Price': avg_price
                    })
            
            return pd.DataFrame(net_changes)
            
        except Exception as e:
            logging.error(f"Error processing Zerodha orders: {e}")
            return pd.DataFrame()

    def _merge_orders_into_portfolio(self, orders_df):
        """
        Merge processed orders into the existing portfolio
        """
        try:
            updated_portfolio = self.portfolio_data.copy()
            
            for _, order in orders_df.iterrows():
                symbol = order['Symbol']
                transaction_type = order['Transaction_Type']
                quantity = order['Quantity']
                price = order['Price']
                
                # Check if symbol exists in portfolio
                existing_position = updated_portfolio[updated_portfolio['Symbol'] == symbol]
                
                if not existing_position.empty:
                    # Update existing position
                    idx = existing_position.index[0]
                    current_qty = updated_portfolio.loc[idx, 'Quantity']
                    current_avg_price = updated_portfolio.loc[idx, 'Buy Price']
                    
                    if transaction_type == 'BUY':
                        # Add to position
                        new_qty = current_qty + quantity
                        new_avg_price = ((current_qty * current_avg_price) + (quantity * price)) / new_qty
                        
                        updated_portfolio.loc[idx, 'Quantity'] = new_qty
                        updated_portfolio.loc[idx, 'Buy Price'] = new_avg_price
                        updated_portfolio.loc[idx, 'Invested'] = new_qty * new_avg_price
                        
                        logging.info(f"Updated {symbol}: +{quantity} shares @ ₹{price:.2f} (New qty: {new_qty}, Avg: ₹{new_avg_price:.2f})")
                        
                    elif transaction_type == 'SELL':
                        # Reduce position
                        new_qty = max(0, current_qty - quantity)
                        
                        if new_qty > 0:
                            # Partial sell - keep same average price
                            updated_portfolio.loc[idx, 'Quantity'] = new_qty
                            updated_portfolio.loc[idx, 'Invested'] = new_qty * current_avg_price
                            logging.info(f"Reduced {symbol}: -{quantity} shares (New qty: {new_qty})")
                        else:
                            # Complete sell - remove from portfolio
                            updated_portfolio = updated_portfolio.drop(idx)
                            logging.info(f"Removed {symbol}: Completely sold out")
                            
                else:
                    # New position from orders
                    if transaction_type == 'BUY':
                        new_position = {
                            'Symbol': symbol,
                            'Company Name': symbol,  # Will be updated later
                            'Quantity': quantity,
                            'Buy Price': price,
                            'Invested': quantity * price,
                            'Date Purchased': None
                        }
                        
                        # Add other columns if they exist in the original portfolio
                        for col in updated_portfolio.columns:
                            if col not in new_position:
                                new_position[col] = None
                        
                        # Convert to DataFrame and append
                        new_row = pd.DataFrame([new_position])
                        updated_portfolio = pd.concat([updated_portfolio, new_row], ignore_index=True)
                        
                        logging.info(f"Added new position {symbol}: {quantity} shares @ ₹{price:.2f}")
            
            # Remove any zero quantity positions
            updated_portfolio = updated_portfolio[updated_portfolio['Quantity'] > 0].reset_index(drop=True)
            
            return updated_portfolio
            
        except Exception as e:
            logging.error(f"Error merging orders into portfolio: {e}")
            return self.portfolio_data
            
    def create_portfolio_template(self, output_path="portfolio_template.csv"):
        """
        Create a template CSV file for portfolio input
        """
        template_df = pd.DataFrame({
            'Symbol': ['RELIANCE', 'HDFCBANK', 'INFY'],
            'Company Name': ['Reliance Industries Ltd', 'HDFC Bank Ltd', 'Infosys Ltd'],
            'Quantity': [10, 15, 20],
            'Buy Price': [2500.00, 1600.00, 1400.00],
            'Current Price': [2600.00, 1650.00, 1380.00],
            'Date Purchased': ['2024-05-15', '2024-06-10', '2024-07-20']
        })
        
        try:
            template_df.to_csv(output_path, index=False)
            logging.info(f"Created portfolio template at: {output_path}")
            print(f"Created portfolio template at: {output_path}")
            return True
        except Exception as e:
            logging.error(f"Error creating portfolio template: {e}")
            return False

    def update_current_prices(self):
        """
        Update current prices for all portfolio stocks
        """
        if self.portfolio_data is None:
            logging.error("No portfolio data loaded")
            return False
            
        logging.info("Updating current market prices for portfolio stocks")
        
        for index, row in self.portfolio_data.iterrows():
            symbol = row['Symbol']
            try:
                # Get current market data using yfinance
                ticker = yf.Ticker(f"{symbol}.NS")
                current_data = ticker.history(period="1d")
                
                if not current_data.empty:
                    current_price = current_data['Close'].iloc[-1]
                    self.portfolio_data.at[index, 'Current Price'] = current_price
                    logging.info(f"Updated price for {symbol}: ₹{current_price:.2f}")
                else:
                    logging.warning(f"No price data found for {symbol}")
            except Exception as e:
                logging.error(f"Error getting price for {symbol}: {e}")
                
        return True

    def analyze_portfolio(self):
        """
        Perform comprehensive analysis on each stock in the portfolio
        """
        if self.portfolio_data is None:
            logging.error("No portfolio data loaded")
            return False
            
        logging.info(f"Starting analysis for {len(self.portfolio_data)} stocks")
        
        # Clear previous results
        self.results = []
        
        for index, row in self.portfolio_data.iterrows():
            symbol = row['Symbol']
            logging.info(f"Analyzing {symbol}...")
            
            # Initialize result dict with basic portfolio info
            stock_result = {
                'symbol': symbol,
                'company_name': row['Company Name'],
                'quantity': float(row['Quantity']),
                'buy_price': float(row['Buy Price']) if not pd.isna(row['Buy Price']) else 0,
                'current_price': float(row['Current Price']) if not pd.isna(row['Current Price']) else 0,
                'invested': float(row['Invested']) if 'Invested' in row and not pd.isna(row['Invested']) else 0,
                'current_value': 0,
                'profit_loss': 0,
                'percent_change': 0,
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            # Calculate current value and P&L if not already available
            if 'Current Value' not in row or pd.isna(row['Current Value']):
                stock_result['current_value'] = stock_result['quantity'] * stock_result['current_price']
            else:
                stock_result['current_value'] = float(row['Current Value'])
                
            if 'Profit/Loss' not in row or pd.isna(row['Profit/Loss']):
                stock_result['profit_loss'] = stock_result['current_value'] - stock_result['invested']
            else:
                stock_result['profit_loss'] = float(row['Profit/Loss'])
                
            if 'Percent Change' not in row or pd.isna(row['Percent Change']):
                if stock_result['invested'] > 0:
                    stock_result['percent_change'] = (stock_result['profit_loss'] / stock_result['invested']) * 100
            else:
                stock_result['percent_change'] = float(row['Percent Change'])
            
            # 1. Fundamental Analysis
            try:
                fund_data = get_comprehensive_stock_data(symbol)
                if fund_data:
                    stock_result.update(fund_data)
                    stock_result['fundamental_status'] = 'success'
                    logging.info(f"Fundamental analysis completed for {symbol}")
                else:
                    stock_result['fundamental_status'] = 'failed'
                    logging.warning(f"Fundamental analysis failed for {symbol}")
            except Exception as e:
                stock_result['fundamental_status'] = f'error: {str(e)}'
                logging.error(f"Error in fundamental analysis for {symbol}: {e}")
            
            # 2. Enhanced Technical Analysis
            try:
                enhanced_tech_data = get_short_term_technical_analysis(symbol, period_days=90)
                if enhanced_tech_data:
                    # Add with prefix to avoid conflicts
                    for key, value in enhanced_tech_data.items():
                        if key not in stock_result:
                            stock_result[f"enhanced_{key}"] = value
                        else:
                            stock_result[f"enhanced_tech_{key}"] = value
                    stock_result['enhanced_technical_status'] = 'success'
                    logging.info(f"Enhanced technical analysis completed for {symbol}")
                else:
                    stock_result['enhanced_technical_status'] = 'failed'
                    logging.warning(f"Enhanced technical analysis failed for {symbol}")
            except Exception as e:
                stock_result['enhanced_technical_status'] = f'error: {str(e)}'
                logging.error(f"Error in enhanced technical analysis for {symbol}: {e}")
            
            # 3. Generate recommendation
            stock_result['recommendation'] = self._generate_stock_recommendation(stock_result)
            
            # Add to results
            self.results.append(stock_result)
            logging.info(f"Completed analysis for {symbol}: {stock_result['recommendation']}")
            
        logging.info(f"Portfolio analysis completed for {len(self.results)} stocks")
        return True
    
    def _generate_stock_recommendation(self, stock_data):
        """
        Generate a recommendation based on analysis
        """
        # Default recommendation
        recommendation = {
            'action': 'HOLD',
            'confidence': 50,
            'reason': 'Insufficient data for recommendation'
        }
        
        # Technical indicators
        enhanced_score = stock_data.get('enhanced_short_term_score', 50) 
        
        # Fundamental indicators
        fund_score = stock_data.get('fundamental_score', 50)
        
        # Combine scores with weighting
        overall_score = (enhanced_score * 0.6) + (fund_score * 0.4)
        
        # Generate recommendation based on overall score
        if overall_score >= 75:
            recommendation = {
                'action': 'BUY',
                'confidence': round(overall_score, 1),
                'reason': 'Strong technical and fundamental indicators'
            }
            self.recommendations['buy'].append(stock_data['symbol'])
        elif overall_score <= 35:
            recommendation = {
                'action': 'SELL',
                'confidence': round(100 - overall_score, 1),
                'reason': 'Poor technical and fundamental indicators'
            }
            self.recommendations['sell'].append(stock_data['symbol'])
        else:
            recommendation = {
                'action': 'HOLD',
                'confidence': round(abs(50 - overall_score) * 2, 1),
                'reason': 'Mixed or neutral technical and fundamental indicators'
            }
            self.recommendations['hold'].append(stock_data['symbol'])
            
        return recommendation
        
    def generate_gtt_recommendations(self):
        """
        Generate GTT (Good Till Triggered) recommendations for both existing 
        positions and potential new opportunities
        """
        if not self.results:
            logging.error("No analysis results available")
            return False
            
        logging.info("Generating GTT recommendations")
        
        # Clear previous recommendations
        self.recommendations['gtt_opportunities'] = []
        self.recommendations['existing_positions_gtt'] = []
        
        # Process each analyzed stock
        for stock_data in self.results:
            symbol = stock_data['symbol']
            current_price = stock_data['current_price']
            
            # Skip if no current price available
            if current_price == 0:
                continue
                
            # Check if this is an existing position
            is_existing = stock_data['quantity'] > 0
            
            # Get technical data
            rsi = stock_data.get('enhanced_rsi', 50)
            macd_signal = stock_data.get('enhanced_macd_signal', 0)
            trend = stock_data.get('enhanced_trend', 'NEUTRAL')
            
            # Get support and resistance levels
            support_levels = stock_data.get('enhanced_support_levels', [current_price * 0.95])
            resistance_levels = stock_data.get('enhanced_resistance_levels', [current_price * 1.05])
            
            # Convert to proper lists if they're strings
            if isinstance(support_levels, str):
                try:
                    support_levels = eval(support_levels)
                except:
                    support_levels = [current_price * 0.95]
                    
            if isinstance(resistance_levels, str):
                try:
                    resistance_levels = eval(resistance_levels)
                except:
                    resistance_levels = [current_price * 1.05]
            
            # Find nearest support and resistance
            nearest_support = min([s for s in support_levels if s < current_price], default=current_price * 0.95)
            nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.05)
            
            # Generate GTT based on position type and technical analysis
            if is_existing:
                # For existing positions, generate stop loss and target price GTTs
                stop_loss = nearest_support * 0.98  # 2% below nearest support
                target_price = nearest_resistance * 1.01  # 1% above nearest resistance
                
                # If in strong uptrend, set tighter stop loss
                if trend == 'STRONG_UPTREND':
                    stop_loss = nearest_support * 0.99  # Tighter stop loss
                    target_price = nearest_resistance * 1.02  # Higher target
                
                # If in strong downtrend, set tighter target
                if trend == 'STRONG_DOWNTREND':
                    stop_loss = nearest_support * 0.97  # Lower stop loss
                    target_price = nearest_resistance  # Tighter target
                
                gtt_recommendation = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'stop_loss': round(stop_loss, 2),
                    'stop_loss_percent': round((stop_loss - current_price) / current_price * 100, 2),
                    'target_price': round(target_price, 2),
                    'target_price_percent': round((target_price - current_price) / current_price * 100, 2),
                    'position_type': 'EXISTING',
                    'trend': trend,
                    'rsi': rsi,
                    'quantity': stock_data['quantity'],
                    'nearest_support': round(nearest_support, 2),
                    'nearest_resistance': round(nearest_resistance, 2)
                }
                
                self.recommendations['existing_positions_gtt'].append(gtt_recommendation)
            else:
                # For new opportunities, generate entry price GTTs
                if stock_data['recommendation']['action'] == 'BUY':
                    entry_price = nearest_support * 1.01  # 1% above support
                    
                    gtt_recommendation = {
                        'symbol': symbol,
                        'current_price': current_price,
                        'entry_price': round(entry_price, 2),
                        'entry_price_percent': round((entry_price - current_price) / current_price * 100, 2),
                        'position_type': 'OPPORTUNITY',
                        'trend': trend,
                        'rsi': rsi,
                        'recommended_quantity': 0,  # This should be set based on user's capital
                        'confidence': stock_data['recommendation']['confidence'],
                        'nearest_support': round(nearest_support, 2),
                        'nearest_resistance': round(nearest_resistance, 2)
                    }
                    
                    self.recommendations['gtt_opportunities'].append(gtt_recommendation)
        
        logging.info(f"Generated GTT recommendations for {len(self.recommendations['existing_positions_gtt'])} existing positions")
        logging.info(f"Generated GTT recommendations for {len(self.recommendations['gtt_opportunities'])} new opportunities")
        
        return True
                
    def save_analysis_report(self, output_path="reports/portfolio_analysis.xlsx"):
        """
        Save comprehensive portfolio analysis to Excel
        """
        if not self.results:
            logging.error("No analysis results available")
            return False
            
        try:
            # Create Excel writer
            writer = pd.ExcelWriter(output_path, engine='xlsxwriter')
            
            # Create summary DataFrame
            summary_data = []
            for stock in self.results:
                summary_data.append({
                    'Symbol': stock['symbol'],
                    'Company Name': stock['company_name'],
                    'Quantity': stock['quantity'],
                    'Buy Price': stock['buy_price'],
                    'Current Price': stock['current_price'],
                    'Current Value': stock['current_value'],
                    'Profit/Loss': stock['profit_loss'],
                    'Percent Change': stock['percent_change'],
                    'Recommendation': stock['recommendation']['action'],
                    'Confidence': stock['recommendation']['confidence'],
                    'Reason': stock['recommendation']['reason'],
                    'Trend': stock.get('enhanced_trend', 'NEUTRAL'),
                    'RSI': stock.get('enhanced_rsi', 50),
                    'Technical Score': stock.get('enhanced_short_term_score', 50),
                    'Fundamental Score': stock.get('fundamental_score', 50)
                })
                
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Portfolio Summary', index=False)
            
            # Create recommendations sheet
            recommendations_data = []
            for stock in self.results:
                recommendations_data.append({
                    'Symbol': stock['symbol'],
                    'Action': stock['recommendation']['action'],
                    'Confidence': stock['recommendation']['confidence'],
                    'Reason': stock['recommendation']['reason']
                })
                
            recommendations_df = pd.DataFrame(recommendations_data)
            recommendations_df.to_excel(writer, sheet_name='Recommendations', index=False)
            
            # Create GTT sheets if available
            if self.recommendations['existing_positions_gtt']:
                existing_gtt_df = pd.DataFrame(self.recommendations['existing_positions_gtt'])
                existing_gtt_df.to_excel(writer, sheet_name='Existing Position GTTs', index=False)
                
            if self.recommendations['gtt_opportunities']:
                opportunities_gtt_df = pd.DataFrame(self.recommendations['gtt_opportunities'])
                opportunities_gtt_df.to_excel(writer, sheet_name='Opportunity GTTs', index=False)
            
            # Save Excel file
            writer.close()
            logging.info(f"Analysis report saved to {output_path}")
            
            return True
        except Exception as e:
            logging.error(f"Error saving analysis report: {e}")
            return False

    def save_gtt_recommendations(self, output_path="reports/gtt_recommendations.json"):
        """
        Save GTT recommendations to JSON file
        """
        if not self.recommendations['existing_positions_gtt'] and not self.recommendations['gtt_opportunities']:
            logging.error("No GTT recommendations available")
            return False
            
        try:
            with open(output_path, 'w') as f:
                json.dump(self.recommendations, f, indent=4)
                
            logging.info(f"GTT recommendations saved to {output_path}")
            return True
        except Exception as e:
            logging.error(f"Error saving GTT recommendations: {e}")
            return False
            
    def export_gtt_csv(self, output_path="reports/gtt_recommendations.csv"):
        """
        Export GTT recommendations to CSV for easy import into trading platform
        """
        if not self.recommendations['existing_positions_gtt'] and not self.recommendations['gtt_opportunities']:
            logging.error("No GTT recommendations available")
            return False
            
        try:
            # Create DataFrames for each recommendation type
            existing_gtts = []
            for rec in self.recommendations['existing_positions_gtt']:
                # Stop Loss GTT
                existing_gtts.append({
                    'Symbol': rec['symbol'],
                    'Product': 'CNC',  # For delivery positions
                    'Transaction Type': 'SELL',  # Sell to exit position
                    'Quantity': rec['quantity'],
                    'Price': rec['stop_loss'],
                    'Trigger Price': rec['stop_loss'],
                    'Disclosing Qty': rec['quantity'],
                    'GTT Type': 'STOP_LOSS',
                    'Status': 'ACTIVE'
                })
                
                # Target Price GTT
                existing_gtts.append({
                    'Symbol': rec['symbol'],
                    'Product': 'CNC',  # For delivery positions
                    'Transaction Type': 'SELL',  # Sell to exit position
                    'Quantity': rec['quantity'],
                    'Price': rec['target_price'],
                    'Trigger Price': rec['target_price'],
                    'Disclosing Qty': rec['quantity'],
                    'GTT Type': 'TARGET',
                    'Status': 'ACTIVE'
                })
                
            opportunities = []
            for rec in self.recommendations['gtt_opportunities']:
                opportunities.append({
                    'Symbol': rec['symbol'],
                    'Product': 'CNC',  # For delivery positions
                    'Transaction Type': 'BUY',  # Buy to enter position
                    'Quantity': rec.get('recommended_quantity', 0),
                    'Price': rec['entry_price'],
                    'Trigger Price': rec['entry_price'],
                    'Disclosing Qty': rec.get('recommended_quantity', 0),
                    'GTT Type': 'ENTRY',
                    'Status': 'ACTIVE'
                })
            
            # Combine and save to CSV
            all_gtts = pd.DataFrame(existing_gtts + opportunities)
            all_gtts.to_csv(output_path, index=False)
            
            logging.info(f"GTT recommendations exported to CSV: {output_path}")
            return True
        except Exception as e:
            logging.error(f"Error exporting GTT recommendations to CSV: {e}")
            return False

    # ------------------------------------------------------------------
    # Entry / Exit Point Generation
    # ------------------------------------------------------------------
    def generate_entry_exit_points(self, use_breakout=True):
        """Generate standardized entry & exit (stop/targets) points for analyzed stocks.

        Uses enhanced support/resistance levels when available. Provides both pullback
        and breakout style entries plus risk/reward metrics.
        """
        if not self.results:
            logging.error("No analysis results available. Run analyze_portfolio() first.")
            return None

        entries = []
        for stock in self.results:
            symbol = stock.get('symbol')
            current_price = float(stock.get('current_price') or 0)
            if current_price <= 0:
                continue

            # Extract support / resistance lists
            support_levels = stock.get('enhanced_support_levels') or stock.get('support_levels') or []
            resistance_levels = stock.get('enhanced_resistance_levels') or stock.get('resistance_levels') or []

            def _to_list(val, fallback_multiplier):
                if isinstance(val, list):
                    return [v for v in val if isinstance(v,(int,float))]
                if isinstance(val, str):
                    # Try safe eval
                    try:
                        tmp = eval(val, {"__builtins__":{}})
                        if isinstance(tmp, list):
                            return [v for v in tmp if isinstance(v,(int,float))]
                    except Exception:
                        pass
                # fallback single synthetic level
                return [current_price * fallback_multiplier]

            support_levels = sorted(set(_to_list(support_levels, 0.95)))
            resistance_levels = sorted(set(_to_list(resistance_levels, 1.05)))

            lower_supports = [s for s in support_levels if s < current_price]
            higher_resistances = [r for r in resistance_levels if r > current_price]

            nearest_support = max(lower_supports) if lower_supports else current_price * 0.95
            nearest_resistance = min(higher_resistances) if higher_resistances else current_price * 1.05
            next_resistance = None
            if len(higher_resistances) > 1:
                # second element after sorted list
                sorted_res = sorted(higher_resistances)
                if sorted_res[0] == nearest_resistance and len(sorted_res) > 1:
                    next_resistance = sorted_res[1]
            if next_resistance is None:
                next_resistance = nearest_resistance * 1.05

            # Entry strategies
            pullback_entry = nearest_support * 1.01
            breakout_entry = nearest_resistance * 1.01

            # Stop loss 2% below support (tighter if strong uptrend)
            trend = stock.get('enhanced_trend') or stock.get('trend') or 'NEUTRAL'
            stop_buffer = 0.02
            if trend == 'STRONG_UPTREND':
                stop_buffer = 0.015
            stop_loss = nearest_support * (1 - stop_buffer)

            # Targets
            target1 = nearest_resistance * 0.99  # just below resistance
            target2 = next_resistance * 0.985 if next_resistance else target1 * 1.05

            # Choose primary entry depending on mode & positioning
            recommendation = stock.get('final_recommendation') or stock.get('recommendation', {}).get('action')
            has_position = stock.get('quantity', 0) > 0
            preferred_entry = breakout_entry if use_breakout and trend.startswith('STRONG') else pullback_entry
            if has_position:
                # For existing position treat preferred entry as add-on level near support
                preferred_entry = pullback_entry

            def rr(entry, target):
                risk = entry - stop_loss
                reward = target - entry
                return round(reward / risk, 2) if risk > 0 else None

            rr1 = rr(preferred_entry, target1)
            rr2 = rr(preferred_entry, target2)

            entries.append({
                'Symbol': symbol,
                'Current Price': round(current_price,2),
                'Trend': trend,
                'Recommendation': recommendation,
                'Has Position': has_position,
                'Nearest Support': round(nearest_support,2),
                'Nearest Resistance': round(nearest_resistance,2),
                'Pullback Entry': round(pullback_entry,2),
                'Breakout Entry': round(breakout_entry,2),
                'Primary Entry': round(preferred_entry,2),
                'Stop Loss': round(stop_loss,2),
                'Target 1': round(target1,2),
                'Target 2': round(target2,2),
                'RR@T1': rr1,
                'RR@T2': rr2,
                'Enhanced Technical Score': stock.get('enhanced_short_term_score'),
                'Fundamental Score': stock.get('fundamental_score'),
            })

        self.entry_exit_points = entries
        logging.info(f"Generated entry/exit points for {len(entries)} stocks")
        return entries

    def export_entry_exit_points(self, output_path="reports/entry_exit_points.csv"):
        """Export generated entry/exit points to CSV."""
        if not hasattr(self, 'entry_exit_points') or not self.entry_exit_points:
            logging.error("No entry/exit points generated. Call generate_entry_exit_points first.")
            return False
        try:
            pd.DataFrame(self.entry_exit_points).to_csv(output_path, index=False)
            logging.info(f"Entry/exit points exported: {output_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to export entry/exit points: {e}")
            return False
            
    def calculate_portfolio_metrics(self):
        """
        Calculate basic portfolio metrics like P&L, returns
        """
        if self.portfolio_data is None or 'Current Price' not in self.portfolio_data.columns:
            logging.error("Cannot calculate portfolio metrics: missing data")
            return None
            
        try:
            # Calculate position metrics
            self.portfolio_data['Investment'] = self.portfolio_data['Quantity'] * self.portfolio_data['Buy Price']
            self.portfolio_data['Current Value'] = self.portfolio_data['Quantity'] * self.portfolio_data['Current Price']
            self.portfolio_data['P&L'] = self.portfolio_data['Current Value'] - self.portfolio_data['Investment']
            self.portfolio_data['Return %'] = (self.portfolio_data['P&L'] / self.portfolio_data['Investment']) * 100
            
            # Calculate portfolio level metrics
            metrics = {
                'total_investment': self.portfolio_data['Investment'].sum(),
                'current_value': self.portfolio_data['Current Value'].sum(),
                'overall_pnl': self.portfolio_data['P&L'].sum(),
                'overall_return_percent': (self.portfolio_data['P&L'].sum() / self.portfolio_data['Investment'].sum()) * 100,
                'profitable_positions': len(self.portfolio_data[self.portfolio_data['P&L'] > 0]),
                'losing_positions': len(self.portfolio_data[self.portfolio_data['P&L'] < 0])
            }
            
            logging.info(f"Portfolio Value: ₹{metrics['current_value']:,.2f}, P&L: ₹{metrics['overall_pnl']:,.2f} ({metrics['overall_return_percent']:.2f}%)")
            return metrics
            
        except Exception as e:
            logging.error(f"Error calculating portfolio metrics: {e}")
            return None

    def analyze_portfolio_stocks(self):
        """
        Run detailed analysis on each portfolio stock
        """
        if self.portfolio_data is None:
            logging.error("No portfolio data loaded")
            return False
            
        self.results = []
        
        for _, row in self.portfolio_data.iterrows():
            symbol = row['Symbol']
            logging.info(f"Analyzing portfolio stock: {symbol}")
            
            stock_analysis = self._analyze_single_stock(symbol, row)
            if stock_analysis:
                self.results.append(stock_analysis)
                
        return len(self.results) > 0

    def _analyze_single_stock(self, symbol, position_data=None):
        """
        Analyze a single stock with comprehensive data
        """
        try:
            stock_data = {
                'symbol': symbol,
                'company_name': position_data['Company Name'] if position_data is not None else symbol,
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            if position_data is not None:
                stock_data.update({
                    'quantity': position_data['Quantity'],
                    'buy_price': position_data['Buy Price'],
                    'current_price': position_data['Current Price'],
                    'investment': position_data['Investment'] if 'Investment' in position_data else None,
                    'current_value': position_data['Current Value'] if 'Current Value' in position_data else None,
                    'pnl': position_data['P&L'] if 'P&L' in position_data else None,
                    'return_percent': position_data['Return %'] if 'Return %' in position_data else None,
                })
            
            # 1. Fundamental Analysis
            fund_data = get_comprehensive_stock_data(symbol)
            if fund_data:
                stock_data.update(fund_data)
                stock_data['fundamental_status'] = 'success'
                logging.info(f"Fundamental analysis completed for {symbol}: {len(fund_data)} fields")
            else:
                stock_data['fundamental_status'] = 'failed'
                logging.warning(f"Fundamental analysis failed for {symbol}")
            
            # 2. Enhanced Technical Analysis
            enhanced_tech_data = get_short_term_technical_analysis(symbol, period_days=90)
            if enhanced_tech_data:
                # Add with prefix to avoid conflicts
                for key, value in enhanced_tech_data.items():
                    if key not in stock_data:
                        stock_data[f"enhanced_{key}"] = value
                    else:
                        stock_data[f"enhanced_tech_{key}"] = value
                stock_data['enhanced_technical_status'] = 'success'
                logging.info(f"Enhanced technical analysis completed for {symbol}")
            else:
                stock_data['enhanced_technical_status'] = 'failed'
                logging.warning(f"Enhanced technical analysis failed for {symbol}")
            
            # 3. Calculate Scores
            fund_score = stock_data.get('fundamental_score', 50)
            enhanced_score = enhanced_tech_data.get('short_term_score', 50) if enhanced_tech_data else 50
            
            stock_data['overall_score'] = (fund_score * 0.6) + (enhanced_score * 0.4)
            
            return stock_data
            
        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {e}")
            return None

    def generate_gtt_recommendations(self):
        """
        Generate Good Till Triggered (GTT) recommendations for portfolio positions
        and new opportunities
        """
        if not self.results:
            logging.error("No analysis results to generate GTT recommendations")
            return False
            
        # Process existing positions
        for stock in self.results:
            symbol = stock['symbol']
            current_price = stock.get('current_price')
            
            if current_price is not None:  # This is a portfolio position
                buy_price = stock.get('buy_price')
                
                # Get technical indicators
                support_levels = stock.get('enhanced_support_levels', [])
                resistance_levels = stock.get('enhanced_resistance_levels', [])
                
                # Convert from string if needed
                if isinstance(support_levels, str):
                    support_levels = json.loads(support_levels.replace("'", "\""))
                if isinstance(resistance_levels, str):
                    resistance_levels = json.loads(resistance_levels.replace("'", "\""))
                    
                # Generate GTT for existing position
                position_gtt = {
                    'symbol': symbol,
                    'company_name': stock.get('company_name', symbol),
                    'current_price': current_price,
                    'buy_price': buy_price,
                    'return_percent': stock.get('return_percent', 0),
                }
                
                # Target and stop-loss based on technical analysis
                if len(resistance_levels) > 0:
                    # Target 1: nearest resistance level
                    nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.05)
                    position_gtt['target_1'] = nearest_resistance
                    position_gtt['target_1_percent'] = ((nearest_resistance / current_price) - 1) * 100
                    
                    # Target 2: second resistance level if available
                    higher_resistances = [r for r in resistance_levels if r > nearest_resistance]
                    if higher_resistances:
                        position_gtt['target_2'] = min(higher_resistances)
                        position_gtt['target_2_percent'] = ((position_gtt['target_2'] / current_price) - 1) * 100
                
                if len(support_levels) > 0:
                    # Stop-loss: nearest support level below current price
                    nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.95)
                    position_gtt['stop_loss'] = nearest_support
                    position_gtt['stop_loss_percent'] = ((nearest_support / current_price) - 1) * 100
                
                # Add recommendation based on technical and fundamental scores
                overall_score = stock.get('overall_score', 50)
                technical_score = stock.get('enhanced_short_term_score', 50)
                
                if overall_score >= 70 and technical_score >= 65:
                    position_gtt['recommendation'] = 'HOLD/ADD'
                elif overall_score <= 40 or (technical_score <= 40 and position_gtt.get('return_percent', 0) > 5):
                    position_gtt['recommendation'] = 'SELL'
                else:
                    position_gtt['recommendation'] = 'HOLD'
                    
                self.recommendations['existing_positions_gtt'].append(position_gtt)
        
        # Process new opportunities from stock list (to be implemented)
        # This would need to scan other potential stocks not in portfolio
        
        logging.info(f"Generated GTT recommendations: {len(self.recommendations['existing_positions_gtt'])} existing positions")
        return True
        
    def scan_for_new_opportunities(self, stock_list_file='stock_list_template.csv'):
        """
        Scan stocks from a stock list for new investment opportunities
        """
        try:
            stock_df = pd.read_csv(stock_list_file)
            
            if 'Symbol' not in stock_df.columns:
                logging.error(f"Stock list file missing Symbol column")
                return False
                
            # Filter out stocks already in portfolio
            if self.portfolio_data is not None:
                portfolio_symbols = set(self.portfolio_data['Symbol'])
                new_stocks = [symbol for symbol in stock_df['Symbol'] if symbol not in portfolio_symbols]
            else:
                new_stocks = stock_df['Symbol'].tolist()
                
            logging.info(f"Scanning {len(new_stocks)} stocks for new opportunities")
            
            # Analyze top opportunities (limit to 20 to avoid excessive API calls)
            opportunities = []
            for symbol in new_stocks[:20]:
                opportunity = self._analyze_single_stock(symbol)
                if opportunity:
                    opportunities.append(opportunity)
            
            # Find the best opportunities based on overall score
            if opportunities:
                # Sort by overall score in descending order
                opportunities.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
                
                # Take top opportunities
                top_opportunities = opportunities[:10]
                
                # Generate GTT for each opportunity
                for stock in top_opportunities:
                    symbol = stock['symbol']
                    
                    # Get current price data
                    try:
                        ticker = yf.Ticker(f"{symbol}.NS")
                        current_data = ticker.history(period="1d")
                        
                        if not current_data.empty:
                            current_price = current_data['Close'].iloc[-1]
                            
                            # Get technical indicators
                            support_levels = stock.get('enhanced_support_levels', [])
                            resistance_levels = stock.get('enhanced_resistance_levels', [])
                            
                            # Convert from string if needed
                            if isinstance(support_levels, str):
                                support_levels = json.loads(support_levels.replace("'", "\""))
                            if isinstance(resistance_levels, str):
                                resistance_levels = json.loads(resistance_levels.replace("'", "\""))
                                
                            # Create GTT opportunity
                            gtt_opp = {
                                'symbol': symbol,
                                'company_name': stock.get('company_name', symbol),
                                'current_price': current_price,
                                'overall_score': stock.get('overall_score', 0),
                                'fundamental_score': stock.get('fundamental_score', 0),
                                'technical_score': stock.get('enhanced_short_term_score', 0),
                            }
                            
                            # Entry points: Support levels or current price with margin
                            if len(support_levels) > 0:
                                # Nearest support below current price
                                nearest_support = max([s for s in support_levels if s < current_price], default=current_price * 0.95)
                                gtt_opp['entry_point_1'] = nearest_support
                                gtt_opp['entry_point_1_discount'] = ((nearest_support / current_price) - 1) * 100
                                
                                # Second support level if available
                                lower_supports = [s for s in support_levels if s < nearest_support]
                                if lower_supports:
                                    gtt_opp['entry_point_2'] = max(lower_supports)
                                    gtt_opp['entry_point_2_discount'] = ((gtt_opp['entry_point_2'] / current_price) - 1) * 100
                            
                            # Exit targets based on resistance levels
                            if len(resistance_levels) > 0:
                                # Nearest resistance above current price
                                nearest_resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.05)
                                gtt_opp['target_1'] = nearest_resistance
                                gtt_opp['target_1_percent'] = ((nearest_resistance / current_price) - 1) * 100
                                
                                # Second resistance level if available
                                higher_resistances = [r for r in resistance_levels if r > nearest_resistance]
                                if higher_resistances:
                                    gtt_opp['target_2'] = min(higher_resistances)
                                    gtt_opp['target_2_percent'] = ((gtt_opp['target_2'] / current_price) - 1) * 100
                            
                            # Add to opportunities list
                            self.recommendations['gtt_opportunities'].append(gtt_opp)
                            
                    except Exception as e:
                        logging.error(f"Error processing opportunity for {symbol}: {e}")
                
                logging.info(f"Generated {len(self.recommendations['gtt_opportunities'])} new GTT opportunities")
                return True
            else:
                logging.warning("No opportunities found")
                return False
                
        except Exception as e:
            logging.error(f"Error scanning for opportunities: {e}")
            return False

    def generate_report(self, output_file="reports/portfolio_analysis.xlsx"):
        """
        Generate Excel report with all analysis and recommendations
        """
        try:
            # Create Excel writer
            writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
            
            # Portfolio summary
            if self.portfolio_data is not None:
                self.portfolio_data.to_excel(writer, sheet_name='Portfolio Summary', index=False)
            
            # Portfolio metrics
            metrics = self.calculate_portfolio_metrics()
            if metrics:
                metrics_df = pd.DataFrame([metrics])
                metrics_df.to_excel(writer, sheet_name='Portfolio Metrics', index=False)
            
            # GTT recommendations for existing positions
            if self.recommendations['existing_positions_gtt']:
                gtt_df = pd.DataFrame(self.recommendations['existing_positions_gtt'])
                gtt_df.to_excel(writer, sheet_name='Portfolio GTT', index=False)
            
            # New opportunities
            if self.recommendations['gtt_opportunities']:
                opp_df = pd.DataFrame(self.recommendations['gtt_opportunities'])
                opp_df.to_excel(writer, sheet_name='New Opportunities', index=False)
            
            # Save Excel file
            writer.close()
            
            logging.info(f"Generated portfolio report: {output_file}")
            print(f"Generated portfolio report: {output_file}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating report: {e}")
            return False

    # ================= Rebalancing Logic =================#
    def compute_rebalance_plan(self, additional_capital: float = 0.0, max_positions: int = None,
                                min_weight: float = 0.0, max_weight: float = 0.25,
                                score_field: str = 'overall_score', exit_threshold: float = 0.0,
                                round_lots: int = 1):
        """Compute a target allocation and trade list to rebalance portfolio.

        Parameters:
            additional_capital: Extra cash (₹) to deploy.
            max_positions: Cap on number of holdings after rebalance (highest scores kept). None = no cap.
            min_weight: Minimum target weight for a position to keep (positions with target < min_weight AND
                        producing very small allocation will be candidates to exit if below exit_threshold).
            max_weight: Maximum weight any single position can have.
            score_field: Field in analysis results to drive weighting (default overall_score).
            exit_threshold: If computed target weight < this, recommend full exit.
            round_lots: Quantity step to round trade share counts (1 = no change, 5 / 10 for lot sizing).

        Produces self.rebalance_plan dict with keys:
            'plan_df' (DataFrame), 'summary' (dict)
        """
        if self.portfolio_data is None:
            logging.error("No portfolio loaded for rebalancing")
            return None
        if not hasattr(self, 'results') or not self.results:
            logging.error("No analysis results. Run analyze_portfolio() first.")
            return None

        try:
            # Build scores DataFrame
            score_rows = []
            for r in self.results:
                symbol = r.get('symbol')
                score = r.get(score_field)
                # Fallback blend if missing chosen score
                if score is None:
                    fund = r.get('fundamental_score', 50)
                    tech = r.get('enhanced_short_term_score', r.get('short_term_score', 50))
                    score = 0.6 * fund + 0.4 * tech
                score_rows.append({'Symbol': symbol, 'Score': float(score or 0)})
            scores_df = pd.DataFrame(score_rows).groupby('Symbol', as_index=False)['Score'].mean()

            # Merge with current holdings
            holdings = self.portfolio_data.copy()
            if 'Current Value' not in holdings.columns:
                # Ensure current metrics
                if 'Quantity' in holdings.columns and 'Current Price' in holdings.columns:
                    holdings['Current Value'] = holdings['Quantity'] * holdings['Current Price']
                else:
                    holdings['Current Value'] = 0.0
            holdings = holdings.merge(scores_df, on='Symbol', how='left')
            holdings['Score'] = holdings['Score'].fillna(0)

            # Optionally restrict to top N by score
            if max_positions is not None and max_positions > 0 and len(holdings) > max_positions:
                top_symbols = holdings.sort_values('Score', ascending=False).head(max_positions)['Symbol']
                holdings['Kept'] = holdings['Symbol'].isin(top_symbols)
            else:
                holdings['Kept'] = True

            # Compute target weights proportional to score (use minimum epsilon for zero scores to keep if Kept)
            kept_df = holdings[holdings['Kept']].copy()
            # Avoid all-zero division
            if kept_df['Score'].sum() <= 0:
                kept_df['AdjScore'] = 1.0  # equal weight fallback
            else:
                kept_df['AdjScore'] = kept_df['Score']

            kept_df['RawWeight'] = kept_df['AdjScore'] / kept_df['AdjScore'].sum()

            # Apply max_weight cap iteratively
            def apply_caps(weights_series, cap):
                w = weights_series.copy()
                changed = True
                while changed:
                    changed = False
                    over = w[w > cap]
                    if not over.empty:
                        excess = (over - cap).sum()
                        w[over.index] = cap
                        under = w[w < cap]
                        if under.sum() > 0:
                            w[under.index] += (under / under.sum()) * excess
                        changed = True
                return w

            kept_df['CappedWeight'] = apply_caps(kept_df['RawWeight'], max_weight)

            # Enforce min_weight by flagging exits if below both min_weight and exit_threshold
            kept_df['TargetWeight'] = kept_df['CappedWeight']
            kept_df['ExitFlag'] = False
            if min_weight > 0:
                below = kept_df['TargetWeight'] < min_weight
                kept_df.loc[below, 'TargetWeight'] = min_weight
                # Re-normalize if any raised
                total = kept_df['TargetWeight'].sum()
                kept_df['TargetWeight'] = kept_df['TargetWeight'] / total
            if exit_threshold > 0:
                kept_df.loc[kept_df['TargetWeight'] < exit_threshold, 'ExitFlag'] = True

            # Combine with dropped holdings (set target weight 0)
            dropped = holdings[~holdings['Kept']].copy()
            if not dropped.empty:
                dropped['TargetWeight'] = 0.0
                dropped['ExitFlag'] = True
                combined = pd.concat([kept_df, dropped], ignore_index=True)
            else:
                combined = kept_df

            # Normalize target weights over non-exit positions
            stay_mask = ~combined['ExitFlag']
            total_target_non_exit = combined.loc[stay_mask, 'TargetWeight'].sum()
            if total_target_non_exit > 0:
                combined.loc[stay_mask, 'TargetWeight'] = combined.loc[stay_mask, 'TargetWeight'] / total_target_non_exit

            # Determine capital base
            current_total_value = holdings['Current Value'].sum()
            target_total_capital = current_total_value + additional_capital

            # Compute target values & trades
            combined['CurrentValue'] = combined['Current Value'].fillna(0)
            combined['CurrentPrice'] = combined.get('Current Price', pd.Series([None]*len(combined)))
            combined['TargetValue'] = combined.apply(lambda r: 0 if r['ExitFlag'] else r['TargetWeight'] * target_total_capital, axis=1)
            combined['DeltaValue'] = combined['TargetValue'] - combined['CurrentValue']
            # Avoid division by zero; if price missing set trade quantity 0
            combined['TradeQtyRaw'] = combined.apply(lambda r: (r['DeltaValue'] / r['CurrentPrice']) if (r.get('CurrentPrice') and r['CurrentPrice'] > 0) else 0, axis=1)
            combined['TradeQty'] = combined['TradeQtyRaw'].apply(lambda q: int(round(q / round_lots) * round_lots))
            combined['Action'] = combined['TradeQty'].apply(lambda q: 'BUY' if q > 0 else ('SELL' if q < 0 else 'HOLD'))
            combined.loc[combined['ExitFlag'] & (combined['TradeQty'] == 0) & (combined['CurrentValue'] > 0), 'Action'] = 'SELL'

            # Compute post-trade allocation estimation
            combined['PostValueEst'] = combined['CurrentValue'] + (combined['TradeQty'] * combined['CurrentPrice'].fillna(0))
            stay_total_post = combined.loc[combined['PostValueEst'] > 0, 'PostValueEst'].sum()
            combined['PostWeightEst'] = combined.apply(lambda r: (r['PostValueEst'] / stay_total_post) if stay_total_post > 0 and r['PostValueEst'] > 0 else 0, axis=1)

            buy_cost = (combined[combined['Action'] == 'BUY']['TradeQty'] * combined[combined['Action'] == 'BUY']['CurrentPrice']).sum()
            sell_proceeds = -(combined[combined['Action'] == 'SELL']['TradeQty'] * combined[combined['Action'] == 'SELL']['CurrentPrice']).sum()
            net_cash_needed = buy_cost - sell_proceeds
            remaining_cash = additional_capital - net_cash_needed

            summary = {
                'current_total_value': round(current_total_value, 2),
                'additional_capital': round(additional_capital, 2),
                'target_total_capital': round(target_total_capital, 2),
                'buy_cost': round(buy_cost, 2),
                'sell_proceeds': round(sell_proceeds, 2),
                'net_cash_needed': round(net_cash_needed, 2),
                'remaining_cash': round(remaining_cash, 2),
                'positions_after': int((combined['PostValueEst'] > 0).sum())
            }

            self.rebalance_plan = {
                'plan_df': combined.sort_values('Action', ascending=False),
                'summary': summary
            }
            logging.info(f"Rebalance plan created. Net cash needed: ₹{summary['net_cash_needed']:.2f}")
            return self.rebalance_plan
        except Exception as e:
            logging.error(f"Error computing rebalance plan: {e}")
            return None

    def export_rebalance_plan(self, file_path: str = 'reports/rebalance_plan.csv'):
        """Export the rebalance plan to CSV (plan + summary)."""
        if not hasattr(self, 'rebalance_plan') or self.rebalance_plan is None:
            logging.error("No rebalance plan to export. Run compute_rebalance_plan first.")
            return False
        try:
            plan_df = self.rebalance_plan['plan_df'].copy()
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            plan_df.to_csv(file_path, index=False)
            # Write summary as separate file for clarity
            summary_path = file_path.replace('.csv', '_summary.json')
            with open(summary_path, 'w') as f:
                json.dump(self.rebalance_plan['summary'], f, indent=2)
            logging.info(f"Rebalance plan exported: {file_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to export rebalance plan: {e}")
            return False

    # ================= Integration with Top 200 Report =================#
    def _find_latest_top200_report(self, reports_dir: str = 'reports'):
        pattern = os.path.join(reports_dir, 'Stock_Report_*.xlsx')
        files = glob.glob(pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def load_top200_report(self, report_path: str = None):
        """Load the latest (or specified) Top 200 analysis Excel report.

        Returns DataFrame or None.
        """
        try:
            if report_path is None:
                report_path = self._find_latest_top200_report()
            if report_path is None or not os.path.exists(report_path):
                logging.error("Top 200 report not found.")
                return None
            # Prefer Summary sheet; fallback to Combined Score
            for sheet in ['Summary', 'Combined Score', 'summary', 'SUMMARY']:
                try:
                    df = pd.read_excel(report_path, sheet_name=sheet)
                    if 'Symbol' in df.columns or 'symbol' in df.columns:
                        # Normalize column names lower-case for internal use
                        df.columns = [c.strip() for c in df.columns]
                        return df
                except Exception:
                    continue
            logging.error("Could not find usable sheet in report.")
            return None
        except Exception as e:
            logging.error(f"Error loading top200 report: {e}")
            return None

    def generate_recommendations_from_report(self, report_df: pd.DataFrame, max_new: int = 5,
                                              min_add_score: float = 70, min_hold_score: float = 55):
        """Derive portfolio action recommendations using an existing top200 report DataFrame.

        Produces:
            self.portfolio_actions (list of dict) for existing holdings
            self.new_opportunities (list of dict) for potential adds
        """
        if report_df is None or report_df.empty or self.portfolio_data is None:
            logging.error("Cannot generate recommendations: missing report or portfolio")
            return False

        # Normalize symbol column
        if 'Symbol' in report_df.columns:
            report_df['symbol_norm'] = report_df['Symbol']
        elif 'symbol' in report_df.columns:
            report_df['symbol_norm'] = report_df['symbol']
        else:
            logging.error("Report lacks Symbol column")
            return False

        # Extract score columns with fallbacks
        score_candidates = ['overall_score_triple', 'Overall Score', 'OverallScore', 'overall_score_balanced']
        def extract_score(row):
            for c in score_candidates:
                if c in row and pd.notna(row[c]):
                    try:
                        return float(row[c])
                    except Exception:
                        continue
            return 0.0

        # Build mapping symbol -> row dict for quick lookup
        report_map = {}
        for _, r in report_df.iterrows():
            sym = str(r['symbol_norm']).strip().upper()
            report_map[sym] = r

        portfolio_actions = []
        for _, pos in self.portfolio_data.iterrows():
            sym = str(pos['Symbol']).strip().upper()
            row = report_map.get(sym)
            if row is None:
                portfolio_actions.append({
                    'Symbol': sym,
                    'Action': 'NO DATA',
                    'Reason': 'Not in top200 analysis',
                })
                continue
            score = extract_score(row)
            rec_text = str(row.get('final_recommendation', row.get('Recommendation', '')))
            # Clean emojis
            for em in ['🟢','🟡','🟠','🔴','🔵']:
                rec_text = rec_text.replace(em, '').strip()

            # Determine action
            if score >= 75:
                action = 'ADD / ACCUMULATE'
                reason = f'Strong score {score:.1f}'
            elif score >= min_hold_score:
                action = 'HOLD'
                reason = f'Stable score {score:.1f}'
            elif score >= 45:
                action = 'REVIEW / TRIM'
                reason = f'Weak score {score:.1f}'
            else:
                action = 'EXIT'
                reason = f'Poor score {score:.1f}'

            # Attempt support/resistance parsing for levels
            support_raw = row.get('enhanced_support_levels') or row.get('support_levels')
            resistance_raw = row.get('enhanced_resistance_levels') or row.get('resistance_levels')
            def parse_levels(raw):
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    return []
                if isinstance(raw, list):
                    return raw
                try:
                    txt = str(raw).replace("'", '"')
                    vals = json.loads(txt)
                    return vals if isinstance(vals, list) else []
                except Exception:
                    return []
            supports = [float(x) for x in parse_levels(support_raw) if str(x).replace('.','',1).isdigit()]
            resistances = [float(x) for x in parse_levels(resistance_raw) if str(x).replace('.','',1).isdigit()]
            supports = sorted(set(supports))
            resistances = sorted(set(resistances))
            current_price = row.get('current_price') or pos.get('Current Price')
            stop = None
            target = None
            if current_price and isinstance(current_price, (int,float)):
                lower_supports = [s for s in supports if s < current_price]
                higher_res = [r for r in resistances if r > current_price]
                if lower_supports:
                    stop = max(lower_supports)
                if higher_res:
                    target = min(higher_res)
            portfolio_actions.append({
                'Symbol': sym,
                'Score': round(score,1),
                'Report Recommendation': rec_text,
                'Action': action,
                'Reason': reason,
                'Current Price': current_price,
                'Stop (Nearest Support)': stop,
                'Target (Nearest Resistance)': target
            })

        # New opportunities
        held_symbols = set([str(s).upper() for s in self.portfolio_data['Symbol']])
        candidates = []
        for sym, row in report_map.items():
            if sym in held_symbols:
                continue
            score = extract_score(row)
            rec_text = str(row.get('final_recommendation', row.get('Recommendation', '')))
            for em in ['🟢','🟡','🟠','🔴','🔵']:
                rec_text = rec_text.replace(em, '').strip()
            if score >= min_add_score and 'BUY' in rec_text.upper():
                # Levels
                support_raw = row.get('enhanced_support_levels') or row.get('support_levels')
                resistance_raw = row.get('enhanced_resistance_levels') or row.get('resistance_levels')
                supports = [float(x) for x in parse_levels(support_raw) if str(x).replace('.','',1).isdigit()]
                resistances = [float(x) for x in parse_levels(resistance_raw) if str(x).replace('.','',1).isdigit()]
                supports = sorted(set(supports))
                resistances = sorted(set(resistances))
                current_price = row.get('current_price')
                # Choose primary entry: first support below price if exists else current
                entry = None
                stop = None
                target = None
                if current_price and isinstance(current_price,(int,float)):
                    below = [s for s in supports if s < current_price]
                    entry = max(below) if below else current_price
                    stop_candidates = [s for s in supports if s < (entry or current_price)]
                    if stop_candidates:
                        stop = max(stop_candidates)
                    above = [r for r in resistances if r > current_price]
                    if above:
                        target = min(above)
                candidates.append({
                    'Symbol': sym,
                    'Score': round(score,1),
                    'Report Recommendation': rec_text,
                    'Suggested Entry': entry,
                    'Stop (Support)': stop,
                    'Target (Resistance)': target
                })
        # Sort and limit
        candidates.sort(key=lambda x: x['Score'], reverse=True)
        candidates = candidates[:max_new]

        self.portfolio_actions = portfolio_actions
        self.new_opportunities = candidates
        logging.info(f"Generated actions for {len(portfolio_actions)} holdings and {len(candidates)} new opportunities")
        return True

    def export_recommendations(self, actions_path='reports/portfolio_actions.csv', opportunities_path='reports/new_opportunities.csv'):
        if hasattr(self, 'portfolio_actions') and self.portfolio_actions:
            try:
                pd.DataFrame(self.portfolio_actions).to_csv(actions_path, index=False)
                logging.info(f"Exported portfolio actions: {actions_path}")
            except Exception as e:
                logging.error(f"Failed exporting portfolio actions: {e}")
        if hasattr(self, 'new_opportunities') and self.new_opportunities:
            try:
                pd.DataFrame(self.new_opportunities).to_csv(opportunities_path, index=False)
                logging.info(f"Exported new opportunities: {opportunities_path}")
            except Exception as e:
                logging.error(f"Failed exporting opportunities: {e}")
        return True


def main():
    """Main function to run portfolio analysis from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Stock Portfolio Analyzer')
    parser.add_argument('--portfolio', '-p', help='Path to portfolio CSV file')
    parser.add_argument('--create-template', '-t', action='store_true', 
                        help='Create a portfolio template file')
    parser.add_argument('--opportunities', '-o', help='Path to stock list CSV for finding new opportunities')
    parser.add_argument('--output', help='Output file path for the analysis report')
    
    args = parser.parse_args()
    
    portfolio_analyzer = PortfolioAnalyzer(args.portfolio)
    
    if args.create_template:
        portfolio_analyzer.create_portfolio_template()
        return
    
    if args.portfolio:
        # Update portfolio with current prices
        portfolio_analyzer.update_current_prices()
        
        # Calculate portfolio metrics
        portfolio_analyzer.calculate_portfolio_metrics()
        
        # Run detailed analysis
        portfolio_analyzer.analyze_portfolio_stocks()
        
        # Generate GTT recommendations
        portfolio_analyzer.generate_gtt_recommendations()
    
    if args.opportunities:
        # Scan for new opportunities
        portfolio_analyzer.scan_for_new_opportunities(args.opportunities)
    
    # Generate final report
    output_file = args.output if args.output else "reports/portfolio_analysis.xlsx"
    portfolio_analyzer.generate_report(output_file)


if __name__ == "__main__":
    main()
