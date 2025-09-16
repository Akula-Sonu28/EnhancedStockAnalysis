"""
Portfolio Insights - Advanced Analysis and Recommendations

This module provides advanced portfolio insights including:
- Exit strategy recommendations with specific price targets
- Buy recommendations  
- Rebalancing strategies
- Capital rotation suggestions
- Risk analysis
- Performance optimization
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from .sell_signals import SellSignalsEngine

class PortfolioInsights:
    """Advanced Portfolio Insights and Recommendations Engine"""
    
    def __init__(self, portfolio_analyzer):
        """
        Initialize Portfolio Insights
        
        Args:
            portfolio_analyzer: Instance of PortfolioAnalyzer
        """
        self.analyzer = portfolio_analyzer
        self.logger = logging.getLogger('PortfolioInsights')
        
        # Initialize enhanced sell signals engine
        self.sell_signals_engine = SellSignalsEngine(portfolio_analyzer)
        
        # Risk thresholds and parameters
        self.LOSS_THRESHOLD = -10.0  # Exit if loss > 10%
        self.PROFIT_BOOKING_THRESHOLD = 25.0  # Consider booking if profit > 25%
        self.CONCENTRATION_LIMIT = 20.0  # Single stock/sector limit
        self.MIN_POSITION_SIZE = 5000  # Minimum position size for new investments
        
    def analyze_exit_strategies(self) -> Dict:
        """Identify stocks that should be exited and provide timing recommendations"""
        if self.analyzer.holdings_df is None:
            return {}
            
        try:
            exit_recommendations = []
            merged_df = self.analyzer.get_holdings_with_enhanced_data()
            
            for _, stock in merged_df.iterrows():
                recommendation = self._analyze_single_stock_exit(stock)
                if recommendation:
                    exit_recommendations.append(recommendation)
            
            # Categorize recommendations
            exit_analysis = {
                'immediate_exits': [r for r in exit_recommendations if r['urgency'] == 'IMMEDIATE'],
                'consider_exits': [r for r in exit_recommendations if r['urgency'] == 'CONSIDER'],
                'profit_booking': [r for r in exit_recommendations if r['reason'] == 'PROFIT_BOOKING'],
                'stop_losses': [r for r in exit_recommendations if r['reason'] == 'STOP_LOSS'],
                'total_exit_recommendations': len(exit_recommendations)
            }
            
            return exit_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing exit strategies: {str(e)}")
            return {}
    
    def _analyze_single_stock_exit(self, stock: pd.Series) -> Optional[Dict]:
        """Analyze individual stock for exit recommendation"""
        try:
            instrument = stock['Instrument']
            return_pct = stock.get('Return_Pct', 0)
            current_value = stock.get('Cur. val', 0)
            day_change = stock.get('Day chg.', 0)
            
            # Get enhanced data if available
            risk_category = stock.get('risk_category', 'MEDIUM')
            final_recommendation = stock.get('final_recommendation', '')
            
            recommendation = None
            
            # Stop Loss Analysis
            if return_pct <= self.LOSS_THRESHOLD:
                if day_change < -2:  # Declining trend
                    recommendation = {
                        'instrument': instrument,
                        'action': 'SELL',
                        'reason': 'STOP_LOSS',
                        'urgency': 'IMMEDIATE',
                        'current_return': return_pct,
                        'current_value': current_value,
                        'rationale': f'Loss of {return_pct:.1f}% with declining trend ({day_change:.1f}% today)',
                        'target_timeline': '1-3 days'
                    }
                else:
                    recommendation = {
                        'instrument': instrument,
                        'action': 'SELL',
                        'reason': 'STOP_LOSS',
                        'urgency': 'CONSIDER',
                        'current_return': return_pct,
                        'current_value': current_value,
                        'rationale': f'Significant loss of {return_pct:.1f}%, monitor for further decline',
                        'target_timeline': '1 week'
                    }
            
            # Profit Booking Analysis
            elif return_pct >= self.PROFIT_BOOKING_THRESHOLD:
                if 'SELL' in str(final_recommendation).upper() or 'OVERVALUED' in str(final_recommendation).upper():
                    recommendation = {
                        'instrument': instrument,
                        'action': 'SELL',
                        'reason': 'PROFIT_BOOKING',
                        'urgency': 'CONSIDER',
                        'current_return': return_pct,
                        'current_value': current_value,
                        'rationale': f'Strong profit of {return_pct:.1f}% and marked as overvalued in analysis',
                        'target_timeline': '2-4 weeks'
                    }
                elif return_pct >= 50:  # Very high profits
                    recommendation = {
                        'instrument': instrument,
                        'action': 'PARTIAL_SELL',
                        'reason': 'PROFIT_BOOKING',
                        'urgency': 'CONSIDER',
                        'current_return': return_pct,
                        'current_value': current_value,
                        'rationale': f'Exceptional profit of {return_pct:.1f}%, consider booking 50% profit',
                        'target_timeline': '2-3 weeks'
                    }
            
            # Risk Category Analysis
            elif risk_category == 'HIGH' and return_pct < 5:
                recommendation = {
                    'instrument': instrument,
                    'action': 'MONITOR',
                    'reason': 'HIGH_RISK',
                    'urgency': 'CONSIDER',
                    'current_return': return_pct,
                    'current_value': current_value,
                    'rationale': f'High risk stock with modest returns ({return_pct:.1f}%)',
                    'target_timeline': '2 weeks'
                }
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error analyzing stock {stock.get('Instrument', 'Unknown')}: {str(e)}")
            return None
    
    def analyze_buy_recommendations(self) -> Dict:
        """Generate intelligent buy recommendations based on Enhanced Stock Report"""
        if self.analyzer.enhanced_report_df is None:
            return {}
            
        try:
            available_funds = self.analyzer.available_funds
            
            # Get top picks and strong buy recommendations
            top_picks = self.analyzer.enhanced_report_df.get('Top Picks', pd.DataFrame())
            complete_data = self.analyzer.enhanced_report_df.get('Complete Data', pd.DataFrame())
            
            if complete_data.empty:
                return {}
            
            # Filter for strong buy recommendations
            strong_buys = complete_data[
                complete_data['final_recommendation'].str.contains('STRONG BUY', case=False, na=False)
            ].copy()
            
            # Exclude stocks already in portfolio
            current_holdings = set(self.analyzer.holdings_df['Instrument'].tolist())
            strong_buys = strong_buys[~strong_buys['symbol'].isin(current_holdings)]
            
            # Analyze sector gaps
            sector_gaps = self._analyze_sector_gaps()
            
            buy_recommendations = []
            
            for _, stock in strong_buys.head(10).iterrows():  # Top 10 recommendations
                recommendation = self._create_buy_recommendation(stock, sector_gaps, available_funds)
                if recommendation:
                    buy_recommendations.append(recommendation)
            
            # Sort by priority score
            buy_recommendations.sort(key=lambda x: x['priority_score'], reverse=True)
            
            # Calculate position sizes
            total_recommendations = len(buy_recommendations[:5])  # Top 5
            if total_recommendations > 0 and available_funds > 0:
                avg_position_size = min(available_funds / total_recommendations, available_funds * 0.3)
                
                for rec in buy_recommendations[:5]:
                    rec['suggested_amount'] = min(avg_position_size, available_funds * 0.25)
            
            buy_analysis = {
                'top_buy_recommendations': buy_recommendations[:5],
                'all_buy_recommendations': buy_recommendations,
                'total_investment_needed': sum([r.get('suggested_amount', 0) for r in buy_recommendations[:5]]),
                'available_funds': available_funds,
                'sector_gaps': sector_gaps
            }
            
            return buy_analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing buy recommendations: {str(e)}")
            return {}
    
    def _analyze_sector_gaps(self) -> Dict:
        """Identify sector allocation gaps and opportunities"""
        if self.analyzer.sector_data is None:
            return {}
            
        try:
            # Ideal sector allocation (can be customized)
            ideal_allocation = {
                'Banking': 25,
                'IT': 20,
                'Consumer Goods': 15,
                'Healthcare': 10,
                'Infrastructure': 10,
                'Energy': 8,
                'Metals': 7,
                'Others': 5
            }
            
            current_allocation = {}
            for _, row in self.analyzer.sector_data.iterrows():
                current_allocation[row['Sector']] = row['Weight_Pct']
            
            gaps = {}
            for sector, ideal_pct in ideal_allocation.items():
                current_pct = current_allocation.get(sector, 0)
                gap = ideal_pct - current_pct
                if gap > 5:  # Significant underallocation
                    gaps[sector] = {
                        'current_allocation': current_pct,
                        'ideal_allocation': ideal_pct,
                        'gap_percentage': gap,
                        'priority': 'HIGH' if gap > 10 else 'MEDIUM'
                    }
            
            return gaps
            
        except Exception as e:
            self.logger.error(f"Error analyzing sector gaps: {str(e)}")
            return {}
    
    def _create_buy_recommendation(self, stock: pd.Series, sector_gaps: Dict, available_funds: float) -> Optional[Dict]:
        """Create individual buy recommendation"""
        try:
            symbol = stock['symbol']
            sector = stock.get('sector', 'Unknown')
            current_price = stock.get('current_price', 0)
            overall_score = stock.get('overall_score_with_value', 0)
            risk_category = stock.get('risk_category', 'MEDIUM')
            
            # Calculate priority score
            priority_score = overall_score
            
            # Boost score for sector gaps
            if sector in sector_gaps:
                gap_info = sector_gaps[sector]
                if gap_info['priority'] == 'HIGH':
                    priority_score += 20
                elif gap_info['priority'] == 'MEDIUM':
                    priority_score += 10
            
            # Adjust for risk
            if risk_category == 'LOW':
                priority_score += 5
            elif risk_category == 'HIGH':
                priority_score -= 10
            
            # Check minimum position size
            min_amount = max(self.MIN_POSITION_SIZE, current_price * 10)  # At least 10 shares
            if available_funds < min_amount:
                return None
            
            recommendation = {
                'symbol': symbol,
                'sector': sector,
                'current_price': current_price,
                'priority_score': priority_score,
                'risk_category': risk_category,
                'overall_score': overall_score,
                'rationale': self._generate_buy_rationale(stock, sector_gaps),
                'min_investment': min_amount,
                'target_timeline': '2-4 weeks',
                'sector_gap_benefit': sector in sector_gaps
            }
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error creating buy recommendation for {stock.get('symbol', 'Unknown')}: {str(e)}")
            return None
    
    def _generate_buy_rationale(self, stock: pd.Series, sector_gaps: Dict) -> str:
        """Generate rationale for buy recommendation"""
        rationale_parts = []
        
        # Overall score
        score = stock.get('overall_score_with_value', 0)
        if score >= 80:
            rationale_parts.append(f"Excellent fundamental score ({score:.1f}/100)")
        elif score >= 70:
            rationale_parts.append(f"Strong fundamental score ({score:.1f}/100)")
        
        # Risk category
        risk = stock.get('risk_category', 'MEDIUM')
        if risk == 'LOW':
            rationale_parts.append("Low risk profile")
        
        # Sector gap
        sector = stock.get('sector', '')
        if sector in sector_gaps:
            gap_pct = sector_gaps[sector]['gap_percentage']
            rationale_parts.append(f"Addresses {sector} sector underallocation ({gap_pct:.1f}% gap)")
        
        # Valuation
        if 'UNDERVALUED' in str(stock.get('final_recommendation', '')):
            rationale_parts.append("Currently undervalued")
        
        return "; ".join(rationale_parts) if rationale_parts else "Strong technical and fundamental indicators"
    
    def analyze_rebalancing_strategies(self) -> Dict:
        """Analyze portfolio rebalancing opportunities"""
        try:
            rebalancing = {
                'sector_rebalancing': [],
                'position_sizing': [],
                'concentration_risks': [],
                'capital_deployment': {}
            }
            
            # Sector concentration analysis
            if self.analyzer.sector_data is not None:
                for _, sector in self.analyzer.sector_data.iterrows():
                    if sector['Weight_Pct'] > self.CONCENTRATION_LIMIT:
                        rebalancing['concentration_risks'].append({
                            'sector': sector['Sector'],
                            'current_weight': sector['Weight_Pct'],
                            'recommended_action': 'REDUCE',
                            'target_weight': self.CONCENTRATION_LIMIT,
                            'excess_amount': (sector['Weight_Pct'] - self.CONCENTRATION_LIMIT) / 100 * self.analyzer.portfolio_metrics.get('current_value', 0)
                        })
            
            # Individual stock concentration
            for _, stock in self.analyzer.holdings_df.iterrows():
                if stock['Weight'] > self.CONCENTRATION_LIMIT:
                    rebalancing['position_sizing'].append({
                        'instrument': stock['Instrument'],
                        'current_weight': stock['Weight'],
                        'recommended_action': 'TRIM',
                        'current_value': stock['Cur. val'],
                        'excess_amount': (stock['Weight'] - self.CONCENTRATION_LIMIT) / 100 * self.analyzer.portfolio_metrics.get('current_value', 0)
                    })
            
            # Capital deployment strategy
            available_funds = self.analyzer.available_funds
            if available_funds > 0:
                sector_gaps = self._analyze_sector_gaps()
                total_gap_value = sum([
                    gap['gap_percentage'] / 100 * self.analyzer.portfolio_metrics.get('current_value', 0) 
                    for gap in sector_gaps.values()
                ])
                
                rebalancing['capital_deployment'] = {
                    'available_funds': available_funds,
                    'sector_gap_opportunity': min(available_funds, total_gap_value),
                    'recommended_deployment': min(available_funds * 0.8, total_gap_value),
                    'priority_sectors': [
                        sector for sector, gap in sector_gaps.items() 
                        if gap['priority'] == 'HIGH'
                    ][:3]
                }
            
            return rebalancing
            
        except Exception as e:
            self.logger.error(f"Error analyzing rebalancing strategies: {str(e)}")
            return {}
    
    def calculate_portfolio_health_score(self) -> Dict:
        """Calculate overall portfolio health score and insights"""
        try:
            health_metrics = {
                'overall_score': 0,
                'performance_score': 0,
                'diversification_score': 0,
                'risk_score': 0,
                'allocation_score': 0,
                'recommendations': []
            }
            
            # Performance Score (0-30 points)
            total_return = self.analyzer.portfolio_metrics.get('total_return_pct', 0)
            if total_return >= 15:
                health_metrics['performance_score'] = 30
            elif total_return >= 10:
                health_metrics['performance_score'] = 25
            elif total_return >= 5:
                health_metrics['performance_score'] = 20
            elif total_return >= 0:
                health_metrics['performance_score'] = 15
            else:
                health_metrics['performance_score'] = max(0, 15 + total_return)  # Penalty for losses
            
            # Diversification Score (0-25 points)
            num_holdings = self.analyzer.portfolio_metrics.get('number_of_holdings', 0)
            top5_concentration = self.analyzer.portfolio_metrics.get('top_5_concentration', 100)
            
            if num_holdings >= 15 and top5_concentration <= 60:
                health_metrics['diversification_score'] = 25
            elif num_holdings >= 10 and top5_concentration <= 70:
                health_metrics['diversification_score'] = 20
            elif num_holdings >= 8:
                health_metrics['diversification_score'] = 15
            else:
                health_metrics['diversification_score'] = 10
            
            # Risk Score (0-25 points) - Based on sector allocation and risk categories
            if self.analyzer.sector_data is not None:
                max_sector_weight = self.analyzer.sector_data['Weight_Pct'].max()
                if max_sector_weight <= 30:
                    health_metrics['risk_score'] = 25
                elif max_sector_weight <= 40:
                    health_metrics['risk_score'] = 20
                elif max_sector_weight <= 50:
                    health_metrics['risk_score'] = 15
                else:
                    health_metrics['risk_score'] = 10
            else:
                health_metrics['risk_score'] = 15  # Neutral score
            
            # Allocation Score (0-20 points) - Based on available funds utilization
            if self.analyzer.available_funds > 0:
                current_value = self.analyzer.portfolio_metrics.get('current_value', 1)
                cash_percentage = self.analyzer.available_funds / (current_value + self.analyzer.available_funds) * 100
                
                if 5 <= cash_percentage <= 15:  # Optimal cash level
                    health_metrics['allocation_score'] = 20
                elif cash_percentage <= 25:
                    health_metrics['allocation_score'] = 15
                else:
                    health_metrics['allocation_score'] = 10  # Too much cash sitting idle
            else:
                health_metrics['allocation_score'] = 15  # Fully invested
            
            # Calculate overall score
            health_metrics['overall_score'] = (
                health_metrics['performance_score'] +
                health_metrics['diversification_score'] +
                health_metrics['risk_score'] +
                health_metrics['allocation_score']
            )
            
            # Generate recommendations based on scores
            if health_metrics['performance_score'] < 15:
                health_metrics['recommendations'].append("Consider reviewing underperforming stocks for exit")
            
            if health_metrics['diversification_score'] < 20:
                health_metrics['recommendations'].append("Improve diversification across sectors and stocks")
            
            if health_metrics['risk_score'] < 20:
                health_metrics['recommendations'].append("Reduce sector concentration risk")
            
            if health_metrics['allocation_score'] < 15:
                health_metrics['recommendations'].append("Optimize cash deployment strategy")
            
            return health_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio health score: {str(e)}")
            return {}
    
    def get_enhanced_sell_recommendations(self) -> Dict:
        """Get enhanced sell recommendations with specific price targets and rotation strategies"""
        try:
            # Get enhanced sell signals
            sell_analysis = self.sell_signals_engine.analyze_sell_signals()
            
            # Format for integration with existing portfolio analysis
            formatted_recommendations = {
                'immediate_sells': [],
                'profit_booking': [],
                'stop_losses': [],
                'rotation_strategies': [],
                'summary': sell_analysis.get('summary', {}),
                'total_proceeds_available': sell_analysis.get('total_capital_available', 0)
            }
            
            # Categorize recommendations by urgency and type
            for rec in sell_analysis.get('sell_recommendations', []):
                if rec.get('urgency') == 'HIGH':
                    formatted_recommendations['immediate_sells'].append(rec)
                elif 'PROFIT' in rec.get('reason', ''):
                    formatted_recommendations['profit_booking'].append(rec)
                elif 'LOSS' in rec.get('reason', ''):
                    formatted_recommendations['stop_losses'].append(rec)
            
            # Add rotation strategies
            formatted_recommendations['rotation_strategies'] = sell_analysis.get('individual_rotations', [])
            formatted_recommendations['portfolio_rotation'] = sell_analysis.get('portfolio_rotation_strategy', {})
            
            return formatted_recommendations
            
        except Exception as e:
            self.logger.error(f"Error getting enhanced sell recommendations: {e}")
            return {
                'immediate_sells': [],
                'profit_booking': [],
                'stop_losses': [],
                'rotation_strategies': [],
                'summary': {},
                'total_proceeds_available': 0
            }