"""
Advanced Technical Pattern Recognition Module
Detects classic chart patterns for enhanced trading signals
"""

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from typing import Dict, List, Tuple, Optional
import logging

class PatternRecognizer:
    """
    Advanced pattern recognition for technical analysis
    Detects: Head & Shoulders, Double Top/Bottom, Cup & Handle, Triangles, Flags, Wedges
    """
    
    def __init__(self, min_pattern_length: int = 20, max_pattern_length: int = 100):
        """
        Initialize pattern recognizer
        
        Args:
            min_pattern_length: Minimum bars for pattern formation
            max_pattern_length: Maximum bars to look back for patterns
        """
        self.min_pattern_length = min_pattern_length
        self.max_pattern_length = max_pattern_length
        self.logger = logging.getLogger(__name__)
        
    def find_peaks_and_troughs(self, prices: pd.Series, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find local peaks (highs) and troughs (lows) in price data
        
        Args:
            prices: Price series (typically 'Close' prices)
            order: Number of points on each side to compare
            
        Returns:
            Tuple of (peak_indices, trough_indices)
        """
        # Find local maxima (peaks)
        peaks = argrelextrema(prices.values, np.greater, order=order)[0]
        
        # Find local minima (troughs)
        troughs = argrelextrema(prices.values, np.less, order=order)[0]
        
        return peaks, troughs
    
    def detect_head_and_shoulders(self, df: pd.DataFrame) -> Dict:
        """
        Detect Head and Shoulders pattern (bearish reversal)
        
        Pattern: Three peaks where middle peak (head) is higher than two shoulders
        Signal: Strong bearish reversal
        
        Returns:
            Dict with pattern info: {'detected': bool, 'confidence': float, 'target': float, 'type': str}
        """
        if len(df) < self.min_pattern_length:
            return {'detected': False, 'confidence': 0.0, 'type': 'head_and_shoulders'}
        
        prices = df['Close'].tail(self.max_pattern_length)
        peaks, troughs = self.find_peaks_and_troughs(prices, order=5)
        
        # Need at least 3 peaks and 2 troughs
        if len(peaks) < 3 or len(troughs) < 2:
            return {'detected': False, 'confidence': 0.0, 'type': 'head_and_shoulders'}
        
        # Check last 3 peaks for H&S pattern
        for i in range(len(peaks) - 2):
            left_shoulder_idx = peaks[i]
            head_idx = peaks[i + 1]
            right_shoulder_idx = peaks[i + 2]
            
            left_shoulder = prices.iloc[left_shoulder_idx]
            head = prices.iloc[head_idx]
            right_shoulder = prices.iloc[right_shoulder_idx]
            
            if left_shoulder == 0 or head == 0:
                continue

            # Head should be higher than both shoulders
            if head > left_shoulder and head > right_shoulder:
                # Shoulders should be roughly equal (within 3%)
                shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder
                
                if shoulder_diff < 0.03:  # Shoulders within 3%
                    # Find neckline (support between shoulders)
                    neckline_troughs = [t for t in troughs if left_shoulder_idx < t < right_shoulder_idx]
                    
                    if len(neckline_troughs) >= 1:
                        neckline = prices.iloc[neckline_troughs[0]]
                        current_price = prices.iloc[-1]
                        
                        # Pattern confirmed if price breaks below neckline
                        if current_price < neckline:
                            # Calculate confidence based on pattern quality
                            head_prominence = (head - max(left_shoulder, right_shoulder)) / head
                            confidence = min(0.9, 0.5 + head_prominence * 10)
                            
                            # Price target: Distance from head to neckline projected down
                            target_distance = head - neckline
                            target_price = neckline - target_distance
                            
                            return {
                                'detected': True,
                                'confidence': confidence,
                                'type': 'head_and_shoulders',
                                'direction': 'bearish',
                                'target': target_price,
                                'neckline': neckline,
                                'pattern_start': left_shoulder_idx,
                                'pattern_end': right_shoulder_idx
                            }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'head_and_shoulders'}
    
    def detect_inverse_head_and_shoulders(self, df: pd.DataFrame) -> Dict:
        """
        Detect Inverse Head and Shoulders pattern (bullish reversal)
        
        Pattern: Three troughs where middle trough (head) is lower than two shoulders
        Signal: Strong bullish reversal
        """
        if len(df) < self.min_pattern_length:
            return {'detected': False, 'confidence': 0.0, 'type': 'inverse_head_and_shoulders'}
        
        prices = df['Close'].tail(self.max_pattern_length)
        peaks, troughs = self.find_peaks_and_troughs(prices, order=5)
        
        # Need at least 3 troughs and 2 peaks
        if len(troughs) < 3 or len(peaks) < 2:
            return {'detected': False, 'confidence': 0.0, 'type': 'inverse_head_and_shoulders'}
        
        # Check last 3 troughs for inverse H&S pattern
        for i in range(len(troughs) - 2):
            left_shoulder_idx = troughs[i]
            head_idx = troughs[i + 1]
            right_shoulder_idx = troughs[i + 2]
            
            left_shoulder = prices.iloc[left_shoulder_idx]
            head = prices.iloc[head_idx]
            right_shoulder = prices.iloc[right_shoulder_idx]
            
            if left_shoulder == 0 or head == 0:
                continue

            # Head should be lower than both shoulders
            if head < left_shoulder and head < right_shoulder:
                # Shoulders should be roughly equal (within 3%)
                shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder
                
                if shoulder_diff < 0.03:
                    # Find neckline (resistance between shoulders)
                    neckline_peaks = [p for p in peaks if left_shoulder_idx < p < right_shoulder_idx]
                    
                    if len(neckline_peaks) >= 1:
                        neckline = prices.iloc[neckline_peaks[0]]
                        current_price = prices.iloc[-1]
                        
                        # Pattern confirmed if price breaks above neckline
                        if current_price > neckline:
                            head_prominence = (min(left_shoulder, right_shoulder) - head) / head if head != 0 else 0
                            confidence = min(0.9, 0.5 + head_prominence * 10)
                            
                            target_distance = neckline - head
                            target_price = neckline + target_distance
                            
                            return {
                                'detected': True,
                                'confidence': confidence,
                                'type': 'inverse_head_and_shoulders',
                                'direction': 'bullish',
                                'target': target_price,
                                'neckline': neckline,
                                'pattern_start': left_shoulder_idx,
                                'pattern_end': right_shoulder_idx
                            }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'inverse_head_and_shoulders'}
    
    def detect_double_top(self, df: pd.DataFrame) -> Dict:
        """
        Detect Double Top pattern (bearish reversal)
        
        Pattern: Two peaks at roughly same level with a trough between
        Signal: Bearish reversal
        """
        if len(df) < self.min_pattern_length:
            return {'detected': False, 'confidence': 0.0, 'type': 'double_top'}
        
        prices = df['Close'].tail(self.max_pattern_length)
        peaks, troughs = self.find_peaks_and_troughs(prices, order=5)
        
        if len(peaks) < 2 or len(troughs) < 1:
            return {'detected': False, 'confidence': 0.0, 'type': 'double_top'}
        
        # Check last 2 peaks
        for i in range(len(peaks) - 1):
            first_peak_idx = peaks[i]
            second_peak_idx = peaks[i + 1]
            
            first_peak = prices.iloc[first_peak_idx]
            second_peak = prices.iloc[second_peak_idx]
            
            if first_peak == 0:
                continue
            # Peaks should be roughly equal (within 2%)
            peak_diff = abs(first_peak - second_peak) / first_peak
            
            if peak_diff < 0.02:
                # Find trough between peaks
                between_troughs = [t for t in troughs if first_peak_idx < t < second_peak_idx]
                
                if len(between_troughs) >= 1:
                    support = prices.iloc[between_troughs[0]]
                    current_price = prices.iloc[-1]
                    
                    # Pattern confirmed if price breaks below support
                    if current_price < support:
                        confidence = min(0.85, 0.6 + (1 - peak_diff) * 5)
                        
                        # Target: Distance from peaks to support projected down
                        target_distance = first_peak - support
                        target_price = support - target_distance
                        
                        return {
                            'detected': True,
                            'confidence': confidence,
                            'type': 'double_top',
                            'direction': 'bearish',
                            'target': target_price,
                            'support': support,
                            'pattern_start': first_peak_idx,
                            'pattern_end': second_peak_idx
                        }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'double_top'}
    
    def detect_double_bottom(self, df: pd.DataFrame) -> Dict:
        """
        Detect Double Bottom pattern (bullish reversal)
        
        Pattern: Two troughs at roughly same level with a peak between
        Signal: Bullish reversal
        """
        if len(df) < self.min_pattern_length:
            return {'detected': False, 'confidence': 0.0, 'type': 'double_bottom'}
        
        prices = df['Close'].tail(self.max_pattern_length)
        peaks, troughs = self.find_peaks_and_troughs(prices, order=5)
        
        if len(troughs) < 2 or len(peaks) < 1:
            return {'detected': False, 'confidence': 0.0, 'type': 'double_bottom'}
        
        # Check last 2 troughs
        for i in range(len(troughs) - 1):
            first_trough_idx = troughs[i]
            second_trough_idx = troughs[i + 1]
            
            first_trough = prices.iloc[first_trough_idx]
            second_trough = prices.iloc[second_trough_idx]
            
            if first_trough == 0:
                continue
            # Troughs should be roughly equal (within 2%)
            trough_diff = abs(first_trough - second_trough) / first_trough
            
            if trough_diff < 0.02:
                # Find peak between troughs
                between_peaks = [p for p in peaks if first_trough_idx < p < second_trough_idx]
                
                if len(between_peaks) >= 1:
                    resistance = prices.iloc[between_peaks[0]]
                    current_price = prices.iloc[-1]
                    
                    # Pattern confirmed if price breaks above resistance
                    if current_price > resistance:
                        confidence = min(0.85, 0.6 + (1 - trough_diff) * 5)
                        
                        target_distance = resistance - first_trough
                        target_price = resistance + target_distance
                        
                        return {
                            'detected': True,
                            'confidence': confidence,
                            'type': 'double_bottom',
                            'direction': 'bullish',
                            'target': target_price,
                            'resistance': resistance,
                            'pattern_start': first_trough_idx,
                            'pattern_end': second_trough_idx
                        }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'double_bottom'}
    
    def detect_triangle(self, df: pd.DataFrame) -> Dict:
        """
        Detect Triangle patterns (continuation/reversal)
        
        Types: Ascending, Descending, Symmetrical
        """
        if len(df) < self.min_pattern_length:
            return {'detected': False, 'confidence': 0.0, 'type': 'triangle'}
        
        prices = df['Close'].tail(60)  # Last 60 days
        highs = df['High'].tail(60)
        lows = df['Low'].tail(60)
        
        peaks, troughs = self.find_peaks_and_troughs(prices, order=3)
        
        if len(peaks) < 2 or len(troughs) < 2:
            return {'detected': False, 'confidence': 0.0, 'type': 'triangle'}
        
        # Get recent peaks and troughs
        recent_peaks = peaks[-4:] if len(peaks) >= 4 else peaks
        recent_troughs = troughs[-4:] if len(troughs) >= 4 else troughs
        
        if len(recent_peaks) >= 2 and len(recent_troughs) >= 2:
            # Fit trendlines to peaks and troughs
            peak_prices = [highs.iloc[p] for p in recent_peaks]
            trough_prices = [lows.iloc[t] for t in recent_troughs]
            
            # Calculate slopes normalised by price level (% per step)
            _mp = np.mean(peak_prices)
            avg_peak = _mp if pd.notna(_mp) and _mp != 0 else 1.0
            _mt = np.mean(trough_prices)
            avg_trough = _mt if pd.notna(_mt) and _mt != 0 else 1.0
            peak_slope = ((peak_prices[-1] - peak_prices[0]) / len(recent_peaks)) / avg_peak
            trough_slope = ((trough_prices[-1] - trough_prices[0]) / len(recent_troughs)) / avg_trough
            
            current_price = prices.iloc[-1]
            
            FLAT_THRESHOLD = 0.005   # ≤0.5 % per step ≈ flat
            TREND_THRESHOLD = 0.005  # >0.5 % per step ≈ trending

            # Ascending Triangle: flat resistance, rising support
            if abs(peak_slope) < FLAT_THRESHOLD and trough_slope > TREND_THRESHOLD:
                resistance = np.mean(peak_prices)
                if current_price > resistance * 0.98:
                    return {
                        'detected': True,
                        'confidence': 0.75,
                        'type': 'ascending_triangle',
                        'direction': 'bullish',
                        'target': resistance + (resistance - trough_prices[0]),
                        'resistance': resistance
                    }
            
            # Descending Triangle: flat support, falling resistance
            elif abs(trough_slope) < FLAT_THRESHOLD and peak_slope < -TREND_THRESHOLD:
                support = np.mean(trough_prices)
                if current_price < support * 1.02:
                    return {
                        'detected': True,
                        'confidence': 0.75,
                        'type': 'descending_triangle',
                        'direction': 'bearish',
                        'target': support - (peak_prices[0] - support),
                        'support': support
                    }
            
            # Symmetrical Triangle: converging trendlines
            elif peak_slope < -(TREND_THRESHOLD / 2) and trough_slope > (TREND_THRESHOLD / 2):
                apex_distance = abs(peak_prices[-1] - trough_prices[-1])
                if apex_distance < (peak_prices[0] - trough_prices[0]) * 0.3:  # Near apex
                    return {
                        'detected': True,
                        'confidence': 0.65,
                        'type': 'symmetrical_triangle',
                        'direction': 'neutral',  # Breakout direction uncertain
                        'apex_distance': apex_distance
                    }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'triangle'}
    
    def detect_flag(self, df: pd.DataFrame) -> Dict:
        """
        Detect Flag pattern (continuation)
        
        Pattern: Strong trend followed by consolidation in narrow channel
        Signal: Continuation of prior trend
        """
        if len(df) < 30:
            return {'detected': False, 'confidence': 0.0, 'type': 'flag'}
        
        prices = df['Close'].tail(30)
        
        # Check for strong prior move (flagpole)
        flagpole_start = prices.iloc[0]
        consolidation_start = prices.iloc[10]
        recent_prices = prices.tail(10)
        
        # Bullish flag: strong uptrend then sideways
        _flag_mean = recent_prices.mean()
        if _flag_mean == 0:
            return {'detected': False, 'confidence': 0.0, 'type': 'flag'}
        if consolidation_start > flagpole_start * 1.05:  # 5%+ move up
            price_range = recent_prices.max() - recent_prices.min()
            if price_range / _flag_mean < 0.03:  # Tight consolidation
                return {
                    'detected': True,
                    'confidence': 0.70,
                    'type': 'bull_flag',
                    'direction': 'bullish',
                    'target': prices.iloc[-1] + (consolidation_start - flagpole_start)
                }
        
        # Bearish flag: strong downtrend then sideways
        elif consolidation_start < flagpole_start * 0.95:  # 5%+ move down
            price_range = recent_prices.max() - recent_prices.min()
            if price_range / _flag_mean < 0.03:
                return {
                    'detected': True,
                    'confidence': 0.70,
                    'type': 'bear_flag',
                    'direction': 'bearish',
                    'target': prices.iloc[-1] - (flagpole_start - consolidation_start)
                }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'flag'}
    
    def detect_cup_and_handle(self, df: pd.DataFrame) -> Dict:
        """
        Detect Cup and Handle pattern (bullish continuation)
        
        Pattern: U-shaped cup followed by smaller downward drift (handle)
        Signal: Strong bullish continuation
        """
        if len(df) < 40:
            return {'detected': False, 'confidence': 0.0, 'type': 'cup_and_handle'}
        
        prices = df['Close'].tail(60)
        
        # Divide into cup (first 40) and handle (last 20)
        cup_prices = prices.iloc[:40]
        handle_prices = prices.iloc[40:]
        
        # Cup should be U-shaped
        cup_start = cup_prices.iloc[0]
        cup_low = cup_prices.min()
        cup_end = cup_prices.iloc[-1]
        
        # Check for U-shape: start and end near same level, significant dip
        if cup_start == 0:
            return {'detected': False, 'confidence': 0.0, 'type': 'cup_and_handle'}
        if abs(cup_start - cup_end) / cup_start < 0.05:  # Within 5%
            cup_depth = (cup_start - cup_low) / cup_start
            
            if 0.10 < cup_depth < 0.40:  # 10-40% depth
                # Handle should drift down slightly
                handle_high = handle_prices.max()
                handle_low = handle_prices.min()
                handle_depth = (handle_high - handle_low) / handle_high if handle_high != 0 else 0
                
                if handle_depth < 0.15 and handle_prices.iloc[-1] > handle_low * 1.02:
                    # Pattern confirmed - breakout above cup rim
                    cup_rim = max(cup_start, cup_end)
                    current_price = prices.iloc[-1]
                    
                    if current_price >= cup_rim * 0.98:
                        return {
                            'detected': True,
                            'confidence': 0.80,
                            'type': 'cup_and_handle',
                            'direction': 'bullish',
                            'target': cup_rim + (cup_rim - cup_low),
                            'cup_rim': cup_rim
                        }
        
        return {'detected': False, 'confidence': 0.0, 'type': 'cup_and_handle'}
    
    def detect_all_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """
        Run all pattern detection methods and return detected patterns
        
        Returns:
            List of detected patterns with their details
        """
        patterns = []
        
        # Run all detection methods
        pattern_methods = [
            self.detect_head_and_shoulders,
            self.detect_inverse_head_and_shoulders,
            self.detect_double_top,
            self.detect_double_bottom,
            self.detect_triangle,
            self.detect_flag,
            self.detect_cup_and_handle
        ]
        
        for method in pattern_methods:
            try:
                result = method(df)
                if result['detected']:
                    patterns.append(result)
            except Exception as e:
                self.logger.warning(f"Pattern detection error in {method.__name__}: {e}")
        
        return patterns
    
    def get_pattern_score(self, patterns: List[Dict]) -> Dict:
        """
        Calculate overall pattern score from detected patterns
        
        Returns:
            Dict with bullish_score, bearish_score, and dominant_signal
        """
        if not patterns:
            return {
                'bullish_score': 0.0,
                'bearish_score': 0.0,
                'dominant_signal': 'neutral',
                'confidence': 0.0
            }
        
        bullish_score = 0.0
        bearish_score = 0.0
        
        for pattern in patterns:
            confidence = pattern.get('confidence', 0.5)
            direction = pattern.get('direction', 'neutral')
            
            if direction == 'bullish':
                bullish_score += confidence
            elif direction == 'bearish':
                bearish_score += confidence
        
        # Normalize scores
        total = bullish_score + bearish_score
        if total > 0:
            bullish_score = bullish_score / total
            bearish_score = bearish_score / total
        
        # Determine dominant signal
        if bullish_score > bearish_score * 1.5:
            dominant_signal = 'bullish'
            confidence = bullish_score
        elif bearish_score > bullish_score * 1.5:
            dominant_signal = 'bearish'
            confidence = bearish_score
        else:
            dominant_signal = 'neutral'
            confidence = max(bullish_score, bearish_score)
        
        return {
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'dominant_signal': dominant_signal,
            'confidence': confidence,
            'patterns_detected': len(patterns)
        }


def analyze_patterns(df: pd.DataFrame) -> Dict:
    """
    Convenience function to analyze patterns in stock data
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Dict with detected patterns and overall score
    """
    recognizer = PatternRecognizer()
    patterns = recognizer.detect_all_patterns(df)
    score = recognizer.get_pattern_score(patterns)
    
    return {
        'patterns': patterns,
        'score': score
    }


if __name__ == "__main__":
    # Test pattern recognition
    import yfinance as yf
    
    print("Testing Pattern Recognition Module...")
    print("=" * 80)
    
    # Test on a few stocks
    test_symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS']
    
    for symbol in test_symbols:
        print(f"\n📊 Testing {symbol}...")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period='6mo')
        
        if len(df) > 0:
            result = analyze_patterns(df)
            score = result['score']
            patterns = result['patterns']
            
            print(f"✅ Patterns detected: {len(patterns)}")
            print(f"   Bullish Score: {score['bullish_score']:.2%}")
            print(f"   Bearish Score: {score['bearish_score']:.2%}")
            print(f"   Signal: {score['dominant_signal'].upper()} (confidence: {score['confidence']:.2%})")
            
            if patterns:
                print(f"\n   Detected patterns:")
                for p in patterns:
                    print(f"   - {p['type']}: {p['direction']} (confidence: {p['confidence']:.2%})")
        else:
            print(f"❌ No data available")
    
    print("\n" + "=" * 80)
    print("✅ Pattern Recognition Module test complete!")
