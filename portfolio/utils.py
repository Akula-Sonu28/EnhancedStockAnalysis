"""
Portfolio Utils - Utility Functions and Helpers

This module provides utility functions for portfolio analysis including:
- File management helpers
- Data validation
- Common calculations
- Configuration management
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union
import logging

class PortfolioUtils:
    """Utility functions for portfolio analysis"""
    
    @staticmethod
    def find_latest_file(pattern: str, base_path: str = ".") -> Optional[str]:
        """
        Find the latest file matching a pattern
        
        Args:
            pattern: Glob pattern to match files
            base_path: Base directory to search in
            
        Returns:
            str: Path to latest file or None if not found
        """
        try:
            search_pattern = os.path.join(base_path, pattern)
            files = glob.glob(search_pattern)
            
            if not files:
                return None
                
            # Return file with latest modification time
            latest_file = max(files, key=os.path.getctime)
            return latest_file
            
        except Exception as e:
            logging.error(f"Error finding latest file with pattern {pattern}: {str(e)}")
            return None
    
    @staticmethod
    def validate_holdings_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validate holdings DataFrame structure and data
        
        Args:
            df: Holdings DataFrame to validate
            
        Returns:
            Tuple: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required columns
        required_columns = ['Instrument', 'Qty.', 'Avg. cost', 'LTP', 'Invested', 'Cur. val', 'P&L']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
        
        # Check for empty data
        if df.empty:
            errors.append("Holdings data is empty")
        
        # Check for negative quantities
        if 'Qty.' in df.columns:
            negative_qty = df[df['Qty.'] < 0]
            if not negative_qty.empty:
                errors.append(f"Found negative quantities for: {negative_qty['Instrument'].tolist()}")
        
        # Check for missing instrument names
        if 'Instrument' in df.columns:
            missing_instruments = df[df['Instrument'].isna() | (df['Instrument'] == '')]
            if not missing_instruments.empty:
                errors.append(f"Found {len(missing_instruments)} rows with missing instrument names")
        
        # Check for unrealistic P&L percentages (> 1000% or < -100%)
        if 'Return_Pct' in df.columns:
            extreme_returns = df[(df['Return_Pct'] > 1000) | (df['Return_Pct'] < -100)]
            if not extreme_returns.empty:
                errors.append(f"Found extreme returns: {extreme_returns[['Instrument', 'Return_Pct']].to_dict('records')}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    @staticmethod
    def validate_enhanced_report_data(report_dict: Dict[str, pd.DataFrame]) -> Tuple[bool, List[str]]:
        """
        Validate Enhanced Stock Report data structure
        
        Args:
            report_dict: Dictionary of DataFrames from Excel sheets
            
        Returns:
            Tuple: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for required sheets
        required_sheets = ['Complete Data']
        missing_sheets = [sheet for sheet in required_sheets if sheet not in report_dict]
        
        if missing_sheets:
            errors.append(f"Missing required sheets: {missing_sheets}")
        
        # Validate Complete Data sheet if exists
        if 'Complete Data' in report_dict:
            complete_data = report_dict['Complete Data']
            required_columns = ['symbol', 'sector', 'current_price']
            missing_columns = [col for col in required_columns if col not in complete_data.columns]
            
            if missing_columns:
                errors.append(f"Missing columns in Complete Data sheet: {missing_columns}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    @staticmethod
    def calculate_portfolio_beta(holdings_df: pd.DataFrame, market_return: float = 0.12) -> float:
        """
        Calculate portfolio beta (simplified estimation)
        
        Args:
            holdings_df: Holdings DataFrame with weights
            market_return: Expected market return (default 12%)
            
        Returns:
            float: Estimated portfolio beta
        """
        try:
            if 'Weight' not in holdings_df.columns or 'Return_Pct' not in holdings_df.columns:
                return 1.0  # Default beta
            
            # Simplified beta calculation based on stock performance vs market
            # In reality, this would require historical price data
            weighted_returns = (holdings_df['Weight'] * holdings_df['Return_Pct'] / 100).sum()
            portfolio_volatility = holdings_df['Return_Pct'].std()
            
            # Estimate beta based on portfolio volatility vs market
            market_volatility = 15.0  # Assumed market volatility of 15%
            estimated_beta = portfolio_volatility / market_volatility
            
            return max(0.1, min(2.0, estimated_beta))  # Clamp between 0.1 and 2.0
            
        except Exception as e:
            logging.error(f"Error calculating portfolio beta: {str(e)}")
            return 1.0
    
    @staticmethod
    def calculate_sector_hhi(sector_weights: List[float]) -> float:
        """
        Calculate Herfindahl-Hirschman Index for sector concentration
        
        Args:
            sector_weights: List of sector weights as percentages
            
        Returns:
            float: HHI score (higher = more concentrated)
        """
        try:
            # Convert percentages to decimals and square them
            hhi = sum((weight / 100) ** 2 for weight in sector_weights)
            return hhi
            
        except Exception as e:
            logging.error(f"Error calculating HHI: {str(e)}")
            return 0.0
    
    @staticmethod
    def format_currency(amount: float, currency: str = "₹") -> str:
        """
        Format amount as currency with proper comma separation
        
        Args:
            amount: Amount to format
            currency: Currency symbol
            
        Returns:
            str: Formatted currency string
        """
        try:
            if abs(amount) >= 10000000:  # 1 crore
                return f"{currency}{amount/10000000:.1f}Cr"
            elif abs(amount) >= 100000:  # 1 lakh
                return f"{currency}{amount/100000:.1f}L"
            else:
                return f"{currency}{amount:,.0f}"
                
        except Exception:
            return f"{currency}0"
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Format percentage with proper sign and decimals
        
        Args:
            value: Percentage value
            decimals: Number of decimal places
            
        Returns:
            str: Formatted percentage string
        """
        try:
            return f"{value:+.{decimals}f}%"
        except Exception:
            return "0.0%"
    
    @staticmethod
    def calculate_position_size(available_funds: float, target_allocation: float, 
                              current_price: float, min_shares: int = 1) -> Tuple[int, float]:
        """
        Calculate optimal position size for new investment
        
        Args:
            available_funds: Total available funds
            target_allocation: Target allocation as percentage (0-100)
            current_price: Current stock price
            min_shares: Minimum number of shares to buy
            
        Returns:
            Tuple: (number_of_shares, investment_amount)
        """
        try:
            target_amount = available_funds * (target_allocation / 100)
            shares = max(min_shares, int(target_amount / current_price))
            investment_amount = shares * current_price
            
            # Ensure we don't exceed available funds
            if investment_amount > available_funds:
                shares = int(available_funds / current_price)
                investment_amount = shares * current_price
            
            return shares, investment_amount
            
        except Exception as e:
            logging.error(f"Error calculating position size: {str(e)}")
            return 0, 0.0
    
    @staticmethod
    def generate_rebalancing_plan(current_allocation: Dict[str, float], 
                                target_allocation: Dict[str, float],
                                total_value: float,
                                tolerance: float = 2.0) -> Dict[str, Dict]:
        """
        Generate rebalancing plan based on current vs target allocation
        
        Args:
            current_allocation: Current sector/stock allocation percentages
            target_allocation: Target allocation percentages
            total_value: Total portfolio value
            tolerance: Allocation tolerance in percentage points
            
        Returns:
            Dict: Rebalancing recommendations
        """
        try:
            rebalancing_plan = {}
            
            for sector, target_pct in target_allocation.items():
                current_pct = current_allocation.get(sector, 0.0)
                difference = current_pct - target_pct
                
                if abs(difference) > tolerance:
                    action = "REDUCE" if difference > 0 else "INCREASE"
                    amount = abs(difference) / 100 * total_value
                    
                    rebalancing_plan[sector] = {
                        'action': action,
                        'current_allocation': current_pct,
                        'target_allocation': target_pct,
                        'difference_pct': difference,
                        'amount_to_adjust': amount,
                        'priority': 'HIGH' if abs(difference) > tolerance * 2 else 'MEDIUM'
                    }
            
            return rebalancing_plan
            
        except Exception as e:
            logging.error(f"Error generating rebalancing plan: {str(e)}")
            return {}
    
    @staticmethod
    def calculate_risk_metrics(returns: pd.Series) -> Dict[str, float]:
        """
        Calculate various risk metrics from returns series
        
        Args:
            returns: Series of returns (as percentages)
            
        Returns:
            Dict: Various risk metrics
        """
        try:
            if returns.empty or returns.isna().all():
                return {}
            
            risk_metrics = {
                'volatility': returns.std(),
                'downside_deviation': returns[returns < 0].std(),
                'max_drawdown': (returns.cumsum().expanding().max() - returns.cumsum()).max(),
                'var_95': returns.quantile(0.05),  # Value at Risk (95%)
                'skewness': returns.skew(),
                'kurtosis': returns.kurtosis(),
                'sortino_ratio': returns.mean() / returns[returns < 0].std() if len(returns[returns < 0]) > 0 else 0
            }
            
            return risk_metrics
            
        except Exception as e:
            logging.error(f"Error calculating risk metrics: {str(e)}")
            return {}
    
    @staticmethod
    def create_backup(filepath: str) -> bool:
        """
        Create backup of important file
        
        Args:
            filepath: Path to file to backup
            
        Returns:
            bool: True if backup successful
        """
        try:
            if not os.path.exists(filepath):
                return False
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{filepath}.backup_{timestamp}"
            
            import shutil
            shutil.copy2(filepath, backup_name)
            
            logging.info(f"Backup created: {backup_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error creating backup: {str(e)}")
            return False
    
    @staticmethod
    def merge_dataframes_safely(df1: pd.DataFrame, df2: pd.DataFrame, 
                               on: Union[str, List[str]], how: str = 'left') -> pd.DataFrame:
        """
        Safely merge two DataFrames with error handling
        
        Args:
            df1: First DataFrame
            df2: Second DataFrame  
            on: Column(s) to merge on
            how: Type of merge
            
        Returns:
            pd.DataFrame: Merged DataFrame or df1 if merge fails
        """
        try:
            if df1.empty or df2.empty:
                return df1
            
            # Check if merge columns exist
            merge_cols = [on] if isinstance(on, str) else on
            
            for col in merge_cols:
                if col not in df1.columns or col not in df2.columns:
                    logging.warning(f"Merge column '{col}' not found in both DataFrames")
                    return df1
            
            merged_df = df1.merge(df2, on=on, how=how)
            return merged_df
            
        except Exception as e:
            logging.error(f"Error merging DataFrames: {str(e)}")
            return df1