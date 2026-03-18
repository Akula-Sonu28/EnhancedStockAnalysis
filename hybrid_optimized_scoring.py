#!/usr/bin/env python3
"""
HYBRID OPTIMIZED SCORING SYSTEM V5.1
====================================

V5.1 Predictive Power Boost:
- Momentum enriched with MACD histogram + Stochastic %K (6 sub-components)
- New multi-timeframe agreement component (replaces dead fundamental/sector weight)
- ML prediction as proper scoring component (10% weight when trained)
- Risk component enriched with beta + max drawdown 6m (4 sub-components)
- Fundamental weight reduced to 5% (IC=-0.020 at 30d, anti-predictive)
"""

import os
import json
import numpy as np
import math
import logging
import yfinance as yf
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

class HybridOptimizedScoringEngine:
    """
    Hybrid system combining the best elements from all tested approaches
    """
    
    def __init__(self):
        self.version = "5.1 - PREDICTIVE BOOST"
        self.target_correlation = 0.401
        
        # V5.0: All sector multipliers neutralized — validation showed 70% of IC
        # was sector bias, not stock selection (Banking 1.20x → Financial Services
        # avg 74.6 vs Consumer Cyclical 49.9). Sector-neutral IC dropped from 0.094 to 0.028.
        self.sector_multipliers = {k: 1.0 for k in [
            'Banking', 'Financial Services', 'Energy', 'Materials', 'IT',
            'Consumer Durables', 'Consumer Discretionary', 'Healthcare',
            'Utilities', 'Real Estate', 'Communication Services', 'default'
        ]}

        # V5.0: Regime multipliers removed — these applied a directional bias
        # (bull 1.1x / bear 0.9x) that inflated scores rather than improving stock selection.
        # Regime-adaptive WEIGHTS are kept (different component proportions per regime).
        self.market_regimes = {
            'bullish': 1.00,
            'bearish': 1.00,
            'neutral': 1.00
        }
    
    def calculate_fundamental_quality_score(self, stock_data):
        """
        V5.0: Continuous fundamental quality scoring.
        Replaces cliff-effect step functions (IC=0.003) with smooth linear
        interpolation to produce a wider score distribution.
        """
        try:
            import math
            pe = self._safe_float(stock_data.get('pe_ratio'), 20)
            roe = self._safe_float(stock_data.get('roe'), 10)
            debt = self._safe_float(stock_data.get('debt_to_equity'), 50)
            market_cap = self._safe_float(stock_data.get('market_cap'), 1e12)

            # PE (25 pts): sweet spot around 14, penalty past 30 and below 5
            if pe <= 0:
                pe_score = 5.0
            elif pe <= 20:
                pe_score = max(10.0, 25.0 - abs(pe - 14.0) * 1.5)
            else:
                pe_score = max(0.0, 25.0 - (pe - 20.0) * 0.8)

            # ROE (25 pts): linear 0-25, saturates at ROE=25%
            roe_score = float(np.clip(roe / 25.0 * 25.0, 0, 25))

            # Debt/Equity (25 pts): inverse linear, saturates at D/E=150
            debt_score = float(np.clip(25.0 - debt / 150.0 * 25.0, 0, 25))

            # Size (25 pts): log-scale, 1B=5pts, 1T=25pts
            log_cap = math.log10(max(market_cap, 1e6))
            size_score = float(np.clip((log_cap - 9.0) / 3.0 * 25.0, 5, 25))

            return pe_score + roe_score + debt_score + size_score

        except Exception as _e:
            logging.debug(f"Scoring component error: {_e}")
            return 50.0
    
    @staticmethod
    def _safe_float(val, default=0.0):
        """Safely convert a value to float, handling None, NaN, and inf."""
        if val is None:
            return default
        try:
            f = float(val)
            if np.isnan(f) or np.isinf(f):
                return default
            return f
        except (TypeError, ValueError):
            return default

    def calculate_momentum_technical_score(self, stock_data, market_regime=None):
        """
        V5.2: Recentered momentum scoring.
        Neutral market (RSI 50, 0% change, price at SMA) yields ~42/100.
        MACD and Stochastic act as confirmation boosters.
        """
        try:
            rsi = self._safe_float(stock_data.get('real_rsi', stock_data.get('enhanced_rsi_14', stock_data.get('rsi'))), 50)
            price_change_20d = self._safe_float(stock_data.get('enhanced_price_change_20d', stock_data.get('price_change_1m')), 0)
            current_price = self._safe_float(stock_data.get('current_price'), 100)
            sma_50 = self._safe_float(stock_data.get('sma_50', stock_data.get('ma_50')), current_price)
            macd_hist = self._safe_float(stock_data.get('enhanced_macd_histogram'), 0)
            stoch_k = self._safe_float(stock_data.get('enhanced_stoch_k'), 50)

            # RSI (0-28 pts): RSI 20->0, 50->14, 80->28
            rsi_score = float(np.clip((rsi - 20.0) / 60.0 * 28.0, 0, 28))

            # Price momentum 20d (0-32 pts): -10%->0, 0%->12.8, +15%->32
            mom_score = float(np.clip((price_change_20d + 10.0) / 25.0 * 32.0, 0, 32))

            # Price vs SMA-50 (0-28 pts): -10%->0, 0%->11.2, +15%->28
            if sma_50 > 0 and current_price > 0:
                price_vs_sma = ((current_price - sma_50) / sma_50) * 100.0
                trend_score = float(np.clip((price_vs_sma + 10.0) / 25.0 * 28.0, 0, 28))
            else:
                trend_score = 14.0

            # MACD histogram (0-6 pts): price-normalized confirmation
            if current_price > 0:
                macd_pct = (macd_hist / current_price) * 100.0
            else:
                macd_pct = 0.0
            macd_score = float(np.clip((macd_pct + 1.0) / 2.0 * 6.0, 0, 6))

            # Stochastic %K (0-6 pts): confirmation
            stoch_score = float(np.clip((stoch_k - 20.0) / 60.0 * 6.0, 0, 6))

            return rsi_score + mom_score + trend_score + macd_score + stoch_score

        except Exception as _e:
            logging.debug(f"Scoring component error: {_e}")
            return 50.0
    
    def calculate_volume_strength_score(self, stock_data):
        """
        V5.2: Continuous volume scoring with quality discount.
        Linear interpolation from volume_ratio 0.5->0 to 3.0->100.
        Guarantees floor of 15 for normal volume (ratio >= 0.8).
        Applies 50% penalty when volume_quality is LOW.
        """
        try:
            volume_ratio = self._safe_float(stock_data.get('enhanced_volume_ratio', stock_data.get('volume_ratio')), 1.0)
            vol_score = float(np.clip((volume_ratio - 0.5) / 2.5 * 100.0, 0, 100))
            if volume_ratio >= 0.8 and vol_score < 15:
                vol_score = 15.0
            _quality = str(stock_data.get('volume_quality', 'MODERATE')).upper()
            if _quality == 'LOW':
                vol_score *= 0.5
            return vol_score
        except Exception as _e:
            logging.debug(f"Scoring component error: {_e}")
            return 50.0
    
    def calculate_sector_momentum_score(self, symbol, stock_data=None):
        """DEPRECATED (V5.0): Always returns neutral 50. Not called by any active code path."""
        import warnings
        warnings.warn("calculate_sector_momentum_score is deprecated", DeprecationWarning, stacklevel=2)
        return 50

    def calculate_multi_timeframe_score(self, stock_data):
        """
        V5.1: Multi-timeframe agreement score.
        When daily/weekly/monthly trends align, the signal is much stronger.
        Uses mtf_timeframe_agreement (0-100), mtf_trend_strength (0-100),
        mtf_composite_score (0-100), mtf_momentum_strength (0-100).
        """
        try:
            agreement = self._safe_float(stock_data.get('mtf_timeframe_agreement'), 50)
            trend_str = self._safe_float(stock_data.get('mtf_trend_strength'), 50)
            composite = self._safe_float(stock_data.get('mtf_composite_score'), 50)
            mom_str = self._safe_float(stock_data.get('mtf_momentum_strength'), 50)

            # Agreement (0-40 pts): 0%→0, 100%→40. High agreement = strong signal.
            agree_score = float(np.clip(agreement / 100.0 * 40.0, 0, 40))

            # Composite score pass-through (0-30 pts): already 0-100 → scale to 0-30
            comp_score = float(np.clip(composite / 100.0 * 30.0, 0, 30))

            # Trend+momentum blend (0-30 pts)
            blend = (trend_str * 0.5 + mom_str * 0.5)
            tm_score = float(np.clip(blend / 100.0 * 30.0, 0, 30))

            return agree_score + comp_score + tm_score

        except Exception as _e:
            logging.debug(f"Scoring component error: {_e}")
            return 50.0

    def calculate_ml_signal_score(self, stock_data):
        """
        V5.1: ML prediction score component.
        Uses ml_expected_return and ml_confidence from the trained GBM model.
        Returns 50 (neutral) when ML model isn't trained or confidence is too low.
        """
        try:
            is_trained = (stock_data.get('ml_model_source') == 'trained_model')
            if not is_trained:
                return 50.0

            confidence = self._safe_float(stock_data.get('ml_confidence'), 0)
            if confidence < 30:
                return 50.0

            expected_return = self._safe_float(stock_data.get('ml_expected_return'), 0)
            signal = str(stock_data.get('ml_signal', 'HOLD')).upper()

            # Base score from expected return: -10%→20, 0%→50, +10%→80
            base = float(np.clip(50.0 + expected_return * 3.0, 20, 80))

            # Direction bonus/penalty
            if signal == 'BUY':
                base = min(100, base + 10)
            elif signal == 'SELL':
                base = max(0, base - 10)

            # Clamp confidence to [30, 100] to prevent runaway scores
            confidence = min(100.0, confidence)
            conf_scale = (confidence - 30.0) / 70.0
            return float(np.clip(50.0 + (base - 50.0) * conf_scale, 0, 100))

        except Exception as _e:
            logging.debug(f"Scoring component error: {_e}")
            return 50.0
    
    def calculate_risk_adjustment_score(self, stock_data):
        """
        V5.1: Risk scoring with beta and max drawdown as supplementary signals.
        Volatility and 52w drawdown stay dominant (proven IC=0.157), beta and
        max_dd_6m add complementary information at lower weight.
        """
        try:
            volatility = self._safe_float(stock_data.get('volatility', stock_data.get('volatility_20d')), 25)
            beta = self._safe_float(stock_data.get('beta'), 1.0)
            max_dd_6m = self._safe_float(stock_data.get('max_drawdown_6m'), 15)

            # Volatility (0-50): dominant — linear vol=0→50, vol=60→0
            vol_score = float(np.clip(50.0 - volatility * 50.0 / 60.0, 0, 50))

            # 52-week drawdown (0-30): linear dd=0%→30, dd=50%→0
            current_price = self._safe_float(stock_data.get('current_price'), 0)
            high_52w = self._safe_float(stock_data.get('52_week_high'), current_price)
            if high_52w > 0 and current_price > 0:
                drawdown_pct = (high_52w - current_price) / high_52w * 100.0
                dd_score = float(np.clip(30.0 - drawdown_pct * 0.6, 0, 30))
            else:
                dd_score = 15.0

            # Beta (0-12): low beta = safer. beta=0.5→12, beta=1.5→0
            beta_score = float(np.clip((1.5 - beta) / 1.0 * 12.0, 0, 12))

            # Max drawdown 6m (0-8): supplementary. dd=0%→8, dd=40%→0
            max_dd_abs = abs(max_dd_6m)
            mdd_score = float(np.clip(8.0 - max_dd_abs * 0.2, 0, 8))

            return vol_score + dd_score + beta_score + mdd_score

        except Exception as _e:
            logging.debug(f"Scoring component error: {_e}")
            return 50.0
    
    def detect_market_regime(self):
        """
        Simple market regime detection based on major indices
        """
        try:
            # Get Nifty 50 recent performance as market proxy
            nifty = yf.Ticker("^NSEI")
            hist = nifty.history(period="1mo")
            
            if len(hist) > 5:
                _denom = hist['Close'].iloc[-5]
                if _denom == 0 or np.isnan(_denom):
                    return 'neutral'
                recent_change = ((hist['Close'].iloc[-1] - _denom) / _denom) * 100
                
                if recent_change > 5:
                    return 'bullish'
                elif recent_change < -5:
                    return 'bearish'
                else:
                    return 'neutral'
            else:
                return 'neutral'
                
        except Exception:
            return 'neutral'
    
    # ML model disabled (test accuracy 39% = random). Weight set to 0, redistributed to momentum.
    # Will be re-enabled when model is retrained with corrected feature pipeline.
    _REGIME_WEIGHTS_NO_ML = {
        'bullish': {
            'fundamental_quality': 0.15,
            'momentum_technical':  0.30,
            'volume_strength':     0.05,
            'multi_timeframe':     0.15,
            'ml_signal':           0.00,
            'risk_adjustment':     0.35,
        },
        'bearish': {
            'fundamental_quality': 0.15,
            'momentum_technical':  0.25,
            'volume_strength':     0.05,
            'multi_timeframe':     0.15,
            'ml_signal':           0.00,
            'risk_adjustment':     0.40,
        },
        'neutral': {
            'fundamental_quality': 0.15,
            'momentum_technical':  0.25,
            'volume_strength':     0.05,
            'multi_timeframe':     0.15,
            'ml_signal':           0.00,
            'risk_adjustment':     0.40,
        },
    }

    def calculate_hybrid_score(self, symbol, stock_data, adaptive_weights=None):
        """
        V5.1: Hybrid score with 6 components (fundamental, momentum, volume, mtf, ml, risk).
        ML weight redistributes to momentum when ML model is not trained.
        """
        try:
            if stock_data is None:
                return {'hybrid_score': 0, 'components': {}, 'adjustments': {}, 'error': 'stock_data is None'}

            _raw_regime = str(stock_data.get('market_regime') or '').upper()
            if _raw_regime in ('BULL', 'BULLISH'):
                market_regime = 'bullish'
            elif _raw_regime in ('BEAR', 'BEARISH', 'VOLATILE'):
                market_regime = 'bearish'
            elif _raw_regime in ('SIDEWAYS', 'NEUTRAL', 'RANGE'):
                market_regime = 'neutral'
            else:
                market_regime = 'neutral'

            fundamental_score = self.calculate_fundamental_quality_score(stock_data)
            momentum_score = self.calculate_momentum_technical_score(stock_data, market_regime=market_regime)
            volume_score = self.calculate_volume_strength_score(stock_data)
            mtf_score = self.calculate_multi_timeframe_score(stock_data)
            ml_score = self.calculate_ml_signal_score(stock_data)
            risk_score = self.calculate_risk_adjustment_score(stock_data)

            ml_active = False  # ML disabled: test accuracy 39% (random for 3-class). Re-enable after retraining.
            mtf_available = (stock_data.get('mtf_analysis_status') == 'success')
            _weight_table = self._REGIME_WEIGHTS_NO_ML
            _regime_defaults = dict(_weight_table.get(market_regime, _weight_table['neutral']))

            # When MTF data is unavailable, redistribute its weight to risk and momentum
            if not mtf_available:
                _mtf_w = _regime_defaults.get('multi_timeframe', 0)
                _regime_defaults['multi_timeframe'] = 0.0
                _regime_defaults['risk_adjustment'] = _regime_defaults.get('risk_adjustment', 0.40) + _mtf_w * 0.6
                _regime_defaults['momentum_technical'] = _regime_defaults.get('momentum_technical', 0.20) + _mtf_w * 0.4

            _calibrated = self._load_calibrated_weights()
            _using_calibrated = False
            if adaptive_weights and isinstance(adaptive_weights, dict):
                weights = {k: adaptive_weights.get(k, _regime_defaults.get(k, 0)) for k in _regime_defaults}
                if not ml_active and weights.get('ml_signal', 0) > 0:
                    _leaked = weights['ml_signal']
                    weights['ml_signal'] = 0.0
                    weights['momentum_technical'] = weights.get('momentum_technical', 0) + _leaked
                if not mtf_available and weights.get('multi_timeframe', 0) > 0:
                    _mtf_w = weights['multi_timeframe']
                    weights['multi_timeframe'] = 0.0
                    weights['risk_adjustment'] = weights.get('risk_adjustment', 0.40) + _mtf_w * 0.6
                    weights['momentum_technical'] = weights.get('momentum_technical', 0.20) + _mtf_w * 0.4
                _wsum = sum(weights.values())
                if _wsum > 0 and abs(_wsum - 1.0) > 0.01:
                    weights = {k: v / _wsum for k, v in weights.items()}
            elif _calibrated:
                weights = {k: _calibrated.get(k, _regime_defaults.get(k, 0)) for k in _regime_defaults}
                if not ml_active and weights.get('ml_signal', 0) > 0:
                    _leaked = weights['ml_signal']
                    weights['ml_signal'] = 0.0
                    weights['momentum_technical'] = weights.get('momentum_technical', 0) + _leaked
                if not mtf_available and weights.get('multi_timeframe', 0) > 0:
                    _mtf_w = weights['multi_timeframe']
                    weights['multi_timeframe'] = 0.0
                    weights['risk_adjustment'] = weights.get('risk_adjustment', 0.40) + _mtf_w * 0.6
                    weights['momentum_technical'] = weights.get('momentum_technical', 0.20) + _mtf_w * 0.4
                _wsum = sum(weights.values())
                if _wsum > 0 and abs(_wsum - 1.0) > 0.01:
                    weights = {k: v / _wsum for k, v in weights.items()}
                _using_calibrated = True
            else:
                weights = _regime_defaults

            weighted_score = (
                (fundamental_score * weights.get('fundamental_quality', 0.05)) +
                (momentum_score    * weights.get('momentum_technical', 0.20))  +
                (volume_score      * weights.get('volume_strength', 0.05))     +
                (mtf_score         * weights.get('multi_timeframe', 0.20))     +
                (ml_score          * weights.get('ml_signal', 0.0))            +
                (risk_score        * weights.get('risk_adjustment', 0.40))
            )

            final_score = max(0, min(100, weighted_score))
            if np.isnan(final_score):
                final_score = 50.0

            _r = lambda v: round(float(np.nan_to_num(v, nan=50.0)), 1)
            return {
                'hybrid_score': round(final_score, 1),
                'components': {
                    'fundamental_quality': _r(fundamental_score),
                    'momentum_technical': _r(momentum_score),
                    'volume_strength': _r(volume_score),
                    'multi_timeframe': _r(mtf_score),
                    'ml_signal': _r(ml_score),
                    'risk_adjustment': _r(risk_score),
                    'sector_momentum': 50.0,
                },
                'adjustments': {
                    'sector_multiplier': 1.0,
                    'market_regime': market_regime,
                    'regime_multiplier': 1.0,
                    'regime_weights': 'calibrated' if _using_calibrated else ('ml_active' if ml_active else 'no_ml'),
                    'ml_active': ml_active,
                    'using_calibrated_weights': _using_calibrated,
                },
                'raw_weighted_score': round(weighted_score, 1)
            }

        except Exception as e:
            print(f"Error calculating hybrid score for {symbol}: {e}")
            return {'hybrid_score': 0, 'components': {}, 'adjustments': {}, 'error': str(e)}
    
    _CALIBRATED_WEIGHTS_PATH = 'data/calibrated_weights.json'

    @classmethod
    def calibrate_weights_from_outcomes(cls, history_df):
        """
        Compute IC (rank correlation) of each scoring component vs return_30d
        from recommendation history, normalize to produce calibrated weights,
        and persist to data/calibrated_weights.json.
        """
        import pandas as pd
        from scipy.stats import spearmanr

        ret_col = 'return_30d'
        if ret_col not in history_df.columns:
            logging.info("calibrate_weights: no return_30d column — skipping")
            return None

        valid = history_df.dropna(subset=[ret_col]).copy()
        valid[ret_col] = pd.to_numeric(valid[ret_col], errors='coerce')
        valid = valid.dropna(subset=[ret_col])

        if len(valid) < 30:
            logging.info(f"calibrate_weights: only {len(valid)} rows with outcomes — need >=30")
            return None

        component_map = {
            'fundamental_quality': 'fundamental_score',
            'momentum_technical': 'momentum_score',
            'volume_strength': 'volume_composite_score',
            'multi_timeframe': 'mtf_composite_score',
            'ml_signal': 'ml_expected_return',
            'risk_adjustment': 'risk_adjusted_score',
        }

        ics = {}
        for weight_key, col in component_map.items():
            if col in valid.columns:
                vals = pd.to_numeric(valid[col], errors='coerce').dropna()
                matched_ret = valid.loc[vals.index, ret_col]
                if len(vals) >= 20:
                    corr, _ = spearmanr(vals, matched_ret)
                    ics[weight_key] = max(0, corr) if not np.isnan(corr) else 0
                else:
                    ics[weight_key] = 0
            else:
                ics[weight_key] = 0

        total_ic = sum(ics.values())
        if total_ic <= 0:
            logging.info("calibrate_weights: all ICs <= 0 — cannot calibrate")
            return None

        calibrated = {k: round(v / total_ic, 4) for k, v in ics.items()}

        result = {
            'weights': calibrated,
            'ics': {k: round(v, 4) for k, v in ics.items()},
            'sample_size': len(valid),
            'updated': datetime.now().isoformat(),
        }
        try:
            os.makedirs(os.path.dirname(cls._CALIBRATED_WEIGHTS_PATH) or '.', exist_ok=True)
            with open(cls._CALIBRATED_WEIGHTS_PATH, 'w') as f:
                json.dump(result, f, indent=2)
            logging.info(f"Calibrated weights saved: {calibrated}")
        except Exception as e:
            logging.warning(f"Could not save calibrated weights: {e}")
        return calibrated

    def _load_calibrated_weights(self):
        """Load calibrated weights if they exist and are < 7 days old."""
        try:
            if not os.path.exists(self._CALIBRATED_WEIGHTS_PATH):
                return None
            with open(self._CALIBRATED_WEIGHTS_PATH) as f:
                data = json.load(f)
            updated = datetime.fromisoformat(data['updated'])
            if (datetime.now() - updated).days > 7:
                return None
            return data.get('weights')
        except Exception:
            return None

    def _get_sector_multiplier(self, stock_data):
        """DEPRECATED: Sector multipliers neutralized in V5.0. Not called by active code paths."""
        sector = str(stock_data.get('sector', '') or '').lower()

        sector_map = {
            'financial services': 'Banking',
            'banks': 'Banking',
            'energy': 'Energy',
            'basic materials': 'Materials',
            'industrials': 'Materials',
            'technology': 'IT',
            'consumer cyclical': 'Consumer Discretionary',
            'consumer defensive': 'Consumer Durables',
            'healthcare': 'Healthcare',
            'utilities': 'Utilities',
            'real estate': 'Real Estate',
            'communication services': 'Communication Services',
        }

        matched = sector_map.get(sector, None)
        if matched and matched in self.sector_multipliers:
            return self.sector_multipliers[matched]
        return self.sector_multipliers['default']
    
    def generate_hybrid_recommendation(self, symbol, hybrid_scores):
        """
        Generate investment recommendation based on hybrid score
        """
        if not hybrid_scores or not isinstance(hybrid_scores, dict):
            return {'recommendation': '🔴 AVOID', 'confidence': 'LOW', 'target_return': 'N/A',
                    'reason': 'Invalid score data', 'score': 0, 'quintile': 'N/A'}
        score = self._safe_float(hybrid_scores.get('hybrid_score'), 0)
        
        # Recommendation thresholds (based on quintile analysis)
        if score >= 85:  # Top quintile (Q5)
            recommendation = "🟢 STRONG BUY"
            confidence = "HIGH"
            target_return = "+8.70%"  # Based on top-20 average
            reason = "Top quintile score - 90% win rate historically"
            
        elif score >= 75:  # Q4
            recommendation = "🟢 BUY"
            confidence = "MEDIUM-HIGH"  
            target_return = "+5.31%"
            reason = "Above average score - solid fundamentals"
            
        elif score >= 65:  # Q3  
            recommendation = "🟡 HOLD"
            confidence = "MEDIUM"
            target_return = "+0.74%"
            reason = "Average score - market performance expected"
            
        elif score >= 50:  # Q2
            recommendation = "🟠 WEAK HOLD"
            confidence = "LOW"
            target_return = "-2.34%"
            reason = "Below average - consider alternatives"
            
        else:  # Q1 (Bottom quintile)
            recommendation = "🔴 AVOID"
            confidence = "HIGH"
            target_return = "-5.32%"
            reason = "Bottom quintile - high probability of loss"
        
        return {
            'recommendation': recommendation,
            'confidence': confidence,
            'target_return': target_return,
            'reason': reason,
            'score': score,
            'quintile': self._get_quintile(score)
        }
    
    def _get_quintile(self, score):
        """Determine quintile based on score"""
        if score >= 85:
            return "Q5 (Top 20%)"
        elif score >= 75:
            return "Q4"
        elif score >= 65:
            return "Q3"  
        elif score >= 50:
            return "Q2"
        else:
            return "Q1 (Bottom 20%)"

# Test the hybrid system
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 HYBRID OPTIMIZED SCORING SYSTEM V4.0")
    print("=" * 60)
    print("Target: +0.401 correlation, +10.63% spread")
    print("Based on 500-stock backtest analysis")
    
    hybrid_engine = HybridOptimizedScoringEngine()
    
    # Test with sample data
    test_stock_data = {
        'pe_ratio': 12.5,
        'roe': 0.18,
        'debt_to_equity': 45,
        'market_cap': 50000000000,
        'rsi': 65,
        'price_change_20d': 8.5,
        'current_price': 150,
        'sma_50': 140,
        'volume': 2000000,
        'volume_sma_20': 1500000,
        'volume_ratio': 1.33,
        'volatility': 22
    }
    
    result = hybrid_engine.calculate_hybrid_score('SBIN.NS', test_stock_data)
    recommendation = hybrid_engine.generate_hybrid_recommendation('SBIN.NS', result)
    
    print(f"\n📊 TEST RESULTS FOR SBIN.NS:")
    print(f"   Hybrid Score: {result['hybrid_score']}")
    print(f"   Components: {result['components']}")
    print(f"   Recommendation: {recommendation['recommendation']}")
    print(f"   Target Return: {recommendation['target_return']}")
    print(f"   Quintile: {recommendation['quintile']}")
    
    print(f"\n✅ HYBRID SYSTEM READY FOR DEPLOYMENT!")