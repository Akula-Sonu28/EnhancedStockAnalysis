"""
Market Regime Detection Module
Classifies market conditions and adjusts trading strategies accordingly
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime, timedelta

class MarketRegimeDetector:
    """
    Single source of truth for market regime detection (CB-06).
    Detects market regime (Bull, Bear, Sideways) using multiple indicators:
    - Price trends (moving averages)
    - Volatility (VIX equivalent for India)
    - Market breadth (advance-decline)
    - Momentum indicators
    """
    
    _LAST_REGIME_PATH = 'data/last_known_regime.json'

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.nifty_symbol = "^NSEI"  # NSE Nifty 50 index
        self.bank_nifty_symbol = "^NSEBANK"  # Bank Nifty index
        self.midcap_symbol = "NIFTY_MID_SELECT.NS"  # Nifty Midcap Select
        self.india_vix_symbol = "^INDIAVIX"  # India VIX
        
        # Regime thresholds (symmetric to avoid bearish classification bias)
        self.bull_threshold = 0.5
        self.bear_threshold = -0.5
        
        # Default signal weights (adjusted dynamically by VIX)
        self.base_weights = {
            'trend': 0.35,
            'momentum': 0.25,
            'volatility': 0.20,
            'breadth': 0.20,
        }
        
        # F-02 FIX: Load previous regime from disk so hysteresis works across runs
        self._last_regime = self._load_last_regime()
        
    def detect_regime(self, period_days: int = 180) -> Dict:
        """
        Detect current market regime using multiple indicators
        
        Args:
            period_days: Number of days to analyze (default 180 = 6 months)
            
        Returns:
            Dict with regime classification and supporting metrics
        """
        try:
            # Get Nifty 50 data
            nifty_data = self._get_index_data(self.nifty_symbol, period_days)
            
            if nifty_data is None or len(nifty_data) < 50:
                return self._get_default_regime()
            
            # Calculate multiple regime indicators on primary index
            trend_signal = self._calculate_trend_signal(nifty_data)
            volatility_signal = self._calculate_volatility_signal(nifty_data)
            momentum_signal = self._calculate_momentum_signal(nifty_data)
            breadth_signal = self._calculate_breadth_signal(nifty_data)
            
            # P4-02: VIX-adaptive weighting — fear spikes raise volatility weight
            vix_level = self._get_vix_level()
            weights = dict(self.base_weights)
            if vix_level > 25:
                extra = 0.15
                weights['volatility'] += extra
                weights['trend'] -= extra
            
            regime_score = (
                trend_signal * weights['trend'] +
                momentum_signal * weights['momentum'] +
                volatility_signal * weights['volatility'] +
                breadth_signal * weights['breadth']
            )
            regime_score = max(-1.0, min(1.0, regime_score))

            if vix_level > 35:
                regime_score = min(regime_score, 0.0)
                self.logger.info(f"[H5] VIX={vix_level:.1f} > 35 — clamping regime_score to non-BULL (max 0)")
            elif vix_level > 30:
                regime_score = min(regime_score, 0.3)
                self.logger.info(f"[H5] VIX={vix_level:.1f} > 30 — softening regime_score (max 0.3, was {regime_score:.2f})")

            # P4-01: Multi-index consensus — adjust confidence
            secondary_scores = self._get_secondary_index_scores(period_days)
            index_agreement = self._compute_index_agreement(regime_score, secondary_scores)
            
            # Classify regime — modulate confidence by index agreement
            effective_score = regime_score * (0.6 + 0.4 * index_agreement)
            
            _prev_regime = getattr(self, '_last_regime', None)
            _bull_hyst = 0.1
            _bear_hyst = 0.05
            _bull_thr = self.bull_threshold - (_bull_hyst if _prev_regime == 'BULL' else 0)
            _bear_thr = self.bear_threshold + (_bear_hyst if _prev_regime == 'BEAR' else 0)
            if effective_score > _bull_thr:
                regime = 'BULL'
                regime_strength = 'STRONG' if effective_score > 0.8 else 'MODERATE'
            elif effective_score < _bear_thr:
                regime = 'BEAR'
                regime_strength = 'STRONG' if effective_score < -0.8 else 'MODERATE'
            else:
                regime = 'SIDEWAYS'
                regime_strength = 'CHOPPY'
            self._last_regime = regime
            
            # Calculate regime stability (how long has this regime persisted)
            regime_stability = self._calculate_regime_stability(nifty_data, regime)
            
            result = {
                'regime': regime,
                'regime_strength': regime_strength,
                'regime_score': regime_score,
                'regime_confidence': abs(regime_score) * (0.6 + 0.4 * index_agreement),
                'index_agreement': index_agreement,
                'regime_stability': regime_stability,
                'trend_signal': trend_signal,
                'momentum_signal': momentum_signal,
                'volatility_signal': volatility_signal,
                'breadth_signal': breadth_signal,
                'vix_level': vix_level,
                'market_sentiment': self._get_market_sentiment(vix_level, regime_score),
                'trading_recommendation': self._get_trading_recommendation(regime, regime_strength, vix_level),
                'risk_level': self._calculate_risk_level(regime, vix_level),
                'current_nifty': nifty_data['Close'].iloc[-1],
                'nifty_change_1m': self._calculate_change(nifty_data, 20),
                'nifty_change_3m': self._calculate_change(nifty_data, 60),
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self._cache_regime(result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error detecting market regime: {e}")
            return self._get_fallback_regime()
    
    def _get_index_data(self, symbol: str, period_days: int) -> Optional[pd.DataFrame]:
        """Fetch index data from yfinance with retry"""
        import time as _time
        for _attempt in range(3):
            try:
                ticker = yf.Ticker(symbol)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=period_days + 30)
                
                data = ticker.history(start=start_date, end=end_date)
                
                if data.empty:
                    self.logger.warning(f"No data available for {symbol}")
                    return None
                
                return data
                
            except (ConnectionError, TimeoutError, OSError) as e:
                _wait = (2 ** _attempt) * 2
                self.logger.warning(f"Retry {_attempt+1}/3 for {symbol}: {e}")
                _time.sleep(_wait)
            except Exception as e:
                self.logger.error(f"Error fetching data for {symbol}: {e}")
                return None
        return None
    
    def _calculate_trend_signal(self, df: pd.DataFrame) -> float:
        """
        Calculate trend signal using moving averages
        Returns: -1 (bearish) to +1 (bullish)
        """
        close = df['Close']
        
        # Calculate multiple moving averages
        ma_20 = close.rolling(window=20).mean()
        ma_50 = close.rolling(window=50).mean()
        ma_100 = close.rolling(window=100).mean()
        ma_200 = close.rolling(window=200).mean() if len(close) >= 200 else ma_100
        
        current_price = close.iloc[-1]
        
        # Score based on price vs MAs (0.25 points each)
        score = 0.0
        
        # Price above MA-20 (short-term trend)
        if current_price > ma_20.iloc[-1]:
            score += 0.25
        else:
            score -= 0.25
        
        # Price above MA-50 (medium-term trend)
        if current_price > ma_50.iloc[-1]:
            score += 0.25
        else:
            score -= 0.25
        
        # MA-50 above MA-100 (trend strength)
        if ma_50.iloc[-1] > ma_100.iloc[-1]:
            score += 0.25
        else:
            score -= 0.25
        
        # MA-100 above MA-200 (long-term trend)
        if len(ma_200) > 0 and ma_100.iloc[-1] > ma_200.iloc[-1]:
            score += 0.25
        else:
            score -= 0.25
        
        return np.clip(score, -1.0, 1.0)
    
    def _calculate_volatility_signal(self, df: pd.DataFrame) -> float:
        """
        Calculate volatility signal
        High volatility = bearish, Low volatility = bullish
        Returns: -1 (high volatility/bearish) to +1 (low volatility/bullish)
        """
        # Calculate 20-day historical volatility
        returns = df['Close'].pct_change()
        volatility = returns.rolling(window=20).std() * np.sqrt(252) * 100
        
        current_vol = volatility.iloc[-1]
        avg_vol = volatility.mean()
        if np.isnan(current_vol) or np.isnan(avg_vol) or avg_vol == 0:
            return 0.0
        
        # Normalize: below average = positive, above average = negative
        if current_vol < avg_vol * 0.8:
            return 1.0  # Very low volatility (bullish)
        elif current_vol < avg_vol:
            return 0.5  # Low volatility (moderately bullish)
        elif current_vol < avg_vol * 1.2:
            return -0.5  # High volatility (moderately bearish)
        else:
            return -1.0  # Very high volatility (bearish)
    
    def _calculate_momentum_signal(self, df: pd.DataFrame) -> float:
        """
        Calculate momentum signal using RSI and rate of change
        Returns: -1 (bearish) to +1 (bullish)
        """
        close = df['Close']
        
        # Calculate RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        loss_safe = loss.replace(0, np.nan)
        rs = gain / loss_safe
        rsi = (100 - (100 / (1 + rs))).fillna(50.0)
        current_rsi = rsi.iloc[-1]
        
        # Calculate 20-day rate of change
        _close_20_raw = close.iloc[-20] if len(close) >= 20 else close.iloc[0]
        _close_20 = 1.0 if (_close_20_raw == 0 or pd.isna(_close_20_raw)) else _close_20_raw
        roc_20 = ((close.iloc[-1] - _close_20) / _close_20) * 100
        
        # Combine RSI and ROC
        rsi_score = (current_rsi - 50) / 50  # Normalize to -1 to +1
        roc_score = np.clip(roc_20 / 10, -1.0, 1.0)  # 10% move = max score
        
        momentum_score = (rsi_score * 0.6 + roc_score * 0.4)
        
        return np.clip(momentum_score, -1.0, 1.0)
    
    def _calculate_breadth_signal(self, df: pd.DataFrame) -> float:
        """
        Calculate market breadth signal using percentage of recent closes
        above their rolling 50-day SMA as a proxy for advance-decline breadth.
        Returns: -1 (bearish) to +1 (bullish)
        """
        close = df['Close']
        if len(close) < 50:
            return 0.0

        sma_50 = close.rolling(50).mean()
        recent = min(20, len(close) - 50)
        recent_close = close.iloc[-recent:]
        recent_sma = sma_50.iloc[-recent:]

        valid = recent_sma.notna()
        if valid.sum() == 0:
            return 0.0

        pct_above = (recent_close[valid] > recent_sma[valid]).sum() / valid.sum()
        breadth = (pct_above - 0.5) * 2.0

        return float(np.clip(breadth, -1.0, 1.0))
    
    def _get_secondary_index_scores(self, period_days: int) -> list:
        """Compute regime scores for Bank Nifty and Midcap indices."""
        scores = []
        for sym in (self.bank_nifty_symbol, self.midcap_symbol):
            try:
                data = self._get_index_data(sym, period_days)
                if data is not None and len(data) >= 50:
                    t = self._calculate_trend_signal(data)
                    m = self._calculate_momentum_signal(data)
                    scores.append(t * 0.6 + m * 0.4)
                    continue
            except Exception as e:
                self.logger.debug(f"Secondary index {sym} unavailable: {e}")
            scores.append(None)
        return scores

    @staticmethod
    def _compute_index_agreement(primary_score: float, secondary_scores: list) -> float:
        """Return 0-1 agreement ratio between primary and secondary indices."""
        valid = [s for s in secondary_scores if s is not None]
        if not valid:
            return 0.5
        if abs(primary_score) < 1e-9:
            return 0.5
        primary_dir = 1 if primary_score > 0 else -1
        agree = sum(1 for s in valid if (s > 0 and primary_dir > 0) or (s < 0 and primary_dir < 0))
        return agree / len(valid)

    def _get_vix_level(self) -> float:
        """Get current India VIX level"""
        try:
            vix_data = self._get_index_data(self.india_vix_symbol, 5)
            if vix_data is not None and not vix_data.empty:
                _vix_val = vix_data['Close'].iloc[-1]
                if pd.isna(_vix_val) or np.isinf(_vix_val):
                    logging.warning("VIX value is NaN/inf — using cautious default (22.0)")
                    return 22.0
                return float(_vix_val)
        except Exception as e:
            logging.warning(f"VIX fetch failed: {e} — using cautious default (22.0)")
        
        return 22.0
    
    def _calculate_regime_stability(self, df: pd.DataFrame, current_regime: str) -> str:
        """
        Calculate how stable the current regime is
        Returns: 'STABLE', 'TRANSITIONING', 'VOLATILE'
        """
        # Look at regime over past 60 days in chunks
        close = df['Close']
        ma_50 = close.rolling(window=50).mean()
        
        if len(close) < 60:
            return 'TRANSITIONING'
        
        # Check if trend has been consistent
        recent_trend = []
        for i in range(0, 60, 20):
            idx = -(i + 10)
            if abs(idx) <= len(close):
                price = close.iloc[idx]
                ma = ma_50.iloc[idx]
                if pd.isna(price) or pd.isna(ma):
                    continue
                recent_trend.append('UP' if price > ma else 'DOWN')
        
        # All same direction = STABLE
        if len(set(recent_trend)) == 1:
            return 'STABLE'
        # Mixed = TRANSITIONING or VOLATILE
        elif len(set(recent_trend)) == len(recent_trend):
            return 'VOLATILE'
        else:
            return 'TRANSITIONING'
    
    def _get_market_sentiment(self, vix: float, regime_score: float) -> str:
        """Determine overall market sentiment"""
        if vix > 25:
            return 'FEARFUL'
        elif vix < 12:
            return 'GREEDY'
        elif regime_score > 0.5:
            return 'OPTIMISTIC'
        elif regime_score < -0.5:
            return 'PESSIMISTIC'
        else:
            return 'NEUTRAL'
    
    def _get_trading_recommendation(self, regime: str, strength: str, vix: float) -> str:
        """Generate trading recommendation based on regime"""
        if regime == 'BULL':
            if vix < 15:
                return 'AGGRESSIVE_LONG'  # Buy growth stocks
            else:
                return 'MODERATE_LONG'  # Buy quality stocks
        elif regime == 'BEAR':
            if vix > 25:
                return 'DEFENSIVE'  # Cash, bonds, defensive stocks
            else:
                return 'CAUTIOUS'  # Selective buying, strong fundamentals only
        else:  # SIDEWAYS
            if vix < 15:
                return 'RANGE_TRADING'  # Trade the range
            else:
                return 'WAIT_AND_WATCH'  # Wait for clarity
    
    def _calculate_risk_level(self, regime: str, vix: float) -> str:
        """Calculate overall market risk level"""
        if regime == 'BEAR' and vix > 25:
            return 'VERY_HIGH'
        elif regime == 'BEAR' or vix > 20:
            return 'HIGH'
        elif regime == 'SIDEWAYS' and vix > 15:
            return 'MODERATE'
        elif regime == 'BULL' and vix < 12:
            return 'LOW'
        else:
            return 'MODERATE'
    
    def _calculate_change(self, df: pd.DataFrame, days: int) -> float:
        """Calculate percentage change over N days"""
        if len(df) < days:
            return 0.0
        
        current = df['Close'].iloc[-1]
        past = df['Close'].iloc[-days]
        if past == 0 or pd.isna(past):
            return 0.0
        return ((current - past) / past) * 100
    
    def _load_last_regime(self):
        """F-02: Load previous regime from disk for hysteresis across runs."""
        import json, os
        try:
            if os.path.exists(self._LAST_REGIME_PATH):
                with open(self._LAST_REGIME_PATH) as f:
                    cache = json.load(f)
                cached_at = datetime.fromisoformat(cache['cached_at'])
                age_hours = (datetime.now() - cached_at).total_seconds() / 3600
                if age_hours <= 48:
                    self.logger.info(f"[F-02] Loaded previous regime '{cache['regime']}' for hysteresis (age={age_hours:.1f}h)")
                    return cache['regime']
        except Exception as e:
            self.logger.debug(f"Could not load last regime for hysteresis: {e}")
        return None

    def _cache_regime(self, result: Dict) -> None:
        """HI-05: Persist last successfully detected regime to disk.
        Uses atomic write (temp file + os.replace) to avoid data loss on disk-full or crash.
        """
        import json, os, tempfile
        try:
            _dir = os.path.dirname(self._LAST_REGIME_PATH) or '.'
            os.makedirs(_dir, exist_ok=True)
            cache = {
                'regime': result.get('regime'),
                'regime_strength': result.get('regime_strength'),
                'regime_score': result.get('regime_score'),
                'vix_level': result.get('vix_level'),
                'cached_at': datetime.now().isoformat(),
            }
            _fd, _tmp_path = tempfile.mkstemp(dir=_dir, suffix='.tmp')
            try:
                with os.fdopen(_fd, 'w') as f:
                    json.dump(cache, f, indent=2)
                os.replace(_tmp_path, self._LAST_REGIME_PATH)
            except Exception:
                try:
                    os.unlink(_tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            self.logger.debug(f"Could not cache regime: {e}")

    def _get_fallback_regime(self) -> Dict:
        """HI-05: On API failure, use last known regime (< 24h) or default to BEAR (conservative).
        M2: Uses wall-clock time, not trading-day awareness. Over weekends/holidays the cache
        may be accepted even though a new trading session has opened, or rejected even though
        no new trading data exists. This is an accepted limitation — the BEAR default is safe.
        """
        import json, os
        try:
            if os.path.exists(self._LAST_REGIME_PATH):
                with open(self._LAST_REGIME_PATH) as f:
                    cache = json.load(f)
                cached_at = datetime.fromisoformat(cache['cached_at'])
                age_hours = (datetime.now() - cached_at).total_seconds() / 3600
                if age_hours <= 24:
                    self.logger.warning(f"[HI-05] Using cached regime '{cache['regime']}' (age={age_hours:.1f}h)")
                    result = self._get_default_regime()
                    result['regime'] = cache['regime']
                    result['regime_strength'] = cache.get('regime_strength', 'MODERATE')
                    result['regime_score'] = cache.get('regime_score', 0.0)
                    result['regime_confidence'] = 0.3
                    result['market_sentiment'] = 'CACHED'
                    return result
        except Exception as e:
            self.logger.debug(f"Could not load cached regime: {e}")
        self.logger.warning("[HI-05] No valid cached regime; defaulting to BEAR (conservative)")
        result = self._get_default_regime()
        result['regime'] = 'BEAR'
        result['regime_strength'] = 'ASSUMED'
        result['regime_confidence'] = 0.1
        result['market_sentiment'] = 'ASSUMED_BEAR'
        return result

    def _get_default_regime(self) -> Dict:
        """Return default regime when data unavailable"""
        return {
            'regime': 'UNKNOWN',
            'regime_strength': 'UNKNOWN',
            'regime_score': 0.0,
            'regime_confidence': 0.0,
            'regime_stability': 'UNKNOWN',
            'trend_signal': 0.0,
            'momentum_signal': 0.0,
            'volatility_signal': 0.0,
            'breadth_signal': 0.0,
            'vix_level': 15.0,
            'market_sentiment': 'NEUTRAL',
            'trading_recommendation': 'WAIT_AND_WATCH',
            'risk_level': 'MODERATE',
            'current_nifty': 0.0,
            'nifty_change_1m': 0.0,
            'nifty_change_3m': 0.0,
            'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def adjust_stock_score_by_regime(self, stock_score: float, stock_data: Dict, regime_data: Dict) -> Dict:
        """
        Adjust individual stock score based on market regime
        
        Args:
            stock_score: Original stock score (0-100)
            stock_data: Stock analysis data
            regime_data: Current market regime data
            
        Returns:
            Dict with adjusted score and explanations
        """
        def _sv(v, d):
            if v is None:
                return d
            try:
                f = float(v)
                return d if (np.isnan(f) or np.isinf(f)) else f
            except (TypeError, ValueError):
                return d

        stock_score = _sv(stock_score, 50.0)
        regime = regime_data.get('regime', 'UNKNOWN')
        regime_score = _sv(regime_data.get('regime_score'), 0)
        vix = _sv(regime_data.get('vix_level'), 15.0)
        
        if regime == 'UNKNOWN':
            return {
                'original_score': stock_score,
                'adjusted_score': stock_score,
                'regime_adjustment': 0.0,
                'adjustment_reasons': ['Regime unknown — no adjustment applied'],
                'regime_context': 'UNKNOWN market'
            }
        
        adjustment = 0.0
        adjustments = []
        
        _pe = _sv(stock_data.get('pe_ratio'), 20)
        is_growth = _pe > 25
        is_value = _pe < 15
        beta = _sv(stock_data.get('beta'), 1.0)
        
        # BULL MARKET adjustments
        if regime == 'BULL':
            # Growth stocks perform better in bull markets
            if is_growth:
                adjustment += 5.0
                adjustments.append("Growth stock premium in bull market (+5)")
            
            # High beta stocks outperform
            if beta > 1.2:
                adjustment += 3.0
                adjustments.append("High beta advantage in bull market (+3)")
            
            # Momentum stocks get boost
            _rsi = _sv(stock_data.get('real_rsi'), 50)
            if _rsi > 60:
                adjustment += 2.0
                adjustments.append("Momentum advantage in bull market (+2)")
        
        elif regime == 'BEAR':
            _bear_magnitude = abs(_sv(regime_data.get('regime_score'), -0.6))
            if _bear_magnitude < 0.6:
                _bear_base = -2.0
            elif _bear_magnitude < 0.75:
                _bear_base = -3.5
            else:
                _bear_base = -5.0
            adjustment += _bear_base
            adjustments.append(f"Bear market scaled penalty ({_bear_base:+.1f}, magnitude={_bear_magnitude:.2f})")

            if vix > 15:
                _vix_addon = min(3.0, (vix - 15.0) / 5.0)
                adjustment -= _vix_addon
                adjustments.append(f"VIX-scaled bear penalty (-{_vix_addon:.1f}, VIX={vix:.1f})")

            _bear_bonus = 0.0
            if is_value:
                _bear_bonus += 2.0
                adjustments.append("Value stock partial credit in bear (+2)")
            if beta < 0.8:
                _bear_bonus += 1.0
                adjustments.append("Low beta partial credit in bear (+1)")
            _bear_bonus = min(_bear_bonus, 3.0)
            adjustment += _bear_bonus
            
            _rsi = _sv(stock_data.get('real_rsi'), 50)
            if _rsi > 70:
                adjustment -= 5.0
                adjustments.append("Overbought penalty in bear market (-5)")
            
            if _rsi < 30:
                adjustment += 2.0
                adjustments.append("Oversold partial opportunity in bear (+2)")

            _pchg_20d = _sv(stock_data.get('enhanced_price_change_20d'), 0)
            if _pchg_20d < -10:
                _mom_penalty = min(5.0, 3.0 + 2.0 * (abs(_pchg_20d) - 10) / 10)
                adjustment -= _mom_penalty
                adjustments.append(f"Declining momentum penalty (-{_mom_penalty:.1f}, 20d chg={_pchg_20d:.1f}%)")
        
        else:
            roe = _sv(stock_data.get('roe'), 0)
            if roe > 15:
                adjustment += 3.0
                adjustments.append("Quality premium in sideways market (+3)")
            
            _rsi = _sv(stock_data.get('real_rsi'), 50)
            if 40 < _rsi < 60:
                adjustment += 2.0
                adjustments.append("Range-trading setup (+2)")
        
        # VIX adjustments (applies to all regimes)
        if vix > 25:  # High fear
            # Penalize risky stocks
            if beta > 1.2:
                adjustment -= 3.0
                adjustments.append("High beta penalty in high VIX (-3)")
        
        elif vix < 12:  # Low fear (complacency)
            # Markets might be overbought
            if regime == 'BULL' and stock_score > 80:
                adjustment -= 2.0
                adjustments.append("Overbought market caution (-2)")
        
        # Apply adjustment (BEAR can go deeper to differentiate declining stocks)
        _adj_floor = -8.0 if regime == 'BEAR' else -6.0
        adjustment = np.clip(adjustment, _adj_floor, 10.0)
        adjusted_score = np.clip(stock_score + adjustment, 0, 100)
        
        return {
            'original_score': stock_score,
            'adjusted_score': adjusted_score,
            'regime_adjustment': adjustment,
            'adjustment_reasons': adjustments,
            'regime_context': f"{regime} market ({regime_data.get('regime_strength', 'MODERATE')})"
        }


def get_market_regime(period_days: int = 180) -> Dict:
    """
    Convenience function to get current market regime
    
    Args:
        period_days: Analysis period (default 180 days)
        
    Returns:
        Dict with market regime data
    """
    detector = MarketRegimeDetector()
    return detector.detect_regime(period_days)


if __name__ == "__main__":
    # Test market regime detection
    print("=" * 80)
    print("🔍 MARKET REGIME DETECTION TEST")
    print("=" * 80)
    
    detector = MarketRegimeDetector()
    regime = detector.detect_regime(period_days=180)
    
    print(f"\n📊 CURRENT MARKET REGIME")
    print("-" * 80)
    print(f"Regime: {regime['regime']} ({regime['regime_strength']})")
    print(f"Confidence: {regime['regime_confidence']:.2%}")
    print(f"Stability: {regime['regime_stability']}")
    print(f"Regime Score: {regime['regime_score']:.3f}")
    
    print(f"\n📈 MARKET INDICATORS")
    print("-" * 80)
    print(f"Trend Signal: {regime['trend_signal']:.3f}")
    print(f"Momentum Signal: {regime['momentum_signal']:.3f}")
    print(f"Volatility Signal: {regime['volatility_signal']:.3f}")
    print(f"Breadth Signal: {regime['breadth_signal']:.3f}")
    
    print(f"\n😨 FEAR & SENTIMENT")
    print("-" * 80)
    print(f"India VIX: {regime['vix_level']:.2f}")
    print(f"Market Sentiment: {regime['market_sentiment']}")
    print(f"Risk Level: {regime['risk_level']}")
    
    print(f"\n💡 TRADING STRATEGY")
    print("-" * 80)
    print(f"Recommendation: {regime['trading_recommendation']}")
    
    print(f"\n📉 NIFTY 50 PERFORMANCE")
    print("-" * 80)
    print(f"Current Level: {regime['current_nifty']:.2f}")
    print(f"1-Month Change: {regime['nifty_change_1m']:.2f}%")
    print(f"3-Month Change: {regime['nifty_change_3m']:.2f}%")
    
    print(f"\n⏰ Analysis Time: {regime['analysis_timestamp']}")
    print("=" * 80)
    
    # Test stock score adjustment
    print("\n🔧 TESTING STOCK SCORE ADJUSTMENT")
    print("=" * 80)
    
    sample_stock = {
        'symbol': 'RELIANCE',
        'pe_ratio': 28.5,
        'beta': 1.15,
        'roe': 12.5,
        'real_rsi': 65.3
    }
    
    adjusted = detector.adjust_stock_score_by_regime(75.0, sample_stock, regime)
    
    print(f"Stock: {sample_stock['symbol']}")
    print(f"Original Score: {adjusted['original_score']:.1f}")
    print(f"Adjusted Score: {adjusted['adjusted_score']:.1f}")
    print(f"Adjustment: {adjusted['regime_adjustment']:+.1f} points")
    print(f"Regime Context: {adjusted['regime_context']}")
    print(f"\nAdjustment Reasons:")
    for reason in adjusted['adjustment_reasons']:
        print(f"  • {reason}")
    
    print("\n" + "=" * 80)
    print("✅ Market Regime Detection test complete!")
