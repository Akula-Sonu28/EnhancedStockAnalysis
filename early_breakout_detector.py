"""
Early Breakout Detector V2.0 - IMPROVED
Detects stocks BEFORE breakout (not after) and momentum exhaustion for exits
Addresses the core problem: System recommends BUY after breakout at tops

IMPROVEMENTS in V2.0:
1. Quality filter - Skip low-quality stocks (score <55)
2. Stricter distance thresholds (2-4%, not 2-5%)
3. Volume buildup vs spike differentiation
4. Tighter RSI range (50-60, not 45-60)
5. Stricter consolidation (<4%, not <5%)
6. Higher support test threshold (3+, not 2+)
7. Quality score bonus (new)
8. Multi-factor confirmation required (3+ confirmations, score >=60)
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class EarlyBreakoutDetector:
    """
    Detects PRE-BREAKOUT setups (1-5 days early) and MOMENTUM EXHAUSTION (exit signals)
    V2.0: Improved with stricter criteria for higher quality signals
    """
    
    def __init__(self):
        self.min_data_points = 30
        
    def detect_pre_breakout_setup(self, df: pd.DataFrame, stock_data: dict) -> Dict:
        """
        Detect PRE-BREAKOUT conditions with IMPROVED multi-factor confirmation (V2.0)
        
        IMPROVEMENTS:
        - Quality filter (only stocks with score >=55)
        - Stricter thresholds (reduce false positives)
        - Multi-factor confirmation required (3+ signals)
        - Relative strength consideration
        
        Returns stocks that are setting up for breakout in next 1-5 days
        NOT stocks that have already broken out
        
        Returns:
            dict: {
                'pre_breakout_detected': bool,
                'breakout_probability': float (0-100),
                'expected_breakout_in_days': int,
                'entry_price_range': tuple,
                'resistance_level': float,
                'support_level': float,
                'stop_loss': float,
                'target_price': float,
                'confidence': str,
                'signals': List[str]
            }
        """
        try:
            if len(df) < 30:
                return self._empty_result()
            
            current_price = df['Close'].iloc[-1]
            if current_price <= 0:
                return self._empty_result()
            
            # IMPROVEMENT 1: Quality Filter - Skip low-quality stocks
            _qs = stock_data.get('risk_adjusted_score', stock_data.get('overall_score_with_value', 0))
            quality_score = 0 if (_qs is None or (isinstance(_qs, float) and np.isnan(_qs))) else float(_qs)
            if quality_score < 55:
                return self._empty_result()
            
            # Calculate key levels
            resistance, support = self._calculate_dynamic_levels(df)
            
            # Calculate all pre-breakout signals
            signals = []
            breakout_score = 0
            confirmations_count = 0  # Track number of confirmations
            
            # Signal 1: Price Near Resistance (IMPROVED - stricter distance)
            distance_to_resistance = ((resistance - current_price) / current_price) * 100 if current_price != 0 else 0
            if 2 <= distance_to_resistance <= 4:  # Tightened from 2-5%
                signals.append(f"🎯 SETUP: {distance_to_resistance:.1f}% below resistance")
                breakout_score += 30
                confirmations_count += 1
            elif 0.5 < distance_to_resistance < 2:
                signals.append(f"⚡ IMMINENT: {distance_to_resistance:.1f}% to breakout")
                breakout_score += 40
                confirmations_count += 1
            elif distance_to_resistance > 5:
                breakout_score -= 10  # Too far, penalize
            
            # Signal 2: Volume Building (IMPROVED - gradual, not spike)
            volume_trend = self._detect_volume_buildup(df)
            if volume_trend['building'] and volume_trend['trend'] == 'increasing':
                signals.append(f"📊 Volume building: gradual increase")
                breakout_score += 25
                confirmations_count += 1
            elif volume_trend['trend'] == 'spike':
                breakout_score -= 20  # Already broken out - too late
            
            # Signal 3: RSI Sweet Spot (IMPROVED - tighter range)
            _rsi = stock_data.get('real_rsi')
            _ersi = stock_data.get('enhanced_rsi_14')
            rsi = _rsi if _rsi is not None else (_ersi if _ersi is not None else 50)
            rsi = 50 if (isinstance(rsi, float) and np.isnan(rsi)) else rsi
            if 50 <= rsi <= 60:  # Tightened from 45-60
                signals.append(f"⚡ RSI optimal: {rsi:.0f} (momentum present)")
                breakout_score += 30
                confirmations_count += 1
            elif 45 <= rsi < 50:
                signals.append(f"⚪ RSI neutral: {rsi:.0f}")
                breakout_score += 10
            elif 60 < rsi <= 65:
                signals.append(f"⚠️ RSI warming: {rsi:.0f}")
                breakout_score += 5
            elif rsi > 70:
                breakout_score -= 20  # Overbought - not a setup
            
            # Signal 4: Consolidation Pattern (IMPROVED - stricter range)
            consolidation = self._detect_consolidation(df)
            if consolidation['is_consolidating'] and consolidation['range'] < 4:  # Very tight
                signals.append(f"🔄 Tight consolidation: {consolidation['range']:.1f}% range")
                breakout_score += 25
                confirmations_count += 1
            elif consolidation['is_consolidating']:
                signals.append(f"⚪ Consolidating: {consolidation['range']:.1f}% range")
                breakout_score += 10
            
            # Signal 5: Support Tests (IMPROVED - higher threshold)
            support_tests = self._count_support_tests(df, support)
            if support_tests >= 3:  # Increased from 2
                signals.append(f"💎 Strong support: {support_tests} tests held")
                breakout_score += 20
                confirmations_count += 1
            elif support_tests == 2:
                signals.append(f"⚪ Support tested: {support_tests} times")
                breakout_score += 10
            
            # Signal 6: Higher Lows Pattern
            if self._has_higher_lows(df, lookback=10):
                signals.append("📈 Higher lows structure")
                breakout_score += 15
                confirmations_count += 1
            
            # Signal 7: Quality Score Bonus (NEW)
            if quality_score >= 75:
                signals.append(f"⭐ High quality: Score {quality_score:.0f}")
                breakout_score += 15
                confirmations_count += 1
            elif quality_score >= 65:
                signals.append(f"✅ Good quality: Score {quality_score:.0f}")
                breakout_score += 10
            
            # IMPROVEMENT 8: Multi-Factor Confirmation Required
            # Require at least 3 confirmations + score >= 60 for valid setup
            if confirmations_count < 3 or breakout_score < 60:
                return self._empty_result()

            # IMPROVEMENT 9: False breakout filter
            if self._is_false_breakout(df, resistance):
                breakout_score = int(breakout_score * 0.5)
                signals.append("⚠️ Possible false breakout — price fell back below resistance")
                if breakout_score < 60:
                    return self._empty_result()

            # Determine breakout timing probability (IMPROVED - more conservative)
            if breakout_score >= 90 and confirmations_count >= 5:
                expected_days = 2
                confidence = "VERY HIGH"
                probability = min(90, breakout_score)
            elif breakout_score >= 75 and confirmations_count >= 4:
                expected_days = 2
                confidence = "HIGH"
                probability = min(80, breakout_score)
            elif breakout_score >= 60 and confirmations_count >= 3:
                expected_days = 3
                confidence = "MEDIUM"
                probability = min(70, breakout_score)
            else:
                return self._empty_result()
            
            # Calculate entry strategy
            entry_range = (
                resistance * 0.98,  # 2% below resistance
                resistance * 1.01   # 1% above resistance (confirmation)
            )
            
            # Calculate risk/reward
            risk_amount = current_price - support
            potential_target = resistance + (resistance - support)  # Measured move
            
            return {
                'pre_breakout_detected': True,
                'breakout_probability': probability,
                'expected_breakout_in_days': expected_days,
                'entry_price_range': entry_range,
                'resistance_level': resistance,
                'support_level': support,
                'stop_loss': support * 0.98,  # 2% below support
                'target_price': potential_target,
                'confidence': confidence,
                'signals': signals,
                'current_price': current_price,
                'distance_to_resistance': distance_to_resistance,
                'confirmations': confirmations_count
            }
            
        except Exception as e:
            logging.error(f"Error in pre-breakout detection: {e}")
            return self._empty_result()
    
    def detect_momentum_exhaustion(self, df: pd.DataFrame, stock_data: dict, entry_price: Optional[float] = None, previous_exhaustion_score: float = 0) -> Dict:
        """
        Detect MOMENTUM EXHAUSTION (exit signals before reversal)
        Addresses: "system fails to recommend to book profit"
        
        Exhaustion Signals:
        1. RSI > 75 (overbought extreme)
        2. Volume declining on up moves (no follow-through)
        3. Long upper wicks (rejection at highs)
        4. Bearish divergence (price up, RSI down)
        5. Parabolic move > 15% in 5 days
        
        Returns:
            dict: {
                'exhaustion_detected': bool,
                'exhaustion_score': float (0-100),
                'exit_recommendation': str,
                'profit_booking_pct': float,
                'exit_signals': List[str]
            }
        """
        try:
            if len(df) < 20:
                return self._empty_exhaustion_result()
            
            current_price = df['Close'].iloc[-1]
            signals = []
            exhaustion_score = 0
            
            # Signal 1: RSI Overbought (>75 is extreme)
            _rsi = stock_data.get('real_rsi')
            _ersi = stock_data.get('enhanced_rsi_14')
            rsi = _rsi if _rsi is not None else (_ersi if _ersi is not None else 50)
            rsi = 50 if (isinstance(rsi, float) and np.isnan(rsi)) else rsi
            if rsi > 80:
                signals.append(f"🔴 RSI extreme: {rsi:.0f} (heavy exhaustion)")
                exhaustion_score += 50
            elif rsi > 75:
                signals.append(f"⚠️ RSI overbought: {rsi:.0f}")
                exhaustion_score += 35
            elif rsi > 70:
                signals.append(f"⚪ RSI elevated: {rsi:.0f}")
                exhaustion_score += 20
            
            # Signal 2: Volume Declining (no follow-through)
            volume_declining = self._check_volume_decline(df)
            if volume_declining:
                signals.append("📉 Volume declining on rally")
                exhaustion_score += 20
            
            # Signal 3: Upper Wicks (rejection at highs)
            upper_wicks = self._detect_upper_wicks(df)
            if upper_wicks >= 3:
                signals.append(f"🕯️ Upper wicks: {upper_wicks} rejections")
                exhaustion_score += 20
            
            # Signal 4: Bearish Divergence
            bearish_divergence = self._check_bearish_divergence(df, stock_data)
            if bearish_divergence:
                signals.append("⚠️ Bearish divergence (price up, RSI down)")
                exhaustion_score += 25
            
            # Signal 5: Parabolic Move (ignore NaN closes so mean/return does not propagate NaN)
            _closes_6 = df['Close'].iloc[-6:].dropna()
            if len(_closes_6) >= 2:
                _p0 = float(_closes_6.iloc[0])
                _p1 = float(_closes_6.iloc[-1])
                move_5d = ((_p1 - _p0) / _p0) * 100 if _p0 != 0 else 0.0
            else:
                move_5d = 0.0
            if move_5d > 20:
                signals.append(f"🚀 Parabolic: +{move_5d:.1f}% in 5 days")
                exhaustion_score += 30
            elif move_5d > 15:
                signals.append(f"📈 Strong rally: +{move_5d:.1f}% in 5 days")
                exhaustion_score += 20
            
            # Signal 6: Distance from moving averages
            ma_20 = float(np.nanmean(df['Close'].tail(20).to_numpy(dtype=float)))
            ma_20 = ma_20 if pd.notna(ma_20) and ma_20 != 0 else 1.0
            distance_from_ma = ((current_price - ma_20) / ma_20) * 100
            if distance_from_ma > 15:
                signals.append(f"📏 Extended: {distance_from_ma:.1f}% above 20-MA")
                exhaustion_score += 15
            
            # Hysteresis: once an EXIT tier is triggered, maintain it until the
            # score drops well below the original trigger to prevent on/off flicker.
            if previous_exhaustion_score >= 80 and exhaustion_score >= 55:
                exhaustion_score = max(exhaustion_score, 80)
            elif previous_exhaustion_score >= 70 and exhaustion_score >= 45:
                exhaustion_score = max(exhaustion_score, 70)
            elif previous_exhaustion_score >= 50 and exhaustion_score >= 30:
                exhaustion_score = max(exhaustion_score, 50)

            # Determine exit recommendation
            if exhaustion_score >= 80:
                exit_rec = "🔴 EXIT NOW - Heavy exhaustion"
                booking_pct = 100
            elif exhaustion_score >= 70:
                exit_rec = "🟠 EXIT 75-80% - Strong exhaustion"
                booking_pct = 75
            elif exhaustion_score >= 50:
                exit_rec = "🟡 BOOK 50-60% - Moderate exhaustion"
                booking_pct = 50
            elif exhaustion_score >= 30:
                exit_rec = "⚪ TRAIL STOP - Early exhaustion"
                booking_pct = 25
            else:
                return self._empty_exhaustion_result()
            
            # Calculate profit if entry_price provided
            profit_pct = 0
            if entry_price and entry_price > 0:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            
            return {
                'exhaustion_detected': True,
                'exhaustion_score': exhaustion_score,
                'exit_recommendation': exit_rec,
                'profit_booking_pct': booking_pct,
                'exit_signals': signals,
                'current_price': current_price,
                'profit_pct': profit_pct if profit_pct > 0 else None
            }
            
        except Exception as e:
            logging.error(f"Error in exhaustion detection: {e}")
            return self._empty_exhaustion_result()
    
    # ===== HELPER FUNCTIONS =====
    
    def _calculate_dynamic_levels(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate support and resistance levels"""
        highs = df['High'].tail(30)
        lows = df['Low'].tail(30)
        
        # Resistance: Recent swing high
        resistance = highs.quantile(0.90)
        
        # Support: Recent swing low
        support = lows.quantile(0.10)
        
        return resistance, support
    
    def _detect_volume_buildup(self, df: pd.DataFrame) -> Dict:
        """Detect gradual volume increase (IMPROVED - not spike)"""
        volumes = df['Volume'].tail(15).values
        
        if len(volumes) < 15:
            return {'building': False, 'trend': 'insufficient_data'}
        
        # Check for gradual increase vs spike
        first_third = np.mean(volumes[:5])
        second_third = np.mean(volumes[5:10])
        last_third = np.mean(volumes[10:])
        
        # Gradual buildup: consistent increase
        if last_third > second_third * 1.2 and second_third > first_third * 1.1:
            return {'building': True, 'trend': 'increasing'}
        
        # Spike: sudden jump (already broken out - too late!)
        elif last_third > second_third * 2.0:
            return {'building': False, 'trend': 'spike'}
        
        return {'building': False, 'trend': 'flat'}
    
    def _detect_consolidation(self, df: pd.DataFrame) -> Dict:
        """Detect tight consolidation (IMPROVED - stricter)"""
        recent_prices = df['Close'].tail(15)
        
        if len(recent_prices) < 15:
            return {'is_consolidating': False, 'range': 0}
        
        _mean_p = recent_prices.mean()
        price_range = ((recent_prices.max() - recent_prices.min()) / _mean_p) * 100 if _mean_p != 0 else 0
        
        # Consolidation: < 5% range (tight: < 4%)
        is_consolidating = price_range < 5
        
        return {'is_consolidating': is_consolidating, 'range': price_range}
    
    def _count_support_tests(self, df: pd.DataFrame, support: float) -> int:
        """Count number of times support was tested and held"""
        lows = df['Low'].tail(30)
        
        # Support zone: +/- 2% around support level
        support_zone_low = support * 0.98
        support_zone_high = support * 1.02
        
        tests = 0
        for low in lows:
            if support_zone_low <= low <= support_zone_high:
                tests += 1
        
        return tests
    
    def _has_higher_lows(self, df: pd.DataFrame, lookback: int = 10) -> bool:
        """Check for higher lows pattern (bullish structure)"""
        lows = df['Low'].tail(lookback).values
        
        if len(lows) < lookback:
            return False
        
        # Check if recent lows are trending higher
        first_half_min = np.min(lows[:lookback//2])
        second_half_min = np.min(lows[lookback//2:])
        
        return second_half_min > first_half_min * 1.01
    
    def _check_volume_decline(self, df: pd.DataFrame) -> bool:
        """Check if volume is declining on up moves"""
        volumes = df['Volume'].tail(10).values
        closes = df['Close'].tail(10).values
        
        if len(volumes) < 10:
            return False
        
        # Check if price is rising but volume declining
        price_rising = closes[-1] > closes[-5]
        volume_declining = np.mean(volumes[-3:]) < np.mean(volumes[-6:-3])
        
        return price_rising and volume_declining
    
    def _detect_upper_wicks(self, df: pd.DataFrame) -> int:
        """Count long upper wicks (rejection at highs)"""
        recent = df.tail(10)
        
        upper_wicks = 0
        for _, row in recent.iterrows():
            body = abs(row['Close'] - row['Open'])
            upper_wick = row['High'] - max(row['Close'], row['Open'])
            
            # Upper wick > 2x body size = rejection
            if upper_wick > body * 2:
                upper_wicks += 1
        
        return upper_wicks
    
    def _check_bearish_divergence(self, df: pd.DataFrame, stock_data: dict) -> bool:
        """Check for bearish divergence: price making higher highs while RSI making lower highs."""
        if len(df) < 20:
            return False

        close = df['Close']
        price_higher = close.iloc[-1] > close.iloc[-10]

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        import numpy as _np
        loss_safe = loss.replace(0, _np.nan)
        rs = gain / loss_safe
        rsi_series = (100 - (100 / (1 + rs))).fillna(50)

        if len(rsi_series) < 10:
            return False

        rsi_now = rsi_series.iloc[-1]
        rsi_prior = rsi_series.iloc[-10]

        return price_higher and rsi_now < rsi_prior and rsi_now > 50
    
    def _is_false_breakout(self, df, resistance_level: float) -> bool:
        """Check if price crossed above resistance recently but fell back below."""
        try:
            if df is None or df.empty or len(df) < 5:
                return False
            recent = df.tail(5)
            close = recent['Close']
            crossed_above = (close > resistance_level).any()
            latest_below = float(close.iloc[-1]) < resistance_level
            return crossed_above and latest_below
        except Exception:
            return False

    def _empty_result(self) -> Dict:
        """Return empty pre-breakout result"""
        return {
            'pre_breakout_detected': False,
            'breakout_probability': 0,
            'expected_breakout_in_days': None,
            'entry_price_range': (0, 0),
            'resistance_level': 0,
            'support_level': 0,
            'stop_loss': 0,
            'target_price': 0,
            'confidence': 'NONE',
            'signals': []
        }
    
    def _empty_exhaustion_result(self) -> Dict:
        """Return empty exhaustion result"""
        return {
            'exhaustion_detected': False,
            'exhaustion_score': 0,
            'exit_recommendation': 'HOLD - No exhaustion',
            'profit_booking_pct': 0,
            'exit_signals': []
        }
