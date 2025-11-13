#!/usr/bin/env python3
"""
ADAPTIVE MARKET REGIME STRATEGY
===============================

Based on all-market-conditions backtest results, this creates
an adaptive strategy that adjusts to different market regimes
for optimal performance across all conditions.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json

class AdaptiveMarketRegimeStrategy:
    def __init__(self):
        # Results from all-market-conditions backtest
        self.market_performance = {
            'BULL_MODERATE': {
                'avg_return': 3.47,
                'success_rate': 72.2,
                'correlation': -0.115,
                'volatility': 5.92,
                'best_quintile': 'Q3',  # Q3 performed best with +6.26%
                'strategy': 'MOMENTUM_FOLLOW'
            },
            'CALM': {
                'avg_return': 2.01,
                'success_rate': 61.1,
                'correlation': 0.061,
                'volatility': 6.62,
                'best_quintile': 'Q3',  # Q3 performed best with +2.83%
                'strategy': 'BALANCED_APPROACH'
            },
            'SIDEWAYS': {
                'avg_return': 1.01,
                'success_rate': 55.0,
                'correlation': -0.185,
                'volatility': 7.13,
                'best_quintile': 'Q1',  # Q1 performed best with +4.13% (contrarian!)
                'strategy': 'CONTRARIAN_VALUE'
            },
            'BEAR_MODERATE': {
                'avg_return': 0.09,
                'success_rate': 54.8,
                'correlation': 0.000,
                'volatility': 6.18,
                'best_quintile': 'Q2',  # Q2 performed best with +1.18%
                'strategy': 'DEFENSIVE_QUALITY'
            }
        }
        
        # Adaptive weights based on market conditions
        self.adaptive_weights = {
            'BULL_MODERATE': {
                'momentum_technical': 0.40,    # Increased - momentum works in bull markets
                'fundamental_quality': 0.30,   # Reduced - momentum more important
                'volume_strength': 0.20,       # Increased - volume confirms moves
                'sector_momentum': 0.10,       # Standard
                'risk_adjustment': 0.00        # Removed - take more risk in bull markets
            },
            'CALM': {
                'momentum_technical': 0.25,    # Balanced approach
                'fundamental_quality': 0.45,   # Increased - fundamentals matter more
                'volume_strength': 0.15,       # Standard
                'sector_momentum': 0.10,       # Standard
                'risk_adjustment': 0.05        # Small weight - stable conditions
            },
            'SIDEWAYS': {
                'momentum_technical': 0.15,    # Reduced - momentum doesn't work
                'fundamental_quality': 0.50,   # Increased - focus on value
                'volume_strength': 0.10,       # Reduced - less institutional flow
                'sector_momentum': 0.15,       # Increased - sector rotation important
                'risk_adjustment': 0.10        # Increased - manage range-bound risk
            },
            'BEAR_MODERATE': {
                'momentum_technical': 0.10,    # Minimal - avoid momentum
                'fundamental_quality': 0.60,   # Maximum - quality companies survive
                'volume_strength': 0.05,       # Minimal - volume can be misleading
                'sector_momentum': 0.05,       # Minimal - all sectors decline
                'risk_adjustment': 0.20        # Maximum - preserve capital
            }
        }
        
        # Position sizing based on market conditions
        self.position_sizing = {
            'BULL_MODERATE': {
                'max_position': 0.15,      # 15% max per position (aggressive)
                'portfolio_exposure': 0.95,  # 95% invested
                'top_quintile_weight': 0.70, # 70% in top quintile
                'cash_reserve': 0.05        # 5% cash
            },
            'CALM': {
                'max_position': 0.12,      # 12% max per position (moderate)
                'portfolio_exposure': 0.90,  # 90% invested
                'top_quintile_weight': 0.60, # 60% in top quintile
                'cash_reserve': 0.10        # 10% cash
            },
            'SIDEWAYS': {
                'max_position': 0.10,      # 10% max per position (conservative)
                'portfolio_exposure': 0.80,  # 80% invested
                'top_quintile_weight': 0.40, # 40% in top quintile (contrarian)
                'cash_reserve': 0.20        # 20% cash
            },
            'BEAR_MODERATE': {
                'max_position': 0.08,      # 8% max per position (defensive)
                'portfolio_exposure': 0.60,  # 60% invested
                'top_quintile_weight': 0.30, # 30% in top quintile (quality focus)
                'cash_reserve': 0.40        # 40% cash (capital preservation)
            }
        }
    
    def detect_current_market_regime(self):
        """Detect current market regime using Nifty 50 data"""
        try:
            nifty = yf.Ticker("^NSEI")
            hist = nifty.history(period="2mo")  # Last 2 months
            
            if len(hist) < 30:
                return 'CALM'  # Default to calm if insufficient data
            
            # Calculate metrics
            current_price = hist['Close'].iloc[-1]
            price_30d_ago = hist['Close'].iloc[-30] if len(hist) > 30 else hist['Close'].iloc[0]
            
            return_30d = (current_price - price_30d_ago) / price_30d_ago
            
            # Calculate volatility
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # Annualized
            
            # Calculate moving averages
            sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
            sma_50 = hist['Close'].rolling(50).mean().iloc[-1] if len(hist) > 50 else sma_20
            
            # Classify market regime
            if return_30d > 0.05 and current_price > sma_20 > sma_50:
                regime = 'BULL_MODERATE'
            elif return_30d < -0.05 and current_price < sma_20:
                regime = 'BEAR_MODERATE'
            elif volatility > 0.25:
                regime = 'SIDEWAYS'  # High volatility = choppy/sideways
            else:
                regime = 'CALM'
            
            return {
                'regime': regime,
                'return_30d': return_30d * 100,
                'volatility': volatility * 100,
                'price_vs_sma20': (current_price / sma_20 - 1) * 100,
                'confidence': self._calculate_regime_confidence(return_30d, volatility, current_price, sma_20)
            }
            
        except Exception as e:
            print(f"❌ Error detecting market regime: {e}")
            return {'regime': 'CALM', 'confidence': 'LOW'}
    
    def _calculate_regime_confidence(self, return_30d, volatility, price, sma_20):
        """Calculate confidence in market regime detection"""
        
        # Strong signals increase confidence
        strong_trend = abs(return_30d) > 0.10
        clear_direction = abs(price / sma_20 - 1) > 0.05
        stable_volatility = 0.15 < volatility < 0.30
        
        confidence_score = 0
        if strong_trend:
            confidence_score += 1
        if clear_direction:
            confidence_score += 1
        if stable_volatility:
            confidence_score += 1
        
        if confidence_score >= 2:
            return 'HIGH'
        elif confidence_score == 1:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_adaptive_scoring_weights(self, current_regime):
        """Get scoring weights optimized for current market regime"""
        return self.adaptive_weights.get(current_regime, self.adaptive_weights['CALM'])
    
    def get_position_sizing_strategy(self, current_regime):
        """Get position sizing strategy for current market regime"""
        return self.position_sizing.get(current_regime, self.position_sizing['CALM'])
    
    def generate_regime_specific_recommendations(self, stocks_scores, current_regime):
        """Generate recommendations tailored to current market regime"""
        
        regime_data = self.market_performance[current_regime]
        position_strategy = self.position_sizing[current_regime]
        
        # Sort stocks by score
        sorted_stocks = sorted(stocks_scores.items(), key=lambda x: x[1], reverse=True)
        
        recommendations = {
            'market_regime': current_regime,
            'regime_performance': regime_data,
            'strategy': regime_data['strategy'],
            'positions': [],
            'portfolio_allocation': {},
            'risk_management': {}
        }
        
        # Determine quintiles
        scores = [score for _, score in sorted_stocks]
        quintile_thresholds = np.percentile(scores, [20, 40, 60, 80])
        
        total_weight = 0
        max_position = position_strategy['max_position']
        
        for symbol, score in sorted_stocks:
            # Determine quintile
            if score >= quintile_thresholds[3]:
                quintile = 'Q5'
            elif score >= quintile_thresholds[2]:
                quintile = 'Q4'
            elif score >= quintile_thresholds[1]:
                quintile = 'Q3'
            elif score >= quintile_thresholds[0]:
                quintile = 'Q2'
            else:
                quintile = 'Q1'
            
            # Regime-specific position sizing
            if current_regime == 'BULL_MODERATE':
                # In bull markets, focus on momentum (Q3 performed best)
                if quintile in ['Q3', 'Q4', 'Q5']:
                    position_weight = max_position * (1.0 if quintile == 'Q3' else 0.8)
                else:
                    position_weight = max_position * 0.3
                    
            elif current_regime == 'SIDEWAYS':
                # In sideways markets, contrarian approach (Q1 performed best!)
                if quintile in ['Q1', 'Q2']:
                    position_weight = max_position * 1.0
                else:
                    position_weight = max_position * 0.5
                    
            elif current_regime == 'BEAR_MODERATE':
                # In bear markets, focus on quality (Q2 performed best)
                if quintile in ['Q2', 'Q3']:
                    position_weight = max_position * 1.0
                else:
                    position_weight = max_position * 0.4
                    
            else:  # CALM
                # Balanced approach (Q3 performed best)
                if quintile in ['Q3', 'Q4']:
                    position_weight = max_position * 1.0
                elif quintile == 'Q5':
                    position_weight = max_position * 0.8
                else:
                    position_weight = max_position * 0.5
            
            # Don't exceed portfolio exposure limits
            if total_weight + position_weight <= position_strategy['portfolio_exposure']:
                action = 'BUY' if position_weight >= max_position * 0.5 else 'SMALL_POSITION'
                confidence = 'HIGH' if quintile in [regime_data['best_quintile']] else 'MEDIUM'
                
                recommendations['positions'].append({
                    'symbol': symbol,
                    'score': score,
                    'quintile': quintile,
                    'weight': position_weight,
                    'action': action,
                    'confidence': confidence,
                    'regime_rationale': f"{regime_data['strategy']} - {quintile} historically {self._get_quintile_performance(current_regime, quintile)}"
                })
                
                total_weight += position_weight
            else:
                break
        
        # Portfolio allocation summary
        recommendations['portfolio_allocation'] = {
            'total_invested': total_weight,
            'cash_reserve': 1.0 - total_weight,
            'max_position_size': max_position,
            'number_of_positions': len(recommendations['positions']),
            'target_exposure': position_strategy['portfolio_exposure']
        }
        
        # Risk management
        recommendations['risk_management'] = {
            'stop_loss': self._get_stop_loss_for_regime(current_regime),
            'rebalance_frequency': self._get_rebalance_frequency(current_regime),
            'monitoring_level': self._get_monitoring_level(current_regime),
            'regime_change_action': self._get_regime_change_action(current_regime)
        }
        
        return recommendations
    
    def _get_quintile_performance(self, regime, quintile):
        """Get historical performance description for quintile in regime"""
        performance_map = {
            'BULL_MODERATE': {
                'Q1': 'avg +2.32%', 'Q2': 'avg +5.43%', 'Q3': 'BEST +6.26%', 
                'Q4': 'avg +2.29%', 'Q5': 'avg +1.26%'
            },
            'CALM': {
                'Q1': 'avg +2.71%', 'Q2': 'avg +0.14%', 'Q3': 'BEST +2.83%',
                'Q4': 'avg +2.39%', 'Q5': 'avg +1.93%'
            },
            'SIDEWAYS': {
                'Q1': 'BEST +4.13%', 'Q2': 'avg +0.34%', 'Q3': 'avg +0.63%',
                'Q4': 'avg -0.98%', 'Q5': 'avg +0.96%'
            },
            'BEAR_MODERATE': {
                'Q1': 'avg -0.83%', 'Q2': 'BEST +1.18%', 'Q3': 'avg -0.86%',
                'Q4': 'avg +0.39%', 'Q5': 'avg +0.51%'
            }
        }
        return performance_map.get(regime, {}).get(quintile, 'avg +0.00%')
    
    def _get_stop_loss_for_regime(self, regime):
        """Get appropriate stop loss for market regime"""
        stop_losses = {
            'BULL_MODERATE': -12,   # Wider stops in bull markets
            'CALM': -10,            # Standard stops
            'SIDEWAYS': -8,         # Tighter stops in choppy markets
            'BEAR_MODERATE': -6     # Very tight stops in bear markets
        }
        return f"{stop_losses.get(regime, -10)}%"
    
    def _get_rebalance_frequency(self, regime):
        """Get rebalance frequency for regime"""
        frequencies = {
            'BULL_MODERATE': 'Monthly',      # Less frequent in trending markets
            'CALM': 'Monthly',               # Standard
            'SIDEWAYS': 'Bi-weekly',         # More frequent in choppy markets
            'BEAR_MODERATE': 'Weekly'        # Very frequent in bear markets
        }
        return frequencies.get(regime, 'Monthly')
    
    def _get_monitoring_level(self, regime):
        """Get monitoring intensity for regime"""
        levels = {
            'BULL_MODERATE': 'STANDARD',     # Trends tend to persist
            'CALM': 'STANDARD',              # Stable conditions
            'SIDEWAYS': 'HIGH',              # Choppy markets need attention
            'BEAR_MODERATE': 'VERY_HIGH'     # Bear markets are dangerous
        }
        return levels.get(regime, 'STANDARD')
    
    def _get_regime_change_action(self, current_regime):
        """Get action to take when regime changes"""
        actions = {
            'BULL_MODERATE': 'If regime changes to BEAR, reduce exposure immediately',
            'CALM': 'Monitor for trend development, adjust gradually',
            'SIDEWAYS': 'If trend emerges, shift to momentum or defensive strategy',
            'BEAR_MODERATE': 'If regime improves, gradually increase exposure'
        }
        return actions.get(current_regime, 'Reassess strategy when regime changes')

def create_adaptive_strategy_report():
    """Generate comprehensive adaptive strategy report"""
    
    strategy = AdaptiveMarketRegimeStrategy()
    
    print("=" * 80)
    print("📊 ADAPTIVE MARKET REGIME STRATEGY REPORT")
    print("=" * 80)
    
    # Current market analysis
    current_regime_data = strategy.detect_current_market_regime()
    current_regime = current_regime_data['regime']
    
    print(f"\n🎯 CURRENT MARKET REGIME: {current_regime}")
    print(f"   Confidence: {current_regime_data.get('confidence', 'MEDIUM')}")
    print(f"   30-day Return: {current_regime_data.get('return_30d', 0):+.2f}%")
    print(f"   Volatility: {current_regime_data.get('volatility', 20):.1f}%")
    
    # Regime performance summary
    print(f"\n📈 HISTORICAL PERFORMANCE BY REGIME:")
    print("-" * 60)
    print(f"{'Regime':<15} {'Avg Return':<12} {'Success Rate':<12} {'Best Quintile':<12}")
    print("-" * 60)
    
    for regime, data in strategy.market_performance.items():
        print(f"{regime:<15} {data['avg_return']:+8.2f}%    {data['success_rate']:8.1f}%     {data['best_quintile']:<12}")
    
    # Current regime strategy
    regime_data = strategy.market_performance[current_regime]
    print(f"\n🚀 CURRENT REGIME STRATEGY: {regime_data['strategy']}")
    print(f"   Expected Return: {regime_data['avg_return']:+.2f}%")
    print(f"   Success Rate: {regime_data['success_rate']:.1f}%")
    print(f"   Best Quintile: {regime_data['best_quintile']}")
    
    # Adaptive weights
    weights = strategy.get_adaptive_scoring_weights(current_regime)
    print(f"\n⚙️  ADAPTIVE SCORING WEIGHTS FOR {current_regime}:")
    for component, weight in weights.items():
        print(f"   {component:<20}: {weight:.1%}")
    
    # Position sizing
    position_strategy = strategy.get_position_sizing_strategy(current_regime)
    print(f"\n📊 POSITION SIZING STRATEGY:")
    print(f"   Max Position Size: {position_strategy['max_position']:.1%}")
    print(f"   Portfolio Exposure: {position_strategy['portfolio_exposure']:.1%}")
    print(f"   Cash Reserve: {position_strategy['cash_reserve']:.1%}")
    
    # Risk management
    stop_loss = strategy._get_stop_loss_for_regime(current_regime)
    rebalance_freq = strategy._get_rebalance_frequency(current_regime)
    monitoring = strategy._get_monitoring_level(current_regime)
    
    print(f"\n🛡️  RISK MANAGEMENT:")
    print(f"   Stop Loss: {stop_loss}")
    print(f"   Rebalance: {rebalance_freq}")
    print(f"   Monitoring: {monitoring}")
    
    # Save strategy configuration
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_filename = f'adaptive_strategy_config_{timestamp}.json'
    
    config_data = {
        'current_regime': current_regime_data,
        'market_performance': strategy.market_performance,
        'adaptive_weights': strategy.adaptive_weights,
        'position_sizing': strategy.position_sizing,
        'generated_timestamp': datetime.now().isoformat()
    }
    
    with open(config_filename, 'w') as f:
        json.dump(config_data, f, indent=2, default=str)
    
    print(f"\n💾 Strategy configuration saved: {config_filename}")
    print(f"\n✅ ADAPTIVE STRATEGY REPORT COMPLETE!")

if __name__ == "__main__":
    create_adaptive_strategy_report()