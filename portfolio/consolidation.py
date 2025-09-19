"""
Portfolio Consolidation Engine
Optimizes portfolio to 25-30 holdings by identifying stocks to remove/consolidate
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class PortfolioConsolidation:
    def __init__(self, analyzer, target_min_stocks=25, target_max_stocks=30):
        self.analyzer = analyzer
        self.target_min_stocks = target_min_stocks
        self.target_max_stocks = target_max_stocks
        
    def analyze_consolidation_opportunities(self) -> Dict:
        """
        Analyze portfolio and suggest which stocks to remove/consolidate
        Returns consolidated recommendations with sell signals and capital rotation
        """
        try:
            holdings_df = self.analyzer.holdings_df.copy()
            current_count = len(holdings_df)
            
            if current_count <= self.target_max_stocks:
                return {
                    'current_holdings': current_count,
                    'target_range': f"{self.target_min_stocks}-{self.target_max_stocks}",
                    'action_needed': False,
                    'message': f"Portfolio already optimized with {current_count} holdings"
                }
            
            # Calculate removal needed
            stocks_to_remove = current_count - self.target_max_stocks
            
            # Score each holding for removal priority
            removal_scores = self._calculate_removal_scores(holdings_df)
            
            # Identify stocks to remove with sell signals
            removal_candidates = self._identify_removal_candidates_with_sell_signals(removal_scores, stocks_to_remove)
            
            # Calculate consolidation benefits and capital rotation
            consolidation_impact = self._calculate_consolidation_impact_with_rotation(removal_candidates)
            
            return {
                'current_holdings': current_count,
                'target_range': f"{self.target_min_stocks}-{self.target_max_stocks}",
                'stocks_to_remove': stocks_to_remove,
                'action_needed': True,
                'removal_candidates': removal_candidates,
                'consolidation_impact': consolidation_impact,
                'recommended_actions': self._generate_consolidation_actions_with_rotation(removal_candidates),
                'sell_recommendations': self._generate_sell_recommendations(removal_candidates),
                'capital_rotation': consolidation_impact.get('capital_rotation', {})
            }
            
        except Exception as e:
            logger.error(f"Error in consolidation analysis: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_removal_scores(self, holdings_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate priority scores for each holding (higher score = higher removal priority)
        """
        scores_df = holdings_df.copy()
        
        # Initialize removal score
        scores_df['removal_score'] = 0.0
        scores_df['removal_reasons'] = ''
        
        # Factor 1: Position Size (smaller positions get higher removal score)
        current_val_col = 'Cur. val' if 'Cur. val' in scores_df.columns else 'Current Value'
        scores_df['size_score'] = self._score_by_position_size(scores_df[current_val_col])
        
        # Factor 2: Performance (poor performers get higher removal score)
        pnl_col = 'P&L' if 'P&L' in scores_df.columns else 'P&L %'
        if pnl_col not in scores_df.columns:
            # Calculate P&L % if not available
            invested_col = 'Invested' if 'Invested' in scores_df.columns else 'Investment'
            if invested_col in scores_df.columns and current_val_col in scores_df.columns:
                scores_df[pnl_col] = ((scores_df[current_val_col] - scores_df[invested_col]) / scores_df[invested_col]) * 100
            else:
                scores_df[pnl_col] = 0  # Default to 0 if can't calculate
        
        scores_df['performance_score'] = self._score_by_performance(scores_df[pnl_col])
        
        # Factor 3: Sector Concentration (over-represented sectors get higher removal score)
        scores_df['sector_score'] = self._score_by_sector_concentration(scores_df)
        
        # Factor 4: Quality Score (if available from enhanced report)
        symbol_col = 'Instrument' if 'Instrument' in scores_df.columns else 'Symbol'
        scores_df['quality_score'] = self._score_by_quality(scores_df[symbol_col])
        
        # Factor 5: Liquidity/Risk (high-risk low-liquidity stocks get higher removal score)
        scores_df['risk_score'] = self._score_by_risk_factors(scores_df[symbol_col])
        
        # Calculate composite removal score (0-100, higher = more likely to remove)
        scores_df['removal_score'] = (
            scores_df['size_score'] * 0.25 +
            scores_df['performance_score'] * 0.25 +
            scores_df['sector_score'] * 0.20 +
            scores_df['quality_score'] * 0.20 +
            scores_df['risk_score'] * 0.10
        )
        
        # Add removal reasons
        scores_df['removal_reasons'] = scores_df.apply(self._generate_removal_reasons, axis=1)
        
        return scores_df.sort_values('removal_score', ascending=False)
    
    def _score_by_position_size(self, values: pd.Series) -> pd.Series:
        """Score based on position size (smaller = higher removal priority)"""
        percentiles = values.rank(pct=True)
        # Invert so smaller positions get higher scores
        return (1 - percentiles) * 100
    
    def _score_by_performance(self, returns: pd.Series) -> pd.Series:
        """Score based on performance (worse performance = higher removal priority)"""
        # Handle inf and nan values
        clean_returns = returns.replace([np.inf, -np.inf], np.nan)
        percentiles = clean_returns.rank(pct=True, na_option='bottom')
        # Invert so poor performers get higher scores
        return (1 - percentiles.fillna(1)) * 100
    
    def _score_by_sector_concentration(self, df: pd.DataFrame) -> pd.Series:
        """Score based on sector over-representation"""
        # Get sector allocation from analyzer
        try:
            sector_allocation = self.analyzer.get_sector_allocation()
            sector_weights = {sector: data['weight'] for sector, data in sector_allocation.items()}
            
            # Map sectors to holdings and score based on overweight
            scores = []
            symbol_col = 'Instrument' if 'Instrument' in df.columns else 'Symbol'
            for _, row in df.iterrows():
                symbol = row[symbol_col]
                sector = self._get_stock_sector(symbol)
                sector_weight = sector_weights.get(sector, 0)
                
                # Higher score for stocks in overweight sectors
                if sector_weight > 20:  # Overweight threshold
                    score = min(sector_weight * 2, 100)  # Cap at 100
                else:
                    score = 0
                scores.append(score)
            
            return pd.Series(scores, index=df.index)
            
        except Exception:
            return pd.Series(0, index=df.index)
    
    def _score_by_quality(self, symbols: pd.Series) -> pd.Series:
        """Score based on fundamental quality (lower quality = higher removal priority)"""
        scores = []
        
        for symbol in symbols:
            try:
                # Get quality metrics from enhanced report if available
                quality_score = self._get_fundamental_score(symbol)
                
                if quality_score is not None and quality_score > 0:
                    # Invert quality score (lower quality = higher removal priority)
                    removal_score = max(0, 100 - quality_score)
                else:
                    removal_score = 50  # Neutral score for unknown quality
                    
                scores.append(removal_score)
                
            except Exception:
                scores.append(50)  # Neutral score on error
        
        return pd.Series(scores, index=symbols.index)
    
    def _score_by_risk_factors(self, symbols: pd.Series) -> pd.Series:
        """Score based on risk factors (higher risk = higher removal priority)"""
        scores = []
        
        for symbol in symbols:
            score = 0
            
            # Check for risk factors
            if self._is_penny_stock(symbol):
                score += 30
            
            if self._is_low_liquidity(symbol):
                score += 20
                
            if self._is_high_volatility(symbol):
                score += 25
                
            if self._is_speculative_sector(symbol):
                score += 25
            
            scores.append(min(score, 100))  # Cap at 100
        
        return pd.Series(scores, index=symbols.index)
    
    def _identify_removal_candidates(self, scores_df: pd.DataFrame, count_to_remove: int, pnl_col: str = 'P&L') -> List[Dict]:
        """Identify top candidates for removal"""
        candidates = []
        
        # Get top removal candidates
        top_candidates = scores_df.head(count_to_remove)
        
        for _, row in top_candidates.iterrows():
            candidates.append({
                'symbol': row['Symbol'],
                'current_value': row['Current Value'],
                'pnl_percent': row.get('P&L %', 0),
                'removal_score': round(row['removal_score'], 1),
                'reasons': row['removal_reasons'],
                'sector': self._get_stock_sector(row['Symbol']),
                'recommended_action': self._get_removal_action(row)
            })
        
        return candidates
    
    def _calculate_consolidation_impact(self, removal_candidates: List[Dict]) -> Dict:
        """Calculate the impact of portfolio consolidation"""
        total_value_freed = sum(candidate['current_value'] for candidate in removal_candidates)
        
        # Calculate sector impact
        sectors_impacted = {}
        for candidate in removal_candidates:
            sector = candidate['sector']
            if sector not in sectors_impacted:
                sectors_impacted[sector] = {'count': 0, 'value': 0}
            sectors_impacted[sector]['count'] += 1
            sectors_impacted[sector]['value'] += candidate['current_value']
        
        return {
            'total_value_freed': total_value_freed,
            'average_position_size_increase': total_value_freed / (len(self.analyzer.holdings_df) - len(removal_candidates)),
            'sectors_impacted': sectors_impacted,
            'management_complexity_reduction': f"{len(removal_candidates)} fewer positions to monitor",
            'expected_benefits': [
                "Reduced portfolio complexity",
                "Increased position sizes in remaining stocks",
                "Better focus on quality holdings",
                f"₹{total_value_freed:,.0f} available for reallocation"
            ]
        }
    
    def _generate_consolidation_actions(self, removal_candidates: List[Dict]) -> List[Dict]:
        """Generate specific consolidation actions"""
        actions = []
        
        # Group by action type
        immediate_sells = [c for c in removal_candidates if c['recommended_action'] == 'SELL_IMMEDIATELY']
        gradual_exits = [c for c in removal_candidates if c['recommended_action'] == 'GRADUAL_EXIT']
        
        if immediate_sells:
            actions.append({
                'action': 'Immediate Liquidation',
                'timeline': 'This week',
                'stocks': [c['symbol'] for c in immediate_sells],
                'value': sum(c['current_value'] for c in immediate_sells),
                'rationale': 'Poor performers or high-risk positions'
            })
        
        if gradual_exits:
            actions.append({
                'action': 'Gradual Exit Strategy',
                'timeline': '2-4 weeks',
                'stocks': [c['symbol'] for c in gradual_exits],
                'value': sum(c['current_value'] for c in gradual_exits),
                'rationale': 'Profitable but non-core positions'
            })
        
        # Reallocation strategy
        total_proceeds = sum(c['current_value'] for c in removal_candidates)
        if total_proceeds > 0:
            actions.append({
                'action': 'Capital Reallocation',
                'timeline': 'After sales completion',
                'description': f"Reinvest ₹{total_proceeds:,.0f} into remaining {self.target_max_stocks} core holdings",
                'strategy': 'Increase position sizes in top-performing, high-quality stocks'
            })
        
        return actions
    
    def _generate_removal_reasons(self, row: pd.Series) -> str:
        """Generate human-readable removal reasons"""
        reasons = []
        
        if row['size_score'] > 70:
            reasons.append("Small position size")
        
        if row['performance_score'] > 60:
            reasons.append("Poor performance")
            
        if row['sector_score'] > 50:
            reasons.append("Sector overweight")
            
        if row['quality_score'] > 70:
            reasons.append("Lower quality metrics")
            
        if row['risk_score'] > 50:
            reasons.append("High risk factors")
        
        return "; ".join(reasons) if reasons else "Optimization candidate"
    
    def _get_removal_action(self, row: pd.Series) -> str:
        """Determine removal action based on stock characteristics"""
        pnl = row.get('P&L %', 0)
        
        if isinstance(pnl, str) or pd.isna(pnl):
            return 'SELL_IMMEDIATELY'
        
        if pnl < -10:  # Significant loss
            return 'SELL_IMMEDIATELY'
        elif pnl > 20:  # Good profit
            return 'GRADUAL_EXIT'
        else:
            return 'SELL_IMMEDIATELY'
    
    # Helper methods
    def _get_stock_sector(self, symbol: str) -> str:
        """Get sector for a stock"""
        try:
            if hasattr(self.analyzer, 'enhanced_report_df') and isinstance(self.analyzer.enhanced_report_df, dict):
                # Try to get from enhanced report
                for sheet_name, sheet_df in self.analyzer.enhanced_report_df.items():
                    if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
                        symbol_col = None
                        for col in ['Symbol', 'Instrument', 'Stock', 'Name']:
                            if col in sheet_df.columns:
                                symbol_col = col
                                break
                        
                        if symbol_col and symbol in sheet_df[symbol_col].values:
                            matching_row = sheet_df[sheet_df[symbol_col] == symbol]
                            if not matching_row.empty and 'Sector' in sheet_df.columns:
                                return matching_row['Sector'].iloc[0]
            return 'Unknown'
        except Exception as e:
            return 'Unknown'
    
    def _get_fundamental_score(self, symbol: str) -> float:
        """Get fundamental score from enhanced report"""
        try:
            if hasattr(self.analyzer, 'enhanced_report_df') and isinstance(self.analyzer.enhanced_report_df, dict):
                for sheet_name, sheet_df in self.analyzer.enhanced_report_df.items():
                    if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
                        symbol_col = None
                        for col in ['Symbol', 'Instrument', 'Stock', 'Name']:
                            if col in sheet_df.columns:
                                symbol_col = col
                                break
                        
                        if symbol_col and symbol in sheet_df[symbol_col].values:
                            score_cols = [col for col in sheet_df.columns if 'score' in col.lower() or 'rating' in col.lower()]
                            if score_cols:
                                matching_row = sheet_df[sheet_df[symbol_col] == symbol]
                                if not matching_row.empty:
                                    return matching_row[score_cols[0]].iloc[0]
            return None
        except Exception:
            return None
    
    def _is_penny_stock(self, symbol: str) -> bool:
        """Check if stock is penny stock (< ₹10)"""
        try:
            symbol_col = 'Instrument' if 'Instrument' in self.analyzer.holdings_df.columns else 'Symbol'
            price_col = 'LTP' if 'LTP' in self.analyzer.holdings_df.columns else 'Current Price'
            holdings_row = self.analyzer.holdings_df[self.analyzer.holdings_df[symbol_col] == symbol]
            if not holdings_row.empty:
                current_price = holdings_row[price_col].iloc[0]
                return current_price < 10
            return False
        except Exception:
            return False
    
    def _is_low_liquidity(self, symbol: str) -> bool:
        """Check for low liquidity indicators"""
        # Simple heuristic - could be enhanced with volume data
        small_cap_indicators = ['SMALL', 'MICRO', 'PENNY']
        return any(indicator in symbol.upper() for indicator in small_cap_indicators)
    
    def _is_high_volatility(self, symbol: str) -> bool:
        """Check for high volatility stocks"""
        # Simple heuristic - could be enhanced with historical volatility data
        volatile_sectors = ['CRYPTO', 'BIOTECH', 'PHARMA']
        return any(sector in symbol.upper() for sector in volatile_sectors)
    
    def _is_speculative_sector(self, symbol: str) -> bool:
        """Check if stock is in speculative sector"""
        sector = self._get_stock_sector(symbol)
        speculative_sectors = ['Unknown', 'Crypto', 'Biotech']
        return sector in speculative_sectors
    
    def _identify_removal_candidates_with_sell_signals(self, removal_scores: pd.DataFrame, stocks_to_remove: int) -> List[Dict]:
        """
        Identify stocks to remove and generate sell signals with price targets
        """
        # Get top candidates for removal
        top_removal_candidates = removal_scores.head(stocks_to_remove)
        
        candidates = []
        for _, row in top_removal_candidates.iterrows():
            # Generate sell signal with price target
            sell_signal = self._generate_sell_signal_for_stock(row)
            
            # Use correct column names from holdings data
            symbol_col = 'Instrument' if 'Instrument' in row.index else 'Symbol'
            current_val_col = 'Cur. val' if 'Cur. val' in row.index else 'Current Value'
            
            candidate = {
                'symbol': row[symbol_col],
                'current_value': row[current_val_col],
                'removal_score': row['removal_score'],
                'removal_reasons': row['removal_reasons'],
                'sell_signal': sell_signal,
                'priority': self._get_removal_priority(row['removal_score'])
            }
            candidates.append(candidate)
        
        return candidates
    
    def _generate_sell_signal_for_stock(self, stock_row) -> Dict:
        """
        Generate sell signal with price target for a stock
        """
        try:
            symbol_col = 'Instrument' if 'Instrument' in stock_row.index else 'Symbol'
            price_col = 'LTP' if 'LTP' in stock_row.index else 'Current Price'
            pnl_col = 'P&L' if 'P&L' in stock_row.index else 'P&L %'
            current_val_col = 'Cur. val' if 'Cur. val' in stock_row.index else 'Current Value'
            
            symbol = stock_row[symbol_col]
            current_price = stock_row[price_col]
            
            # Calculate P&L % if needed
            if pnl_col == 'P&L' and 'P&L %' not in stock_row.index:
                invested_col = 'Invested' if 'Invested' in stock_row.index else 'Investment'
                if invested_col in stock_row.index and stock_row[invested_col] > 0:
                    pnl_pct = (stock_row[pnl_col] / stock_row[invested_col]) * 100
                else:
                    pnl_pct = 0
            else:
                pnl_pct = stock_row.get('P&L %', 0)
            
            # Get technical data for price target
            technical_data = self._get_technical_data_for_stock(symbol)
            
            # Determine sell type and target price
            if pnl_pct < -10:
                sell_type = 'STOP_LOSS'
                target_price = current_price * 0.98  # Immediate exit with 2% buffer
                urgency = 'IMMEDIATE'
            elif stock_row['removal_score'] > 80:
                sell_type = 'CONSOLIDATION_SELL'
                target_price = current_price * 0.99  # Quick exit with 1% buffer
                urgency = 'HIGH'
            else:
                sell_type = 'GRADUAL_EXIT'
                target_price = max(current_price * 1.02, technical_data.get('support_1', current_price * 0.98))
                urgency = 'MEDIUM'
            
            return {
                'type': sell_type,
                'target_price': round(target_price, 2),
                'current_price': current_price,
                'urgency': urgency,
                'expected_proceeds': stock_row[current_val_col],
                'rationale': f"Portfolio consolidation: {stock_row['removal_reasons']}"
            }
            
        except Exception as e:
            price_col = 'LTP' if 'LTP' in stock_row.index else 'Current Price'
            current_val_col_fallback = 'Cur. val' if 'Cur. val' in stock_row.index else 'Current Value'
            return {
                'type': 'MARKET_SELL',
                'target_price': stock_row[price_col],
                'current_price': stock_row[price_col],
                'urgency': 'MEDIUM',
                'expected_proceeds': stock_row[current_val_col_fallback],
                'rationale': f"Portfolio consolidation (error in analysis: {str(e)})"
            }
    
    def _get_technical_data_for_stock(self, symbol: str) -> Dict:
        """
        Get technical analysis data for price target calculation
        """
        try:
            # Try to get from enhanced report
            if hasattr(self.analyzer, 'enhanced_report_df') and isinstance(self.analyzer.enhanced_report_df, dict):
                for sheet_name, sheet_df in self.analyzer.enhanced_report_df.items():
                    if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
                        symbol_col = None
                        for col in ['Symbol', 'Instrument', 'Stock', 'Name']:
                            if col in sheet_df.columns:
                                symbol_col = col
                                break
                        
                        if symbol_col and symbol in sheet_df[symbol_col].values:
                            stock_data = sheet_df[sheet_df[symbol_col] == symbol].iloc[0]
                            return {
                                'support_1': stock_data.get('S1', 0),
                                'support_2': stock_data.get('S2', 0),
                                'resistance_1': stock_data.get('R1', 0),
                                'resistance_2': stock_data.get('R2', 0),
                                'rsi': stock_data.get('RSI', 50)
                            }
            return {}
        except Exception:
            return {}
    
    def _calculate_consolidation_impact_with_rotation(self, removal_candidates: List[Dict]) -> Dict:
        """
        Calculate the impact of consolidation including capital rotation strategy
        """
        try:
            # Calculate total proceeds from sales
            total_proceeds = sum(candidate['current_value'] for candidate in removal_candidates)
            
            # Identify top performing stocks to strengthen
            top_performers = self._identify_top_performers_for_rotation()
            
            # Calculate capital allocation strategy
            capital_rotation = self._calculate_capital_rotation_strategy(total_proceeds, top_performers)
            
            # Calculate portfolio impact
            current_val_col = 'Cur. val' if 'Cur. val' in self.analyzer.holdings_df.columns else 'Current Value'
            current_portfolio_value = self.analyzer.holdings_df[current_val_col].sum()
            concentration_before = self._calculate_portfolio_concentration()
            
            return {
                'total_proceeds': total_proceeds,
                'proceeds_percentage': (total_proceeds / current_portfolio_value) * 100,
                'capital_rotation': capital_rotation,
                'portfolio_impact': {
                    'holdings_reduction': f"{len(self.analyzer.holdings_df)} → {len(self.analyzer.holdings_df) - len(removal_candidates)}",
                    'concentration_improvement': f"Expected improvement in diversification",
                    'risk_reduction': f"Elimination of {len(removal_candidates)} underperforming/risky positions"
                },
                'timeline': 'Execute over 2-4 weeks for optimal market impact'
            }
            
        except Exception as e:
            return {'error': f"Error calculating consolidation impact: {str(e)}"}
    
    def _identify_top_performers_for_rotation(self) -> List[Dict]:
        """
        Identify top performing stocks that should receive additional capital
        """
        try:
            holdings_df = self.analyzer.holdings_df.copy()
            
            # Get correct column names
            symbol_col = 'Instrument' if 'Instrument' in holdings_df.columns else 'Symbol'
            current_val_col = 'Cur. val' if 'Cur. val' in holdings_df.columns else 'Current Value'
            pnl_col = 'P&L' if 'P&L' in holdings_df.columns else 'P&L %'
            
            # Calculate P&L % if not available
            if pnl_col == 'P&L' and 'P&L %' not in holdings_df.columns:
                invested_col = 'Invested' if 'Invested' in holdings_df.columns else 'Investment'
                if invested_col in holdings_df.columns:
                    holdings_df['P&L %'] = ((holdings_df[current_val_col] - holdings_df[invested_col]) / holdings_df[invested_col]) * 100
                    pnl_col = 'P&L %'
                else:
                    holdings_df['P&L %'] = 0
                    pnl_col = 'P&L %'
            
            # Score stocks for additional investment
            holdings_df['investment_score'] = 0.0
            
            # Factor 1: Strong performance (30%)
            holdings_df['perf_score'] = holdings_df[pnl_col].rank(pct=True) * 30
            
            # Factor 2: Quality fundamentals (40%) 
            quality_scores = []
            for symbol in holdings_df[symbol_col]:
                fund_score = self._get_fundamental_score(symbol)
                quality_scores.append(fund_score if fund_score else 50)
            holdings_df['quality_score'] = pd.Series(quality_scores).rank(pct=True) * 40
            
            # Factor 3: Sector underweight (20%)
            sector_scores = []
            try:
                sector_analysis = self.analyzer.analyze_sector_allocation()
                if isinstance(sector_analysis, dict):
                    sector_allocation = sector_analysis.get('sector_allocation', {})
                else:
                    sector_allocation = {}
            except:
                sector_allocation = {}
            for symbol in holdings_df[symbol_col]:
                sector = self._get_stock_sector(symbol)
                # Handle both dict and list formats for sector allocation
                try:
                    if isinstance(sector_allocation, dict):
                        sector_data = sector_allocation.get(sector, {})
                        if isinstance(sector_data, dict):
                            sector_weight = sector_data.get('weight', 0)
                        else:
                            sector_weight = 0
                    else:
                        sector_weight = 0
                except:
                    sector_weight = 0
                # Higher score for underweight sectors
                sector_score = max(0, (25 - sector_weight) * 0.8)  # Target 25% max per sector
                sector_scores.append(sector_score)
            holdings_df['sector_score'] = pd.Series(sector_scores)
            
            # Factor 4: Position size optimization (10%)
            holdings_df['size_score'] = (1 - holdings_df[current_val_col].rank(pct=True)) * 10
            
            # Calculate total investment score
            holdings_df['investment_score'] = (
                holdings_df['perf_score'] + 
                holdings_df['quality_score'] + 
                holdings_df['sector_score'] + 
                holdings_df['size_score']
            )
            
            # Get top 5-7 candidates for additional investment
            top_performers = holdings_df.nlargest(7, 'investment_score')
            
            performers = []
            for _, row in top_performers.iterrows():
                performers.append({
                    'symbol': row[symbol_col],
                    'current_value': row[current_val_col],
                    'investment_score': round(row['investment_score'], 1),
                    'sector': self._get_stock_sector(row[symbol_col]),
                    'performance': row[pnl_col],
                    'rationale': f"High quality score with {row[pnl_col]:.1f}% returns"
                })
            
            return performers
            
        except Exception as e:
            logger.error(f"Error identifying top performers: {str(e)}")
            return []
    
    def _calculate_capital_rotation_strategy(self, total_proceeds: float, top_performers: List[Dict]) -> Dict:
        """
        Calculate how to distribute proceeds among top performing stocks
        """
        try:
            if not top_performers or total_proceeds <= 0:
                return {}
            
            # Allocation strategy: 
            # - 60% to top 3 performers (equal weight)
            # - 40% to next 4 performers (proportional to score)
            
            top_3 = top_performers[:3]
            next_4 = top_performers[3:7]
            
            allocation_plan = []
            
            # Allocate 60% to top 3 (20% each)
            allocation_per_top = (total_proceeds * 0.60) / len(top_3)
            for performer in top_3:
                allocation_plan.append({
                    'symbol': performer['symbol'],
                    'allocation_amount': round(allocation_per_top, 2),
                    'allocation_percentage': 20.0,
                    'rationale': f"Top performer with {performer['performance']:.1f}% returns",
                    'new_total_value': performer['current_value'] + allocation_per_top
                })
            
            # Allocate 40% to next 4 (proportional to scores)
            if next_4:
                total_score = sum(p['investment_score'] for p in next_4)
                remaining_amount = total_proceeds * 0.40
                
                for performer in next_4:
                    weight = performer['investment_score'] / total_score
                    allocation = remaining_amount * weight
                    allocation_plan.append({
                        'symbol': performer['symbol'],
                        'allocation_amount': round(allocation, 2),
                        'allocation_percentage': round(weight * 40, 1),
                        'rationale': f"Quality stock with score {performer['investment_score']:.1f}/100",
                        'new_total_value': performer['current_value'] + allocation
                    })
            
            return {
                'strategy': 'STRENGTHEN_TOP_PERFORMERS',
                'total_amount': total_proceeds,
                'allocation_plan': allocation_plan,
                'expected_impact': 'Increased concentration in high-quality, performing stocks'
            }
            
        except Exception as e:
            return {'error': f"Error in capital rotation calculation: {str(e)}"}
    
    def _generate_sell_recommendations(self, removal_candidates: List[Dict]) -> List[Dict]:
        """
        Generate formatted sell recommendations for portfolio consolidation
        """
        sell_recommendations = []
        
        for candidate in removal_candidates:
            sell_rec = {
                'symbol': candidate['symbol'],
                'action': 'SELL',
                'type': candidate['sell_signal']['type'],
                'target_price': candidate['sell_signal']['target_price'],
                'current_price': candidate['sell_signal']['current_price'],
                'expected_proceeds': candidate['sell_signal']['expected_proceeds'],
                'urgency': candidate['sell_signal']['urgency'],
                'rationale': f"CONSOLIDATION: {candidate['removal_reasons']}",
                'category': 'PORTFOLIO_OPTIMIZATION'
            }
            sell_recommendations.append(sell_rec)
        
        return sell_recommendations
    
    def _generate_consolidation_actions_with_rotation(self, removal_candidates: List[Dict]) -> List[str]:
        """
        Generate actionable consolidation steps including capital rotation
        """
        actions = []
        
        # Sell actions
        for candidate in removal_candidates:
            urgency_text = {
                'IMMEDIATE': '📍 SELL NOW',
                'HIGH': '⚡ SELL THIS WEEK', 
                'MEDIUM': '📅 SELL OVER 2 WEEKS'
            }.get(candidate['sell_signal']['urgency'], 'SELL')
            
            actions.append(
                f"{urgency_text}: {candidate['symbol']} at ₹{candidate['sell_signal']['target_price']} "
                f"(Expected: ₹{candidate['current_value']:,.0f}) - {candidate['removal_reasons']}"
            )
        
        # Capital rotation summary
        total_proceeds = sum(c['current_value'] for c in removal_candidates)
        actions.append(f"💰 TOTAL PROCEEDS: ₹{total_proceeds:,.0f}")
        actions.append(f"🔄 ROTATE CAPITAL: Strengthen top {min(7, len(removal_candidates))} performing stocks")
        actions.append(f"🎯 TARGET: Optimize portfolio to {self.target_max_stocks} high-quality holdings")
        
        return actions
    
    def _calculate_portfolio_concentration(self) -> float:
        """Calculate current portfolio concentration"""
        try:
            current_val_col = 'Cur. val' if 'Cur. val' in self.analyzer.holdings_df.columns else 'Current Value'
            total_value = self.analyzer.holdings_df[current_val_col].sum()
            top_5_value = self.analyzer.holdings_df.nlargest(5, current_val_col)[current_val_col].sum()
            return (top_5_value / total_value) * 100
        except Exception:
            return 0.0
    
    def _get_removal_priority(self, score: float) -> str:
        """Convert removal score to priority level"""
        if score >= 80:
            return 'HIGH'
        elif score >= 60:
            return 'MEDIUM' 
        else:
            return 'LOW'
        speculative_sectors = ['Real Estate', 'Commodities', 'Mining', 'Oil & Gas']
        return sector in speculative_sectors