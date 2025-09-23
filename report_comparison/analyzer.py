#!/usr/bin/env python3
"""
Enhanced Stock Report Comparison Analyzer
=========================================

This module compares two Enhanced Stock Reports to identify:
- Stock ranking changes
- Performance metric differences
- Market trends and sector rotation
- Buy/sell signal changes
- Risk level variations

Author: Enhanced Stock Analysis System
Version: 1.0.0
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

class ReportComparator:
    """Compare two Enhanced Stock Reports and generate insights"""
    
    def __init__(self):
        self.reports_dir = "reports"
        self.comparison_dir = "reports/comparisons"
        os.makedirs(self.comparison_dir, exist_ok=True)
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def get_latest_reports(self, count: int = 2) -> List[str]:
        """Get the latest Enhanced Stock Reports"""
        pattern = os.path.join(self.reports_dir, "Enhanced_Stock_Report_*.xlsx")
        files = glob.glob(pattern)
        
        if not files:
            raise FileNotFoundError("No Enhanced Stock Reports found!")
            
        # Sort by modification time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        
        if len(files) < count:
            raise ValueError(f"Need at least {count} reports for comparison. Found {len(files)}")
            
        return files[:count]
    
    def load_report_data(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Load data from Enhanced Stock Report Excel file"""
        try:
            # Read all sheets
            excel_data = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
            
            # Use print instead of logger to avoid Unicode issues on Windows
            print(f"📊 Loaded report: {os.path.basename(file_path)}")
            print(f"📋 Available sheets: {len(excel_data.keys())} sheets found")
            
            return excel_data
            
        except Exception as e:
            self.logger.error(f"Error loading {file_path}: {e}")
            raise
    
    def compare_stock_rankings(self, old_data: Dict, new_data: Dict) -> pd.DataFrame:
        """Compare stock rankings between two reports"""
        try:
            # Priority order for sheet selection (comprehensive to specific)
            sheet_priority = [
                'Complete Data',     # Full dataset (200 stocks) - BEST for comprehensive analysis
                'Undervalued',      # Undervalued stocks (30 stocks) - Good for value investing
                'Trading Plans',    # Top trading candidates (20 stocks) - Current default
                'Summary', 'Top_Stocks', 'Analysis_Results', 'Main', 'Stock_Analysis'  # Fallbacks
            ]
            
            old_summary = None
            new_summary = None
            selected_sheet = None
            
            # Try sheets in priority order
            for sheet_name in sheet_priority:
                if sheet_name in old_data and sheet_name in new_data:
                    old_df = old_data[sheet_name]
                    new_df = new_data[sheet_name]
                    
                    # Check if sheet has stock data (Symbol or symbol column)
                    if hasattr(old_df, 'columns') and hasattr(new_df, 'columns'):
                        old_has_symbol = 'Symbol' in old_df.columns or 'symbol' in old_df.columns
                        new_has_symbol = 'Symbol' in new_df.columns or 'symbol' in new_df.columns
                        
                        if old_has_symbol and new_has_symbol and len(old_df) > 0 and len(new_df) > 0:
                            old_summary = old_df.copy()
                            new_summary = new_df.copy()
                            selected_sheet = sheet_name
                            break
            
            # Fallback: Find any sheet with Symbol/symbol column
            if old_summary is None:
                for sheet_name, df in old_data.items():
                    if hasattr(df, 'columns') and ('Symbol' in df.columns or 'symbol' in df.columns) and len(df) > 0:
                        if sheet_name in new_data:
                            new_df = new_data[sheet_name]
                            if hasattr(new_df, 'columns') and ('Symbol' in new_df.columns or 'symbol' in new_df.columns):
                                old_summary = df.copy()
                                new_summary = new_df.copy()
                                selected_sheet = sheet_name
                                break
            
            if old_summary is None or new_summary is None:
                raise ValueError("Could not find suitable data sheets for comparison")
            
            # Standardize column names (handle both 'Symbol' and 'symbol')
            symbol_col_old = 'Symbol' if 'Symbol' in old_summary.columns else 'symbol'
            symbol_col_new = 'Symbol' if 'Symbol' in new_summary.columns else 'symbol'
            
            if symbol_col_old not in old_summary.columns or symbol_col_new not in new_summary.columns:
                raise ValueError("Symbol column not found in data")
            
            # Rename to standard 'Symbol' for consistency
            if symbol_col_old == 'symbol':
                old_summary = old_summary.rename(columns={'symbol': 'Symbol'})
            if symbol_col_new == 'symbol':
                new_summary = new_summary.rename(columns={'symbol': 'Symbol'})
            
            # Add ranking based on index position
            old_summary['Old_Rank'] = old_summary.index + 1
            new_summary['New_Rank'] = new_summary.index + 1
            
            # Merge on Symbol
            comparison = pd.merge(
                old_summary[['Symbol', 'Old_Rank'] + [col for col in old_summary.columns if col not in ['Symbol', 'Old_Rank']]],
                new_summary[['Symbol', 'New_Rank'] + [col for col in new_summary.columns if col not in ['Symbol', 'New_Rank']]],
                on='Symbol', 
                how='outer',
                suffixes=('_Old', '_New')
            )
            
            # Calculate rank change
            comparison['Rank_Change'] = comparison['Old_Rank'] - comparison['New_Rank']
            comparison['Rank_Movement'] = comparison['Rank_Change'].apply(self._categorize_movement)
            
            # Fill NaN ranks (new or removed stocks)
            comparison['Old_Rank'] = comparison['Old_Rank'].fillna(999)  # New stocks
            comparison['New_Rank'] = comparison['New_Rank'].fillna(999)  # Removed stocks
            
            return comparison.sort_values('New_Rank'), selected_sheet or "Unknown"
            
        except Exception as e:
            self.logger.error(f"Error comparing rankings: {e}")
            raise
    
    def _categorize_movement(self, change: float) -> str:
        """Categorize rank movement"""
        if pd.isna(change):
            return "New/Removed"
        elif change > 10:
            return "🚀 Major Rise"
        elif change > 5:
            return "📈 Significant Rise"
        elif change > 0:
            return "⬆️ Rise"
        elif change == 0:
            return "➡️ No Change"
        elif change > -5:
            return "⬇️ Fall"
        elif change > -10:
            return "📉 Significant Fall"
        else:
            return "💥 Major Fall"
    
    def analyze_performance_changes(self, comparison_df: pd.DataFrame) -> Dict:
        """Analyze performance metric changes"""
        insights = {
            'biggest_gainers': [],
            'biggest_losers': [],
            'new_entries': [],
            'removed_stocks': [],
            'sector_changes': {},
            'risk_changes': {}
        }
        
        # Biggest gainers (rank improved significantly)
        gainers = comparison_df[comparison_df['Rank_Change'] > 5].nlargest(10, 'Rank_Change')
        insights['biggest_gainers'] = gainers[['Symbol', 'Old_Rank', 'New_Rank', 'Rank_Change']].to_dict('records')
        
        # Biggest losers (rank dropped significantly)
        losers = comparison_df[comparison_df['Rank_Change'] < -5].nsmallest(10, 'Rank_Change')
        insights['biggest_losers'] = losers[['Symbol', 'Old_Rank', 'New_Rank', 'Rank_Change']].to_dict('records')
        
        # New entries (wasn't in old report)
        new_entries = comparison_df[comparison_df['Old_Rank'] == 999]
        insights['new_entries'] = new_entries[['Symbol', 'New_Rank']].to_dict('records')
        
        # Removed stocks (not in new report)
        removed = comparison_df[comparison_df['New_Rank'] == 999]
        insights['removed_stocks'] = removed[['Symbol', 'Old_Rank']].to_dict('records')
        
        return insights
    
    def generate_market_insights(self, comparison_df: pd.DataFrame, insights: Dict) -> Dict:
        """Generate high-level market insights"""
        market_insights = {
            'market_sentiment': 'Neutral',
            'dominant_trend': 'Mixed',
            'sector_rotation': [],
            'risk_appetite': 'Moderate',
            'key_observations': []
        }
        
        # Analyze overall market movement
        total_stocks = len(comparison_df[comparison_df['New_Rank'] < 999])
        rising_stocks = len(comparison_df[comparison_df['Rank_Change'] > 0])
        falling_stocks = len(comparison_df[comparison_df['Rank_Change'] < 0])
        
        if rising_stocks > falling_stocks * 1.5:
            market_insights['market_sentiment'] = '🐂 Bullish'
            market_insights['dominant_trend'] = 'Upward momentum'
        elif falling_stocks > rising_stocks * 1.5:
            market_insights['market_sentiment'] = '🐻 Bearish'
            market_insights['dominant_trend'] = 'Downward pressure'
        else:
            market_insights['market_sentiment'] = '🦘 Mixed'
            market_insights['dominant_trend'] = 'Sideways/Consolidation'
        
        # Key observations
        if len(insights['biggest_gainers']) > 0:
            top_gainer = insights['biggest_gainers'][0]
            market_insights['key_observations'].append(
                f"Top performer: {top_gainer['Symbol']} (Rank: {top_gainer['Old_Rank']} → {top_gainer['New_Rank']})"
            )
        
        if len(insights['biggest_losers']) > 0:
            top_loser = insights['biggest_losers'][0]
            market_insights['key_observations'].append(
                f"Biggest decline: {top_loser['Symbol']} (Rank: {top_loser['Old_Rank']} → {top_loser['New_Rank']})"
            )
        
        if len(insights['new_entries']) > 0:
            market_insights['key_observations'].append(
                f"{len(insights['new_entries'])} new stocks entered top rankings"
            )
        
        if len(insights['removed_stocks']) > 0:
            market_insights['key_observations'].append(
                f"{len(insights['removed_stocks'])} stocks dropped out of top rankings"
            )
        
        return market_insights
    
    def compare_reports(self, old_report: Optional[str] = None, new_report: Optional[str] = None) -> Dict:
        """Main comparison function"""
        try:
            # Get report files
            if not old_report or not new_report:
                reports = self.get_latest_reports(2)
                new_report = reports[0]  # Most recent
                old_report = reports[1]   # Second most recent
            
            print(f"\n🔄 COMPARING STOCK REPORTS")
            print("=" * 50)
            print(f"📊 Previous Report: {os.path.basename(old_report)}")
            print(f"📈 Current Report:  {os.path.basename(new_report)}")
            print()
            
            # Load data from both reports
            old_data = self.load_report_data(old_report)
            new_data = self.load_report_data(new_report)
            
            # Compare rankings
            comparison_df, selected_sheet = self.compare_stock_rankings(old_data, new_data)
            
            # Analyze performance changes
            insights = self.analyze_performance_changes(comparison_df)
            
            # Generate market insights
            market_insights = self.generate_market_insights(comparison_df, insights)
            
            # Compile results
            results = {
                'old_report': old_report,
                'new_report': new_report,
                'comparison_data': comparison_df,
                'performance_insights': insights,
                'market_insights': market_insights,
                'comparison_sheet': selected_sheet,
                'comparison_stats': {
                    'total_stocks': len(comparison_df[comparison_df['New_Rank'] < 999]),
                    'sheet_used': selected_sheet,
                    'data_source': f"{selected_sheet} ({len(comparison_df[comparison_df['New_Rank'] < 999])} stocks)"
                },
                'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S')
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in report comparison: {e}")
            raise
    
    def display_console_insights(self, results: Dict):
        """Display insights in console format"""
        insights = results['performance_insights']
        market = results['market_insights']
        
        print(f"🎯 MARKET ANALYSIS INSIGHTS")
        print("=" * 50)
        
        # Show comparison source info
        if 'comparison_stats' in results:
            stats = results['comparison_stats']
            print(f"📊 Analysis Source: {stats['data_source']}")
            print()
        
        print(f"Market Sentiment: {market['market_sentiment']}")
        print(f"Dominant Trend: {market['dominant_trend']}")
        print(f"Risk Appetite: {market['risk_appetite']}")
        print()
        
        # Top gainers
        if insights['biggest_gainers']:
            print("🚀 TOP GAINERS (Ranking Improved)")
            print("-" * 40)
            for stock in insights['biggest_gainers'][:5]:
                print(f"   {stock['Symbol']:<12} Rank: {stock['Old_Rank']:>3} → {stock['New_Rank']:>3} ({stock['Rank_Change']:+3})")
            print()
        
        # Top losers
        if insights['biggest_losers']:
            print("💥 TOP DECLINERS (Ranking Dropped)")
            print("-" * 40)
            for stock in insights['biggest_losers'][:5]:
                print(f"   {stock['Symbol']:<12} Rank: {stock['Old_Rank']:>3} → {stock['New_Rank']:>3} ({stock['Rank_Change']:+3})")
            print()
        
        # New entries
        if insights['new_entries']:
            print("🌟 NEW ENTRIES")
            print("-" * 20)
            for stock in insights['new_entries'][:5]:
                print(f"   {stock['Symbol']:<12} New Rank: {stock['New_Rank']}")
            print()
        
        # Key observations
        if market['key_observations']:
            print("📋 KEY OBSERVATIONS")
            print("-" * 30)
            for obs in market['key_observations']:
                print(f"   • {obs}")
            print()


if __name__ == "__main__":
    # Example usage
    comparator = ReportComparator()
    
    try:
        results = comparator.compare_reports()
        comparator.display_console_insights(results)
        print("✅ Report comparison completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during comparison: {e}")