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
        self.max_single_stock_weight = 0.07  # Max 7% in single stock (Enhanced Rule)
        
        # Defence stock allocation parameters (Enhanced Rule)
        self.min_defence_allocation = 0.10  # Minimum 10% in defence stocks
        self.max_defence_allocation = 0.15  # Maximum 15% in defence stocks
        
        # Defence sectors classification
        self.defence_sectors = {
            'Defense',
            'Utilities', 
            'Consumer Defensive',
            'Consumer Staples',
            'Healthcare',
            'Real Estate Investment Trusts (REITs)',
            'Telecommunications'
        }
        
        # Defence stock keywords for identification
        self.defence_keywords = {
            'HAL', 'BEL', 'BEML', 'COCHINSHIP', 'GRSE', 'MDL', 'MIDHANI',  # Defense
            'POWERGRID', 'NTPC', 'PGCIL', 'SJVN', 'NHPC', 'IRCON',  # Utilities/Infrastructure
            'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'MARICO', 'GODREJCP',  # Consumer Staples
            'DRREDDY', 'SUNPHARMA', 'CIPLA', 'LUPIN', 'BIOCON', 'TORNTPHARM',  # Healthcare/Pharma
            'AIRTEL', 'INDUSINDBK', 'RCOM', 'IDEA'  # Telecom (some defensive characteristics)
        }
    
    def classify_stock_type(self, symbol: str, sector: str, pe_ratio: float = None, 
                           growth_rate: float = None, dividend_yield: float = None) -> str:
        """
        Classify stock as Defence, Growth, or Value based on multiple criteria
        
        Args:
            symbol: Stock symbol
            sector: Stock sector
            pe_ratio: Price-to-Earnings ratio
            growth_rate: Revenue/earnings growth rate
            dividend_yield: Dividend yield percentage
            
        Returns:
            str: 'DEFENCE', 'GROWTH', or 'VALUE'
        """
        # Check if it's a defence stock
        if (sector in self.defence_sectors or 
            symbol in self.defence_keywords or
            any(keyword in symbol for keyword in ['HAL', 'BEL', 'POWERGRID', 'NTPC'])):
            return 'DEFENCE'
        
        # Growth stock characteristics: High PE, High growth, Low dividend
        if (pe_ratio and pe_ratio > 25 and 
            growth_rate and growth_rate > 15 and 
            (dividend_yield is None or dividend_yield < 2)):
            return 'GROWTH'
        
        # Value stock characteristics: Low PE, Reasonable dividend, Mature companies
        if (pe_ratio and pe_ratio < 15 and 
            dividend_yield and dividend_yield > 2):
            return 'VALUE'
        
        # Default classification based on sector
        growth_sectors = {'Technology', 'Consumer Cyclical', 'Communication Services'}
        value_sectors = {'Financial Services', 'Basic Materials', 'Energy', 'Industrials'}
        
        if sector in growth_sectors:
            return 'GROWTH'
        elif sector in value_sectors:
            return 'VALUE'
        else:
            return 'VALUE'  # Default to value for safety
    
    def validate_portfolio_weight_limits(self, allocation_plan: List[Dict], 
                                       current_holdings_value: float) -> List[Dict]:
        """
        Validate and adjust allocations to ensure 7% weight limit per stock
        
        Args:
            allocation_plan: List of allocation dictionaries
            current_holdings_value: Current portfolio value
            
        Returns:
            List[Dict]: Adjusted allocation plan
        """
        total_portfolio_value = current_holdings_value + self.available_funds
        max_stock_value = total_portfolio_value * self.max_single_stock_weight
        
        validated_plan = []
        for allocation in allocation_plan:
            original_amount = allocation['Allocation_Amount']
            
            # Check if allocation exceeds 7% limit
            if original_amount > max_stock_value:
                # Cap the allocation at 7%
                allocation['Allocation_Amount'] = max_stock_value
                allocation['Weight_Capped'] = True
                allocation['Original_Amount'] = original_amount
                allocation['Rationale'] += f" (Capped at 7% weight limit: Rs.{max_stock_value:,.0f})"
                self.logger.info(f"Capped {allocation['Stock']} allocation from Rs.{original_amount:,.0f} to Rs.{max_stock_value:,.0f} (7% limit)")
            else:
                allocation['Weight_Capped'] = False
            
            validated_plan.append(allocation)
        
        return validated_plan

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
            
            # Enhanced Rules Implementation
            
            # Step 1: Apply 7% weight limit validation
            current_portfolio_value = allocation_analysis['total_portfolio_value']
            allocation_plan = self.validate_portfolio_weight_limits(allocation_plan, current_portfolio_value)
            
            # Step 2: Ensure defence stock allocation (10-15%)
            allocation_plan = self.ensure_defence_stock_allocation(
                allocation_plan, buy_recommendations, current_portfolio_value
            )
            
            # Step 3: Classify and balance growth vs value stocks
            allocation_plan = self.classify_and_balance_stocks(allocation_plan)
            
            # Calculate final allocation summary
            total_allocated = sum(plan['Allocation_Amount'] for plan in allocation_plan)
            
            # Analyze allocation by stock type
            defence_allocation = sum(plan['Allocation_Amount'] for plan in allocation_plan 
                                   if plan.get('Stock_Type') == 'DEFENCE')
            growth_allocation = sum(plan['Allocation_Amount'] for plan in allocation_plan 
                                  if plan.get('Stock_Type') == 'GROWTH')
            value_allocation = sum(plan['Allocation_Amount'] for plan in allocation_plan 
                                 if plan.get('Stock_Type') == 'VALUE')
            
            total_target_portfolio = current_portfolio_value + total_allocated
            
            allocation_summary = {
                'total_funds_available': self.available_funds,
                'total_allocated': total_allocated,
                'remaining_cash': self.available_funds - total_allocated,
                'allocation_efficiency': (total_allocated / self.available_funds) * 100,
                'new_sectors_count': len(set(plan['Sector'] for plan in allocation_plan if plan['Action_Type'] == 'NEW_SECTOR')),
                'total_stocks_to_add': len(allocation_plan),
                'defence_allocation': defence_allocation,
                'defence_percentage': (defence_allocation / total_target_portfolio) * 100,
                'growth_allocation': growth_allocation,
                'growth_percentage': (growth_allocation / total_target_portfolio) * 100,
                'value_allocation': value_allocation,
                'value_percentage': (value_allocation / total_target_portfolio) * 100,
                'max_single_stock_weight': max((plan['Allocation_Amount'] / total_target_portfolio) * 100 
                                              for plan in allocation_plan) if allocation_plan else 0,
                'weight_cap_violations': sum(1 for plan in allocation_plan if plan.get('Weight_Capped', False))
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
    
    def ensure_defence_stock_allocation(self, allocation_plan: List[Dict], 
                                      buy_recommendations: List[Dict], 
                                      current_portfolio_value: float) -> List[Dict]:
        """
        Ensure 10-15% of portfolio is allocated to defence stocks
        
        Args:
            allocation_plan: Current allocation plan
            buy_recommendations: Available buy recommendations
            current_portfolio_value: Current portfolio value
            
        Returns:
            List[Dict]: Updated allocation plan with defence stocks
        """
        try:
            total_target_value = current_portfolio_value + self.available_funds
            min_defence_value = total_target_value * self.min_defence_allocation
            max_defence_value = total_target_value * self.max_defence_allocation
            
            # Calculate current defence allocation in plan
            current_defence_allocation = sum(
                plan['Allocation_Amount'] for plan in allocation_plan 
                if self.classify_stock_type(plan['Stock'], plan['Sector']) == 'DEFENCE'
            )
            
            # Add defence classification to existing plan
            for plan in allocation_plan:
                plan['Stock_Type'] = self.classify_stock_type(plan['Stock'], plan['Sector'])
            
            # Check if we need more defence stocks
            defence_gap = min_defence_value - current_defence_allocation
            
            if defence_gap > self.min_position_size:
                # Find available defence stocks in recommendations
                defence_recommendations = [
                    stock for stock in buy_recommendations 
                    if self.classify_stock_type(stock.get('Symbol', ''), stock.get('Sector', '')) == 'DEFENCE'
                ]
                
                # Sort by score and add defence stocks
                defence_recommendations.sort(key=lambda x: x.get('Score', 0), reverse=True)
                
                remaining_defence_needed = min(defence_gap, max_defence_value - current_defence_allocation)
                
                for defence_stock in defence_recommendations[:3]:  # Max 3 defence stocks
                    if remaining_defence_needed < self.min_position_size:
                        break
                    
                    # Check if already in plan
                    if any(plan['Stock'] == defence_stock.get('Symbol') for plan in allocation_plan):
                        continue
                    
                    suggested_amount = min(
                        remaining_defence_needed / 2,  # Split among available defence stocks
                        total_target_value * self.max_single_stock_weight,  # 7% limit
                        self.max_position_size
                    )
                    
                    if suggested_amount >= self.min_position_size:
                        allocation_plan.append({
                            'Stock': defence_stock.get('Symbol', 'Unknown'),
                            'Company': defence_stock.get('Company', 'Unknown'),
                            'Sector': defence_stock.get('Sector', 'Unknown'),
                            'Allocation_Amount': suggested_amount,
                            'Priority': 'HIGH',
                            'Action_Type': 'DEFENCE_ALLOCATION',
                            'Rationale': f"Defence stock for portfolio stability (Min 10% rule)",
                            'Score': defence_stock.get('Score', 0),
                            'Current_Price': defence_stock.get('Current_Price', 0),
                            'Stock_Type': 'DEFENCE',
                            'Weight_Capped': False
                        })
                        remaining_defence_needed -= suggested_amount
                        
                        self.logger.info(f"Added defence stock {defence_stock.get('Symbol')} with Rs.{suggested_amount:,.0f}")
            
            return allocation_plan
            
        except Exception as e:
            self.logger.error(f"Error ensuring defence stock allocation: {str(e)}")
            return allocation_plan
    
    def classify_and_balance_stocks(self, allocation_plan: List[Dict]) -> List[Dict]:
        """
        Classify stocks and ensure balanced growth/value allocation
        
        Args:
            allocation_plan: Current allocation plan
            
        Returns:
            List[Dict]: Updated allocation plan with stock classifications
        """
        try:
            # Classify any remaining stocks that don't have classification
            for plan in allocation_plan:
                if 'Stock_Type' not in plan or not plan['Stock_Type']:
                    plan['Stock_Type'] = self.classify_stock_type(
                        plan['Stock'], 
                        plan['Sector']
                    )
            
            # Log classification summary
            type_summary = {}
            for plan in allocation_plan:
                stock_type = plan['Stock_Type']
                type_summary[stock_type] = type_summary.get(stock_type, 0) + plan['Allocation_Amount']
            
            total_allocation = sum(type_summary.values())
            if total_allocation > 0:
                for stock_type, amount in type_summary.items():
                    percentage = (amount / total_allocation) * 100
                    self.logger.info(f"{stock_type} stocks: Rs.{amount:,.0f} ({percentage:.1f}%)")
            
            return allocation_plan
            
        except Exception as e:
            self.logger.error(f"Error classifying and balancing stocks: {str(e)}")
            return allocation_plan
    
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