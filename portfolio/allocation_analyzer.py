"""
Portfolio Allocation Analyzer - Intelligent Fund Allocation

This module provides intelligent portfolio allocation analysis that considers:
1. Current holdings and their performance
2. Available funds for allocation
3. Sector balance and diversification
4. Position sizing optimization
5. Smart rebalancing recommendations
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

class PortfolioAllocationAnalyzer:
    """
    Intelligent Portfolio Allocation Analyzer
    
    Analyzes current holdings and available funds to provide optimized
    allocation recommendations considering sector balance, position sizing,
    and portfolio optimization strategies.
    """
    
    def __init__(self, portfolio_analyzer, available_funds: float):
        """
        Initialize allocation analyzer
        
        Args:
            portfolio_analyzer: Instance of PortfolioAnalyzer
            available_funds: Available funds for allocation
        """
        self.analyzer = portfolio_analyzer
        self.available_funds = available_funds
        self.logger = logging.getLogger('AllocationAnalyzer')
        
        # Target allocation parameters
        self.target_sector_weights = {
            'Financial Services': 0.25,  # 25%
            'Technology': 0.20,          # 20%
            'Consumer Goods': 0.15,      # 15%
            'Healthcare': 0.10,          # 10%
            'Industrials': 0.10,         # 10%
            'Energy': 0.08,              # 8%
            'Basic Materials': 0.07,     # 7%
            'Utilities': 0.05            # 5%
        }
        
        self.min_position_size = 5000    # Minimum ₹5,000 per position
        self.max_position_size = 50000   # Maximum ₹50,000 per position
        self.max_single_stock_weight = 0.05  # Max 5% in single stock
        
    def analyze_current_allocation(self) -> Dict:
        """Analyze current portfolio allocation and identify gaps"""
        try:
            holdings_df = self.analyzer.holdings_df.copy()
            total_portfolio_value = holdings_df['Cur. val'].sum()
            
            # Calculate current sector allocation
            current_sector_allocation = holdings_df.groupby('Sector').agg({
                'Cur. val': 'sum',
                'Qty.': 'count'
            }).reset_index()
            
            current_sector_allocation['Current_Weight'] = (
                current_sector_allocation['Cur. val'] / total_portfolio_value
            ).round(4)
            
            current_sector_allocation['Stock_Count'] = current_sector_allocation['Qty.']
            
            # Add target weights and gaps
            allocation_analysis = []
            for _, row in current_sector_allocation.iterrows():
                sector = row['Sector']
                current_weight = row['Current_Weight']
                target_weight = self.target_sector_weights.get(sector, 0.05)  # Default 5% for unknown sectors
                
                gap = target_weight - current_weight
                gap_value = gap * (total_portfolio_value + self.available_funds)
                
                allocation_analysis.append({
                    'Sector': sector,
                    'Current_Value': row['Cur. val'],
                    'Current_Weight': current_weight,
                    'Target_Weight': target_weight,
                    'Weight_Gap': gap,
                    'Value_Gap': gap_value,
                    'Stock_Count': row['Stock_Count'],
                    'Action': 'INCREASE' if gap > 0.02 else 'DECREASE' if gap < -0.02 else 'MAINTAIN'
                })
            
            # Add missing sectors
            current_sectors = set(current_sector_allocation['Sector'])
            for sector, target_weight in self.target_sector_weights.items():
                if sector not in current_sectors:
                    gap_value = target_weight * (total_portfolio_value + self.available_funds)
                    allocation_analysis.append({
                        'Sector': sector,
                        'Current_Value': 0,
                        'Current_Weight': 0,
                        'Target_Weight': target_weight,
                        'Weight_Gap': target_weight,
                        'Value_Gap': gap_value,
                        'Stock_Count': 0,
                        'Action': 'ADD'
                    })
            
            return {
                'current_allocation': pd.DataFrame(allocation_analysis),
                'total_portfolio_value': total_portfolio_value,
                'available_funds': self.available_funds,
                'total_target_value': total_portfolio_value + self.available_funds
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing current allocation: {str(e)}")
            return {}
    
    def generate_fund_allocation_plan(self) -> Dict:
        """Generate intelligent fund allocation plan"""
        try:
            allocation_analysis = self.analyze_current_allocation()
            if not allocation_analysis:
                return {}
            
            allocation_df = allocation_analysis['current_allocation']
            total_target_value = allocation_analysis['total_target_value']
            
            # Get buy recommendations from enhanced stock report
            buy_recommendations = self._get_enhanced_buy_recommendations()
            
            # Generate allocation plan
            allocation_plan = []
            remaining_funds = self.available_funds
            
            # Priority 1: Fill missing sectors (ADD action)
            missing_sectors = allocation_df[allocation_df['Action'] == 'ADD'].copy()
            for _, sector_row in missing_sectors.iterrows():
                sector = sector_row['Sector']
                target_allocation = min(sector_row['Value_Gap'], remaining_funds * 0.3)  # Max 30% to any sector
                
                sector_stocks = [stock for stock in buy_recommendations 
                               if stock.get('Sector', '').lower() == sector.lower()][:2]  # Max 2 stocks per new sector
                
                for stock in sector_stocks:
                    if remaining_funds < self.min_position_size:
                        break
                        
                    suggested_amount = min(
                        target_allocation / len(sector_stocks),
                        self.max_position_size,
                        remaining_funds
                    )
                    
                    if suggested_amount >= self.min_position_size:
                        allocation_plan.append({
                            'Stock': stock.get('Symbol', 'Unknown'),
                            'Company': stock.get('Company', 'Unknown'),
                            'Sector': sector,
                            'Allocation_Amount': suggested_amount,
                            'Priority': 'HIGH',
                            'Action_Type': 'NEW_SECTOR',
                            'Rationale': f"Fill missing {sector} sector allocation",
                            'Score': stock.get('Score', 0),
                            'Current_Price': stock.get('Current_Price', 0)
                        })
                        remaining_funds -= suggested_amount
            
            # Priority 2: Increase underweight sectors (INCREASE action)
            underweight_sectors = allocation_df[
                (allocation_df['Action'] == 'INCREASE') & 
                (allocation_df['Weight_Gap'] > 0.02)
            ].copy().sort_values('Weight_Gap', ascending=False)
            
            for _, sector_row in underweight_sectors.iterrows():
                sector = sector_row['Sector']
                target_allocation = min(sector_row['Value_Gap'] * 0.7, remaining_funds * 0.4)  # 70% of gap, max 40% of remaining
                
                sector_stocks = [stock for stock in buy_recommendations 
                               if stock.get('Sector', '').lower() == sector.lower()][:3]  # Max 3 stocks per sector
                
                for stock in sector_stocks:
                    if remaining_funds < self.min_position_size:
                        break
                        
                    suggested_amount = min(
                        target_allocation / len(sector_stocks),
                        self.max_position_size,
                        remaining_funds
                    )
                    
                    if suggested_amount >= self.min_position_size:
                        allocation_plan.append({
                            'Stock': stock.get('Symbol', 'Unknown'),
                            'Company': stock.get('Company', 'Unknown'),
                            'Sector': sector,
                            'Allocation_Amount': suggested_amount,
                            'Priority': 'MEDIUM',
                            'Action_Type': 'INCREASE_SECTOR',
                            'Rationale': f"Increase {sector} allocation (current: {sector_row['Current_Weight']:.1%}, target: {sector_row['Target_Weight']:.1%})",
                            'Score': stock.get('Score', 0),
                            'Current_Price': stock.get('Current_Price', 0)
                        })
                        remaining_funds -= suggested_amount
            
            # Priority 3: Best remaining opportunities
            if remaining_funds >= self.min_position_size:
                remaining_stocks = [stock for stock in buy_recommendations[:10]  # Top 10 stocks
                                  if stock.get('Symbol') not in [plan['Stock'] for plan in allocation_plan]]
                
                for stock in remaining_stocks:
                    if remaining_funds < self.min_position_size:
                        break
                        
                    suggested_amount = min(
                        remaining_funds / max(1, len(remaining_stocks) - remaining_stocks.index(stock)),
                        self.max_position_size,
                        remaining_funds
                    )
                    
                    if suggested_amount >= self.min_position_size:
                        allocation_plan.append({
                            'Stock': stock.get('Symbol', 'Unknown'),
                            'Company': stock.get('Company', 'Unknown'),
                            'Sector': stock.get('Sector', 'Unknown'),
                            'Allocation_Amount': suggested_amount,
                            'Priority': 'LOW',
                            'Action_Type': 'OPPORTUNISTIC',
                            'Rationale': f"High-quality opportunity (Score: {stock.get('Score', 0)})",
                            'Score': stock.get('Score', 0),
                            'Current_Price': stock.get('Current_Price', 0)
                        })
                        remaining_funds -= suggested_amount
            
            # Calculate allocation summary
            total_allocated = sum(plan['Allocation_Amount'] for plan in allocation_plan)
            allocation_summary = {
                'total_funds_available': self.available_funds,
                'total_allocated': total_allocated,
                'remaining_cash': self.available_funds - total_allocated,
                'allocation_efficiency': (total_allocated / self.available_funds) * 100,
                'new_sectors_count': len(set(plan['Sector'] for plan in allocation_plan if plan['Action_Type'] == 'NEW_SECTOR')),
                'total_stocks_to_add': len(allocation_plan)
            }
            
            return {
                'allocation_plan': pd.DataFrame(allocation_plan),
                'allocation_summary': allocation_summary,
                'sector_analysis': allocation_df
            }
            
        except Exception as e:
            self.logger.error(f"Error generating fund allocation plan: {str(e)}")
            return {}
    
    def _get_enhanced_buy_recommendations(self) -> List[Dict]:
        """Get enhanced buy recommendations from stock analysis"""
        try:
            buy_recommendations = []
            
            # Try to get from enhanced report if available
            if hasattr(self.analyzer, 'enhanced_report_df') and self.analyzer.enhanced_report_df:
                for sheet_name, sheet_df in self.analyzer.enhanced_report_df.items():
                    if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
                        # Look for buy recommendations in sheets
                        if 'Symbol' in sheet_df.columns and 'Recommendation' in sheet_df.columns:
                            buy_stocks = sheet_df[
                                sheet_df['Recommendation'].str.contains('BUY', na=False, case=False)
                            ].copy()
                            
                            for _, row in buy_stocks.iterrows():
                                buy_recommendations.append({
                                    'Symbol': row.get('Symbol', ''),
                                    'Company': row.get('Company', row.get('Symbol', '')),
                                    'Sector': row.get('Sector', 'Unknown'),
                                    'Score': row.get('Final_Score', row.get('Score', 0)),
                                    'Current_Price': row.get('Current_Price', row.get('Price', 0)),
                                    'Recommendation': row.get('Recommendation', ''),
                                    'Source_Sheet': sheet_name
                                })
            
            # Remove duplicates and sort by score
            unique_recommendations = {}
            for rec in buy_recommendations:
                symbol = rec['Symbol']
                if symbol not in unique_recommendations or rec['Score'] > unique_recommendations[symbol]['Score']:
                    unique_recommendations[symbol] = rec
            
            sorted_recommendations = sorted(
                unique_recommendations.values(), 
                key=lambda x: x['Score'], 
                reverse=True
            )
            
            return sorted_recommendations[:20]  # Return top 20
            
        except Exception as e:
            self.logger.error(f"Error getting buy recommendations: {str(e)}")
            return []
    
    def analyze_position_sizing(self) -> pd.DataFrame:
        """Analyze current position sizing and suggest optimizations"""
        try:
            holdings_df = self.analyzer.holdings_df.copy()
            total_value = holdings_df['Cur. val'].sum()
            
            position_analysis = []
            for _, row in holdings_df.iterrows():
                current_weight = row['Cur. val'] / total_value
                position_size_category = 'SMALL' if row['Cur. val'] < 10000 else 'MEDIUM' if row['Cur. val'] < 30000 else 'LARGE'
                
                # Suggest action based on weight and performance
                if current_weight > self.max_single_stock_weight:
                    action = 'REDUCE'
                elif row['Cur. val'] < self.min_position_size:
                    action = 'INCREASE_OR_EXIT'
                else:
                    action = 'MAINTAIN'
                
                position_analysis.append({
                    'Symbol': row['Instrument'],
                    'Current_Value': row['Cur. val'],
                    'Current_Weight': current_weight,
                    'Position_Size': position_size_category,
                    'P&L': row.get('P&L', 0),
                    'P&L_Percent': row.get('Net chg %', 0),
                    'Action': action,
                    'Target_Weight': min(current_weight, self.max_single_stock_weight),
                    'Suggested_Value': min(row['Cur. val'], total_value * self.max_single_stock_weight)
                })
            
            return pd.DataFrame(position_analysis)
            
        except Exception as e:
            self.logger.error(f"Error analyzing position sizing: {str(e)}")
            return pd.DataFrame()