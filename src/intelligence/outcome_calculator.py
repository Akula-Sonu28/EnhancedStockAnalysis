"""
📈 Outcome Calculator - Performance Analytics

Calculates hit rates, ROI, and other performance metrics from tracked outcomes.
Provides insights into system accuracy and recommendation quality.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import pandas as pd
from .intelligence_db import IntelligenceDB


class OutcomeCalculator:
    """Calculates performance metrics and analytics from outcomes"""
    
    def __init__(self, db_path: str = "data/stock_analysis.db"):
        """
        Initialize outcome calculator
        
        Args:
            db_path: Path to intelligence database
        """
        self.db = IntelligenceDB(db_path)
        logging.info("OutcomeCalculator initialized")
    
    def calculate_hit_rates(self, period_days: int = 30, 
                           check_period: int = 30) -> Dict[str, float]:
        """
        Calculate hit rates by action type
        
        Args:
            period_days: How far back to look for recommendations
            check_period: Outcome check period (7, 30, or 90 days)
            
        Returns:
            Dict with hit rates per action type
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    r.action,
                    COUNT(*) as total,
                    SUM(CASE WHEN o.was_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(o.return_pct) as avg_return
                FROM recommendations r
                JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.date >= date('now', '-' || ? || ' days')
                  AND o.days_elapsed = ?
                GROUP BY r.action
                ORDER BY correct DESC
            """, (period_days, check_period))
            
            results = {}
            for row in cursor.fetchall():
                action = row['action']
                hit_rate = (row['correct'] / row['total'] * 100) if row['total'] > 0 else 0
                
                results[action] = {
                    'hit_rate': hit_rate,
                    'total': row['total'],
                    'correct': row['correct'],
                    'avg_return': row['avg_return'] or 0
                }
            
            return results
            
        finally:
            conn.close()
    
    def calculate_roi_by_action(self, period_days: int = 90) -> Dict:
        """
        Calculate ROI statistics by action type
        
        Args:
            period_days: Period to analyze
            
        Returns:
            Dict with ROI stats per action
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    r.action,
                    o.days_elapsed,
                    COUNT(*) as count,
                    AVG(o.return_pct) as avg_return,
                    MIN(o.return_pct) as min_return,
                    MAX(o.return_pct) as max_return,
                    AVG(o.outperformance) as avg_outperformance
                FROM recommendations r
                JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.date >= date('now', '-' || ? || ' days')
                GROUP BY r.action, o.days_elapsed
                ORDER BY r.action, o.days_elapsed
            """, (period_days,))
            
            results = defaultdict(dict)
            for row in cursor.fetchall():
                action = row['action']
                days = row['days_elapsed']
                
                results[action][f'{days}d'] = {
                    'count': row['count'],
                    'avg_return': row['avg_return'] or 0,
                    'min_return': row['min_return'] or 0,
                    'max_return': row['max_return'] or 0,
                    'avg_outperformance': row['avg_outperformance'] or 0
                }
            
            return dict(results)
            
        finally:
            conn.close()
    
    def get_best_performers(self, period_days: int = 90, 
                           check_period: int = 30, 
                           limit: int = 10) -> List[Dict]:
        """
        Get best performing recommendations
        
        Args:
            period_days: Period to analyze
            check_period: Outcome period to use
            limit: Number of results
            
        Returns:
            List of best performers
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    r.symbol,
                    r.date,
                    r.action,
                    r.price as entry_price,
                    r.score,
                    o.return_pct,
                    o.outperformance,
                    r.sector
                FROM recommendations r
                JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.date >= date('now', '-' || ? || ' days')
                  AND o.days_elapsed = ?
                ORDER BY o.return_pct DESC
                LIMIT ?
            """, (period_days, check_period, limit))
            
            return [dict(row) for row in cursor.fetchall()]
            
        finally:
            conn.close()
    
    def get_worst_performers(self, period_days: int = 90, 
                            check_period: int = 30, 
                            limit: int = 10) -> List[Dict]:
        """
        Get worst performing recommendations
        
        Args:
            period_days: Period to analyze
            check_period: Outcome period to use
            limit: Number of results
            
        Returns:
            List of worst performers
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    r.symbol,
                    r.date,
                    r.action,
                    r.price as entry_price,
                    r.score,
                    o.return_pct,
                    o.outperformance,
                    r.sector
                FROM recommendations r
                JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.date >= date('now', '-' || ? || ' days')
                  AND o.days_elapsed = ?
                ORDER BY o.return_pct ASC
                LIMIT ?
            """, (period_days, check_period, limit))
            
            return [dict(row) for row in cursor.fetchall()]
            
        finally:
            conn.close()
    
    def calculate_sector_performance(self, period_days: int = 90, 
                                    check_period: int = 30) -> Dict:
        """
        Calculate performance by sector
        
        Args:
            period_days: Period to analyze
            check_period: Outcome period to use
            
        Returns:
            Dict with sector performance
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    r.sector,
                    COUNT(*) as total,
                    SUM(CASE WHEN o.was_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(o.return_pct) as avg_return,
                    AVG(o.outperformance) as avg_outperformance
                FROM recommendations r
                JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.date >= date('now', '-' || ? || ' days')
                  AND o.days_elapsed = ?
                  AND r.sector IS NOT NULL
                GROUP BY r.sector
                ORDER BY correct DESC
            """, (period_days, check_period))
            
            results = {}
            for row in cursor.fetchall():
                sector = row['sector']
                hit_rate = (row['correct'] / row['total'] * 100) if row['total'] > 0 else 0
                
                results[sector] = {
                    'hit_rate': hit_rate,
                    'total': row['total'],
                    'correct': row['correct'],
                    'avg_return': row['avg_return'] or 0,
                    'avg_outperformance': row['avg_outperformance'] or 0
                }
            
            return results
            
        finally:
            conn.close()
    
    def calculate_regime_performance(self, period_days: int = 90, 
                                    check_period: int = 30) -> Dict:
        """
        Calculate performance by market regime
        
        Args:
            period_days: Period to analyze
            check_period: Outcome period to use
            
        Returns:
            Dict with regime performance
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    r.market_regime,
                    COUNT(*) as total,
                    SUM(CASE WHEN o.was_correct = 1 THEN 1 ELSE 0 END) as correct,
                    AVG(o.return_pct) as avg_return
                FROM recommendations r
                JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.date >= date('now', '-' || ? || ' days')
                  AND o.days_elapsed = ?
                  AND r.market_regime IS NOT NULL
                GROUP BY r.market_regime
            """, (period_days, check_period))
            
            results = {}
            for row in cursor.fetchall():
                regime = row['market_regime']
                hit_rate = (row['correct'] / row['total'] * 100) if row['total'] > 0 else 0
                
                results[regime] = {
                    'hit_rate': hit_rate,
                    'total': row['total'],
                    'correct': row['correct'],
                    'avg_return': row['avg_return'] or 0
                }
            
            return results
            
        finally:
            conn.close()
    
    def get_consistency_analysis(self, symbol: str) -> Dict:
        """
        Analyze consistency of recommendations for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with consistency metrics
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get all recommendations for this symbol
            cursor.execute("""
                SELECT 
                    r.date,
                    r.action,
                    r.score,
                    o.return_pct,
                    o.was_correct,
                    o.days_elapsed
                FROM recommendations r
                LEFT JOIN outcomes o ON r.id = o.recommendation_id
                WHERE r.symbol = ?
                ORDER BY r.date DESC
            """, (symbol,))
            
            recs = [dict(row) for row in cursor.fetchall()]
            
            if not recs:
                return {'symbol': symbol, 'total': 0}
            
            # Calculate consistency metrics
            total = len(recs)
            outcomes = [r for r in recs if r['return_pct'] is not None]
            
            if not outcomes:
                return {
                    'symbol': symbol,
                    'total_recommendations': total,
                    'outcomes_tracked': 0
                }
            
            wins = sum(1 for r in outcomes if r['was_correct'])
            hit_rate = (wins / len(outcomes) * 100) if outcomes else 0
            avg_return = sum(r['return_pct'] for r in outcomes) / len(outcomes) if outcomes else 0
            
            # Check for action changes
            actions = [r['action'] for r in recs]
            action_changes = sum(1 for i in range(len(actions)-1) if actions[i] != actions[i+1])
            
            return {
                'symbol': symbol,
                'total_recommendations': total,
                'outcomes_tracked': len(outcomes),
                'wins': wins,
                'losses': len(outcomes) - wins,
                'hit_rate': hit_rate,
                'avg_return': avg_return,
                'action_changes': action_changes,
                'last_action': recs[0]['action'],
                'last_score': recs[0]['score']
            }
            
        finally:
            conn.close()
    
    def generate_performance_report(self, period_days: int = 30) -> Dict:
        """
        Generate comprehensive performance report
        
        Args:
            period_days: Period to analyze
            
        Returns:
            Dict with full performance report
        """
        report = {
            'period_days': period_days,
            'generated_at': datetime.now().isoformat(),
            'statistics': {},
            'hit_rates': {},
            'roi_by_action': {},
            'sector_performance': {},
            'regime_performance': {},
            'best_performers': [],
            'worst_performers': []
        }
        
        # Overall statistics
        report['statistics'] = self.db.get_statistics(period_days)
        
        # Hit rates for each check period
        for check_period in [7, 30, 90]:
            report['hit_rates'][f'{check_period}d'] = self.calculate_hit_rates(
                period_days, check_period
            )
        
        # ROI by action
        report['roi_by_action'] = self.calculate_roi_by_action(period_days)
        
        # Sector performance (30-day)
        report['sector_performance'] = self.calculate_sector_performance(period_days, 30)
        
        # Regime performance (30-day)
        report['regime_performance'] = self.calculate_regime_performance(period_days, 30)
        
        # Best and worst performers (30-day)
        report['best_performers'] = self.get_best_performers(period_days, 30, 10)
        report['worst_performers'] = self.get_worst_performers(period_days, 30, 10)
        
        return report
