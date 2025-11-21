"""
🎓 ML MODEL TRAINING SCRIPT
Collects historical stock data and trains the ML price predictor
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import pickle
from pathlib import Path
from ml_predictor import get_ml_predictor
from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'data/ml_training_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

class MLTrainer:
    """Train ML model with historical stock data"""
    
    def __init__(self, lookback_days=180, forward_days=5):
        """
        Args:
            lookback_days: Days of historical data to analyze
            forward_days: Days ahead to predict price movement
        """
        self.lookback_days = lookback_days
        self.forward_days = forward_days
        self.predictor = get_ml_predictor()
        self.training_data = []
        self.labels = []
        
    def load_stock_list(self, csv_file='stock_list_template.csv', test_mode=False):
        """Load stocks from CSV"""
        try:
            df = pd.read_csv(csv_file)
            if 'Symbol' in df.columns:
                symbols = df['Symbol'].dropna().tolist()
                logging.info(f"Loaded {len(symbols)} stocks from {csv_file}")
                if test_mode:
                    return symbols[:2]  # Use only 2 stocks for testing
                return symbols[:50]  # Use top 50 for training
            return []
        except Exception as e:
            logging.error(f"Error loading stock list: {e}")
            return []
    
    def collect_historical_data(self, symbol, end_date):
        """
        Collect historical stock data for a specific date
        
        Returns:
            tuple: (stock_data_dict, future_return)
        """
        try:
            # Get data from lookback_days before end_date
            start_date = end_date - timedelta(days=self.lookback_days)
            ticker = yf.Ticker(f"{symbol}.NS")
            
            # Get historical prices
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=self.forward_days + 10))
            
            if len(hist) < 30:  # Need minimum data
                logging.debug(f"{symbol}: Insufficient history ({len(hist)} days)")
                return None, None
            
            # Get price at end_date and forward_days later
            end_date_str = end_date.strftime('%Y-%m-%d')
            future_date = end_date + timedelta(days=self.forward_days)
            
            # Find closest dates in data
            hist_dates = hist.index
            
            # Convert end_date to timezone-aware if hist_dates is timezone-aware
            search_date = end_date
            if hist_dates.tz is not None:
                # Make search_date timezone-aware using pandas
                search_date = pd.Timestamp(search_date).tz_localize(hist_dates.tz)
            
            end_idx = hist_dates.get_indexer([search_date], method='nearest')[0]
            
            if end_idx >= len(hist) - self.forward_days - 5:
                logging.debug(f"{symbol}: Not enough future data (end_idx={end_idx}, hist_len={len(hist)})")
                return None, None  # Not enough future data
            
            current_price = hist.iloc[end_idx]['Close']
            
            # Get future price (5 days ahead)
            future_idx = min(end_idx + self.forward_days, len(hist) - 1)
            future_price = hist.iloc[future_idx]['Close']
            
            # Calculate return
            price_return = ((future_price - current_price) / current_price) * 100
            
            # Label: UP (+2%+), HOLD (-2% to +2%), DOWN (-2%-) 
            if price_return > 2.0:
                label = 1  # UP
            elif price_return < -2.0:
                label = -1  # DOWN
            else:
                label = 0  # HOLD
            
            # Build stock_data dict for feature extraction
            stock_data = {
                'symbol': symbol,
                'current_price': float(current_price),
                'analysis_date': end_date_str
            }
            
            # Add historical price features
            if len(hist) >= end_idx + 1:
                hist_slice = hist.iloc[:end_idx + 1]
                
                # Calculate technical indicators from historical data
                closes = hist_slice['Close'].values
                volumes = hist_slice['Volume'].values
                
                if len(closes) >= 50:
                    # RSI
                    deltas = np.diff(closes)
                    gains = np.where(deltas > 0, deltas, 0)
                    losses = np.where(deltas < 0, -deltas, 0)
                    avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
                    avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0
                    rs = avg_gain / avg_loss if avg_loss != 0 else 0
                    rsi = 100 - (100 / (1 + rs))
                    stock_data['real_rsi'] = rsi
                    stock_data['enhanced_rsi_14'] = rsi
                    
                    # Moving averages
                    stock_data['ma_20'] = np.mean(closes[-20:]) if len(closes) >= 20 else current_price
                    stock_data['ma_50'] = np.mean(closes[-50:]) if len(closes) >= 50 else current_price
                    
                    # Price changes
                    stock_data['enhanced_price_change_1d'] = ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0
                    stock_data['enhanced_price_change_5d'] = ((closes[-1] - closes[-6]) / closes[-6] * 100) if len(closes) >= 6 else 0
                    stock_data['enhanced_price_change_20d'] = ((closes[-1] - closes[-21]) / closes[-21] * 100) if len(closes) >= 21 else 0
                    
                    # Volatility
                    returns = np.diff(closes) / closes[:-1]
                    stock_data['volatility_20d'] = np.std(returns[-20:]) * 100 if len(returns) >= 20 else 0
                    
                    # Volume
                    stock_data['avg_volume'] = np.mean(volumes[-20:]) if len(volumes) >= 20 else 0
                    stock_data['enhanced_volume_ratio'] = volumes[-1] / stock_data['avg_volume'] if stock_data['avg_volume'] > 0 else 1
                    
                    # 52-week high
                    stock_data['52_week_high'] = np.max(closes[-252:]) if len(closes) >= 252 else np.max(closes)
            
            # Try to get fundamental data (may not be available for all dates)
            try:
                fund_data = get_comprehensive_stock_data(symbol)
                if fund_data:
                    for key in ['pe_ratio', 'pb_ratio', 'debt_to_equity', 'roe', 'roa', 
                               'profit_margin', 'dividend_yield', 'current_ratio']:
                        if key in fund_data:
                            stock_data[key] = fund_data[key]
            except:
                pass  # Skip if fundamental data unavailable
            
            # Set defaults for missing fields
            defaults = {
                'enhanced_macd': 0, 'enhanced_signal_line': 0, 'enhanced_bb_position': 0.5,
                'enhanced_bb_width': 0, 'enhanced_atr_14': 0, 'enhanced_adx': 0,
                'enhanced_cci': 0, 'enhanced_stoch_k': 50, 'enhanced_stoch_d': 50,
                'enhanced_williams_r': -50, 'enhanced_roc': 0, 'enhanced_mfi': 50,
                'enhanced_obv_trend': 0, 'enhanced_vwap_distance': 0,
                'enhanced_price_vs_ma20': 0, 'price_momentum_5d': 0, 'price_momentum_20d': 0,
                'enhanced_price_change_50d': 0, 'volatility_6m': 0, 'enhanced_high_low_range': 0,
                'volume_spike': 0, 'enhanced_volume_trend': 0, 'enhanced_volume_volatility': 0,
                'volume_ma_ratio': 1, 'enhanced_obv': 0, 'pe_ratio': 15, 'pb_ratio': 3,
                'debt_to_equity': 1, 'current_ratio': 1.5, 'roe': 15, 'roa': 10,
                'profit_margin': 10, 'operating_margin': 15, 'revenue_growth': 10,
                'earnings_growth': 10, 'dividend_yield': 2, 'free_cash_flow': 0,
                'book_value_per_share': 0, 'price_to_sales': 3, 'enterprise_value': 0,
                'institutional_score': 50, 'fii_activity': 0, 'dii_activity': 0,
                'mtf_trend_strength': 50, 'mtf_momentum_strength': 50,
                'mtf_timeframe_agreement': 50, 'real_technical_score': 50,
                'daily_trend': 0, 'weekly_trend': 0, 'monthly_trend': 0,
                'mtf_composite_score': 50, 'advanced_technical_score_final': 50
            }
            
            for key, default_val in defaults.items():
                if key not in stock_data:
                    stock_data[key] = default_val
            
            return stock_data, label
            
        except Exception as e:
            logging.debug(f"Error collecting data for {symbol} at {end_date}: {e}")
            return None, None
    
    def collect_training_data(self, symbols, num_samples_per_stock=10):
        """
        Collect training data from multiple stocks and time periods
        
        Args:
            symbols: List of stock symbols
            num_samples_per_stock: Number of historical samples per stock
        """
        logging.info(f"Collecting training data from {len(symbols)} stocks...")
        
        successful_samples = 0
        failed_samples = 0
        
        for i, symbol in enumerate(symbols):
            logging.info(f"Processing {symbol} ({i+1}/{len(symbols)})...")
            
            # Sample different dates over the past year
            # Need to ensure we have forward_days of data after each sample date
            end_date = datetime.now()
            date_samples = []
            
            for j in range(num_samples_per_stock):
                # Sample dates from (forward_days + 10) to 365 days ago
                # This ensures we have future data to calculate returns
                min_days_ago = self.forward_days + 10  # At least 15 days ago
                max_days_ago = 365
                days_ago = min_days_ago + (j * (max_days_ago - min_days_ago) // num_samples_per_stock)
                sample_date = end_date - timedelta(days=days_ago)
                date_samples.append(sample_date)
            
            for sample_date in date_samples:
                stock_data, label = self.collect_historical_data(symbol, sample_date)
                
                if stock_data and label is not None:
                    # Extract features
                    features = self.predictor.prepare_features(stock_data)
                    
                    if features is not None:
                        self.training_data.append(features)
                        self.labels.append(label)
                        successful_samples += 1
                    else:
                        logging.warning(f"{symbol}: prepare_features returned None")
                        failed_samples += 1
                else:
                    if stock_data is None:
                        logging.debug(f"{symbol}: No stock_data collected for {sample_date.strftime('%Y-%m-%d')}")
                    elif label is None:
                        logging.debug(f"{symbol}: Label is None for {sample_date.strftime('%Y-%m-%d')}")
                    failed_samples += 1
        
        logging.info(f"Collected {successful_samples} training samples")
        logging.info(f"Failed to collect {failed_samples} samples")
        logging.info(f"Label distribution: UP={sum(1 for l in self.labels if l == 1)}, "
                    f"HOLD={sum(1 for l in self.labels if l == 0)}, "
                    f"DOWN={sum(1 for l in self.labels if l == -1)}")
    
    def train_model(self):
        """Train the ML model with collected data"""
        if len(self.training_data) < 50:
            logging.error("Insufficient training data. Need at least 50 samples.")
            return False
        
        logging.info(f"Training ML model with {len(self.training_data)} samples...")
        
        success = self.predictor.train_model(self.training_data, self.labels)
        
        if success:
            # Save trained model
            model_dir = Path('models')
            model_dir.mkdir(exist_ok=True)
            
            model_path = model_dir / f'ml_predictor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pkl'
            
            with open(model_path, 'wb') as f:
                pickle.dump({
                    'model': self.predictor.model,
                    'scaler': self.predictor.scaler,
                    'trained_date': datetime.now().isoformat(),
                    'num_samples': len(self.training_data),
                    'label_distribution': {
                        'UP': sum(1 for l in self.labels if l == 1),
                        'HOLD': sum(1 for l in self.labels if l == 0),
                        'DOWN': sum(1 for l in self.labels if l == -1)
                    }
                }, f)
            
            logging.info(f"Model saved to {model_path}")
            
            # Also save as latest
            latest_path = model_dir / 'ml_predictor_latest.pkl'
            with open(latest_path, 'wb') as f:
                pickle.dump({
                    'model': self.predictor.model,
                    'scaler': self.predictor.scaler,
                    'trained_date': datetime.now().isoformat(),
                    'num_samples': len(self.training_data)
                }, f)
            
            logging.info(f"Latest model saved to {latest_path}")
            
        return success

def main():
    """Main training function"""
    import sys
    
    # Check for test mode
    test_mode = '--test' in sys.argv
    
    print("=" * 80)
    print("ML MODEL TRAINING - Stock Price Prediction")
    if test_mode:
        print("(TEST MODE - 2 stocks only)")
    print("=" * 80)
    
    # Enable debug logging in test mode
    if test_mode:
        logging.getLogger().setLevel(logging.DEBUG)
    
    trainer = MLTrainer(lookback_days=180, forward_days=5)
    
    # Load stocks
    symbols = trainer.load_stock_list(test_mode=test_mode)
    
    if not symbols:
        print("No stocks found. Please check stock_list_template.csv")
        return
    
    print(f"Training on {len(symbols)} stocks")
    if not test_mode:
        print(f"⏱️  This may take 10-15 minutes...")
    print()
    
    # Collect training data (fewer samples in test mode)
    num_samples = 3 if test_mode else 10
    trainer.collect_training_data(symbols, num_samples_per_stock=num_samples)
    
    # Train model
    if trainer.train_model():
        print()
        print("=" * 80)
        print("ML MODEL TRAINING COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("   1. Run: python validate_ml_model.py")
        print("   2. Test with: python analyze_top200_stocks_enhanced.py -n 5 -b 5")
        print()
    else:
        print()
        print("=" * 80)
        print("ML MODEL TRAINING FAILED")
        print("=" * 80)

if __name__ == '__main__':
    main()
