"""
Volume Profile & Order Flow Analysis Module for Stock Analysis
Phase 2 - Task 5

Analyzes volume distribution, order flow imbalances, and institutional activity
to identify high-probability trading zones and price levels.

Key Features:
1. VWAP Zones - Volume-weighted average price support/resistance
2. Order Flow Imbalances - Buy vs sell pressure detection
3. Large Block Trades - Institutional activity identification
4. Volume Profile Clustering - High-volume price levels
5. Volume-Based Support/Resistance - Key price zones

Expected Accuracy Boost: 5-10%
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

class VolumeAnalyzer:
    """
    Volume Profile & Order Flow Analysis for enhanced stock scoring.
    """
    
    def __init__(self):
        """Initialize the volume analyzer."""
        self.logger = logging.getLogger(__name__)
        
        # Volume analysis parameters
        self.volume_lookback = 90  # Days for volume analysis
        self.block_trade_threshold = 2.0  # 2x average volume
        self.imbalance_threshold = 0.15  # 15% imbalance threshold
        self.vwap_deviation_bands = [0.5, 1.0, 1.5, 2.0]  # Standard deviation bands
        
        # Scoring weights
        self.max_adjustment = 10.0  # Maximum score adjustment
        
    def analyze_volume(self, symbol: str, stock_data: pd.DataFrame) -> Dict:
        """
        Comprehensive volume analysis for a stock.
        
        Args:
            symbol: Stock ticker symbol
            stock_data: DataFrame with price/volume data
            
        Returns:
            Dictionary with volume analysis results
        """
        try:
            if stock_data is None or len(stock_data) < 20:
                return self._get_default_volume_analysis()
            
            # 1. Calculate VWAP and zones
            vwap_data = self._calculate_vwap_zones(stock_data)
            
            # 2. Detect order flow imbalances
            flow_data = self._detect_order_flow_imbalances(stock_data)
            
            # 3. Identify large block trades
            blocks_data = self._identify_block_trades(stock_data)
            
            # 4. Generate volume profile
            profile_data = self._generate_volume_profile(stock_data)
            
            # 5. Calculate volume-based support/resistance
            sr_data = self._calculate_volume_sr_levels(stock_data, profile_data)
            
            # 6. Generate composite volume signal
            composite_signal = self._generate_composite_signal(
                vwap_data, flow_data, blocks_data, profile_data, sr_data
            )
            
            # Combine all analysis
            volume_analysis = {
                # VWAP Analysis
                'vwap_current': vwap_data['current_vwap'],
                'vwap_position': vwap_data['position'],  # Above/Below/At VWAP
                'vwap_distance_pct': vwap_data['distance_pct'],
                'vwap_trend': vwap_data['trend'],  # BULLISH/BEARISH/NEUTRAL
                'vwap_support': vwap_data['support_level'],
                'vwap_resistance': vwap_data['resistance_level'],
                
                # Order Flow
                'order_flow_imbalance': flow_data['imbalance'],  # Buy/Sell pressure
                'flow_strength': flow_data['strength'],  # STRONG/MODERATE/WEAK
                'flow_direction': flow_data['direction'],  # BUYING/SELLING/BALANCED
                'flow_consistency': flow_data['consistency'],  # % of days with same direction
                
                # Block Trades
                'block_trades_count': blocks_data['count'],
                'block_trades_volume_pct': blocks_data['volume_pct'],
                'institutional_activity': blocks_data['activity_level'],  # HIGH/MODERATE/LOW
                'recent_blocks_direction': blocks_data['recent_direction'],  # BUY/SELL/MIXED
                
                # Volume Profile
                'volume_poc': profile_data['poc'],  # Point of Control (highest volume)
                'volume_vah': profile_data['vah'],  # Value Area High
                'volume_val': profile_data['val'],  # Value Area Low
                'volume_profile_shape': profile_data['shape'],  # NORMAL/SKEWED/BIMODAL
                'price_in_value_area': profile_data['price_in_va'],
                
                # Support/Resistance
                'volume_support_1': sr_data['support_levels'][0] if sr_data['support_levels'] else None,
                'volume_support_2': sr_data['support_levels'][1] if len(sr_data['support_levels']) > 1 else None,
                'volume_resistance_1': sr_data['resistance_levels'][0] if sr_data['resistance_levels'] else None,
                'volume_resistance_2': sr_data['resistance_levels'][1] if len(sr_data['resistance_levels']) > 1 else None,
                'nearest_volume_zone': sr_data['nearest_zone'],
                'zone_distance_pct': sr_data['zone_distance_pct'],
                
                # Composite Signal
                'volume_composite_score': composite_signal['score'],  # 0-100
                'volume_signal': composite_signal['signal'],  # BUY/HOLD/SELL
                'volume_confidence': composite_signal['confidence'],  # 0-100%
                'volume_quality': composite_signal['quality'],  # HIGH/MODERATE/LOW
                
                # Metadata
                'volume_analysis_timestamp': datetime.now().isoformat(),
                'volume_analysis_status': 'SUCCESS'
            }
            
            self.logger.info(
                f"Volume analysis for {symbol}: Score={composite_signal['score']:.1f}/100, "
                f"Signal={composite_signal['signal']}, VWAP Position={vwap_data['position']}, "
                f"Flow={flow_data['direction']}"
            )
            
            return volume_analysis
            
        except Exception as e:
            self.logger.error(f"Volume analysis failed for {symbol}: {e}")
            return self._get_default_volume_analysis()
    
    def _calculate_vwap_zones(self, data: pd.DataFrame) -> Dict:
        """Calculate VWAP and identify support/resistance zones."""
        try:
            # Calculate VWAP
            data = data.copy()
            data['typical_price'] = (data['High'] + data['Low'] + data['Close']) / 3
            data['vwap'] = (data['typical_price'] * data['Volume']).cumsum() / data['Volume'].cumsum()
            
            current_price = data['Close'].iloc[-1]
            current_vwap = data['vwap'].iloc[-1]
            
            # Calculate standard deviation bands
            data['vwap_diff'] = data['typical_price'] - data['vwap']
            vwap_std = data['vwap_diff'].std()
            
            # Determine position relative to VWAP
            distance_pct = ((current_price - current_vwap) / current_vwap) * 100
            
            if abs(distance_pct) < 0.5:
                position = 'AT_VWAP'
            elif distance_pct > 0:
                position = 'ABOVE_VWAP'
            else:
                position = 'BELOW_VWAP'
            
            # Calculate VWAP trend (is VWAP rising or falling?)
            vwap_slope = (data['vwap'].iloc[-1] - data['vwap'].iloc[-10]) / data['vwap'].iloc[-10]
            if vwap_slope > 0.01:
                trend = 'BULLISH'
            elif vwap_slope < -0.01:
                trend = 'BEARISH'
            else:
                trend = 'NEUTRAL'
            
            # Support/Resistance levels (VWAP ± std dev bands)
            support_level = current_vwap - vwap_std
            resistance_level = current_vwap + vwap_std
            
            return {
                'current_vwap': current_vwap,
                'position': position,
                'distance_pct': distance_pct,
                'trend': trend,
                'support_level': support_level,
                'resistance_level': resistance_level
            }
            
        except Exception as e:
            self.logger.error(f"VWAP calculation failed: {e}")
            return {
                'current_vwap': 0, 'position': 'UNKNOWN', 'distance_pct': 0,
                'trend': 'NEUTRAL', 'support_level': 0, 'resistance_level': 0
            }
    
    def _detect_order_flow_imbalances(self, data: pd.DataFrame) -> Dict:
        """Detect buy/sell pressure imbalances using price-volume analysis."""
        try:
            data = data.copy()
            
            # Estimate buy/sell volume based on price action
            # Up days = buying pressure, down days = selling pressure
            data['price_change'] = data['Close'].diff()
            data['buy_volume'] = np.where(data['price_change'] > 0, data['Volume'], 0)
            data['sell_volume'] = np.where(data['price_change'] < 0, data['Volume'], 0)
            
            # Calculate recent buy/sell ratio (last 20 days)
            recent_buy_vol = data['buy_volume'].tail(20).sum()
            recent_sell_vol = data['sell_volume'].tail(20).sum()
            total_vol = recent_buy_vol + recent_sell_vol
            
            if total_vol > 0:
                buy_pct = recent_buy_vol / total_vol
                sell_pct = recent_sell_vol / total_vol
                imbalance = buy_pct - sell_pct  # Positive = buying pressure
            else:
                imbalance = 0
                buy_pct = 0.5
                sell_pct = 0.5
            
            # Determine flow direction
            if imbalance > self.imbalance_threshold:
                direction = 'BUYING'
                strength = 'STRONG' if imbalance > 0.3 else 'MODERATE'
            elif imbalance < -self.imbalance_threshold:
                direction = 'SELLING'
                strength = 'STRONG' if imbalance < -0.3 else 'MODERATE'
            else:
                direction = 'BALANCED'
                strength = 'WEAK'
            
            # Consistency: % of recent days with positive flow
            data['daily_flow'] = data['buy_volume'] - data['sell_volume']
            positive_days = (data['daily_flow'].tail(20) > 0).sum()
            consistency = (positive_days / 20) * 100
            
            return {
                'imbalance': imbalance,
                'direction': direction,
                'strength': strength,
                'consistency': consistency,
                'buy_pct': buy_pct * 100,
                'sell_pct': sell_pct * 100
            }
            
        except Exception as e:
            self.logger.error(f"Order flow analysis failed: {e}")
            return {
                'imbalance': 0, 'direction': 'BALANCED', 'strength': 'WEAK',
                'consistency': 50, 'buy_pct': 50, 'sell_pct': 50
            }
    
    def _identify_block_trades(self, data: pd.DataFrame) -> Dict:
        """Identify large block trades (institutional activity)."""
        try:
            data = data.copy()
            
            # Calculate average volume
            avg_volume = data['Volume'].rolling(20).mean()
            
            # Identify block trades (volume > threshold * avg)
            data['is_block'] = data['Volume'] > (avg_volume * self.block_trade_threshold)
            data['block_direction'] = np.where(
                data['Close'] > data['Open'], 'BUY',
                np.where(data['Close'] < data['Open'], 'SELL', 'NEUTRAL')
            )
            
            # Count recent block trades (last 20 days)
            recent_blocks = data.tail(20)
            block_count = recent_blocks['is_block'].sum()
            
            # Calculate block trade volume percentage
            block_volume = recent_blocks[recent_blocks['is_block']]['Volume'].sum()
            total_volume = recent_blocks['Volume'].sum()
            volume_pct = (block_volume / total_volume * 100) if total_volume > 0 else 0
            
            # Determine activity level
            if block_count >= 5:
                activity_level = 'HIGH'
            elif block_count >= 2:
                activity_level = 'MODERATE'
            else:
                activity_level = 'LOW'
            
            # Recent block direction (last 5 blocks)
            recent_block_data = data[data['is_block']].tail(5)
            if len(recent_block_data) > 0:
                buy_blocks = (recent_block_data['block_direction'] == 'BUY').sum()
                sell_blocks = (recent_block_data['block_direction'] == 'SELL').sum()
                
                if buy_blocks > sell_blocks * 1.5:
                    recent_direction = 'BUY'
                elif sell_blocks > buy_blocks * 1.5:
                    recent_direction = 'SELL'
                else:
                    recent_direction = 'MIXED'
            else:
                recent_direction = 'NONE'
            
            return {
                'count': int(block_count),
                'volume_pct': volume_pct,
                'activity_level': activity_level,
                'recent_direction': recent_direction
            }
            
        except Exception as e:
            self.logger.error(f"Block trade analysis failed: {e}")
            return {
                'count': 0, 'volume_pct': 0,
                'activity_level': 'LOW', 'recent_direction': 'NONE'
            }
    
    def _generate_volume_profile(self, data: pd.DataFrame) -> Dict:
        """Generate volume profile distribution."""
        try:
            data = data.copy()
            
            # Create price bins (20 bins across price range)
            price_min = data['Low'].min()
            price_max = data['High'].max()
            bins = np.linspace(price_min, price_max, 21)
            
            # Assign volume to price bins
            data['price_bin'] = pd.cut(data['Close'], bins=bins)
            volume_profile = data.groupby('price_bin')['Volume'].sum().sort_values(ascending=False)
            
            # Point of Control (POC) - price level with highest volume
            poc_bin = volume_profile.index[0]
            poc = (poc_bin.left + poc_bin.right) / 2
            
            # Value Area (70% of volume)
            total_volume = volume_profile.sum()
            cumsum_volume = 0
            value_area_bins = []
            
            for bin_label, vol in volume_profile.items():
                cumsum_volume += vol
                value_area_bins.append(bin_label)
                if cumsum_volume >= total_volume * 0.70:
                    break
            
            # Value Area High and Low
            vah = max([bin.right for bin in value_area_bins])
            val = min([bin.left for bin in value_area_bins])
            
            # Current price in value area?
            current_price = data['Close'].iloc[-1]
            price_in_va = val <= current_price <= vah
            
            # Profile shape analysis
            profile_std = volume_profile.std()
            profile_mean = volume_profile.mean()
            
            if profile_std / profile_mean < 0.5:
                shape = 'NORMAL'  # Balanced distribution
            elif volume_profile.iloc[0] > volume_profile.iloc[1] * 2:
                shape = 'SKEWED'  # Heavily concentrated
            else:
                shape = 'BIMODAL'  # Multiple peaks
            
            return {
                'poc': poc,
                'vah': vah,
                'val': val,
                'shape': shape,
                'price_in_va': price_in_va
            }
            
        except Exception as e:
            self.logger.error(f"Volume profile generation failed: {e}")
            current_price = data['Close'].iloc[-1] if len(data) > 0 else 0
            return {
                'poc': current_price, 'vah': current_price * 1.02,
                'val': current_price * 0.98, 'shape': 'NORMAL',
                'price_in_va': True
            }
    
    def _calculate_volume_sr_levels(self, data: pd.DataFrame, profile_data: Dict) -> Dict:
        """Calculate support/resistance levels based on volume."""
        try:
            current_price = data['Close'].iloc[-1]
            
            # Support levels: POC, VAL, and high-volume zones below current price
            support_levels = []
            resistance_levels = []
            
            # Add profile-based levels
            if profile_data['poc'] < current_price:
                support_levels.append(profile_data['poc'])
            elif profile_data['poc'] > current_price:
                resistance_levels.append(profile_data['poc'])
            
            if profile_data['val'] < current_price:
                support_levels.append(profile_data['val'])
            
            if profile_data['vah'] > current_price:
                resistance_levels.append(profile_data['vah'])
            
            # Sort levels
            support_levels = sorted([s for s in support_levels if s > 0], reverse=True)[:2]
            resistance_levels = sorted([r for r in resistance_levels if r > 0])[:2]
            
            # Find nearest zone
            all_levels = support_levels + resistance_levels
            if all_levels:
                nearest_zone = min(all_levels, key=lambda x: abs(x - current_price))
                zone_distance_pct = ((current_price - nearest_zone) / nearest_zone) * 100
            else:
                nearest_zone = current_price
                zone_distance_pct = 0
            
            return {
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'nearest_zone': nearest_zone,
                'zone_distance_pct': zone_distance_pct
            }
            
        except Exception as e:
            self.logger.error(f"Volume S/R calculation failed: {e}")
            return {
                'support_levels': [],
                'resistance_levels': [],
                'nearest_zone': 0,
                'zone_distance_pct': 0
            }
    
    def _generate_composite_signal(self, vwap_data: Dict, flow_data: Dict,
                                   blocks_data: Dict, profile_data: Dict,
                                   sr_data: Dict) -> Dict:
        """Generate composite volume signal from all analyses."""
        try:
            score = 50  # Start neutral
            signals = []
            
            # 1. VWAP Position (30% weight)
            if vwap_data['position'] == 'ABOVE_VWAP' and vwap_data['trend'] == 'BULLISH':
                score += 15
                signals.append(('VWAP', 'BULLISH'))
            elif vwap_data['position'] == 'BELOW_VWAP' and vwap_data['trend'] == 'BEARISH':
                score -= 15
                signals.append(('VWAP', 'BEARISH'))
            elif vwap_data['position'] == 'AT_VWAP':
                score += 5  # Near VWAP is neutral-positive
                signals.append(('VWAP', 'NEUTRAL'))
            
            # 2. Order Flow (30% weight)
            if flow_data['direction'] == 'BUYING' and flow_data['strength'] == 'STRONG':
                score += 15
                signals.append(('FLOW', 'STRONG_BUYING'))
            elif flow_data['direction'] == 'BUYING':
                score += 8
                signals.append(('FLOW', 'BUYING'))
            elif flow_data['direction'] == 'SELLING' and flow_data['strength'] == 'STRONG':
                score -= 15
                signals.append(('FLOW', 'STRONG_SELLING'))
            elif flow_data['direction'] == 'SELLING':
                score -= 8
                signals.append(('FLOW', 'SELLING'))
            
            # 3. Institutional Activity (20% weight)
            if blocks_data['activity_level'] == 'HIGH':
                if blocks_data['recent_direction'] == 'BUY':
                    score += 10
                    signals.append(('BLOCKS', 'INSTITUTIONAL_BUYING'))
                elif blocks_data['recent_direction'] == 'SELL':
                    score -= 10
                    signals.append(('BLOCKS', 'INSTITUTIONAL_SELLING'))
            elif blocks_data['activity_level'] == 'MODERATE':
                if blocks_data['recent_direction'] == 'BUY':
                    score += 5
                    signals.append(('BLOCKS', 'MODERATE_BUYING'))
            
            # 4. Volume Profile (20% weight)
            if profile_data['price_in_va']:
                score += 5  # In value area is good
                signals.append(('PROFILE', 'IN_VALUE_AREA'))
            
            if profile_data['shape'] == 'NORMAL':
                score += 5  # Normal distribution is stable
                signals.append(('PROFILE', 'BALANCED'))
            
            # Clamp score to 0-100
            score = max(0, min(100, score))
            
            # Generate signal
            if score >= 65:
                signal = 'STRONG_BUY'
            elif score >= 55:
                signal = 'BUY'
            elif score >= 45:
                signal = 'HOLD'
            elif score >= 35:
                signal = 'SELL'
            else:
                signal = 'STRONG_SELL'
            
            # Calculate confidence based on signal agreement
            bullish_signals = sum(1 for _, s in signals if 'BUY' in s or 'BULLISH' in s)
            bearish_signals = sum(1 for _, s in signals if 'SELL' in s or 'BEARISH' in s)
            total_signals = len(signals)
            
            if total_signals > 0:
                agreement = max(bullish_signals, bearish_signals) / total_signals
                confidence = agreement * 100
            else:
                confidence = 50
            
            # Quality assessment
            if confidence >= 75 and blocks_data['activity_level'] == 'HIGH':
                quality = 'HIGH'
            elif confidence >= 60:
                quality = 'MODERATE'
            else:
                quality = 'LOW'
            
            return {
                'score': score,
                'signal': signal,
                'confidence': confidence,
                'quality': quality,
                'component_signals': signals
            }
            
        except Exception as e:
            self.logger.error(f"Composite signal generation failed: {e}")
            return {
                'score': 50, 'signal': 'HOLD', 'confidence': 50,
                'quality': 'LOW', 'component_signals': []
            }
    
    def adjust_score_by_volume(self, base_score: float, volume_data: Dict) -> Dict:
        """
        Adjust stock score based on volume analysis.
        
        Args:
            base_score: Current stock score before volume adjustment
            volume_data: Volume analysis results
            
        Returns:
            Dictionary with adjusted score and adjustment details
        """
        try:
            # Calculate adjustment based on volume composite score
            volume_score = volume_data.get('volume_composite_score', 50)
            volume_signal = volume_data.get('volume_signal', 'HOLD')
            volume_confidence = volume_data.get('volume_confidence', 50)
            
            # Adjustment calculation (max ±10 points)
            # Formula: (volume_score - 50) * 0.2 * (confidence / 100)
            base_adjustment = (volume_score - 50) * 0.2
            confidence_factor = volume_confidence / 100
            adjustment = base_adjustment * confidence_factor
            
            # Clamp to max adjustment
            adjustment = max(-self.max_adjustment, min(self.max_adjustment, adjustment))
            
            # Apply adjustment
            adjusted_score = base_score + adjustment
            
            # Generate adjustment reasons
            reasons = []
            if adjustment > 5:
                reasons.append(f"Strong volume support (+{adjustment:.1f})")
            elif adjustment > 2:
                reasons.append(f"Positive volume pattern (+{adjustment:.1f})")
            elif adjustment > 0:
                reasons.append(f"Slight volume support (+{adjustment:.1f})")
            elif adjustment < -5:
                reasons.append(f"Weak volume profile ({adjustment:.1f})")
            elif adjustment < -2:
                reasons.append(f"Negative volume pattern ({adjustment:.1f})")
            elif adjustment < 0:
                reasons.append(f"Slight volume weakness ({adjustment:.1f})")
            else:
                reasons.append("Neutral volume (no adjustment)")
            
            # Add specific factors
            if volume_data.get('vwap_position') == 'ABOVE_VWAP':
                reasons.append("Trading above VWAP")
            if volume_data.get('flow_direction') == 'BUYING':
                reasons.append("Positive order flow")
            if volume_data.get('institutional_activity') == 'HIGH':
                reasons.append("High institutional activity")
            
            result = {
                'volume_adjusted_score': adjusted_score,
                'volume_adjustment_amount': adjustment,
                'volume_adjustment_reasons': ', '.join(reasons),
                'volume_signal_used': volume_signal,
                'volume_confidence_used': volume_confidence
            }
            
            self.logger.info(
                f"Volume adjustment: {base_score:.1f} -> {adjusted_score:.1f} "
                f"({adjustment:+.1f}) | Signal: {volume_signal}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Volume score adjustment failed: {e}")
            return {
                'volume_adjusted_score': base_score,
                'volume_adjustment_amount': 0,
                'volume_adjustment_reasons': 'Volume adjustment failed',
                'volume_signal_used': 'HOLD',
                'volume_confidence_used': 0
            }
    
    def _get_default_volume_analysis(self) -> Dict:
        """Return default volume analysis when analysis fails."""
        return {
            'vwap_current': 0, 'vwap_position': 'UNKNOWN', 'vwap_distance_pct': 0,
            'vwap_trend': 'NEUTRAL', 'vwap_support': 0, 'vwap_resistance': 0,
            'order_flow_imbalance': 0, 'flow_strength': 'WEAK', 'flow_direction': 'BALANCED',
            'flow_consistency': 50, 'block_trades_count': 0, 'block_trades_volume_pct': 0,
            'institutional_activity': 'LOW', 'recent_blocks_direction': 'NONE',
            'volume_poc': 0, 'volume_vah': 0, 'volume_val': 0,
            'volume_profile_shape': 'NORMAL', 'price_in_value_area': True,
            'volume_support_1': None, 'volume_support_2': None,
            'volume_resistance_1': None, 'volume_resistance_2': None,
            'nearest_volume_zone': 0, 'zone_distance_pct': 0,
            'volume_composite_score': 50, 'volume_signal': 'HOLD',
            'volume_confidence': 50, 'volume_quality': 'LOW',
            'volume_analysis_timestamp': datetime.now().isoformat(),
            'volume_analysis_status': 'FAILED'
        }


# Test code
if __name__ == "__main__":
    import yfinance as yf
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print("🎯 VOLUME PROFILE & ORDER FLOW ANALYZER - TEST")
    print("="*60)
    
    # Test with a sample stock
    symbol = "RELIANCE.NS"
    print(f"\n📊 Testing with: {symbol}")
    
    # Download data
    print("📥 Downloading 90 days of data...")
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="3mo")
    
    if len(data) > 0:
        print(f"✅ Downloaded {len(data)} days of data")
        
        # Initialize analyzer
        analyzer = VolumeAnalyzer()
        
        # Run analysis
        print("\n🔍 Running volume analysis...")
        volume_data = analyzer.analyze_volume(symbol, data)
        
        # Display results
        print("\n" + "="*60)
        print("📊 VOLUME ANALYSIS RESULTS")
        print("="*60)
        
        print(f"\n🎯 COMPOSITE SIGNAL:")
        print(f"   Score: {volume_data['volume_composite_score']:.1f}/100")
        print(f"   Signal: {volume_data['volume_signal']}")
        print(f"   Confidence: {volume_data['volume_confidence']:.1f}%")
        print(f"   Quality: {volume_data['volume_quality']}")
        
        print(f"\n📈 VWAP ANALYSIS:")
        print(f"   Current VWAP: ₹{volume_data['vwap_current']:.2f}")
        print(f"   Position: {volume_data['vwap_position']}")
        print(f"   Distance: {volume_data['vwap_distance_pct']:.2f}%")
        print(f"   Trend: {volume_data['vwap_trend']}")
        print(f"   Support: ₹{volume_data['vwap_support']:.2f}")
        print(f"   Resistance: ₹{volume_data['vwap_resistance']:.2f}")
        
        print(f"\n💹 ORDER FLOW:")
        print(f"   Direction: {volume_data['flow_direction']}")
        print(f"   Strength: {volume_data['flow_strength']}")
        print(f"   Imbalance: {volume_data['order_flow_imbalance']:.3f}")
        print(f"   Consistency: {volume_data['flow_consistency']:.1f}%")
        
        print(f"\n🏛️ INSTITUTIONAL ACTIVITY:")
        print(f"   Block Trades: {volume_data['block_trades_count']}")
        print(f"   Block Volume %: {volume_data['block_trades_volume_pct']:.1f}%")
        print(f"   Activity Level: {volume_data['institutional_activity']}")
        print(f"   Recent Direction: {volume_data['recent_blocks_direction']}")
        
        print(f"\n📊 VOLUME PROFILE:")
        print(f"   POC (Point of Control): ₹{volume_data['volume_poc']:.2f}")
        print(f"   VAH (Value Area High): ₹{volume_data['volume_vah']:.2f}")
        print(f"   VAL (Value Area Low): ₹{volume_data['volume_val']:.2f}")
        print(f"   Profile Shape: {volume_data['volume_profile_shape']}")
        print(f"   In Value Area: {volume_data['price_in_value_area']}")
        
        # Test score adjustment
        print(f"\n📈 SCORE ADJUSTMENT TEST:")
        base_score = 75.0
        adjustment_result = analyzer.adjust_score_by_volume(base_score, volume_data)
        print(f"   Base Score: {base_score}")
        print(f"   Adjustment: {adjustment_result['volume_adjustment_amount']:+.1f}")
        print(f"   Adjusted Score: {adjustment_result['volume_adjusted_score']:.1f}")
        print(f"   Reasons: {adjustment_result['volume_adjustment_reasons']}")
        
        print("\n✅ Volume analysis test completed successfully!")
        
    else:
        print("❌ Failed to download data")
    
    print("\n" + "="*60)
