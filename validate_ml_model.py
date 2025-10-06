"""
📊 ML MODEL VALIDATION SCRIPT
Tests the trained ML model and measures accuracy
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from pathlib import Path
import pickle
from ml_predictor import get_ml_predictor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MLValidator:
    """Validate ML model performance"""
    
    def __init__(self):
        self.predictor = get_ml_predictor()
        self.validation_results = []
        
    def load_validation_stocks(self, csv_file='stock_list_template.csv', num_stocks=20):
        """Load stocks for validation (different from training set)"""
        try:
            df = pd.read_csv(csv_file)
            if 'Symbol' in df.columns:
                symbols = df['Symbol'].dropna().tolist()
                # Use stocks 51-70 for validation (different from training set 1-50)
                return symbols[50:50+num_stocks]
            return []
        except Exception as e:
            logging.error(f"Error loading validation stocks: {e}")
            return []
    
    def validate_prediction(self, symbol, test_date):
        """
        Make a prediction and validate against actual price movement
        
        Returns:
            dict: validation results
        """
        try:
            # Get data up to test_date
            start_date = test_date - timedelta(days=180)
            end_date = test_date + timedelta(days=10)  # Need future data
            
            ticker = yf.Ticker(f"{symbol}.NS")
            hist = ticker.history(start=start_date, end=end_date)
            
            if len(hist) < 30:
                return None
            
            # Find test date index
            # Convert test_date to timezone-aware if hist.index is timezone-aware
            search_date = test_date
            if hist.index.tz is not None:
                search_date = pd.Timestamp(test_date).tz_localize(hist.index.tz)
            
            test_idx = hist.index.get_indexer([search_date], method='nearest')[0]
            
            if test_idx >= len(hist) - 7:
                return None  # Not enough future data
            
            current_price = hist.iloc[test_idx]['Close']
            future_price = hist.iloc[test_idx + 5]['Close']  # 5 days ahead
            
            actual_return = ((future_price - current_price) / current_price) * 100
            
            # Actual label
            if actual_return > 2.0:
                actual_label = 1  # UP
            elif actual_return < -2.0:
                actual_label = -1  # DOWN
            else:
                actual_label = 0  # HOLD
            
            # Build stock_data for prediction (simplified for validation)
            closes = hist.iloc[:test_idx + 1]['Close'].values
            volumes = hist.iloc[:test_idx + 1]['Volume'].values
            
            stock_data = {
                'symbol': symbol,
                'current_price': float(current_price),
                'real_rsi': self._calculate_rsi(closes),
                'enhanced_rsi_14': self._calculate_rsi(closes),
                'ma_20': np.mean(closes[-20:]) if len(closes) >= 20 else current_price,
                'ma_50': np.mean(closes[-50:]) if len(closes) >= 50 else current_price,
                'enhanced_price_change_5d': ((closes[-1] - closes[-6]) / closes[-6] * 100) if len(closes) >= 6 else 0,
                'avg_volume': np.mean(volumes[-20:]) if len(volumes) >= 20 else 0,
                '52_week_high': np.max(closes[-252:]) if len(closes) >= 252 else np.max(closes)
            }
            
            # Set defaults for other features
            defaults = {
                'enhanced_macd': 0, 'enhanced_signal_line': 0, 'enhanced_bb_position': 0.5,
                'enhanced_bb_width': 0, 'enhanced_atr_14': 0, 'enhanced_adx': 0,
                'enhanced_cci': 0, 'enhanced_stoch_k': 50, 'enhanced_stoch_d': 50,
                'enhanced_williams_r': -50, 'enhanced_roc': 0, 'enhanced_mfi': 50,
                'enhanced_obv_trend': 0, 'enhanced_vwap_distance': 0,
                'enhanced_price_vs_ma20': 0, 'price_momentum_5d': 0, 'price_momentum_20d': 0,
                'enhanced_price_change_1d': 0, 'enhanced_price_change_20d': 0,
                'enhanced_price_change_50d': 0, 'volatility_20d': 0, 'volatility_6m': 0,
                'enhanced_high_low_range': 0, 'enhanced_volume_ratio': 1,
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
            
            for key, val in defaults.items():
                if key not in stock_data:
                    stock_data[key] = val
            
            # Make prediction
            prediction_result = self.predictor.predict_price_movement(stock_data)
            
            if prediction_result:
                predicted_label = prediction_result['prediction']
                confidence = prediction_result['confidence']
                
                # Check if prediction matches actual
                correct = (predicted_label == actual_label)
                
                return {
                    'symbol': symbol,
                    'date': test_date.strftime('%Y-%m-%d'),
                    'current_price': current_price,
                    'future_price': future_price,
                    'actual_return': actual_return,
                    'actual_label': actual_label,
                    'predicted_label': predicted_label,
                    'confidence': confidence,
                    'signal': prediction_result['signal'],
                    'correct': correct,
                    'correct_direction': (np.sign(predicted_label) == np.sign(actual_label)) or (predicted_label == 0 and abs(actual_return) < 2)
                }
            
            return None
            
        except Exception as e:
            logging.debug(f"Error validating {symbol} at {test_date}: {e}")
            return None
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def run_validation(self, symbols, num_tests_per_stock=5):
        """Run validation on multiple stocks"""
        logging.info(f"📊 Validating ML model on {len(symbols)} stocks...")
        
        total_tests = 0
        successful_tests = 0
        
        for i, symbol in enumerate(symbols):
            logging.info(f"Testing {symbol} ({i+1}/{len(symbols)})...")
            
            # Test on different dates from the past
            test_dates = []
            end_date = datetime.now()
            
            for j in range(num_tests_per_stock):
                days_ago = 15 + (j * 15)  # Test on dates 15, 30, 45, 60, 75 days ago
                test_date = end_date - timedelta(days=days_ago)
                test_dates.append(test_date)
            
            for test_date in test_dates:
                result = self.validate_prediction(symbol, test_date)
                if result:
                    self.validation_results.append(result)
                    total_tests += 1
                    if result['correct']:
                        successful_tests += 1
        
        # Calculate metrics
        self.calculate_metrics()
    
    def calculate_metrics(self):
        """Calculate validation metrics"""
        if not self.validation_results:
            logging.error("No validation results available")
            return
        
        df = pd.DataFrame(self.validation_results)
        
        total = len(df)
        correct_exact = df['correct'].sum()
        correct_direction = df['correct_direction'].sum()
        
        # Accuracy by label
        for label, name in [(1, 'UP'), (0, 'HOLD'), (-1, 'DOWN')]:
            label_df = df[df['actual_label'] == label]
            if len(label_df) > 0:
                accuracy = (label_df['correct'].sum() / len(label_df)) * 100
                logging.info(f"  {name} Accuracy: {accuracy:.1f}% ({label_df['correct'].sum()}/{len(label_df)})")
        
        # Average confidence
        avg_confidence = df['confidence'].mean()
        
        # Confidence vs accuracy
        high_conf = df[df['confidence'] > 60]
        if len(high_conf) > 0:
            high_conf_accuracy = (high_conf['correct'].sum() / len(high_conf)) * 100
            logging.info(f"  High Confidence (>60%) Accuracy: {high_conf_accuracy:.1f}% ({len(high_conf)} predictions)")
        
        print("\n" + "="*80)
        print("📊 ML MODEL VALIDATION RESULTS")
        print("="*80)
        print(f"Total Predictions: {total}")
        print(f"Exact Match Accuracy: {(correct_exact/total)*100:.1f}% ({correct_exact}/{total})")
        print(f"Directional Accuracy: {(correct_direction/total)*100:.1f}% ({correct_direction}/{total})")
        print(f"Average Confidence: {avg_confidence:.1f}%")
        print()
        
        # Distribution of predictions
        print("Prediction Distribution:")
        for label, name in [(1, 'BUY'), (0, 'HOLD'), (-1, 'SELL')]:
            count = (df['predicted_label'] == label).sum()
            print(f"  {name}: {count} ({count/total*100:.1f}%)")
        
        print()
        print("Actual Distribution:")
        for label, name in [(1, 'UP'), (0, 'HOLD'), (-1, 'DOWN')]:
            count = (df['actual_label'] == label).sum()
            print(f"  {name}: {count} ({count/total*100:.1f}%)")
        
        print("="*80)
        
        # Save results
        results_path = Path('models/validation_results.csv')
        df.to_csv(results_path, index=False)
        logging.info(f"✅ Validation results saved to {results_path}")

def main():
    """Main validation function"""
    print("=" * 80)
    print("📊 ML MODEL VALIDATION - Testing Predictions")
    print("=" * 80)
    print()
    
    validator = MLValidator()
    
    if not validator.predictor.is_trained:
        print("❌ No trained model found!")
        print("   Please run: python train_ml_model.py")
        return
    
    print("✅ Trained model loaded successfully")
    print()
    
    # Load validation stocks
    symbols = validator.load_validation_stocks(num_stocks=20)
    
    if not symbols:
        print("❌ No validation stocks found")
        return
    
    print(f"📊 Validating on {len(symbols)} stocks (5 tests each)")
    print(f"⏱️  This may take 5-10 minutes...")
    print()
    
    # Run validation
    validator.run_validation(symbols, num_tests_per_stock=5)

if __name__ == '__main__':
    main()
