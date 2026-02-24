"""
📊 Performance Tracker - Track Recommendation Outcomes

Monitors all recommendations and checks their actual performance after
7, 30, and 90 days. Determines if recommendations were correct and 
calculates actual returns.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import yfinance as yf
from .intelligence_db import IntelligenceDB


class PerformanceTracker:
    """Tracks recommendation outcomes and performance over time"""
    
    def __init__(self, db_path: str = "data/stock_analysis.db"):
        """
        Initialize performance tracker
        
        Args:
            db_path: Path to intelligence database
        """
        self.db = IntelligenceDB(db_path)
        self.check_periods = [7, 30, 90]  # Days to check outcomes
        logging.info("PerformanceTracker initialized")
    
    def check_pending_outcomes(self, force_recheck: bool = False):
        """
        Check outcomes for all pending recommendations
        
        Args:
            force_recheck: If True, recheck even if outcome exists
        """
        logging.info("Checking pending outcomes...")
        
        for days in self.check_periods:
            recommendations = self.db.get_recommendations_needing_outcome_check(days)
            
            if not recommendations:
                logging.info(f"No recommendations pending {days}-day check")
                continue
            
            logging.info(f"Checking {len(recommendations)} recommendations for {days}-day outcomes")
            
            for rec in recommendations:
                try:
                    self._check_recommendation_outcome(rec, days)
                except Exception as e:
                    logging.error(f"Error checking outcome for {rec['symbol']}: {e}")
        
        logging.info("Outcome check complete")
    
    def _check_recommendation_outcome(self, recommendation: Dict, days_elapsed: int):
        """
        Check outcome for a single recommendation
        
        Args:
            recommendation: Recommendation dict from database
            days_elapsed: Number of days to check (7, 30, or 90)
        """
        symbol = recommendation['symbol']
        rec_date = datetime.fromisoformat(str(recommendation['date']))
        check_date = rec_date + timedelta(days=days_elapsed)
        original_price = recommendation['price']
        action = recommendation['action']
        
        if not original_price or original_price <= 0:
            logging.warning(f"Invalid original price for {symbol}: {original_price}")
            return
        
        # Get price at check date
        current_price = self._get_price_at_date(symbol, check_date)
        
        if not current_price or current_price <= 0:
            logging.warning(f"Could not get price for {symbol} at {check_date}")
            return
        
        # Calculate return
        return_pct = ((current_price - original_price) / original_price) * 100
        
        # Determine if recommendation was correct
        was_correct, outcome_type = self._evaluate_recommendation(
            action, return_pct, days_elapsed
        )
        
        # Get benchmark return (Nifty 50)
        benchmark_return = self._get_benchmark_return(rec_date, check_date)
        outperformance = return_pct - benchmark_return if benchmark_return is not None else None
        
        # Calculate risk metrics
        max_drawdown = self._calculate_max_drawdown(symbol, rec_date, check_date, original_price)
        volatility = self._calculate_volatility(symbol, rec_date, check_date)
        
        # Record outcome
        outcome = {
            'recommendation_id': recommendation['id'],
            'check_date': check_date,
            'days_elapsed': days_elapsed,
            'price_at_check': current_price,
            'return_pct': return_pct,
            'was_correct': was_correct,
            'outcome_type': outcome_type,
            'benchmark_return': benchmark_return,
            'outperformance': outperformance,
            'max_drawdown': max_drawdown,
            'volatility': volatility
        }
        
        self.db.record_outcome(outcome)
        
        logging.info(
            f"{symbol} ({action}): {return_pct:+.2f}% in {days_elapsed}d "
            f"[{outcome_type}] - {'✅ CORRECT' if was_correct else '❌ WRONG'}"
        )
    
    def _get_price_at_date(self, symbol: str, date: datetime) -> Optional[float]:
        """
        Get stock price at a specific date
        
        Args:
            symbol: Stock symbol
            date: Date to check
            
        Returns:
            Price at date, or None if not available
        """
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            
            # Get data around the target date (±5 days buffer)
            start_date = date - timedelta(days=5)
            end_date = date + timedelta(days=5)
            
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                logging.warning(f"No price data for {symbol} around {date}")
                return None
            
            # Find closest date
            hist.index = hist.index.tz_localize(None)  # Remove timezone
            closest_date = min(hist.index, key=lambda d: abs(d - date))
            
            price = hist.loc[closest_date, 'Close']
            return float(price)
            
        except Exception as e:
            logging.error(f"Error getting price for {symbol} at {date}: {e}")
            return None
    
    def _evaluate_recommendation(self, action: str, return_pct: float, days_elapsed: int) -> Tuple[bool, str]:
        """
        Evaluate if a recommendation was correct
        
        Args:
            action: Original action (BUY/SELL/HOLD/etc)
            return_pct: Actual return percentage
            days_elapsed: Days since recommendation
            
        Returns:
            Tuple of (was_correct, outcome_type)
        """
        # Define thresholds based on time period
        if days_elapsed == 7:
            win_threshold = 3.0  # 3% gain in 7 days
            loss_threshold = -3.0
        elif days_elapsed == 30:
            win_threshold = 5.0  # 5% gain in 30 days
            loss_threshold = -5.0
        else:  # 90 days
            win_threshold = 10.0  # 10% gain in 90 days
            loss_threshold = -10.0
        
        # Classify outcome
        if return_pct >= win_threshold:
            outcome_type = "WIN"
        elif return_pct <= loss_threshold:
            outcome_type = "LOSS"
        else:
            outcome_type = "NEUTRAL"
        
        # Determine correctness based on action
        action_upper = action.upper()
        
        if any(keyword in action_upper for keyword in ['BUY', 'INCREASE', 'STRONG BUY']):
            # For buy recommendations, positive returns = correct
            was_correct = return_pct > 0
            
        elif any(keyword in action_upper for keyword in ['SELL', 'EXIT', 'BOOK']):
            # For sell recommendations, we expect stock to decline or underperform
            # Consider correct if return is below 50% of win threshold
            was_correct = return_pct < (win_threshold * 0.5)
            
        else:  # HOLD or other
            # For hold, expect stability (between -2% and +5%)
            was_correct = -2.0 <= return_pct <= 5.0
        
        return was_correct, outcome_type
    
    def _get_benchmark_return(self, start_date: datetime, end_date: datetime) -> Optional[float]:
        """
        Get Nifty 50 return for comparison
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Benchmark return percentage
        """
        try:
            nifty = yf.Ticker("^NSEI")
            hist = nifty.history(start=start_date, end=end_date + timedelta(days=2))
            
            if len(hist) < 2:
                return None
            
            start_price = hist.iloc[0]['Close']
            end_price = hist.iloc[-1]['Close']
            
            return ((end_price - start_price) / start_price) * 100
            
        except Exception as e:
            logging.warning(f"Could not get benchmark return: {e}")
            return None
    
    def _calculate_max_drawdown(self, symbol: str, start_date: datetime, 
                               end_date: datetime, original_price: float) -> Optional[float]:
        """
        Calculate maximum drawdown during period
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            original_price: Entry price
            
        Returns:
            Maximum drawdown percentage (negative)
        """
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=2))
            
            if hist.empty:
                return None
            
            # Calculate drawdown from entry price
            min_price = hist['Low'].min()
            drawdown = ((min_price - original_price) / original_price) * 100
            
            return drawdown if drawdown < 0 else 0.0
            
        except Exception as e:
            logging.warning(f"Could not calculate drawdown for {symbol}: {e}")
            return None
    
    def _calculate_volatility(self, symbol: str, start_date: datetime, 
                             end_date: datetime) -> Optional[float]:
        """
        Calculate annualized volatility during period
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            
        Returns:
            Annualized volatility percentage
        """
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=2))
            
            if len(hist) < 5:
                return None
            
            # Calculate daily returns
            returns = hist['Close'].pct_change().dropna()
            
            # Annualized volatility (252 trading days)
            volatility = returns.std() * (252 ** 0.5) * 100
            
            return volatility
            
        except Exception as e:
            logging.warning(f"Could not calculate volatility for {symbol}: {e}")
            return None
    
    def get_recent_performance_summary(self, days: int = 30) -> Dict:
        """
        Get performance summary for recent period
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict with performance metrics
        """
        return self.db.get_statistics(days)
    
    def record_new_recommendation(self, recommendation: Dict) -> int:
        """
        Record a new recommendation for tracking
        
        Args:
            recommendation: Recommendation dict
            
        Returns:
            ID of recorded recommendation
        """
        return self.db.record_recommendation(recommendation)
