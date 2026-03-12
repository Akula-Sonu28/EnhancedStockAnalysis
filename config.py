#!/usr/bin/env python3
"""
Configuration Management for Enhanced Stock Analysis
Centralized configuration for all analysis parameters
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class AnalysisConfig:
    """Configuration class for stock analysis parameters"""
    
    # Performance Settings
    MAX_WORKERS: int = 3
    BATCH_SIZE: int = 5
    TIMEOUT_SECONDS: int = 120
    RETRY_ATTEMPTS: int = 3
    
    # Sentiment adjustment (disable until a real news API is wired in)
    ENABLE_SENTIMENT_ADJUSTMENT: bool = False
    
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
    
    # File Paths
    REPORTS_DIR: str = "reports"
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"
    TEMPLATES_DIR: str = "templates"
    
    # Default Stock Lists
    NIFTY_50_STOCKS: List[str] = None
    NIFTY_200_STOCKS: List[str] = None
    
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

def get_config() -> AnalysisConfig:
    """Get the global configuration instance"""
    return CONFIG

def update_config(**kwargs) -> None:
    """Update configuration parameters"""
    global CONFIG
    for key, value in kwargs.items():
        if hasattr(CONFIG, key):
            setattr(CONFIG, key, value)
        else:
            print(f"Warning: Unknown configuration parameter: {key}")

def load_config_from_file(file_path: str) -> None:
    """Load configuration from a JSON or YAML file"""
    # TODO: Implement file-based configuration loading
    pass

def save_config_to_file(file_path: str) -> None:
    """Save current configuration to a file"""
    # TODO: Implement configuration saving
    pass

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
