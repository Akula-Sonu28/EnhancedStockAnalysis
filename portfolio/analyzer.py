"""
Portfolio Analyzer - Core Analysis Engine

This module provides the main portfolio analysis functionality including:
- Holdings data processing
- Enhanced Stock Report integration  
- Performance calculations
- Risk analysis
- Sector allocation analysis
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

# Import existing project modules
import sys
sys.path.append('..')
from config import AnalysisConfig

class PortfolioAnalyzer:
    """Main Portfolio Analysis Engine"""
    
    def __init__(self, available_funds: float = 0.0, config_file: str = 'config.py'):
        """
        Initialize Portfolio Analyzer
        
        Args:
            available_funds: Available cash for new investments
            config_file: Configuration file path
        """
        self.available_funds = available_funds
        self.config = AnalysisConfig()
        self.logger = self._setup_logging()
        self.holdings_df = None
        self.enhanced_report_df = None
        self.sector_data = None
        self.portfolio_metrics = {}
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for portfolio analysis"""
        logger = logging.getLogger('PortfolioAnalyzer')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def load_portfolio_data(self, holdings_pattern: str = None, report_pattern: str = None) -> bool:
        """
        Load portfolio holdings and enhanced stock report data
        
        Args:
            holdings_pattern: Pattern to find holdings CSV file
            report_pattern: Pattern to find Enhanced Stock Report Excel file
            
        Returns:
            bool: True if data loaded successfully
        """
        try:
            # Auto-detect latest files if patterns not provided
            if holdings_pattern is None:
                holdings_pattern = "Holding/holdings*.csv"
            if report_pattern is None:
                report_pattern = "reports/Enhanced_Stock_Report_*.xlsx"
                
            # Find latest holdings file
            holdings_files = glob.glob(holdings_pattern)
            if not holdings_files:
                self.logger.error(f"No holdings files found with pattern: {holdings_pattern}")
                return False
                
            latest_holdings = max(holdings_files, key=os.path.getctime)
            self.holdings_file = latest_holdings  # Store file path for executor
            self.logger.info(f"Loading holdings from: {latest_holdings}")
            
            # Load holdings data
            self.holdings_df = pd.read_csv(latest_holdings)
            self.holdings_df = self._clean_holdings_data(self.holdings_df)
            
            # Find latest Enhanced Stock Report
            report_files = glob.glob(report_pattern)
            if not report_files:
                self.logger.error(f"No Enhanced Stock Report files found with pattern: {report_pattern}")
                return False
                
            latest_report = max(report_files, key=os.path.getctime)
            self.logger.info(f"Loading Enhanced Stock Report from: {latest_report}")
            
            # Load Enhanced Stock Report (multiple sheets)
            excel_file = pd.ExcelFile(latest_report)
            self.enhanced_report_df = {}
            
            for sheet_name in excel_file.sheet_names:
                self.enhanced_report_df[sheet_name] = pd.read_excel(latest_report, sheet_name=sheet_name)
                
            self.logger.info(f"Loaded {len(self.holdings_df)} holdings and {len(excel_file.sheet_names)} report sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading portfolio data: {str(e)}")
            return False
    
    def _clean_holdings_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize holdings data"""
        try:
            # Remove empty rows and columns
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            # Clean column names
            df.columns = df.columns.str.strip().str.replace('"', '')
            
            # Convert numeric columns
            numeric_columns = ['Qty.', 'Avg. cost', 'LTP', 'Invested', 'Cur. val', 'P&L', 'Net chg.', 'Day chg.']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Clean instrument names
            if 'Instrument' in df.columns:
                df['Instrument'] = df['Instrument'].str.strip().str.replace('"', '')
                
            # Calculate additional metrics
            df['Return_Pct'] = (df['P&L'] / df['Invested'] * 100).round(2)
            df['Weight'] = (df['Cur. val'] / df['Cur. val'].sum() * 100).round(2)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error cleaning holdings data: {str(e)}")
            return df
    
    def calculate_portfolio_performance(self) -> Dict:
        """Calculate comprehensive portfolio performance metrics with caching"""
        if self.holdings_df is None:
            self.logger.error("Holdings data not loaded")
            return {}
        
        # Return cached result if already calculated
        if hasattr(self, '_cached_portfolio_metrics') and self._cached_portfolio_metrics:
            return self._cached_portfolio_metrics
            
        try:
            metrics = {}
            
            # Basic P&L Metrics
            total_invested = self.holdings_df['Invested'].sum()
            total_current_value = self.holdings_df['Cur. val'].sum()
            total_pnl = self.holdings_df['P&L'].sum()
            
            metrics['total_invested'] = total_invested
            metrics['current_value'] = total_current_value
            metrics['total_pnl'] = total_pnl
            metrics['total_return_pct'] = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            # Individual Stock Performance
            metrics['top_performers'] = self.holdings_df.nlargest(5, 'Return_Pct')[['Instrument', 'Return_Pct', 'P&L']].to_dict('records')
            metrics['worst_performers'] = self.holdings_df.nsmallest(5, 'Return_Pct')[['Instrument', 'Return_Pct', 'P&L']].to_dict('records')
            
            # Risk Metrics
            returns = self.holdings_df['Return_Pct'].dropna()
            if len(returns) > 0:
                metrics['portfolio_volatility'] = returns.std()
                metrics['sharpe_estimate'] = returns.mean() / returns.std() if returns.std() > 0 else 0
            
            # Concentration Analysis
            metrics['top_5_concentration'] = self.holdings_df.nlargest(5, 'Weight')['Weight'].sum()
            metrics['number_of_holdings'] = len(self.holdings_df)
            
            # Day Change Analysis
            day_pnl = (self.holdings_df['Day chg.'] * self.holdings_df['Cur. val'] / 100).sum()
            metrics['day_pnl'] = day_pnl
            metrics['day_return_pct'] = (day_pnl / total_current_value * 100) if total_current_value > 0 else 0
            
            self.portfolio_metrics = metrics
            # Cache the results to avoid repeated calculations
            self._cached_portfolio_metrics = metrics
            self.logger.info("Portfolio performance metrics calculated successfully")
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio performance: {str(e)}")
            return {}
    
    def clear_performance_cache(self):
        """Clear cached performance metrics to force recalculation"""
        if hasattr(self, '_cached_portfolio_metrics'):
            self._cached_portfolio_metrics = None
    
    def analyze_sector_allocation(self) -> Dict:
        """Analyze sector allocation and concentration"""
        if self.enhanced_report_df is None or 'Complete Data' not in self.enhanced_report_df:
            self.logger.warning("Enhanced report data not available for sector analysis")
            return {}
            
        try:
            # Get sector data from Enhanced Stock Report
            complete_data = self.enhanced_report_df['Complete Data']
            sector_mapping = dict(zip(complete_data['symbol'], complete_data['sector']))
            
            # Map sectors to holdings
            self.holdings_df['Sector'] = self.holdings_df['Instrument'].map(sector_mapping)
            self.holdings_df['Sector'] = self.holdings_df['Sector'].fillna('Unknown')
            
            # Calculate sector allocation
            sector_allocation = self.holdings_df.groupby('Sector').agg({
                'Cur. val': 'sum',
                'P&L': 'sum',
                'Invested': 'sum'
            }).reset_index()
            
            sector_allocation['Weight_Pct'] = (sector_allocation['Cur. val'] / sector_allocation['Cur. val'].sum() * 100).round(2)
            sector_allocation['Return_Pct'] = (sector_allocation['P&L'] / sector_allocation['Invested'] * 100).round(2)
            
            sector_metrics = {
                'sector_allocation': sector_allocation.to_dict('records'),
                'most_allocated_sector': sector_allocation.loc[sector_allocation['Weight_Pct'].idxmax(), 'Sector'],
                'best_performing_sector': sector_allocation.loc[sector_allocation['Return_Pct'].idxmax(), 'Sector'],
                'worst_performing_sector': sector_allocation.loc[sector_allocation['Return_Pct'].idxmin(), 'Sector'],
                'sector_concentration_risk': sector_allocation['Weight_Pct'].max()
            }
            
            self.sector_data = sector_allocation
            return sector_metrics
            
        except Exception as e:
            self.logger.error(f"Error analyzing sector allocation: {str(e)}")
            return {}
    
    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary"""
        summary = {}
        
        # Load data if not already loaded
        if self.holdings_df is None:
            if not self.load_portfolio_data():
                return {"error": "Failed to load portfolio data"}
        
        # Calculate metrics
        performance = self.calculate_portfolio_performance()
        sector_analysis = self.analyze_sector_allocation()
        
        summary.update(performance)
        summary.update(sector_analysis)
        summary['available_funds'] = self.available_funds
        summary['analysis_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return summary
    
    def get_holdings_with_enhanced_data(self) -> pd.DataFrame:
        """Merge holdings with Enhanced Stock Report data"""
        if self.holdings_df is None or self.enhanced_report_df is None:
            return pd.DataFrame()
            
        try:
            # Get complete data sheet
            complete_data = self.enhanced_report_df.get('Complete Data', pd.DataFrame())
            if complete_data.empty:
                return self.holdings_df
                
            # Merge holdings with enhanced data
            merged_df = self.holdings_df.merge(
                complete_data, 
                left_on='Instrument', 
                right_on='symbol', 
                how='left'
            )
            
            return merged_df
            
        except Exception as e:
            self.logger.error(f"Error merging holdings with enhanced data: {str(e)}")
            return self.holdings_df