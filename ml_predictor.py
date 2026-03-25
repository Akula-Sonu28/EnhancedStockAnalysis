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
import json
import os
from pathlib import Path
from datetime import datetime

class MLPricePredictor:
    """
    🎯 ML-based price movement predictor
    
    Uses 65+ features to predict:
    - Price direction (UP/HOLD/DOWN)
    - Confidence level (0-100%)
    - Expected return
    """
    
    FEATURE_NAMES = [
        # 1. Technical Indicators (20)
        'real_rsi', 'enhanced_rsi_14', 'enhanced_macd', 'enhanced_signal_line',
        'enhanced_bb_position', 'enhanced_bb_width', 'enhanced_atr_14', 'enhanced_adx',
        'enhanced_cci', 'enhanced_stoch_k', 'enhanced_stoch_d', 'enhanced_williams_r',
        'enhanced_roc', 'enhanced_mfi', 'enhanced_obv_trend', 'enhanced_vwap_distance',
        'ma_20', 'ma_50', 'ma_200', 'enhanced_price_vs_ma20',
        # 2. Price Momentum (10)
        'enhanced_price_change_1d', 'enhanced_price_change_5d', 'enhanced_price_change_20d',
        'enhanced_price_change_50d', 'price_momentum_5d', 'price_momentum_20d',
        'volatility_20d', 'volatility_6m', 'enhanced_high_low_range', 'price_vs_52wk_high_ratio',
        # 3. Volume Patterns (8)
        'enhanced_volume_ratio', 'enhanced_volume_trend', 'enhanced_volume_volatility',
        'volume_spike', 'avg_volume', 'volume_ma_ratio', 'enhanced_obv', 'enhanced_mfi_vol',
        # 4. Fundamental Metrics (15)
        'pe_ratio', 'pb_ratio', 'debt_to_equity', 'current_ratio', 'roe',
        'roa', 'profit_margin', 'operating_margin', 'revenue_growth', 'earnings_growth',
        'dividend_yield', 'free_cash_flow', 'book_value_per_share', 'price_to_sales', 'enterprise_value',
        # 5. Sentiment & Flow (7)
        'institutional_score', 'fii_activity', 'dii_activity',
        'mtf_trend_strength', 'mtf_momentum_strength', 'mtf_timeframe_agreement', 'real_technical_score',
        # 6. Multi-Timeframe (5)
        'daily_trend', 'weekly_trend', 'monthly_trend', 'mtf_composite_score', 'advanced_technical_score_final',
    ]
    MODEL_DIR = Path('models')

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_version = None
        self.train_accuracy = None
        self.test_accuracy = None
        self.feature_importances = None
        self._load_trained_model()
    
    def _load_trained_model(self):
        """Load pre-trained model if available"""
        try:
            model_path = (self.MODEL_DIR / 'ml_predictor_latest.pkl').resolve()
            models_root = self.MODEL_DIR.resolve()
            try:
                model_path.relative_to(models_root)
            except ValueError:
                logging.warning("ML model path escapes MODEL_DIR — refusing to load")
                self.is_trained = False
                return
            if model_path.exists():
                # SECURITY: pickle can execute arbitrary code on load. Only read files under
                # MODEL_DIR (validated above); never load pickles from untrusted paths.
                with open(model_path, 'rb') as f:
                    data = pickle.load(f)
                    if not isinstance(data, dict) or 'model' not in data or 'scaler' not in data:
                        logging.warning("Invalid ML pickle structure — expected dict with 'model' and 'scaler'")
                        self.is_trained = False
                        return
                    if not hasattr(data['model'], 'predict'):
                        logging.warning("ML pickle 'model' lacks predict method")
                        self.is_trained = False
                        return
                    self.model = data['model']
                    self.scaler = data['scaler']
                    self.is_trained = True
                    self.model_version = data.get('version')
                    self.train_accuracy = data.get('train_accuracy')
                    self.test_accuracy = data.get('test_accuracy')
                    trained_date = data.get('trained_date', 'unknown')
                    num_samples = data.get('num_samples', 0)
                    logging.info(f"Loaded ML model v{self.model_version} (trained: {trained_date}, samples: {num_samples})")
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
            
            self.train_accuracy = self.model.score(X_train, y_train)
            self.test_accuracy = self.model.score(X_test, y_test)
            
            logging.info(f"ML Model trained - Train acc: {self.train_accuracy:.2%}, Test acc: {self.test_accuracy:.2%}")
            
            self.is_trained = True
            self.model_version = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Feature importance
            if hasattr(self.model, 'feature_importances_'):
                importances = self.model.feature_importances_
                names = self.FEATURE_NAMES[:len(importances)] if len(self.FEATURE_NAMES) >= len(importances) else \
                    [f'feature_{i}' for i in range(len(importances))]
                self.feature_importances = sorted(
                    zip(names, importances), key=lambda x: x[1], reverse=True
                )

            self._save_model(len(training_data))
            self._export_feature_importance()
            return True
            
        except Exception as e:
            logging.error(f"Error training ML model: {e}")
            return False

    def _save_model(self, num_samples: int):
        """Save model with versioning."""
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            'model': self.model,
            'scaler': self.scaler,
            'trained_date': datetime.now().isoformat(),
            'num_samples': num_samples,
            'version': self.model_version,
            'train_accuracy': self.train_accuracy,
            'test_accuracy': self.test_accuracy,
        }
        try:
            latest = self.MODEL_DIR / 'ml_predictor_latest.pkl'
            versioned = self.MODEL_DIR / f'ml_predictor_{self.model_version}.pkl'
            with open(latest, 'wb') as f:
                pickle.dump(payload, f)
            with open(versioned, 'wb') as f:
                pickle.dump(payload, f)
            logging.info(f"Model saved: {versioned.name}")
        except Exception as e:
            logging.warning(f"Failed to save model: {e}")

    def _export_feature_importance(self):
        """Export feature importances to JSON for analysis."""
        if not self.feature_importances:
            return
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        out = self.MODEL_DIR / 'feature_importance.json'
        try:
            data = {
                'version': self.model_version,
                'exported_at': datetime.now().isoformat(),
                'features': [
                    {'name': name, 'importance': float(imp)}
                    for name, imp in self.feature_importances
                ]
            }
            with open(out, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"Feature importance exported to {out}")
        except Exception as e:
            logging.debug(f"Failed to export feature importance: {e}")

    def should_retrain(self, days_threshold: int = 30) -> bool:
        """Check if model needs retraining based on age."""
        latest = self.MODEL_DIR / 'ml_predictor_latest.pkl'
        if not latest.exists():
            return True
        try:
            mtime = datetime.fromtimestamp(latest.stat().st_mtime)
            age_days = (datetime.now() - mtime).days
            if age_days >= days_threshold:
                logging.info(f"Model is {age_days} days old — retraining recommended")
                return True
            return False
        except Exception:
            return True

    def get_model_info(self) -> Dict:
        """Return metadata about current model."""
        return {
            'is_trained': self.is_trained,
            'version': self.model_version,
            'train_accuracy': self.train_accuracy,
            'test_accuracy': self.test_accuracy,
            'top_features': self.feature_importances[:10] if self.feature_importances else [],
            'needs_retrain': self.should_retrain(),
        }
    
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
            # Note: enhanced_mfi appears in both technical and volume blocks intentionally
            # to match the trained model's feature vector. Do NOT change without retraining.
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
            
            # Validate feature count against scaler
            expected_features = getattr(self.scaler, 'n_features_in_', None)
            if expected_features is not None and features.shape[0] != expected_features:
                logging.warning(f"Feature count mismatch: got {features.shape[0]}, expected {expected_features}")
                return self._get_fallback_prediction(stock_data)

            # Get prediction and probabilities
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            # Map probabilities using model.classes_ for correct ordering
            classes = list(self.model.classes_) if hasattr(self.model, 'classes_') else [-1, 0, 1]
            prob_map = {int(c): float(probabilities[i]) for i, c in enumerate(classes) if i < len(probabilities)}
            
            confidence = float(np.max(probabilities) * 100)
            
            signal_map = {1: 'BUY', 0: 'HOLD', -1: 'SELL'}
            signal = signal_map.get(int(prediction), 'HOLD')
            
            expected_return = float(prediction * confidence * 0.2)
            
            return {
                'prediction': int(prediction),
                'confidence': confidence,
                'signal': signal,
                'expected_return': expected_return,
                'probabilities': {
                    'down': prob_map.get(-1, 0.33),
                    'hold': prob_map.get(0, 0.34),
                    'up': prob_map.get(1, 0.33),
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
        _stock_data = info or {}
        try:
            import pandas as _pd
            if hist is None or (hasattr(hist, 'empty') and hist.empty) or len(hist) < 60:
                return self._get_fallback_prediction(_stock_data)
            if not self.is_trained or self.model is None:
                return self._get_fallback_prediction(_stock_data)
            from train_ml_model import build_features_from_hist  # noqa: E402
            features = build_features_from_hist(
                hist, info=info or {}, hist_full=hist_full
            )
            if features is None:
                return self._get_fallback_prediction(_stock_data)

            expected_features = getattr(self.scaler, 'n_features_in_', None)
            if expected_features is not None and features.shape[0] != expected_features:
                logging.warning(f"predict_from_ohlcv: feature count {features.shape[0]} != expected {expected_features}")
                return self._get_fallback_prediction(_stock_data)

            features_scaled = self.scaler.transform(features.reshape(1, -1))
            prediction    = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            confidence    = float(np.max(probabilities) * 100)
            signal_map    = {1: 'BUY', 0: 'HOLD', -1: 'SELL'}
            signal        = signal_map.get(int(prediction), 'HOLD')
            expected_return = float(prediction * confidence * 0.2)

            classes = list(self.model.classes_) if hasattr(self.model, 'classes_') else [-1, 0, 1]
            prob_map = {int(c): float(probabilities[i]) for i, c in enumerate(classes) if i < len(probabilities)}

            return {
                'prediction':      int(prediction),
                'confidence':      confidence,
                'signal':          signal,
                'expected_return': expected_return,
                'probabilities': {
                    'down': prob_map.get(-1, 0.33),
                    'hold': prob_map.get(0, 0.34),
                    'up':   prob_map.get(1, 0.33),
                },
            }
        except Exception as e:
            logging.error(f"predict_from_ohlcv error: {e}")
            return self._get_fallback_prediction(_stock_data)

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
            
            # MACD signal (handles both BUY/SELL and BULLISH/BEARISH naming)
            _macd_upper = str(macd_signal).upper()
            if _macd_upper in ('BUY', 'BULLISH') or 'BUY' in _macd_upper:
                score += 2
            elif _macd_upper in ('SELL', 'BEARISH') or 'SELL' in _macd_upper:
                score -= 2
            
            # Momentum (handles BULLISH/BEARISH and STRONG/WEAK)
            _mom_upper = str(momentum).upper()
            if 'STRONG' in _mom_upper or _mom_upper == 'BULLISH':
                score += 1
            elif 'WEAK' in _mom_upper or _mom_upper == 'BEARISH':
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
                'probabilities': {'down': 0.33, 'hold': 0.34, 'up': 0.33}
            }
            
        except Exception as e:
            logging.error(f"Fallback prediction error: {e}")
            return {
                'prediction': 0,
                'confidence': 0.0,
                'signal': 'HOLD',
                'expected_return': 0.0,
                'probabilities': {'down': 0.33, 'hold': 0.34, 'up': 0.33}
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
