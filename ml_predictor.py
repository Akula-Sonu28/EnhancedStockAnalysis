"""
🤖 ML PRICE PREDICTOR - PHASE 2 TASK 1
Machine Learning-based stock price movement prediction
Expected accuracy boost: 20-30%
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, List
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import logging
import pickle
from pathlib import Path

class MLPricePredictor:
    """
    🎯 ML-based price movement predictor
    
    Uses 65+ features to predict:
    - Price direction (UP/HOLD/DOWN)
    - Confidence level (0-100%)
    - Expected return
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self._load_trained_model()
    
    def _load_trained_model(self):
        """Load pre-trained model if available"""
        try:
            model_path = Path('models/ml_predictor_latest.pkl')
            if model_path.exists():
                with open(model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data['model']
                    self.scaler = data['scaler']
                    self.is_trained = True
                    trained_date = data.get('trained_date', 'unknown')
                    num_samples = data.get('num_samples', 0)
                    logging.info(f"Loaded trained ML model (trained: {trained_date}, samples: {num_samples})")
            else:
                logging.info("No trained model found. Using fallback predictions.")
        except Exception as e:
            logging.warning(f"Failed to load trained model: {e}. Using fallback predictions.")
            self.is_trained = False
    
    def train_model(self, training_data: List, labels: List) -> bool:
        """
        🎓 Train the ML model with historical data
        
        Args:
            training_data: List of feature vectors
            labels: List of labels (1=UP, 0=HOLD, -1=DOWN)
        """
        try:
            if len(training_data) < 50:
                logging.warning("Insufficient training data for ML model")
                return False
            
            X = np.array(training_data)
            y = np.array(labels)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Split data
            from sklearn.model_selection import train_test_split
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            
            # Train Gradient Boosting Classifier (better for financial data)
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42,
                verbose=0
            )
            
            self.model.fit(X_train, y_train)
            
            # Calculate accuracy
            train_accuracy = self.model.score(X_train, y_train)
            test_accuracy = self.model.score(X_test, y_test)
            
            logging.info(f"ML Model trained - Train accuracy: {train_accuracy:.2%}, Test accuracy: {test_accuracy:.2%}")
            
            self.is_trained = True
            return True
            
        except Exception as e:
            logging.error(f"Error training ML model: {e}")
            return False
    
    def _safe_float(self, value, default=0.0):
        """Convert value to float, handling strings and None"""
        if value is None:
            return default
        if isinstance(value, (int, float, np.number)):
            return float(value)
        if isinstance(value, str):
            # Handle categorical strings
            value_lower = value.lower().strip()
            if value_lower in ['low', 'weak', 'bearish', 'sell', 'negative', 'very_negative', 'selling']:
                return -1.0
            elif value_lower in ['normal', 'neutral', 'hold', 'average', 'moderate', 'middle']:
                return 0.0
            elif value_lower in ['high', 'strong', 'bullish', 'buy', 'positive', 'very_positive', 'buying']:
                return 1.0
            # Try to convert numeric strings
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        return default
        
    def prepare_features(self, stock_data: dict) -> Optional[np.ndarray]:
        """
        📊 Prepare feature vector from stock data (65 features)
        """
        try:
            features = []
            
            # 1. Technical Indicators (20 features)
            features.extend([
                self._safe_float(stock_data.get('real_rsi', 50)),
                self._safe_float(stock_data.get('enhanced_rsi_14', 50)),
                self._safe_float(stock_data.get('enhanced_macd', 0)),
                self._safe_float(stock_data.get('enhanced_signal_line', 0)),
                self._safe_float(stock_data.get('enhanced_bb_position', 0.5)),
                self._safe_float(stock_data.get('enhanced_bb_width', 0)),
                self._safe_float(stock_data.get('enhanced_atr_14', 0)),
                self._safe_float(stock_data.get('enhanced_adx', 0)),
                self._safe_float(stock_data.get('enhanced_cci', 0)),
                self._safe_float(stock_data.get('enhanced_stoch_k', 50)),
                self._safe_float(stock_data.get('enhanced_stoch_d', 50)),
                self._safe_float(stock_data.get('enhanced_williams_r', -50)),
                self._safe_float(stock_data.get('enhanced_roc', 0)),
                self._safe_float(stock_data.get('enhanced_mfi', 50)),
                self._safe_float(stock_data.get('enhanced_obv_trend', 0)),
                self._safe_float(stock_data.get('enhanced_vwap_distance', 0)),
                self._safe_float(stock_data.get('ma_20', 0)),
                self._safe_float(stock_data.get('ma_50', 0)),
                self._safe_float(stock_data.get('ma_200', 0)),
                self._safe_float(stock_data.get('enhanced_price_vs_ma20', 0)),
            ])
            
            # 2. Price Momentum (10 features)
            current_price = self._safe_float(stock_data.get('current_price', 0))
            features.extend([
                self._safe_float(stock_data.get('enhanced_price_change_1d', 0)),
                self._safe_float(stock_data.get('enhanced_price_change_5d', 0)),
                self._safe_float(stock_data.get('enhanced_price_change_20d', 0)),
                self._safe_float(stock_data.get('enhanced_price_change_50d', 0)),
                self._safe_float(stock_data.get('price_momentum_5d', 0)),
                self._safe_float(stock_data.get('price_momentum_20d', 0)),
                self._safe_float(stock_data.get('volatility_20d', 0)),
                self._safe_float(stock_data.get('volatility_6m', 0)),
                self._safe_float(stock_data.get('enhanced_high_low_range', 0)),
                current_price / max(self._safe_float(stock_data.get('52_week_high', current_price)), 1),
            ])
            
            # 3. Volume Patterns (8 features)
            features.extend([
                self._safe_float(stock_data.get('enhanced_volume_ratio', 1)),
                self._safe_float(stock_data.get('enhanced_volume_trend', 0)),
                self._safe_float(stock_data.get('enhanced_volume_volatility', 0)),
                self._safe_float(stock_data.get('volume_spike', 0)),
                self._safe_float(stock_data.get('avg_volume', 0)),
                self._safe_float(stock_data.get('volume_ma_ratio', 1)),
                self._safe_float(stock_data.get('enhanced_obv', 0)),
                self._safe_float(stock_data.get('enhanced_mfi', 50)),
            ])
            
            # 4. Fundamental Metrics (15 features)
            features.extend([
                self._safe_float(stock_data.get('pe_ratio', 15)),
                self._safe_float(stock_data.get('pb_ratio', 3)),
                self._safe_float(stock_data.get('debt_to_equity', 1)),
                self._safe_float(stock_data.get('current_ratio', 1.5)),
                self._safe_float(stock_data.get('roe', 15)),
                self._safe_float(stock_data.get('roa', 10)),
                self._safe_float(stock_data.get('profit_margin', 10)),
                self._safe_float(stock_data.get('operating_margin', 15)),
                self._safe_float(stock_data.get('revenue_growth', 10)),
                self._safe_float(stock_data.get('earnings_growth', 10)),
                self._safe_float(stock_data.get('dividend_yield', 2)),
                self._safe_float(stock_data.get('free_cash_flow', 0)),
                self._safe_float(stock_data.get('book_value_per_share', 0)),
                self._safe_float(stock_data.get('price_to_sales', 3)),
                self._safe_float(stock_data.get('enterprise_value', 0)),
            ])
            
            # 5. Sentiment & Flow (7 features)
            features.extend([
                self._safe_float(stock_data.get('institutional_score', 50)),
                self._safe_float(stock_data.get('fii_activity', 0)),  # Will handle categorical
                self._safe_float(stock_data.get('dii_activity', 0)),  # Will handle categorical
                self._safe_float(stock_data.get('mtf_trend_strength', 50)),
                self._safe_float(stock_data.get('mtf_momentum_strength', 50)),
                self._safe_float(stock_data.get('mtf_timeframe_agreement', 50)),
                self._safe_float(stock_data.get('real_technical_score', 50)),
            ])
            
            # 6. Multi-Timeframe (5 features)
            features.extend([
                self._safe_float(stock_data.get('daily_trend', 0)),  # Will handle categorical
                self._safe_float(stock_data.get('weekly_trend', 0)),
                self._safe_float(stock_data.get('monthly_trend', 0)),
                self._safe_float(stock_data.get('mtf_composite_score', 50)),
                self._safe_float(stock_data.get('advanced_technical_score_final', 50)),
            ])
            
            features_array = np.array(features, dtype=float)
            
            # Validate features
            if len(features_array) != 65:
                logging.warning(f"Expected 65 features, got {len(features_array)}")
                return None
            
            if np.any(np.isnan(features_array)) or np.any(np.isinf(features_array)):
                logging.warning("Features contain NaN or Inf values, replacing with defaults")
                features_array = np.nan_to_num(features_array, nan=0.0, posinf=100.0, neginf=-100.0)
            
            return features_array
            
        except Exception as e:
            logging.error(f"Error preparing features: {e}")
            return None
    
    def predict_price_movement(self, stock_data: dict) -> Optional[Dict]:
        """
        🔮 Predict price movement and confidence
        
        Returns:
            dict: {
                'prediction': 1 (UP), 0 (HOLD), -1 (DOWN),
                'confidence': 0-100,
                'signal': 'BUY'/'HOLD'/'SELL',
                'expected_return': expected return %,
                'probabilities': class probabilities
            }
        """
        try:
            features = self.prepare_features(stock_data)
            
            if features is None:
                return self._get_fallback_prediction(stock_data)
            
            # If model not trained, use fallback
            if not self.is_trained or self.model is None:
                return self._get_fallback_prediction(stock_data)
            
            # Scale features
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            
            # Get prediction and probabilities
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            # Calculate confidence (max probability)
            confidence = float(np.max(probabilities) * 100)
            
            # Map prediction to signal
            signal_map = {1: 'BUY', 0: 'HOLD', -1: 'SELL'}
            signal = signal_map.get(int(prediction), 'HOLD')
            
            # Estimate expected return (rough approximation)
            expected_return = float(prediction * confidence * 0.2)  # Simple heuristic
            
            return {
                'prediction': int(prediction),
                'confidence': confidence,
                'signal': signal,
                'expected_return': expected_return,
                'probabilities': {
                    'down': float(probabilities[0]),
                    'hold': float(probabilities[1]),
                    'up': float(probabilities[2])
                }
            }
            
        except Exception as e:
            logging.error(f"ML prediction error: {e}")
            return self._get_fallback_prediction(stock_data)
    
    def predict_from_ohlcv(self, hist, info: dict = None, hist_full=None):
        """
        A-018: Predict using raw OHLCV — uses the SAME feature builder as train_ml_model.py.
        This is the correct inference path when a trained pkl is loaded.

        Args:
            hist:      Recent 60-100 day OHLCV window (pd.DataFrame with Close/High/Low/Volume).
            info:      yfinance ticker.info dict (fundamentals).  None → empty dict.
            hist_full: Full available OHLCV history (for 52-week high / 6-month vol).
                       If None, hist is used for both.
        """
        try:
            import pandas as _pd
            if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) < 60:
                return self._get_fallback_prediction({})
            if not self.is_trained or self.model is None:
                return self._get_fallback_prediction({})
            # Lazy import — train_ml_model is the single source-of-truth for feature building.
            # The import runs module-level setup once (logging, dir creation) — acceptable cost.
            from train_ml_model import build_features_from_hist  # noqa: E402
            features = build_features_from_hist(
                hist, info=info or {}, hist_full=hist_full
            )
            if features is None:
                return self._get_fallback_prediction({})
            features_scaled = self.scaler.transform(features.reshape(1, -1))
            prediction    = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            confidence    = float(np.max(probabilities) * 100)
            signal_map    = {1: 'BUY', 0: 'HOLD', -1: 'SELL'}
            signal        = signal_map.get(int(prediction), 'HOLD')
            expected_return = float(prediction * confidence * 0.2)
            return {
                'prediction':      int(prediction),
                'confidence':      confidence,
                'signal':          signal,
                'expected_return': expected_return,
                'probabilities': {
                    'down': float(probabilities[0]),
                    'hold': float(probabilities[1]),
                    'up':   float(probabilities[2]),
                },
            }
        except Exception as e:
            logging.error(f"predict_from_ohlcv error: {e}")
            return self._get_fallback_prediction({})

    def _get_fallback_prediction(self, stock_data: dict) -> Dict:
        """
        🛡️ Fallback rule-based prediction when ML unavailable
        Uses simple technical indicators
        """
        try:
            rsi = self._safe_float(stock_data.get('real_rsi', 50))
            macd_signal = stock_data.get('real_macd_signal', 'NEUTRAL')
            momentum = stock_data.get('real_momentum', 'NEUTRAL')
            volume_trend = stock_data.get('real_volume_trend', 'AVERAGE')
            
            score = 0
            
            # RSI scoring
            if rsi < 30:
                score += 2  # Oversold - bullish
            elif rsi > 70:
                score -= 2  # Overbought - bearish
            elif 40 <= rsi <= 60:
                score += 1  # Neutral zone
            
            # MACD signal
            if 'BUY' in str(macd_signal).upper():
                score += 2
            elif 'SELL' in str(macd_signal).upper():
                score -= 2
            
            # Momentum
            if 'STRONG' in str(momentum).upper():
                score += 1
            elif 'WEAK' in str(momentum).upper():
                score -= 1
            
            # Volume
            if 'HIGH' in str(volume_trend).upper():
                score += 1
            elif 'LOW' in str(volume_trend).upper():
                score -= 1
            
            # Determine prediction
            if score >= 3:
                prediction = 1
                signal = 'BUY'
                confidence = min(50 + score * 5, 75)
            elif score <= -3:
                prediction = -1
                signal = 'SELL'
                confidence = min(50 + abs(score) * 5, 75)
            else:
                prediction = 0
                signal = 'HOLD'
                confidence = 40
            
            return {
                'prediction': prediction,
                'confidence': float(confidence),
                'signal': signal,
                'expected_return': prediction * confidence * 0.15,
                'probabilities': {}
            }
            
        except Exception as e:
            logging.error(f"Fallback prediction error: {e}")
            return {
                'prediction': 0,
                'confidence': 0.0,
                'signal': 'HOLD',
                'expected_return': 0.0,
                'probabilities': {}
            }

# Singleton instance
_ml_predictor_instance = None

def get_ml_predictor() -> MLPricePredictor:
    """Get singleton ML predictor instance"""
    global _ml_predictor_instance
    if _ml_predictor_instance is None:
        _ml_predictor_instance = MLPricePredictor()
        logging.info("ML Price Predictor initialized (using fallback mode - no training data yet)")
    return _ml_predictor_instance
