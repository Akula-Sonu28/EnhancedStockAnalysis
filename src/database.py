"""
Database module for storing stock analysis data
"""
import sqlite3
import pandas as pd
import logging
from datetime import datetime
import os

class StockDatabase:
    def __init__(self, db_path="data/stock_analysis.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Prices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    adj_close REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
            # Fundamentals table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fundamentals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    pe_ratio REAL,
                    pb_ratio REAL,
                    roe REAL,
                    debt_to_equity REAL,
                    current_ratio REAL,
                    market_cap REAL,
                    revenue_growth REAL,
                    profit_growth REAL,
                    dividend_yield REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
            # Technical indicators table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    rsi REAL,
                    macd REAL,
                    macd_signal REAL,
                    macd_histogram REAL,
                    sma_20 REAL,
                    sma_50 REAL,
                    ema_12 REAL,
                    ema_26 REAL,
                    bb_upper REAL,
                    bb_lower REAL,
                    bb_middle REAL,
                    adx REAL,
                    atr REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
            # News sentiment table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    headline TEXT,
                    source TEXT,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Analysis scores table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    fundamental_score REAL,
                    technical_score REAL,
                    sentiment_score REAL,
                    overall_score REAL,
                    recommendation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, date)
                )
            ''')
            
            conn.commit()
            logging.info("Database initialized successfully")
    
    def insert_prices(self, df):
        """Insert price data into database"""
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('prices', conn, if_exists='append', index=False)
    
    def insert_fundamentals(self, df):
        """Insert fundamental data into database"""
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('fundamentals', conn, if_exists='append', index=False)
    
    def insert_indicators(self, df):
        """Insert technical indicators into database"""
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('indicators', conn, if_exists='append', index=False)
    
    def insert_news(self, df):
        """Insert news data into database"""
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('news', conn, if_exists='append', index=False)
    
    def insert_scores(self, df):
        """Insert analysis scores into database"""
        with sqlite3.connect(self.db_path) as conn:
            df.to_sql('scores', conn, if_exists='append', index=False)
    
    def get_latest_prices(self, symbol=None, days=30):
        """Get latest price data"""
        with sqlite3.connect(self.db_path) as conn:
            if symbol:
                query = "SELECT * FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT ?"
                return pd.read_sql_query(query, conn, params=(symbol, days))
            else:
                query = "SELECT * FROM prices ORDER BY date DESC LIMIT ?"
                return pd.read_sql_query(query, conn, params=(days,))
    
    def get_latest_scores(self, date=None):
        """Get latest analysis scores"""
        with sqlite3.connect(self.db_path) as conn:
            if date:
                query = "SELECT * FROM scores WHERE date = ? ORDER BY overall_score DESC"
                return pd.read_sql_query(query, conn, params=(date,))
            else:
                query = """
                SELECT * FROM scores 
                WHERE date = (SELECT MAX(date) FROM scores) 
                ORDER BY overall_score DESC
                """
                return pd.read_sql_query(query, conn)
