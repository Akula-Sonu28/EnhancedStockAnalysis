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
    
    # Scoring Weights (validation-only; hybrid_optimized_scoring.py uses regime-adaptive weights)
    FUNDAMENTAL_WEIGHT: float = 0.4
    TECHNICAL_WEIGHT: float = 0.3
    UNDERVALUATION_WEIGHT: float = 0.3
    
    # Undervaluation Thresholds (reserved for future per-metric scoring; not consumed at runtime)
    PE_EXCELLENT: float = 10
    PE_GOOD: float = 15
    PE_AVERAGE: float = 20
    PB_EXCELLENT: float = 1.0
    PB_GOOD: float = 1.5
    DIVIDEND_EXCELLENT: float = 4.0
    
    # Risk Categories (reserved for future risk bucketing; not consumed at runtime)
    VOLATILITY_LOW: float = 15
    VOLATILITY_MODERATE: float = 25
    VOLATILITY_HIGH: float = 35
    
    # Recommendation Thresholds
    STRONG_BUY_THRESHOLD: float = 70
    BUY_THRESHOLD: float = 60
    HOLD_THRESHOLD: float = 50
    SELL_THRESHOLD: float = 40
    UNDERVALUED_THRESHOLD: float = 65
    
    # Data Sources
    NSE_SUFFIX: str = ".NS"
    BSE_SUFFIX: str = ".BO"  # reserved for BSE support
    DEFAULT_EXCHANGE: str = "NSE"  # reserved for multi-exchange support
    
    # Portfolio Settings
    DEFAULT_PORTFOLIO_AMOUNT: float = 100000
    MAX_PORTFOLIO_POSITIONS: int = 15
    MIN_ALLOCATION_PERCENTAGE: float = 2.0
    MAX_SINGLE_STOCK_WEIGHT: float = 20.0  # NOT WIRED: allocation engine uses per-cap-tier limits instead

    # Allocation Thresholds
    MIN_INVESTMENT_PER_STOCK: float = 3000
    MAX_ALLOCATION_PCT: float = 0.05  # NOT WIRED: allocation engine uses per-cap-tier limits instead
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
    EMERGENCY_EXIT_LOSS: float = -0.30
    EMERGENCY_EXIT_SCORE: float = 45.0

    # Regime Exposure
    BEAR_EXPOSURE: float = 0.50
    SIDEWAYS_EXPOSURE: float = 0.85
    BULL_EXPOSURE: float = 1.00

    # Score Smoothing
    SCORE_SMOOTHING_WEIGHT: float = 0.55
    SCORE_SMOOTHING_WEIGHT_BEAR: float = 0.80
    SCORE_SMOOTHING_MAX_AGE_DAYS: int = 3

    # Recommendation Hysteresis (prevents flip-flops at threshold boundaries)
    HYSTERESIS_BUFFER: float = 3.0
    HYSTERESIS_PROXIMITY_BOOST: float = 1.5

    # ML Tag Control (disabled until model accuracy > 60%)
    ML_TAG_IN_RECOMMENDATION: bool = False

    # Sector Cap Enforcement
    SECTOR_CAP_ENFORCE_HOLDINGS: bool = True

    # Liquidity Filter
    MIN_AVG_DAILY_VOLUME: int = 50000
    ILLIQUID_SCORE_PENALTY: float = 15.0

    # Cache Retention
    CACHE_MAX_AGE_DAYS: int = 7

    # Extreme Volatility
    MAX_SAFE_VOLATILITY: float = 80.0

    # Rate Limiting (consolidated from src/config.py — CB-05; REQUEST_DELAY used by nse_scraper)
    REQUEST_DELAY: float = 0.5
    REQUESTS_PER_MIN: int = 20  # reserved; yfinance wrapper uses internal rate control
    RETRY_LIMIT: int = 3  # reserved; analyzer uses RETRY_ATTEMPTS
    RETRY_BACKOFF: int = 2  # reserved

    # Market Cap Thresholds in INR crores (consolidated from src/config.py — CB-05)
    MARKET_CAP_MEGA: int = 200000
    MARKET_CAP_LARGE: int = 50000
    MARKET_CAP_MID: int = 10000
    MARKET_CAP_SMALL: int = 2000

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
    """Update configuration parameters (thread-safe). Validates after mutation; rolls back on failure."""
    global CONFIG
    with _CONFIG_LOCK:
        _snapshot = {k: getattr(CONFIG, k) for k in kwargs if hasattr(CONFIG, k)}
        for key, value in kwargs.items():
            if hasattr(CONFIG, key):
                setattr(CONFIG, key, value)
            else:
                print(f"Warning: Unknown configuration parameter: {key}")
        try:
            _validate_config(CONFIG)
        except ValueError:
            for k, v in _snapshot.items():
                setattr(CONFIG, k, v)
            raise

_VALIDATION_RULES: dict = {
    'STRONG_BUY_THRESHOLD': (float, 50, 100),
    'BUY_THRESHOLD': (float, 30, 100),
    'HOLD_THRESHOLD': (float, 10, 90),
    'SECTOR_CAP': (int, 1, 50),
    'CATEGORY_SECTOR_CAP': (int, 1, 20),
    'MAX_WORKERS': (int, 1, 20),
    'BATCH_SIZE': (int, 1, 50),
    'TIMEOUT_SECONDS': (int, 10, 600),
    'RETRY_ATTEMPTS': (int, 0, 10),
    'CACHE_EXPIRY_HOURS': (int, 1, 168),
    'CACHE_MAX_AGE_DAYS': (int, 1, 30),
    'SCORE_SMOOTHING_WEIGHT': (float, 0.0, 1.0),
    'SCORE_SMOOTHING_MAX_AGE_DAYS': (int, 1, 14),
    'HYSTERESIS_BUFFER': (float, 0.0, 10.0),
    'BEAR_EXPOSURE': (float, 0.0, 1.0),
    'SIDEWAYS_EXPOSURE': (float, 0.0, 1.0),
    'BULL_EXPOSURE': (float, 0.0, 1.0),
    'FUNDAMENTAL_WEIGHT': (float, 0.0, 1.0),
    'TECHNICAL_WEIGHT': (float, 0.0, 1.0),
    'UNDERVALUATION_WEIGHT': (float, 0.0, 1.0),
    'MAX_SINGLE_STOCK_WEIGHT': (float, 1.0, 100.0),
    'MAX_ALLOCATION_PCT': (float, 0.01, 1.0),
    'MIN_ALLOCATION_PERCENTAGE': (float, 0.0, 50.0),
    'TARGET_PORTFOLIO_SIZE': (int, 1, 100),
    'MAX_PORTFOLIO_POSITIONS': (int, 1, 100),
    'DEFAULT_PORTFOLIO_AMOUNT': (float, 1000, 1e9),
    'SECTOR_REDUCE_MIN_SCORE': (float, 0, 100),
    'MAX_SAFE_VOLATILITY': (float, 10, 200),
    'ILLIQUID_SCORE_PENALTY': (float, 0, 50),
    'MIN_AVG_DAILY_VOLUME': (int, 10_000, 10_000_000),
    'PROFIT_BOOKING_THRESHOLD': (float, 0.0, 1.0),
    'REBALANCE_PROFIT_THRESHOLD': (float, 0.0, 1.0),
    'SELL_THRESHOLD': (float, 0, 100),
    'EMERGENCY_EXIT_LOSS': (float, -1.0, 0.0),
    'EMERGENCY_EXIT_SCORE': (float, 0, 100),
}

def _validate_config(cfg: 'AnalysisConfig') -> None:
    """Validate config values are within acceptable ranges. Raises ValueError on failure."""
    errors = []
    for key, (expected_type, lo, hi) in _VALIDATION_RULES.items():
        if not hasattr(cfg, key):
            continue
        val = getattr(cfg, key)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            errors.append(f"{key}: expected numeric, got {type(val).__name__}")
            continue
        if val < lo or val > hi:
            errors.append(f"{key}={val} out of range [{lo}, {hi}]")
    thr_sb = getattr(cfg, 'STRONG_BUY_THRESHOLD', 70)
    thr_b = getattr(cfg, 'BUY_THRESHOLD', 60)
    thr_h = getattr(cfg, 'HOLD_THRESHOLD', 50)
    thr_s = getattr(cfg, 'SELL_THRESHOLD', 40)
    if not (thr_sb > thr_b > thr_h > thr_s):
        errors.append(f"Thresholds must satisfy STRONG_BUY({thr_sb}) > BUY({thr_b}) > HOLD({thr_h}) > SELL({thr_s})")
    _fw = getattr(cfg, 'FUNDAMENTAL_WEIGHT', 0.4)
    _tw = getattr(cfg, 'TECHNICAL_WEIGHT', 0.3)
    _uw = getattr(cfg, 'UNDERVALUATION_WEIGHT', 0.3)
    if _fw < 0 or _tw < 0 or _uw < 0:
        errors.append(f"Scoring weights must be non-negative: F={_fw}, T={_tw}, U={_uw}")
    _w_sum = _fw + _tw + _uw
    if abs(_w_sum - 1.0) > 0.01:
        errors.append(f"Scoring weights must sum to 1.0, got {_w_sum:.3f} (FUNDAMENTAL+TECHNICAL+UNDERVALUATION)")
    if errors:
        raise ValueError("[CONFIG] Validation failed:\n  " + "\n  ".join(errors))


def load_config_from_file(file_path: str = 'config.json') -> None:
    """Load configuration from a JSON file and update the global CONFIG instance.
    Validates inside the lock; rolls back to snapshot on validation failure.
    """
    global CONFIG
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _CONFIG_LOCK:
            valid_fields = {fld.name for fld in fields(CONFIG)}
            _snapshot = {k: getattr(CONFIG, k) for k in valid_fields}
            for key, value in data.items():
                if key in valid_fields:
                    setattr(CONFIG, key, value)
            try:
                _validate_config(CONFIG)
            except ValueError:
                for k, v in _snapshot.items():
                    setattr(CONFIG, k, v)
                raise
        print(f"[CONFIG] Loaded and validated settings from {file_path}")
    except ValueError as ve:
        print(f"[CONFIG] {ve}")
        raise
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
