#!/usr/bin/env python3
"""
Configuration Management for Enhanced Stock Analysis
Centralized configuration for all analysis parameters
"""

import os
import json
import threading
from dataclasses import dataclass, fields, asdict
from typing import Dict, List, Optional

@dataclass
class AnalysisConfig:
    """Configuration class for stock analysis parameters"""
    
    # Performance Settings
    MAX_WORKERS: int = 3
    BATCH_SIZE: int = 5
    TIMEOUT_SECONDS: int = 120
    RETRY_ATTEMPTS: int = 3
    
    # Sentiment adjustment (capped at ±3 pts, confidence-weighted)
    ENABLE_SENTIMENT_ADJUSTMENT: bool = True
    
    # Caching Settings
    CACHE_ENABLED: bool = True
    CACHE_EXPIRY_HOURS: int = 4
    CACHE_DIR: str = "data/cache"
    
    # Scoring Weights
    FUNDAMENTAL_WEIGHT: float = 0.4
    TECHNICAL_WEIGHT: float = 0.3
    UNDERVALUATION_WEIGHT: float = 0.3
    
    # Undervaluation Thresholds
    PE_EXCELLENT: float = 10
    PE_GOOD: float = 15
    PE_AVERAGE: float = 20
    PB_EXCELLENT: float = 1.0
    PB_GOOD: float = 1.5
    DIVIDEND_EXCELLENT: float = 4.0
    
    # Risk Categories
    VOLATILITY_LOW: float = 15
    VOLATILITY_MODERATE: float = 25
    VOLATILITY_HIGH: float = 35
    
    # Recommendation Thresholds
    STRONG_BUY_THRESHOLD: float = 70
    BUY_THRESHOLD: float = 60
    HOLD_THRESHOLD: float = 50
    UNDERVALUED_THRESHOLD: float = 65
    
    # Data Sources
    NSE_SUFFIX: str = ".NS"
    BSE_SUFFIX: str = ".BO"
    DEFAULT_EXCHANGE: str = "NSE"
    
    # Portfolio Settings
    DEFAULT_PORTFOLIO_AMOUNT: float = 100000
    MAX_PORTFOLIO_POSITIONS: int = 15
    MIN_ALLOCATION_PERCENTAGE: float = 2.0
    MAX_SINGLE_STOCK_WEIGHT: float = 20.0

    # Allocation Thresholds
    MIN_INVESTMENT_PER_STOCK: float = 3000
    MAX_ALLOCATION_PCT: float = 0.05
    TARGET_PORTFOLIO_SIZE: int = 23
    SECTOR_CAP: int = 10
    CATEGORY_SECTOR_CAP: int = 5
    SECTOR_REDUCE_MIN_SCORE: float = 45.0
    CORE_CONCENTRATION_THRESHOLD: float = 0.40

    # Exit Strategy Thresholds
    EXIT_TOP_PCT: float = 0.30
    EXIT_BOTTOM_PCT: float = 0.20
    REBALANCE_PROFIT_THRESHOLD: float = 0.05
    PROFIT_BOOKING_THRESHOLD: float = 0.20

    # Regime Exposure
    BEAR_EXPOSURE: float = 0.50
    SIDEWAYS_EXPOSURE: float = 0.85
    BULL_EXPOSURE: float = 1.00

    # Score Smoothing
    SCORE_SMOOTHING_WEIGHT: float = 0.70
    SCORE_SMOOTHING_MAX_AGE_DAYS: int = 3

    # Sector Cap Enforcement
    SECTOR_CAP_ENFORCE_HOLDINGS: bool = True

    # Liquidity Filter
    MIN_AVG_DAILY_VOLUME: int = 50000
    ILLIQUID_SCORE_PENALTY: float = 15.0

    # Cache Retention
    CACHE_MAX_AGE_DAYS: int = 7

    # Extreme Volatility
    MAX_SAFE_VOLATILITY: float = 80.0

    # File Paths
    REPORTS_DIR: str = "reports"
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"
    TEMPLATES_DIR: str = "templates"
    
    # Default Stock Lists
    NIFTY_50_STOCKS: List[str] = None
    
    def __post_init__(self):
        """Initialize default stock lists"""
        self.NIFTY_50_STOCKS = [
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", 
            "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", 
            "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", 
            "SUNPHARMA", "WIPRO", "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", 
            "POWERGRID", "NTPC", "COALINDIA", "HINDALCO", "TATASTEEL", 
            "JSWSTEEL", "INDUSINDBK", "HEROMOTOCO", "BAJAJ-AUTO", "M&M", 
            "SHRIRAMFIN", "TATACONSUM", "DIVISLAB", "BRITANNIA", "DRREDDY", 
            "CIPLA", "APOLLOHOSP", "ADANIENT", "ADANIPORTS", "BPCL", 
            "GRASIM", "EICHERMOT", "TATAMOTORS", "UPL", "LTIM", "ONGC"
        ]
        
        # Create required directories
        for directory in [self.REPORTS_DIR, self.DATA_DIR, self.LOGS_DIR, 
                         self.TEMPLATES_DIR, self.CACHE_DIR]:
            os.makedirs(directory, exist_ok=True)

# Global configuration instance
CONFIG = AnalysisConfig()
_CONFIG_LOCK = threading.Lock()

def get_config() -> AnalysisConfig:
    """Get the global configuration instance"""
    return CONFIG

def update_config(**kwargs) -> None:
    """Update configuration parameters (thread-safe)."""
    global CONFIG
    with _CONFIG_LOCK:
        for key, value in kwargs.items():
            if hasattr(CONFIG, key):
                setattr(CONFIG, key, value)
            else:
                print(f"Warning: Unknown configuration parameter: {key}")

def load_config_from_file(file_path: str = 'config.json') -> None:
    """Load configuration from a JSON file and update the global CONFIG instance."""
    global CONFIG
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _CONFIG_LOCK:
            valid_fields = {fld.name for fld in fields(CONFIG)}
            for key, value in data.items():
                if key in valid_fields:
                    setattr(CONFIG, key, value)
        print(f"[CONFIG] Loaded settings from {file_path}")
    except Exception as e:
        print(f"[CONFIG] Warning: could not load {file_path}: {e}")

def save_config_to_file(file_path: str = 'config.json') -> None:
    """Serialize current CONFIG to a JSON file."""
    try:
        with _CONFIG_LOCK:
            data = {}
            for fld in fields(CONFIG):
                val = getattr(CONFIG, fld.name)
                if isinstance(val, list) and fld.name == 'NIFTY_50_STOCKS':
                    continue
                try:
                    json.dumps(val)
                    data[fld.name] = val
                except (TypeError, ValueError):
                    pass
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[CONFIG] Saved settings to {file_path}")
    except Exception as e:
        print(f"[CONFIG] Warning: could not save {file_path}: {e}")


# Auto-load config.json at import time if it exists
load_config_from_file('config.json')

# Technical Analysis Weights (Required by technical_analyzer.py)
TECHNICAL_WEIGHTS = {
    'ma_trend': 25,      # Moving Average Trend (25%)
    'rsi': 20,           # RSI Momentum (20%)
    'macd': 20,          # MACD Signal (20%)
    'trend': 15,         # Overall Trend (15%)
    'stochastic': 10,    # Stochastic Oscillator (10%)
    'volume': 5,         # Volume Analysis (5%)
    'volatility': 5      # Volatility Analysis (5%)
}

# Fundamental Analysis Weights (for enhanced_fundamental_analyzer.py)
FUNDAMENTAL_WEIGHTS = {
    'profitability': 30,    # ROE, ROA, Profit Margin
    'valuation': 25,        # P/E, P/B, EV/EBITDA
    'growth': 20,           # Revenue Growth, Earnings Growth
    'financial_health': 15, # Debt/Equity, Current Ratio
    'efficiency': 10        # Asset Turnover, Inventory Turnover
}
