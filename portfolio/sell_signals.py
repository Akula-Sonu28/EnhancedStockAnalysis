"""
Enhanced Sell Signals and Capital Rotation Engine
===============================================

Provides specific sell recommendations with target prices and capital rotation strategies.

Features:
- Technical analysis based sell signals (RSI, Support/Resistance)
- Profit booking with price targets
- Stop loss recommendations
- Capital rotation suggestions based on market gaps
- Sector rotation strategies

Author: Enhanced Stock Analysis System
Version: 1.0.0
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import warnings

# Suppress pandas RuntimeWarnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning, module='pandas')

class SellSignalsEngine:
    """Enhanced sell signals with specific price targets and rotation strategies"""
    
    def __init__(self, portfolio_analyzer):
        self.analyzer = portfolio_analyzer
        self.logger = logging.getLogger('SellSignals')
        
        # Technical thresholds
        self.RSI_OVERBOUGHT = 70
        self.RSI_OVERSOLD = 30
        self.PROFIT_BOOKING_LEVELS = [25, 50, 75, 100]  # Progressive profit booking
        self.STOP_LOSS_LEVELS = [-5, -10, -15]  # Progressive stop loss
        
        # Advanced Pattern Recognition Thresholds
        self.PATTERN_THRESHOLDS = {
            'breakout_volume_multiplier': 2.0,  # 2x avg volume for breakout confirmation
            'consolidation_range_pct': 5.0,  # 5% price range for consolidation pattern
            'trend_strength_days': 5,  # Days to confirm trend direction
            'momentum_acceleration': 15.0,  # 15% price move for momentum pattern
            'reversal_rsi_divergence': 10,  # RSI divergence for reversal pattern
            'support_resistance_precision': 2.0,  # 2% tolerance for S/R levels
            'golden_cross_confirmation': 3,  # Days to confirm MA crossover
            'head_shoulders_ratio': 0.95  # Symmetry ratio for H&S pattern
        }
        
    def analyze_sell_signals(self) -> Dict:
        """Comprehensive sell signal analysis with price targets including portfolio consolidation"""
        try:
            sell_recommendations = []
            rotation_suggestions = []
            
            # Calculate portfolio metrics once and cache them
            portfolio_metrics = self.analyzer.calculate_portfolio_performance()
            
            # Check if portfolio consolidation is needed (25-30 stocks max)
            consolidation_analysis = None
            if hasattr(self.analyzer, 'consolidation_engine'):
                consolidation_analysis = self.analyzer.consolidation_engine.analyze_consolidation_opportunities()
            
            merged_df = self.analyzer.get_holdings_with_enhanced_data()
            total_stocks = len(merged_df)
            
            # Add consolidation sell signals if needed
            if consolidation_analysis and consolidation_analysis.get('action_needed'):
                consolidation_sells = consolidation_analysis.get('sell_recommendations', [])
                self.logger.info(f"Adding {len(consolidation_sells)} consolidation sell signals")
                sell_recommendations.extend(consolidation_sells)
                
                # Add consolidation rotation strategy
                if consolidation_analysis.get('capital_rotation'):
                    rotation_suggestions.append({
                        'type': 'CONSOLIDATION_ROTATION',
                        'strategy': consolidation_analysis['capital_rotation']['strategy'],
                        'allocation_plan': consolidation_analysis['capital_rotation']['allocation_plan'],
                        'total_amount': consolidation_analysis['capital_rotation']['total_amount']
                    })
            
            for idx, (_, stock) in enumerate(merged_df.iterrows(), 1):
                symbol = stock['Instrument']
                if idx % 5 == 0 or idx == 1:  # Log progress every 5 stocks
                    self.logger.debug(f"Processing sell signals: {idx}/{total_stocks} ({symbol})")
                
                # Skip if already marked for consolidation sell
                if any(rec.get('symbol') == symbol for rec in sell_recommendations):
                    continue
                
                # Get real-time technical data
                technical_data = self._get_technical_data(symbol)
                
                # Analyze patterns and predictions
                patterns = self.detect_price_patterns(symbol, technical_data)
                price_predictions = self.predict_price_target(symbol, technical_data, patterns)
                
                # Analyze sell signals with pattern context
                sell_signal = self._analyze_sell_signals(stock, technical_data, patterns, price_predictions)
                if sell_signal:
                    sell_recommendations.append(sell_signal)
                    
                    # Generate rotation suggestion for this sale
                    rotation = self._suggest_capital_rotation(sell_signal, stock)
                    if rotation:
                        rotation_suggestions.append(rotation)
            
            # Overall portfolio rotation strategy (pass cached metrics)
            portfolio_rotation = self._analyze_portfolio_rotation_needs(portfolio_metrics)
            
            # Merge consolidation rotation into portfolio rotation
            if consolidation_analysis and consolidation_analysis.get('capital_rotation'):
                portfolio_rotation['consolidation_strategy'] = consolidation_analysis['capital_rotation']
                portfolio_rotation['consolidation_impact'] = consolidation_analysis['consolidation_impact']
            
            return {
                'sell_recommendations': sell_recommendations,
                'individual_rotations': rotation_suggestions,
                'portfolio_rotation_strategy': portfolio_rotation,
                'consolidation_analysis': consolidation_analysis,
                'summary': self._generate_sell_summary(sell_recommendations),
                'total_capital_available': sum([rec.get('expected_proceeds', 0) for rec in sell_recommendations])
            }
            
        except Exception as e:
            self.logger.error(f"Error in sell signals analysis: {e}")
            return {}
    
    def detect_price_patterns(self, symbol: str, technical_data: Dict) -> Dict:
        """Advanced pattern recognition for price movements"""
        try:
            patterns_detected = {
                'breakout_pattern': False,
                'consolidation_pattern': False,
                'trend_reversal': False,
                'momentum_pattern': False,
                'support_resistance_test': False,
                'pattern_strength': 0,
                'predicted_direction': 'NEUTRAL',
                'confidence_score': 0.0,
                'pattern_description': []
            }
            
            current_price = technical_data.get('current_price', 0)
            rsi = technical_data.get('rsi', 50)
            support_1 = technical_data.get('support_1', 0)
            resistance_1 = technical_data.get('resistance_1', 0)
            sma_20 = technical_data.get('sma_20', current_price)
            volume_ratio = technical_data.get('volume_ratio', 1.0)
            
            # 1. BREAKOUT PATTERN DETECTION
            if resistance_1 > 0 and current_price > resistance_1 * 1.01:  # 1% above resistance
                if volume_ratio > self.PATTERN_THRESHOLDS['breakout_volume_multiplier']:
                    patterns_detected['breakout_pattern'] = True
                    patterns_detected['predicted_direction'] = 'BULLISH'
                    patterns_detected['confidence_score'] += 0.3
                    patterns_detected['pattern_description'].append(f"Bullish breakout above ₹{resistance_1:.2f} with high volume")
            
            # 2. SUPPORT BREAKDOWN PATTERN
            elif support_1 > 0 and current_price < support_1 * 0.99:  # 1% below support
                if volume_ratio > self.PATTERN_THRESHOLDS['breakout_volume_multiplier']:
                    patterns_detected['breakout_pattern'] = True
                    patterns_detected['predicted_direction'] = 'BEARISH'
                    patterns_detected['confidence_score'] += 0.3
                    patterns_detected['pattern_description'].append(f"Bearish breakdown below ₹{support_1:.2f} with high volume")
            
            # 3. CONSOLIDATION PATTERN DETECTION
            if support_1 > 0 and resistance_1 > 0:
                consolidation_range = (resistance_1 - support_1) / support_1 * 100
                if consolidation_range <= self.PATTERN_THRESHOLDS['consolidation_range_pct']:
                    patterns_detected['consolidation_pattern'] = True
                    patterns_detected['confidence_score'] += 0.2
                    patterns_detected['pattern_description'].append(f"Tight consolidation in {consolidation_range:.1f}% range")
            
            # 4. RSI DIVERGENCE PATTERN (Reversal Signal)
            if rsi > 80:  # Extreme overbought
                patterns_detected['trend_reversal'] = True
                patterns_detected['predicted_direction'] = 'BEARISH'
                patterns_detected['confidence_score'] += 0.25
                patterns_detected['pattern_description'].append(f"Extreme overbought RSI ({rsi:.1f}) - reversal likely")
            elif rsi < 20:  # Extreme oversold
                patterns_detected['trend_reversal'] = True
                patterns_detected['predicted_direction'] = 'BULLISH'
                patterns_detected['confidence_score'] += 0.25
                patterns_detected['pattern_description'].append(f"Extreme oversold RSI ({rsi:.1f}) - bounce expected")
            
            # 5. MOMENTUM PATTERN DETECTION
            if sma_20 > 0:
                price_vs_ma = (current_price - sma_20) / sma_20 * 100
                if abs(price_vs_ma) > self.PATTERN_THRESHOLDS['momentum_acceleration']:
                    patterns_detected['momentum_pattern'] = True
                    direction = 'BULLISH' if price_vs_ma > 0 else 'BEARISH'
                    patterns_detected['predicted_direction'] = direction
                    patterns_detected['confidence_score'] += 0.15
                    patterns_detected['pattern_description'].append(f"{direction.lower()} momentum: {abs(price_vs_ma):.1f}% from SMA20")
            
            # 6. SUPPORT/RESISTANCE TEST PATTERN
            if support_1 > 0 and abs(current_price - support_1) / support_1 * 100 <= 2:
                patterns_detected['support_resistance_test'] = True
                patterns_detected['pattern_description'].append(f"Testing support at ₹{support_1:.2f}")
            elif resistance_1 > 0 and abs(current_price - resistance_1) / resistance_1 * 100 <= 2:
                patterns_detected['support_resistance_test'] = True
                patterns_detected['pattern_description'].append(f"Testing resistance at ₹{resistance_1:.2f}")
            
            # CALCULATE OVERALL PATTERN STRENGTH
            pattern_count = sum([
                patterns_detected['breakout_pattern'],
                patterns_detected['consolidation_pattern'], 
                patterns_detected['trend_reversal'],
                patterns_detected['momentum_pattern'],
                patterns_detected['support_resistance_test']
            ])
            
            patterns_detected['pattern_strength'] = min(pattern_count * 20, 100)  # 0-100 scale
            
            # CONFIDENCE SCORE NORMALIZATION
            patterns_detected['confidence_score'] = min(patterns_detected['confidence_score'], 1.0) * 100
            
            return patterns_detected
            
        except Exception as e:
            self.logger.error(f"Error in pattern detection for {symbol}: {e}")
            return {'pattern_strength': 0, 'predicted_direction': 'NEUTRAL', 'confidence_score': 0}
    
    def predict_price_target(self, symbol: str, technical_data: Dict, patterns: Dict) -> Dict:
        """Predict price targets based on patterns and technical analysis"""
        try:
            current_price = technical_data.get('current_price', 0)
            support_1 = technical_data.get('support_1', 0)
            support_2 = technical_data.get('support_2', 0)
            resistance_1 = technical_data.get('resistance_1', 0)
            resistance_2 = technical_data.get('resistance_2', 0)
            
            predictions = {
                'upside_targets': [],
                'downside_targets': [],
                'probability_up': 50.0,
                'probability_down': 50.0,
                'time_horizon': '1-4 weeks',
                'key_levels': []
            }
            
            if current_price <= 0:
                return predictions
            
            # BULLISH SCENARIO TARGETS
            if patterns.get('predicted_direction') == 'BULLISH':
                predictions['probability_up'] = 60 + (patterns.get('confidence_score', 0) * 0.3)
                predictions['probability_down'] = 100 - predictions['probability_up']
                
                # Target 1: Next resistance level
                if resistance_1 > current_price:
                    upside_1 = (resistance_1 - current_price) / current_price * 100
                    predictions['upside_targets'].append({
                        'price': resistance_1,
                        'upside_pct': upside_1,
                        'probability': 70,
                        'rationale': 'Next resistance level'
                    })
                
                # Target 2: Extended target (R1 + 10%)
                if resistance_1 > 0:
                    extended_target = resistance_1 * 1.10
                    upside_2 = (extended_target - current_price) / current_price * 100
                    predictions['upside_targets'].append({
                        'price': extended_target,
                        'upside_pct': upside_2,
                        'probability': 40,
                        'rationale': 'Breakout extension target'
                    })
            
            # BEARISH SCENARIO TARGETS
            elif patterns.get('predicted_direction') == 'BEARISH':
                predictions['probability_down'] = 60 + (patterns.get('confidence_score', 0) * 0.3)
                predictions['probability_up'] = 100 - predictions['probability_down']
                
                # Target 1: Next support level
                if support_1 > 0 and support_1 < current_price:
                    downside_1 = (current_price - support_1) / current_price * 100
                    predictions['downside_targets'].append({
                        'price': support_1,
                        'downside_pct': downside_1,
                        'probability': 70,
                        'rationale': 'Next support level'
                    })
                
                # Target 2: Extended target (S1 - 10%)
                if support_1 > 0:
                    extended_target = support_1 * 0.90
                    downside_2 = (current_price - extended_target) / current_price * 100
                    predictions['downside_targets'].append({
                        'price': extended_target,
                        'downside_pct': downside_2,
                        'probability': 35,
                        'rationale': 'Breakdown extension target'
                    })
            
            # KEY LEVELS TO WATCH
            if support_1 > 0:
                predictions['key_levels'].append({'level': support_1, 'type': 'Support'})
            if resistance_1 > 0:
                predictions['key_levels'].append({'level': resistance_1, 'type': 'Resistance'})
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error in price target prediction for {symbol}: {e}")
            return {'upside_targets': [], 'downside_targets': [], 'probability_up': 50, 'probability_down': 50}
    
    def _get_technical_data(self, symbol: str) -> Dict:
        """Get technical analysis data from Enhanced Stock Report (faster than real-time fetch)"""
        try:
            # First, try to get data from Enhanced Stock Report
            enhanced_data = self._get_technical_from_report(symbol)
            if enhanced_data:
                return enhanced_data
            
            # Fallback to real-time data only if not found in report
            return self._get_realtime_technical_data(symbol)
            
        except Exception as e:
            self.logger.debug(f"Error getting technical data for {symbol}: {str(e)}")
            return {}
    
    def _get_technical_from_report(self, symbol: str) -> Dict:
        """Extract technical data from Enhanced Stock Report"""
        try:
            if not hasattr(self.analyzer, 'enhanced_report_df') or self.analyzer.enhanced_report_df is None:
                return {}
            
            # Check if Technical Analysis sheet exists
            if 'Technical Analysis' not in self.analyzer.enhanced_report_df:
                return {}
            
            tech_df = self.analyzer.enhanced_report_df['Technical Analysis']
            
            # Find the stock in technical analysis data
            stock_data = tech_df[tech_df['symbol'] == symbol]
            if stock_data.empty:
                return {}
            
            # Extract technical indicators from the report
            stock_row = stock_data.iloc[0]
            
            return {
                'current_price': stock_row.get('current_price', 0),
                'rsi': stock_row.get('rsi', 50),
                'support_1': stock_row.get('support_1', 0),
                'support_2': stock_row.get('support_2', 0), 
                'resistance_1': stock_row.get('resistance_1', 0),
                'resistance_2': stock_row.get('resistance_2', 0),
                'sma_20': stock_row.get('sma_20', 0),
                'sma_50': stock_row.get('sma_50', 0),
                'volume_avg': stock_row.get('volume_avg', 0),
                'volume_current': stock_row.get('volume_current', 0),
                'volatility': stock_row.get('volatility', 0),
                'trend_signal': stock_row.get('trend_signal', 'NEUTRAL')
            }
            
        except Exception as e:
            self.logger.debug(f"Could not get technical data from report for {symbol}: {str(e)}")
            return {}
    
    def _get_realtime_technical_data(self, symbol: str) -> Dict:
        """Fallback method to get real-time technical data (slower)"""
        try:
            # Add .NS for NSE stocks
            ticker_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            
            # Get recent data (last 50 days for technical analysis) with timeout handling
            stock = yf.Ticker(ticker_symbol)
            
            # Add error handling for delisted or problematic stocks
            try:
                hist = stock.history(period="50d", timeout=3)  # Very short timeout for fallback
            except (KeyboardInterrupt, Exception) as fetch_error:
                self.logger.debug(f"Skipping real-time fetch for {symbol} - using defaults")
                return self._get_default_technical_data()
            
            if hist.empty:
                return self._get_default_technical_data()
            
            # Check if required columns exist
            required_columns = ['Close', 'High', 'Low', 'Volume']
            missing_columns = [col for col in required_columns if col not in hist.columns]
            if missing_columns:
                return self._get_default_technical_data()
            
            # Calculate technical indicators with additional error handling
            current_price = hist['Close'].iloc[-1]
            
            # RSI calculation
            rsi = self._calculate_rsi(hist['Close'])
            
            # Support and Resistance levels
            support_resistance = self._calculate_support_resistance(hist)
            
            # Moving averages with proper bounds checking
            sma_20_window = min(20, len(hist))
            sma_50_window = min(50, len(hist))
            
            sma_20 = hist['Close'].rolling(window=sma_20_window).mean().iloc[-1] if len(hist) >= sma_20_window else current_price
            sma_50 = hist['Close'].rolling(window=sma_50_window).mean().iloc[-1] if len(hist) >= sma_50_window else current_price
            
            # Volume analysis with safety checks
            avg_volume = hist['Volume'].mean() if 'Volume' in hist.columns and not hist['Volume'].empty else 0
            current_volume = hist['Volume'].iloc[-1] if 'Volume' in hist.columns and not hist['Volume'].empty else 0
            
            return {
                'current_price': current_price,
                'rsi': rsi,
                'support_1': support_resistance['S1'],
                'support_2': support_resistance['S2'],
                'resistance_1': support_resistance['R1'],
                'resistance_2': support_resistance['R2'],
                'sma_20': sma_20,
                'sma_50': sma_50,
                'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 1,
                'price_vs_sma20': ((current_price - sma_20) / sma_20 * 100) if pd.notna(sma_20) else 0
            }
            
        except Exception as e:
            self.logger.warning(f"Could not get technical data for {symbol}: {e}")
            return self._get_default_technical_data()
    
    def _get_default_technical_data(self) -> Dict:
        """Return default technical data when real data is unavailable"""
        return {
            'current_price': 0,
            'rsi': 50,  # Neutral RSI
            'support_1': 0,
            'support_2': 0,
            'resistance_1': 0,
            'resistance_2': 0,
            'sma_20': 0,
            'sma_50': 0,
            'volume_ratio': 1,
            'price_vs_sma20': 0,
            'trend_signal': 'NEUTRAL'
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        except:
            return 50  # Neutral RSI if calculation fails
    
    def _calculate_support_resistance(self, hist: pd.DataFrame) -> Dict:
        """Calculate support and resistance levels using pivot points"""
        try:
            recent_data = hist.tail(20)  # Last 20 days
            
            high = recent_data['High'].max()
            low = recent_data['Low'].min()
            close = recent_data['Close'].iloc[-1]
            
            # Pivot point calculation
            pivot = (high + low + close) / 3
            
            # Support and Resistance levels
            r1 = 2 * pivot - low
            s1 = 2 * pivot - high
            r2 = pivot + (high - low)
            s2 = pivot - (high - low)
            
            return {
                'S1': round(s1, 2),
                'S2': round(s2, 2),
                'R1': round(r1, 2),
                'R2': round(r2, 2),
                'Pivot': round(pivot, 2)
            }
            
        except Exception as e:
            # Fallback: use recent high/low as resistance/support
            try:
                recent_high = hist['High'].tail(10).max()
                recent_low = hist['Low'].tail(10).min()
                current_price = hist['Close'].iloc[-1]
                
                return {
                    'S1': round(recent_low * 0.98, 2),
                    'S2': round(recent_low * 0.95, 2),
                    'R1': round(recent_high * 1.02, 2),
                    'R2': round(recent_high * 1.05, 2),
                    'Pivot': round(current_price, 2)
                }
            except:
                return {'S1': 0, 'S2': 0, 'R1': 0, 'R2': 0, 'Pivot': 0}
    
    def _analyze_sell_signals(self, stock: pd.Series, technical_data: Dict, patterns: Dict = None, predictions: Dict = None) -> Optional[Dict]:
        """Analyze individual stock for sell signals with specific price targets"""
        try:
            instrument = stock['Instrument']
            return_pct = stock.get('Return_Pct', 0)
            current_value = stock.get('Cur. val', 0)
            avg_price = stock.get('Avg. cost', 0)
            quantity = stock.get('Qty.', 0)
            
            # Get technical indicators
            rsi = technical_data.get('rsi', 50)
            current_price = technical_data.get('current_price', avg_price)
            r1 = technical_data.get('resistance_1', 0)
            r2 = technical_data.get('resistance_2', 0)
            s1 = technical_data.get('support_1', 0)
            s2 = technical_data.get('support_2', 0)
            
            sell_recommendation = None
            
            # 1. STOP LOSS SIGNALS
            if return_pct <= -10:
                sell_recommendation = {
                    'instrument': instrument,
                    'action': 'IMMEDIATE_SELL',
                    'reason': 'STOP_LOSS',
                    'current_price': current_price,
                    'target_price': max(s1, current_price * 0.98) if s1 > 0 else current_price * 0.98,
                    'stop_loss_price': s2 if s2 > 0 else current_price * 0.95,
                    'expected_proceeds': current_value * 0.95,  # Conservative estimate
                    'urgency': 'HIGH',
                    'rationale': f'Heavy loss of {return_pct:.1f}%, cut losses immediately',
                    'timeline': '1-2 days',
                    'sell_type': 'FULL',
                    'profit_loss': return_pct,
                    'risk_level': 'HIGH'
                }
            
            # 2. TECHNICAL OVERBOUGHT + PROFIT BOOKING (Enhanced with Patterns)
            elif rsi >= self.RSI_OVERBOUGHT and return_pct >= 25:
                target_price = r1 if r1 > current_price else current_price * 1.02
                
                # Enhanced rationale with pattern analysis
                rationale_parts = [f'RSI overbought ({rsi:.1f}) with good profit ({return_pct:.1f}%)']
                
                if patterns:
                    if patterns.get('trend_reversal'):
                        rationale_parts.append('Trend reversal pattern detected')
                    if patterns.get('pattern_strength', 0) >= 60:
                        rationale_parts.append(f"Strong pattern signals ({patterns['pattern_strength']}% strength)")
                    
                    # Add specific pattern descriptions
                    pattern_desc = patterns.get('pattern_description', [])
                    if pattern_desc:
                        rationale_parts.extend(pattern_desc[:2])  # Add up to 2 pattern descriptions
                
                # Enhanced target price with predictions
                if predictions and predictions.get('downside_targets'):
                    # If bearish prediction, use more conservative target
                    prob_down = predictions.get('probability_down', 50)
                    if prob_down > 60:
                        target_price = current_price * 0.99  # More aggressive exit
                        rationale_parts.append(f'Bearish outlook ({prob_down:.0f}% prob)')
                
                sell_recommendation = {
                    'instrument': instrument,
                    'action': 'PROFIT_BOOKING',
                    'reason': 'OVERBOUGHT_PROFIT',
                    'current_price': current_price,
                    'target_price': target_price,
                    'resistance_level': r2,
                    'expected_proceeds': quantity * target_price,
                    'urgency': 'MEDIUM',
                    'rationale': '; '.join(rationale_parts),
                    'timeline': '1-2 weeks',
                    'sell_type': 'PARTIAL' if return_pct < 50 else 'FULL',
                    'sell_quantity': int(quantity * 0.5) if return_pct < 50 else quantity,
                    'profit_loss': return_pct,
                    'risk_level': 'LOW',
                    'pattern_strength': patterns.get('pattern_strength', 0) if patterns else 0,
                    'predicted_direction': patterns.get('predicted_direction', 'NEUTRAL') if patterns else 'NEUTRAL',
                    'confidence_score': patterns.get('confidence_score', 0) if patterns else 0
                }
            
            # 3. RESISTANCE LEVEL REACHED
            elif current_price >= r1 and return_pct >= 15:
                sell_recommendation = {
                    'instrument': instrument,
                    'action': 'RESISTANCE_SELL',
                    'reason': 'RESISTANCE_LEVEL',
                    'current_price': current_price,
                    'target_price': r1,
                    'next_resistance': r2,
                    'expected_proceeds': quantity * r1,
                    'urgency': 'MEDIUM',
                    'rationale': f'Price near resistance R1 (₹{r1}) with profit of {return_pct:.1f}%',
                    'timeline': '3-7 days',
                    'sell_type': 'PARTIAL',
                    'sell_quantity': int(quantity * 0.6),  # Sell 60%
                    'profit_loss': return_pct,
                    'risk_level': 'MEDIUM'
                }
            
            # 4. EXCESSIVE PROFIT BOOKING
            elif return_pct >= 75:
                sell_recommendation = {
                    'instrument': instrument,
                    'action': 'MAJOR_PROFIT_BOOKING',
                    'reason': 'EXCESSIVE_PROFIT',
                    'current_price': current_price,
                    'target_price': current_price * 0.98,  # Slight discount for quick sale
                    'expected_proceeds': current_value * 0.8,  # 80% of current value
                    'urgency': 'HIGH',
                    'rationale': f'Exceptional profit of {return_pct:.1f}%, book major profits',
                    'timeline': '1 week',
                    'sell_type': 'MAJOR_PARTIAL',  # Sell 70-80%
                    'sell_quantity': int(quantity * 0.75),
                    'profit_loss': return_pct,
                    'risk_level': 'LOW'
                }
            
            return sell_recommendation
            
        except Exception as e:
            self.logger.error(f"Error analyzing sell signals for {instrument}: {e}")
            return None
    
    def _suggest_capital_rotation(self, sell_signal: Dict, original_stock: pd.Series) -> Dict:
        """Suggest where to rotate capital from sale proceeds"""
        try:
            instrument = sell_signal['instrument']
            proceeds = sell_signal.get('expected_proceeds', 0)
            
            # Get current sector allocation
            sector_allocation = self.analyzer.analyze_sector_allocation()
            
            # Get buy recommendations from insights (workaround for method name)
            try:
                # Try to get buy recommendations from insights instead
                from portfolio.insights import PortfolioInsights
                insights = PortfolioInsights(self.analyzer)
                buy_analysis = insights.analyze_buy_recommendations()
                buy_recommendations = buy_analysis.get('top_buy_recommendations', [])
            except:
                buy_recommendations = []
            
            rotation_suggestion = {
                'source_stock': instrument,
                'sale_proceeds': proceeds,
                'rotation_strategy': [],
                'rationale': []
            }
            
            # Strategy 1: Diversification (if selling from over-allocated sector)
            current_sector = original_stock.get('Sector', 'Unknown')
            if current_sector in sector_allocation and sector_allocation[current_sector]['allocation_pct'] > 25:
                # Find underallocated sectors
                target_sectors = [sector for sector, data in sector_allocation.items() 
                                if data['allocation_pct'] < 15 and sector != current_sector]
                
                if target_sectors:
                    rotation_suggestion['rotation_strategy'].append({
                        'type': 'SECTOR_DIVERSIFICATION',
                        'target_sectors': target_sectors[:2],  # Top 2 underallocated
                        'allocation_pct': 70,  # 70% of proceeds
                        'amount': proceeds * 0.7
                    })
                    rotation_suggestion['rationale'].append(f'Diversify from over-allocated {current_sector} sector')
            
            # Strategy 2: Upgrade (move to better performing stocks)
            if buy_recommendations:
                top_buys = sorted(buy_recommendations, key=lambda x: x.get('score', 0), reverse=True)[:2]
                rotation_suggestion['rotation_strategy'].append({
                    'type': 'UPGRADE_POSITIONS',
                    'target_stocks': [stock['symbol'] for stock in top_buys],
                    'allocation_pct': 30,
                    'amount': proceeds * 0.3,
                    'reasons': [stock.get('reason', 'High score') for stock in top_buys]
                })
                rotation_suggestion['rationale'].append('Upgrade to higher-scoring opportunities')
            
            # Strategy 3: Cash position (if market is risky)
            if sell_signal['reason'] in ['STOP_LOSS', 'MARKET_RISK']:
                rotation_suggestion['rotation_strategy'].append({
                    'type': 'CASH_POSITION',
                    'allocation_pct': 50,
                    'amount': proceeds * 0.5,
                    'duration': '2-4 weeks',
                    'condition': 'Wait for market stabilization'
                })
                rotation_suggestion['rationale'].append('Maintain cash during market uncertainty')
            
            return rotation_suggestion
            
        except Exception as e:
            self.logger.error(f"Error in capital rotation suggestion: {e}")
            return {}
    
    def _analyze_portfolio_rotation_needs(self, portfolio_metrics: Dict = None) -> Dict:
        """Analyze overall portfolio rotation strategy"""
        try:
            sector_analysis = self.analyzer.analyze_sector_allocation()
            if portfolio_metrics is None:
                portfolio_metrics = self.analyzer.calculate_portfolio_performance()
            
            rotation_strategy = {
                'sector_rebalancing': [],
                'risk_rebalancing': [],
                'performance_optimization': [],
                'timeline': '4-8 weeks'
            }
            
            # Get sector allocation data (it's a list of sector records)
            sector_allocation_list = sector_analysis.get('sector_allocation', [])
            portfolio_value = portfolio_metrics.get('current_value', 1)
            
            # Sector rebalancing needs
            for sector_data in sector_allocation_list:
                sector_name = sector_data.get('Sector', 'Unknown')
                allocation_pct = sector_data.get('Weight_Pct', 0)
                
                if allocation_pct > 30:  # Over-allocated
                    rotation_strategy['sector_rebalancing'].append({
                        'action': 'REDUCE',
                        'sector': sector_name,
                        'current_pct': allocation_pct,
                        'target_pct': 20,
                        'reduce_amount': (allocation_pct - 20) * portfolio_value / 100
                    })
                elif allocation_pct < 5 and sector_name != 'Unknown':  # Under-allocated
                    rotation_strategy['sector_rebalancing'].append({
                        'action': 'INCREASE',
                        'sector': sector_name,
                        'current_pct': allocation_pct,
                        'target_pct': 15,
                        'increase_amount': (15 - allocation_pct) * portfolio_value / 100
                    })
            
            return rotation_strategy
            
        except Exception as e:
            self.logger.error(f"Error in portfolio rotation analysis: {e}")
            return {}
    
    def _generate_sell_summary(self, sell_recommendations: List[Dict]) -> Dict:
        """Generate summary of sell recommendations"""
        try:
            if not sell_recommendations:
                return {'total_stocks': 0, 'total_proceeds': 0, 'urgency_breakdown': {}}
            
            total_proceeds = sum([rec.get('expected_proceeds', 0) for rec in sell_recommendations])
            
            urgency_breakdown = {}
            for rec in sell_recommendations:
                urgency = rec.get('urgency', 'LOW')
                urgency_breakdown[urgency] = urgency_breakdown.get(urgency, 0) + 1
            
            return {
                'total_stocks': len(sell_recommendations),
                'total_proceeds': total_proceeds,
                'urgency_breakdown': urgency_breakdown,
                'immediate_actions': len([r for r in sell_recommendations if r.get('urgency') == 'HIGH']),
                'profit_booking_count': len([r for r in sell_recommendations if 'PROFIT' in r.get('reason', '')]),
                'stop_loss_count': len([r for r in sell_recommendations if 'LOSS' in r.get('reason', '')])
            }
            
        except Exception as e:
            self.logger.error(f"Error generating sell summary: {e}")
            return {}