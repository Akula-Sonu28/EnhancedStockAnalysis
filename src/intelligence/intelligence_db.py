"""
🗄️ Intelligence Database - Centralized Intelligence Storage

Manages the SQLite database for storing recommendations, outcomes,
performance metrics, and learning data.

Schema Version: 1.0
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json


class IntelligenceDB:
    """Manages the intelligence database with recommendations, outcomes, and performance metrics"""
    
    VERSION = "1.0"
    
    def __init__(self, db_path: str = "data/stock_analysis.db"):
        """
        Initialize intelligence database
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.ensure_database_exists()
        self._initialize_schema()
        logging.info(f"IntelligenceDB initialized: {db_path}")
    
    def ensure_database_exists(self):
        """Ensure database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_schema(self):
        """Initialize or upgrade database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if schema version table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY,
                    applied_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check current version
            cursor.execute("SELECT version FROM schema_version ORDER BY applied_date DESC LIMIT 1")
            result = cursor.fetchone()
            current_version = result['version'] if result else None
            
            if current_version != self.VERSION:
                self._create_schema(cursor)
                cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (self.VERSION,))
                conn.commit()
                logging.info(f"Database schema initialized/upgraded to version {self.VERSION}")
            
        except Exception as e:
            logging.error(f"Error initializing database schema: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _create_schema(self, cursor: sqlite3.Cursor):
        """Create complete database schema"""
        
        # 1. Recommendations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                score REAL,
                price REAL,
                
                -- Scores breakdown
                technical_score REAL,
                fundamental_score REAL,
                ml_prediction REAL,
                sentiment_score REAL,
                pattern_score REAL,
                
                -- Fundamentals snapshot
                pe_ratio REAL,
                pb_ratio REAL,
                roe REAL,
                debt_to_equity REAL,
                revenue_growth REAL,
                
                -- Technical snapshot
                rsi REAL,
                macd REAL,
                volume_trend TEXT,
                
                -- Context
                market_regime TEXT,
                sector TEXT,
                industry TEXT,
                rank INTEGER,
                confidence REAL,
                reason TEXT,
                
                -- Metadata
                report_file TEXT,
                analysis_version TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Outcomes Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id INTEGER NOT NULL,
                check_date DATETIME NOT NULL,
                days_elapsed INTEGER NOT NULL,
                
                price_at_check REAL,
                return_pct REAL,
                was_correct BOOLEAN,
                outcome_type TEXT, -- WIN/LOSS/NEUTRAL
                
                -- Benchmark comparison
                benchmark_return REAL,
                outperformance REAL,
                
                -- Risk metrics
                max_drawdown REAL,
                volatility REAL,
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recommendation_id) REFERENCES recommendations(id)
            )
        """)
        
        # 3. Indicator Performance Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indicator_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_name TEXT NOT NULL,
                evaluation_date DATE NOT NULL,
                period_days INTEGER NOT NULL,
                
                market_regime TEXT,
                sector TEXT,
                
                hit_rate REAL,
                avg_contribution REAL,
                current_weight REAL,
                recommended_weight REAL,
                
                sample_size INTEGER,
                wins INTEGER,
                losses INTEGER,
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. Model Performance Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                model_version TEXT,
                evaluation_date DATE NOT NULL,
                period_days INTEGER NOT NULL,
                
                accuracy REAL,
                precision_score REAL,
                recall_score REAL,
                f1_score REAL,
                
                avg_return REAL,
                win_rate REAL,
                
                best_sector TEXT,
                worst_sector TEXT,
                
                regime_performance TEXT, -- JSON: {BULLISH: 0.75, BEARISH: 0.62}
                
                sample_size INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 5. System Metrics Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_date DATE NOT NULL,
                period_days INTEGER NOT NULL,
                
                total_recommendations INTEGER,
                
                hit_rate_7d REAL,
                hit_rate_30d REAL,
                hit_rate_90d REAL,
                
                avg_return_7d REAL,
                avg_return_30d REAL,
                avg_return_90d REAL,
                
                best_action TEXT,
                worst_action TEXT,
                
                flip_flop_count INTEGER,
                avg_hold_days REAL,
                
                total_wins INTEGER,
                total_losses INTEGER,
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_symbol ON recommendations(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_date ON recommendations(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_action ON recommendations(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_sector ON recommendations(sector)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcome_rec_id ON outcomes(recommendation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcome_date ON outcomes(check_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_indicator_name ON indicator_performance(indicator_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_name ON model_performance(model_name)")
        
        logging.info("Database schema created successfully")
    
    def record_recommendation(self, recommendation: Dict) -> int:
        """
        Record a new recommendation
        
        Args:
            recommendation: Dict with recommendation details
            
        Returns:
            ID of inserted recommendation
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO recommendations (
                    date, symbol, action, score, price,
                    technical_score, fundamental_score, ml_prediction, sentiment_score, pattern_score,
                    pe_ratio, pb_ratio, roe, debt_to_equity, revenue_growth,
                    rsi, macd, volume_trend,
                    market_regime, sector, industry, rank, confidence, reason,
                    report_file, analysis_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                recommendation.get('date', datetime.now()),
                recommendation['symbol'],
                recommendation['action'],
                recommendation.get('score'),
                recommendation.get('price'),
                recommendation.get('technical_score'),
                recommendation.get('fundamental_score'),
                recommendation.get('ml_prediction'),
                recommendation.get('sentiment_score'),
                recommendation.get('pattern_score'),
                recommendation.get('pe_ratio'),
                recommendation.get('pb_ratio'),
                recommendation.get('roe'),
                recommendation.get('debt_to_equity'),
                recommendation.get('revenue_growth'),
                recommendation.get('rsi'),
                recommendation.get('macd'),
                recommendation.get('volume_trend'),
                recommendation.get('market_regime'),
                recommendation.get('sector'),
                recommendation.get('industry'),
                recommendation.get('rank'),
                recommendation.get('confidence'),
                recommendation.get('reason'),
                recommendation.get('report_file'),
                recommendation.get('analysis_version', '1.0')
            ))
            
            rec_id = cursor.lastrowid
            conn.commit()
            logging.debug(f"Recorded recommendation: {recommendation['symbol']} - {recommendation['action']} (ID: {rec_id})")
            return rec_id
            
        except Exception as e:
            logging.error(f"Error recording recommendation: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def record_outcome(self, outcome: Dict) -> int:
        """
        Record an outcome for a recommendation
        
        Args:
            outcome: Dict with outcome details
            
        Returns:
            ID of inserted outcome
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO outcomes (
                    recommendation_id, check_date, days_elapsed,
                    price_at_check, return_pct, was_correct, outcome_type,
                    benchmark_return, outperformance, max_drawdown, volatility
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome['recommendation_id'],
                outcome.get('check_date', datetime.now()),
                outcome['days_elapsed'],
                outcome.get('price_at_check'),
                outcome.get('return_pct'),
                outcome.get('was_correct'),
                outcome.get('outcome_type'),
                outcome.get('benchmark_return'),
                outcome.get('outperformance'),
                outcome.get('max_drawdown'),
                outcome.get('volatility')
            ))
            
            outcome_id = cursor.lastrowid
            conn.commit()
            logging.debug(f"Recorded outcome for recommendation {outcome['recommendation_id']}: {outcome.get('outcome_type')}")
            return outcome_id
            
        except Exception as e:
            logging.error(f"Error recording outcome: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_recommendations(self, 
                           symbol: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           action: Optional[str] = None) -> List[Dict]:
        """Get recommendations with optional filters"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM recommendations WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if action:
            query += " AND action = ?"
            params.append(action)
        
        query += " ORDER BY date DESC"
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_recommendations_needing_outcome_check(self, days: int = 7) -> List[Dict]:
        """
        Get recommendations that need outcome checking
        
        Args:
            days: Number of days elapsed since recommendation
            
        Returns:
            List of recommendations without outcomes for this period
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT r.* 
                FROM recommendations r
                LEFT JOIN outcomes o ON r.id = o.recommendation_id AND o.days_elapsed = ?
                WHERE o.id IS NULL
                  AND date(r.date) <= date('now', '-' || ? || ' days')
                ORDER BY r.date ASC
            """, (days, days))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_statistics(self, period_days: int = 30) -> Dict:
        """Get system statistics for a period"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Total recommendations
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM recommendations
                WHERE date >= date('now', '-' || ? || ' days')
            """, (period_days,))
            stats['total_recommendations'] = cursor.fetchone()['total']
            
            # Outcomes summary
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_outcomes,
                    SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN was_correct = 0 THEN 1 ELSE 0 END) as losses,
                    AVG(return_pct) as avg_return,
                    AVG(CASE WHEN was_correct = 1 THEN return_pct END) as avg_win_return,
                    AVG(CASE WHEN was_correct = 0 THEN return_pct END) as avg_loss_return
                FROM outcomes o
                JOIN recommendations r ON o.recommendation_id = r.id
                WHERE r.date >= date('now', '-' || ? || ' days')
                  AND o.days_elapsed = ?
            """, (period_days, period_days))
            
            row = cursor.fetchone()
            if row and row['total_outcomes']:
                stats['total_outcomes'] = row['total_outcomes']
                stats['wins'] = row['wins'] or 0
                stats['losses'] = row['losses'] or 0
                stats['hit_rate'] = (row['wins'] / row['total_outcomes'] * 100) if row['total_outcomes'] > 0 else 0
                stats['avg_return'] = row['avg_return'] or 0
                stats['avg_win_return'] = row['avg_win_return'] or 0
                stats['avg_loss_return'] = row['avg_loss_return'] or 0
            else:
                stats['total_outcomes'] = 0
                stats['wins'] = 0
                stats['losses'] = 0
                stats['hit_rate'] = 0
                stats['avg_return'] = 0
            
            return stats
            
        finally:
            conn.close()
    
    def cleanup_test_data(self):
        """Remove test data (for testing only)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM outcomes WHERE recommendation_id IN (SELECT id FROM recommendations WHERE symbol LIKE 'TEST%')")
            cursor.execute("DELETE FROM recommendations WHERE symbol LIKE 'TEST%'")
            conn.commit()
            logging.info("Test data cleaned up")
        finally:
            conn.close()
