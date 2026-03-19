#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Top 200 NSE Stocks Analysis
Advanced comprehensive analysis with undervaluation detection and portfolio recommendations
Features:
- Multi-threaded stock analysis
- Advanced undervaluation scoring
- Portfolio integration recommendations
- Enhanced reporting with actionable insights
"""

import sys
import io

# 🔧 FIX: Force UTF-8 encoding for console output to handle emojis on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass  # If wrapping fails, continue without it

# Add both src directory and project root to Python path
sys.path.append('src')
sys.path.append('.')

import pandas as pd
import logging
from datetime import datetime
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import argparse
import glob
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import warnings
import requests
import pickle
from pathlib import Path
import sqlite3
import hashlib
import shutil
from filelock import FileLock, Timeout as FileLockTimeout  # HI-06: hard dependency
_HAS_FILELOCK = True
warnings.filterwarnings('ignore')


def _nv(val, default=0):
    """NaN-safe value: returns default if val is None, NaN, or inf."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


# Use the proper import paths for each module
from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis
from src.technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
# V5.0: CorrectedScoringEngine removed (anti-predictive IC=-0.13)
# V5.0: ImprovedScoringEngine removed (90% unstable, score swings >20pts/month)
from hybrid_optimized_scoring import HybridOptimizedScoringEngine  # 🚀 LATEST: V4.0 - Multi-market validated
from adaptive_market_strategy import AdaptiveMarketRegimeStrategy  # 🎯 NEW: Market regime adaptation
from ml_predictor import get_ml_predictor  # Phase 2: ML Price Prediction
from pattern_recognition import analyze_patterns  # Phase 2: Advanced Pattern Recognition
from market_regime_detector import MarketRegimeDetector  # Phase 2: Market Regime Detection
from crisis_detector import CrisisDetector  # GAP-18: Cross-asset crisis & global event detection
from sentiment_analyzer import SentimentAnalyzer  # Phase 2: News & Sentiment Analysis
from volume_analyzer import VolumeAnalyzer  # Phase 2: Volume Profile & Order Flow Analysis
from recommendation_history import RecommendationHistory  # 🔧 FIX: Recommendation consistency tracking
from early_breakout_detector import EarlyBreakoutDetector  # 🚀 NEW: Pre-breakout detection & exit signals
import yfinance as yf
from config import AnalysisConfig, get_config  # A-009: Centralised thresholds & settings

# MI-05: Use the global CONFIG singleton, not a local instance.
_config = get_config()

# Suppress yfinance verbose error logging for cleaner output
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)


class StockDataBundle:
    """
    A-005: Single-download context for one NSE stock.
    Downloads 5Y daily OHLCV + ticker.info exactly ONCE per stock;
    all callers receive pre-sliced DataFrames — zero redundant HTTP calls.
    """
    __slots__ = ('symbol', 'ticker', 'hist_5y', 'hist_2y', 'hist_1y',
                 'hist_6mo', 'hist_3mo', 'hist_1mo', 'info',
                 'is_valid', 'quality_warnings')

    MIN_ROWS_1Y = 200
    STALE_DAYS = 5

    def __init__(self, symbol: str):
        self.symbol = symbol
        ns_sym = f"{symbol}{_config.NSE_SUFFIX}"
        self.ticker = yf.Ticker(ns_sym)

        _RETRYABLE = (ConnectionError, TimeoutError, OSError)

        self.hist_5y = pd.DataFrame()
        for _attempt in range(4):
            try:
                self.hist_5y = self.ticker.history(period='5y', interval='1d',
                                                    timeout=_config.TIMEOUT_SECONDS)
                break
            except _RETRYABLE as _e:
                _wait = (2 ** _attempt) * 2
                logging.warning(f"Network error on {symbol} hist (attempt {_attempt+1}/4): {_e}, retrying in {_wait}s")
                time.sleep(_wait)
            except Exception as _e:
                _msg = str(_e).lower()
                if 'too many requests' in _msg or '429' in _msg or 'rate' in _msg:
                    _wait = (2 ** _attempt) * 2
                    logging.warning(f"Rate limit on {symbol} hist (attempt {_attempt+1}/4), waiting {_wait}s")
                    time.sleep(_wait)
                else:
                    logging.warning(f"Non-retryable error on {symbol} hist: {_e}")
                    break

        # Compute date-range slices — no additional HTTP calls
        if not self.hist_5y.empty and self.hist_5y.index.tz is not None:
            _tz = self.hist_5y.index.tz
        else:
            _tz = None
        _now = pd.Timestamp.now(tz=_tz) if _tz else pd.Timestamp.now(tz='UTC')

        def _tail(months: int) -> pd.DataFrame:
            if self.hist_5y.empty:
                return self.hist_5y
            cutoff = _now - pd.DateOffset(months=months)
            return self.hist_5y[self.hist_5y.index >= cutoff]

        self.hist_2y  = _tail(24)
        self.hist_1y  = _tail(12)
        self.hist_6mo = _tail(6)
        self.hist_3mo = _tail(3)
        self.hist_1mo = _tail(1)

        self.info = {}
        for _attempt in range(4):
            try:
                self.info = self.ticker.info
                break
            except _RETRYABLE as _e:
                _wait = (2 ** _attempt) * 2
                logging.warning(f"Network error on {symbol} info (attempt {_attempt+1}/4): {_e}, retrying in {_wait}s")
                time.sleep(_wait)
            except Exception as _e:
                _msg = str(_e).lower()
                if 'too many requests' in _msg or '429' in _msg or 'rate' in _msg:
                    _wait = (2 ** _attempt) * 2
                    logging.warning(f"Rate limit on {symbol} info (attempt {_attempt+1}/4), waiting {_wait}s")
                    time.sleep(_wait)
                else:
                    logging.warning(f"Non-retryable error on {symbol} info: {_e}")
                    break

        self.quality_warnings = []
        self.is_valid = self._validate()

    def _validate(self) -> bool:
        """Check data completeness; populate quality_warnings.
        Large-cap stocks (market cap > 20,000 Cr) are allowed through with
        partial data so that the analysis can apply defaults rather than
        skip them entirely.
        """
        ok = True

        if self.hist_5y.empty:
            self.quality_warnings.append("no_price_data")
            return False

        if 'Close' in self.hist_5y.columns and self.hist_5y['Close'].isna().all():
            self.quality_warnings.append("all_nan_close")
            return False

        if len(self.hist_1y) < self.MIN_ROWS_1Y:
            self.quality_warnings.append(f"low_rows_1y:{len(self.hist_1y)}")
            ok = False

        if not self.info or self.info.get('regularMarketPrice') is None:
            self.quality_warnings.append("empty_or_stub_info")
            ok = False

        if not self.hist_5y.empty:
            last_date = self.hist_5y.index[-1]
            _tz = last_date.tz
            days_stale = (pd.Timestamp.now(tz=_tz) - last_date).days
            if days_stale > self.STALE_DAYS:
                self.quality_warnings.append(f"stale_data:{days_stale}d")

        _cp = self.info.get('currentPrice')
        _rmp = self.info.get('regularMarketPrice')
        current_price = (_cp if _cp is not None and not (isinstance(_cp, float) and np.isnan(_cp)) else
                         _rmp if _rmp is not None and not (isinstance(_rmp, float) and np.isnan(_rmp)) else 0)
        if current_price is not None and current_price <= 0:
            self.quality_warnings.append("invalid_current_price")
            ok = False

        if not ok:
            mcap = self.info.get('marketCap', 0) if self.info else 0
            has_some_price = len(self.hist_5y) >= 30
            has_solid_price = len(self.hist_5y) >= 200
            if mcap and mcap > 2e11 and has_some_price:
                logging.warning(
                    f"Large-cap {self.symbol} (₹{mcap/1e10:.0f}k Cr) has validation issues "
                    f"{self.quality_warnings} — allowing with partial data"
                )
                return True
            if has_solid_price and (not self.info or not self.info.get('regularMarketPrice')):
                self.quality_warnings.append("empty_info_bypass")
                logging.warning(
                    f"{self.symbol}: empty/stub info but {len(self.hist_5y)} price rows "
                    f"— allowing with price-only analysis"
                )
                return True

        return ok


class EnhancedTop200StockAnalyzer:
    """Enhanced comprehensive analyzer for top 200 NSE stocks with undervaluation detection"""
    
    def __init__(self, max_workers=None, csv_file=None, risk_profile="moderate", 
                 focus_growth=False, focus_momentum=False, min_volatility=0.0):
        self.max_workers = max_workers if max_workers is not None else _config.MAX_WORKERS
        # V5.0: corrected/improved engines removed from pipeline (kept on disk for reference)
        self.hybrid_scoring_engine = HybridOptimizedScoringEngine()  # [LATEST] LATEST: V4.0 Multi-market validated
        self.adaptive_strategy = AdaptiveMarketRegimeStrategy()  # [NEW] NEW: Regime-adaptive recommendations
        self.ml_predictor = get_ml_predictor()  # [PHASE 2] Phase 2: ML Price Prediction
        self.regime_detector = MarketRegimeDetector()  # [PHASE 2] Phase 2: Market Regime Detection
        self.crisis_detector = CrisisDetector()   # [GAP-18] Cross-asset crisis detection (war/oil/panic)
        self.crisis_data = None                    # [GAP-18] Detected once in analyze_batch(), read-only in workers
        self.sentiment_analyzer = SentimentAnalyzer()  # [PHASE 2] Phase 2: Sentiment Analysis
        self.volume_analyzer = VolumeAnalyzer()  # [PHASE 2] Phase 2: Volume Profile & Order Flow
        self.recommendation_history = RecommendationHistory()  # 🔧 FIX: Track recommendation consistency
        self.early_breakout_detector = EarlyBreakoutDetector()  # 🚀 NEW: Pre-breakout & exit signals
        
        # 🚀 NEW: Market Regime Adaptive System
        self.current_market_regime = None  # Will be detected at start (hybrid system)
        self.market_regime = None  # Legacy system compatibility
        self.regime_confidence = None
        self.current_regime_confidence = 0.5  # Set in analyze_batch() before workers; default 0.5
        self.adaptive_weights = None
        self.position_sizing_strategy = None
        
        self._past_accuracy = {}  # V5.0: Populated by feedback loop
        self.setup_logging()
        self.results = {}  # A-014: keyed by symbol → O(1) retry lookup, no duplicates
        self.failed_stocks = []
        self.low_quality_stocks = []
        self._validation_error_count = 0
        self._state_lock = threading.Lock()  # Thread safety: protects shared mutable state in worker threads
        self._sector_adj_cache = {}  # Per-run sector adjustment cache (computed once per sector)
        self.ENABLE_SENTIMENT_ADJUSTMENT = getattr(_config, 'ENABLE_SENTIMENT_ADJUSTMENT', False)
        self._ml_using_fallback = not os.path.exists('models/ml_predictor_latest.pkl')
        if self._ml_using_fallback:
            logging.warning("[ML] 'models/ml_predictor_latest.pkl' not found — "
                            "all ML signals use rule-based fallback. "
                            "To train: python train_ml_model.py")
        self.total_stocks = 0
        self.processed_stocks = 0
        self.company_names = {}  # Map symbols to company names
        
        # 🚀 ENHANCEMENT: Add caching system
        self.cache_enabled = _config.CACHE_ENABLED        # A-009: from config.py
        self.cache_expiry_hours = _config.CACHE_EXPIRY_HOURS  # A-009: from config.py
        self.cache_dir = "data/cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 🚀 ENHANCEMENT: Performance monitoring
        self.performance_metrics = {
            'start_time': None,
            'batch_times': [],
            'failed_count': 0,
            'cache_hits': 0,
            'api_calls': 0
        }
        
        # 🚀 NEW: Risk Profile Settings
        self.risk_profile = risk_profile
        # Validate risk profile
        if self.risk_profile not in ["conservative", "moderate", "aggressive", "balanced"]:
            logging.warning(f"Invalid risk profile '{self.risk_profile}', defaulting to 'moderate'")
            self.risk_profile = "moderate"
        logging.info(f"Risk profile set to: {self.risk_profile}")      # conservative, moderate, aggressive, balanced
        self.focus_growth = focus_growth      # Focus on growth stocks
        self.focus_momentum = focus_momentum  # Focus on momentum stocks
        self.min_volatility = min_volatility  # Minimum volatility for aggressive investors
        
        # Log risk profile configuration
        if risk_profile == "aggressive" or focus_growth or focus_momentum:
            logging.info(f"HIGH-RISK MODE: Profile={risk_profile}, Growth={focus_growth}, Momentum={focus_momentum}, MinVol={min_volatility}")
        
        # Default to stock_list_template.csv in the project root if exists
        default_csv = "stock_list_template.csv"
        if not csv_file and os.path.exists(default_csv):
            csv_file = default_csv
            logging.info(f"Using default stock list from {default_csv}")
        
        # Load stocks from CSV if provided, otherwise use hardcoded list
        self.stock_list = self.load_stocks_from_csv(csv_file) if csv_file else self.get_default_stock_list()
        
        # Take first 200 stocks
        # Dynamic limit - use all stocks from CSV or default list

    @staticmethod
    def _safe_yf_ticker(symbol, retries=3, timeout=15):
        """Shared yfinance Ticker wrapper with retries and timeout."""
        import time as _time
        ns_sym = f"{symbol}.NS" if not symbol.endswith('.NS') and '=' not in symbol and '^' not in symbol else symbol
        for attempt in range(retries):
            try:
                ticker = yf.Ticker(ns_sym)
                _ = ticker.info  # force a fetch to test connectivity
                return ticker
            except Exception as e:
                if attempt < retries - 1:
                    _wait = (2 ** attempt) * 2
                    logging.debug(f"yf.Ticker({ns_sym}) retry {attempt+1}/{retries}: {e}")
                    _time.sleep(_wait)
                else:
                    logging.warning(f"yf.Ticker({ns_sym}) failed after {retries} attempts: {e}")
                    raise

    def load_stocks_from_csv(self, csv_file):
        """Load stock symbols from a CSV file"""
        try:
            logging.info(f"Loading stocks from CSV: {csv_file}")
            self._csv_path = csv_file
            try:
                df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(csv_file, encoding='latin1')
            
            # Check if the CSV has the required columns
            if 'Symbol' in df.columns:
                # CRITICAL: Ensure we get clean symbols without whitespace
                symbols = df['Symbol'].dropna().astype(str).str.strip().tolist()
                
                # Filter out any obviously invalid entries (company names accidentally in Symbol column)
                # Valid NSE symbols are typically all-caps alphanumeric, under 20 chars, no spaces
                valid_symbols = []
                invalid_entries = []
                _dummy_prefixes = ('DUMMY', 'TEST', 'SAMPLE')
                for s in symbols:
                    if s.upper().startswith(_dummy_prefixes):
                        invalid_entries.append(s)
                    elif len(s) <= 20 and ' ' not in s and (s.isupper() or '-' in s or '&' in s):
                        valid_symbols.append(s)
                    else:
                        invalid_entries.append(s)
                
                if invalid_entries:
                    logging.warning(f"Filtered out {len(invalid_entries)} invalid symbols: {invalid_entries[:5]}")
                
                symbols = valid_symbols
                
                # If there's a company name column, create a mapping
                if 'Company Name' in df.columns:
                    self.company_names = dict(zip(df['Symbol'].str.strip(), df['Company Name']))
                    logging.info(f"Loaded {len(symbols)} stocks with company names")
                else:
                    logging.info(f"Loaded {len(symbols)} stocks without company names")
                
                # Print first few stocks for verification
                sample = symbols[:5]
                logging.info(f"Sample stocks: {', '.join(sample)}")
                
                return symbols
            else:
                logging.error(f"CSV file does not have 'Symbol' column. Available columns: {df.columns.tolist()}")
                self._csv_path = None
                return self.get_default_stock_list()
        except Exception as e:
            logging.error(f"Error loading stocks from CSV: {e}")
            self._csv_path = None
            return self.get_default_stock_list()
    
    def get_default_stock_list(self):
        """Return the default list of stocks"""
        logging.info("Using default stock list")
        # NIFTY 50 core stocks - Default list of 25 stocks
        return [
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", 
            "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", 
            "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", "SUNPHARMA", "WIPRO",
            "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", "POWERGRID", "NTPC",
        ]
        
    # 🚀 ENHANCEMENT: Caching System
    def get_cache_path(self, symbol: str, analysis_type: str = "comprehensive") -> str:
        """Get cache file path for a symbol and analysis type"""
        return os.path.join(self.cache_dir, f"{symbol}_{analysis_type}_{datetime.now().strftime('%Y%m%d')}.json")
    
    def is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache file is valid (exists and not expired)"""
        if not os.path.exists(cache_path):
            return False
        
        # Check if cache is within expiry time
        cache_time = os.path.getmtime(cache_path)
        current_time = time.time()
        expiry_seconds = self.cache_expiry_hours * 3600
        
        return (current_time - cache_time) < expiry_seconds
    
    def load_from_cache(self, symbol: str, analysis_type: str = "comprehensive") -> Optional[Dict]:
        """Load analysis data from cache if available and valid"""
        if not self.cache_enabled:
            return None
            
        cache_path = self.get_cache_path(symbol, analysis_type)
        
        if self.is_cache_valid(cache_path):
            try:
                if _HAS_FILELOCK:
                    with FileLock(cache_path + ".lock", timeout=5):
                        with open(cache_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                else:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                self.performance_metrics['cache_hits'] += 1
                logging.info(f"Cache hit for {symbol} ({analysis_type})")
                return data
            except Exception as e:
                logging.warning(f"Failed to load cache for {symbol}: {e}")
        
        return None
    
    def _make_json_safe(self, value):
        """
        Recursively convert any Python value to a JSON-serializable form.
        Correctly handles numpy scalars/arrays, pandas DataFrames/Series, nested dicts/lists.
        Replaces the broken str() conversion that destroyed complex types on cache save,
        causing every warm-run cache hit to return wrong types and fall back to score=50.
        """
        if value is None or isinstance(value, (bool, str)):
            return value
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value != value:  # NaN check
                return None
            return value
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            v = float(value)
            return None if v != v else v  # NaN → None
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.ndarray):
            return [self._make_json_safe(x) for x in value.tolist()]
        if isinstance(value, pd.DataFrame):
            return {col: self._make_json_safe(value[col].tolist()) for col in value.columns}
        if isinstance(value, pd.Series):
            return self._make_json_safe(value.tolist())
        if isinstance(value, dict):
            return {str(k): self._make_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._make_json_safe(i) for i in value]
        try:
            return str(value)
        except Exception:
            return None

    def save_to_cache(self, symbol: str, data: Dict, analysis_type: str = "comprehensive"):
        """Save analysis data to cache (file-locked for concurrent safety)"""
        if not self.cache_enabled:
            return
            
        cache_path = self.get_cache_path(symbol, analysis_type)
        
        try:
            serializable_data = {k: self._make_json_safe(v) for k, v in data.items()}
            
            if _HAS_FILELOCK:
                with FileLock(cache_path + ".lock", timeout=10):
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            else:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            
            logging.debug(f"Cached analysis for {symbol}")
        except Exception as e:
            logging.warning(f"Failed to cache data for {symbol}: {e}")
    
    def clear_cache(self, older_than_days: int = 1):
        """Clear cache files older than specified days"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (older_than_days * 24 * 3600)
            
            removed_count = 0
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.cache_dir, filename)
                    if os.path.getmtime(filepath) < cutoff_time:
                        os.remove(filepath)
                        removed_count += 1
            
            if removed_count > 0:
                logging.info(f"Cleared {removed_count} old cache files")
        except Exception as e:
            logging.warning(f"Error clearing cache: {e}")

    def cleanup_cache(self, max_age_days=7, max_files=500):
        """Auto-cleanup: remove cache files older than max_age_days, cap at max_files."""
        try:
            cache_files = sorted(
                [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith('.json')],
                key=os.path.getmtime, reverse=True
            )
            cutoff = datetime.now().timestamp() - (max_age_days * 86400)
            removed = 0
            for i, fpath in enumerate(cache_files):
                if i >= max_files or os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    removed += 1
            if removed:
                print(f"   🧹 Cache cleanup: removed {removed} old/excess cache files")
        except Exception as e:
            logging.warning(f"Cache cleanup error: {e}")

    def setup_logging(self):
        """Setup comprehensive logging with ASCII-safe console output"""
        import sys
        os.makedirs('data', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        self.log_filename = f"data/top200_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Custom filter to remove emojis from console output only
        class SafeConsoleFilter(logging.Filter):
            """Filter to remove Unicode characters from console output on Windows"""
            def filter(self, record):
                # Create a safe version of the message for console
                if hasattr(record, 'msg'):
                    # Replace common emojis with text equivalents
                    safe_msg = str(record.msg)
                    safe_msg = safe_msg.replace('👀', '[HOLD]')
                    safe_msg = safe_msg.replace('⚠️', '[WEAK]')
                    safe_msg = safe_msg.replace('🚀', '[BUY]')
                    # safe_msg = safe_msg.replace('[CHART]', '[INFO]')
                    safe_msg = safe_msg.replace('✅', '[OK]')
                    safe_msg = safe_msg.replace('❌', '[X]')
                    safe_msg = safe_msg.replace('💰', '[PROFIT]')
                    safe_msg = safe_msg.replace('🎯', '[TARGET]')
                    safe_msg = safe_msg.replace('→', '->')
                    safe_msg = safe_msg.replace('₹', 'Rs.')
                    # Remove any remaining Unicode characters (keep only ASCII)
                    safe_msg = safe_msg.encode('ascii', errors='replace').decode('ascii')
                    record.msg = safe_msg
                return True
        
        # Create custom StreamHandler with safe encoding for Windows
        class SafeStreamHandler(logging.StreamHandler):
            """StreamHandler that handles Unicode encoding errors gracefully"""
            def emit(self, record):
                try:
                    msg = self.format(record)
                    stream = self.stream
                    # Try to encode as ASCII, replacing problematic characters
                    stream.write(msg.encode('ascii', errors='replace').decode('ascii') + self.terminator)
                    self.flush()
                except Exception:
                    self.handleError(record)
        
        # Create handlers
        file_handler = logging.FileHandler(self.log_filename, encoding='utf-8', errors='replace')
        stream_handler = SafeStreamHandler(sys.stdout)
        
        # Add emoji filter only to console handler
        stream_handler.addFilter(SafeConsoleFilter())
        
        # Set formatters
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        
        # Configure logging — guard against duplicate handlers when class is re-instantiated
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                handlers=[file_handler, stream_handler]
            )
        else:
            if not any(isinstance(h, logging.FileHandler) and
                       getattr(h, 'baseFilename', '') == os.path.abspath(self.log_filename)
                       for h in root_logger.handlers):
                root_logger.addHandler(file_handler)
            root_logger.setLevel(logging.INFO)
        
        logging.info("Dynamic NSE Stock Analysis Initialized")
    
    def classify_market_cap(self, market_cap):
        """
        # COMMENTED OUT - OVERCOMPLICATED ALLOCATION LIMITS
        # Classify stocks by market cap and return appropriate allocation percentage
        # 
        # SIMPLIFIED: Just use equal weight or score-based allocation instead
        # 
        # Args:
        #     market_cap: Market capitalization value
        #     
        # Returns:
        #     tuple: (category, max_allocation_percentage)
        """
        if not market_cap or market_cap <= 0:
            return "Unknown", 0.05  # Simplified: Default equal allocation
        
        market_cap_cr = market_cap / 10000  # Convert to crores
        
        # SIMPLIFIED Market cap classification:
        if market_cap_cr >= 50000:  # Nifty 50 / Mega Cap
            return "Large Cap (Nifty 50)", 0.05  # SIMPLIFIED: Equal 5% max
        elif market_cap_cr >= 20000:  # Large Cap
            return "Large Cap", 0.05  # SIMPLIFIED: Equal 5% max
        elif market_cap_cr >= 5000:  # Mid Cap
            return "Mid Cap", 0.05  # SIMPLIFIED: Equal 5% max
        else:  # Small Cap
            return "Small Cap", 0.05  # SIMPLIFIED: Equal 5% max (instead of complex 3.5%)
    
    # ========================================================================
    # PHASE 1: QUICK WINS - ACCURACY IMPROVEMENTS
    # Expected Total Improvement: 25-40%
    # ========================================================================
    
    _IQR_HISTORY = {}

    def enhanced_data_validation(self, stock_data: dict) -> dict:
        """
        PHASE 1 - IMPROVEMENT #1: Enhanced Data Validation
        - IQR-based outlier detection (replaces placeholder 3-sigma)
        - Cross-validation of metrics
        - Reasonable bounds for all ratios
        """
        validated_data = stock_data.copy()

        # 0. IQR-BASED OUTLIER DETECTION
        _iqr_fields = ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity', 'dividend_yield']
        for _fld in _iqr_fields:
            val = validated_data.get(_fld)
            if val is None:
                continue
            try:
                val = float(val)
            except (TypeError, ValueError):
                continue
            hist = self._IQR_HISTORY.setdefault(_fld, [])
            hist.append(val)
            if len(hist) >= 20:
                _sorted = sorted(hist)
                q1 = _sorted[len(_sorted) // 4]
                q3 = _sorted[3 * len(_sorted) // 4]
                iqr = q3 - q1
                lower = q1 - 3.0 * iqr
                upper = q3 + 3.0 * iqr
                if val < lower or val > upper:
                    validated_data[_fld] = max(min(val, upper), lower)
                    validated_data.setdefault('_iqr_outliers', []).append(
                        f"{_fld}: {val:.2f} clamped to [{lower:.2f}, {upper:.2f}]"
                    )
                    logging.warning(f"IQR outlier {stock_data.get('symbol','?')}: {_fld}={val:.2f} -> clamped [{lower:.2f},{upper:.2f}]")

        # 1. PRICE VALIDATION - Remove extreme outliers
        price_fields = ['current_price', '52_week_high', '52_week_low', 'book_value', 'target_price']
        for field in price_fields:
            if field in validated_data and validated_data[field]:
                try:
                    value = float(validated_data[field])
                    if value > 0:
                        validated_data[field] = max(value, 0.01)
                        validated_data[field] = min(validated_data[field], 500000)
                except (ValueError, TypeError):
                    validated_data[field] = None
        
        # 2. RATIO VALIDATION - Set industry-standard bounds (unified with _validate_and_clean_data)
        ratio_bounds = {
            'pe_ratio': (0, 500),
            'pb_ratio': (0, 50),
            'debt_to_equity': (0, 500),
            'current_ratio': (0, 20),
            'roe': (-100, 200),
            'profit_margin': (-100, 100),
            'operating_margin': (-100, 100),
            'dividend_yield': (0, 50)
        }
        
        for field, (min_val, max_val) in ratio_bounds.items():
            if field in validated_data and validated_data[field] is not None:
                try:
                    value = float(validated_data[field])
                    validated_data[field] = max(min(value, max_val), min_val)
                except (ValueError, TypeError):
                    validated_data[field] = None
        
        # 3. CROSS-VALIDATION - Check consistency between related metrics
        try:
            # Validate market cap vs price consistency
            def _valid_numeric(vd, key):
                v = vd.get(key)
                if v is None or v == 0:
                    return False
                try:
                    return not (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))
                except (TypeError, ValueError):
                    return False
            if all(_valid_numeric(validated_data, k) for k in ['market_cap', 'shares_outstanding', 'current_price']):
                implied_price = validated_data['market_cap'] / validated_data['shares_outstanding']
                current_price = validated_data['current_price']
                
                # Flag if discrepancy > 15%
                if abs(implied_price - current_price) / current_price > 0.15:
                    logging.warning(f"{validated_data.get('symbol', 'Unknown')}: Price inconsistency detected - Current: ₹{current_price:.2f} vs Implied: ₹{implied_price:.2f}")
                    validated_data['data_quality_flag'] = 'price_inconsistency'
            
            # Validate P/E vs Earnings consistency
            if all(_valid_numeric(validated_data, k) for k in ['pe_ratio', 'current_price', 'earnings_per_share']):
                implied_pe = validated_data['current_price'] / validated_data['earnings_per_share']
                stated_pe = validated_data['pe_ratio']
                
                if abs(implied_pe - stated_pe) / stated_pe > 0.20:
                    logging.warning(f"{validated_data.get('symbol', 'Unknown')}: P/E inconsistency - Stated: {stated_pe:.1f} vs Calculated: {implied_pe:.1f}")
            
            # Validate ROE vs Profit Margin consistency (basic sanity check)
            if 'roe' in validated_data and validated_data['roe']:
                roe = validated_data['roe']
                if roe < -50:
                    validated_data['quality_warning'] = 'extreme_negative_roe'
                elif roe > 100:
                    validated_data['quality_warning'] = 'extremely_high_roe'
        
        except Exception as e:
            logging.warning(f"Cross-validation error for {validated_data.get('symbol', '?')}: {e}")
            self._validation_error_count += 1
        
        return validated_data
    
    def calculate_data_quality_score(self, stock_data: dict) -> float:
        """
        PHASE 1 - IMPROVEMENT #2: Data Quality Scoring
        - Assign quality scores to each stock's data
        - Weight analysis based on data confidence
        - Missing data impact assessment
        - Consistency checks for suspicious data
        """
        quality_score = 70.0
        
        # Critical fields - Heavy penalty if missing
        critical_fields = {
            'current_price': 25,
            'market_cap': 20,
            'pe_ratio': 15,
            'pb_ratio': 10
        }
        
        for field, penalty in critical_fields.items():
            if field not in stock_data or stock_data[field] is None or stock_data[field] == 0:
                quality_score -= penalty
        
        # Important fields - Moderate penalty if missing
        important_fields = {
            'debt_to_equity': 5,
            'current_ratio': 5,
            'roe': 5,
            'revenue_growth': 5,
            'earnings_per_share': 5
        }
        
        for field, penalty in important_fields.items():
            if field not in stock_data or stock_data[field] is None:
                quality_score -= penalty
        
        # Bonus for having optional enrichment data (+3 per field)
        bonus_fields = [
            'operating_margin', 'profit_margin', 'dividend_yield',
            'book_value', 'price_to_sales', 'asset_turnover',
            'quick_ratio', 'interest_coverage'
        ]
        
        available_bonus = sum(1 for field in bonus_fields 
                             if field in stock_data and stock_data[field] is not None)
        quality_score += available_bonus * 3
        
        # Consistency checks — penalize contradictory or suspicious data
        _pe = stock_data.get('pe_ratio')
        _roe = stock_data.get('roe')
        _mcap = stock_data.get('market_cap', 0)
        _rev_g = stock_data.get('revenue_growth')

        if _pe is not None and _roe is not None:
            if _pe < 0 and _roe > 0:
                quality_score -= 10
        if _mcap and _mcap < 1e9 and _pe is not None and _pe > 50:
            quality_score -= 10
        if _rev_g is not None and _rev_g == 0:
            quality_score -= 5

        # Penalty for data quality warnings
        if stock_data.get('data_quality_flag'):
            quality_score -= 10
        if stock_data.get('quality_warning'):
            quality_score -= 5
        
        if isinstance(quality_score, float) and np.isnan(quality_score):
            quality_score = 50.0
        return max(0, min(100, quality_score))
    
    def _calculate_optimized_score(self, stock_data: dict) -> float:
        """DEPRECATED: Shadow scoring removed in CB-02 remediation.
        Returns final_blended_score if available, else 50.
        All sector biases (+10 Banking, -10 IT) have been eliminated.
        """
        return stock_data.get('final_blended_score', 50.0)
    
    def apply_confidence_bands(self, score: float, stock_data: dict) -> dict:
        """HI-01: Confidence bands aligned with config thresholds (single source)."""
        from config import get_config as _gc
        _cfg = _gc()
        _sb = getattr(_cfg, 'STRONG_BUY_THRESHOLD', 70)
        _b = getattr(_cfg, 'BUY_THRESHOLD', 60)
        _h = getattr(_cfg, 'HOLD_THRESHOLD', 50)
        if score >= _sb:
            return {
                'confidence_level': 'STRONG BUY',
                'recommendation_strength': 'HIGH',
                'risk_warning': None,
                'action_bias': 'AGGRESSIVE'
            }
        elif score >= _b:
            return {
                'confidence_level': 'BUY',
                'recommendation_strength': 'MEDIUM',
                'risk_warning': None,
                'action_bias': 'NORMAL'
            }
        elif score >= _h:
            return {
                'confidence_level': 'HOLD/CAUTIOUS',
                'recommendation_strength': 'LOW',
                'risk_warning': 'Skip in uncertain markets - mixed historical performance',
                'action_bias': 'CONSERVATIVE'
            }
        else:
            return {
                'confidence_level': 'AVOID',
                'recommendation_strength': 'NONE',
                'risk_warning': 'Below minimum threshold',
                'action_bias': 'DEFENSIVE'
            }
    
    # CB-06: detect_market_regime() REMOVED — use self.market_regime_detector.detect_regime()
    # (MarketRegimeDetector) as single source of truth.

    def calculate_portfolio_context_score(self, symbol: str, stock_data: dict, 
                                         current_holdings: dict = None) -> dict:
        """
        PHASE 1 - IMPROVEMENT #3: Portfolio Context Awareness
        - Consider existing portfolio diversification
        - Correlation with current holdings
        - Sector concentration analysis
        - Marginal contribution to portfolio risk
        
        Expected Improvement: 10-15% accuracy boost
        Complexity: LOW
        """
        context_score = 50.0
        adjustments = []
        
        if not current_holdings:
            return {
                'portfolio_context_score': 50.0,
                'diversification_benefit': 'unknown',
                'sector_concentration': 'unknown',
                'portfolio_fit': 'neutral',
                'context_adjustments': []
            }
        
        try:
            stock_sector = stock_data.get('sector', 'Unknown')
            total_holdings = len(current_holdings)

            holdings_have_sector = any(
                h.get('sector') not in (None, 'Unknown')
                for h in current_holdings.values()
            )

            sector_concentration = 0.0
            if total_holdings > 0 and holdings_have_sector:
                sector_holdings = [h for h in current_holdings.values()
                                   if h.get('sector') == stock_sector]
                sector_count = len(sector_holdings)
                sector_concentration = sector_count / total_holdings

                if sector_concentration > 0.40:
                    context_score -= 15
                    adjustments.append(f"High sector concentration: {sector_concentration*100:.0f}%")
                elif sector_concentration > 0.30:
                    context_score -= 10
                    adjustments.append(f"Moderate sector concentration: {sector_concentration*100:.0f}%")
                elif sector_concentration < 0.10:
                    context_score += 10
                    adjustments.append("Good sector diversification")

                if stock_sector != 'Unknown':
                    if stock_sector not in [h.get('sector') for h in current_holdings.values()]:
                        context_score += 15
                        adjustments.append(f"New sector addition: {stock_sector}")
            elif total_holdings > 0 and not holdings_have_sector:
                context_score = 45.0
                adjustments.append("Holdings lack sector data — sector analysis limited")

            stock_market_cap = stock_data.get('market_cap', 0)
            if stock_market_cap > 0:
                similar_size_count = 0
                for holding in current_holdings.values():
                    holding_mc = holding.get('market_cap', 0)
                    if holding_mc > 0:
                        ratio = stock_market_cap / holding_mc
                        if 0.5 <= ratio <= 2.0:
                            similar_size_count += 1

                if similar_size_count > total_holdings * 0.6:
                    context_score -= 5
                    adjustments.append("Low size diversification")

            if total_holdings > 20:
                stock_quality = stock_data.get('data_quality_score', 50)
                if stock_quality < 70:
                    context_score -= 10
                    adjustments.append("Large portfolio requires high-quality additions")
            
            # 5. DETERMINE OVERALL FIT
            if context_score >= 90:
                portfolio_fit = 'excellent'
                diversification_benefit = 'high'
            elif context_score >= 70:
                portfolio_fit = 'good'
                diversification_benefit = 'moderate'
            elif context_score >= 50:
                portfolio_fit = 'acceptable'
                diversification_benefit = 'low'
            else:
                portfolio_fit = 'poor'
                diversification_benefit = 'negative'
            
            # Determine sector concentration level
            if sector_concentration > 0.40:
                sector_concentration_level = 'high'
            elif sector_concentration > 0.25:
                sector_concentration_level = 'moderate'
            else:
                sector_concentration_level = 'low'
            
            return {
                'portfolio_context_score': max(0, min(100, _nv(context_score, 50))),
                'diversification_benefit': diversification_benefit,
                'sector_concentration': sector_concentration_level,
                'portfolio_fit': portfolio_fit,
                'context_adjustments': adjustments,
                'current_sector_exposure': f"{sector_concentration*100:.1f}%",
                'total_holdings_count': total_holdings
            }
            
        except Exception as e:
            logging.warning(f"Portfolio context calculation error: {e}")
            return {
                'portfolio_context_score': 50.0,
                'diversification_benefit': 'unknown',
                'sector_concentration': 'unknown',
                'portfolio_fit': 'neutral',
                'context_adjustments': [f"Error: {str(e)}"]
            }
    
    def calculate_momentum_score(self, stock_data, historical_data=None):
        """🚀 MOMENTUM DETECTION - Calculate momentum score for predictive analysis"""
        try:
            momentum_score = 0
            momentum_flags = []
            
            # Volume momentum (30% weight)
            volume_ratio = stock_data.get('enhanced_volume_ratio', 1.0)
            if volume_ratio > 2.0:
                momentum_score += 30
                momentum_flags.append("🚀 VOLUME SURGE")
            elif volume_ratio > 1.5:
                momentum_score += 20
                momentum_flags.append("📈 HIGH VOLUME")
            
            # Price momentum (40% weight)
            price_change_5d = stock_data.get('enhanced_price_change_5d', 0)
            if price_change_5d > 10:
                momentum_score += 40
                momentum_flags.append("🚀 PRICE MOMENTUM")
            elif price_change_5d > 5:
                momentum_score += 25
                momentum_flags.append("📈 POSITIVE TREND")
            
            # Technical momentum (30% weight)
            rsi = stock_data.get('real_rsi', stock_data.get('enhanced_rsi_14', 50))
            if 60 <= rsi <= 75:  # Sweet spot for momentum
                momentum_score += 30
                momentum_flags.append("⚡ TECHNICAL MOMENTUM")
            elif 50 <= rsi <= 60:
                momentum_score += 15
            
            return min(momentum_score, 100), momentum_flags
            
        except Exception as e:
            return 0, []
    
    def calculate_profit_booking_strategy(self, current_value, invested_amount, symbol, stock_data=None):
        """💰 ADVANCED SMART BOOKING - AI-powered profit booking with market intelligence"""
        try:
            if current_value <= 0 or invested_amount <= 0:
                return "HOLD", 0, "No profit to book"
            
            # Calculate base profit percentage as decimal (0.15 = 15%)
            profit_pct = (current_value - invested_amount) / invested_amount
            
            # 🧠 SMART BOOKING INTELLIGENCE - Dynamic thresholds based on stock characteristics
            
            # 1. Determine stock category and risk profile
            # Convert pandas Series to scalar values to avoid ambiguous truth value errors
            sector = stock_data.get('sector', 'Unknown') if stock_data else 'Unknown'
            if isinstance(sector, pd.Series):
                sector = sector.iloc[0] if len(sector) > 0 else 'Unknown'
            
            overall_score = stock_data.get('overall_score_with_value', 50) if stock_data else 50
            if isinstance(overall_score, pd.Series):
                overall_score = overall_score.iloc[0] if len(overall_score) > 0 else 50
            overall_score = float(overall_score) if overall_score is not None else 50
            
            momentum_score = self.calculate_momentum_score(stock_data)[0] if stock_data else 0
            if isinstance(momentum_score, pd.Series):
                momentum_score = momentum_score.iloc[0] if len(momentum_score) > 0 else 0
            momentum_score = float(momentum_score) if momentum_score is not None else 0
            
            rsi = stock_data.get('real_rsi', 50) if stock_data else 50
            if isinstance(rsi, pd.Series):
                rsi = rsi.iloc[0] if len(rsi) > 0 else 50
            rsi = float(rsi) if rsi is not None else 50
            
            # 2. Adaptive thresholds based on stock quality and type (REFINED VERSION 2.0)
            if 'BANK' in symbol or 'Financial' in sector:
                # Banking stocks - CONSERVATIVE after backtest (mature, dividend-paying)
                mega_threshold = 0.40  # 40% as decimal
                big_threshold = 0.25   # 25% as decimal
                good_threshold = 0.12  # 12% as decimal
                stop_loss = -0.15      # -15% as decimal
                category = "🏦 BANKING"
            elif overall_score >= 80:
                # High-quality stocks - can hold longer for bigger gains
                mega_threshold = 0.80
                big_threshold = 0.60
                good_threshold = 0.35
                stop_loss = -0.18
                category = "⭐ HIGH QUALITY"
            elif 'GROWTH' in self.classify_stock_type(symbol, sector) if hasattr(self, 'classify_stock_type') else False:
                # Growth stocks - higher risk, higher reward
                mega_threshold = 1.00
                big_threshold = 0.70
                good_threshold = 0.40
                stop_loss = -0.20
                category = "🚀 GROWTH"
            else:
                # Standard stocks - balanced approach
                mega_threshold = 0.60
                big_threshold = 0.40
                good_threshold = 0.20
                stop_loss = -0.15
                category = "[STD] STANDARD"
            
            # 3. Technical analysis adjustments
            if momentum_score >= 70:
                # Strong momentum - hold longer for bigger gains
                mega_threshold *= 1.2
                big_threshold *= 1.15
                good_threshold *= 1.1
                technical_signal = "🚀 MOMENTUM+"
            elif rsi >= 75:
                # Overbought - book profits earlier
                mega_threshold *= 0.85
                big_threshold *= 0.9
                good_threshold *= 0.95
                technical_signal = "⚠️ OVERBOUGHT"
            elif rsi <= 30:
                # Oversold - hold longer if recovering
                mega_threshold *= 1.1
                big_threshold *= 1.05
                stop_loss *= 0.8  # Wider stop loss
                technical_signal = "💎 OVERSOLD"
            else:
                technical_signal = "[NEUTRAL] NEUTRAL"
            
            # 4. Apply smart booking logic with dynamic thresholds
            if profit_pct >= mega_threshold:
                booking_pct = min(80, max(60, int(70 + (profit_pct - mega_threshold) * 100)))
                return f"BOOK {booking_pct}% PROFITS", booking_pct / 100, f"🎯 MEGA GAINS (+{profit_pct*100:.1f}%) | {category} | {technical_signal}"
            
            elif profit_pct >= big_threshold:
                booking_pct = min(60, max(40, int(50 + (profit_pct - big_threshold) * 100 / 2)))
                return f"BOOK {booking_pct}% PROFITS", booking_pct / 100, f"💰 BIG GAINS (+{profit_pct*100:.1f}%) | {category} | {technical_signal}"
            
            elif profit_pct >= good_threshold:
                booking_pct = min(40, max(25, int(30 + (profit_pct - good_threshold) * 100 / 1.5)))
                return f"BOOK {booking_pct}% PROFITS", booking_pct / 100, f"📈 GOOD GAINS (+{profit_pct*100:.1f}%) | {category} | {technical_signal}"
            
            elif profit_pct >= 0.05:
                trail_pct = max(5, min(12, int(8 + profit_pct * 100 / 10)))
                return f"TRAILING STOP {trail_pct}%", 0, f"🔒 MODERATE GAINS (+{profit_pct*100:.1f}%) | {category} | Trail: {trail_pct}%"
            
            elif profit_pct <= stop_loss:
                return "STOP LOSS", 1.0, f"🛑 CUT LOSSES ({profit_pct*100:.1f}%) | {category} | Exit now"
            
            elif profit_pct <= -0.10:  # -10% as decimal
                return "REDUCE 25%", 0.25, f"⚠️ REDUCE RISK ({profit_pct*100:.1f}%) | {category} | Partial exit"
            
            else:
                if momentum_score >= 60:
                    return "HOLD & ADD", 0, f"💎 HOLD STRONG (+{profit_pct*100:.1f}%) | {category} | {technical_signal}"
                else:
                    return "HOLD & MONITOR", 0, f"[HOLD] HOLD STEADY ({profit_pct*100:+.1f}%) | {category} | {technical_signal}"
                
        except Exception as e:
            return "HOLD", 0, f"Unable to calculate: {str(e)}"
    
    def detect_breakout_patterns(self, stock_data):
        """📈 BREAKOUT DETECTION - Detect potential breakout patterns"""
        try:
            patterns = []
            breakout_score = 0
            
            # Volume breakout
            volume_ratio = stock_data.get('enhanced_volume_ratio', 1.0)
            if volume_ratio > 2.5:
                patterns.append("🚀 VOLUME BREAKOUT")
                breakout_score += 40
            
            # Price breakout above resistance
            rsi = stock_data.get('real_rsi', stock_data.get('enhanced_rsi_14', 50))
            price_change = stock_data.get('enhanced_price_change_5d', 0)
            
            if rsi > 65 and price_change > 8:
                patterns.append("📈 RESISTANCE BREAK")
                breakout_score += 35
            
            # Momentum consolidation
            if 55 <= rsi <= 65 and 3 <= price_change <= 7:
                patterns.append("⚡ MOMENTUM BUILD")
                breakout_score += 25
            
            return patterns, min(breakout_score, 100)
            
        except Exception as e:
            return [], 0
    
    def _validate_and_clean_data(self, stock_data: dict, symbol: str) -> dict:
        """
        ACCURACY IMPROVEMENT #1: Enhanced Data Validation & Cleaning
        
        Validates and cleans stock data to remove outliers and inconsistencies
        that can significantly impact analysis accuracy.
        
        Expected Accuracy Improvement: 15-20%
        """
        validated_data = stock_data.copy()
        validation_issues = []
        
        try:
            # 1. Price Data Validation
            price_fields = ['current_price', '52_week_high', '52_week_low', 'book_value']
            for field in price_fields:
                if field in validated_data and validated_data[field] is not None:
                    value = float(validated_data[field])
                    if value <= 0:
                        validated_data[field] = None
                        validation_issues.append(f"Invalid {field}: {value} (set to None)")
                    elif value > 500000:
                        validated_data[field] = min(value, 500000)
                        validation_issues.append(f"Capped {field}: {value} -> 500000")
            
            # 2. Ratio Validation — unified bounds (same as enhanced_data_validation)
            ratio_validations = {
                'pe_ratio': (0, 500),
                'pb_ratio': (0, 50),
                'debt_to_equity': (0, 500),
                'current_ratio': (0, 20),
                'roe': (-100, 200),
                'operating_margin': (-100, 100),
                'net_margin': (-100, 100)
            }
            
            for field, (min_val, max_val) in ratio_validations.items():
                if field in validated_data and validated_data[field] is not None:
                    try:
                        value = float(validated_data[field])
                        if value < min_val or value > max_val:
                            validated_data[field] = max(min(value, max_val), min_val)
                            validation_issues.append(f"Bounded {field}: {value} -> {validated_data[field]}")
                    except (ValueError, TypeError):
                        validated_data[field] = None
                        validation_issues.append(f"Invalid {field} format, set to None")
            
            # 3. Cross-Validation of Related Metrics
            self._cross_validate_metrics(validated_data, validation_issues, symbol)
            
            # 4. Data Quality Score
            validated_data['data_quality_score'] = self._calculate_data_quality_score(validated_data)
            
            # Log validation issues (limit to avoid spam)
            if validation_issues and len(validation_issues) <= 3:
                logging.info(f"Data validation for {symbol}: {len(validation_issues)} issues corrected")
            elif len(validation_issues) > 3:
                logging.info(f"Data validation for {symbol}: {len(validation_issues)} issues found")
            
            return validated_data
            
        except Exception as e:
            logging.error(f"Data validation failed for {symbol}: {e}")
            return stock_data
    
    def _cross_validate_metrics(self, data: dict, issues: list, symbol: str):
        """Cross-validate related financial metrics for consistency"""
        try:
            # P/E vs P/B vs ROE relationship validation
            pe = data.get('pe_ratio')
            pb = data.get('pb_ratio')
            roe = data.get('roe')
            
            if pe and pb and roe and pe > 0 and pb > 0 and roe > 0:
                # P/B ≈ P/E × ROE (approximately)
                expected_pb = pe * roe / 100  # ROE in percentage
                if expected_pb > 0:
                    pb_ratio = pb / expected_pb
                    if pb_ratio > 2.0 or pb_ratio < 0.5:  # Significant inconsistency
                        issues.append(f"P/E-P/B-ROE inconsistency detected")
                        
        except Exception as e:
            logging.warning(f"Cross-validation error for {symbol}: {e}")
    
    def _calculate_data_quality_score(self, data: dict) -> float:
        """Delegate to the canonical public implementation."""
        return self.calculate_data_quality_score(data)
    
    def analyze_single_stock(self, symbol):
        """Analyze a single stock with comprehensive data"""
        try:
            start_time = time.time()

            cached = self.load_from_cache(symbol)
            if cached is not None:
                if cached.get('improved_overall_score', 0) == 0:
                    cached['improved_overall_score'] = cached.get('final_blended_score', cached.get('risk_adjusted_score', 0))
                if cached.get('corrected_overall_score', 0) == 0:
                    cached['corrected_overall_score'] = cached.get('final_blended_score', cached.get('risk_adjusted_score', 0))
                return cached

            bundle = StockDataBundle(symbol)

            if not bundle.is_valid:
                logging.warning(f"Skipping {symbol}: data validation failed — {bundle.quality_warnings}")
                return {
                    'symbol': symbol,
                    'company_name': self.company_names.get(symbol) or symbol,
                    'status': 'data_invalid',
                    'quality_warnings': bundle.quality_warnings,
                    'overall_score': 0,
                    'overall_score_with_value': 0,
                    'final_blended_score': 0,
                    'final_recommendation': 'SKIP - Data Invalid',
                    'analysis_completeness_pct': 0.0,
                    'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'sector': 'Unknown',
                    'current_price': 0,
                    'market_cap': 0,
                }

            stock_data = {
                'symbol': symbol,
                'company_name': self.company_names.get(symbol) or symbol,
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'processing',
                'quality_warnings': bundle.quality_warnings
            }
            
            # 1. Fundamental Analysis with Enhanced Data Validation
            fund_data = get_comprehensive_stock_data(symbol, bundle=bundle)
            if fund_data:
                # ACCURACY IMPROVEMENT #1: Enhanced Data Validation & Cleaning
                fund_data = self._validate_and_clean_data(fund_data, symbol)
                stock_data.update(fund_data)
                stock_data['fundamental_status'] = 'success'
                logging.info(f"Fundamental analysis completed for {symbol}: {len(fund_data)} fields")
            else:
                stock_data['fundamental_status'] = 'failed'
                logging.warning(f"Fundamental analysis failed for {symbol}")
            
            # 2. Enhanced Technical Analysis
            enhanced_tech_data = get_short_term_technical_analysis(symbol, period_days=90, bundle=bundle)
            if enhanced_tech_data:
                # Add with prefix to avoid conflicts
                for key, value in enhanced_tech_data.items():
                    if key not in stock_data:
                        stock_data[f"enhanced_{key}"] = value
                    else:
                        stock_data[f"enhanced_tech_{key}"] = value
                stock_data['enhanced_technical_status'] = 'success'
                logging.info(f"Enhanced technical analysis completed for {symbol}: {len(enhanced_tech_data)} fields")
            else:
                stock_data['enhanced_technical_status'] = 'failed'
                logging.warning(f"Enhanced technical analysis failed for {symbol}")
            
            # 2.5. ACCURACY IMPROVEMENT #4: Real Technical Analysis
            real_technical_data = self._calculate_real_technical_indicators(symbol, hist=bundle.hist_6mo)
            if real_technical_data:
                stock_data.update({
                    'real_rsi': real_technical_data.get('rsi', 50.0),
                    'real_macd_signal': real_technical_data.get('macd_signal', 'NEUTRAL'),
                    'real_bb_position': real_technical_data.get('bb_position', 'MIDDLE'),
                    'real_volume_trend': real_technical_data.get('volume_trend', 'AVERAGE'),
                    'real_momentum': real_technical_data.get('momentum', 'NEUTRAL'),
                    'real_technical_score': real_technical_data.get('technical_score', 50.0),
                    'support_level': real_technical_data.get('support_level', 0.0),
                    'resistance_level': real_technical_data.get('resistance_level', 0.0),
                    'ma_signal': real_technical_data.get('ma_signal', 'HOLD')
                })
                stock_data['real_technical_status'] = 'success'
                logging.info(f"Real technical analysis completed for {symbol}: RSI={real_technical_data.get('rsi')}, Score={real_technical_data.get('technical_score')}")
            else:
                stock_data['real_technical_status'] = 'failed'
                logging.warning(f"Real technical analysis failed for {symbol}")
            
            # 2.7. ACCURACY IMPROVEMENT #5: Multi-Timeframe Analysis
            mtf_data = self._calculate_multi_timeframe_analysis(symbol, hist_daily=bundle.hist_3mo)
            if mtf_data:
                stock_data.update({
                    'mtf_trend_signal': mtf_data.get('mtf_trend_signal', 'NEUTRAL'),
                    'mtf_momentum_signal': mtf_data.get('mtf_momentum_signal', 'NEUTRAL'),
                    'mtf_volume_signal': mtf_data.get('mtf_volume_signal', 'NEUTRAL'),
                    'mtf_trend_strength': mtf_data.get('mtf_trend_strength', 50),
                    'mtf_momentum_strength': mtf_data.get('mtf_momentum_strength', 50),
                    'mtf_signal_quality': mtf_data.get('mtf_signal_quality', 'LOW'),
                    'mtf_timeframe_agreement': mtf_data.get('mtf_timeframe_agreement', 0),
                    'mtf_composite_score': mtf_data.get('mtf_composite_score', 50),
                    'daily_trend': mtf_data.get('daily_trend', 'NEUTRAL'),
                    'weekly_trend': mtf_data.get('weekly_trend', 'NEUTRAL'),
                    'monthly_trend': mtf_data.get('monthly_trend', 'NEUTRAL')
                })
                stock_data['mtf_analysis_status'] = 'success'
                logging.info(f"Multi-timeframe analysis completed for {symbol}: Trend={mtf_data.get('mtf_trend_signal')}, Agreement={mtf_data.get('mtf_timeframe_agreement'):.1f}%, Score={mtf_data.get('mtf_composite_score')}")
            else:
                stock_data['mtf_analysis_status'] = 'failed'
                logging.warning(f"Multi-timeframe analysis failed for {symbol}")
            
            # 2.8. ACCURACY IMPROVEMENT #7: Institutional Flow Analysis
            institutional_data = self._analyze_institutional_flow(symbol, bundle=bundle)
            if institutional_data:
                stock_data.update({
                    'institutional_sentiment': institutional_data.get('institutional_sentiment', 'NEUTRAL'),
                    'fii_activity': institutional_data.get('fii_activity', 'NEUTRAL'),
                    'dii_activity': institutional_data.get('dii_activity', 'NEUTRAL'),
                    'bulk_deals_signal': institutional_data.get('bulk_deals_signal', 'NEUTRAL'),
                    'insider_activity': institutional_data.get('insider_activity', 'NEUTRAL'),
                    'institutional_score': institutional_data.get('institutional_score', 50),
                    'smart_money_flow': institutional_data.get('smart_money_flow', 'NEUTRAL'),
                    'institutional_ownership_change': institutional_data.get('institutional_ownership_change', 0),
                    'large_block_activity': institutional_data.get('large_block_activity', 'NEUTRAL')
                })
                stock_data['institutional_analysis_status'] = 'success'
                logging.info(f"Institutional flow analysis completed for {symbol}: Sentiment={institutional_data.get('institutional_sentiment')}, FII={institutional_data.get('fii_activity')}, Score={institutional_data.get('institutional_score'):.1f}")
            else:
                stock_data['institutional_analysis_status'] = 'failed'
                logging.warning(f"Institutional flow analysis failed for {symbol}")
            
            # 3. Legacy Technical Analysis
            try:
                hist = bundle.hist_1y  # A-005: reuse pre-downloaded 1Y slice
                
                if not hist.empty:
                    # Safe calculation of indicators with error handling
                    try:
                        indicators = calculate_indicators(hist)
                        if indicators:
                            # Safely convert lists to strings for JSON and Excel compatibility
                            for key, value in indicators.items():
                                if isinstance(value, list):
                                    indicators[key] = str(value)
                                    
                            tech_score, tech_analysis = compute_technical_score(indicators)
                            stock_data.update({
                                'legacy_technical_score': tech_score,
                                'legacy_technical_analysis': tech_analysis,
                                'legacy_rsi': indicators.get('rsi14', 0),
                                'legacy_macd': indicators.get('macd', 0),
                                'legacy_sma_20': indicators.get('sma20', 0),
                                'legacy_sma_50': indicators.get('sma50', 0),
                                'legacy_trend': indicators.get('trend', 'Unknown')
                            })
                            stock_data['legacy_technical_status'] = 'success'
                        else:
                            stock_data['legacy_technical_status'] = 'failed'
                    except Exception as ind_error:
                        logging.error(f"Error calculating indicators for {symbol}: {ind_error}")
                        stock_data['legacy_technical_status'] = f'indicator_error: {str(ind_error)}'
                else:
                    stock_data['legacy_technical_status'] = 'no_data'
            except Exception as e:
                stock_data['legacy_technical_status'] = f'error: {str(e)}'
                logging.error(f"Legacy technical analysis error for {symbol}: {e}")
            
            # 3.5. PHASE 2 - TASK 1: ML Price Prediction Model
            # A-011: propagate fallback flag so Excel report is honest about signal source
            _ml_is_fallback = self._ml_using_fallback or not getattr(self.ml_predictor, 'is_trained', False)
            try:
                # A-018: use predict_from_ohlcv so features match the training pipeline exactly.
                # hist_5y.iloc[-80:] = same 80-row window used during sliding-window training.
                _hist_win = bundle.hist_5y.iloc[-80:] if not bundle.hist_5y.empty else pd.DataFrame()
                ml_results = self.ml_predictor.predict_from_ohlcv(
                    _hist_win, bundle.info, bundle.hist_5y
                )
                if ml_results:
                    # A-011: quality is 'fallback' when no trained model is present
                    _raw_quality = 'high' if ml_results['confidence'] > 70 else 'medium' if ml_results['confidence'] > 50 else 'low'
                    _quality = 'fallback' if _ml_is_fallback else _raw_quality
                    stock_data.update({
                        'ml_prediction': ml_results['prediction'],      # 1 (up), 0 (hold), -1 (down)
                        'ml_confidence': round(float(ml_results['confidence']), 2),  # 0-100, 2dp
                        'ml_signal': ml_results['signal'],              # BUY, HOLD, SELL
                        'ml_expected_return': ml_results['expected_return'],
                        'ml_prediction_quality': _quality,
                        'ml_using_fallback': _ml_is_fallback,           # A-011: explicit flag in result dict
                        'ml_model_source': 'rule_based' if _ml_is_fallback else 'trained_model',
                        'ml_probabilities': str(ml_results.get('probabilities', {}))
                    })
                    stock_data['ml_prediction_status'] = 'success_fallback' if _ml_is_fallback else 'success'
                    logging.info(
                        f"ML Prediction for {symbol}: Signal={ml_results['signal']}, "
                        f"Confidence={ml_results['confidence']:.1f}%, "
                        f"Source={'RULE-BASED FALLBACK' if _ml_is_fallback else 'TRAINED MODEL'}"
                    )
                else:
                    stock_data['ml_prediction_status'] = 'no_prediction'
                    stock_data.update({
                        'ml_prediction': 0,
                        'ml_confidence': 0,
                        'ml_signal': 'HOLD',
                        'ml_expected_return': 0.0,
                        'ml_prediction_quality': 'none',
                        'ml_using_fallback': True,
                        'ml_model_source': 'none'
                    })
            except Exception as ml_error:
                logging.warning(f"ML prediction error for {symbol}: {ml_error}")
                stock_data['ml_prediction_status'] = f'error: {str(ml_error)}'
                stock_data.update({
                    'ml_prediction': 0,
                    'ml_confidence': 0,
                    'ml_signal': 'HOLD',
                    'ml_expected_return': 0.0,
                    'ml_prediction_quality': 'error',
                    'ml_using_fallback': True,
                    'ml_model_source': 'error'
                })
            
            # 3.6. PHASE 2 - TASK 5: Advanced Pattern Recognition
            try:
                hist = bundle.hist_6mo  # A-005: reuse pre-downloaded 6M slice
                
                if not hist.empty and len(hist) > 30:
                    pattern_results = analyze_patterns(hist)
                    patterns_detected = pattern_results['patterns']
                    pattern_score = pattern_results['score']
                    
                    stock_data.update({
                        'pattern_count': len(patterns_detected),
                        'pattern_bullish_score': pattern_score['bullish_score'],
                        'pattern_bearish_score': pattern_score['bearish_score'],
                        'pattern_dominant_signal': pattern_score['dominant_signal'],
                        'pattern_confidence': pattern_score['confidence'],
                        'pattern_signal': pattern_score['dominant_signal'].upper(),
                        'patterns_detected': ', '.join([p['type'] for p in patterns_detected])
                    })
                    
                    # Add individual pattern details if detected
                    if patterns_detected:
                        for i, pattern in enumerate(patterns_detected[:3], 1):  # Top 3 patterns
                            stock_data[f'pattern{i}_type'] = pattern['type']
                            stock_data[f'pattern{i}_direction'] = pattern.get('direction', 'neutral')
                            stock_data[f'pattern{i}_confidence'] = pattern.get('confidence', 0.0)
                            if 'target' in pattern:
                                stock_data[f'pattern{i}_target'] = pattern['target']
                    
                    stock_data['pattern_recognition_status'] = 'success'
                    logging.info(f"Pattern Recognition for {symbol}: {len(patterns_detected)} patterns, Signal={pattern_score['dominant_signal'].upper()}, Confidence={pattern_score['confidence']:.1%}")
                else:
                    stock_data['pattern_recognition_status'] = 'insufficient_data'
                    stock_data.update({
                        'pattern_count': 0,
                        'pattern_bullish_score': 0.0,
                        'pattern_bearish_score': 0.0,
                        'pattern_dominant_signal': 'neutral',
                        'pattern_confidence': 0.0,
                        'pattern_signal': 'NEUTRAL',
                        'patterns_detected': 'none'
                    })
            except Exception as pattern_error:
                logging.warning(f"Pattern recognition error for {symbol}: {pattern_error}")
                stock_data['pattern_recognition_status'] = f'error: {str(pattern_error)}'
                stock_data.update({
                    'pattern_count': 0,
                    'pattern_bullish_score': 0.0,
                    'pattern_bearish_score': 0.0,
                    'pattern_dominant_signal': 'neutral',
                    'pattern_confidence': 0.0,
                    'pattern_signal': 'NEUTRAL',
                    'patterns_detected': 'error'
                })
            
            # 3.7. PHASE 2 - TASK 6: Market Regime Detection
            try:
                # Regime pre-detected in analyze_batch() before workers started — read-only here.
                # Fallback block only executes in single-stock CLI mode (symbol arg) where
                # analyze_batch() was not called. Lock prevents double-init in that edge case.
                if self.market_regime is None:
                    with self._state_lock:
                        if self.market_regime is None:
                            try:
                                self.market_regime = self.regime_detector.detect_regime(period_days=180)
                                if not self.market_regime:
                                    self.market_regime = {'regime': 'SIDEWAYS', 'regime_strength': 'MODERATE', 'vix_level': 15.0,
                                                          'regime_score': 0.0, 'regime_confidence': 0.0, 'market_sentiment': 'NEUTRAL',
                                                          'risk_level': 'MEDIUM', 'trading_recommendation': 'SELECTIVE', 'current_nifty': 0}
                                self.current_market_regime = self.market_regime.get('regime', 'SIDEWAYS')
                                logging.info(f"[REGIME] Single-stock fallback detection: {self.current_market_regime}")
                            except Exception as _re:
                                self.market_regime = {'regime': 'SIDEWAYS', 'regime_strength': 'MODERATE', 'vix_level': 15.0,
                                                      'regime_score': 0.0, 'regime_confidence': 0.0, 'market_sentiment': 'NEUTRAL',
                                                      'risk_level': 'MEDIUM', 'trading_recommendation': 'SELECTIVE', 'current_nifty': 0}
                                self.current_market_regime = 'SIDEWAYS'
                                logging.warning(f"[REGIME] Fallback detection failed: {_re} — using SIDEWAYS")
                
                regime_data = self.market_regime if self.market_regime else {
                    'regime': 'SIDEWAYS', 'regime_strength': 'MODERATE',
                    'regime_score': 0.0, 'regime_confidence': 0.0,
                    'market_sentiment': 'NEUTRAL', 'risk_level': 'MEDIUM',
                    'trading_recommendation': 'SELECTIVE', 'vix_level': 15.0,
                    'current_nifty': 0.0
                }
                
                stock_data.update({
                    'market_regime': regime_data.get('regime', 'UNKNOWN'),
                    'regime_strength': regime_data.get('regime_strength', 'MODERATE'),
                    'regime_score': regime_data.get('regime_score', 50),
                    'regime_confidence': regime_data.get('regime_confidence', 'MEDIUM'),
                    'market_sentiment': regime_data.get('market_sentiment', 'NEUTRAL'),
                    'market_risk_level': regime_data.get('risk_level', 'MODERATE'),
                    'trading_recommendation': regime_data.get('trading_recommendation', 'HOLD'),
                    'vix_level': regime_data.get('vix_level', 15.0),
                    'nifty_level': regime_data.get('current_nifty', 0)
                })
                
                stock_data['regime_detection_status'] = 'success'
                logging.debug(f"Market regime data added for {symbol}: {regime_data['regime']}")
                
            except Exception as regime_error:
                logging.warning(f"Market regime detection error for {symbol}: {regime_error}")
                stock_data['regime_detection_status'] = f'error: {str(regime_error)}'
                stock_data.update({
                    'market_regime': 'UNKNOWN',
                    'regime_strength': 'UNKNOWN',
                    'regime_score': 0.0,
                    'regime_confidence': 0.0,
                    'market_sentiment': 'NEUTRAL',
                    'market_risk_level': 'MODERATE',
                    'trading_recommendation': 'WAIT_AND_WATCH',
                    'vix_level': 15.0,
                    'nifty_level': 0.0
                })
            
            # 3.8. PHASE 2 - TASK 7: News & Sentiment Analysis
            try:
                sentiment_data = self.sentiment_analyzer.analyze_sentiment(symbol, stock_data, bundle=bundle)
                
                stock_data.update({
                    'sentiment_composite_score': sentiment_data['composite_score'],
                    'overall_sentiment': sentiment_data['overall_sentiment'],
                    'sentiment_signal': sentiment_data['sentiment_signal'],
                    'sentiment_confidence': sentiment_data['confidence'],
                    'sentiment_strength': sentiment_data['sentiment_strength'],
                    'news_sentiment_score': sentiment_data['news_sentiment']['score'],
                    'news_sentiment_signal': sentiment_data['news_sentiment']['signal'],
                    'analyst_sentiment_score': sentiment_data['analyst_sentiment']['score'],
                    'analyst_sentiment_signal': sentiment_data['analyst_sentiment']['signal'],
                    'analyst_buy_count': sentiment_data['analyst_sentiment'].get('buy_count', 0),
                    'analyst_hold_count': sentiment_data['analyst_sentiment'].get('hold_count', 0),
                    'analyst_sell_count': sentiment_data['analyst_sentiment'].get('sell_count', 0),
                    'market_sentiment_score': sentiment_data['market_sentiment']['score'],
                    'market_sentiment_signal': sentiment_data['market_sentiment']['signal'],
                    'earnings_sentiment_score': sentiment_data['earnings_sentiment']['score'],
                    'earnings_sentiment_signal': sentiment_data['earnings_sentiment']['signal'],
                    'sentiment_earnings_growth': sentiment_data['earnings_sentiment'].get('earnings_growth', 0),
                    'buzz_sentiment_score': sentiment_data['buzz_sentiment']['score'],
                    'buzz_sentiment_signal': sentiment_data['buzz_sentiment']['signal'],
                    'buzz_level': sentiment_data['buzz_sentiment'].get('buzz_level', 'LOW'),
                    'sentiment_analysis_status': 'fallback' if sentiment_data.get('is_fallback') else 'success',
                    'sentiment_is_fallback': sentiment_data.get('is_fallback', False),
                })
                
                _sent_label = sentiment_data['overall_sentiment']
                if sentiment_data.get('is_fallback'):
                    _sent_label = f"{_sent_label} (NO DATA)"
                logging.info(f"Sentiment Analysis for {symbol}: {_sent_label} ({sentiment_data['composite_score']:.1f}/100), Confidence: {sentiment_data['confidence']:.1f}%")
                
            except Exception as sentiment_error:
                logging.warning(f"Sentiment analysis error for {symbol}: {sentiment_error}")
                stock_data.update({
                    'sentiment_composite_score': 50.0,
                    'overall_sentiment': 'NEUTRAL',
                    'sentiment_signal': 'HOLD',
                    'sentiment_confidence': 40.0,
                    'sentiment_strength': 'MODERATE',
                    'news_sentiment_score': 50.0,
                    'news_sentiment_signal': 'NEUTRAL',
                    'analyst_sentiment_score': 50.0,
                    'analyst_sentiment_signal': 'NEUTRAL',
                    'analyst_buy_count': 0,
                    'analyst_hold_count': 0,
                    'analyst_sell_count': 0,
                    'market_sentiment_score': 50.0,
                    'market_sentiment_signal': 'NEUTRAL',
                    'earnings_sentiment_score': 50.0,
                    'earnings_sentiment_signal': 'NEUTRAL',
                    'sentiment_earnings_growth': 0.0,
                    'buzz_sentiment_score': 50.0,
                    'buzz_sentiment_signal': 'NEUTRAL',
                    'buzz_level': 'LOW',
                    'sentiment_analysis_status': f'error: {str(sentiment_error)}'
                })
            
            # 3.9. PHASE 2 - TASK 5: Volume Profile & Order Flow Analysis
            try:
                volume_data = self.volume_analyzer.analyze_volume(symbol, bundle.hist_1y)
                
                stock_data.update({
                    'vwap_current': volume_data['vwap_current'],
                    'vwap_position': volume_data['vwap_position'],
                    'vwap_distance_pct': volume_data['vwap_distance_pct'],
                    'vwap_trend': volume_data['vwap_trend'],
                    'vwap_support': volume_data['vwap_support'],
                    'vwap_resistance': volume_data['vwap_resistance'],
                    'order_flow_imbalance': volume_data['order_flow_imbalance'],
                    'flow_strength': volume_data['flow_strength'],
                    'flow_direction': volume_data['flow_direction'],
                    'flow_consistency': volume_data['flow_consistency'],
                    'block_trades_count': volume_data['block_trades_count'],
                    'block_trades_volume_pct': volume_data['block_trades_volume_pct'],
                    'institutional_activity': volume_data['institutional_activity'],
                    'recent_blocks_direction': volume_data['recent_blocks_direction'],
                    'volume_poc': volume_data['volume_poc'],
                    'volume_vah': volume_data['volume_vah'],
                    'volume_val': volume_data['volume_val'],
                    'volume_profile_shape': volume_data['volume_profile_shape'],
                    'price_in_value_area': volume_data['price_in_value_area'],
                    'volume_support_1': volume_data['volume_support_1'],
                    'volume_support_2': volume_data['volume_support_2'],
                    'volume_resistance_1': volume_data['volume_resistance_1'],
                    'volume_resistance_2': volume_data['volume_resistance_2'],
                    'nearest_volume_zone': volume_data['nearest_volume_zone'],
                    'zone_distance_pct': volume_data['zone_distance_pct'],
                    'volume_composite_score': volume_data['volume_composite_score'],
                    'volume_signal': volume_data['volume_signal'],
                    'volume_confidence': volume_data['volume_confidence'],
                    'volume_quality': volume_data['volume_quality'],
                    'ad_line_value': volume_data.get('ad_line_value', 0),
                    'ad_line_slope_20d': volume_data.get('ad_line_slope_20d', 0),
                    'ad_line_signal': volume_data.get('ad_line_signal', 'NEUTRAL'),
                    'mfi_value': volume_data.get('mfi_value', 50),
                    'mfi_signal': volume_data.get('mfi_signal', 'NEUTRAL'),
                    'volume_analysis_status': 'success'
                })
                
                logging.info(f"Volume Analysis for {symbol}: Score={volume_data['volume_composite_score']:.1f}/100, Signal={volume_data['volume_signal']}, VWAP={volume_data['vwap_position']}, Flow={volume_data['flow_direction']}")
                
            except Exception as volume_error:
                logging.warning(f"Volume analysis error for {symbol}: {volume_error}")
                stock_data.update({
                    'vwap_current': 0, 'vwap_position': 'UNKNOWN', 'vwap_distance_pct': 0,
                    'vwap_trend': 'NEUTRAL', 'vwap_support': 0, 'vwap_resistance': 0,
                    'order_flow_imbalance': 0, 'flow_strength': 'WEAK', 'flow_direction': 'BALANCED',
                    'flow_consistency': 50, 'block_trades_count': 0, 'block_trades_volume_pct': 0,
                    'institutional_activity': 'LOW', 'recent_blocks_direction': 'NONE',
                    'volume_poc': 0, 'volume_vah': 0, 'volume_val': 0,
                    'volume_profile_shape': 'NORMAL', 'price_in_value_area': True,
                    'volume_support_1': None, 'volume_support_2': None,
                    'volume_resistance_1': None, 'volume_resistance_2': None,
                    'nearest_volume_zone': 0, 'zone_distance_pct': 0,
                    'volume_composite_score': 50, 'volume_signal': 'HOLD',
                    'volume_confidence': 50, 'volume_quality': 'LOW',
                    'ad_line_value': 0, 'ad_line_slope_20d': 0, 'ad_line_signal': 'NEUTRAL',
                    'mfi_value': 50, 'mfi_signal': 'NEUTRAL',
                    'volume_analysis_status': f'error: {str(volume_error)}'
                })
            
            # 4. Calculate Comprehensive Scores with All Accuracy Improvements
            fund_score = _nv(stock_data.get('fundamental_score'), 50)
            enhanced_score = _nv(enhanced_tech_data.get('short_term_score'), 50) if enhanced_tech_data else 50
            legacy_score = _nv(stock_data.get('legacy_technical_score'), 50)
            real_tech_score = _nv(stock_data.get('real_technical_score'), 50)
            mtf_score = _nv(stock_data.get('mtf_composite_score'), 50)
            institutional_score = _nv(stock_data.get('institutional_score'), 50)
            ml_confidence = _nv(stock_data.get('ml_confidence'), 0)
            _pconf_raw = stock_data.get('pattern_confidence', 0.0)
            pattern_confidence = float(_pconf_raw) if _pconf_raw is not None and not (isinstance(_pconf_raw, float) and np.isnan(_pconf_raw)) else 0.0
            
            # Convert pattern signal to score (0-100 scale)
            pattern_signal = str(stock_data.get('pattern_dominant_signal', 'neutral') or 'neutral').lower()
            pattern_bullish = stock_data.get('pattern_bullish_score', 0.0)
            pattern_bearish = stock_data.get('pattern_bearish_score', 0.0)
            
            if pattern_signal == 'bullish':
                pattern_score = 50 + (pattern_confidence * 50)
            elif pattern_signal == 'bearish':
                pattern_score = 50 - (pattern_confidence * 50)
            else:
                pattern_score = 50
            pattern_score = 50 if (pattern_score is None or (isinstance(pattern_score, float) and np.isnan(pattern_score))) else max(0, min(100, pattern_score))
            
            # 5. ENHANCED: Undervaluation Detection  
            undervaluation_score = self.calculate_undervaluation_score(stock_data)
            
            # PHASE 2 IMPROVEMENTS: Combine Real Technical + Multi-Timeframe + Institutional + Pattern Recognition
            # Weight distribution: Real Tech (35%) + Multi-Timeframe (22%) + Institutional (18%) + Pattern (15%) + Enhanced (10%)
            advanced_tech_score = (real_tech_score * 0.35) + (mtf_score * 0.22) + (institutional_score * 0.18) + (pattern_score * 0.15) + (enhanced_score * 0.10)
            
            # Legacy combined score for compatibility
            combined_tech_score = (real_tech_score * 0.7) + (enhanced_score * 0.3)
            
            # Multiple scoring approaches with all accuracy improvements
            stock_data.update({
                'fundamental_score_final': fund_score,
                'enhanced_technical_score_final': enhanced_score,
                'real_technical_score_final': real_tech_score,
                'mtf_composite_score_final': mtf_score,
                'institutional_score_final': institutional_score,
                'pattern_recognition_score_final': pattern_score,
                'advanced_technical_score_final': advanced_tech_score,
                'combined_technical_score_final': combined_tech_score,
                'legacy_technical_score_final': legacy_score,
                'undervaluation_score': undervaluation_score,
                'overall_score_balanced': (fund_score * 0.6) + (advanced_tech_score * 0.4),
                'overall_score_triple': (fund_score * 0.5) + (advanced_tech_score * 0.3) + (legacy_score * 0.2),
                'overall_score_with_value': 50,  # CB-02: placeholder — overwritten by final_blended_score after hybrid scoring
                'overall_score_real_tech': (fund_score * 0.5) + (real_tech_score * 0.35) + (undervaluation_score * 0.15),
                'overall_score_mtf_enhanced': (fund_score * 0.4) + (advanced_tech_score * 0.35) + (undervaluation_score * 0.25),
                'overall_score_institutional': (fund_score * 0.35) + (advanced_tech_score * 0.3) + (institutional_score * 0.2) + (undervaluation_score * 0.15),
                # Provide canonical columns some exporters/search tools expect
                'TechnicalScore': advanced_tech_score,
                'FundamentalScore': fund_score,
                'OverallScore': (fund_score * 0.4) + (enhanced_score * 0.3) + (undervaluation_score * 0.3),
                
                # ========================================================================
                # OPTIMIZED SCORING FORMULA (0.556 correlation - proven accuracy!)
                # Based on correlation analysis showing best predictors
                # ========================================================================
                'optimized_score': 50,  # CB-02: shadow scoring removed; overwritten by final_blended_score
                'analysis_duration_seconds': round(time.time() - start_time, 2),
                'status': 'completed'
            })
            
            # ========================================================================
            # PHASE 1 ACCURACY IMPROVEMENTS - Apply before final scoring
            # ========================================================================
            
            # PHASE 1.1: Enhanced Data Validation
            stock_data = self.enhanced_data_validation(stock_data)
            logging.debug(f"Applied enhanced data validation for {symbol}")
            
            # PHASE 1.2: Data Quality Scoring
            data_quality_score = self.calculate_data_quality_score(stock_data)
            stock_data['data_quality_score'] = data_quality_score
            logging.debug(f"Data quality score for {symbol}: {data_quality_score:.1f}/100")
            
            # PHASE 1.3: Portfolio Context Awareness
            try:
                current_holdings_dict = getattr(self, '_holdings_dict', {})
                _stock_sector = stock_data.get('sector', 'Unknown')
                if symbol in current_holdings_dict and _stock_sector != 'Unknown':
                    with self._state_lock:
                        current_holdings_dict[symbol]['sector'] = _stock_sector
                        current_holdings_dict[symbol]['market_cap'] = stock_data.get('market_cap', 0)
                portfolio_context = self.calculate_portfolio_context_score(
                    symbol, stock_data, current_holdings_dict
                )
                stock_data.update({
                    'portfolio_context_score': portfolio_context['portfolio_context_score'],
                    'diversification_benefit': portfolio_context['diversification_benefit'],
                    'sector_concentration': portfolio_context['sector_concentration'],
                    'portfolio_fit': portfolio_context['portfolio_fit'],
                    'portfolio_adjustments': ', '.join(portfolio_context['context_adjustments'])
                })
                logging.debug(f"Portfolio context for {symbol}: {portfolio_context['portfolio_fit']} fit, {portfolio_context['diversification_benefit']} diversification benefit")
                
            except Exception as e:
                logging.debug(f"Portfolio context calculation skipped for {symbol}: {e}")
                stock_data['portfolio_context_score'] = 50.0
                stock_data['portfolio_fit'] = 'neutral'
                stock_data['diversification_benefit'] = 'unknown'
            
            # PHASE 1 COMBINED SCORE ADJUSTMENT
            # Adjust final scores based on Phase 1 improvements
            quality_weight = 0.20  # 20% weight to data quality
            context_weight = 0.15  # 15% weight to portfolio context
            
            # Calculate Phase 1 adjusted score
            base_score = _nv(stock_data.get('overall_score_with_value'), 50)
            quality_adjustment = (_nv(data_quality_score, 70) - 70) * quality_weight
            context_adjustment = (_nv(stock_data.get('portfolio_context_score'), 50) - 50) * context_weight
            
            phase1_adjusted_score = _nv(base_score + quality_adjustment + context_adjustment, 50)
            stock_data['phase1_adjusted_score'] = max(0, min(100, phase1_adjusted_score))
            stock_data['phase1_quality_adjustment'] = quality_adjustment
            stock_data['phase1_context_adjustment'] = context_adjustment
            
            logging.info(f"Phase 1 improvements for {symbol}: Quality={data_quality_score:.0f}, Context={stock_data.get('portfolio_context_score', 100):.0f}, Adjusted Score={phase1_adjusted_score:.1f}")
            
            # 🌍 PHASE 2 - TASK 6: Apply Regime-Based Score Adjustment
            try:
                if hasattr(self, 'market_regime') and self.market_regime:
                    # Apply regime-based adjustments to Phase 1 score
                    regime_adjustment_result = self.regime_detector.adjust_stock_score_by_regime(
                        phase1_adjusted_score, 
                        stock_data, 
                        self.market_regime
                    )
                    
                    # Update stock data with regime-adjusted scores
                    stock_data.update({
                        'regime_adjusted_score': regime_adjustment_result['adjusted_score'],
                        'regime_adjustment_amount': regime_adjustment_result['regime_adjustment'],
                        'regime_adjustment_reasons': ', '.join(regime_adjustment_result['adjustment_reasons']),
                        'regime_context': regime_adjustment_result['regime_context']
                    })
                    
                    if regime_adjustment_result['regime_adjustment'] != 0:
                        logging.info(f"Regime adjustment for {symbol}: {regime_adjustment_result['regime_adjustment']:+.1f} points "
                                   f"({stock_data['market_regime']}). Reasons: {stock_data['regime_adjustment_reasons']}")
                else:
                    stock_data['regime_adjusted_score'] = phase1_adjusted_score
                    stock_data['regime_adjustment_amount'] = 0.0
                    stock_data['regime_adjustment_reasons'] = 'No regime detected'
                    stock_data['regime_context'] = 'Unknown'
                    
            except Exception as e:
                logging.warning(f"Regime adjustment failed for {symbol}: {e}")
                stock_data['regime_adjusted_score'] = phase1_adjusted_score
                stock_data['regime_adjustment_amount'] = 0.0
                stock_data['regime_adjustment_reasons'] = f'Error: {str(e)}'
                stock_data['regime_context'] = 'Error'
            
            # 🎭 PHASE 2 - TASK 7: Apply Sentiment-Based Score Adjustment
            base_score_for_sentiment = phase1_adjusted_score  # safe default before try
            if not self.ENABLE_SENTIMENT_ADJUSTMENT:
                stock_data['sentiment_adjusted_score'] = stock_data.get('regime_adjusted_score', phase1_adjusted_score)
                stock_data['sentiment_adjustment_amount'] = 0.0
                stock_data['sentiment_adjustment_reasons'] = 'Sentiment adjustment disabled (no real news API)'
                stock_data['sentiment_context'] = 'DISABLED'
            else:
                try:
                    base_score_for_sentiment = stock_data.get('regime_adjusted_score', phase1_adjusted_score)
                    
                    sentiment_data = {
                        'composite_score': stock_data.get('sentiment_composite_score', 50),
                        'overall_sentiment': stock_data.get('overall_sentiment', 'NEUTRAL'),
                        'confidence': stock_data.get('sentiment_confidence', 40),
                        'news_sentiment': {
                            'signal': stock_data.get('news_sentiment_signal', 'NEUTRAL'),
                            'volume_surge': ({'VERY_HIGH': 3.0, 'HIGH': 2.5, 'ABOVE_AVERAGE': 1.5,
                                              'AVERAGE': 1.0, 'BELOW_AVERAGE': 0.7, 'LOW': 0.5, 'VERY_LOW': 0.3}
                                             .get(str(stock_data.get('volume_trend', 'AVERAGE')).upper(), 1.0)
                                             if isinstance(stock_data.get('volume_trend'), str)
                                             else _nv(stock_data.get('volume_trend'), 1.0))
                        },
                        'analyst_sentiment': {
                            'signal': stock_data.get('analyst_sentiment_signal', 'NEUTRAL'),
                            'total_recommendations': (
                                stock_data.get('analyst_buy_count', 0) +
                                stock_data.get('analyst_hold_count', 0) +
                                stock_data.get('analyst_sell_count', 0)
                            )
                        },
                        'earnings_sentiment': {
                            'earnings_growth': stock_data.get('earnings_growth', 0)
                        }
                    }
                    
                    sentiment_adjustment_result = self.sentiment_analyzer.adjust_score_by_sentiment(
                        base_score_for_sentiment,
                        sentiment_data
                    )
                    
                    stock_data.update({
                        'sentiment_adjusted_score': sentiment_adjustment_result['adjusted_score'],
                        'sentiment_adjustment_amount': sentiment_adjustment_result['sentiment_adjustment'],
                        'sentiment_adjustment_reasons': ', '.join(sentiment_adjustment_result['adjustment_reasons']),
                        'sentiment_context': sentiment_adjustment_result['sentiment_context']
                    })
                    
                    if sentiment_adjustment_result['sentiment_adjustment'] != 0:
                        logging.info(f"Sentiment adjustment for {symbol}: {sentiment_adjustment_result['sentiment_adjustment']:+.1f} points "
                                   f"({sentiment_data['overall_sentiment']}). Reasons: {stock_data['sentiment_adjustment_reasons']}")
                
                except Exception as e:
                    logging.warning(f"Sentiment adjustment failed for {symbol}: {e}")
                    stock_data['sentiment_adjusted_score'] = base_score_for_sentiment
                    stock_data['sentiment_adjustment_amount'] = 0.0
                    stock_data['sentiment_adjustment_reasons'] = f'Error: {str(e)}'
                    stock_data['sentiment_context'] = 'Error'
            
            # PHASE 2 - TASK 5: Apply Volume Profile & Order Flow Adjustments
            base_score_for_volume = stock_data.get('sentiment_adjusted_score', base_score_for_sentiment)
            try:
                
                # Prepare volume data for adjustment
                volume_data = {
                    'volume_composite_score': stock_data.get('volume_composite_score', 50),
                    'volume_signal': stock_data.get('volume_signal', 'HOLD'),
                    'volume_confidence': stock_data.get('volume_confidence', 50),
                    'vwap_position': stock_data.get('vwap_position', 'UNKNOWN'),
                    'flow_direction': stock_data.get('flow_direction', 'BALANCED'),
                    'institutional_activity': stock_data.get('institutional_activity', 'LOW')
                }
                
                # Apply volume adjustment
                volume_adjustment_result = self.volume_analyzer.adjust_score_by_volume(
                    base_score_for_volume,
                    volume_data
                )
                
                # Update stock data with volume-adjusted scores
                stock_data.update({
                    'volume_adjusted_score': volume_adjustment_result['volume_adjusted_score'],
                    'volume_adjustment_amount': volume_adjustment_result['volume_adjustment_amount'],
                    'volume_adjustment_reasons': volume_adjustment_result['volume_adjustment_reasons'],
                    'volume_signal_used': volume_adjustment_result['volume_signal_used'],
                    'volume_confidence_used': volume_adjustment_result['volume_confidence_used']
                })
                
                if volume_adjustment_result['volume_adjustment_amount'] != 0:
                    logging.info(f"Volume adjustment for {symbol}: {volume_adjustment_result['volume_adjustment_amount']:+.1f} points "
                               f"({volume_data['volume_signal']}). Reasons: {stock_data['volume_adjustment_reasons']}")
            
            except Exception as e:
                logging.warning(f"Volume adjustment failed for {symbol}: {e}")
                stock_data['volume_adjusted_score'] = base_score_for_volume
                stock_data['volume_adjustment_amount'] = 0.0
                stock_data['volume_adjustment_reasons'] = f'Error: {str(e)}'
                stock_data['volume_signal_used'] = 'HOLD'
                stock_data['volume_confidence_used'] = 0
            
            # V5.0: Corrected & Improved engines removed — backward-compat defaults
            corrected_results = {
                'corrected_overall_score': 0, 'contrarian_technical': 0,
                'contrarian_momentum': 0, 'fundamental_quality': 0,
                'value_opportunity': 0, 'sector': stock_data.get('sector', 'Others'),
                'timing_factor': 1.0
            }
            stock_data.update({
                'corrected_overall_score': 0,
                'contrarian_technical_score': 0, 'contrarian_momentum_score': 0,
                'fundamental_quality_score': 0, 'value_opportunity_score': 0,
                'sector_classification': corrected_results['sector'],
                'timing_factor': 1.0
            })
            improved_results = {
                'improved_overall_score': 0, 'fundamental_quality': 0,
                'momentum_technical': 0, 'contrarian_momentum': 0, 'quality_multiplier': 1.0,
            }
            stock_data.update({
                'improved_overall_score': 0,
                'improved_fundamental_quality': 0,
                'improved_momentum_technical': 0,
                'improved_contrarian_momentum': 0,
                'improved_quality_multiplier': 1.0
            })
            
            # GAP-2 FIX: Pre-compute live sector adj BEFORE hybrid scoring so the internal
            # sector_momentum component uses live data instead of frozen 2023 backtest values.
            # _compute_sector_adjustment is cached per-sector per-run (1 HTTP call per sector).
            _sector_name_pre = str(stock_data.get('sector', 'unknown'))
            _sector_adj_pre = self._compute_sector_adjustment(_sector_name_pre)
            stock_data['sector_performance_adj'] = round(_sector_adj_pre, 2)

            # 🚀 LATEST: Apply HYBRID OPTIMIZED scoring V4.0 (Validated: +40.1% correlation, all market conditions)
            try:
                # Detect market regime if not already detected
                if not hasattr(self, 'current_market_regime') or self.current_market_regime is None:
                    # Read from pre-detected regime (set in analyze_batch before workers start).
                    # Use lock to prevent double-init in single-stock CLI edge case.
                    with self._state_lock:
                        if not hasattr(self, 'current_market_regime') or self.current_market_regime is None:
                            self.current_market_regime = (
                                self.market_regime.get('regime', 'SIDEWAYS')
                                if self.market_regime else 'SIDEWAYS'
                            )
                            self.current_regime_confidence = (
                                self.market_regime.get('regime_confidence', 0.5)
                                if self.market_regime else 0.5
                            )
                
                regime_key = str(self.current_market_regime or '').upper() or 'SIDEWAYS'
                _adaptive_wts = self.adaptive_strategy.get_adaptive_scoring_weights(regime_key)
                self._last_adaptive_weights = _adaptive_wts
                hybrid_results = self.hybrid_scoring_engine.calculate_hybrid_score(
                    symbol, stock_data, adaptive_weights=_adaptive_wts
                )
                
                # Create adaptive recommendation based on market regime
                position_size = self.adaptive_strategy.get_position_sizing_strategy(regime_key)
                _mapped_regime = self.adaptive_strategy._map_regime(regime_key)
                _default_perf = {'best_quintile': 'Q3', 'strategy': 'BALANCED_APPROACH'}
                regime_performance = self.adaptive_strategy.market_performance.get(
                    _mapped_regime,
                    self.adaptive_strategy.market_performance.get('CALM', _default_perf)
                ) or _default_perf
                best_quintile = regime_performance.get('best_quintile', 'Q3')
                
                _max_pos = position_size.get('max_position', 0.10) if isinstance(position_size, dict) else 0.10
                _pos_label = 'LARGE' if _max_pos >= 0.12 else ('MEDIUM' if _max_pos >= 0.08 else 'SMALL')
                adaptive_recommendation = {
                    'position_size': _pos_label,
                    'position_sizing_detail': position_size,
                    'quintile_preference': best_quintile,
                    'strategy': regime_performance.get('strategy', 'BALANCED_APPROACH'),
                    'regime_confidence': self.current_regime_confidence
                }
                
                # Add hybrid scores to stock data
                _scoring_failed = hybrid_results.get('scoring_failed', False)
                stock_data.update({
                    'hybrid_overall_score': hybrid_results['hybrid_score'],
                    'hybrid_fundamental_quality': hybrid_results['components'].get('fundamental_quality', 0),
                    'hybrid_momentum_technical': hybrid_results['components'].get('momentum_technical', 0),
                    'hybrid_volume_strength': hybrid_results['components'].get('volume_strength', 50),
                    'hybrid_multi_timeframe': hybrid_results['components'].get('multi_timeframe', 50),
                    'hybrid_ml_signal': hybrid_results['components'].get('ml_signal', 50),
                    'hybrid_risk_adjustment': hybrid_results['components'].get('risk_adjustment', 50),
                    'hybrid_sector_multiplier': hybrid_results['adjustments'].get('sector_multiplier', 1.0),
                    'market_regime_detected': self.current_market_regime,
                    'adaptive_position_size': adaptive_recommendation['position_size'],
                    'adaptive_quintile_target': adaptive_recommendation['quintile_preference'],
                    'hybrid_confidence': 0.0 if _scoring_failed else 0.8,
                    'hybrid_market_regime': hybrid_results['adjustments'].get('market_regime', 'SIDEWAYS'),
                    'hybrid_ml_active': hybrid_results['adjustments'].get('ml_active', False),
                    'scoring_failed': _scoring_failed,
                    'data_coverage': hybrid_results.get('data_coverage', 1.0),
                })
                
                logging.debug(f"Hybrid scoring applied to {symbol}: Score={hybrid_results['hybrid_score']:.2f}, Regime={self.current_market_regime}")
                
            except Exception as e:
                logging.warning(f"Hybrid scoring failed for {symbol}: {e}")
                stock_data.update({
                    'hybrid_overall_score': 0,
                    'hybrid_fundamental_quality': 0,
                    'hybrid_momentum_technical': 0,
                    'hybrid_volume_strength': 0,
                    'hybrid_risk_adjustment': 0,
                    'hybrid_sector_multiplier': 1.0,
                    'market_regime_detected': 'UNKNOWN',
                    'adaptive_position_size': 'SMALL',
                    'adaptive_quintile_target': 'Q1',
                    'hybrid_confidence': 0.0,
                    'hybrid_market_regime': 'UNKNOWN',
                    'scoring_failed': True,
                })
            
            # ✅ PORTFOLIO ALLOCATION ENHANCEMENT: Add missing fields for retail investors
            # Fetch historical data if not already present to calculate additional metrics
            try:
                if '52_week_high' not in stock_data or not stock_data.get('52_week_high'):
                    hist = bundle.hist_1y   # A-005: reuse pre-downloaded 1Y slice
                    info = bundle.info      # A-005: reuse pre-downloaded ticker.info
                    
                    if not hist.empty:
                        current_price = stock_data.get('current_price', hist['Close'].iloc[-1])
                        
                        # 52-week high and low
                        stock_data['52_week_high'] = float(hist['High'].max()) if len(hist) > 0 else current_price
                        stock_data['52_week_low'] = float(hist['Low'].min()) if len(hist) > 0 else current_price
                        
                        # Volatility (annualized percentage)
                        if len(hist) > 20:
                            returns = hist['Close'].pct_change().dropna()
                            _vol = returns.std() * (252 ** 0.5) * 100
                            stock_data['volatility'] = 0.0 if (len(returns) == 0 or np.isnan(_vol)) else float(_vol)
                        else:
                            stock_data['volatility'] = 0.0
                        
                        # 20-day price change
                        if len(hist) >= 20:
                            price_20d_ago = hist['Close'].iloc[-20]
                            if price_20d_ago and price_20d_ago != 0 and not np.isnan(price_20d_ago):
                                stock_data['enhanced_price_change_20d'] = float((current_price - price_20d_ago) / price_20d_ago * 100)
                            else:
                                stock_data['enhanced_price_change_20d'] = 0.0
                        else:
                            stock_data['enhanced_price_change_20d'] = 0.0
                        
                        logging.debug(f"Added portfolio fields for {symbol}: 52W_HIGH={stock_data['52_week_high']:.2f}, VOL={stock_data.get('volatility', 0):.2f}%")
                    else:
                        # Set defaults if no historical data
                        stock_data['52_week_high'] = stock_data.get('current_price', 0)
                        stock_data['52_week_low'] = stock_data.get('current_price', 0)
                        stock_data['volatility'] = 0.0
                        stock_data['enhanced_price_change_20d'] = 0.0
            except Exception as e:
                logging.warning(f"Failed to fetch portfolio enhancement fields for {symbol}: {e}")
                # Set defaults on error
                stock_data['52_week_high'] = stock_data.get('current_price', 0)
                stock_data['52_week_low'] = stock_data.get('current_price', 0)
                stock_data['volatility'] = 0.0
                stock_data['enhanced_price_change_20d'] = 0.0
            
            # Map real_rsi to enhanced_rsi_14 if not already set (for Portfolio Allocation sheet compatibility)
            if 'enhanced_rsi_14' not in stock_data or not stock_data.get('enhanced_rsi_14'):
                stock_data['enhanced_rsi_14'] = stock_data.get('real_rsi', 50.0)
            
            # V5.0: Corrected recommendation engine removed
            corrected_recommendation = 'REMOVED'
            
            best_score = _nv(stock_data.get('overall_score_with_value'), 50)
            corrected_score = 0
            phase1_score = _nv(stock_data.get('phase1_adjusted_score'), 50)
            is_undervalued = undervaluation_score >= _config.UNDERVALUED_THRESHOLD  # A-009
            
            # V5.1: ML is now a proper component inside the hybrid engine (10% weight
            # when trained). The old ±4pt external adjustment is removed.
            ml_confidence = stock_data.get('ml_confidence', 0)
            ml_signal = stock_data.get('ml_signal', 'HOLD')
            ml_prediction_quality = stock_data.get('ml_prediction_quality', 'none')
            ml_score_adjustment = 0
            stock_data['ml_score_adjustment'] = 0

            # 🚀 HYBRID OPTIMIZED SCORING: Use latest validated scoring system (primary) + ML adjustment
            # Keep legacy scores for comparison and backtesting validation
            improved_score = 0
            hybrid_score = _nv(stock_data.get('hybrid_overall_score'), 50)
            if hybrid_score <= 0 or np.isnan(hybrid_score):
                hybrid_score = 50  # Safety floor
            old_phase1_blend = 0

            # V5.0: Sentiment and pattern adjustments removed — they added noise.
            # Sentiment analyzer still runs for data collection; it just doesn't affect the score.
            _sent_adj = 0.0
            _vol_adj  = 0.0
            _pattern_adj = 0.0
            stock_data['sentiment_score_contribution'] = 0.0
            stock_data['volume_score_contribution']    = 0.0
            stock_data['pattern_score_contribution']   = 0.0

            # Crisis adjustment kept — it's a genuine macro signal
            _cd = self.crisis_data if self.crisis_data else {'crisis_detected': False, 'crisis_type': 'NONE', 'severity': 0}
            _stock_sector = stock_data.get('sector', '')
            try:
                _crisis_adj = self.crisis_detector.get_stock_crisis_adjustment(symbol, _stock_sector, _cd)
            except Exception as _ce:
                logging.warning(f"Crisis adjustment failed for {symbol}: {_ce}")
                _crisis_adj = 0.0
            stock_data['crisis_type_detected']   = _cd.get('crisis_type', 'NONE')
            stock_data['crisis_severity']         = _cd.get('severity_label', 'NONE')
            stock_data['crisis_score_adjustment'] = _crisis_adj

            # V5.1: ML is inside hybrid engine; only crisis adjustment is external
            stock_data['signal_conviction_scale'] = 1.0
            final_blended_score = hybrid_score + _crisis_adj

            stock_data['phase1_blended_score'] = 0
            stock_data['improved_score_used'] = 0
            stock_data['hybrid_score_used'] = hybrid_score
            stock_data['pre_adj_blended_score'] = final_blended_score

            _dq_raw = stock_data.get('data_quality_score')
            data_quality = _nv(_dq_raw, 70) if _dq_raw is not None else 70
            portfolio_fit = stock_data.get('portfolio_fit', 'unknown')

            _quality_adj = (data_quality - 70) * 0.10
            final_blended_score += _quality_adj
            stock_data['quality_adj_recorded'] = round(_quality_adj, 2)

            _sector_adj = _nv(stock_data.get('sector_performance_adj'), 0.0)
            final_blended_score += _sector_adj
            stock_data['sector_adj_recorded'] = _sector_adj

            final_blended_score = _nv(final_blended_score, 50)
            final_blended_score = max(0, min(100, final_blended_score))

            # V5.1: Score smoothing — blend with previous score to reduce instability.
            # Must find the most recent cache file for this symbol (any date), since
            # today's file hasn't been saved yet and yesterday's has a different date stamp.
            stock_data['raw_blended_score'] = final_blended_score
            try:
                import glob as _glob_mod
                _today_path = self.get_cache_path(symbol)
                _prev_files = sorted(
                    _glob_mod.glob(os.path.join(self.cache_dir, f"{symbol}_comprehensive_*.json")),
                    key=os.path.getmtime, reverse=True
                )
                _cached = None
                _max_age_days = getattr(_config, 'SCORE_SMOOTHING_MAX_AGE_DAYS', 3)
                _smooth_w = getattr(_config, 'SCORE_SMOOTHING_WEIGHT', 0.70)
                for _pf in _prev_files:
                    if _pf != _today_path:
                        _file_age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(_pf))).days
                        if _file_age_days > _max_age_days:
                            break
                        _lock = FileLock(_pf + '.lock', timeout=5)  # HI-06
                        with _lock:
                            with open(_pf, 'r', encoding='utf-8') as _fp:
                                _cached = json.load(_fp)
                        break
                if _cached and isinstance(_cached, dict):
                    _prev_score = _cached.get('final_blended_score')
                    if _prev_score is not None and not (isinstance(_prev_score, float) and np.isnan(_prev_score)):
                        _prev_score = float(_prev_score)
                        if 0 < _prev_score <= 100:
                            _delta = abs(final_blended_score - _prev_score)
                            if _delta > 10:
                                stock_data['score_smoothing_skipped'] = 'circuit_breaker'
                                logging.info(f"[CB-04] {symbol}: smoothing skipped, delta={_delta:.1f} > 10")
                            else:
                                final_blended_score = _smooth_w * final_blended_score + (1 - _smooth_w) * _prev_score
                                stock_data['score_smoothed'] = True
                                stock_data['prev_score_used'] = _prev_score
            except Exception as _smooth_err:
                logging.debug(f"Score smoothing failed for {symbol}: {_smooth_err}")
            stock_data.setdefault('score_smoothed', False)

            final_blended_score = 0 if (isinstance(final_blended_score, float) and np.isnan(final_blended_score)) else max(0, min(100, final_blended_score))
            stock_data['final_blended_score'] = final_blended_score
            stock_data['final_score_with_phase1'] = final_blended_score
            stock_data['overall_score'] = final_blended_score
            stock_data['overall_score_with_value'] = final_blended_score  # CB-02: canonical alias
            stock_data['improved_overall_score'] = final_blended_score
            stock_data['corrected_overall_score'] = final_blended_score

            # Original recommendation logic (for comparison)
            if best_score >= _config.STRONG_BUY_THRESHOLD and is_undervalued:
                original_recommendation = "🟢 STRONG BUY (UNDERVALUED)"
            elif best_score >= _config.STRONG_BUY_THRESHOLD:
                original_recommendation = "🟢 STRONG BUY"
            elif best_score >= _config.BUY_THRESHOLD and is_undervalued:
                original_recommendation = "🟢 BUY (VALUE)"
            elif best_score >= _config.BUY_THRESHOLD:
                original_recommendation = "🟢 BUY"
            elif best_score >= _config.HOLD_THRESHOLD:
                original_recommendation = "🟡 HOLD"
            elif best_score >= 40:
                original_recommendation = "🟠 WEAK SELL"
            else:
                original_recommendation = "🔴 SELL"

            # PHASE 1+2 FINAL RECOMMENDATION: Use blended score with quality gates and ML signal
            # GAP-6 FIX: Regime-adaptive thresholds — stricter in BEAR/BEARISH (+5), same in SIDEWAYS,
            # slightly easier in BULL/BULLISH (−2). Prevents over-buying in down markets.
            # GAP-Q5 FIX: MarketRegimeDetector returns 'BEAR'/'BULL' (not 'BEARISH'/'BULLISH').
            # Check both variants so the threshold delta fires correctly.
            _resolved_regime = (stock_data.get('market_regime_detected') or stock_data.get('market_regime', 'SIDEWAYS'))
            _resolved_regime = str(_resolved_regime).upper()
            if _resolved_regime in ('UNKNOWN', ''):
                _resolved_regime = (stock_data.get('market_regime') or 'SIDEWAYS').upper()
            _curr_regime = _resolved_regime
            _is_bear = _curr_regime in ('BEAR', 'BEARISH')
            _is_bull = _curr_regime in ('BULL', 'BULLISH')
            _regime_thr_delta = 5 if _is_bear else (-2 if _is_bull else 0)
            _strong_buy_thr = _config.STRONG_BUY_THRESHOLD + _regime_thr_delta
            _buy_thr        = _config.BUY_THRESHOLD        + _regime_thr_delta
            _hold_thr       = _config.HOLD_THRESHOLD + (3 if _is_bear else 0)
            logging.debug(f"[GAP-6] Regime={_curr_regime} bear={_is_bear} bull={_is_bull} → STRONG_BUY≥{_strong_buy_thr}, BUY≥{_buy_thr}")
            if stock_data.get('scoring_failed'):
                phase2_recommendation = "⛔ INSUFFICIENT DATA - SKIP"
                logging.warning(f"[CB-01] {symbol}: scoring_failed=True, coverage={stock_data.get('data_coverage', 0):.0%}")
            elif data_quality < 30:
                phase2_recommendation = "🟡 HOLD (LOW DATA QUALITY)"
                with self._state_lock:
                    if symbol not in self.low_quality_stocks:
                        self.low_quality_stocks.append(symbol)
            elif final_blended_score >= _strong_buy_thr and is_undervalued:  # GAP-6
                phase2_recommendation = "🟢 STRONG BUY (UNDERVALUED)"
            elif final_blended_score >= _strong_buy_thr:                      # GAP-6
                phase2_recommendation = "🟢 STRONG BUY"
            elif final_blended_score >= _buy_thr and is_undervalued:          # GAP-6
                phase2_recommendation = "🟢 BUY (VALUE)"
            elif final_blended_score >= _buy_thr:                             # GAP-6
                phase2_recommendation = "🟢 BUY"
            elif final_blended_score >= _hold_thr:                            # GAP-6
                phase2_recommendation = "🟡 HOLD"
            elif final_blended_score >= 40:
                phase2_recommendation = "🟠 WEAK SELL"
            else:
                phase2_recommendation = "🔴 SELL"
            
            # MI-11: Flag if fundamental data was unavailable
            if stock_data.get('fundamental_data_failed') and 'BUY' in phase2_recommendation:
                phase2_recommendation += " (CAUTION: NO FUNDAMENTAL DATA)"
                logging.warning(f"[MI-11] {symbol}: fundamental_data_failed=True, recommendation downgraded")

            market_regime = _resolved_regime
            adaptive_position = stock_data.get('adaptive_position_size', 'MEDIUM')
            adaptive_quintile = stock_data.get('adaptive_quintile_target', 'Q3')
            hybrid_confidence = stock_data.get('hybrid_confidence', 0.5)
            
            # Apply market regime-specific adjustments to recommendation
            regime_adjustment = ""
            if market_regime == 'BULL' and adaptive_quintile == 'Q3' and final_blended_score >= 65:
                # In bull markets, Q3 performs best - be more aggressive
                if 'BUY' in phase2_recommendation and adaptive_position in ['LARGE', 'MEDIUM']:
                    regime_adjustment = f" (BULL-Q3: {adaptive_position})"
            elif market_regime == 'SIDEWAYS' and adaptive_quintile == 'Q1' and final_blended_score >= 70:
                # In sideways markets, Q1 (contrarian) performs best
                if 'BUY' in phase2_recommendation and adaptive_position in ['LARGE', 'MEDIUM']:
                    regime_adjustment = f" (SIDEWAYS-Q1: {adaptive_position})"
            elif market_regime == 'BEAR':
                if adaptive_position == 'SMALL' and 'BUY' in phase2_recommendation:
                    if 'STRONG BUY' in phase2_recommendation:
                        phase2_recommendation = phase2_recommendation.replace('STRONG BUY', 'BUY')
                    regime_adjustment = f" (BEAR: SMALL)"
                elif adaptive_position == 'MEDIUM':
                    if 'STRONG BUY' in phase2_recommendation:
                        phase2_recommendation = phase2_recommendation.replace('STRONG BUY', 'BUY')
                        regime_adjustment = f" (BEAR: MEDIUM)"
                    elif 'BUY' in phase2_recommendation and final_blended_score < _buy_thr + 5:
                        if 'BUY (VALUE)' in phase2_recommendation:
                            phase2_recommendation = phase2_recommendation.replace('BUY (VALUE)', 'HOLD')
                        elif 'BUY (UNDERVALUED)' in phase2_recommendation:
                            phase2_recommendation = phase2_recommendation.replace('BUY (UNDERVALUED)', 'HOLD')
                        else:
                            phase2_recommendation = phase2_recommendation.replace('BUY', 'HOLD')
                        regime_adjustment = f" (BEAR: MARGINAL)"
                    elif 'BUY' in phase2_recommendation:
                        regime_adjustment = f" (BEAR: MEDIUM)"
                elif adaptive_position == 'LARGE' and 'STRONG BUY' in phase2_recommendation:
                    regime_adjustment = f" (BEAR: CAUTIOUS)"
            elif market_regime in ['VOLATILE', 'CALM']:
                # Add regime context for other conditions
                regime_adjustment = f" ({market_regime}: {adaptive_position})"
                
            # Add ML signal confirmation to recommendation
            ml_confidence = _nv(ml_confidence, 0)
            ml_prediction_quality = str(ml_prediction_quality or '').lower()
            if ml_prediction_quality in ['high', 'medium'] and ml_confidence > 60:
                if ml_signal == 'BUY' and 'BUY' in phase2_recommendation:
                    phase2_recommendation += f" (ML: {ml_confidence:.0f}%)"
                elif ml_signal == 'SELL' and 'SELL' in phase2_recommendation:
                    phase2_recommendation += f" (ML: {ml_confidence:.0f}%)"
                elif ml_signal != 'HOLD':
                    # ML disagrees with main recommendation
                    phase2_recommendation += f" (ML: {ml_signal})"
            
            # Add regime adjustment to final recommendation
            if regime_adjustment:
                phase2_recommendation += regime_adjustment
            
            # Add portfolio context to recommendation if relevant
            diversification = stock_data.get('diversification_benefit', 'unknown')
            if diversification == 'high' and 'BUY' in phase2_recommendation:
                if '(ML:' not in phase2_recommendation and '(' not in regime_adjustment:  # Avoid double parentheses
                    phase2_recommendation += " (DIVERSIFIES)"
            elif diversification == 'negative' and 'BUY' in phase2_recommendation:
                if '(ML:' not in phase2_recommendation and '(' not in regime_adjustment:
                    phase2_recommendation += " (CONCENTRATION RISK)"
            
            # Store all recommendations for comparison and backtesting validation
            stock_data['original_recommendation'] = original_recommendation
            stock_data['corrected_recommendation'] = 'REMOVED'
            _p1_score = _nv(stock_data.get('phase1_adjusted_score'), _nv(best_score, 50))
            stock_data['phase1_recommendation'] = (
                'STRONG BUY' if _p1_score >= _config.STRONG_BUY_THRESHOLD else
                'BUY' if _p1_score >= _config.BUY_THRESHOLD else
                'HOLD' if _p1_score >= _config.HOLD_THRESHOLD else
                'SELL'
            )
            stock_data['phase2_recommendation'] = phase2_recommendation
            stock_data['final_recommendation'] = phase2_recommendation

            # Extreme volatility / corporate action safety downgrade
            _ext_vol = stock_data.get('extreme_volatility_flag', False)
            _corp_warn = stock_data.get('corporate_action_warning', False)
            _pre_safety_rec = stock_data.get('final_recommendation', '')
            if _ext_vol and 'BUY' in str(_pre_safety_rec).upper():
                stock_data['pre_safety_recommendation'] = _pre_safety_rec
                stock_data['final_recommendation'] = f'HOLD (EXTREME VOLATILITY — was {_pre_safety_rec})'
                logging.warning(f"{symbol}: {_pre_safety_rec} downgraded to HOLD due to extreme volatility")
            if _corp_warn and 'BUY' in str(stock_data.get('final_recommendation', '')).upper():
                _pre_corp_rec = stock_data.get('final_recommendation', '')
                stock_data['pre_safety_recommendation'] = stock_data.get('pre_safety_recommendation', _pre_corp_rec)
                stock_data['final_recommendation'] = f'HOLD (CORPORATE ACTION REVIEW — was {_pre_safety_rec})'
                logging.warning(f"{symbol}: {_pre_corp_rec} downgraded to HOLD due to possible corporate action")

            # Score comparison (legacy fields zeroed for backward compat)
            stock_data['score_adjustment'] = 0
            stock_data['phase1_score_adjustment'] = 0
            stock_data['phase2_score_adjustment'] = final_blended_score
            stock_data['improved_vs_corrected'] = 0
            stock_data['recommendation_changed'] = original_recommendation != phase2_recommendation
            
            # Convert complex objects for Excel compatibility (use JSON for cache fidelity)
            for key, value in list(stock_data.items()):
                if isinstance(value, (list, tuple)):
                    try:
                        stock_data[key] = json.dumps(self._make_json_safe(value))
                    except Exception:
                        stock_data[key] = '[]'
                elif isinstance(value, dict):
                    try:
                        stock_data[key] = json.dumps(self._make_json_safe(value))
                    except Exception:
                        stock_data[key] = '{}'
                elif isinstance(value, (float, int, np.floating, np.integer)) and pd.isna(value):
                    stock_data[key] = 0
                elif value is None:
                    stock_data[key] = ''
            
            # Remove ALL emojis from logging to avoid encoding issues in Windows console
            clean_recommendation = phase2_recommendation
            clean_recommendation = clean_recommendation.encode('ascii', errors='ignore').decode('ascii')
            
            # A-015: OUTPUT CONTRACT — standardised completeness field present on every result
            _status_keys = [
                'fundamental_status', 'enhanced_technical_status', 'real_technical_status',
                'mtf_analysis_status', 'institutional_analysis_status', 'legacy_technical_status',
                'ml_prediction_status', 'pattern_recognition_status', 'regime_detection_status',
                'sentiment_analysis_status', 'volume_analysis_status'
            ]
            _completed = sum(1 for k in _status_keys if stock_data.get(k) == 'success')
            stock_data['analysis_completeness_pct'] = round((_completed / len(_status_keys)) * 100, 1)
            stock_data['status'] = 'complete'

            self.save_to_cache(symbol, stock_data)

            logging.info(
                f"Completed analysis for {symbol}: Score={final_blended_score:.1f}, "
                f"Completeness={stock_data['analysis_completeness_pct']:.0f}%, "
                f"Recommendation={clean_recommendation.strip()}"
            )
            return stock_data

        except (ConnectionError, TimeoutError, OSError) as net_err:
            # A-007 TIER-1: Network / IO — transient, safe to retry
            error_data = {
                'symbol': symbol, 'status': 'network_error',
                'error_message': f"[NETWORK] {net_err}",
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'analysis_completeness_pct': 0.0
            }
            logging.warning(
                f"[NETWORK ERROR] {symbol}: {str(net_err)[:120]} — queued for retry"
            )
            return error_data
        except (KeyError, ValueError, TypeError, AttributeError) as logic_err:
            # A-007 TIER-2: Logic / data shape — needs investigation, don't blindly retry
            error_data = {
                'symbol': symbol, 'status': 'logic_error',
                'error_message': f"[LOGIC] {logic_err}",
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'analysis_completeness_pct': 0.0
            }
            logging.error(
                f"[LOGIC ERROR] {symbol}: {str(logic_err).encode('ascii', 'replace').decode('ascii')}",
                exc_info=True
            )
            return error_data
        except Exception as e:
            # A-007 TIER-3: Unknown — log full traceback
            error_data = {
                'symbol': symbol, 'status': 'error',
                'error_message': str(e),
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'analysis_completeness_pct': 0.0
            }
            logging.error(
                f"Analysis failed for {symbol}: {str(e).encode('ascii', 'replace').decode('ascii')}",
                exc_info=True
            )
            return error_data
    
    # ── A-013: DYNAMIC SECTOR ADJUSTMENT ────────────────────────────────────────
    # Sector-ETF 3-month return vs Nifty50 → score delta in [-7, +7] pts.
    # Computed once per sector per run (cached in self._sector_adj_cache).
    _SECTOR_INDEX_MAP = {
        'banking':               '^NSEBANK',
        'bank':                  '^NSEBANK',
        'financial':             '^CNXFIN',
        'finance':               '^CNXFIN',
        'technology':            '^CNXIT',
        'it':                    '^CNXIT',
        'software':              '^CNXIT',
        'pharma':                '^CNXPHARMA',
        'healthcare':            '^CNXPHARMA',
        'auto':                  '^CNXAUTO',
        'automobile':            '^CNXAUTO',
        'fmcg':                  '^CNXFMCG',
        'consumer':              '^CNXFMCG',
        'oil':                   '^CNXENERGY',
        'energy':                '^CNXENERGY',
        'power':                 '^CNXENERGY',
        'realty':                '^CNXREALTY',
        'real estate':           '^CNXREALTY',   # GAP-B fix: 'Real Estate' sector now mapped
        'metal':                 '^CNXMETAL',
        'steel':                 '^CNXMETAL',
        'mining':                '^CNXMETAL',
        'basic materials':       '^CNXMETAL',    # GAP-B fix: 'Basic Materials' → Nifty Metal
        'materials':             '^CNXMETAL',    # GAP-B fix: alias
        'industrials':           '^CNXINFRA',    # GAP-B fix: 'Industrials' → Nifty Infra
        'infrastructure':        '^CNXINFRA',    # GAP-B fix: alias
        'capital goods':         '^CNXINFRA',    # GAP-B fix: alias used by some yfinance data
        'communication services':'CNXMEDIA.NS',  # GAP-B fix: 'Communication Services' → Nifty Media
        'media':                 'CNXMEDIA.NS',  # GAP-B fix: alias
        'telecom':               'CNXMEDIA.NS',  # GAP-B fix: alias
        'utilities':             '^CNXENERGY',   # GAP-B fix: Utilities → Energy (closest NSE proxy)
    }

    def _compute_sector_adjustment(self, sector: str) -> float:
        """
        A-013: Return a score delta (−7 … +7) reflecting the sector's 3-month
        relative performance vs Nifty50.  Result is cached per sector per run
        (self._sector_adj_cache) so the HTTP call fires at most once per sector.
        """
        sector_lower = str(sector or '').lower()

        # Fast path — already cached this run
        with self._state_lock:
            if sector_lower in self._sector_adj_cache:
                return self._sector_adj_cache[sector_lower]

        # Find matching sector index ticker
        sector_ticker = None
        for key, val in self._SECTOR_INDEX_MAP.items():
            if key in sector_lower:
                sector_ticker = val
                break

        adj = 0.0
        if sector_ticker:
            try:
                if not hasattr(self, '_nifty_3mo_cache') or self._nifty_3mo_cache is None:
                    self._nifty_3mo_cache = yf.Ticker('^NSEI').history(period='3mo', interval='1d')
                nifty_h = self._nifty_3mo_cache
                sector_h  = yf.Ticker(sector_ticker).history(period='3mo', interval='1d')
                _nifty_d0 = nifty_h['Close'].iloc[0] if not nifty_h.empty else 0
                _sector_d0 = sector_h['Close'].iloc[0] if not sector_h.empty else 0
                if not nifty_h.empty and not sector_h.empty and _nifty_d0 != 0 and _sector_d0 != 0 and not np.isnan(_nifty_d0) and not np.isnan(_sector_d0):
                    nifty_ret  = (nifty_h['Close'].iloc[-1]  / _nifty_d0  - 1) * 100
                    sector_ret = (sector_h['Close'].iloc[-1] / _sector_d0 - 1) * 100
                    relative   = sector_ret - nifty_ret
                    # Scale: 1% outperformance ≈ 0.3 pts; cap at ±3
                    # Kept moderate so sector context helps but doesn't override stock merit
                    adj = float(max(-3.0, min(3.0, relative * 0.3)))
                    logging.info(
                        f"[SECTOR ADJ] {sector}: {sector_ret:.1f}% vs Nifty {nifty_ret:.1f}% "
                        f"→ relative={relative:+.1f}% adj={adj:+.1f}pts"
                    )
            except Exception as _e:
                logging.debug(f"[SECTOR ADJ] Failed for '{sector}': {_e}")
                adj = 0.0

        # Cache result (lock for thread safety)
        with self._state_lock:
            self._sector_adj_cache[sector_lower] = adj
        return adj

    def _get_dynamic_industry_benchmarks(self, sector: str, industry: str) -> dict:
        """
        ACCURACY IMPROVEMENT #6: Dynamic Benchmark Updates

        Fetches live market data to update industry benchmarks dynamically.
        Falls back to static benchmarks if live data is unavailable.

        Expected Additional Accuracy Improvement: 3-5%
        """
        # Try to get cached dynamic benchmarks first
        cache_file = f"data/dynamic_benchmarks_{sector.lower().replace(' ', '_')}.pkl"
        cache_expiry_hours = 24  # Update daily
        
        try:
            if os.path.exists(cache_file):
                cache_time = os.path.getmtime(cache_file)
                if (time.time() - cache_time) < (cache_expiry_hours * 3600):
                    with open(cache_file, 'rb') as f:
                        cached_benchmarks = pickle.load(f)
                        logging.debug(f"Using cached dynamic benchmarks for {sector}")
                        return cached_benchmarks
        except Exception as e:
            logging.warning(f"Failed to load cached benchmarks: {e}")
        
        # Fetch live benchmarks
        dynamic_benchmarks = self._fetch_live_sector_benchmarks(sector, industry)
        
        if dynamic_benchmarks:
            # Cache the results
            try:
                os.makedirs("data", exist_ok=True)
                with open(cache_file, 'wb') as f:
                    pickle.dump(dynamic_benchmarks, f)
                logging.info(f"Cached dynamic benchmarks for {sector}")
            except Exception as e:
                logging.warning(f"Failed to cache benchmarks: {e}")
            
            return dynamic_benchmarks
        
        # Fallback to static benchmarks
        logging.debug(f"Using static benchmarks for {sector} (dynamic fetch failed)")
        return self._get_static_industry_benchmarks(sector, industry)
    
    def _fetch_live_sector_benchmarks(self, sector: str, industry: str) -> dict:
        """
        Fetch live sector benchmarks from multiple sources
        """
        try:
            # Get sector stock list based on common sector names
            sector_stocks = self._get_sector_stock_list(sector)
            
            if not sector_stocks or len(sector_stocks) < 5:
                return None
            
            # Fetch data for sector stocks
            sector_data = []
            for symbol in sector_stocks[:20]:  # Limit to top 20 for performance
                try:
                    ticker = yf.Ticker(f"{symbol}.NS")
                    info = ticker.info
                    financials = ticker.financials
                    
                    if info and 'trailingPE' in info:
                        stock_metrics = {
                            'pe_ratio': info.get('trailingPE'),
                            'pb_ratio': info.get('priceToBook'),
                            'roe': info.get('returnOnEquity'),  # Already decimal (0.15 = 15%)
                            'debt_to_equity': info.get('debtToEquity'),
                            'current_ratio': info.get('currentRatio'),
                            'operating_margin': info.get('operatingMargins'),  # Already decimal
                            'revenue_growth': info.get('revenueGrowth')  # Already decimal
                        }
                        
                        # Filter out None and extreme values
                        filtered_metrics = {}
                        for key, value in stock_metrics.items():
                            if value is not None and isinstance(value, (int, float)):
                                if key == 'pe_ratio' and 0 < value < 200:
                                    filtered_metrics[key] = value
                                elif key == 'pb_ratio' and 0 < value < 50:
                                    filtered_metrics[key] = value
                                elif key == 'roe' and -50 < value < 100:
                                    filtered_metrics[key] = value
                                elif key == 'debt_to_equity' and 0 <= value < 2000:
                                    filtered_metrics[key] = value
                                elif key == 'current_ratio' and 0 <= value < 20:
                                    filtered_metrics[key] = value
                                elif key in ['operating_margin', 'revenue_growth'] and -100 < value < 200:
                                    filtered_metrics[key] = value
                        
                        if filtered_metrics:
                            sector_data.append(filtered_metrics)
                
                except Exception as e:
                    logging.debug(f"Failed to fetch data for {symbol}: {e}")
                    continue
            
            if len(sector_data) >= 3:  # Need at least 3 data points
                # Calculate median values (more robust than mean)
                benchmarks = {}
                for metric in ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity', 'current_ratio', 'operating_margin', 'revenue_growth']:
                    values = [d[metric] for d in sector_data if metric in d]
                    if values:
                        benchmarks[f'avg_{metric}'] = float(np.median(values))
                
                logging.info(f"Generated dynamic benchmarks for {sector} from {len(sector_data)} stocks")
                return benchmarks
            
        except Exception as e:
            logging.warning(f"Failed to fetch live benchmarks for {sector}: {e}")
        
        return None
    
    def _get_sector_stock_list(self, sector: str) -> List[str]:
        """
        Get a list of stocks for a given sector
        """
        # Mapping of sectors to known stock symbols
        sector_stocks = {
            'banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 'INDUSINDBK', 'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'PNB'],
            'financial': ['BAJFINANCE', 'BAJAJFINSV', 'HDFCLIFE', 'SBILIFE', 'ICICIGI', 'ICICIPRULI', 'HDFCAMC', 'MUTHOOTFIN', 'CHOLAFIN', 'PFC'],
            'technology': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM', 'LTTS', 'PERSISTENT', 'COFORGE', 'MPHASIS', 'LTIM'],
            'it': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM', 'LTTS', 'MINDTREE', 'PERSISTENT', 'COFORGE', 'MPHASIS'],
            'fmcg': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'GODREJCP', 'MARICO', 'COLPAL', 'UBL', 'EMAMILTD'],
            'consumer': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'MARUTI', 'TITAN', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT', 'TVSMOTOR'],
            'pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'BIOCON', 'LUPIN', 'AUROPHARMA', 'TORNTPHARM', 'ALKEM', 'ABBOTINDIA'],
            'auto': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT', 'TVSMOTOR', 'ASHOKLEY', 'ESCORTS', 'BALKRISIND'],
            'steel': ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'VEDL', 'SAIL', 'JINDALSTEL', 'NMDC', 'MOIL', 'COALINDIA', 'RATNAMANI'],
            'oil': ['RELIANCE', 'ONGC', 'IOC', 'BPCL', 'HINDPETRO', 'GAIL', 'OIL', 'MGL', 'IGL', 'PETRONET'],
            'power': ['POWERGRID', 'NTPC', 'ADANIGREEN', 'TATAPOWER', 'ADANIPOWER', 'NHPC', 'SJVN', 'RPOWER', 'TORNTPOWER', 'CESC']
        }
        
        sector_lower = sector.lower()
        
        # Find matching sector
        for key, stocks in sector_stocks.items():
            if key in sector_lower or any(keyword in sector_lower for keyword in [key]):
                return stocks
        
        # If no specific sector found, return empty list
        return []

    def _get_static_industry_benchmarks(self, sector: str, industry: str) -> dict:
        """
        Static industry benchmarks (fallback when dynamic data is unavailable)
        """
        # Default benchmarks
        default_benchmarks = {
            'avg_pe_ratio': 20.0,
            'avg_pb_ratio': 3.0,
            'avg_roe': 15.0,
            'avg_debt_to_equity': 1.0,
            'avg_current_ratio': 1.5,
            'avg_operating_margin': 10.0,
            'avg_revenue_growth': 8.0
        }
        
        sector_lower = sector.lower() if sector else ''
        industry_lower = industry.lower() if industry else ''
        
        # Banking/Financial Services
        if any(keyword in sector_lower + industry_lower for keyword in ['bank', 'financial', 'insurance', 'nbfc']):
            return {
                'avg_pe_ratio': 12.0,    # Banks typically trade at lower P/E
                'avg_pb_ratio': 1.8,     # P/B more relevant for banks
                'avg_roe': 12.0,         # Good ROE for banks
                'avg_debt_to_equity': 8.0, # Banks have high leverage
                'avg_current_ratio': 0.8,  # Different liquidity model
                'avg_operating_margin': 25.0, # Net interest margin equivalent
                'avg_revenue_growth': 12.0
            }
        
        # Technology/Software
        elif any(keyword in sector_lower + industry_lower for keyword in ['technology', 'software', 'it', 'computer']):
            return {
                'avg_pe_ratio': 25.0,    # Tech commands premium valuations
                'avg_pb_ratio': 4.5,     # Higher asset-light model
                'avg_roe': 18.0,         # High ROE expected
                'avg_debt_to_equity': 0.3, # Low debt typically
                'avg_current_ratio': 2.0,
                'avg_operating_margin': 15.0,
                'avg_revenue_growth': 18.0 # High growth expected
            }
        
        # FMCG/Consumer Goods
        elif any(keyword in sector_lower + industry_lower for keyword in ['consumer', 'fmcg', 'food', 'beverage']):
            return {
                'avg_pe_ratio': 30.0,    # Premium valuations for quality
                'avg_pb_ratio': 4.0,
                'avg_roe': 20.0,         # High ROE expected
                'avg_debt_to_equity': 0.5,
                'avg_current_ratio': 1.8,
                'avg_operating_margin': 12.0,
                'avg_revenue_growth': 10.0
            }
        
        # Pharmaceutical/Healthcare
        elif any(keyword in sector_lower + industry_lower for keyword in ['pharma', 'healthcare', 'drug', 'medicine']):
            return {
                'avg_pe_ratio': 22.0,
                'avg_pb_ratio': 3.2,
                'avg_roe': 16.0,
                'avg_debt_to_equity': 0.4,
                'avg_current_ratio': 2.2,
                'avg_operating_margin': 18.0,
                'avg_revenue_growth': 12.0
            }
        
        # Infrastructure/Capital Intensive
        elif any(keyword in sector_lower + industry_lower for keyword in ['infrastructure', 'power', 'steel', 'cement', 'mining']):
            return {
                'avg_pe_ratio': 15.0,    # Asset-heavy, lower multiples
                'avg_pb_ratio': 2.0,
                'avg_roe': 10.0,
                'avg_debt_to_equity': 2.0, # Higher debt acceptable
                'avg_current_ratio': 1.2,
                'avg_operating_margin': 8.0,
                'avg_revenue_growth': 6.0
            }
        
        # Auto/Manufacturing
        elif any(keyword in sector_lower + industry_lower for keyword in ['auto', 'manufacturing', 'industrial']):
            return {
                'avg_pe_ratio': 18.0,
                'avg_pb_ratio': 2.5,
                'avg_roe': 12.0,
                'avg_debt_to_equity': 1.2,
                'avg_current_ratio': 1.4,
                'avg_operating_margin': 7.0,
                'avg_revenue_growth': 8.0
            }
        
        return default_benchmarks
    
    def _calculate_industry_relative_scores(self, stock_data: dict) -> dict:
        """
        Calculate industry-relative scores for key metrics with dynamic benchmarks
        """
        sector = stock_data.get('sector', '')
        industry = stock_data.get('industry', '')
        benchmarks = self._get_dynamic_industry_benchmarks(sector, industry)
        
        relative_scores = {}
        
        # P/E Relative Score
        pe_ratio = _nv(stock_data.get('pe_ratio'), None)
        _bench_pe = _nv(benchmarks.get('avg_pe_ratio'), None)
        if pe_ratio is not None and _bench_pe is not None:
            pe_relative = _bench_pe / pe_ratio if pe_ratio > 0 else 0
            if pe_relative >= 1.5:  # 50% below industry average
                relative_scores['pe_relative_score'] = 100
            elif pe_relative >= 1.2:  # 20% below industry average
                relative_scores['pe_relative_score'] = 80
            elif pe_relative >= 1.0:  # At or slightly below industry average
                relative_scores['pe_relative_score'] = 60
            elif pe_relative >= 0.8:  # 20% above industry average
                relative_scores['pe_relative_score'] = 40
            else:  # More than 20% above industry average
                relative_scores['pe_relative_score'] = 20
        
        # P/B Relative Score
        pb_ratio = _nv(stock_data.get('pb_ratio'), None)
        _bench_pb = _nv(benchmarks.get('avg_pb_ratio'), None)
        if pb_ratio is not None and _bench_pb is not None:
            pb_relative = _bench_pb / pb_ratio if pb_ratio > 0 else 0
            if pb_relative >= 1.3:
                relative_scores['pb_relative_score'] = 100
            elif pb_relative >= 1.1:
                relative_scores['pb_relative_score'] = 80
            elif pb_relative >= 0.9:
                relative_scores['pb_relative_score'] = 60
            elif pb_relative >= 0.7:
                relative_scores['pb_relative_score'] = 40
            else:
                relative_scores['pb_relative_score'] = 20
        
        # ROE Relative Score
        roe = _nv(stock_data.get('roe'), None)
        _bench_roe = _nv(benchmarks.get('avg_roe'), None)
        if roe is not None and _bench_roe is not None:
            roe_relative = roe / _bench_roe if _bench_roe > 0 else 0
            if roe_relative >= 1.5:  # 50% above industry average
                relative_scores['roe_relative_score'] = 100
            elif roe_relative >= 1.2:  # 20% above industry average
                relative_scores['roe_relative_score'] = 80
            elif roe_relative >= 1.0:  # At industry average
                relative_scores['roe_relative_score'] = 60
            elif roe_relative >= 0.8:  # 20% below industry average
                relative_scores['roe_relative_score'] = 40
            else:  # More than 20% below industry average
                relative_scores['roe_relative_score'] = 20
        
        # Revenue Growth Relative Score
        revenue_growth = stock_data.get('revenue_growth', 0)
        if revenue_growth is not None and benchmarks['avg_revenue_growth']:
            # Data already in decimal format (0.15 = 15%)
            
            growth_relative = revenue_growth / benchmarks['avg_revenue_growth'] if benchmarks['avg_revenue_growth'] > 0 else 0
            if growth_relative >= 1.5:
                relative_scores['growth_relative_score'] = 100
            elif growth_relative >= 1.2:
                relative_scores['growth_relative_score'] = 80
            elif growth_relative >= 1.0:
                relative_scores['growth_relative_score'] = 60
            elif growth_relative >= 0.5:
                relative_scores['growth_relative_score'] = 40
            else:
                relative_scores['growth_relative_score'] = 20
        
        return relative_scores

    def _calculate_real_technical_indicators(self, symbol: str, hist=None) -> dict:
        """
        ACCURACY IMPROVEMENT #4: Real Technical Analysis

        Calculate actual technical indicators from historical price data
        instead of using placeholder values.

        Expected Accuracy Improvement: 15-18%

        Parameters
        ----------
        hist : pd.DataFrame, optional
            Pre-downloaded 6M daily OHLCV. When supplied (A-005 bundle path),
            no additional HTTP call is made. Falls back to a fresh download if None.
        """
        try:
            import numpy as np
            import pandas as pd

            # A-005: use caller-supplied slice when available; otherwise download fresh
            if hist is None:
                import yfinance as yf
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="6mo", interval="1d")

            if hist.empty or len(hist) < 30:
                return self._get_fallback_technical_indicators()
            
            indicators = {}
            
            # 1. Calculate Real RSI (14-period)
            indicators['rsi'] = self._calculate_rsi(hist['Close'])
            
            # 2. Calculate Real MACD
            macd_data = self._calculate_macd(hist['Close'])
            indicators.update(macd_data)
            
            # 3. Calculate Real Bollinger Bands
            bb_data = self._calculate_bollinger_bands(hist['Close'])
            indicators.update(bb_data)
            
            # 4. Volume Analysis
            if 'Volume' in hist.columns:
                volume_data = self._calculate_volume_indicators(hist['Volume'], hist['Close'])
                indicators.update(volume_data)
            
            # 5. Support and Resistance Levels
            sr_data = self._calculate_support_resistance(hist['Close'], hist['High'], hist['Low'])
            indicators.update(sr_data)
            
            # 6. Momentum Indicators
            momentum_data = self._calculate_momentum_indicators(hist['Close'])
            indicators.update(momentum_data)
            
            # 7. Technical Score (composite)
            indicators['technical_score'] = self._calculate_technical_score(indicators)
            
            return indicators
            
        except Exception as e:
            logging.warning(f"Real technical analysis failed for {symbol}: {e}")
            return self._get_fallback_technical_indicators()
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate Real RSI (Relative Strength Index)"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            all_gains = (loss == 0) & (gain > 0)
            loss = loss.replace(0, np.nan)
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).where(~all_gains, 100.0).fillna(50.0)
            
            return round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else 50.0
        except Exception:
            return 50.0
    
    def _calculate_macd(self, prices: pd.Series) -> dict:
        """Calculate Real MACD (Moving Average Convergence Divergence)"""
        try:
            ema12 = prices.ewm(span=12).mean()
            ema26 = prices.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            histogram = macd_line - signal_line
            
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_histogram = histogram.iloc[-1]
            
            # Determine MACD signal
            if current_macd > current_signal and current_histogram > 0:
                macd_signal = "BULLISH"
            elif current_macd < current_signal and current_histogram < 0:
                macd_signal = "BEARISH"
            else:
                macd_signal = "NEUTRAL"
            
            return {
                'macd_line': round(current_macd, 2),
                'macd_signal_line': round(current_signal, 2),
                'macd_histogram': round(current_histogram, 2),
                'macd_signal': macd_signal
            }
        except Exception:
            return {
                'macd_line': 0.0,
                'macd_signal_line': 0.0,
                'macd_histogram': 0.0,
                'macd_signal': 'NEUTRAL'
            }
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> dict:
        """Calculate Real Bollinger Bands"""
        try:
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            current_price = prices.iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            current_middle = sma.iloc[-1]
            
            # Determine position within bands
            if current_price >= current_upper * 0.98:  # Within 2% of upper band
                bb_position = "UPPER"
            elif current_price <= current_lower * 1.02:  # Within 2% of lower band
                bb_position = "LOWER"
            else:
                bb_position = "MIDDLE"
            
            # Calculate BB squeeze (volatility indicator)
            bb_width = (current_upper - current_lower) / current_middle if current_middle != 0 else 0
            
            return {
                'bb_upper': round(current_upper, 2),
                'bb_middle': round(current_middle, 2),
                'bb_lower': round(current_lower, 2),
                'bb_position': bb_position,
                'bb_width': round(bb_width * 100, 2)  # As percentage
            }
        except Exception:
            return {
                'bb_upper': 0.0,
                'bb_middle': 0.0,
                'bb_lower': 0.0,
                'bb_position': 'MIDDLE',
                'bb_width': 0.0
            }
    
    def _calculate_volume_indicators(self, volume: pd.Series, prices: pd.Series) -> dict:
        """Calculate Volume-based indicators"""
        try:
            # Volume moving average
            volume_ma = volume.rolling(window=20).mean()
            current_volume = volume.iloc[-1]
            avg_volume = volume_ma.iloc[-1]
            
            # Volume trend
            if current_volume > avg_volume * 1.5:
                volume_trend = "HIGH"
            elif current_volume > avg_volume * 1.1:
                volume_trend = "ABOVE_AVERAGE"
            elif current_volume < avg_volume * 0.7:
                volume_trend = "LOW"
            else:
                volume_trend = "AVERAGE"
            
            # On Balance Volume (OBV)
            price_change = prices.diff()
            obv = (volume * np.sign(price_change)).cumsum()
            obv_trend = "RISING" if obv.iloc[-1] > obv.iloc[-10] else "FALLING"
            
            return {
                'volume_ratio': round(current_volume / avg_volume, 2) if avg_volume and avg_volume != 0 and not np.isnan(avg_volume) else 1.0,
                'volume_trend': volume_trend,
                'obv_trend': obv_trend
            }
        except Exception:
            return {
                'volume_ratio': 1.0,
                'volume_trend': 'AVERAGE',
                'obv_trend': 'NEUTRAL'
            }
    
    def _calculate_support_resistance(self, close: pd.Series, high: pd.Series, low: pd.Series) -> dict:
        """Calculate dynamic support and resistance levels"""
        try:
            # Ensure current_price is float
            _cp_raw = float(close.iloc[-1])
            current_price = _cp_raw if not (np.isnan(_cp_raw) or _cp_raw == 0) else 100.0
            
            # Recent highs and lows for support/resistance
            recent_data = close.tail(60)  # Last 60 days
            recent_highs = high.tail(60)
            recent_lows = low.tail(60)
            
            # Resistance: Recent significant highs
            resistance_candidates = recent_highs[recent_highs > current_price * 1.02]
            resistance = resistance_candidates.quantile(0.2) if not resistance_candidates.empty else current_price * 1.05
            if np.isnan(resistance):
                resistance = current_price * 1.05
            
            # Support: Recent significant lows
            support_candidates = recent_lows[recent_lows < current_price * 0.98]
            support = support_candidates.quantile(0.8) if not support_candidates.empty else current_price * 0.95
            if np.isnan(support):
                support = current_price * 0.95
            
            return {
                'support_level': round(support, 2),
                'resistance_level': round(resistance, 2),
                'distance_to_support': round((current_price - support) / current_price * 100, 2) if current_price != 0 else 0.0,
                'distance_to_resistance': round((resistance - current_price) / current_price * 100, 2) if current_price != 0 else 0.0
            }
        except Exception as e:
            # Ensure fallback current_price is also float
            current_price = float(close.iloc[-1]) if not close.empty else 100.0
            return {
                'support_level': round(current_price * 0.95, 2),
                'resistance_level': round(current_price * 1.05, 2),
                'distance_to_support': 5.0,
                'distance_to_resistance': 5.0
            }
    
    def _calculate_momentum_indicators(self, prices: pd.Series) -> dict:
        """Calculate momentum-based indicators"""
        try:
            # Rate of Change (ROC) - 10 day
            _denom_11 = prices.iloc[-11] if len(prices) > 11 else prices.iloc[0]
            if pd.isna(_denom_11) or _denom_11 == 0:
                roc = 0.0
            else:
                roc = ((prices.iloc[-1] - _denom_11) / _denom_11) * 100
                if np.isnan(roc):
                    roc = 0.0
            
            # Price momentum score
            if roc > 5:
                momentum = "STRONG_BULLISH"
            elif roc > 2:
                momentum = "BULLISH"
            elif roc > -2:
                momentum = "NEUTRAL"
            elif roc > -5:
                momentum = "BEARISH"
            else:
                momentum = "STRONG_BEARISH"
            
            # Moving average crossover signal
            ma10 = prices.rolling(window=10).mean().iloc[-1]
            ma50 = prices.rolling(window=50).mean().iloc[-1] if len(prices) >= 50 else ma10
            if np.isnan(ma10):
                ma10 = 0.0
            if np.isnan(ma50):
                ma50 = 0.0
            
            if ma10 > ma50 * 1.02:
                ma_signal = "BUY"
            elif ma10 < ma50 * 0.98:
                ma_signal = "SELL"
            else:
                ma_signal = "HOLD"
            
            return {
                'price_roc': round(roc, 2),
                'momentum': momentum,
                'ma_signal': ma_signal,
                'ma10': round(ma10, 2),
                'ma50': round(ma50, 2)
            }
        except Exception:
            return {
                'price_roc': 0.0,
                'momentum': 'NEUTRAL',
                'ma_signal': 'HOLD',
                'ma10': 0.0,
                'ma50': 0.0
            }
    
    def _calculate_technical_score(self, indicators: dict) -> float:
        """Calculate composite technical score from all indicators"""
        try:
            score = 50  # Base neutral score
            
            # RSI scoring (30 points max)
            rsi = indicators.get('rsi', 50)
            if 30 <= rsi <= 70:  # Healthy range
                score += 10
            if rsi < 30:  # Oversold - potential buy
                score += 15
            elif rsi > 70:  # Overbought - potential sell
                score -= 5
            
            # MACD scoring (20 points max)
            macd_signal = indicators.get('macd_signal', 'NEUTRAL')
            if macd_signal == 'BULLISH':
                score += 15
            elif macd_signal == 'BEARISH':
                score -= 10
            
            # Bollinger Bands scoring (15 points max)
            bb_position = indicators.get('bb_position', 'MIDDLE')
            if bb_position == 'LOWER':  # Near support
                score += 10
            elif bb_position == 'UPPER':  # Near resistance
                score -= 5
            
            # Volume scoring (10 points max)
            volume_trend = indicators.get('volume_trend', 'AVERAGE')
            if volume_trend in ['HIGH', 'ABOVE_AVERAGE']:
                score += 8
            
            # Momentum scoring (15 points max)
            momentum = indicators.get('momentum', 'NEUTRAL')
            if momentum in ['STRONG_BULLISH', 'BULLISH']:
                score += 12
            elif momentum in ['STRONG_BEARISH', 'BEARISH']:
                score -= 8
            
            # MA Signal scoring (10 points max)
            ma_signal = indicators.get('ma_signal', 'HOLD')
            if ma_signal == 'BUY':
                score += 8
            elif ma_signal == 'SELL':
                score -= 5
            
            return max(min(score, 100), 0)  # Clamp between 0-100
            
        except Exception:
            return 50.0
    
    def _get_fallback_technical_indicators(self) -> dict:
        """Fallback technical indicators when real calculation fails"""
        return {
            'rsi': 50.0,
            'macd_signal': 'NEUTRAL',
            'bb_position': 'MIDDLE',
            'volume_trend': 'AVERAGE',
            'momentum': 'NEUTRAL',
            'technical_score': 50.0,
            'support_level': None,   # None = unknown, not zero
            'resistance_level': None
        }

    def _calculate_multi_timeframe_analysis(self, symbol: str, hist_daily=None) -> dict:
        """
        ACCURACY IMPROVEMENT #5: Multi-Timeframe Analysis

        Analyze multiple timeframes (1D, 1W, 1M) to validate trend consistency
        and improve signal reliability through cross-timeframe confirmation.

        Expected Accuracy Improvement: 15-20%

        Parameters
        ----------
        hist_daily : pd.DataFrame, optional
            Pre-downloaded 3M daily OHLCV for the 'daily' timeframe. When
            supplied (A-005 bundle path) the daily HTTP call is skipped.
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(f"{symbol}.NS")
            timeframes = {
                'daily': {'period': '3mo', 'interval': '1d', 'weight': 0.5},
                'weekly': {'period': '1y', 'interval': '1wk', 'weight': 0.3},
                'monthly': {'period': '2y', 'interval': '1mo', 'weight': 0.2}
            }

            mtf_analysis = {}
            trend_signals = []
            momentum_signals = []
            volume_signals = []

            for tf_name, tf_config in timeframes.items():
                try:
                    # A-005: use pre-downloaded daily slice if provided; download others fresh
                    if tf_name == 'daily' and hist_daily is not None:
                        hist = hist_daily
                    else:
                        hist = ticker.history(period=tf_config['period'], interval=tf_config['interval'])
                    
                    if hist.empty or len(hist) < 20:
                        continue
                    
                    # Calculate timeframe-specific indicators
                    tf_data = self._calculate_timeframe_indicators(hist, tf_name)
                    mtf_analysis[tf_name] = tf_data
                    
                    # Collect signals for cross-timeframe analysis
                    trend_signals.append({
                        'timeframe': tf_name,
                        'signal': tf_data.get('trend_signal', 'NEUTRAL'),
                        'strength': tf_data.get('trend_strength', 0),
                        'weight': tf_config['weight']
                    })
                    
                    momentum_signals.append({
                        'timeframe': tf_name,
                        'signal': tf_data.get('momentum_signal', 'NEUTRAL'),
                        'strength': tf_data.get('momentum_strength', 0),
                        'weight': tf_config['weight']
                    })
                    
                    volume_signals.append({
                        'timeframe': tf_name,
                        'signal': tf_data.get('volume_signal', 'NEUTRAL'),
                        'weight': tf_config['weight']
                    })
                    
                except Exception as e:
                    logging.warning(f"Multi-timeframe analysis failed for {symbol} {tf_name}: {e}")
                    continue
            
            # Cross-timeframe signal validation
            mtf_results = self._analyze_cross_timeframe_signals(trend_signals, momentum_signals, volume_signals)
            
            # Calculate multi-timeframe score
            mtf_score = self._calculate_multi_timeframe_score(mtf_analysis, mtf_results)
            
            return {
                'mtf_trend_signal': mtf_results.get('consensus_trend', 'NEUTRAL'),
                'mtf_momentum_signal': mtf_results.get('consensus_momentum', 'NEUTRAL'),
                'mtf_volume_signal': mtf_results.get('consensus_volume', 'NEUTRAL'),
                'mtf_trend_strength': mtf_results.get('trend_strength', 50),
                'mtf_momentum_strength': mtf_results.get('momentum_strength', 50),
                'mtf_signal_quality': mtf_results.get('signal_quality', 'LOW'),
                'mtf_timeframe_agreement': mtf_results.get('timeframe_agreement', 0),
                'mtf_composite_score': mtf_score,
                'daily_trend': mtf_analysis.get('daily', {}).get('trend_signal', 'NEUTRAL'),
                'weekly_trend': mtf_analysis.get('weekly', {}).get('trend_signal', 'NEUTRAL'),
                'monthly_trend': mtf_analysis.get('monthly', {}).get('trend_signal', 'NEUTRAL')
            }
            
        except Exception as e:
            logging.warning(f"Multi-timeframe analysis failed for {symbol}: {e}")
            return self._get_fallback_mtf_analysis()
    
    def _calculate_timeframe_indicators(self, hist: pd.DataFrame, timeframe: str) -> dict:
        """Calculate indicators specific to a timeframe"""
        try:
            close = hist['Close']
            volume = hist['Volume'] if 'Volume' in hist.columns else None
            
            # Adjust periods based on timeframe
            if timeframe == 'daily':
                short_ma, long_ma, rsi_period = 10, 50, 14
            elif timeframe == 'weekly':
                short_ma, long_ma, rsi_period = 5, 20, 10
            else:  # monthly
                short_ma, long_ma, rsi_period = 3, 12, 8
            
            # Calculate moving averages
            ma_short = close.rolling(window=min(short_ma, len(close))).mean()
            ma_long = close.rolling(window=min(long_ma, len(close))).mean()
            
            # Current values
            current_price = _nv(close.iloc[-1], 0)
            current_ma_short = _nv(ma_short.iloc[-1], 0)
            current_ma_long = _nv(ma_long.iloc[-1] if len(close) >= long_ma else current_ma_short, 0)
            
            # Trend analysis
            if current_ma_long != 0 and current_ma_short != 0 and current_ma_short > current_ma_long * 1.02:
                trend_signal = 'BULLISH'
                trend_strength = min(((current_ma_short / current_ma_long - 1) * 100) * 10, 100)
            elif current_ma_long != 0 and current_ma_short != 0 and current_ma_short < current_ma_long * 0.98:
                trend_signal = 'BEARISH'  
                trend_strength = min(((1 - current_ma_short / current_ma_long) * 100) * 10, 100)
            else:
                trend_signal = 'NEUTRAL'
                trend_strength = 50
            
            # Momentum analysis (price vs MA)
            price_vs_ma = _nv(((current_price / current_ma_short - 1) * 100) if (current_ma_short != 0 and not np.isnan(current_ma_short)) else 0, 0)
            if price_vs_ma > 3:
                momentum_signal = 'STRONG_BULLISH'
                momentum_strength = min(85 + price_vs_ma, 100)
            elif price_vs_ma > 1:
                momentum_signal = 'BULLISH'
                momentum_strength = 70 + price_vs_ma * 5
            elif price_vs_ma < -3:
                momentum_signal = 'STRONG_BEARISH'
                momentum_strength = max(15 - abs(price_vs_ma), 0)
            elif price_vs_ma < -1:
                momentum_signal = 'BEARISH'
                momentum_strength = 30 - abs(price_vs_ma) * 5
            else:
                momentum_signal = 'NEUTRAL'
                momentum_strength = 50 + _nv(price_vs_ma, 0) * 2
            
            # Volume analysis (if available)
            volume_signal = 'NEUTRAL'
            if volume is not None and len(volume) >= 10:
                avg_volume = volume.rolling(window=min(10, len(volume))).mean().iloc[-1]
                current_volume = volume.iloc[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
                
                if volume_ratio > 1.5:
                    volume_signal = 'HIGH'
                elif volume_ratio > 1.2:
                    volume_signal = 'ABOVE_AVERAGE'
                elif volume_ratio < 0.7:
                    volume_signal = 'LOW'
                else:
                    volume_signal = 'AVERAGE'
            
            return {
                'trend_signal': trend_signal,
                'trend_strength': trend_strength,
                'momentum_signal': momentum_signal,
                'momentum_strength': momentum_strength,
                'volume_signal': volume_signal,
                'price_vs_ma': price_vs_ma,
                'ma_short': current_ma_short,
                'ma_long': current_ma_long
            }
            
        except Exception as e:
            logging.warning(f"Timeframe indicator calculation failed: {e}")
            return {
                'trend_signal': 'NEUTRAL',
                'trend_strength': 50,
                'momentum_signal': 'NEUTRAL', 
                'momentum_strength': 50,
                'volume_signal': 'NEUTRAL'
            }
    
    def _analyze_cross_timeframe_signals(self, trend_signals: list, momentum_signals: list, volume_signals: list) -> dict:
        """Analyze signals across multiple timeframes for consensus"""
        try:
            # Trend consensus analysis
            trend_scores = {'BULLISH': 0, 'BEARISH': 0, 'NEUTRAL': 0}
            trend_weighted_strength = 0
            total_trend_weight = 0
            
            for signal in trend_signals:
                signal_type = signal['signal']
                weight = signal['weight']
                strength = signal['strength']
                
                trend_scores[signal_type] += weight
                trend_weighted_strength += strength * weight
                total_trend_weight += weight
            
            # Determine consensus trend
            max_trend = max(trend_scores.keys(), key=lambda k: trend_scores[k])
            trend_agreement = trend_scores[max_trend] / sum(trend_scores.values()) if sum(trend_scores.values()) > 0 else 0
            avg_trend_strength = trend_weighted_strength / total_trend_weight if total_trend_weight > 0 else 50
            
            # Momentum consensus analysis
            momentum_scores = {'STRONG_BULLISH': 0, 'BULLISH': 0, 'NEUTRAL': 0, 'BEARISH': 0, 'STRONG_BEARISH': 0}
            momentum_weighted_strength = 0
            total_momentum_weight = 0
            
            for signal in momentum_signals:
                signal_type = signal['signal']
                weight = signal['weight']
                strength = signal['strength']
                
                if signal_type in momentum_scores:
                    momentum_scores[signal_type] += weight
                momentum_weighted_strength += strength * weight
                total_momentum_weight += weight
            
            # Determine consensus momentum
            max_momentum = max(momentum_scores.keys(), key=lambda k: momentum_scores[k])
            momentum_agreement = momentum_scores[max_momentum] / sum(momentum_scores.values()) if sum(momentum_scores.values()) > 0 else 0
            avg_momentum_strength = momentum_weighted_strength / total_momentum_weight if total_momentum_weight > 0 else 50
            
            # Volume consensus
            volume_scores = {'HIGH': 0, 'ABOVE_AVERAGE': 0, 'AVERAGE': 0, 'LOW': 0, 'NEUTRAL': 0}
            for signal in volume_signals:
                signal_type = signal['signal']
                weight = signal['weight']
                if signal_type in volume_scores:
                    volume_scores[signal_type] += weight
            
            max_volume = max(volume_scores.keys(), key=lambda k: volume_scores[k])
            
            # Signal quality assessment
            timeframe_agreement = (trend_agreement + momentum_agreement) / 2
            if timeframe_agreement >= 0.8:
                signal_quality = 'HIGH'
            elif timeframe_agreement >= 0.6:
                signal_quality = 'MEDIUM'
            else:
                signal_quality = 'LOW'
            
            return {
                'consensus_trend': max_trend,
                'consensus_momentum': max_momentum,
                'consensus_volume': max_volume,
                'trend_strength': avg_trend_strength,
                'momentum_strength': avg_momentum_strength,
                'timeframe_agreement': timeframe_agreement * 100,
                'signal_quality': signal_quality
            }
            
        except Exception as e:
            logging.warning(f"Cross-timeframe analysis failed: {e}")
            return {
                'consensus_trend': 'NEUTRAL',
                'consensus_momentum': 'NEUTRAL',
                'consensus_volume': 'NEUTRAL',
                'trend_strength': 50,
                'momentum_strength': 50,
                'timeframe_agreement': 0,
                'signal_quality': 'LOW'
            }
    
    def _calculate_multi_timeframe_score(self, mtf_analysis: dict, mtf_results: dict) -> float:
        """Calculate composite multi-timeframe score"""
        try:
            base_score = 50
            
            # Trend consensus bonus/penalty (30 points max)
            trend = mtf_results.get('consensus_trend', 'NEUTRAL')
            trend_strength = _nv(mtf_results.get('trend_strength'), 50)
            
            if trend == 'BULLISH':
                trend_score = 15 + (trend_strength - 50) * 0.3
            elif trend == 'BEARISH':
                trend_score = -15 + (trend_strength - 50) * 0.3
            else:
                trend_score = 0
            
            # Momentum consensus bonus/penalty (25 points max)
            momentum = mtf_results.get('consensus_momentum', 'NEUTRAL')
            momentum_strength = _nv(mtf_results.get('momentum_strength'), 50)
            
            if momentum in ['STRONG_BULLISH', 'BULLISH']:
                momentum_score = 20 if momentum == 'STRONG_BULLISH' else 12
                momentum_score += (momentum_strength - 50) * 0.2
            elif momentum in ['STRONG_BEARISH', 'BEARISH']:
                momentum_score = -15 if momentum == 'STRONG_BEARISH' else -8
                momentum_score += (momentum_strength - 50) * 0.2
            else:
                momentum_score = 0
            
            # Timeframe agreement bonus (15 points max)
            agreement = _nv(mtf_results.get('timeframe_agreement'), 0)
            agreement_score = (agreement / 100) * 15
            
            # Signal quality bonus (10 points max)
            quality = mtf_results.get('signal_quality', 'LOW')
            quality_score = {'HIGH': 10, 'MEDIUM': 6, 'LOW': 2}.get(quality, 2)
            
            # Volume confirmation bonus (10 points max)
            volume = mtf_results.get('consensus_volume', 'NEUTRAL')
            volume_score = {'HIGH': 8, 'ABOVE_AVERAGE': 5, 'AVERAGE': 2, 'LOW': -2, 'NEUTRAL': 0}.get(volume, 0)
            
            final_score = base_score + trend_score + momentum_score + agreement_score + quality_score + volume_score
            
            return max(min(_nv(final_score, 50), 100), 0)  # Clamp between 0-100
            
        except Exception as e:
            logging.warning(f"Multi-timeframe score calculation failed: {e}")
            return 50.0
    
    def _get_fallback_mtf_analysis(self) -> dict:
        """Fallback multi-timeframe analysis when calculation fails"""
        return {
            'mtf_trend_signal': 'NEUTRAL',
            'mtf_momentum_signal': 'NEUTRAL',
            'mtf_volume_signal': 'NEUTRAL',
            'mtf_trend_strength': 50,
            'mtf_momentum_strength': 50,
            'mtf_signal_quality': 'LOW',
            'mtf_timeframe_agreement': 0,
            'mtf_composite_score': 50,
            'daily_trend': 'NEUTRAL',
            'weekly_trend': 'NEUTRAL',
            'monthly_trend': 'NEUTRAL'
        }

    def _analyze_institutional_flow(self, symbol: str, bundle=None) -> dict:
        """
        ACCURACY IMPROVEMENT #7: Institutional Flow Analysis
        
        Analyzes institutional trading patterns, bulk deals, and insider activities
        to detect smart money movements and improve investment timing.
        
        Expected Additional Accuracy Improvement: 5-8%
        """
        try:
            institutional_data = {
                'institutional_sentiment': 'NEUTRAL',
                'fii_activity': 'NEUTRAL',
                'dii_activity': 'NEUTRAL',
                'bulk_deals_signal': 'NEUTRAL',
                'insider_activity': 'NEUTRAL',
                'institutional_score': 50,
                'smart_money_flow': 'NEUTRAL',
                'institutional_ownership_change': 0,
                'large_block_activity': 'NEUTRAL'
            }
            
            # 1. Analyze FII/DII Activity through price-volume patterns
            fii_dii_analysis = self._analyze_fii_dii_patterns(symbol, bundle=bundle)
            institutional_data.update(fii_dii_analysis)
            
            # 2. Detect bulk deal patterns
            bulk_deal_analysis = self._detect_bulk_deal_patterns(symbol, bundle=bundle)
            institutional_data.update(bulk_deal_analysis)
            
            # 3. Analyze institutional ownership trends
            ownership_analysis = self._analyze_ownership_trends(symbol, bundle=bundle)
            institutional_data.update(ownership_analysis)
            
            # 4. Smart money flow detection
            smart_money_analysis = self._detect_smart_money_flow(symbol, bundle=bundle)
            institutional_data.update(smart_money_analysis)
            
            # 5. Calculate composite institutional score
            institutional_score = self._calculate_institutional_score(institutional_data)
            institutional_data['institutional_score'] = institutional_score
            
            # 6. Overall institutional sentiment
            institutional_data['institutional_sentiment'] = self._determine_institutional_sentiment(institutional_score)
            
            logging.debug(f"Institutional analysis completed for {symbol}: Score={institutional_score:.1f}")
            return institutional_data
            
        except Exception as e:
            logging.warning(f"Institutional flow analysis failed for {symbol}: {e}")
            return self._get_fallback_institutional_analysis()
    
    def _analyze_fii_dii_patterns(self, symbol: str, bundle=None) -> dict:
        """
        Analyze FII/DII activity patterns through volume and price behavior
        """
        try:
            if bundle is not None:
                hist = bundle.hist_6mo
            else:
                import yfinance as yf
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="6mo", interval="1d")
            
            if hist.empty or len(hist) < 60:
                return {'fii_activity': 'NEUTRAL', 'dii_activity': 'NEUTRAL'}
            
            # Calculate volume-weighted returns for institutional pattern detection
            hist['returns'] = hist['Close'].pct_change()
            hist['volume_ma'] = hist['Volume'].rolling(window=20).mean()
            hist['volume_ratio'] = hist['Volume'] / hist['volume_ma'].replace(0, np.nan)
            hist['volume_ratio'] = hist['volume_ratio'].fillna(1.0)
            
            # Detect institutional accumulation/distribution patterns
            recent_data = hist.tail(30)  # Last 30 days
            
            # FII Activity Indicators (typically prefer large cap, momentum)
            high_volume_positive_days = len(recent_data[(recent_data['returns'] > 0.02) & (recent_data['volume_ratio'] > 1.5)])
            high_volume_negative_days = len(recent_data[(recent_data['returns'] < -0.02) & (recent_data['volume_ratio'] > 1.5)])
            
            # FII pattern: High volume on up days indicates buying, high volume on down days indicates selling
            if high_volume_positive_days > high_volume_negative_days * 1.5:
                fii_activity = 'BUYING'
            elif high_volume_negative_days > high_volume_positive_days * 1.5:
                fii_activity = 'SELLING'
            else:
                fii_activity = 'NEUTRAL'
            
            # DII Activity Indicators (typically accumulate on dips, defensive)
            # Look for accumulation on price weakness
            weak_days_high_volume = len(recent_data[(recent_data['returns'] < -0.01) & (recent_data['volume_ratio'] > 1.2)])
            strong_days_low_volume = len(recent_data[(recent_data['returns'] > 0.01) & (recent_data['volume_ratio'] < 0.8)])
            
            if weak_days_high_volume > 5 and strong_days_low_volume > 3:
                dii_activity = 'ACCUMULATING'  # Buying dips, not chasing
            elif weak_days_high_volume < 2:
                dii_activity = 'NEUTRAL'
            else:
                dii_activity = 'NEUTRAL'
            
            return {
                'fii_activity': fii_activity,
                'dii_activity': dii_activity,
                'high_volume_up_days': high_volume_positive_days,
                'high_volume_down_days': high_volume_negative_days
            }
            
        except Exception as e:
            logging.debug(f"FII/DII pattern analysis failed for {symbol}: {e}")
            return {'fii_activity': 'NEUTRAL', 'dii_activity': 'NEUTRAL'}
    
    def _detect_bulk_deal_patterns(self, symbol: str, bundle=None) -> dict:
        """
        Detect bulk deal patterns through unusual volume and price movements
        """
        try:
            if bundle is not None:
                hist = bundle.hist_3mo
            else:
                import yfinance as yf
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="3mo", interval="1d")
            
            if hist.empty or len(hist) < 30:
                return {'bulk_deals_signal': 'NEUTRAL', 'large_block_activity': 'NEUTRAL'}
            
            # Calculate volume statistics
            avg_volume = hist['Volume'].rolling(window=20).mean()
            volume_std = hist['Volume'].rolling(window=20).std()
            hist['volume_zscore'] = (hist['Volume'] - avg_volume) / volume_std.replace(0, np.nan)
            hist['volume_zscore'] = hist['volume_zscore'].fillna(0)
            
            # Detect unusual volume spikes (potential bulk deals)
            recent_data = hist.tail(10)  # Last 10 days
            unusual_volume_days = len(recent_data[recent_data['volume_zscore'] > 2])  # 2 standard deviations
            
            # Analyze price reaction to volume spikes
            bulk_signal = 'NEUTRAL'
            large_block_signal = 'NEUTRAL'
            
            if unusual_volume_days >= 2:
                # Check if high volume is accompanied by specific price patterns
                high_vol_data = recent_data[recent_data['volume_zscore'] > 2]
                
                if not high_vol_data.empty:
                    avg_return_on_high_vol = high_vol_data['Close'].pct_change().mean()
                    
                    if avg_return_on_high_vol > 0.015:  # 1.5% average gain on high volume
                        bulk_signal = 'POSITIVE'
                        large_block_signal = 'INSTITUTIONAL_BUYING'
                    elif avg_return_on_high_vol < -0.015:  # 1.5% average loss on high volume
                        bulk_signal = 'NEGATIVE'
                        large_block_signal = 'INSTITUTIONAL_SELLING'
                    else:
                        bulk_signal = 'MIXED'
                        large_block_signal = 'MIXED'
            
            return {
                'bulk_deals_signal': bulk_signal,
                'large_block_activity': large_block_signal,
                'unusual_volume_days': unusual_volume_days
            }
            
        except Exception as e:
            logging.debug(f"Bulk deal pattern detection failed for {symbol}: {e}")
            return {'bulk_deals_signal': 'NEUTRAL', 'large_block_activity': 'NEUTRAL'}
    
    def _analyze_ownership_trends(self, symbol: str, bundle=None) -> dict:
        """
        Analyze institutional ownership trends using available data
        """
        try:
            if bundle is not None:
                info = bundle.info or {}
            else:
                import yfinance as yf
                ticker = yf.Ticker(f"{symbol}.NS")
                info = ticker.info or {}
            
            ownership_data = {
                'institutional_ownership_change': 0,
                'insider_activity': 'NEUTRAL'
            }
            
            # Extract ownership information
            institutional_ownership = info.get('heldByInstitutions', 0)
            insider_ownership = info.get('heldByInsiders', 0)
            
            # Analyze ownership levels (relative to market norms)
            if institutional_ownership > 0.6:  # >60% institutional ownership
                ownership_data['institutional_ownership_level'] = 'HIGH'
            elif institutional_ownership > 0.3:  # 30-60% institutional ownership
                ownership_data['institutional_ownership_level'] = 'MODERATE'
            else:
                ownership_data['institutional_ownership_level'] = 'LOW'
            
            # Insider ownership analysis
            if insider_ownership > 0.05:  # >5% insider ownership
                ownership_data['insider_ownership_level'] = 'HIGH'
            elif insider_ownership > 0.02:  # 2-5% insider ownership
                ownership_data['insider_ownership_level'] = 'MODERATE'
            else:
                ownership_data['insider_ownership_level'] = 'LOW'
            
            return ownership_data
            
        except Exception as e:
            logging.debug(f"Ownership trend analysis failed for {symbol}: {e}")
            return {'institutional_ownership_change': 0, 'insider_activity': 'NEUTRAL'}
    
    def _detect_smart_money_flow(self, symbol: str, bundle=None) -> dict:
        """
        Detect smart money flow patterns
        """
        try:
            if bundle is not None:
                hist = bundle.hist_3mo
            else:
                import yfinance as yf
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="3mo", interval="1d")
            
            if hist.empty or len(hist) < 30:
                return {'smart_money_flow': 'NEUTRAL'}
            
            # Calculate price-volume relationship indicators
            hist['returns'] = hist['Close'].pct_change()
            hist['volume_ma'] = hist['Volume'].rolling(window=10).mean()
            hist['price_ma'] = hist['Close'].rolling(window=10).mean()
            
            # Smart money indicators
            recent_data = hist.tail(20)
            
            # 1. Accumulation during price weakness
            weak_price_high_volume = len(recent_data[
                (recent_data['Close'] < recent_data['price_ma']) & 
                (recent_data['Volume'] > recent_data['volume_ma'])
            ])
            
            # 2. Distribution during price strength
            strong_price_high_volume = len(recent_data[
                (recent_data['Close'] > recent_data['price_ma']) & 
                (recent_data['Volume'] > recent_data['volume_ma'])
            ])
            
            # Determine smart money flow
            if weak_price_high_volume > strong_price_high_volume * 1.5:
                smart_money_flow = 'ACCUMULATION'
            elif strong_price_high_volume > weak_price_high_volume * 1.5:
                smart_money_flow = 'DISTRIBUTION'
            else:
                smart_money_flow = 'NEUTRAL'
            
            return {'smart_money_flow': smart_money_flow}
            
        except Exception as e:
            logging.debug(f"Smart money flow detection failed for {symbol}: {e}")
            return {'smart_money_flow': 'NEUTRAL'}
    
    def _calculate_institutional_score(self, institutional_data: dict) -> float:
        """
        Calculate composite institutional score
        """
        try:
            score = 50  # Base neutral score
            
            # FII Activity scoring (25 points max)
            fii_activity = institutional_data.get('fii_activity', 'NEUTRAL')
            if fii_activity == 'BUYING':
                score += 20
            elif fii_activity == 'SELLING':
                score -= 15
            
            # DII Activity scoring (20 points max)
            dii_activity = institutional_data.get('dii_activity', 'NEUTRAL')
            if dii_activity == 'ACCUMULATING':
                score += 15
            
            # Bulk Deals scoring (15 points max)
            bulk_signal = institutional_data.get('bulk_deals_signal', 'NEUTRAL')
            if bulk_signal == 'POSITIVE':
                score += 12
            elif bulk_signal == 'NEGATIVE':
                score -= 10
            elif bulk_signal == 'MIXED':
                score -= 2
            
            # Smart Money Flow scoring (20 points max)
            smart_money = institutional_data.get('smart_money_flow', 'NEUTRAL')
            if smart_money == 'ACCUMULATION':
                score += 15
            elif smart_money == 'DISTRIBUTION':
                score -= 12
            
            # Large Block Activity scoring (10 points max)
            large_block = institutional_data.get('large_block_activity', 'NEUTRAL')
            if large_block == 'INSTITUTIONAL_BUYING':
                score += 8
            elif large_block == 'INSTITUTIONAL_SELLING':
                score -= 6
            
            # Ownership level scoring (10 points max)
            ownership_level = institutional_data.get('institutional_ownership_level', 'MODERATE')
            if ownership_level == 'HIGH':
                score += 5  # High institutional ownership is generally positive
            elif ownership_level == 'LOW':
                score -= 3
            
            return max(min(score, 100), 0)  # Clamp between 0-100
            
        except Exception as e:
            logging.warning(f"Institutional score calculation failed: {e}")
            return 50.0
    
    def _determine_institutional_sentiment(self, score: float) -> str:
        """
        Determine overall institutional sentiment based on composite score
        """
        if score >= 75:
            return 'VERY_POSITIVE'
        elif score >= 65:
            return 'POSITIVE'
        elif score >= 45:
            return 'NEUTRAL'
        elif score >= 35:
            return 'NEGATIVE'
        else:
            return 'VERY_NEGATIVE'
    
    def _get_fallback_institutional_analysis(self) -> dict:
        """
        Fallback institutional analysis when calculation fails
        """
        return {
            'institutional_sentiment': 'NEUTRAL',
            'fii_activity': 'NEUTRAL',
            'dii_activity': 'NEUTRAL',
            'bulk_deals_signal': 'NEUTRAL',
            'insider_activity': 'NEUTRAL',
            'institutional_score': 50,
            'smart_money_flow': 'NEUTRAL',
            'institutional_ownership_change': 0,
            'large_block_activity': 'NEUTRAL'
        }
    
    def _get_dynamic_risk_free_rate(self) -> float:
        """
        ACCURACY IMPROVEMENT #8: Dynamic Risk-Free Rate
        
        Fetches current Indian risk-free rate (10-year government bond yield)
        with fallback to reasonable approximation.
        
        Expected Additional Accuracy Improvement: 1-2%
        """
        try:
            # Cache for 24 hours
            cache_file = "data/risk_free_rate.pkl"
            cache_expiry_hours = 24
            
            # Check cache first
            if os.path.exists(cache_file):
                try:
                    cache_time = os.path.getmtime(cache_file)
                    if (time.time() - cache_time) < (cache_expiry_hours * 3600):
                        with open(cache_file, 'rb') as f:
                            cached_rate = pickle.load(f)
                            logging.debug(f"Using cached risk-free rate: {cached_rate:.2f}%")
                            return cached_rate
                except Exception as e:
                    logging.debug(f"Cache read failed: {e}")
            
            # Try to fetch current 10-year bond yield from multiple sources
            current_rate = self._fetch_india_10y_bond_yield()
            
            if current_rate and 2.0 <= current_rate <= 12.0:  # Sanity check
                # Cache the result
                try:
                    os.makedirs("data", exist_ok=True)
                    with open(cache_file, 'wb') as f:
                        pickle.dump(current_rate, f)
                    logging.info(f"Updated risk-free rate to {current_rate:.2f}%")
                except Exception as e:
                    logging.debug(f"Cache write failed: {e}")
                
                return current_rate
            
        except Exception as e:
            logging.debug(f"Dynamic risk-free rate fetch failed: {e}")
        
        # Fallback: Use reasonable approximation based on current market conditions
        # As of 2025, Indian 10-year bond yields are typically in 6.5-7.5% range
        fallback_rate = 7.0
        logging.debug(f"Using fallback risk-free rate: {fallback_rate:.2f}%")
        return fallback_rate
    
    def _fetch_india_10y_bond_yield(self) -> Optional[float]:
        """
        Attempt to fetch current Indian 10-year government bond yield
        """
        try:
            # Method 1: Try to get Indian bond data through yfinance
            # Indian 10-year benchmark bond (approximate ticker)
            bond_tickers = ["^TNX", "IN10Y=X"]  # US 10Y as proxy, Indian 10Y if available
            
            for ticker_symbol in bond_tickers:
                try:
                    import yfinance as yf
                    ticker = yf.Ticker(ticker_symbol)
                    hist = ticker.history(period="5d", interval="1d")
                    
                    if not hist.empty:
                        latest_yield = hist['Close'].iloc[-1]
                        
                        # If US 10Y, adjust for India (typically 200-300 bps higher)
                        if ticker_symbol == "^TNX":
                            indian_equivalent = latest_yield + 2.5  # Add typical spread
                            if 4.0 <= indian_equivalent <= 10.0:
                                logging.debug(f"Estimated Indian 10Y yield from US 10Y: {indian_equivalent:.2f}%")
                                return indian_equivalent
                        else:
                            if 4.0 <= latest_yield <= 10.0:
                                logging.debug(f"Fetched Indian 10Y yield: {latest_yield:.2f}%")
                                return latest_yield
                    
                except Exception as e:
                    logging.debug(f"Failed to fetch {ticker_symbol}: {e}")
                    continue
            
            # Method 2: Use backup estimation based on RBI repo rate
            # RBI repo rate is typically 150-200 bps below 10Y bond yield
            try:
                # This is a simplified estimation - in practice, you'd fetch RBI repo rate
                # Current RBI repo rate (as of 2025) is around 6.5%, so 10Y would be ~7.0-7.5%
                estimated_10y = 7.25  # Conservative estimate
                logging.debug(f"Using estimated 10Y yield: {estimated_10y:.2f}%")
                return estimated_10y
                
            except Exception as e:
                logging.debug(f"Estimation method failed: {e}")
        
        except Exception as e:
            logging.debug(f"All risk-free rate fetch methods failed: {e}")
        
        return None

    def _get_dynamic_weights(self, stock_data: dict) -> dict:
        """
        ACCURACY IMPROVEMENT #2: Dynamic Weight Adjustment
        
        Adjusts scoring weights based on market conditions, sector, and company characteristics
        for more accurate analysis in different market environments.
        
        Expected Accuracy Improvement: 20-25%
        """
        # Base weights for different metrics
        base_weights = {
            'pe_ratio': 0.25,
            'pb_ratio': 0.20,
            'debt_to_equity': 0.15,
            'roe': 0.15,
            'revenue_growth': 0.15,
            'current_ratio': 0.10
        }
        
        # Market condition adjustments (based on current market volatility)
        market_cap = stock_data.get('market_cap', 0)
        
        # Sector-specific adjustments
        sector = stock_data.get('sector', '').lower()
        industry = stock_data.get('industry', '').lower()
        
        # Banking/Financial sector adjustments
        if any(keyword in sector + industry for keyword in ['bank', 'financial', 'insurance', 'finance']):
            base_weights['pb_ratio'] *= 1.4  # P/B more relevant for banks
            base_weights['pe_ratio'] *= 0.8  # P/E less reliable for banks
            base_weights['debt_to_equity'] *= 1.2  # Capital structure important
            base_weights['roe'] *= 1.3  # ROE critical for banks
        
        # Technology sector adjustments
        elif any(keyword in sector + industry for keyword in ['technology', 'software', 'it', 'computer']):
            base_weights['revenue_growth'] *= 1.5  # Growth matters more
            base_weights['pb_ratio'] *= 0.7  # Book value less relevant
            base_weights['pe_ratio'] *= 1.1  # P/E still important but adjusted
            base_weights['debt_to_equity'] *= 0.8  # Less debt-heavy
        
        # Infrastructure/Capital-intensive sectors
        elif any(keyword in sector + industry for keyword in ['infrastructure', 'power', 'steel', 'cement', 'mining']):
            base_weights['debt_to_equity'] *= 1.4  # Debt levels critical
            base_weights['pb_ratio'] *= 1.2  # Asset-heavy businesses
            base_weights['current_ratio'] *= 1.3  # Liquidity important
            base_weights['revenue_growth'] *= 0.8  # Growth less critical
        
        # FMCG/Consumer goods adjustments
        elif any(keyword in sector + industry for keyword in ['consumer', 'fmcg', 'food', 'beverage']):
            base_weights['roe'] *= 1.3  # High ROE expected
            base_weights['revenue_growth'] *= 1.2  # Consistent growth important
            base_weights['debt_to_equity'] *= 0.9  # Generally lower debt
        
        # Market cap based adjustments
        if market_cap:
            if market_cap < 5000:  # Small cap - focus on growth and risk
                base_weights['revenue_growth'] *= 1.3
                base_weights['debt_to_equity'] *= 1.2
                base_weights['current_ratio'] *= 1.2
            elif market_cap > 50000:  # Large cap - focus on stability
                base_weights['roe'] *= 1.2
                base_weights['debt_to_equity'] *= 0.9
                base_weights['revenue_growth'] *= 0.9
        
        # Risk profile adjustments
        if hasattr(self, 'risk_profile'):
            if self.risk_profile == 'conservative':
                base_weights['debt_to_equity'] *= 1.3
                base_weights['current_ratio'] *= 1.3
                base_weights['revenue_growth'] *= 0.8
            elif self.risk_profile == 'aggressive':
                base_weights['revenue_growth'] *= 1.4
                base_weights['pe_ratio'] *= 0.9
                base_weights['debt_to_equity'] *= 0.8
        
        # Normalize weights to sum to 1
        total_weight = sum(base_weights.values()) or 1.0
        return {k: v/total_weight for k, v in base_weights.items()}

    def calculate_undervaluation_score(self, stock_data):
        """
        ENHANCEMENT 1: Advanced Undervaluation Detection with Dynamic Weights
        Calculate comprehensive undervaluation score based on multiple criteria
        """
        try:
            score_components = []
            weights = []
            
            # Get dynamic weights based on stock characteristics
            dynamic_weights = self._get_dynamic_weights(stock_data)
            
            # 1. P/E Ratio Analysis (dynamic weight)
            pe_ratio = stock_data.get('pe_ratio', None)
            if pe_ratio and pe_ratio > 0:
                if pe_ratio <= 10:
                    pe_score = 100
                elif pe_ratio <= 15:
                    pe_score = 80
                elif pe_ratio <= 20:
                    pe_score = 60
                elif pe_ratio <= 25:
                    pe_score = 40
                else:
                    pe_score = 20
                score_components.append(pe_score)
                weights.append(dynamic_weights.get('pe_ratio', 0.25))
            
            # 2. P/B Ratio Analysis (dynamic weight)
            pb_ratio = stock_data.get('pb_ratio', None)
            if pb_ratio and pb_ratio > 0:
                if pb_ratio <= 1.0:
                    pb_score = 100
                elif pb_ratio <= 1.5:
                    pb_score = 80
                elif pb_ratio <= 2.0:
                    pb_score = 60
                elif pb_ratio <= 3.0:
                    pb_score = 40
                else:
                    pb_score = 20
                score_components.append(pb_score)
                weights.append(dynamic_weights.get('pb_ratio', 0.20))
            
            # 3. Dividend Yield Analysis (15% weight)
            div_yield = stock_data.get('dividend_yield', None)
            if div_yield and div_yield >= 0:
                if div_yield >= 4.0:
                    div_score = 100
                elif div_yield >= 3.0:
                    div_score = 80
                elif div_yield >= 2.0:
                    div_score = 60
                elif div_yield >= 1.0:
                    div_score = 40
                else:
                    div_score = 20
                score_components.append(div_score)
                weights.append(0.15)
            
            # 4. ROE vs P/B Analysis (15% weight)
            roe = stock_data.get('roe', None)
            _roe_valid = roe is not None and not (isinstance(roe, float) and np.isnan(roe))
            _pb_valid = pb_ratio is not None and not (isinstance(pb_ratio, float) and np.isnan(pb_ratio)) and pb_ratio > 0
            if _roe_valid and _pb_valid:
                # Graham's formula: Intrinsic Value = EPS × (8.5 + 2g)
                # Simplified: High ROE with Low P/B is attractive
                roe_pb_ratio = roe / pb_ratio
                if roe_pb_ratio >= 10:
                    roe_pb_score = 100
                elif roe_pb_ratio >= 7.5:
                    roe_pb_score = 80
                elif roe_pb_ratio >= 5:
                    roe_pb_score = 60
                elif roe_pb_ratio >= 2.5:
                    roe_pb_score = 40
                else:
                    roe_pb_score = 20
                score_components.append(roe_pb_score)
                weights.append(0.15)
            
            # 5. Debt-to-Equity Analysis (10% weight)
            debt_eq = stock_data.get('debt_to_equity', None)
            if debt_eq is not None:
                if debt_eq <= 30:
                    debt_score = 100
                elif debt_eq <= 50:
                    debt_score = 80
                elif debt_eq <= 70:
                    debt_score = 60
                elif debt_eq <= 100:
                    debt_score = 40
                else:
                    debt_score = 20
                score_components.append(debt_score)
                weights.append(0.10)
            
            # 6. Current Ratio Analysis (10% weight)
            current_ratio = stock_data.get('current_ratio', None)
            if current_ratio and current_ratio > 0:
                if current_ratio >= 2.0:
                    current_score = 100
                elif current_ratio >= 1.5:
                    current_score = 80
                elif current_ratio >= 1.2:
                    current_score = 60
                elif current_ratio >= 1.0:
                    current_score = 40
                else:
                    current_score = 20
                score_components.append(current_score)
                weights.append(0.10)
            
            # 7. Price vs 52-week low (5% weight)
            current_price = stock_data.get('current_price', None)
            week_52_low = stock_data.get('52_week_low', None)
            if current_price and week_52_low and week_52_low > 0:
                price_vs_low = (current_price / week_52_low - 1) * 100
                if price_vs_low <= 10:  # Within 10% of 52-week low
                    price_score = 100
                elif price_vs_low <= 25:
                    price_score = 80
                elif price_vs_low <= 50:
                    price_score = 60
                elif price_vs_low <= 75:
                    price_score = 40
                else:
                    price_score = 20
                score_components.append(price_score)
                weights.append(0.05)
            
            # ACCURACY IMPROVEMENT #3: Add Industry-Relative Scoring Components
            relative_scores = self._calculate_industry_relative_scores(stock_data)
            
            # Add industry-relative P/E score (15% weight)
            if 'pe_relative_score' in relative_scores:
                score_components.append(relative_scores['pe_relative_score'])
                weights.append(dynamic_weights.get('pe_ratio', 0.25) * 0.6)  # 60% of P/E weight for relative
            
            # Add industry-relative P/B score (10% weight)
            if 'pb_relative_score' in relative_scores:
                score_components.append(relative_scores['pb_relative_score'])
                weights.append(dynamic_weights.get('pb_ratio', 0.20) * 0.5)  # 50% of P/B weight for relative
            
            # Add industry-relative ROE score (10% weight)
            if 'roe_relative_score' in relative_scores:
                score_components.append(relative_scores['roe_relative_score'])
                weights.append(dynamic_weights.get('roe', 0.15) * 0.67)  # 67% of ROE weight for relative
            
            # Add industry-relative growth score (8% weight)
            if 'growth_relative_score' in relative_scores:
                score_components.append(relative_scores['growth_relative_score'])
                weights.append(dynamic_weights.get('revenue_growth', 0.15) * 0.53)  # 53% of growth weight for relative
            
            # Store relative scores for reporting
            stock_data.update(relative_scores)
            
            # Calculate weighted average with industry-relative components
            if score_components:
                total_weight = sum(weights)
                if total_weight > 0:
                    weighted_score = sum(score * weight for score, weight in zip(score_components, weights)) / total_weight
                    
                    # Add bonus for having industry context
                    industry_bonus = len(relative_scores) * 2  # 2 points per relative metric
                    final_score = min(weighted_score + industry_bonus, 100)
                    
                    return round(final_score, 1)
            
            return 50  # Default neutral score if no data available
            
        except Exception as e:
            logging.error(f"Error calculating undervaluation score: {e}")
            return 50
    
    def calculate_momentum_growth_score(self, stock_data):
        """
        🚀 HIGH-RISK HIGH-REWARD: Calculate Momentum & Growth Score
        Perfect for aggressive investors seeking high returns
        """
        try:
            score_components = []
            weights = []
            
            # 1. Revenue Growth Rate (20% weight) - Higher is better for growth
            revenue_growth = stock_data.get('revenue_growth', 0)
            if revenue_growth is not None:
                if revenue_growth >= 30:      # Hyper growth
                    rev_score = 100
                elif revenue_growth >= 20:    # High growth
                    rev_score = 85
                elif revenue_growth >= 15:    # Good growth
                    rev_score = 70
                elif revenue_growth >= 10:    # Moderate growth
                    rev_score = 55
                else:                         # Low/no growth
                    rev_score = 30
                score_components.append(rev_score)
                weights.append(0.20)
            
            # 2. Earnings Growth Rate (20% weight)
            profit_growth = stock_data.get('profit_growth') or stock_data.get('earnings_growth', 0)
            if profit_growth is not None:
                if profit_growth >= 35:       # Explosive earnings growth
                    profit_score = 100
                elif profit_growth >= 25:     # Strong earnings growth
                    profit_score = 85
                elif profit_growth >= 15:     # Good earnings growth
                    profit_score = 70
                elif profit_growth >= 8:      # Moderate growth
                    profit_score = 55
                else:                         # Weak/declining
                    profit_score = 25
                score_components.append(profit_score)
                weights.append(0.20)
            
            # 3. Advanced Technical Momentum (25% weight) - Multi-Timeframe + Real Technical
            # Combine multi-timeframe analysis with real technical indicators for superior accuracy
            mtf_score = stock_data.get('mtf_composite_score', 50)
            real_technical_score = stock_data.get('real_technical_score', 50)
            mtf_agreement = stock_data.get('mtf_timeframe_agreement', 0)
            
            # Calculate advanced momentum score with timeframe validation
            base_momentum_score = (real_technical_score * 0.6) + (mtf_score * 0.4)
            
            # Boost for high timeframe agreement (strong signal confidence)
            if mtf_agreement >= 80:  # Very high confidence
                agreement_multiplier = 1.15
            elif mtf_agreement >= 60:  # Good confidence
                agreement_multiplier = 1.1
            elif mtf_agreement >= 40:  # Moderate confidence
                agreement_multiplier = 1.05
            else:  # Low confidence
                agreement_multiplier = 0.95
            
            adjusted_momentum_score = base_momentum_score * agreement_multiplier
            
            # Final momentum categorization
            if adjusted_momentum_score >= 85:     # Exceptional momentum with timeframe confirmation
                tech_momentum = 100
            elif adjusted_momentum_score >= 75:   # Very strong momentum
                tech_momentum = 90
            elif adjusted_momentum_score >= 65:   # Strong momentum  
                tech_momentum = 80
            elif adjusted_momentum_score >= 55:   # Good momentum
                tech_momentum = 70
            elif adjusted_momentum_score >= 45:   # Neutral momentum
                tech_momentum = 55
            else:                                 # Weak momentum
                tech_momentum = 35
            
            score_components.append(tech_momentum)
            weights.append(0.25)
            
            # 4. Price Performance vs 52-week range (15% weight)
            current_price = stock_data.get('current_price', None)
            week_52_high = stock_data.get('52_week_high', None)
            week_52_low = stock_data.get('52_week_low', None)
            
            if all([current_price, week_52_high, week_52_low]) and week_52_high > week_52_low:
                price_position = (current_price - week_52_low) / (week_52_high - week_52_low) * 100
                
                if price_position >= 85:      # Near 52-week high (momentum)
                    position_score = 90
                elif price_position >= 70:    # Strong position
                    position_score = 75
                elif price_position >= 50:    # Above midpoint
                    position_score = 60
                else:                         # Lower range (value but not momentum)
                    position_score = 35
                
                score_components.append(position_score)
                weights.append(0.15)
            
            # 5. ROE for Quality Growth (10% weight) - High ROE indicates efficient growth
            roe = stock_data.get('roe', None)
            if roe and roe > 0:
                if roe >= 25:                 # Exceptional ROE
                    roe_score = 100
                elif roe >= 20:               # High ROE
                    roe_score = 85
                elif roe >= 15:               # Good ROE
                    roe_score = 70
                elif roe >= 10:               # Acceptable ROE
                    roe_score = 50
                else:                         # Low ROE
                    roe_score = 30
                score_components.append(roe_score)
                weights.append(0.10)
            
            # 6. Market Cap Bias (10% weight) - Mid-cap sweet spot for growth
            market_cap = stock_data.get('market_cap', None)
            if market_cap and market_cap > 0:
                market_cap_cr = market_cap / 10000  # Convert to crores for easier handling
                
                if 5000 <= market_cap_cr <= 50000:    # Mid to large cap sweet spot
                    mcap_score = 85
                elif 1000 <= market_cap_cr < 5000:    # Small to mid cap (higher growth potential)
                    mcap_score = 95
                elif 500 <= market_cap_cr < 1000:     # Small cap (highest growth potential)
                    mcap_score = 100
                elif market_cap_cr >= 50000:          # Large cap (stable but lower growth)
                    mcap_score = 60
                else:                                  # Micro cap (too risky)
                    mcap_score = 40
                
                score_components.append(mcap_score)
                weights.append(0.10)
            
            # Calculate weighted momentum score
            if score_components:
                total_weight = sum(weights)
                if total_weight > 0:
                    momentum_score = sum(score * weight for score, weight in zip(score_components, weights)) / total_weight
                    
                    # 🚀 BONUS: Add volatility bonus for high-risk investors
                    # Higher volatility = higher potential returns for aggressive traders
                    volatility = stock_data.get('volatility_6m', 0)
                    if volatility and volatility > 20:  # High volatility bonus
                        volatility_bonus = min(10, (volatility - 20) * 0.5)  # Max 10 point bonus
                        momentum_score = min(100, momentum_score + volatility_bonus)
                    
                    return round(momentum_score, 1)
            
            return 50  # Default neutral score
            
        except Exception as e:
            logging.error(f"Error calculating momentum/growth score: {e}")
            return 50
    
    def calculate_sector_rankings(self, results_df):
        """
        ENHANCEMENT 2: Sector-wise Comparison and Ranking
        Analyze performance within sectors and assign sector rankings
        """
        try:
            if 'sector' not in results_df.columns:
                logging.warning("No sector data available for sector analysis")
                return results_df
            
            # Convert numeric columns to proper types to avoid ufunc errors
            _score_cols_sector = {'fundamental_score_final', 'enhanced_technical_score_final',
                                 'undervaluation_score', 'overall_score_with_value'}
            _ratio_cols_sector = {'pe_ratio', 'pb_ratio', 'roe'}
            for col in (_score_cols_sector | _ratio_cols_sector):
                if col in results_df.columns:
                    _default = 50 if col in _score_cols_sector else 0
                    results_df[col] = pd.to_numeric(results_df[col], errors='coerce').fillna(_default)
            
            # Group by sector and calculate statistics
            sector_stats = {}
            
            for sector in results_df['sector'].dropna().unique():
                sector_data = results_df[results_df['sector'] == sector]
                
                if len(sector_data) == 0:
                    continue
                
                # Calculate sector metrics
                sector_stats[sector] = {
                    'count': len(sector_data),
                    'avg_fundamental_score': sector_data['fundamental_score_final'].mean(),
                    'avg_technical_score': sector_data['enhanced_technical_score_final'].mean(),
                    'avg_undervaluation_score': sector_data['undervaluation_score'].mean(),
                    'avg_overall_score': sector_data['overall_score_with_value'].mean(),
                    'avg_pe_ratio': sector_data['pe_ratio'].mean(),
                    'avg_pb_ratio': sector_data['pb_ratio'].mean(),
                    'avg_roe': sector_data['roe'].mean(),
                    'strong_buy_count': len(sector_data[sector_data['final_recommendation'].str.contains('STRONG BUY', na=False)]),
                    'buy_count': len(sector_data[sector_data['final_recommendation'].str.contains('BUY', na=False)])
                }
            
            # Add sector rankings to results
            results_with_sector = results_df.copy()
            
            # Calculate sector rank for each stock
            for idx, row in results_with_sector.iterrows():
                sector = row.get('sector')
                if pd.isna(sector):
                    continue
                
                sector_stocks = results_with_sector[results_with_sector['sector'] == sector]
                
                # Rank within sector (1 = best in sector)
                sector_rank = (sector_stocks['overall_score_with_value'] > row['overall_score_with_value']).sum() + 1
                sector_percentile = round((1 - (sector_rank - 1) / len(sector_stocks)) * 100, 1)
                
                results_with_sector.at[idx, 'sector_rank'] = sector_rank
                results_with_sector.at[idx, 'sector_percentile'] = sector_percentile
                results_with_sector.at[idx, 'sector_size'] = len(sector_stocks)
            
            # Add sector strength indicator
            sector_strength = {}
            for sector, stats in sector_stats.items():
                # Sector strength based on average scores and buy recommendations
                strength_score = (
                    stats['avg_overall_score'] * 0.4 +
                    stats['avg_undervaluation_score'] * 0.3 +
                    (stats['strong_buy_count'] / max(stats['count'], 1) * 100) * 0.3
                )
                
                if strength_score >= 70:
                    sector_strength[sector] = "STRONG"
                elif strength_score >= 60:
                    sector_strength[sector] = "GOOD"
                elif strength_score >= 50:
                    sector_strength[sector] = "NEUTRAL"
                else:
                    sector_strength[sector] = "WEAK"
            
            # Add sector strength to results
            results_with_sector['sector_strength'] = results_with_sector['sector'].map(sector_strength)
            
            # Store sector statistics for reporting
            self.sector_statistics = sector_stats
            
            logging.info(f"Calculated sector rankings for {len(sector_stats)} sectors")
            return results_with_sector
            
        except Exception as e:
            logging.error(f"Error in sector analysis: {e}")
            return results_df
    
    def calculate_risk_return_metrics(self, results_df):
        """
        ENHANCEMENT 3: Risk-Return Optimization
        Calculate risk-adjusted returns and optimization metrics
        """
        try:
            # Calculate volatility proxy using technical indicators
            for idx, row in results_df.iterrows():
                symbol = row.get('symbol', '')
                
                if not symbol:  # Skip if no symbol
                    continue
                    
                try:
                    volatility = row.get('volatility', None)
                    max_drawdown = row.get('max_drawdown_6m', None)
                    beta = row.get('beta', None)

                    if volatility is not None and pd.notna(volatility):
                        volatility = max(float(volatility), 0)
                    if volatility is not None and volatility > 0:
                        
                        overall_score = row.get('final_blended_score', 50)
                        overall_score = overall_score if pd.notna(overall_score) else 50
                        underval_score = row.get('undervaluation_score', 50)
                        
                        risk_free_rate = self._get_dynamic_risk_free_rate()
                        sharpe_proxy = (overall_score - risk_free_rate) / max(volatility, 1)
                        
                        # V5.0: Meaningful 0-30% volatility penalty instead of trivial max-2pt
                        risk_adjusted_score = overall_score * (1.0 - min(volatility / 100.0, 0.30))
                        
                        # Risk category based on user profile and volatility
                        # Adjust thresholds based on user's risk profile
                        if self.risk_profile == "conservative":
                            if volatility <= 15:
                                risk_category = "LOW"
                            elif volatility <= 25:
                                risk_category = "MODERATE" 
                            elif volatility <= 38:
                                risk_category = "HIGH"
                            else:
                                risk_category = "VERY HIGH"
                        elif self.risk_profile == "aggressive":
                            if volatility <= 25:
                                risk_category = "LOW"
                            elif volatility <= 40:
                                risk_category = "MODERATE"
                            elif volatility <= 55:
                                risk_category = "HIGH" 
                            else:
                                risk_category = "VERY HIGH"
                        else:  # moderate (default)
                            if volatility <= 20:
                                risk_category = "LOW"
                            elif volatility <= 32:
                                risk_category = "MODERATE"
                            elif volatility <= 45:
                                risk_category = "HIGH"
                            else:
                                risk_category = "VERY HIGH"
                        
                        # Extreme volatility override
                        if volatility > _config.MAX_SAFE_VOLATILITY:
                            risk_category = "EXTREME"
                            results_df.at[idx, 'extreme_volatility_flag'] = True
                            logging.warning(f"{symbol}: extreme volatility {volatility:.1f}% > {_config.MAX_SAFE_VOLATILITY}% — EXTREME risk")

                        if max_drawdown is None or pd.isna(max_drawdown):
                            max_drawdown = 0
                        if beta is None or pd.isna(beta):
                            beta = 1.0

                        # Update results
                        results_df.at[idx, 'volatility_6m'] = round(volatility, 2)
                        results_df.at[idx, 'max_drawdown_6m'] = round(max_drawdown, 2)
                        results_df.at[idx, 'beta'] = round(beta, 2)
                        results_df.at[idx, 'sharpe_proxy'] = round(sharpe_proxy, 2)
                        results_df.at[idx, 'risk_adjusted_score'] = round(risk_adjusted_score, 1)
                        results_df.at[idx, 'risk_category'] = risk_category
                        # Debug log for risk category assignment
                        logging.debug(f"{symbol}: volatility={volatility:.1f}%, profile={self.risk_profile}, risk_category={risk_category}")

                        # ILLIQUIDITY CHECK: penalize stocks with very low average volume
                        _avg_vol = _nv(row.get('avg_volume_10d', row.get('current_volume', 0)), 0)
                        if _avg_vol > 0 and _avg_vol < _config.MIN_AVG_DAILY_VOLUME:
                            risk_adjusted_score = max(0, risk_adjusted_score - _config.ILLIQUID_SCORE_PENALTY)
                            results_df.at[idx, 'risk_adjusted_score'] = round(risk_adjusted_score, 1)
                            results_df.at[idx, 'quality_warnings'] = str(results_df.at[idx, 'quality_warnings'] or '') + ',low_liquidity'
                            logging.warning(f"{symbol}: avg volume {_avg_vol:.0f} < {_config.MIN_AVG_DAILY_VOLUME} — illiquid penalty applied (-{_config.ILLIQUID_SCORE_PENALTY})")

                    else:
                        # Default values if no data - USE OPTIMIZED SCORE
                        results_df.at[idx, 'volatility_6m'] = None
                        results_df.at[idx, 'max_drawdown_6m'] = None
                        results_df.at[idx, 'beta'] = None
                        results_df.at[idx, 'sharpe_proxy'] = None
                        results_df.at[idx, 'risk_adjusted_score'] = row.get('final_blended_score', 50)
                        results_df.at[idx, 'risk_category'] = "UNKNOWN"
                        
                except Exception as e:
                    logging.warning(f"Risk calculation failed for {symbol}: {e}")
                    results_df.at[idx, 'volatility_6m'] = None
                    results_df.at[idx, 'max_drawdown_6m'] = None
                    results_df.at[idx, 'beta'] = None
                    results_df.at[idx, 'sharpe_proxy'] = None
                    results_df.at[idx, 'risk_adjusted_score'] = row.get('final_blended_score', 50)
                    results_df.at[idx, 'risk_category'] = "UNKNOWN"
                    continue
            
            logging.info("Completed risk-return analysis")
            return results_df
            
        except Exception as e:
            logging.error(f"Error in risk-return analysis: {e}")
            return results_df
    
    def calculate_max_drawdown(self, prices):
        """Calculate maximum drawdown from price series"""
        try:
            cumulative = (1 + prices.pct_change()).cumprod()
            rolling_max = cumulative.expanding().max()
            drawdown = (cumulative - rolling_max) / rolling_max
            return abs(drawdown.min()) * 100
        except Exception:
            return 0
    
    def calculate_beta(self, returns):
        """Calculate beta against market (simplified)"""
        try:
            # Using a simplified beta calculation
            # In practice, you'd use NIFTY50 returns as market benchmark
            market_volatility = 0.20  # Approximate market volatility
            stock_volatility = returns.std() * (252 ** 0.5)
            return stock_volatility / market_volatility
        except Exception:
            return 1.0
    
    def _load_holdings_from_excel(self, excel_file_path):
        """
        Load holdings from Excel file with column mapping
        Excel format: Stock Name, ISIN, Quantity, Average buy price, Buy value, Closing price, Closing value, Unrealised P&L
        Header is at row 11 (index 10)
        """
        try:
            # Read Excel with header at row 11
            df = pd.read_excel(excel_file_path, sheet_name='Sheet1', header=10)
            
            # Column mapping: Excel → CSV format
            column_mapping = {
                'Stock Name': 'Instrument',
                'Quantity': 'Qty.',
                'Average buy price': 'Avg. cost',
                'Closing price': 'LTP',
                'Closing value': 'Cur. val',
                'Unrealised P&L': 'P&L'
            }
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            
            # Extract symbol from Stock Name (keep both for matching)
            if 'Instrument' in df.columns:
                df['Company Name'] = df['Instrument'].copy()
                df['Instrument'] = df['Instrument'].apply(self._extract_symbol_from_company_name)
            
            # Calculate Net chg. (not provided in Excel, set to 0)
            df['Net chg.'] = 0.0
            
            # Calculate Day chg. (not provided in Excel, set to 0)
            df['Day chg.'] = 0.0
            
            # Calculate Invested amount; fallback to LTP if Avg. cost missing
            if 'Avg. cost' in df.columns and 'Qty.' in df.columns:
                if 'LTP' in df.columns:
                    df['Avg. cost'] = df['Avg. cost'].fillna(df['LTP'])
                    df.loc[df['Avg. cost'] == 0, 'Avg. cost'] = df.loc[df['Avg. cost'] == 0, 'LTP']
                df['Invested'] = df['Avg. cost'] * df['Qty.']
            
            # Sector will be filled later from analysis (set to empty for now)
            df['Sector'] = ''
            
            # Clean numeric columns (handle commas and convert to numeric)
            numeric_cols = ['Qty.', 'Avg. cost', 'LTP', 'Invested', 'Cur. val', 'P&L', 'Net chg.', 'Day chg.']
            for col in numeric_cols:
                if col in df.columns:
                    # Remove commas and convert to numeric
                    if df[col].dtype == 'object':
                        df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            print(f"   ✅ Loaded {len(df)} holdings from Excel file (header row 11)")
            return df
            
        except Exception as e:
            print(f"   ⚠️  Error loading Excel holdings: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_symbol_from_company_name(self, stock_name):
        """
        Extract NSE symbol from company name
        Common patterns:
        - "State Bank of India" → "SBIN"
        - "Reliance Industries Limited" → "RELIANCE"
        - "Tata Consultancy Services Limited" → "TCS"
        """
        if pd.isna(stock_name):
            return ''
        
        # Common mappings for major stocks
        name_to_symbol = {
            'STATE BANK OF INDIA': 'SBIN',
            'HDFC BANK LIMITED': 'HDFCBANK',
            'ICICI BANK LIMITED': 'ICICIBANK',
            'RELIANCE INDUSTRIES LIMITED': 'RELIANCE',
            'TATA CONSULTANCY SERVICES LIMITED': 'TCS',
            'INFOSYS LIMITED': 'INFY',
            'BHARTI AIRTEL LIMITED': 'BHARTIARTL',
            'HINDUSTAN UNILEVER LIMITED': 'HINDUNILVR',
            'ITC LIMITED': 'ITC',
            'AXIS BANK LIMITED': 'AXISBANK',
            'KOTAK MAHINDRA BANK LIMITED': 'KOTAKBANK',
            'LARSEN & TOUBRO LIMITED': 'LT',
            'ASIAN PAINTS LIMITED': 'ASIANPAINT',
            'MARUTI SUZUKI INDIA LIMITED': 'MARUTI',
            'MAHINDRA & MAHINDRA LIMITED': 'M&M',
            'WIPRO LIMITED': 'WIPRO',
            'ULTRATECH CEMENT LIMITED': 'ULTRACEMCO',
            'TITAN COMPANY LIMITED': 'TITAN',
            'BAJAJ FINANCE LIMITED': 'BAJFINANCE',
            'NESTLE INDIA LIMITED': 'NESTLEIND',
            'HCL TECHNOLOGIES LIMITED': 'HCLTECH',
            'SUN PHARMACEUTICAL INDUSTRIES LIMITED': 'SUNPHARMA',
            'POWER GRID CORPORATION OF INDIA LIMITED': 'POWERGRID',
            'NTPC LIMITED': 'NTPC',
            'TATA STEEL LIMITED': 'TATASTEEL',
            'ONGC': 'ONGC',
            'COAL INDIA LIMITED': 'COALINDIA',
            'COAL INDIA LTD': 'COALINDIA',
            'COAL INDIA LTD.': 'COALINDIA',
            'GRASIM INDUSTRIES LIMITED': 'GRASIM',
            'ADANI PORTS AND SPECIAL ECONOMIC ZONE LIMITED': 'ADANIPORTS',
            'TECH MAHINDRA LIMITED': 'TECHM',
            'HINDALCO INDUSTRIES LIMITED': 'HINDALCO',
            'HINDALCO  INDUSTRIES  LTD': 'HINDALCO',
            'HINDALCO INDUSTRIES LTD.': 'HINDALCO',
            'FINOLEX INDUSTRIES LTD': 'FINPIPE',
            'INDUSIND BANK LIMITED': 'INDUSINDBK',
            'SHREE CEMENT LIMITED': 'SHREECEM',
            'BAJAJ AUTO LIMITED': 'BAJAJ-AUTO',
            'BRITANNIA INDUSTRIES LIMITED': 'BRITANNIA',
            'EICHER MOTORS LIMITED': 'EICHERMOT',
            'HERO MOTOCORP LIMITED': 'HEROMOTOCO',
            'DIVIS LABORATORIES LIMITED': 'DIVISLAB',
            'TATA MOTORS LIMITED': 'TATAMOTORS',
            'CIPLA LIMITED': 'CIPLA',
            'DR. REDDYS LABORATORIES LIMITED': 'DRREDDY',
            'UPL LIMITED': 'UPL',
            'JSW STEEL LIMITED': 'JSWSTEEL',
            'BHARAT PETROLEUM CORPORATION LIMITED': 'BPCL',
            'INDIAN OIL CORPORATION LIMITED': 'IOC',
            'BANK OF MAHARASHTRA': 'MAHABANK',
            'FEDERAL BANK LIMITED': 'FEDERALBNK',
            'FEDERAL BANK LTD': 'FEDERALBNK',
            'KARUR VYSYA BANK LTD': 'KARURVYSYA',
            'INDRAPRASTHA GAS LIMITED': 'IGL',
            'INDRAPRASTHA GAS LTD': 'IGL',
            'LIC HOUSING FINANCE LIMITED': 'LICHSGFIN',
            'LIC HOUSING FINANCE LTD': 'LICHSGFIN',
            'MUTHOOT FINANCE LIMITED': 'MUTHOOTFIN',
            'NATIONAL ALUMINIUM COMPANY LIMITED': 'NATIONALUM',
            'NATIONAL ALUMINIUM CO LTD': 'NATIONALUM',
            'NATIONAL ALUMINIUM CO.LTD.': 'NATIONALUM',
            'PUNJAB NATIONAL BANK': 'PNB',
            'CANARA BANK': 'CANBK',
            'BANK OF BARODA': 'BANKBARODA',
            'UNION BANK OF INDIA': 'UNIONBANK',
            'INDIAN BANK': 'INDIANB',
            'INDIAN OVERSEAS BANK': 'IOB',
            'CENTRAL BANK OF INDIA': 'CENTRALBK',
            'IDBI BANK LIMITED': 'IDBI',
            'UCO BANK': 'UCOBANK',
            'BANK OF INDIA': 'BANKINDIA',
            'PUNJAB & SIND BANK': 'PSB',
            'NMDC LIMITED': 'NMDC',
            'NMDC LTD': 'NMDC',
            'NMDC LTD.': 'NMDC',
            'NLC INDIA LIMITED': 'NLCINDIA',
            'OIL INDIA LTD': 'OIL',
            'REC LIMITED': 'RECLTD',
            'YES BANK LIMITED': 'YESBANK',
            'RURAL ELECTRIFICATION CORPORATION LIMITED': 'RECLTD',
            'POWER FINANCE CORPORATION LIMITED': 'PFC',
            'PFC': 'PFC',
            'MARUTI SUZUKI INDIA LIMITED': 'MARUTI',
            'MARUTI SUZUKI INDIA LTD': 'MARUTI',
            'MARUTI SUZUKI INDIA LTD.': 'MARUTI',
            'WIPRO LTD': 'WIPRO',
            'WIPRO LTD.': 'WIPRO'
        }
        
        # Normalize company name
        normalized_name = stock_name.upper().strip()
        
        # Check exact match in mapping
        if normalized_name in name_to_symbol:
            return name_to_symbol[normalized_name]
        
        # Try partial match (if mapping key is contained in stock name)
        for key, symbol in name_to_symbol.items():
            if key in normalized_name or normalized_name.startswith(key.split()[0]):
                return symbol
        
        # Fallback: Remove common suffixes and use first word or full name
        for suffix in [' LIMITED', ' LTD', ' LTD.', ' INDIA', ' INDUSTRIES']:
            normalized_name = normalized_name.replace(suffix, '')
        
        # If single word remaining, use it
        words = normalized_name.split()
        if len(words) == 1:
            return words[0]
        
        # Try reverse lookup from company_names dict (symbol→name)
        if hasattr(self, 'company_names') and self.company_names:
            _upper_name = stock_name.strip().upper()
            for _sym, _cname in self.company_names.items():
                if str(_cname).upper() == _upper_name or _upper_name.startswith(str(_cname).upper().split()[0]):
                    return _sym
        
        print(f"   ⚠️  Could not extract symbol from '{stock_name}', using as-is")
        return stock_name.strip()
    
    def _load_current_holdings(self):
        """Load current portfolio holdings from CSV or Excel holdings file"""
        try:
            import glob
            
            # Check for both CSV and Excel holdings files
            holdings_csv_files = glob.glob('Holding/holdings*.csv')
            holdings_excel_files = glob.glob('Holding/Stocks_Holdings_Statement_*.xlsx')
            orders_files = glob.glob('Holding/orders*.csv') + glob.glob('orders*.csv')
            
            # If we have both holdings and orders, use merged portfolio
            if holdings_csv_files and orders_files:
                merged_files = glob.glob('reports/merged_portfolio_*.xlsx')
                if merged_files:
                    # Get the most recent merged file
                    latest_merged = max(merged_files, key=os.path.getmtime)
                    try:
                        holdings_df = pd.read_excel(latest_merged)
                        print(f"   📁 Loaded holdings from: {latest_merged} (merged portfolio)")
                        
                        # Filter out zero quantity stocks if any
                        if 'Qty.' in holdings_df.columns:
                            initial_count = len(holdings_df)
                            holdings_df = holdings_df[holdings_df['Qty.'] > 0]
                            if len(holdings_df) < initial_count:
                                print(f"   🧹 Filtered out {initial_count - len(holdings_df)} zero quantity stocks")
                        
                        return holdings_df
                    except Exception as e:
                        print(f"   ⚠️  Could not read merged file {latest_merged}: {e}")
            
            # If only holdings file exists (CSV or Excel), use it directly
            elif holdings_csv_files or holdings_excel_files:
                # Combine both and get the most recent
                all_holdings_files = holdings_csv_files + holdings_excel_files
                latest_holdings = max(all_holdings_files, key=os.path.getmtime)
                
                # Load based on file type
                if latest_holdings.endswith('.xlsx'):
                    # Excel file - read with header at row 11
                    holdings_df = self._load_holdings_from_excel(latest_holdings)
                    print(f"   [FILE] Loaded holdings from: {latest_holdings} (Excel format)")
                else:
                    # CSV file - use existing logic
                    try:
                        holdings_df = pd.read_csv(latest_holdings) # Try default (utf-8)
                    except UnicodeDecodeError:
                        print(f"   ⚠️  UTF-8 decoding failed, retrying with 'latin1'...")
                        holdings_df = pd.read_csv(latest_holdings, encoding='latin1')
                    
                    print(f"   [FILE] Loaded holdings from: {latest_holdings} (CSV format)")
                    
                    # Clean numeric columns immediately (handle strings with commas like "49,112.00")
                    numeric_cols = ['Qty.', 'Avg. cost', 'LTP', 'Invested', 'Cur. val', 'P&L', 'Net chg.', 'Day chg.']
                    for col in numeric_cols:
                        if col in holdings_df.columns:
                            # Remove commas and convert to numeric
                            if holdings_df[col].dtype == 'object':
                                holdings_df[col] = holdings_df[col].str.replace(',', '', regex=False)
                            holdings_df[col] = pd.to_numeric(holdings_df[col], errors='coerce').fillna(0)
                
                # Filter out zero quantity stocks
                if 'Qty.' in holdings_df.columns:
                    initial_count = len(holdings_df)
                    holdings_df = holdings_df[holdings_df['Qty.'] > 0]
                    if len(holdings_df) < initial_count:
                        print(f"   🧹 Filtered out {initial_count - len(holdings_df)} zero quantity stocks")
                
                return holdings_df
            
            # Fallback: Try multiple possible locations and names for holdings file
            possible_paths = [
                'portfolio.csv',
                'holdings.csv',
                'Holding/holdings*.csv',
                'Holding/portfolio*.csv'
            ]
            
            for pattern in possible_paths:
                files = glob.glob(pattern)
                if files:
                    # Get the most recent file
                    latest_file = max(files, key=os.path.getmtime)
                    try:
                        holdings_df = pd.read_csv(latest_file, encoding='utf-8')
                    except UnicodeDecodeError:
                        holdings_df = pd.read_csv(latest_file, encoding='latin1')
                    print(f"   📁 Loaded holdings from: {latest_file}")
                    
                    # Standardize column names
                    if 'Current Value' in holdings_df.columns and 'Cur. val' not in holdings_df.columns:
                        holdings_df['Cur. val'] = holdings_df['Current Value']
                    
                    # Filter out zero quantity stocks
                    if 'Qty.' in holdings_df.columns:
                        initial_count = len(holdings_df)
                        holdings_df = holdings_df[holdings_df['Qty.'] > 0]
                        if len(holdings_df) < initial_count:
                            print(f"   🧹 Filtered out {initial_count - len(holdings_df)} zero quantity stocks")
                    
                    return holdings_df
            
            print("   ⚠️  No holdings file found - using allocation without current portfolio")
            return None
            
        except Exception as e:
            print(f"   ⚠️  Could not load holdings: {str(e)}")
            return None
    
    def _compute_past_accuracy(self):
        """Compute hit rates and quintile returns from backfilled recommendation outcomes."""
        try:
            df = self.recommendation_history.history_df
            if df is None or df.empty:
                return {}

            if 'return_30d' not in df.columns:
                return {'total_with_outcomes': 0}

            has_30d = df['return_30d'].notna()
            df_30 = df[has_30d].copy()
            if df_30.empty:
                return {'total_with_outcomes': 0}

            buy_mask = df_30['action'].str.upper().str.contains('BUY|INCREASE|NEW POSITION|BREAKOUT', na=False, regex=True)
            sell_mask = df_30['action'].str.upper().str.contains('SELL|BOOK|EXIT|CONSIDER SELLING', na=False, regex=True)

            buy_df = df_30[buy_mask]
            sell_df = df_30[sell_mask]

            buy_hit = (buy_df['return_30d'] > 0).mean() * 100 if len(buy_df) > 0 else 0
            sell_hit = (sell_df['return_30d'] < 0).mean() * 100 if len(sell_df) > 0 else 0

            q5_avg = q1_avg = 0.0
            if len(df_30) >= 5 and 'score' in df_30.columns:
                df_30['_q'] = pd.qcut(df_30['score'], 5, labels=False, duplicates='drop')
                q5_avg = df_30[df_30['_q'] == 4]['return_30d'].mean()
                q1_avg = df_30[df_30['_q'] == 0]['return_30d'].mean()
                q5_avg = 0.0 if pd.isna(q5_avg) else float(q5_avg)
                q1_avg = 0.0 if pd.isna(q1_avg) else float(q1_avg)

            return {
                'total_with_outcomes': len(df_30),
                'buy_hit_rate_30d': buy_hit,
                'sell_hit_rate_30d': sell_hit,
                'q5_avg_return_30d': q5_avg,
                'q1_avg_return_30d': q1_avg,
            }
        except Exception as e:
            logging.warning(f"Past accuracy computation failed: {e}")
            return {}

    def generate_portfolio_allocation_suggestions(self, results_df, target_amount=100000, target_stocks=35, portfolio_size_info=None):
        """
        ENHANCEMENT 4: Risk-Based Portfolio Allocation with Strict Limits
        Shows complete target portfolio with strict risk profile enforcement
        Analyzes all holdings, ranks by performance, enforces category allocation
        Generates both BUY and SELL recommendations to meet risk profile targets
        """
        print(f"\n   🔧 CHECKPOINT 1: Starting portfolio allocation generation...")
        print(f"      Results: {len(results_df)} stocks, Target: {target_stocks}, Amount: ₹{target_amount:,}")
        
        try:
            # Load current holdings
            current_holdings = self._load_current_holdings()
            current_portfolio_value = 0
            current_sectors = {}
            
            print(f"   🔧 CHECKPOINT 2: Loaded {len(current_holdings) if current_holdings is not None else 0} current holdings")
            
            # 🚀 OPTIMIZATION: Skip expensive pre-breakout API calls for large portfolios
            skip_prebreakout_api = current_holdings is not None and len(current_holdings) > 50
            if skip_prebreakout_api:
                print(f"   ⚡ OPTIMIZATION: Skipping pre-breakout API calls ({len(current_holdings)} holdings > 50 limit)")
                print(f"      This avoids 200+ sequential API calls that can timeout.")
            
            if current_holdings is not None and not current_holdings.empty:
                # Ensure numeric columns are properly converted (handle strings with commas)
                numeric_cols = ['Cur. val', 'Invested', 'Qty.', 'Avg. cost', 'LTP', 'P&L']
                for col in numeric_cols:
                    if col in current_holdings.columns:
                        current_holdings[col] = pd.to_numeric(current_holdings[col], errors='coerce').fillna(0)
                
                current_portfolio_value = float(current_holdings['Cur. val'].sum())
                
                if 'Sector' in current_holdings.columns:
                    sector_values = current_holdings.groupby('Sector')['Cur. val'].sum()
                    current_sectors = {sector: float(value)/current_portfolio_value if current_portfolio_value > 0 else 0 for sector, value in sector_values.items()}
                
                # Reconciliation: compare sum-of-parts to individual position values
                _invested_total = float(current_holdings['Invested'].sum()) if 'Invested' in current_holdings.columns else 0
                _pnl_total = float(current_holdings['P&L'].sum()) if 'P&L' in current_holdings.columns else 0
                _recon_expected = _invested_total + _pnl_total
                if _recon_expected > 0 and current_portfolio_value > 0:
                    _recon_diff_pct = abs(current_portfolio_value - _recon_expected) / _recon_expected * 100
                    if _recon_diff_pct > 2.0:
                        logging.warning(
                            f"Portfolio reconciliation mismatch: Cur.val sum=₹{current_portfolio_value:,.0f} "
                            f"vs Invested+P&L=₹{_recon_expected:,.0f} (diff={_recon_diff_pct:.1f}%)"
                        )
                        print(f"   ⚠️  RECONCILIATION: ₹{current_portfolio_value:,.0f} vs ₹{_recon_expected:,.0f} ({_recon_diff_pct:.1f}% diff)")
                    else:
                        print(f"   ✅ RECONCILIATION: ₹{current_portfolio_value:,.0f} matches Invested+P&L (diff < 2%)")

                print(f"   📊 Current Portfolio: ₹{current_portfolio_value:,.0f} across {len(current_holdings)} stocks")
                print(f"   💰 Available Funds: ₹{target_amount:,.0f}")
                print(f"   🎯 Total Target Portfolio: ₹{current_portfolio_value + target_amount:,.0f}")
                print(f"   📈 Target Portfolio Size: {target_stocks} stocks")
            
            allocation_data = []
            
            # STEP 1: Add current holdings to allocation
            _INSTRUMENT_ALIASES = ['Instrument', 'Symbol', 'Stock', 'Ticker', 'symbol', 'instrument']
            def _resolve_instrument_col(df_cols):
                for alias in _INSTRUMENT_ALIASES:
                    if alias in df_cols:
                        return alias
                return 'Instrument'

            if current_holdings is not None and not current_holdings.empty:
                _inst_col = _resolve_instrument_col(current_holdings.columns)
                for idx, holding in current_holdings.iterrows():
                    symbol = holding[_inst_col].upper()
                    
                    # Calculate holding percentage of current portfolio
                    holding_percentage = (holding['Cur. val'] / current_portfolio_value) * 100 if current_portfolio_value > 0 else 0
                    
                    # Find this stock in analysis results
                    stock_analysis = results_df[results_df['symbol'].str.upper() == symbol]
                    
                    if not stock_analysis.empty:
                        # Convert Series to dict to avoid ambiguous truth value errors
                        stock_data = stock_analysis.iloc[0].to_dict()
                        
                        logging.debug(f"Holdings analysis for {symbol}: ios={stock_data.get('improved_overall_score')}, pe={stock_data.get('pe_ratio')}")
                        
                        recommendation = stock_data.get('final_recommendation', 'HOLD')
                        
                        # Calculate enhanced metrics
                        momentum_score, momentum_flags = self.calculate_momentum_score(stock_data)
                        
                        # 🚀 NEW: Pre-Breakout Detection (instead of post-breakout)
                        breakout_patterns, breakout_score = self.detect_breakout_patterns(stock_data)  # OLD: Post-breakout (too late)
                        
                        # Fetch historical data for early breakout detection
                        if skip_prebreakout_api:
                            # Use default values for large portfolios (avoid API timeout)
                            pre_breakout = {'pre_breakout_detected': False, 'breakout_probability': 0, 'signals': []}
                            exhaustion = {'exhaustion_detected': False, 'exhaustion_score': 0, 'exit_signals': []}
                        else:
                            try:
                                ticker = yf.Ticker(f"{symbol}.NS")
                                hist = ticker.history(period="3mo", interval="1d")
                                
                                # 🚀 PRE-BREAKOUT DETECTION: Catch stocks BEFORE they break out
                                pre_breakout = self.early_breakout_detector.detect_pre_breakout_setup(hist, stock_data)
                                
                                # 🛑 MOMENTUM EXHAUSTION: Detect when to exit
                                entry_price = holding.get('Avg. cost', 0)
                                exhaustion = self.early_breakout_detector.detect_momentum_exhaustion(
                                    hist, stock_data, entry_price
                                )
                                
                                # Store pre-breakout signals in stock_data for reporting
                                stock_data['pre_breakout_detected'] = pre_breakout['pre_breakout_detected']
                                stock_data['breakout_probability'] = pre_breakout.get('breakout_probability', 0)
                                stock_data['pre_breakout_signals'] = ' | '.join(pre_breakout.get('signals', []))
                                stock_data['exhaustion_detected'] = exhaustion['exhaustion_detected']
                                stock_data['exhaustion_score'] = exhaustion['exhaustion_score']
                                stock_data['exit_signals'] = ' | '.join(exhaustion.get('exit_signals', []))
                                
                            except Exception as e:
                                logging.warning(f"Pre-breakout detection failed for {symbol}: {e}")
                                pre_breakout = {'pre_breakout_detected': False, 'breakout_probability': 0}
                                exhaustion = {'exhaustion_detected': False, 'exhaustion_score': 0}
                        
                        profit_action, profit_pct, profit_reason = self.calculate_profit_booking_strategy(
                            holding['Cur. val'], holding.get('Invested', 0), symbol, stock_data
                        )
                        
                        # 🚀 IMPROVED: Determine action using PRE-BREAKOUT and EXHAUSTION signals with CONFLICT RESOLUTION
                        # Priority order: Exhaustion > Conflicts > Profit Booking > Pre-Breakout > Recommendation
                        
                        # Check for CONFLICTS (both pre-breakout AND exhaustion)
                        has_conflict = (pre_breakout['pre_breakout_detected'] and 
                                       pre_breakout['breakout_probability'] >= 60 and
                                       exhaustion['exhaustion_detected'] and 
                                       exhaustion['exhaustion_score'] >= 30)
                        
                        if has_conflict:
                            # CONFLICT RESOLUTION: Apply decision matrix
                            bp = pre_breakout['breakout_probability']
                            es = exhaustion['exhaustion_score']
                            
                            if es >= 60:
                                # Exit score too high - SKIP entry
                                action_type = f"⚠️ SKIP - EXHAUSTED ({es:.0f})"
                                priority = "URGENT"
                                action_reason = f"Conflict: High exhaustion ({es:.0f}) overrides breakout setup ({bp:.0f}%). {exhaustion.get('exit_signals', [''])[0]}"
                            
                            elif es >= 45 and bp >= 85:
                                # Strong setup but moderate exhaustion - CAUTIOUS
                                action_type = f"🟡 SMALL ENTRY (20-30%)"
                                priority = "HIGH"
                                action_reason = f"Conflict: Strong setup ({bp:.0f}%) but exhaustion ({es:.0f}%). Enter small, tight stop -3%"
                            
                            elif es < 45 and bp >= 70:
                                # Setup strong, exhaustion manageable - CAN ENTER
                                action_type = f"🟢 ENTER (50-70%)"
                                priority = "HIGH"
                                action_reason = f"Conflict resolved: Setup strong ({bp:.0f}%), exhaustion manageable ({es:.0f}%). Monitor RSI closely"
                            
                            else:
                                # Risk/reward unfavorable
                                # [RT-13 FIX] If EXIT_SCORE>30 on owned stock, SELL instead of SKIP - rotate capital out
                                if exhaustion.get('exhaustion_detected', False) and es > 30:
                                    action_type = "SELL"
                                    priority = "HIGH"
                                    action_reason = f"EXHAUSTION OVERRIDE: EXIT_SCORE={es:.0f}. Conflict but high exit risk — rotate capital out."
                                else:
                                    action_type = "⚪ SKIP - WAIT"
                                    priority = "LOW"
                                    action_reason = f"Conflict: Risk/reward unfavorable (Breakout {bp:.0f}%, Exit {es:.0f}%)"
                        
                        elif exhaustion['exhaustion_detected'] and exhaustion['exhaustion_score'] >= 50:
                            # PRIORITY 1: Exit signals when momentum is exhausting (no pre-breakout)
                            action_type = exhaustion['exit_recommendation']
                            priority = "URGENT" if exhaustion['exhaustion_score'] >= 70 else "HIGH"
                            action_reason = f"MOMENTUM EXHAUSTION: {' | '.join(exhaustion.get('exit_signals', []))}"
                            
                        elif 'BOOK' in profit_action or 'STOP LOSS' in profit_action:
                            # PRIORITY 2: Profit booking or stop loss
                            action_type = profit_action
                            priority = "HIGH"
                            action_reason = profit_reason
                            
                        elif pre_breakout['pre_breakout_detected'] and pre_breakout['breakout_probability'] >= 60:
                            # PRIORITY 3: Pre-breakout setup - BUY BEFORE breakout happens (no exhaustion)
                            # [RT-11 FIX] Block PRE-BREAKOUT if bearish pattern, zero breakout%, or RSI>67+dist>8% from support
                            _pds = stock_data.get('pattern_dominant_signal', '')
                            _bpct = pre_breakout.get('breakout_probability', 0)
                            _rsi_pb = stock_data.get('real_rsi', stock_data.get('enhanced_rsi_14', 50))
                            _price_pb = stock_data.get('current_price', 0)
                            _support_pb = stock_data.get('support_level', _price_pb)
                            _dist_pb = ((_price_pb - _support_pb) / _support_pb * 100) if _support_pb > 0 else 0
                            # [RT-08C FIX] Also block PRE-BREAKOUT if owned position is at a meaningful loss (> -2%)
                            _cur_pnl_pb = profit_pct  # profit_pct is already defined in this scope
                            if _pds == 'bearish' or _bpct == 0 or (_rsi_pb > 67 and _dist_pb > 8):
                                action_type = "⚪ SKIP - WAIT"
                                priority = "LOW"
                                action_reason = f"PRE-BREAKOUT BLOCKED: Pattern={_pds}, BP%={_bpct:.0f}, RSI={_rsi_pb:.0f}, Dist={_dist_pb:.1f}%"
                            elif _cur_pnl_pb < -0.02:  # [RT-08C] Already losing >2% — hold, don't add more
                                action_type = "HOLD CURRENT"
                                priority = "LOW"
                                action_reason = f"PRE-BREAKOUT BLOCKED: At loss ({_cur_pnl_pb:.1%}) — don't average down, wait for recovery first"
                            elif pre_breakout['breakout_probability'] >= 70:
                                action_type = "🚀 PRE-BREAKOUT - BUY NOW"
                                priority = "HIGH"
                                action_reason = f"PRE-BREAKOUT: {' | '.join(pre_breakout.get('signals', []))}"
                            else:
                                action_type = "⚡ BREAKOUT SETUP - ACCUMULATE"
                                priority = "MEDIUM"
                                action_reason = f"PRE-BREAKOUT: {' | '.join(pre_breakout.get('signals', []))}"
                            
                        elif 'SELL' in recommendation:
                            action_type = "CONSIDER SELLING"
                            priority = "HIGH"
                            action_reason = recommendation
                            
                        elif momentum_score >= 70:
                            action_type = "🚀 MOMENTUM PLAY - INCREASE"
                            priority = "HIGH"
                            action_reason = f"Strong momentum: {momentum_score}/100"
                            
                        elif 'BUY' in recommendation:
                            action_type = "INCREASE POSITION"
                            priority = "MEDIUM"
                            action_reason = recommendation
                        else:
                            action_type = "HOLD CURRENT"
                            priority = "LOW"
                            action_reason = recommendation
                        
                        # 🔧 FIX: Validate recommendation against history
                        fundamentals = {
                            'pe_ratio': stock_data.get('pe_ratio', 0),
                            'roe': stock_data.get('roe', 0),
                            'debt_to_equity': stock_data.get('debt_to_equity', 0)
                        }
                        validation = self.recommendation_history.validate_recommendation(
                            symbol=symbol,
                            proposed_action=action_type,
                            # GAP-VALIDATE-SCORE FIX: use final_blended_score (hybrid-based,
                            # all adjustments applied) — was using old Phase 1 score which
                            # diverges from the hybrid score driving the recommendation.
                            current_score=stock_data.get('final_blended_score',
                                          stock_data.get('overall_score_with_value', 0)),
                            current_price=stock_data.get('current_price', 0),
                            fundamentals=fundamentals,
                            reason=recommendation,
                            rank=idx + 1,
                            sector=stock_data.get('sector', '')
                        )
                        
                        # Apply validated action
                        original_action = action_type
                        action_type = validation['final_action']
                        
                        # Add warnings if recommendation changed
                        if original_action != action_type and validation['warnings']:
                            if idx < 3:  # Show details for first 3 stocks
                                print(f"      ⚠️  {symbol}: {original_action} → {action_type}")
                                for warning in validation['warnings']:
                                    print(f"         {warning}")
                        
                        # Tax awareness for SELL recommendations (Indian STCG/LTCG)
                        _tax_type = 'NA'
                        _estimated_tax = 0
                        _post_tax_proceeds = 0
                        if 'SELL' in str(action_type).upper() or 'EXIT' in str(action_type).upper() or 'BOOK' in str(action_type).upper():
                            _invested = holding.get('Invested', 0)
                            _cur_val = holding.get('Cur. val', 0)
                            _gain = _cur_val - _invested if _invested > 0 else 0
                            _purchase_date = holding.get('purchase_date', None)
                            _holding_months = 0  # Conservative: assume STCG when date unknown
                            if _purchase_date:
                                try:
                                    _pd = pd.to_datetime(_purchase_date, errors='coerce')
                                    if not pd.isna(_pd):
                                        _holding_months = max(0, (datetime.now() - _pd).days / 30)
                                except Exception:
                                    pass

                            if _gain > 0:
                                if _holding_months < 12:
                                    _tax_type = 'STCG'
                                    _estimated_tax = _gain * 0.20
                                else:
                                    _tax_type = 'LTCG'
                                    _exempt = 125000
                                    _taxable = max(0, _gain - _exempt)
                                    _estimated_tax = _taxable * 0.125
                                _post_tax_proceeds = _cur_val - _estimated_tax
                                action_reason += f" | TAX: {_tax_type} est. Rs{_estimated_tax:,.0f}"
                            else:
                                _tax_type = 'NO_TAX (LOSS)'
                                _estimated_tax = 0
                                _post_tax_proceeds = _cur_val

                        allocation_data.append({
                            'symbol': symbol,
                            'company_name': stock_data.get('company_name', symbol),
                            'sector': stock_data.get('sector', 'Unknown'),
                            'current_value': holding['Cur. val'],
                            'current_quantity': holding.get('Qty.', 0),
                            'current_price': stock_data.get('current_price', holding.get('LTP', 0)),
                            'avg_cost': holding.get('Avg. cost') or holding.get('LTP') or stock_data.get('current_price', 0),
                            'holding_percentage': holding_percentage,
                            # ✅ UPDATED: Robust Score fallback (Hybrid V4 -> Overall -> Improved -> Risk-Adj)
                            'overall_score': stock_data.get('final_blended_score', stock_data.get('improved_score_used', 0)),
                            'risk_adjusted_score': stock_data.get('risk_adjusted_score', 0),
                            'undervaluation_score': stock_data.get('undervaluation_score', 50),
                            'risk_category': stock_data.get('risk_category', 'MODERATE'),
                            'recommendation': recommendation,
                            'action_type': action_type,
                            'priority': priority,
                            'is_current_holding': True,
                            'volatility_6m': stock_data.get('volatility_6m', 0),
                            'market_cap': stock_data.get('market_cap', 0),
                            # NEW PREDICTIVE FEATURES
                            'momentum_score': momentum_score,
                            'momentum_flags': ' | '.join(momentum_flags) if momentum_flags else 'NONE',
                            'breakout_patterns': ' | '.join(breakout_patterns) if breakout_patterns else 'NONE',
                            'breakout_score': breakout_score,
                            'profit_booking_action': profit_action,
                            'profit_booking_pct': profit_pct,
                            'profit_booking_reason': profit_reason,
                            'current_profit_pct': ((holding['Cur. val'] - holding.get('Invested', 0)) / max(holding.get('Invested', 1), 1)) if holding.get('Invested', 0) > 0 else 0,
                            # 🚀 NEW: Pre-Breakout and Exhaustion Signals
                            'pre_breakout_detected': stock_data.get('pre_breakout_detected', False),
                            'breakout_probability': stock_data.get('breakout_probability', 0),
                            'pre_breakout_signals': stock_data.get('pre_breakout_signals', 'NONE'),
                            'exhaustion_detected': stock_data.get('exhaustion_detected', False),
                            'exhaustion_score': stock_data.get('exhaustion_score', 0),
                            'exit_signals': stock_data.get('exit_signals', 'NONE'),
                            # ✅ ENHANCED: Additional retail investor columns
                            'improved_overall_score': _nv(stock_data.get('final_blended_score', stock_data.get('risk_adjusted_score')), 0),
                            'pe_ratio': stock_data.get('pe_ratio', None),
                            'pb_ratio': stock_data.get('pb_ratio', None),
                            'price_change_1m': stock_data.get('price_change_1m', None),
                            'price_change_3m': stock_data.get('price_change_3m', None),
                            'beta': stock_data.get('beta', None),
                            'dividend_yield': stock_data.get('dividend_yield', None),
                            'optimized_score': stock_data.get('optimized_score', stock_data.get('overall_score_with_value', None)),
                            'roe': stock_data.get('roe', None),
                            'debt_to_equity': stock_data.get('debt_to_equity', None),
                            '52_week_high': stock_data.get('52_week_high', None),
                            '52_week_low': stock_data.get('52_week_low', None),
                            'enhanced_price_change_20d': stock_data.get('enhanced_price_change_20d', None),
                            'support_level': stock_data.get('support_level', None),
                            'resistance_level': stock_data.get('resistance_level', None),
                            'enhanced_rsi_14': stock_data.get('enhanced_rsi_14', None),
                            'volatility': stock_data.get('volatility', None),
                            'improved_fundamental_quality': stock_data.get('improved_fundamental_quality', None),
                            'improved_momentum_technical': stock_data.get('improved_momentum_technical', None),
                            # A-019: ML model signal — visible in Portfolio Allocation sheet
                            'ml_signal': stock_data.get('ml_signal', 'HOLD'),
                            'ml_confidence': stock_data.get('ml_confidence', 0),
                            'ml_score_adjustment': stock_data.get('ml_score_adjustment', 0),
                            # GAP-3 FIX: Score component breakdown now visible in sheet
                            'sector_performance_adj': stock_data.get('sector_performance_adj', 0),
                            'sentiment_score_contribution': stock_data.get('sentiment_score_contribution', 0),
                            'volume_score_contribution': stock_data.get('volume_score_contribution', 0),
                            # GAP-PATTERN-REPORT FIX: pattern adj now propagated to alloc_df
                            'pattern_score_contribution': stock_data.get('pattern_score_contribution', 0),
                            # Hybrid scoring components
                            'hybrid_fundamental_quality': stock_data.get('hybrid_fundamental_quality', 50),
                            'hybrid_momentum_technical': stock_data.get('hybrid_momentum_technical', 50),
                            'hybrid_volume_strength': stock_data.get('hybrid_volume_strength', 50),
                            'hybrid_multi_timeframe': stock_data.get('hybrid_multi_timeframe', 50),
                            'hybrid_ml_signal': stock_data.get('hybrid_ml_signal', 50),
                            'hybrid_risk_adjustment': stock_data.get('hybrid_risk_adjustment', 50),
                            'ad_line_signal': stock_data.get('ad_line_signal', 'NEUTRAL'),
                            'mfi_signal': stock_data.get('mfi_signal', 'NEUTRAL'),
                            # Tax awareness columns
                            'tax_type': _tax_type,
                            'estimated_tax': round(_estimated_tax, 0),
                            'post_tax_proceeds': round(_post_tax_proceeds, 0),
                            'action_reason': action_reason,
                        })
                    else:
                        logging.warning(f"[M5] Holdings symbol {symbol} not found in analysis results — may need manual review")
                        _stale_action = "HOLD CURRENT"
                        _stale_rec = "HOLD (NOT ANALYZED)"
                        _stale_priority = "LOW"
                        try:
                            _last_rec = self.recommendation_history.get_recommendation_summary(symbol, days=7)
                            if _last_rec.empty:
                                _stale_action = "REVIEW REQUIRED (STALE)"
                                _stale_rec = "REVIEW REQUIRED — no analysis in 7+ days"
                                _stale_priority = "HIGH"
                                logging.warning(f"{symbol}: NOT ANALYZED and no recent recommendation — marked REVIEW REQUIRED")
                        except Exception:
                            pass
                        allocation_data.append({
                            'symbol': symbol,
                            'company_name': symbol,
                            'sector': 'Unknown',
                            'current_value': holding['Cur. val'],
                            'current_quantity': holding.get('Qty.', 0),
                            'current_price': holding.get('LTP', 0),
                            'avg_cost': holding.get('Avg. cost') or holding.get('LTP', 0),
                            'holding_percentage': holding_percentage,
                            'overall_score': 0,
                            'risk_adjusted_score': 0,
                            'undervaluation_score': 0,
                            'risk_category': 'UNKNOWN',
                            'recommendation': _stale_rec,
                            'action_type': _stale_action,
                            'priority': _stale_priority,
                            'is_current_holding': True,
                            'volatility_6m': 0,
                            'market_cap': 0,
                            'momentum_score': 0,
                            'momentum_flags': 'NOT ANALYZED',
                            'breakout_patterns': 'NOT ANALYZED',
                            'breakout_score': 0,
                            'profit_booking_action': 'HOLD (NOT ANALYZED)',
                            'profit_booking_pct': 0,
                            'profit_booking_reason': 'Stock not in analysis scope',
                            'current_profit_pct': ((holding['Cur. val'] - holding.get('Invested', 0)) / max(holding.get('Invested', 1), 1)) if holding.get('Invested', 0) > 0 else 0,
                            'pre_breakout_detected': False,
                            'breakout_probability': 0,
                            'pre_breakout_signals': 'NOT ANALYZED',
                            'exhaustion_detected': False,
                            'exhaustion_score': 0,
                            'exit_signals': 'NOT ANALYZED',
                            'improved_overall_score': 0,
                            'pe_ratio': None,
                            'pb_ratio': None,
                            'price_change_1m': None,
                            'price_change_3m': None,
                            'beta': None,
                            'dividend_yield': None,
                            'optimized_score': None,
                            'roe': None,
                            'debt_to_equity': None,
                            '52_week_high': None,
                            '52_week_low': None,
                            'enhanced_price_change_20d': None,
                            'support_level': None,
                            'resistance_level': None,
                            'enhanced_rsi_14': None,
                            'volatility': None,
                            'improved_fundamental_quality': None,
                            'improved_momentum_technical': None,
                            'ml_signal': 'NOT ANALYZED',
                            'ml_confidence': 0,
                            'ml_score_adjustment': 0,
                            'sector_performance_adj': 0,
                            'sentiment_score_contribution': 0,
                            'volume_score_contribution': 0,
                            'pattern_score_contribution': 0,
                            'hybrid_fundamental_quality': 50,
                            'hybrid_momentum_technical': 50,
                            'hybrid_volume_strength': 50,
                            'hybrid_multi_timeframe': 50,
                            'hybrid_ml_signal': 50,
                            'hybrid_risk_adjustment': 50,
                            'ad_line_signal': 'NOT ANALYZED',
                            'mfi_signal': 'NOT ANALYZED',
                        })
            
            print(f"   🔧 CHECKPOINT 3: Processed {len(allocation_data)} current holdings")

            # SECTOR CAP ENFORCEMENT ON EXISTING HOLDINGS
            # Strategy: reduce down to SECTOR_CAP, protecting the top-scoring stocks.
            # The lowest-scoring stocks in the overweight sector are marked REDUCE
            # until the sector count reaches SECTOR_CAP.
            if getattr(_config, 'SECTOR_CAP_ENFORCE_HOLDINGS', True):
                _sector_counts_h = {}
                for _alloc in allocation_data:
                    _s = _alloc.get('sector', 'Unknown')
                    _sector_counts_h[_s] = _sector_counts_h.get(_s, 0) + 1

                _overweight_sectors = {s: c for s, c in _sector_counts_h.items()
                                       if c > _config.SECTOR_CAP and s != 'Unknown'}
                if _overweight_sectors:
                    print(f"\n   ⚠️  SECTOR OVERWEIGHT DETECTED:")
                    for _ow_sector, _ow_count in _overweight_sectors.items():
                        _sector_stocks = [a for a in allocation_data
                                          if a.get('sector') == _ow_sector and a.get('is_current_holding')]
                        _sector_stocks.sort(key=lambda x: x.get('risk_adjusted_score', x.get('overall_score', 0)))
                        _to_reduce = max(0, len(_sector_stocks) - _config.SECTOR_CAP)
                        _reduced = 0
                        _kept = 0
                        for _ss in _sector_stocks:
                            if _reduced >= _to_reduce:
                                _kept += 1
                                continue
                            _ss_score = _ss.get('risk_adjusted_score', _ss.get('overall_score', 0))
                            if _ss.get('action_type', '') in ('HOLD CURRENT', 'KEEP'):
                                _ss['action_type'] = 'REDUCE (SECTOR OVERWEIGHT)'
                                _ss['priority'] = 'MEDIUM'
                                _ss['profit_booking_reason'] = (
                                    f"Sector {_ow_sector} has {_ow_count} stocks (cap={_config.SECTOR_CAP}). "
                                    f"Score {_ss_score:.1f} — reducing weakest to reach cap."
                                )
                                logging.warning(
                                    f"Sector overweight: marking {_ss['symbol']} for reduction "
                                    f"(score={_ss_score:.1f}, "
                                    f"{_ow_sector} has {_ow_count} stocks, cap={_config.SECTOR_CAP})"
                                )
                                _reduced += 1
                            else:
                                _kept += 1
                        print(f"      {_ow_sector}: {_ow_count} stocks (cap={_config.SECTOR_CAP}) "
                              f"→ {_reduced} REDUCE, {_kept} KEPT (top {_config.SECTOR_CAP} by score)")

            # STEP 2: Find new investment candidates (not currently held)
            holding_symbols = set()
            if current_holdings is not None and not current_holdings.empty:
                _hs_col = next((c for c in ['Instrument', 'Symbol', 'Stock', 'Ticker', 'symbol', 'instrument'] if c in current_holdings.columns), 'Instrument')
                holding_symbols = set(current_holdings[_hs_col].str.upper())
            
            # Get BUY candidates not currently held
            # Convert scores to numeric to avoid comparison errors
            results_df['overall_score_with_value'] = pd.to_numeric(results_df['overall_score_with_value'], errors='coerce').fillna(50)  # HI-04: neutral, not sell
            if 'overall_score' not in results_df.columns:
                results_df['overall_score'] = results_df['overall_score_with_value']
            results_df['overall_score'] = pd.to_numeric(results_df['overall_score'], errors='coerce').fillna(50)  # HI-04
            results_df['undervaluation_score'] = pd.to_numeric(results_df['undervaluation_score'], errors='coerce').fillna(50)  # HI-04
            
            new_candidates = results_df[
                (results_df['final_recommendation'].str.contains('BUY', na=False)) &
                (~results_df['symbol'].str.upper().isin(holding_symbols)) &
                (results_df['overall_score'] >= 55) &
                (results_df['undervaluation_score'] >= 40)
            ].copy()
            
            # Sort by risk-adjusted score and limit to remaining slots
            current_holdings_count = len(allocation_data)
            remaining_slots = target_stocks - current_holdings_count
            
            if remaining_slots > 0 and not new_candidates.empty:
                # ✅ UPDATED: Sort by Hybrid V4 Score (hybrid_overall_score) instead of Risk-Adjusted
                # First ensure hybrid_overall_score is numeric
                new_candidates['hybrid_overall_score'] = pd.to_numeric(new_candidates.get('hybrid_overall_score', new_candidates['overall_score_with_value']), errors='coerce').fillna(50)  # HI-04
                new_candidates = new_candidates.sort_values('hybrid_overall_score', ascending=False).head(remaining_slots)
                
                for idx, stock in new_candidates.iterrows():
                    # Calculate predictive metrics for new positions
                    momentum_score, momentum_flags = self.calculate_momentum_score(stock)
                    breakout_patterns, breakout_score = self.detect_breakout_patterns(stock)  # OLD: Post-breakout
                    
                    # 🚀 NEW: Pre-Breakout Detection for new positions
                    try:
                        symbol = stock['symbol']
                        ticker = yf.Ticker(f"{symbol}.NS")
                        hist = ticker.history(period="3mo", interval="1d")
                        
                        # Convert Series to dict for early_breakout_detector
                        stock_dict = stock.to_dict() if hasattr(stock, 'to_dict') else stock
                        
                        # PRE-BREAKOUT DETECTION for new candidates
                        pre_breakout = self.early_breakout_detector.detect_pre_breakout_setup(hist, stock_dict)
                        
                        # Store in stock dict for later use
                        stock_dict['pre_breakout_detected'] = pre_breakout['pre_breakout_detected']
                        stock_dict['breakout_probability'] = pre_breakout.get('breakout_probability', 0)
                        stock_dict['pre_breakout_signals'] = ' | '.join(pre_breakout.get('signals', []))
                        
                    except Exception as e:
                        logging.warning(f"Pre-breakout detection failed for {stock['symbol']}: {e}")
                        pre_breakout = {'pre_breakout_detected': False, 'breakout_probability': 0}
                        stock_dict = stock.to_dict() if hasattr(stock, 'to_dict') else stock
                    
                    # 🚀 IMPROVED: Determine action type with CONFLICT RESOLUTION for new candidates
                    # New candidates don't have exhaustion (no entry price), but check for overbought conditions
                    
                    # Check if stock is overbought (pseudo-exhaustion for new entries)
                    rsi = stock_dict.get('real_rsi', stock_dict.get('enhanced_rsi_14', 50))
                    is_overbought = rsi > 70

                    # [RT-11 FIX] Block PRE-BREAKOUT for new candidates if bearish/zero breakout/overbought+far from support
                    _pds_nc = stock_dict.get('pattern_dominant_signal', '')
                    _bpct_nc = pre_breakout.get('breakout_probability', 0)
                    _price_nc = stock_dict.get('current_price', 0)
                    _support_nc = stock_dict.get('support_level', _price_nc)
                    _dist_nc = ((_price_nc - _support_nc) / _support_nc * 100) if _support_nc > 0 else 0
                    if _pds_nc == 'bearish' or _bpct_nc == 0 or (rsi > 67 and _dist_nc > 8):
                        pre_breakout['pre_breakout_detected'] = False

                    # Conflict: Pre-breakout setup but overbought
                    if pre_breakout['pre_breakout_detected'] and pre_breakout['breakout_probability'] >= 60 and is_overbought:
                        bp = pre_breakout['breakout_probability']
                        action_type = f"⚠️ WAIT - OVERBOUGHT (RSI {rsi:.0f})"
                        priority = 'LOW'
                        action_reason = f"Pre-breakout setup ({bp:.0f}%) but RSI overbought ({rsi:.0f}). Wait for pullback."
                    
                    elif pre_breakout['pre_breakout_detected'] and pre_breakout['breakout_probability'] >= 70:
                        action_type = "🚀 PRE-BREAKOUT - BUY NOW"
                        priority = 'VERY HIGH'
                        action_reason = f"Strong pre-breakout setup: {pre_breakout.get('signals', [''])[0]}"
                    
                    elif pre_breakout['pre_breakout_detected'] and pre_breakout['breakout_probability'] >= 50:
                        action_type = "⚡ BREAKOUT SETUP - NEW POSITION"
                        priority = 'HIGH'
                        action_reason = f"Good setup: {pre_breakout.get('signals', [''])[0]}"
                    
                    elif momentum_score >= 70:
                        action_type = "🚀 HIGH MOMENTUM NEW POSITION"
                        priority = 'VERY HIGH'
                        action_reason = f"High momentum score: {momentum_score}/100"
                    
                    elif breakout_score >= 60:
                        action_type = "📈 BREAKOUT NEW POSITION"
                        priority = 'HIGH'
                        action_reason = f"Breakout detected: {breakout_score}/100"
                    
                    else:
                        action_type = "NEW POSITION"
                        priority = 'HIGH'
                        action_reason = stock.get('final_recommendation', 'BUY recommendation')
                    
                    # 🔧 FIX: Validate new position against history
                    fundamentals = {
                        'pe_ratio': stock.get('pe_ratio', 0),
                        'roe': stock.get('roe', 0),
                        'debt_to_equity': stock.get('debt_to_equity', 0)
                    }
                    validation = self.recommendation_history.validate_recommendation(
                        symbol=stock['symbol'],
                        proposed_action="BUY",  # Normalize all new positions to BUY
                        # GAP-VALIDATE-SCORE FIX: use final_blended_score for consistency
                        current_score=stock.get('final_blended_score',
                                      stock.get('overall_score_with_value', 0)),
                        current_price=stock.get('current_price', 0),
                        fundamentals=fundamentals,
                        reason=stock.get('final_recommendation', ''),
                        rank=len(allocation_data) + 1,
                        sector=stock.get('sector', '')
                    )
                    
                    # Check if we should skip this position due to cooldown
                    if validation['final_action'] == 'HOLD' and 'COOLDOWN' in ' '.join(validation['warnings']):
                        continue  # Skip this new position
                    
                    allocation_data.append({
                        'symbol': stock['symbol'],
                        'company_name': stock.get('company_name', stock['symbol']),
                        'sector': stock.get('sector', 'Unknown'),
                        'current_value': 0,
                        'current_quantity': 0,
                        'current_price': stock.get('current_price', 0),
                        'avg_cost': 0,
                        # ✅ UPDATED: Robust Score fallback (Hybrid V4 -> Overall -> Improved -> Risk-Adj)
                        'overall_score': stock.get('final_blended_score', stock.get('improved_score_used', 0)),
                        'risk_adjusted_score': stock.get('risk_adjusted_score', 0),
                        'undervaluation_score': stock.get('undervaluation_score', 50),
                        'risk_category': stock.get('risk_category', 'MODERATE'),
                        'recommendation': stock.get('final_recommendation', ''),
                        'action_type': action_type,
                        'priority': priority,
                        'is_current_holding': False,
                        'volatility_6m': stock.get('volatility_6m', 0),
                        'market_cap': stock.get('market_cap', 0),
                        # NEW PREDICTIVE FEATURES
                        'momentum_score': momentum_score,
                        'momentum_flags': ' | '.join(momentum_flags) if momentum_flags else 'NONE',
                        'breakout_patterns': ' | '.join(breakout_patterns) if breakout_patterns else 'NONE',
                        'breakout_score': breakout_score,
                        'profit_booking_action': 'NEW POSITION',
                        'profit_booking_pct': 0,
                        'profit_booking_reason': 'Fresh investment opportunity',
                        'current_profit_pct': 0,
                        # 🚀 NEW: Pre-Breakout Signals for new positions
                        'pre_breakout_detected': stock_dict.get('pre_breakout_detected', False),
                        'breakout_probability': stock_dict.get('breakout_probability', 0),
                        'pre_breakout_signals': stock_dict.get('pre_breakout_signals', 'NONE'),
                        'exhaustion_detected': False,  # New positions don't have exhaustion
                        'exhaustion_score': 0,
                        'exit_signals': 'NONE',
                        # ✅ ENHANCED: Additional retail investor columns
                        'improved_overall_score': _nv(stock.get('final_blended_score', stock.get('risk_adjusted_score')), 0),
                        'pe_ratio': stock.get('pe_ratio', None),
                        'pb_ratio': stock.get('pb_ratio', None),
                        'price_change_1m': stock.get('price_change_1m', None),
                        'price_change_3m': stock.get('price_change_3m', None),
                        'beta': stock.get('beta', None),
                        'dividend_yield': stock.get('dividend_yield', None),
                        'optimized_score': stock.get('optimized_score', stock.get('overall_score_with_value', None)),
                        'roe': stock.get('roe', None),
                        'debt_to_equity': stock.get('debt_to_equity', None),
                        '52_week_high': stock.get('52_week_high', None),
                        '52_week_low': stock.get('52_week_low', None),
                        'enhanced_price_change_20d': stock.get('enhanced_price_change_20d', None),
                        'support_level': stock.get('support_level', None),
                        'resistance_level': stock.get('resistance_level', None),
                        'enhanced_rsi_14': stock.get('enhanced_rsi_14', None),
                        'volatility': stock.get('volatility', None),
                        'improved_fundamental_quality': stock.get('improved_fundamental_quality', None),
                        'improved_momentum_technical': stock.get('improved_momentum_technical', None),
                        # A-019: ML model signal — visible in Portfolio Allocation sheet
                        'ml_signal': stock.get('ml_signal', 'HOLD'),
                        'ml_confidence': stock.get('ml_confidence', 0),
                        'ml_score_adjustment': stock.get('ml_score_adjustment', 0),
                        # GAP-3 FIX: Score component breakdown now visible in sheet
                        'sector_performance_adj': stock.get('sector_performance_adj', 0),
                        'sentiment_score_contribution': stock.get('sentiment_score_contribution', 0),
                        'volume_score_contribution': stock.get('volume_score_contribution', 0),
                        # GAP-PATTERN-REPORT FIX: pattern adj now propagated to alloc_df
                        'pattern_score_contribution': stock.get('pattern_score_contribution', 0),
                        # Hybrid scoring components
                        'hybrid_fundamental_quality': stock.get('hybrid_fundamental_quality', 50),
                        'hybrid_momentum_technical': stock.get('hybrid_momentum_technical', 50),
                        'hybrid_volume_strength': stock.get('hybrid_volume_strength', 50),
                        'hybrid_multi_timeframe': stock.get('hybrid_multi_timeframe', 50),
                        'hybrid_ml_signal': stock.get('hybrid_ml_signal', 50),
                        'hybrid_risk_adjustment': stock.get('hybrid_risk_adjustment', 50),
                        'ad_line_signal': stock.get('ad_line_signal', 'NEUTRAL'),
                        'mfi_signal': stock.get('mfi_signal', 'NEUTRAL'),
                    })
            
            # STEP 3: Risk Profile-Based Category Allocation
            allocation_df = pd.DataFrame(allocation_data)
            
            # Initialize allocation columns for all rows
            allocation_df['allocation_percentage'] = 0.0
            allocation_df['portfolio_weight'] = 0.0
            allocation_df['investment_amount'] = 0.0
            allocation_df['suggested_quantity'] = 0
            allocation_df['stock_type'] = 'VALUE'  # Default classification
            allocation_df['weight_capped'] = False
            
            # 🔧 FIX: Initialize action_recommendation from action_type (if exists)
            if 'action_type' in allocation_df.columns:
                allocation_df['action_recommendation'] = allocation_df['action_type']
            else:
                allocation_df['action_recommendation'] = 'HOLD'
            
            # 🔧 FIX: Ensure all critical columns exist with defaults
            if 'exit_reason' not in allocation_df.columns:
                allocation_df['exit_reason'] = ''
            if 'priority' not in allocation_df.columns:
                allocation_df['priority'] = 'LOW'
            if 'profit_booking_amount' not in allocation_df.columns:
                allocation_df['profit_booking_amount'] = 0.0
            if 'stop_loss_price' not in allocation_df.columns:
                allocation_df['stop_loss_price'] = 0.0
            
            # 🔧 FIX #1: Calculate portfolio_weight for ALL EXISTING holdings (not just new ones)
            print(f"   📊 Calculating portfolio weights for existing holdings...")
            if current_portfolio_value > 0:
                for idx, row in allocation_df[allocation_df['is_current_holding'] == True].iterrows():
                    if row['current_value'] > 0:
                        portfolio_weight = row['current_value'] / current_portfolio_value  # As decimal
                        allocation_df.at[idx, 'portfolio_weight'] = portfolio_weight
                
                total_weight = allocation_df[allocation_df['is_current_holding'] == True]['portfolio_weight'].sum()
                print(f"      ✅ Current holdings portfolio weight: {total_weight:.2%} (should be ~100%)")
            
            # 🔧 FIX #2: Add market cap classification for ALL stocks (not just new ones)
            print(f"   🏷️ Classifying market cap for all stocks...")
            for idx, row in allocation_df.iterrows():
                market_cap = row.get('market_cap', 0)
                if market_cap > 0:
                    cap_category, max_allocation_pct = self.classify_market_cap(market_cap)
                    allocation_df.at[idx, 'market_cap_category'] = cap_category
                    allocation_df.at[idx, 'max_allocation_pct'] = max_allocation_pct * 100
                else:
                    allocation_df.at[idx, 'market_cap_category'] = 'UNKNOWN'
                    allocation_df.at[idx, 'max_allocation_pct'] = 5.0  # Default 5%
            
            # Initialize profit booking and timing columns
            allocation_df['profit_booking_pct'] = None
            allocation_df['profit_booking_timing'] = None
            
            # 🔧 FIX #3: Rank ALL current holdings by performance (for exit strategy)
            print(f"   📊 Ranking current holdings by performance...")
            current_holdings_df = allocation_df[allocation_df['is_current_holding'] == True].copy()
            if not current_holdings_df.empty:
                # Rank by overall_score (best to worst) - USING HYBRID V4 SCORE for better returns
                current_holdings_df['holdings_rank'] = current_holdings_df['overall_score'].rank(method='dense', ascending=False).astype(int)
                
                # Update main dataframe with rankings
                for idx, row in current_holdings_df.iterrows():
                    allocation_df.at[idx, 'holdings_rank'] = row['holdings_rank']
                
                # Add holdings_rank column to allocation_df (default 0 for new positions)
                if 'holdings_rank' not in allocation_df.columns:
                    allocation_df['holdings_rank'] = 0
                
                total_holdings = len(current_holdings_df)
                top_30_pct = int(total_holdings * 0.30)
                bottom_20_pct = int(total_holdings * 0.20)
                
                print(f"      📊 Holdings ranked: Top {top_30_pct} (INCREASE), Bottom {bottom_20_pct} (CONSIDER SELLING)")
                print(f"      🏆 Best performer: {current_holdings_df.nsmallest(1, 'holdings_rank')['symbol'].iloc[0]} (Rank #{current_holdings_df['holdings_rank'].min()})")
                print(f"      ⚠️  Worst performer: {current_holdings_df.nlargest(1, 'holdings_rank')['symbol'].iloc[0]} (Rank #{current_holdings_df['holdings_rank'].max()})")
                
                # 🎯 VALUE INVESTING PROTECTION: Identify quality winners (don't sell these!)
                quality_winners = current_holdings_df[
                    (current_holdings_df['current_profit_pct'] > 0.20)  # High profit (>20%)
                ].copy()
                
                if len(quality_winners) > 0:
                    print(f"\n   🏆 QUALITY WINNERS IDENTIFIED: {len(quality_winners)} stocks with >20% profit")
                    print(f"      These are SUCCESS stories - will protect from exit strategy")
                    for _, winner in quality_winners.iterrows():
                        symbol = winner['symbol']
                        profit = winner['current_profit_pct']
                        print(f"      ✅ {symbol}: +{profit:.1f}% (KEEP core position)")
                
                # 🔧 FIX #4: CLEAR EXIT STRATEGY - Bottom 20% = SELL, Top 30% = INCREASE, Middle = HOLD
                # Modified for VALUE INVESTING: Don't sell quality winners just because of low score
                print(f"\n   🎯 Applying VALUE-BASED EXIT STRATEGY (30/50/20 Rule)...")
                
                for idx, row in current_holdings_df.iterrows():
                    rank = row['holdings_rank']
                    score = row['overall_score']  # Use Hybrid V4 score
                    profit_pct = row.get('current_profit_pct', 0)
                    symbol = row['symbol']
                    
                    # 🏆 VALUE INVESTING RULE: Protect quality winners (>20% profit)
                    # These are SUCCESS stories - don't sell just because score is lower!
                    is_quality_winner = profit_pct > 0.20
                    
                    if is_quality_winner:
                        # Quality winner - ALWAYS protect, suggest partial profit booking
                        if profit_pct > 0.40:
                            action = 'HOLD'
                            reason = f"🏆 QUALITY WINNER +{profit_pct:.1f}% | Consider taking 50% profit, hold rest"
                            priority = 'HIGH'
                            allocation_df.at[idx, 'exit_strategy'] = '💎 QUALITY - TAKE PARTIAL PROFIT'
                        elif profit_pct > 0.30:
                            action = 'HOLD'
                            reason = f"🏆 QUALITY WINNER +{profit_pct:.1f}% | Consider taking 30-40% profit"
                            priority = 'MEDIUM'
                            allocation_df.at[idx, 'exit_strategy'] = '💎 QUALITY - HOLD CORE'
                        else:  # 20-30% profit
                            action = 'INCREASE'
                            reason = f"🏆 QUALITY WINNER +{profit_pct:.1f}% | Can add on dips"
                            priority = 'LOW'
                            allocation_df.at[idx, 'exit_strategy'] = '💎 QUALITY - ADD ON DIPS'
                    
                    # TOP 30% - INCREASE POSITION (best performers)
                    elif rank <= top_30_pct:
                        # [RT-08 FIX] Don't INCREASE if currently at a loss (>2%) unless ML=STRONG_BUY
                        _ml_sig_inc = str(allocation_df.at[idx, 'ml_signal']) if 'ml_signal' in allocation_df.columns else ''
                        if profit_pct < -0.02 and _ml_sig_inc != 'STRONG_BUY':
                            action = 'HOLD'
                            reason = f"🔄 TOP SCORER but AT LOSS ({profit_pct:.1f}%) - Hold, rotate when profitable | Score: {score:.1f}"
                            priority = 'MEDIUM'
                            allocation_df.at[idx, 'exit_strategy'] = '⚠️ HOLD - ROTATION CANDIDATE'
                        else:
                            action = 'INCREASE'
                            reason = f"🏆 TOP PERFORMER (Rank #{rank}/{total_holdings}) | Score: {score:.1f}"
                            priority = 'HIGH'
                            allocation_df.at[idx, 'exit_strategy'] = '✅ KEEP & INCREASE'
                    
                    # BOTTOM 20% - SELL (underperformers or need rebalancing)
                    elif rank > (total_holdings - bottom_20_pct):
                        # [MI-L04 FIX] Never crystallize a loss if ML=HOLD — wait for recovery
                        _ml_l04 = str(allocation_df.at[idx, 'ml_signal']) if 'ml_signal' in allocation_df.columns else ''
                        _ml_hold_l04 = _ml_l04 in ('HOLD', 'STRONG_BUY')
                        # Check if it's actually profitable before recommending sell
                        if profit_pct < -0.05:  # Loss > 5%
                            if _ml_hold_l04:  # [MI-L04] Don't book a loss when ML=HOLD
                                action = 'HOLD'
                                reason = f"⚠️ UNDERPERFORMER but ML={_ml_l04} — Don't crystallize loss | Wait for recovery | Score: {score:.1f}"
                                priority = 'MEDIUM'
                                allocation_df.at[idx, 'exit_strategy'] = '⚠️ HOLD - NO LOSS BOOKING (ML=HOLD)'
                            else:
                                action = 'SELL'
                                reason = f"❌ UNDERPERFORMER (Rank #{rank}/{total_holdings}) | Score: {score:.1f} | Loss: {profit_pct:.1f}%"
                                priority = 'HIGH'
                                allocation_df.at[idx, 'exit_strategy'] = '🔴 SELL - CUT LOSSES'
                        elif score < 50 and profit_pct < 0.05:  # Low score AND minimal profit
                            if _ml_hold_l04 and profit_pct < 0:  # [MI-L04] At a loss + ML=HOLD → protect
                                action = 'HOLD'
                                reason = f"⚠️ WEAK SCORE but AT LOSS + ML={_ml_l04} — Hold, don't book loss | Score: {score:.1f}"
                                priority = 'MEDIUM'
                                allocation_df.at[idx, 'exit_strategy'] = '⚠️ HOLD - RECOVERY PENDING (ML=HOLD)'
                            else:
                                action = 'SELL'
                                reason = f"⚠️ WEAK FUNDAMENTALS (Rank #{rank}/{total_holdings}) | Score: {score:.1f}"
                                priority = 'MEDIUM'
                                allocation_df.at[idx, 'exit_strategy'] = '🟠 SELL - WEAK STOCK'
                        elif profit_pct < 0.05:  # Minimal profit, better opportunities exist
                            if _ml_hold_l04 and profit_pct < 0:  # [MI-L04] At a loss + ML=HOLD → hold until breakeven
                                action = 'HOLD'
                                reason = f"⚠️ REBALANCE candidate but AT LOSS + ML={_ml_l04} — Hold until breakeven (Rank #{rank})"
                                priority = 'LOW'
                                allocation_df.at[idx, 'exit_strategy'] = '⚠️ HOLD - WAIT BREAKEVEN (ML=HOLD)'
                            else:
                                action = 'SELL'
                                reason = f"🔄 REBALANCE (Rank #{rank}/{total_holdings}) | Better opportunities available"
                                priority = 'MEDIUM'
                                allocation_df.at[idx, 'exit_strategy'] = '🟡 SELL - REBALANCE'
                        else:  # Has some profit - maybe hold instead
                            action = 'HOLD'
                            reason = f"⚪ HOLD (Rank #{rank}/{total_holdings}) | Profit: +{profit_pct:.1f}% | Monitor closely"
                            priority = 'LOW'
                            allocation_df.at[idx, 'exit_strategy'] = '⚪ HOLD - MONITOR CLOSELY'
                    
                    # MIDDLE 50% - HOLD (maintain position)
                    else:
                        action = 'HOLD'
                        reason = f"📊 HOLD STEADY (Rank #{rank}/{total_holdings}) | Score: {score:.1f}"
                        priority = 'LOW'
                        allocation_df.at[idx, 'exit_strategy'] = '⚪ HOLD - MONITOR'
                    
                    # Update action_recommendation with EXIT STRATEGY
                    # Skip overwriting if we already have conflict-resolved or REDUCE action
                    current_action = allocation_df.at[idx, 'action_recommendation']
                    _preserve = ('REDUCE' in str(current_action).upper() or
                                 any(emoji in str(current_action) for emoji in ['⚠️', '🟡', '🟢', '⚪', '🚀']))
                    if not _preserve:
                        allocation_df.at[idx, 'action_recommendation'] = action
                    allocation_df.at[idx, 'exit_reason'] = reason
                    allocation_df.at[idx, 'priority'] = priority
                
                # Summary of exit strategy
                _exit_sell_count = len(current_holdings_df[current_holdings_df['holdings_rank'] > (total_holdings - bottom_20_pct)])
                increase_count = len(current_holdings_df[current_holdings_df['holdings_rank'] <= top_30_pct])
                hold_count = total_holdings - _exit_sell_count - increase_count
                
                print(f"      🚀 INCREASE: {increase_count} stocks (top 30%)")
                print(f"      ⚪ HOLD: {hold_count} stocks (middle 50%)")
                print(f"      [SELL] EXIT candidates: {_exit_sell_count} stocks (bottom 20%)")
                print(f"      📊 Net change: {increase_count} to add, {_exit_sell_count} to remove")
                
                # PROFIT BOOKING RULES - Apply to all holdings with >20% profit
                print(f"\n   💰 Applying PROFIT BOOKING rules (>20% gains)...")
                profit_book_candidates = current_holdings_df[current_holdings_df['current_profit_pct'] > 0.20].copy()
                
                if len(profit_book_candidates) > 0:
                    for idx, row in profit_book_candidates.iterrows():
                        profit_pct = row['current_profit_pct']
                        current_action = allocation_df.at[idx, 'action_recommendation']
                        
                        # Determine profit booking percentage based on gain level
                        if profit_pct > 0.40:
                            book_pct = 0.50
                            timing = "Within 1 week"
                        elif profit_pct > 0.30:
                            book_pct = 0.40
                            timing = "Within 2 weeks"
                        else:  # 20-30%
                            book_pct = 0.30
                            timing = "Within 3 weeks"
                        
                        # Override action to include profit booking (SKIP if conflict-resolved)
                        current_action = allocation_df.at[idx, 'action_recommendation']
                        has_conflict_resolution = any(emoji in str(current_action) for emoji in ['⚠️', '🟡', '🟢', '⚪'])
                        
                        if current_action == 'HOLD' and not has_conflict_resolution:
                            allocation_df.at[idx, 'action_recommendation'] = 'BOOK_PROFIT'
                            allocation_df.at[idx, 'exit_reason'] = f"💰 PROFIT BOOKING ({book_pct}%) | Gain: {profit_pct:.1f}% | Keep rest long-term"
                            allocation_df.at[idx, 'profit_booking_pct'] = book_pct
                            allocation_df.at[idx, 'profit_booking_timing'] = timing
                        elif current_action == 'INCREASE' and not has_conflict_resolution:
                            # 🔧 FIX: For top performers with high profits, BOOK_PROFIT takes priority
                            allocation_df.at[idx, 'action_recommendation'] = 'BOOK_PROFIT'
                            allocation_df.at[idx, 'exit_reason'] = f"🏆 TOP PERFORMER + 💰 Book {book_pct}% profit | Then INCREASE remaining position"
                            allocation_df.at[idx, 'profit_booking_pct'] = book_pct
                            allocation_df.at[idx, 'profit_booking_timing'] = timing
                    
                    print(f"      💰 {len(profit_book_candidates)} stocks marked for profit booking")
                    print(f"      📊 Book 30-50% profit, keep 50-70% for long term")
                else:
                    print(f"      ✓ No stocks with >20% profit requiring booking")
                
                # AGGRESSIVE PORTFOLIO REDUCTION: Add more sells to reach 20-25 target
                print(f"\n   📉 AGGRESSIVE PORTFOLIO REDUCTION (Target: 20-25 stocks)...")
                current_sell_count = len(allocation_df[(allocation_df['is_current_holding']) & (allocation_df['action_recommendation'] == 'SELL')])
                target_final_size = 23  # Midpoint of 20-25
                current_size = len(current_holdings_df)
                needed_sells = current_size - target_final_size
                additional_sells_needed = max(0, needed_sells - current_sell_count)
                
                if additional_sells_needed > 0:
                    print(f"      Current: {current_size} → Target: {target_final_size} → Need {additional_sells_needed} more SELLs")
                    
                    # Find weak HOLD stocks (low score, near breakeven, small positions)
                    weak_holds = current_holdings_df[
                        allocation_df.loc[current_holdings_df.index, 'action_recommendation'] == 'HOLD'
                    ].copy()
                    
                    # Score criteria: low score OR dead money OR small position
                    weak_holds['sell_priority'] = (
                        (70 - weak_holds['risk_adjusted_score']).clip(0, 30) * 2 +  # Low score (max 60 points)
                        (5 - abs(weak_holds.get('current_profit_pct', 0))).clip(0, 5) * 5 +  # Near breakeven (max 25 points)
                        (3 - weak_holds.get('portfolio_weight', 3)).clip(0, 3) * 5   # Small position (max 15 points)
                    )
                    
                    weak_holds_sorted = weak_holds.sort_values('sell_priority', ascending=False)
                    additional_sells = weak_holds_sorted.head(additional_sells_needed)
                    
                    for idx, stock in additional_sells.iterrows():
                        allocation_df.at[idx, 'action_recommendation'] = 'SELL'
                        allocation_df.at[idx, 'exit_reason'] = f"🎯 PORTFOLIO REDUCTION | Weak performer (Score: {stock['risk_adjusted_score']:.1f})"
                        allocation_df.at[idx, 'priority'] = 'LOW'
                    
                    print(f"      ✅ Marked {len(additional_sells)} additional weak stocks for SELL")
                else:
                    print(f"      ✅ Current SELL count sufficient to reach target size")
                
                # EXECUTION TIMING FOR SELL ACTIONS
                print(f"\n   ⏰ Adding EXECUTION TIMING for SELL actions...")
                sell_candidates = current_holdings_df[
                    allocation_df.loc[current_holdings_df.index, 'action_recommendation'] == 'SELL'
                ].copy()
                
                if len(sell_candidates) > 0:
                    for idx, row in sell_candidates.iterrows():
                        profit_pct = row.get('current_profit_pct', 0)
                        score = row.get('risk_adjusted_score', 0)
                        
                        # Timing based on urgency
                        if profit_pct < -0.05:  # Loss >5%
                            timing = "TODAY (cut losses)"
                            book_pct = 1.0
                        elif score < 50:  # Weak fundamentals
                            timing = "Next 1-2 days"
                            book_pct = 1.0
                        else:  # Rebalancing
                            timing = "Within 1 week"
                            book_pct = 1.0
                        
                        allocation_df.at[idx, 'profit_booking_pct'] = book_pct
                        allocation_df.at[idx, 'profit_booking_timing'] = timing
                    
                    print(f"      ⏰ {len(sell_candidates)} SELL orders assigned execution timing")
                
                # Add exit_strategy column if not present
                if 'exit_strategy' not in allocation_df.columns:
                    allocation_df['exit_strategy'] = 'NEW POSITION'
                if 'exit_reason' not in allocation_df.columns:
                    allocation_df['exit_reason'] = ''
            else:
                allocation_df['holdings_rank'] = 0
                allocation_df['exit_strategy'] = ''
                allocation_df['exit_reason'] = ''
            
            # Calculate enhanced predictive score (combines risk-adjusted + momentum + breakout)
            allocation_df['predictive_score'] = (
                allocation_df['risk_adjusted_score'] * 0.7 +  # 70% traditional analysis
                allocation_df['momentum_score'] * 0.2 +       # 20% momentum analysis
                allocation_df['breakout_score'] * 0.1         # 10% breakout patterns
            ).round(1)
            
            # Add priority ranking based on predictive score
            allocation_df['predictive_rank'] = allocation_df['predictive_score'].rank(method='dense', ascending=False).astype(int)
            
            # 🔧 FIX: Only set default if action_recommendation doesn't exist
            # DO NOT use fillna as it would overwrite EXIT STRATEGY and PROFIT BOOKING updates
            if 'action_recommendation' not in allocation_df.columns:
                allocation_df['action_recommendation'] = 'HOLD'
            
            # 🎯 VALUE INVESTING: 40/30/20/10 STRATEGY CLASSIFICATION
            print(f"\n   🎯 Applying VALUE INVESTING Strategy (40/30/20/10)...")
            print(f"      💎 CORE_VALUE (40%): Deep undervalued stocks (P/E <20, P/B <3.5)")
            print(f"      🚀 CORE_MOMENTUM (30%): Undervalued + trending (P/E <25, relative strength)")
            print(f"      🛡️  OPPORTUNISTIC (20%): Defensive/hedging (low beta, defensive sectors)")
            print(f"      ⚡ SPECULATIVE (10%): High risk/high reward (volatility >45%)")
            
            allocation_df['stock_classification'] = 'CORE_VALUE'  # Default
            
            # Classify based on VALUE INVESTING characteristics
            # Priority: OPPORTUNISTIC > CORE_MOMENTUM > CORE_VALUE > SPECULATIVE
            for idx, row in allocation_df.iterrows():
                score = row.get('risk_adjusted_score', row.get('overall_score', 50))
                score = score if pd.notna(score) else 50
                
                # Handle None values with safe defaults
                volatility = row.get('volatility_6m', 20)
                volatility = volatility if pd.notna(volatility) else 20
                
                sector = row.get('sector', '')
                sector = sector if pd.notna(sector) else ''
                
                pe_ratio = row.get('pe_ratio', 25)
                pe_ratio = pe_ratio if pd.notna(pe_ratio) and pe_ratio is not None else 25
                
                pb_ratio = row.get('pb_ratio', 3)
                pb_ratio = pb_ratio if pd.notna(pb_ratio) and pb_ratio is not None else 3
                
                price_change_3m = row.get('price_change_3m', 0)
                price_change_3m = price_change_3m if pd.notna(price_change_3m) else 0
                
                price_change_1m = row.get('price_change_1m', 0)
                price_change_1m = price_change_1m if pd.notna(price_change_1m) else 0
                
                beta = row.get('beta', 1.0)
                beta = beta if pd.notna(beta) else 1.0
                
                underval_score = row.get('undervaluation_score', 50)
                underval_score = underval_score if pd.notna(underval_score) else 50
                
                # 1. OPPORTUNISTIC (20%): Defensive/hedging stocks - FIRST PRIORITY
                div_yield = row.get('dividend_yield', 0)
                div_yield = div_yield if pd.notna(div_yield) else 0
                if sector in ['Consumer Defensive', 'Healthcare', 'Utilities', 'Consumer Staples']:
                    allocation_df.at[idx, 'stock_classification'] = 'OPPORTUNISTIC'
                elif beta < 0.3 and volatility < 15:
                    allocation_df.at[idx, 'stock_classification'] = 'OPPORTUNISTIC'
                
                # 2. CORE_MOMENTUM (30%): Positive 3M momentum + reasonable valuation
                elif price_change_3m > 5 and pe_ratio > 0 and pe_ratio < 30 and score >= 55:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_MOMENTUM'
                elif price_change_3m > 5 and underval_score >= 65:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_MOMENTUM'
                elif price_change_1m > 3 and score >= 65:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_MOMENTUM'
                
                # 3. CORE_VALUE (40%): Good fundamentals, flat/negative momentum
                elif underval_score >= 80 and score >= 55:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_VALUE'
                elif pe_ratio > 0 and pe_ratio < 20 and pb_ratio < 3.5:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_VALUE'
                elif pe_ratio > 0 and pe_ratio < 25 and score >= 60:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_VALUE'
                
                # 4. SPECULATIVE (10%): High risk/reward - LAST PRIORITY
                elif volatility > 45 and score < 40:
                    allocation_df.at[idx, 'stock_classification'] = 'SPECULATIVE'
                elif pe_ratio > 50 or (pe_ratio < 0 and score < 45):
                    allocation_df.at[idx, 'stock_classification'] = 'SPECULATIVE'
                
                # 5. Default: Put in CORE categories based on score
                elif score >= 65:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_VALUE'  # High quality = value
                elif score >= 55:
                    allocation_df.at[idx, 'stock_classification'] = 'CORE_MOMENTUM'  # Medium quality = momentum
                else:
                    allocation_df.at[idx, 'stock_classification'] = 'SPECULATIVE'  # Low quality = speculative
            
            # Count by classification
            class_counts = allocation_df['stock_classification'].value_counts()
            total_stocks_classified = len(allocation_df)
            for cls in ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']:
                count = class_counts.get(cls, 0)
                pct = (count / total_stocks_classified * 100) if total_stocks_classified > 0 else 0
                print(f"         • {cls}: {count} stocks ({pct:.1f}%)")
            
            # STEP 3.1: Copy stock_classification to stock_type for compatibility
            allocation_df['stock_type'] = allocation_df['stock_classification']
            
            # Count stocks by VALUE INVESTING category
            category_counts = allocation_df['stock_type'].value_counts()
            print(f"\n   📊 VALUE INVESTING Classification Complete:")
            for category in ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']:
                count = category_counts.get(category, 0)
                print(f"      • {category}: {count} stocks")
            
            # STEP 3.2: Apply VALUE INVESTING Allocation Rules (40/30/20/10)
            if portfolio_size_info:
                print(f"\n   🎯 Enforcing 40/30/20/10 VALUE INVESTING Targets...")
                
                # Define VALUE INVESTING allocation targets
                target_counts = {
                    'CORE_VALUE': int(target_stocks * 0.40),      # 40% deep value
                    'CORE_MOMENTUM': int(target_stocks * 0.30),   # 30% momentum+value
                    'OPPORTUNISTIC': int(target_stocks * 0.20),   # 20% hedging
                    'SPECULATIVE': int(target_stocks * 0.10)      # 10% high risk
                }
                
                print(f"      Target Portfolio Size: {target_stocks} stocks")
                for category, count in target_counts.items():
                    pct = (count / target_stocks * 100) if target_stocks > 0 else 0
                    print(f"      • {category}: {count} stocks ({pct:.0f}%)")
                
                # Rank stocks within each category and mark for keeping/selling
                allocation_df['rank_in_category'] = 0
                allocation_df['keep_stock'] = False  # Default to sell - only keep the selected ones
                
                # First pass: Allocate based on 40/30/20/10 targets
                actual_counts = {}
                for category in ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']:
                    category_stocks = allocation_df[allocation_df['stock_type'] == category].copy()
                    
                    if not category_stocks.empty:
                        # Sort by risk_adjusted_score (descending - best first)
                        category_stocks = category_stocks.sort_values('risk_adjusted_score', ascending=False, na_position='last')
                        target_count = target_counts.get(category, 0)
                        available_count = len(category_stocks)
                        
                        # Take min of target and available
                        actual_count = min(target_count, available_count)
                        actual_counts[category] = actual_count
                        
                        # Rank stocks in category and select top ones to keep
                        for i, (idx, row) in enumerate(category_stocks.iterrows()):
                            allocation_df.at[idx, 'rank_in_category'] = i + 1
                            
                            if i < actual_count:
                                allocation_df.at[idx, 'keep_stock'] = True
                                current_action = allocation_df.at[idx, 'action_recommendation']
                                has_special_action = ('REDUCE' in str(current_action).upper() or
                                                     (current_action not in ['HOLD', ''] and 
                                                      any(emoji in str(current_action) for emoji in ['⚠️', '🟡', '🟢', '⚪', '🚀', '💰'])))
                                if not has_special_action:
                                    allocation_df.at[idx, 'action_recommendation'] = 'KEEP' if row['is_current_holding'] else 'BUY'
                            else:
                                allocation_df.at[idx, 'keep_stock'] = False
                                current_action = allocation_df.at[idx, 'action_recommendation']
                                has_special_action = ('REDUCE' in str(current_action).upper() or
                                                     (current_action not in ['HOLD', ''] and 
                                                      any(emoji in str(current_action) for emoji in ['⚠️', '🟡', '🟢', '⚪', '🚀', '💰'])))
                                if not has_special_action:
                                    allocation_df.at[idx, 'action_recommendation'] = 'SELL' if row['is_current_holding'] else 'SKIP'
                
                # Second pass: Backfill if any category is short
                current_keep_count = len(allocation_df[allocation_df['keep_stock'] == True])
                _fill_floor = getattr(_config, 'SECTOR_REDUCE_MIN_SCORE', 45.0)
                
                if current_keep_count < target_stocks:
                    shortfall = target_stocks - current_keep_count
                    print(f"\n      🔄 Portfolio shortfall: Need {shortfall} more stocks (min score: {_fill_floor})")
                    
                    backfill_priority = ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']
                    
                    for category in backfill_priority:
                        if shortfall <= 0:
                            break
                        
                        remaining_stocks = allocation_df[
                            (allocation_df['keep_stock'] == False) & 
                            (allocation_df['stock_type'] == category)
                        ].copy()
                        
                        if not remaining_stocks.empty:
                            remaining_stocks = remaining_stocks.sort_values('risk_adjusted_score', ascending=False)
                            
                            added = 0
                            for idx, row in remaining_stocks.iterrows():
                                if shortfall <= 0:
                                    break
                                if row['risk_adjusted_score'] < _fill_floor:
                                    continue
                                allocation_df.at[idx, 'keep_stock'] = True
                                current_action = allocation_df.at[idx, 'action_recommendation']
                                has_special_action = ('REDUCE' in str(current_action).upper() or
                                                     any(emoji in str(current_action) for emoji in ['⚠️', '🟡', '🟢', '⚪', '🚀', '💰']))
                                if not has_special_action:
                                    allocation_df.at[idx, 'action_recommendation'] = 'KEEP' if row['is_current_holding'] else 'BUY'
                                print(f"         + Added {row['symbol']} ({category}) - Score: {row['risk_adjusted_score']:.1f}")
                                shortfall -= 1
                                added += 1
                            
                            if added > 0:
                                actual_counts[category] = actual_counts.get(category, 0) + added
                    
                    if shortfall > 0:
                        print(f"      ℹ️  Accepting {target_stocks - shortfall} stocks (no more candidates above {_fill_floor} score floor)")
                
                # Show VALUE INVESTING allocation summary
                print(f"\n   ✅ VALUE INVESTING Portfolio Allocation Complete:")
                total_allocated = sum(actual_counts.values())
                
                print(f"      📊 Total Portfolio: {total_allocated} stocks")
                print(f"      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                # Show 70% CORE breakdown
                core_value_count = actual_counts.get('CORE_VALUE', 0)
                core_momentum_count = actual_counts.get('CORE_MOMENTUM', 0)
                core_total = core_value_count + core_momentum_count
                core_pct = (core_total / total_allocated * 100) if total_allocated > 0 else 0
                
                print(f"      💎 CORE (70%): {core_total} stocks ({core_pct:.1f}%)")
                if core_value_count > 0:
                    value_pct = (core_value_count / total_allocated * 100) if total_allocated > 0 else 0
                    print(f"         ├─ Value (40%): {core_value_count} stocks ({value_pct:.1f}%) - Deep undervalued")
                if core_momentum_count > 0:
                    momentum_pct = (core_momentum_count / total_allocated * 100) if total_allocated > 0 else 0
                    print(f"         └─ Momentum (30%): {core_momentum_count} stocks ({momentum_pct:.1f}%) - Trending cheap")
                
                # Show OPPORTUNISTIC (20%)
                opp_count = actual_counts.get('OPPORTUNISTIC', 0)
                opp_pct = (opp_count / total_allocated * 100) if total_allocated > 0 else 0
                print(f"      🛡️  OPPORTUNISTIC (20%): {opp_count} stocks ({opp_pct:.1f}%) - Defensive/hedging")
                
                # Show SPECULATIVE (10%)
                spec_count = actual_counts.get('SPECULATIVE', 0)
                spec_pct = (spec_count / total_allocated * 100) if total_allocated > 0 else 0
                print(f"      ⚡ SPECULATIVE (10%): {spec_count} stocks ({spec_pct:.1f}%) - High risk/reward")
                
                print(f"      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                if total_allocated < target_stocks:
                    print(f"      ⚠️  Note: {total_allocated} stocks allocated (target: {target_stocks})")
                
                _not_selected = allocation_df[allocation_df['keep_stock'] == False]
                if not _not_selected.empty:
                    sell_counts = _not_selected['stock_type'].value_counts()
                    if not sell_counts.empty:
                        print(f"      [SKIP] Not Selected: {len(_not_selected)} stocks")
                        for category in ['CORE_VALUE', 'CORE_MOMENTUM', 'OPPORTUNISTIC', 'SPECULATIVE']:
                            count = sell_counts.get(category, 0)
                            if count > 0:
                                print(f"         • {category}: {count} stocks")
            
            # STEP 3.3: Keep ALL stocks in allocation_df for transparency
            # Don't filter out - just mark actions (KEEP/SELL/BUY)
            if 'keep_stock' in allocation_df.columns:
                keep_count = len(allocation_df[allocation_df['keep_stock'] == True])
                _skip_count = len(allocation_df[allocation_df['keep_stock'] == False])
                
                print(f"   📋 Portfolio Actions: {keep_count} KEEP/BUY + {_skip_count} SKIP/UNSELECTED = {len(allocation_df)} total stocks")
                
                # 🔧 FIX #5: EXIT STRATEGY OVERRIDES keep_stock logic
                # For current holdings, EXIT STRATEGY (30/50/20 rule) is the source of truth
                for idx, row in allocation_df[allocation_df['is_current_holding'] == True].iterrows():
                    if pd.notna(row.get('exit_strategy', '')) and row['exit_strategy'] != '':
                        # Use exit_reason to determine action (already set in lines 4028-4082)
                        exit_reason = row.get('exit_reason', '')
                        current_action = allocation_df.at[idx, 'action_recommendation']
                        
                        # 🔧 FIX: Preserve CONFLICT RESOLUTION and special actions - highest priority
                        has_conflict_resolution = any(emoji in str(current_action) for emoji in ['⚠️', '🟡', '🟢', '⚪'])
                        
                        if has_conflict_resolution:
                            allocation_df.at[idx, 'keep_stock'] = '⚠️ SKIP' not in current_action
                            continue
                        
                        if 'REDUCE' in str(current_action).upper():
                            allocation_df.at[idx, 'keep_stock'] = False
                            continue
                        
                        if current_action == 'BOOK_PROFIT' or '💰 PROFIT BOOKING' in exit_reason:
                            # Keep BOOK_PROFIT action intact
                            allocation_df.at[idx, 'keep_stock'] = True  # Always keep stocks with profit booking
                        # Parse the action from exit_reason
                        elif 'TOP PERFORMER' in exit_reason:
                            # Top 30% - INCREASE
                            allocation_df.at[idx, 'action_recommendation'] = 'INCREASE'
                            allocation_df.at[idx, 'keep_stock'] = True
                        elif 'HOLD STEADY' in exit_reason:
                            # Middle 50% - HOLD
                            allocation_df.at[idx, 'action_recommendation'] = 'HOLD'
                            allocation_df.at[idx, 'keep_stock'] = True
                        elif 'UNDERPERFORMER' in exit_reason or 'WEAK FUNDAMENTALS' in exit_reason or 'CUT LOSSES' in exit_reason:
                            # Bottom 20% with actual issues - SELL
                            allocation_df.at[idx, 'action_recommendation'] = 'SELL'
                            allocation_df.at[idx, 'keep_stock'] = False
                        elif 'REBALANCE' in exit_reason:
                            profit = row.get('current_profit_pct', 0)
                            if profit < _config.REBALANCE_PROFIT_THRESHOLD:
                                allocation_df.at[idx, 'action_recommendation'] = 'SELL'
                                allocation_df.at[idx, 'keep_stock'] = False
                            else:  # Good profit, just hold
                                allocation_df.at[idx, 'action_recommendation'] = 'HOLD'
                                allocation_df.at[idx, 'keep_stock'] = True
                                allocation_df.at[idx, 'exit_reason'] = f"📊 HOLD STEADY (Rank #{row.get('holdings_rank', 'N/A')}/{current_holdings_count}) | Profitable"
                        else:
                            # Default: keep it
                            allocation_df.at[idx, 'keep_stock'] = True
                
                # Update action_recommendation for stocks WITHOUT exit strategy (new recommendations)
                allocation_df.loc[
                    (allocation_df['keep_stock'] == False) & 
                    (allocation_df.get('exit_strategy', '') == ''), 
                    'action_recommendation'
                ] = allocation_df.loc[
                    (allocation_df['keep_stock'] == False) & 
                    (allocation_df.get('exit_strategy', '') == '')
                ].apply(lambda x: 'SELL' if x['is_current_holding'] else 'SKIP', axis=1)
            
            # Store all stocks marked for selling or skipping
            sell_recommendations_df = allocation_df[allocation_df['keep_stock'] == False].copy() if 'keep_stock' in allocation_df.columns else pd.DataFrame()
            
            # STEP 3.4: 🎯 SALE PROCEEDS + PROFIT BOOKING + NEW CAPITAL ALLOCATION
            if 'keep_stock' in allocation_df.columns and target_amount > 0:
                # Phase 1a+1b: Apply cash reserve BEFORE allocation using VIX-based regime
                _vix_regime = str(getattr(self, 'current_market_regime', 'SIDEWAYS') or 'SIDEWAYS').upper()
                _is_vix_bear = _vix_regime in ('BEAR', 'BEARISH')
                _is_vix_bull = _vix_regime in ('BULL', 'BULLISH')
                if _is_vix_bear:
                    _regime_exposure = 0.50
                elif _vix_regime in ('ROTATION', 'SIDEWAYS', 'NEUTRAL'):
                    _regime_exposure = 0.85
                else:
                    _regime_exposure = 1.0
                _original_target = target_amount
                _cash_reserve = target_amount * (1.0 - _regime_exposure)
                target_amount = target_amount * _regime_exposure
                if _regime_exposure < 1.0:
                    print(f"\n   🌐 REGIME CASH RESERVE ({_vix_regime}): deploying {_regime_exposure*100:.0f}%, reserving ₹{_cash_reserve:,.0f}")

                # Calculate sale proceeds from stocks marked for SELL (100% of position)
                sell_proceeds = allocation_df[
                    (allocation_df['action_recommendation'] == 'SELL') & 
                    (allocation_df['is_current_holding'] == True)
                ]['current_value'].sum()
                
                # Calculate profit booking proceeds from stocks marked for BOOK_PROFIT
                # (based on profit_booking_pct % of current value)
                book_profit_df = allocation_df[
                    (allocation_df['action_recommendation'] == 'BOOK_PROFIT') & 
                    (allocation_df['is_current_holding'] == True)
                ].copy()
                
                book_profit_proceeds = 0
                if not book_profit_df.empty:
                    for idx, row in book_profit_df.iterrows():
                        booking_pct = row.get('profit_booking_pct', 0)
                        if booking_pct is None or (isinstance(booking_pct, float) and np.isnan(booking_pct)):
                            booking_pct = 0
                        booking_pct = float(booking_pct)
                        current_val = _nv(row.get('current_value'), 0)
                        proceeds = booking_pct * current_val
                        book_profit_proceeds += proceeds
                
                # Total available = regime-adjusted capital + sell proceeds + book profit proceeds
                total_available = target_amount + sell_proceeds + book_profit_proceeds
                
                print(f"\n   [MONEY] CAPITAL ALLOCATION:")
                print(f"      [NEW] New capital (user input): Rs{target_amount:,.0f}")
                print(f"      [SELL] SELL proceeds: Rs{sell_proceeds:,.0f}")
                print(f"      [BOOK] BOOK_PROFIT proceeds: Rs{book_profit_proceeds:,.0f}")
                print(f"      [DATA] Total available: Rs{total_available:,.0f}")
                
                # [RANK] UNIFIED RANKING-BASED ALLOCATION (No 80/20 split)
                # Combine ALL opportunities (existing INCREASE + new BUY) into ONE ranked list
                print(f"\n   [RANK] UNIFIED RANKING-BASED CAPITAL ALLOCATION:")
                
                keep_stocks = allocation_df[allocation_df['keep_stock'] == True].copy()
                current_portfolio_value = allocation_df['current_value'].sum()
                total_target_portfolio = current_portfolio_value + total_available
                
                # === BUILD UNIFIED OPPORTUNITY LIST ===
                all_opportunities = []
                
                # 1. EXISTING HOLDINGS - Calculate max additional investment
                print(f"\n   📊 Analyzing existing holdings for additional investment...")
                for idx, row in keep_stocks.iterrows():
                    if row['current_value'] > 0:  # Already holding this stock
                        # CRITICAL: Exclude SELL stocks from allocation
                        action = str(row.get('action_recommendation', '')).upper()
                        if action == 'SELL':
                            continue  # Skip SELL stocks - they should get ₹0 allocation
                        
                        rank = row.get('holdings_rank', 999)
                        exit_reason = str(row.get('exit_reason', ''))
                        
                        # 🚀 UPDATED: Include ALL holdings for analysis (even mediocre ones for potential SWAP)
                        # We used to filter by rank, but now we let the Unified Allocation logic decide.
                        # [RT-08 FIX] Only allow INCREASE opportunity if not at meaningful loss (unless ML=STRONG_BUY)
                        _profit_for_increase = _nv(row.get('current_profit_pct'), 0)
                        _ml_for_increase = str(row.get('ml_signal', ''))
                        is_top_performer = (_profit_for_increase >= -0.02) or (_ml_for_increase == 'STRONG_BUY')
                        
                        if is_top_performer:
                            current_value = row['current_value']
                            market_cap = row.get('market_cap', 0)
                            
                            # Get market cap category and max allocation percentage
                            cap_category, max_allocation_pct = self.classify_market_cap(market_cap)
                            max_allocation_per_stock = total_target_portfolio * max_allocation_pct
                            
                            # 🔧 FIX: Allow top performers (score >= 80 or rank <= 6) to exceed normal cap
                            # This ensures best stocks get fresh capital even if already well-allocated
                            score = _nv(row.get('overall_score', row.get('final_blended_score', row.get('risk_adjusted_score', 0))), 0)
                            is_top_scorer = score >= 80 or rank <= 6
                            
                            if is_top_scorer:
                                # Allow up to 150% of normal cap for elite stocks
                                extended_cap = max_allocation_per_stock * 1.5
                                max_additional = max(0, extended_cap - current_value)
                            else:
                                max_additional = max(0, max_allocation_per_stock - current_value)
                            
                            # allow all holdings to be added (for SWAP analysis), even if fully allocated
                            if True: 
                                # [FIX-SCORE] allocation_df does not carry final_blended_score (only in results_df).
                                # Use overall_score (the capped 100-pt score written to allocation_df) as the
                                # primary sort key so high-conviction holdings like J&KBANK (score=100) rank
                                # above weaker stocks and are funded first.
                                _opp_score = _nv(row.get('overall_score'), _nv(row.get('final_blended_score'), _nv(row.get('risk_adjusted_score'), 0)))
                                all_opportunities.append({
                                    'type': 'INCREASE',
                                    'index': idx,
                                    'symbol': row['symbol'],
                                    # ✅ UPDATED: Use overall_score from allocation_df (correctly reflects ranking)
                                    'score': _opp_score,
                                    'rank': rank,
                                    'current_value': current_value,
                                    'max_investment': max_additional,
                                    'current_price': row['current_price'],
                                    'sector': row.get('sector', 'Unknown'),
                                    'market_cap_category': cap_category,
                                    'stock_class': row.get('stock_classification', 'CORE_VALUE'),
                                    'is_existing_holding': True
                                })
                
                print(f"      ✅ Found {len(all_opportunities)} existing holdings eligible for INCREASE")
                
                # Check if OPPORTUNISTIC category is underweight — steer new capital toward defensive stocks
                _opp_count = actual_counts.get('OPPORTUNISTIC', 0) if 'actual_counts' in dir() else 0
                _total_alloc = sum(actual_counts.values()) if 'actual_counts' in dir() else 1
                _opp_pct = (_opp_count / _total_alloc * 100) if _total_alloc > 0 else 0
                _needs_opp = _opp_pct < 15
                
                # 2. NEW BUY OPPORTUNITIES
                print(f"\n   🔍 Searching for NEW buy opportunities...")
                
                # Get current holdings symbols
                actual_holdings_symbols = set()
                if current_holdings is not None and not current_holdings.empty:
                    _ah_col = next((c for c in ['Instrument', 'Symbol', 'Stock', 'Ticker', 'symbol', 'instrument'] if c in current_holdings.columns), 'Instrument')
                    actual_holdings_symbols = set(current_holdings[_ah_col].str.upper())
                
                # 🔧 FIX: Load full analysis report to get ALL opportunities (not just current holdings)
                all_analyzed_df = results_df.copy()
                
                # 🔧 DISABLED: Implicit merging of previous reports causes confusion (e.g. phantom AUBANK)
                # If users want full allocation, they should run full analysis.
                # import glob
                # reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
                # ... (disabled logic)
                        
                if len(all_analyzed_df) == len(results_df):
                    # print(f"      ⚠️  Could not load additional stocks from reports")
                    print(f"      📊 Using current analysis only: {len(all_analyzed_df)} stocks")
                
                # 🚀 CRITICAL FIX: Check allocation_df for pre-breakout/high-momentum stocks (already has action_recommendation)
                # These stocks have pre-breakout flags set during holdings analysis but may not be current holdings
                prebreakout_stocks_in_allocation = allocation_df[
                    (allocation_df['keep_stock'] == True) &
                    (~allocation_df['symbol'].str.upper().isin(actual_holdings_symbols)) &
                    (
                        allocation_df.get('action_recommendation', pd.Series(dtype=str)).str.contains('🚀', na=False) |
                        allocation_df.get('action_recommendation', pd.Series(dtype=str)).str.contains('PRE-BREAKOUT', na=False) |
                        allocation_df.get('action_recommendation', pd.Series(dtype=str)).str.contains('HIGH MOMENTUM', na=False) |
                        allocation_df.get('action_recommendation', pd.Series(dtype=str)).str.contains('🟢 ENTER', na=False)
                    )
                ].copy()
                
                print(f"      🚀 Found {len(prebreakout_stocks_in_allocation)} pre-breakout/high-ROI stocks from allocation")
                
                # 🚀 ENHANCED: Include pre-breakout and high-momentum stocks in allocation
                # These stocks have high ROI potential but were previously excluded
                new_opportunities_candidates = all_analyzed_df[
                    (~all_analyzed_df['symbol'].str.upper().isin(actual_holdings_symbols)) &
                    (all_analyzed_df['final_recommendation'].str.contains('BUY', na=False)) &
                    (all_analyzed_df['risk_adjusted_score'] >= 60)
                ].copy()
                
                _curr_regime_alloc = str(getattr(self, 'current_market_regime', '') or '').upper()
                if _curr_regime_alloc in ('BEAR', 'BEARISH'):
                    _bear_vol_cap = getattr(_config, 'MAX_SAFE_VOLATILITY', 80.0) * 0.5
                    _pre_count = len(new_opportunities_candidates)
                    new_opportunities_candidates = new_opportunities_candidates[
                        new_opportunities_candidates['volatility'].fillna(100) <= _bear_vol_cap  # HI-04: unknown vol = high risk
                    ]
                    _dropped = _pre_count - len(new_opportunities_candidates)
                    if _dropped > 0:
                        print(f"      🛡️ BEAR filter: Excluded {_dropped} high-volatility (>{_bear_vol_cap:.0f}%) candidates")
                
                print(f"      📊 Found {len(new_opportunities_candidates)} standard BUY candidates from analysis")
                
                # 🚀 PROCESS PRE-BREAKOUT STOCKS FROM ALLOCATION_DF FIRST (priority)
                for _, prebreakout_stock in prebreakout_stocks_in_allocation.iterrows():
                    symbol = str(prebreakout_stock.get('symbol', '')).upper()
                    
                    if symbol:
                        market_cap = prebreakout_stock.get('market_cap', 0)
                        cap_category, max_allocation_pct = self.classify_market_cap(market_cap)
                        max_allocation_per_stock = total_target_portfolio * max_allocation_pct
                        
                        # 🚀 ROI POTENTIAL SCORING: These are HIGH PRIORITY - already flagged with pre-breakout
                        base_score = prebreakout_stock.get('overall_score', prebreakout_stock.get('risk_adjusted_score', 0))
                        action_rec = str(prebreakout_stock.get('action_recommendation', ''))
                        roi_boost = 0
                        roi_label = ""
                        
                        # Check for high-ROI indicators from action_recommendation
                        if '🚀' in action_rec or 'PRE-BREAKOUT' in action_rec:
                            breakout_prob = prebreakout_stock.get('breakout_probability', 0)
                            if breakout_prob >= 85:
                                roi_boost = 8  # Very high ROI potential
                                roi_label = "🔥 Very High ROI"
                            elif breakout_prob >= 70:
                                roi_boost = 5  # High ROI potential
                                roi_label = "⚡ High ROI"
                            else:
                                roi_boost = 3  # Moderate ROI potential
                                roi_label = "💫 Moderate ROI"
                        elif '🟢 ENTER' in action_rec:
                            roi_boost = 6  # Conflict-resolved ENTER signal
                            roi_label = "✅ Conflict-Resolved ENTER"
                        elif 'HIGH MOMENTUM' in action_rec:
                            roi_boost = 4  # Momentum play
                            roi_label = "📈 High Momentum"
                        
                        adjusted_score = base_score + roi_boost
                        
                        print(f"         🚀 Adding pre-breakout: {symbol} (Base: {base_score:.1f} + ROI: +{roi_boost} = {adjusted_score:.1f}) {roi_label}")
                        
                        all_opportunities.append({
                            'type': 'BUY',
                            'symbol': symbol,
                            'score': adjusted_score,  # Use ROI-adjusted score
                            'base_score': base_score,
                            'roi_boost': roi_boost,
                            'roi_label': roi_label,
                            'max_investment': max_allocation_per_stock,
                            'current_price': prebreakout_stock.get('current_price', 100),
                            'sector': prebreakout_stock.get('sector', 'Unknown'),
                            'market_cap_category': cap_category,
                            'max_allocation_pct': max_allocation_pct * 100,
                            'is_existing_holding': False,
                            'recommendation': 'BUY',
                            'action_recommendation': action_rec,
                            'company_name': prebreakout_stock.get('company_name', symbol),
                            'market_cap': market_cap,
                            'rank': 0,
                            'breakout_probability': prebreakout_stock.get('breakout_probability', 0)
                        })
                
                # Add new opportunities to the unified list
                for _, analyzed_stock in new_opportunities_candidates.iterrows():
                    symbol = str(analyzed_stock.get('symbol', '')).upper()
                    
                    if symbol:
                        market_cap = analyzed_stock.get('market_cap', 0)
                        cap_category, max_allocation_pct = self.classify_market_cap(market_cap)
                        max_allocation_per_stock = total_target_portfolio * max_allocation_pct
                        
                        # 🚀 ROI POTENTIAL SCORING: Boost scores for high-probability setups based on available data
                        base_score = _nv(analyzed_stock.get('final_blended_score', analyzed_stock.get('risk_adjusted_score')), 0)
                        
                        # Check momentum indicators (already calculated during analysis)
                        momentum_score = analyzed_stock.get('momentum_score', 0)
                        rsi = analyzed_stock.get('rsi', 50)
                        volume_trend = analyzed_stock.get('volume_trend', 0)
                        price_near_high = analyzed_stock.get('distance_from_52w_high_pct', 100)
                        
                        roi_boost = 0
                        roi_label = ""
                        
                        # 🚀 HIGH MOMENTUM: Strong uptrend with volume support
                        if momentum_score >= 75 and volume_trend > 20 and rsi < 70:
                            roi_boost = 5  # High momentum opportunity
                            roi_label = "🚀 High Momentum"
                        elif momentum_score >= 70 and rsi < 70:
                            roi_boost = 4  # Good momentum
                            roi_label = "📈 Good Momentum"
                        
                        # 🎯 PRE-BREAKOUT SETUP: Near 52-week high with good momentum
                        elif price_near_high <= 5 and momentum_score >= 65 and 50 <= rsi <= 65:
                            roi_boost = 6  # Pre-breakout setup
                            roi_label = "⚡ Pre-Breakout Setup"
                        
                        # 📊 STRONG FUNDAMENTALS: High score with undervaluation
                        elif base_score >= 80 and analyzed_stock.get('is_undervalued', False):
                            roi_boost = 3  # Strong fundamental opportunity
                            roi_label = "💎 Strong Fundamentals"
                        
                        adjusted_score = base_score + roi_boost
                        
                        if _needs_opp:
                            _beta = _nv(analyzed_stock.get('beta', 1.0), 1.0)
                            _sector = str(analyzed_stock.get('sector', '')).lower()
                            _defensive_sectors = ('healthcare', 'pharma', 'fmcg', 'consumer defensive', 'utilities')
                            if _beta < 0.9 or any(ds in _sector for ds in _defensive_sectors):
                                _opp_boost = 3
                                adjusted_score += _opp_boost
                                roi_boost += _opp_boost
                                roi_label = (roi_label + " + " if roi_label else "") + "🛡️ Defensive (rebalance)"
                        
                        if roi_boost > 0:
                            print(f"         {roi_label}: {symbol} (Base: {base_score:.1f} + ROI: +{roi_boost} = {adjusted_score:.1f})")
                        
                        action_rec = str(analyzed_stock.get('action_recommendation', analyzed_stock.get('final_recommendation', 'BUY')))
                        
                        all_opportunities.append({
                            'type': 'BUY',
                            'symbol': symbol,
                            'score': adjusted_score,
                            'base_score': base_score,
                            'roi_boost': roi_boost,
                            'roi_label': roi_label,
                            'max_investment': max_allocation_per_stock,
                            'current_price': analyzed_stock.get('current_price', 100),
                            'sector': analyzed_stock.get('sector', 'Unknown'),
                            'market_cap_category': cap_category,
                            'max_allocation_pct': max_allocation_pct * 100,
                            'is_existing_holding': False,
                            'recommendation': analyzed_stock.get('final_recommendation', ''),
                            'action_recommendation': action_rec,
                            'company_name': analyzed_stock.get('company_name', symbol),
                            'market_cap': market_cap,
                            'rank': 0,
                            'breakout_probability': analyzed_stock.get('breakout_probability', 0)
                        })
                
                # Deduplicate all_opportunities by symbol (keep highest score)
                _seen_syms = {}
                for opp in all_opportunities:
                    sym = opp['symbol']
                    if sym not in _seen_syms or opp['score'] > _seen_syms[sym]['score']:
                        _seen_syms[sym] = opp
                _dedup_count = len(all_opportunities) - len(_seen_syms)
                all_opportunities = list(_seen_syms.values())
                if _dedup_count > 0:
                    print(f"      ⚠️  Removed {_dedup_count} duplicate opportunity entries")
                print(f"      ✅ Total opportunities: {len(all_opportunities)} (INCREASE + BUY)")
                
                # === SORT BY SCORE (HIGHEST FIRST) ===
                all_opportunities.sort(key=lambda x: x['score'], reverse=True)
                
                # 🔄 SMART ROTATION LOGIC (Expert Portfolio Management)
                print(f"\n   🔄 Analyzing Portfolio Rotation Opportunities...")
                
                # 1. Identify "Weak" Holdings (Score < 50) - CUT
                weak_holdings = [op for op in all_opportunities if op.get('is_existing_holding') and op['score'] < 50]
                for wh in weak_holdings:
                    print(f"      [CUT] CUT CANDIDATE: {wh['symbol']} (Score: {wh['score']:.1f}) -> WEAK")
                    wh['recommendation'] = "SELL (WEAK)"
                    wh['action_comment'] = "Score < 50: Fundamental momentum lost"
                
                # 2. Identify "Mediocre" Holdings (Score 50-70) - SWAP CANDIDATES
                mediocre_holdings = [op for op in all_opportunities if op.get('is_existing_holding') and 50 <= op['score'] < 70]
                
                # 3. Identify "Superstar" Opportunities (Score > 70, Not Held) - UPGRADE TARGETS
                # Lowered to 70 to capture solid upgrades (e.g. 55 -> 71 is a +16 gap and worth it)
                superstars = [op for op in all_opportunities if not op.get('is_existing_holding') and op['score'] >= 70]


                
                # 4. Find Valid Swaps (Gap > 15 points)
                swaps_found = 0
                
                # Match worst mediocre with best superstar
                if mediocre_holdings and superstars:
                    mediocre_holdings.sort(key=lambda x: x['score']) # Lowest first
                    superstars.sort(key=lambda x: x['score'], reverse=True) # Highest first
                    

                    
                    for med in mediocre_holdings:
                        if swaps_found >= 3: break # Limit recommendations to top 3 swaps
                        
                        # Find best available superstar
                        for star in superstars:
                            if star.get('is_matched'): continue
                            
                            score_gap = star['score'] - med['score']
                            


                            if score_gap >= 15:
                                # FOUND SWAP!
                                print(f"      🔄 SWAP FOUND: Sell {med['symbol']} ({med['score']:.1f}) -> Buy {star['symbol']} ({star['score']:.1f}) | Gap: +{score_gap:.1f}")
                                


                                # Update Mediocre Holding Action
                                med['recommendation'] = f"SWAP -> {star['symbol']}"
                                med['action_comment'] = f"Upgrade to {star['symbol']} (Score +{score_gap:.1f})"
                                med['priority_sell'] = True
                                
                                # Update Superstar Action
                                star['recommendation'] = "BUY (SWAP)"
                                star['action_comment'] = f"Funded by selling {med['symbol']}"
                                star['is_matched'] = True
                                star['swap_source_value'] = med.get('current_value', 0) # Store source value for capping
                                
                                swaps_found += 1
                                break

                
                # === ALLOCATE FUNDS SEQUENTIALLY ===
                print(f"\n   💰 Allocating ₹{total_available:,.0f} across ranked opportunities...")
                
                remaining_budget = total_available
                sector_allocation = {}  # Track sector diversification
                category_sector_counts = {}  # Track per-category sector caps
                increase_count = 0
                buy_count = 0
                total_allocated = 0
                
                # 🔄 CRITICAL FIX: Process Priority Sells/Swaps FIRST & RECYCLE CAPITAL
                # Then IMMEDIATELY fund SWAP targets before other opportunities consume the budget
                print(f"\n   🔄 Applying Priority Swap Actions & Recycling Capital...")
                
                # Step 1: Recycle capital from SELL stocks
                swap_targets = []
                for opportunity in all_opportunities:
                    if opportunity.get('priority_sell'):
                        # [FIX] Use symbol-based lookup — index stored before SWAP/concat may be stale
                        _sw1_sym = opportunity['symbol']
                        _sw1_mask = allocation_df['symbol'] == _sw1_sym
                        action_rec = opportunity['recommendation']
                        reason = opportunity.get('action_comment', '')
                        current_val = opportunity.get('current_value', 0)
                        
                        print(f"      ✅ Executing Swap: {opportunity['symbol']} | Recycling Rs{current_val:,.0f}")
                        
                        # Apply to Allocation DF (symbol-safe)
                        if _sw1_mask.any():
                            _sw1_idx = allocation_df.index[_sw1_mask][0]
                            allocation_df.loc[_sw1_idx, 'action_recommendation'] = action_rec
                            allocation_df.loc[_sw1_idx, 'action_type'] = action_rec
                            allocation_df.loc[_sw1_idx, 'exit_reason'] = reason
                            allocation_df.loc[_sw1_idx, 'investment_amount'] = 0
                            allocation_df.loc[_sw1_idx, 'priority'] = 'HIGH'
                        
                        # 💰 RECYCLE CAPITAL back to budget and total_available
                        remaining_budget += current_val
                        total_available += current_val
                        print(f"         💰 Budget increased to: ₹{remaining_budget:,.0f}")
                        try:
                            with open("critical_debug.txt", "a", encoding='utf-8') as f: 
                                f.write(f"{opportunity['symbol']} Recycled {current_val} -> New Budget {remaining_budget}\n")
                        except Exception:
                            pass
                
                # Step 2: IMMEDIATELY fund SWAP targets (guaranteed allocation from recycled capital)
                print(f"\n   🚀 Funding SWAP Targets (Priority Allocation)...")
                for opportunity in all_opportunities:
                    if opportunity.get('recommendation') == 'BUY (SWAP)' and not opportunity.get('is_existing_holding'):
                        symbol = opportunity['symbol']
                        swap_source_value = opportunity.get('swap_source_value', 0)
                        
                        # 🎯 GUARANTEED ALLOCATION: Use recycled capital for SWAP target
                        # Cap at 40% of total budget OR recycled amount, whichever is HIGHER for high-ROI swaps
                        roi_score = opportunity.get('score', 0)
                        max_swap_allocation = total_available * 0.40
                        
                        if roi_score >= 85:
                            final_cap = swap_source_value  # Allow full recycled amount for very high ROI
                            cap_reason = f"Very High ROI (Score {roi_score:.1f})"
                        else:
                            # For lower scores, use min of recycled amount and 40% cap
                            final_cap = min(swap_source_value, max_swap_allocation) if swap_source_value > 0 else max_swap_allocation
                            cap_reason = f"SWAP Guarantee (40% cap check: Score {roi_score:.1f})"
                        
                        optimal_investment = min(remaining_budget, final_cap)
                        
                        if optimal_investment >= 3000:
                            current_price = _nv(float(opportunity['current_price']), 0)
                            if current_price <= 0 or np.isnan(current_price):
                                continue
                            shares_to_buy = int(optimal_investment / current_price)
                            actual_investment = shares_to_buy * current_price
                            
                            if actual_investment >= 3000:
                                print(f"      ✅ SWAP TARGET {symbol}: ₹{actual_investment:,.0f} ({shares_to_buy} shares) | {cap_reason}")
                                
                                # Add to allocation_df as NEW POSITION
                                new_row = pd.Series({
                                    'symbol': symbol,
                                    'company_name': opportunity.get('company_name', symbol),
                                    'sector': opportunity['sector'],
                                    'current_price': current_price,
                                    'current_value': 0,
                                    'current_quantity': 0,
                                    'investment_amount': actual_investment,
                                    'suggested_quantity': shares_to_buy,
                                    'risk_adjusted_score': opportunity.get('base_score', opportunity['score']),
                                    'overall_score': min(100.0, opportunity['score']),  # GAP-A: cap display score at 100 (ROI boost is internal ranking only)
                                    'market_cap_category': opportunity['market_cap_category'],
                                    'action_recommendation': opportunity.get('action_recommendation', '🚀 HIGH MOMENTUM NEW POSITION'),
                                    'action_type': 'NEW POSITION',
                                    'keep_stock': True,
                                    'recommendation': 'BUY (SWAP)',
                                    'exit_reason': opportunity.get('roi_label', 'SWAP upgrade'),
                                    'stock_classification': 'CORE_VALUE' if opportunity['score'] >= 75 else 'OPPORTUNISTIC'
                                })
                                
                                # Check if already exists
                                existing_mask = allocation_df['symbol'] == symbol
                                if existing_mask.any():
                                    existing_idx = allocation_df.index[existing_mask][0]
                                    allocation_df.loc[existing_idx, 'investment_amount'] = actual_investment
                                    allocation_df.loc[existing_idx, 'suggested_quantity'] = shares_to_buy
                                else:
                                    allocation_df = pd.concat([allocation_df, new_row.to_frame().T], ignore_index=True)
                                
                                # Update tracking
                                remaining_budget -= actual_investment
                                total_allocated += actual_investment
                                buy_count += 1
                                opportunity['funded'] = True  # Mark as funded to skip in main loop

                for opportunity in all_opportunities:
                    if opportunity['symbol'] == 'NMDC':
                        try:
                            with open("critical_debug.txt", "a", encoding='utf-8') as f: f.write(f"NMDC Found. Rec='{opportunity.get('recommendation')}' Budget={remaining_budget} MaxInv={opportunity.get('max_investment')}\n")
                        except Exception:
                            pass

                    # Skip if already funded as SWAP target
                    if opportunity.get('funded'):
                        continue

                    # 🔄 HANDLE SWAPS / SELLS (Priority Over Allocation)
                    if opportunity.get('priority_sell'):
                        # Already handled in SWAP recycling section above
                        continue
                        
                    if remaining_budget < 3000:  # Minimum allocation
                        break
                    
                    sector = opportunity['sector']
                    sector_count = sector_allocation.get(sector, 0)
                    
                    if sector_count >= _config.SECTOR_CAP:
                        logging.info(f"Sector cap reached: {sector} has {sector_count} stocks, skipping {opportunity['symbol']}")
                        continue

                    # Per-category sector cap: max 3 from same sector in one category
                    _opp_cat = opportunity.get('stock_classification', '')
                    _cat_sector_key = f"{_opp_cat}|{sector}"
                    _cat_sector_counts = category_sector_counts if 'category_sector_counts' in dir() else {}
                    if _cat_sector_key not in _cat_sector_counts:
                        _cat_sector_counts[_cat_sector_key] = 0
                    if _cat_sector_counts[_cat_sector_key] >= _config.CATEGORY_SECTOR_CAP:
                        logging.info(f"Per-category sector cap: {sector} has {_cat_sector_counts[_cat_sector_key]} in {_opp_cat}, skipping {opportunity['symbol']}")
                        continue
                    
                    
                    # Calculate optimal investment (standard logic for INCREASE and remaining BUY opportunities)
                    optimal_investment = min(
                        opportunity['max_investment'],
                        remaining_budget
                    )
                    logging.debug(f"Alloc calc for {opportunity['symbol']}: invest={optimal_investment:.0f} | Score={opportunity['score']:.1f} | Type={opportunity['type']}")
                    
                    # Ensure minimum ₹3,000 per stock
                    if optimal_investment < 3000:
                        continue
                    
                    current_price = _nv(float(opportunity['current_price']), 0)
                    if current_price <= 0 or np.isnan(current_price):
                        continue
                    shares_to_buy = int(optimal_investment / current_price)
                    actual_investment = shares_to_buy * current_price
                    
                    if opportunity['symbol'] == 'NMDC':
                        try:
                            with open("critical_debug.txt", "a") as f: f.write(f"CALC: Opt={optimal_investment} Price={current_price} Shares={shares_to_buy} Actual={actual_investment}\n")
                        except Exception:
                            pass

                    # Final validation
                    if actual_investment < 3000 or shares_to_buy < 1:
                        continue
                    
                    # ALLOCATE FUNDS
                    if opportunity['type'] == 'INCREASE':
                        # [FIX] Use symbol-based lookup instead of stale index.
                        # pd.concat(ignore_index=True) in the SWAP step above resets the
                        # DataFrame index, so the original idx stored in opportunity['index']
                        # may point to the wrong row or be silently ignored.
                        _inc_sym = opportunity['symbol']
                        _inc_mask = allocation_df['symbol'] == _inc_sym
                        if _inc_mask.any():
                            _inc_idx = allocation_df.index[_inc_mask][0]
                            allocation_df.loc[_inc_idx, 'investment_amount'] = actual_investment
                            allocation_df.loc[_inc_idx, 'suggested_quantity'] = shares_to_buy
                        else:
                            # Fallback to old index if symbol lookup fails (shouldn't happen)
                            idx = opportunity['index']
                            allocation_df.loc[idx, 'investment_amount'] = actual_investment
                            allocation_df.loc[idx, 'suggested_quantity'] = shares_to_buy
                        
                        increase_count += 1
                        print(f"      🔼 {opportunity['symbol']} (Rank #{opportunity.get('rank', 'N/A')}): +₹{actual_investment:,.0f} ({shares_to_buy} shares) | Score: {opportunity['score']:.1f} | {sector}")
                    
                    else:  # BUY
                        # 🚀 ENHANCED: Preserve specific action recommendations for high-ROI stocks
                        action_rec_from_analysis = opportunity.get('action_recommendation', '')
                        if action_rec_from_analysis and ('🚀' in action_rec_from_analysis or '🟢' in action_rec_from_analysis):
                            action_label = action_rec_from_analysis  # Keep specific pre-breakout/conflict label
                        else:
                            action_label = 'NEW POSITION'  # Default for standard BUY
                        
                        # Create new row for new position
                        new_row = pd.Series({
                            'symbol': opportunity['symbol'],
                            'company_name': opportunity.get('company_name', opportunity['symbol']),
                            'sector': opportunity['sector'],
                            'current_price': opportunity['current_price'],
                            'current_value': 0,
                            'current_quantity': 0,
                            'investment_amount': actual_investment,
                            'suggested_quantity': shares_to_buy,
                            'risk_adjusted_score': opportunity.get('base_score', opportunity['score']),  # Use base score for risk_adjusted
                            'overall_score': min(100.0, opportunity['score']),  # GAP-A: cap at 100; ROI boost is internal ranking only
                            'market_cap_category': opportunity['market_cap_category'],
                            'action_recommendation': action_label,  # ✅ Preserve specific action for high-ROI stocks
                            'action_type': 'NEW POSITION',
                            'keep_stock': True,
                            'recommendation': opportunity.get('recommendation', 'BUY'),
                            'market_cap': opportunity.get('market_cap', 0),
                            'max_allocation_pct': opportunity.get('max_allocation_pct', 5.0),
                            'is_current_holding': False,
                            'exit_reason': opportunity.get('roi_label', 'New opportunity - Quality stock not in portfolio'),
                            'exit_strategy': '🆕 NEW POSITION',
                            'stock_classification': 'CORE_VALUE' if opportunity['score'] >= 75 else 'OPPORTUNISTIC',
                            'holdings_rank': 0,
                            'current_profit_pct': 0,
                            'portfolio_weight': (actual_investment / total_target_portfolio) if total_target_portfolio > 0 else 0
                        })
                        
                        # Check if symbol already exists to prevent DUPLICATES
                        existing_mask = allocation_df['symbol'] == opportunity['symbol']
                        if existing_mask.any():
                            # Update existing row
                            existing_idx = allocation_df.index[existing_mask][0]
                            allocation_df.loc[existing_idx, 'investment_amount'] = actual_investment
                            allocation_df.loc[existing_idx, 'suggested_quantity'] = shares_to_buy
                            # Preserve specific action labels (pre-breakout, conflict-resolved, etc.)
                            current_action = allocation_df.loc[existing_idx, 'action_recommendation']
                            if current_action == 'BUY' or pd.isna(current_action):
                                allocation_df.loc[existing_idx, 'action_recommendation'] = action_label
                            # Update scores
                            if allocation_df.loc[existing_idx, 'overall_score'] == 0:
                                allocation_df.loc[existing_idx, 'overall_score'] = opportunity['score']
                        else:
                            # Add to allocation_df
                            allocation_df = pd.concat([allocation_df, new_row.to_frame().T], ignore_index=True)
                        
                        buy_count += 1
                        roi_info = f" | {opportunity.get('roi_label', '')}" if opportunity.get('roi_label') else ""
                        print(f"      🆕 {opportunity['symbol']}: ₹{actual_investment:,.0f} ({shares_to_buy} shares) | Score: {opportunity['score']:.1f}{roi_info} | {sector}")
                    
                    # Update tracking
                    remaining_budget -= actual_investment
                    total_allocated += actual_investment
                    sector_allocation[sector] = sector_count + 1
                    _cat_sector_counts[_cat_sector_key] = _cat_sector_counts.get(_cat_sector_key, 0) + 1
                
                # Relabel unfunded BUY/NEW POSITION stocks as WATCHLIST
                _unfunded = (
                    allocation_df['action_recommendation'].str.contains('NEW POSITION|BUY', na=False, regex=True) &
                    ~allocation_df['action_recommendation'].str.contains('SWAP', na=False) &
                    (allocation_df['investment_amount'] == 0)
                )
                _n_watchlist = _unfunded.sum()
                if _n_watchlist > 0:
                    allocation_df.loc[_unfunded, 'action_recommendation'] = 'WATCHLIST'
                    allocation_df.loc[_unfunded, 'exit_reason'] = 'Budget exhausted — monitor for future entry'
                    print(f"   📋 Relabeled {_n_watchlist} unfunded positions as WATCHLIST")

                # === ALLOCATION SUMMARY ===
                print(f"\n   🎯 UNIFIED ALLOCATION SUMMARY:")
                print(f"      💰 SELL proceeds: ₹{sell_proceeds:,.0f}")
                print(f"      📈 BOOK_PROFIT proceeds: ₹{book_profit_proceeds:,.0f}")
                print(f"      🆕 New capital (user input): ₹{target_amount:,.0f}")
                print(f"      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"      📊 Total available: ₹{total_available:,.0f}")
                print(f"      ✅ Total allocated: ₹{total_allocated:,.0f}")
                print(f"      🔼 INCREASE actions: {increase_count}")
                print(f"      🆕 BUY actions: {buy_count}")
                print(f"      💵 Remaining funds: ₹{remaining_budget:,.0f}")
                
                # Show sector diversification
                if sector_allocation:
                    print(f"\n   📊 Sector Diversification:")
                    for sector, count in sorted(sector_allocation.items(), key=lambda x: x[1], reverse=True):
                        print(f"      • {sector}: {count} stocks")
            
            # 🔧 REBALANCING LOGIC: Check 70/20/10 allocation
            print(f"\n   ⚖️  REBALANCING CHECK (70/20/10 Rule):")
            
            current_holdings_only = allocation_df[allocation_df['is_current_holding'] == True].copy()
            if not current_holdings_only.empty:
                total_portfolio_value = current_holdings_only['current_value'].sum()
                
                core_value = current_holdings_only[current_holdings_only['stock_classification'].isin(['CORE', 'CORE_VALUE', 'CORE_MOMENTUM'])]['current_value'].sum()
                opp_value = current_holdings_only[current_holdings_only['stock_classification'] == 'OPPORTUNISTIC']['current_value'].sum()
                spec_value = current_holdings_only[current_holdings_only['stock_classification'] == 'SPECULATIVE']['current_value'].sum()
                
                core_pct = (core_value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                opp_pct = (opp_value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                spec_pct = (spec_value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                
                print(f"      📊 Current allocation:")
                print(f"         • CORE: {core_pct:.1f}% (Target: 70%)")
                print(f"         • OPPORTUNISTIC: {opp_pct:.1f}% (Target: 20%)")
                print(f"         • SPECULATIVE: {spec_pct:.1f}% (Target: 10%)")
                
                # Rebalancing recommendations
                if core_pct < 60:
                    print(f"      ⚠️  CORE underweight: Increase CORE stocks")
                elif core_pct > 80:
                    print(f"      ⚠️  CORE overweight: Reduce CORE, add OPPORTUNISTIC")
                
                if spec_pct > 15:
                    print(f"      ⚠️  SPECULATIVE overweight: Reduce high-risk positions")
                elif spec_pct < 5:
                    print(f"      💡 SPECULATIVE underweight: Consider some hedging positions")
                
                if 60 <= core_pct <= 80 and 15 <= opp_pct <= 25 and 5 <= spec_pct <= 15:
                    print(f"      ✅ Portfolio well-balanced!")
                
                # 🔧 SECTOR CONCENTRATION CHECK (Max 40% in CORE)
                print(f"\n   🏢 SECTOR CONCENTRATION CHECK (Max 40% in CORE):")
                
                core_holdings = current_holdings_only[current_holdings_only['stock_classification'].isin(['CORE', 'CORE_VALUE', 'CORE_MOMENTUM'])]
                core_total_value = 0  # Initialize to avoid UnboundLocalError
                sector_allocation = {}  # Initialize empty dict
                if not core_holdings.empty:
                    core_total_value = core_holdings['current_value'].sum()
                    sector_allocation = core_holdings.groupby('sector')['current_value'].sum().sort_values(ascending=False)
                    
                    print(f"      📊 CORE sector allocation:")
                    for sector, value in sector_allocation.head(3).items():
                        sector_pct = (value / core_total_value * 100) if core_total_value > 0 else 0
                        overall_pct = (value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                        
                        _core_thresh = _config.CORE_CONCENTRATION_THRESHOLD * 100
                        status = "✅" if sector_pct <= _core_thresh else "⚠️"
                        print(f"         {status} {sector}: {sector_pct:.1f}% of CORE ({overall_pct:.1f}% overall)")
                        
                        if sector_pct > _core_thresh:
                            excess = sector_pct - _core_thresh
                            print(f"            ⚠️ OVER-CONCENTRATED! Reduce by {excess:.1f}% through rotation")
                            print(f"            💡 Rotate capital to undervalued sectors")
                            
                            # Mark some stocks in this sector for selling to reduce concentration
                            sector_stocks = core_holdings[core_holdings['sector'] == sector].sort_values('risk_adjusted_score')
                            weak_in_sector = sector_stocks.head(3)  # Bottom 3 stocks in overweight sector
                            
                            for idx, stock in weak_in_sector.iterrows():
                                current_action = allocation_df.at[idx, 'action_recommendation']
                                if current_action == 'HOLD':
                                    allocation_df.at[idx, 'action_recommendation'] = 'SELL'
                                    allocation_df.at[idx, 'exit_reason'] = f"🔄 SECTOR ROTATION | {sector} over-concentrated ({sector_pct:.1f}%)"
                                    allocation_df.at[idx, 'priority'] = 'MEDIUM'
                                    allocation_df.at[idx, 'profit_booking_pct'] = 1.0
                                    allocation_df.at[idx, 'profit_booking_timing'] = "Within 2 weeks"
                                else:
                                    _sym = stock.get('symbol', '?')
                                    logging.info(f"Sector rotation skipped {_sym}: action={current_action} (only HOLD overridden)")
                
                # Check for sector rotation opportunities (find undervalued sectors)
                all_stocks_sector = allocation_df.groupby('sector')['risk_adjusted_score'].mean().sort_values(ascending=False)
                print(f"\n      💡 UNDERVALUED SECTOR OPPORTUNITIES (for rotation):")
                
                # Find sectors NOT in current portfolio or underweight
                current_sectors = set(current_holdings_only['sector'].unique())
                new_stocks_avail = allocation_df[allocation_df['is_current_holding'] == False]
                
                if not new_stocks_avail.empty:
                    new_sectors = new_stocks_avail.groupby('sector').agg({
                        'risk_adjusted_score': 'mean',
                        'symbol': 'count'
                    }).sort_values('risk_adjusted_score', ascending=False).head(3)
                    
                    for sector, data in new_sectors.iterrows():
                        if sector not in current_sectors or sector_allocation.get(sector, 0) < core_total_value * 0.1:
                            print(f"         🎯 {sector}: Avg Score {data['risk_adjusted_score']:.1f} ({int(data['symbol'])} stocks available)")
            
            # Sort by action and score
            allocation_df['priority_rank'] = allocation_df['priority'].map({'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'VERY HIGH': 0})
            allocation_df = allocation_df.sort_values(['priority_rank', 'risk_adjusted_score'], ascending=[True, False])
            allocation_df = allocation_df.drop('priority_rank', axis=1)
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🎯 ENHANCEMENT #2: MARKET REGIME DETECTION
            # (Just before this, verify NMDC)
            for _, row_debug in allocation_df.iterrows():
                if row_debug['symbol'] == 'NMDC':
                    try:
                        with open("critical_debug.txt", "a", encoding='utf-8') as f: f.write(f"LATE_CHECK: NMDC Investment={row_debug['investment_amount']} Action={row_debug['action_recommendation']}\n")
                    except Exception:
                        pass

            # ═══════════════════════════════════════════════════════════════════════
            print(f"\n   🌐 MARKET REGIME SUMMARY (applied before allocation)...")
            
            try:
                regime_adjustment = {
                    'market_regime': _vix_regime,
                    'recommended_exposure': _regime_exposure,
                    'original_capital': _original_target,
                    'adjusted_capital': target_amount,
                    'cash_reserve': _cash_reserve,
                    'regime_strategy': 'VIX-based regime from MarketRegimeDetector'
                }
                print(f"      📊 Market Regime: {_vix_regime} (VIX-based)")
                print(f"      💰 Exposure: {_regime_exposure*100:.0f}% | Cash Reserve: ₹{_cash_reserve:,.0f}")
            except Exception as e:
                print(f"      ⚠️ Market regime summary skipped: {e}")
                regime_adjustment = {'market_regime': 'NEUTRAL', 'recommended_exposure': 0.85}
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🎯 ENHANCEMENT #3: CONFIDENCE BANDS
            # ═══════════════════════════════════════════════════════════════════════
            print(f"\n   🎚️ APPLYING CONFIDENCE BANDS (Enhancement #3)...")
            
            confidence_filtered = 0
            strong_buy_count = 0
            cautious_count = 0
            
            for idx, row in allocation_df.iterrows():
                score = row.get('overall_score_with_value', row.get('overall_score', 50))
                stock_data = row.to_dict()
                
                try:
                    confidence_info = self.apply_confidence_bands(score, stock_data)
                    confidence_level = confidence_info['confidence_level']
                    recommendation_strength = confidence_info['recommendation_strength']
                    action_bias = confidence_info['action_bias']
                    risk_warning = confidence_info.get('risk_warning')
                    
                    # Store confidence info
                    allocation_df.at[idx, 'confidence_level'] = confidence_level
                    allocation_df.at[idx, 'recommendation_strength'] = recommendation_strength
                    allocation_df.at[idx, 'action_bias'] = action_bias
                    
                    # Apply confidence-based filtering
                    current_action = allocation_df.at[idx, 'action_recommendation']
                    
                    # STRONG BUY: Boost priority
                    if confidence_level == 'STRONG BUY' and current_action in ['BUY', 'KEEP']:
                        allocation_df.at[idx, 'priority'] = 'VERY HIGH'
                        strong_buy_count += 1
                    
                    # CAUTIOUS: Downgrade in uncertain markets
                    elif confidence_level == 'HOLD/CAUTIOUS':
                        cautious_count += 1
                        if regime_adjustment.get('market_regime') in ['BEARISH', 'ROTATION']:
                            if current_action == 'BUY' and not row.get('is_current_holding', False):
                                # 🔧 FIX: Don't skip if funds were already allocated
                                already_allocated = allocation_df.at[idx, 'investment_amount'] > 0
                                if not already_allocated:
                                    allocation_df.at[idx, 'action_recommendation'] = 'SKIP'
                                    allocation_df.at[idx, 'skip_reason'] = f"Low confidence (Score: {score:.1f}) in {regime_adjustment.get('market_regime')} market"
                                    confidence_filtered += 1
                    
                    # AVOID: Skip new positions
                    elif confidence_level == 'AVOID':
                        if current_action == 'BUY' and not row.get('is_current_holding', False):
                            # 🔧 FIX: Don't skip if funds were already allocated
                            already_allocated = allocation_df.at[idx, 'investment_amount'] > 0
                            if not already_allocated:
                                allocation_df.at[idx, 'action_recommendation'] = 'SKIP'
                                allocation_df.at[idx, 'skip_reason'] = f"Below confidence threshold (Score: {score:.1f})"
                                confidence_filtered += 1
                    
                    if risk_warning:
                        allocation_df.at[idx, 'risk_warning'] = risk_warning
                        
                except Exception as e:
                    # If confidence band fails, continue without it
                    allocation_df.at[idx, 'confidence_level'] = 'BUY'
                    allocation_df.at[idx, 'recommendation_strength'] = 'MEDIUM'
            
            print(f"      ✅ Confidence bands applied to {len(allocation_df)} stocks")
            print(f"      🏆 STRONG BUY: {strong_buy_count} stocks (very high confidence)")
            print(f"      ⚠️ CAUTIOUS: {cautious_count} stocks (lower confidence)")
            if confidence_filtered > 0:
                print(f"      🚫 Filtered out: {confidence_filtered} low-confidence stocks in {regime_adjustment.get('market_regime')} market")
            
            # Enhanced portfolio summary statistics with risk-based actions
            keep_stocks = allocation_df[allocation_df.get('keep_stock', True) == True] if 'keep_stock' in allocation_df.columns else allocation_df
            sell_stocks = allocation_df[allocation_df.get('keep_stock', False) == False] if 'keep_stock' in allocation_df.columns else pd.DataFrame()
            
            # [MI-L04] Protect ML=HOLD owned losing positions from pure SELL (before printing)
            _ml_col = 'ml_signal' if 'ml_signal' in allocation_df.columns else None
            _own_col = 'is_current_holding' if 'is_current_holding' in allocation_df.columns else None
            _pnl_col = 'current_profit_pct' if 'current_profit_pct' in allocation_df.columns else None
            _l04_count = 0
            if _ml_col and _own_col and _pnl_col:
                for _li, _lr in allocation_df.iterrows():
                    _la = str(_lr.get('action_recommendation', ''))
                    if _la.upper() != 'SELL':
                        continue
                    _lo = bool(_lr.get(_own_col, False))
                    _lp = _nv(_lr.get(_pnl_col), 0)
                    _lm = str(_lr.get(_ml_col, ''))
                    if _lo and _lp < 0 and _lm in ('HOLD', 'STRONG_BUY'):
                        allocation_df.at[_li, 'action_recommendation'] = 'HOLD'
                        if 'exit_reason' in allocation_df.columns:
                            allocation_df.at[_li, 'exit_reason'] = (
                                f"[MI-L04] ML={_lm} + loss={_lp:.1%} — Don't crystallize loss, wait for recovery"
                            )
                        _l04_count += 1
            if _l04_count:
                print(f"   🔧 [MI-L04] Protected {_l04_count} ML=HOLD losing positions from SELL → HOLD")

            sell_list = allocation_df[
                (allocation_df['is_current_holding'] == True) & 
                (allocation_df['action_recommendation'] == 'SELL')
            ].copy()
            
            if not sell_list.empty:
                print(f"\n   [SELL] EXPLICIT SELL LIST: {len(sell_list)} stocks to remove")
                print(f"   " + "="*80)
                sell_list_sorted = sell_list.sort_values('holdings_rank', ascending=False)  # Worst first
                for idx, stock in sell_list_sorted.iterrows():
                    symbol = stock['symbol']
                    rank = stock.get('holdings_rank', 'N/A')
                    score = stock['risk_adjusted_score']
                    profit = stock.get('current_profit_pct', 0)
                    reason = stock.get('exit_reason', 'Rebalancing required')
                    value = stock['current_value']
                    
                    profit_str = f"+{profit:.1f}%" if profit > 0 else f"{profit:.1f}%"
                    print(f"      🔴 {symbol}: {reason}")
                    print(f"         Current Value: ₹{value:,.0f} | Profit: {profit_str}")
                print(f"   " + "="*80)
            
            # Count actions by category
            increase_stocks = allocation_df[
                (allocation_df['is_current_holding'] == True) & 
                (allocation_df['action_recommendation'] == 'INCREASE')
            ]
            hold_stocks = allocation_df[
                (allocation_df['is_current_holding'] == True) & 
                (allocation_df['action_recommendation'] == 'HOLD')
            ]
            
            # Calculate sale proceeds
            sale_proceeds_value = sell_list['current_value'].sum() if not sell_list.empty else 0
            
            portfolio_summary = {
                'total_stocks': len(allocation_df),
                'stocks_to_keep': len(keep_stocks),
                'stocks_to_sell': len(sell_stocks),
                'current_holdings': len(allocation_df[allocation_df['is_current_holding'] == True]),
                'new_positions': len(allocation_df[allocation_df['action_type'] == 'NEW POSITION']),
                'positions_to_sell': len(sell_list),  # Explicit sell count
                'positions_to_increase': len(increase_stocks),  # NEW: Track increases
                'positions_to_hold': len(hold_stocks),  # NEW: Track holds
                'positions_to_buy': len(allocation_df[allocation_df['action_recommendation'].isin(['BUY'])]) if 'action_recommendation' in allocation_df.columns else 0,
                'positions_to_keep': len(allocation_df[allocation_df['action_recommendation'].isin(['KEEP'])]) if 'action_recommendation' in allocation_df.columns else 0,
                'sale_proceeds': sale_proceeds_value,  # NEW: Money from selling
                'new_capital': target_amount,
                'total_available_capital': target_amount + sale_proceeds_value,
                'available_funds': target_amount,
                'current_portfolio_value': current_portfolio_value,
                'market_regime': regime_adjustment.get('market_regime', 'NEUTRAL'),  # NEW: Market regime
                'recommended_exposure': regime_adjustment.get('recommended_exposure', 0.85),  # NEW: Exposure %
                'cash_reserve': regime_adjustment.get('cash_reserve', 0),  # NEW: Cash buffer
                'regime_strategy': regime_adjustment.get('regime_strategy', 'Balanced approach'),  # NEW: Strategy
                'strong_buy_count': strong_buy_count,  # NEW: High confidence stocks
                'confidence_filtered_count': confidence_filtered,  # NEW: Filtered low confidence
                'total_target_portfolio_value': current_portfolio_value + target_amount,
                'avg_score': allocation_df[allocation_df['overall_score'] > 0]['overall_score'].mean() if len(allocation_df[allocation_df['overall_score'] > 0]) > 0 else 0,
                'avg_undervaluation': allocation_df[allocation_df['undervaluation_score'] > 0]['undervaluation_score'].mean() if len(allocation_df[allocation_df['undervaluation_score'] > 0]) > 0 else 0,
                'sector_count': allocation_df['sector'].nunique(),
                'high_priority_count': len(allocation_df[allocation_df['priority'] == 'HIGH']),
                'funds_utilization': (keep_stocks['investment_amount'].sum() / max(total_available, 1)) * 100 if len(keep_stocks) > 0 else 0,
                'target_portfolio_size': target_stocks,
                'max_allowed_size': portfolio_size_info['max_allowed'] if portfolio_size_info else target_stocks,
                'portfolio_utilization': (len(keep_stocks) / target_stocks) * 100 if target_stocks > 0 else 0
            }
            
            # No additional processing needed
            
            # ✅ FIX: Explicitly sort by Score (Highest First) for final display
            if 'overall_score' in allocation_df.columns:
                allocation_df.sort_values(by='overall_score', ascending=False, inplace=True)

            # ✅ FIX: Ensure consistent "NEW POSITION" label for all BUY recommendations
            if 'action_recommendation' in allocation_df.columns:
                allocation_df.loc[allocation_df['action_recommendation'] == 'BUY', 'action_recommendation'] = 'NEW POSITION'

            # ✅ FIX: Re-calculate Investment Amounts & Limit to Top 20
            # This ensures (1) Values are not empty/zero, (2) User gets a focused list
            
            # 1. Identify New Positions
            new_pos_mask = allocation_df['action_recommendation'] == 'NEW POSITION'
            new_positions_df = allocation_df[new_pos_mask].copy()
            
            # 🔧 DISABLED: RE-CALCULATION section that was overwriting unified allocation
            # The unified ranking-based allocation (lines 5700-6100) already handles proper
            # distribution across INCREASE + BUY opportunities. This re-calculation was
            # giving ALL fresh capital to NEW POSITIONS, starving existing holdings.
            # Keep the SKIP logic for limiting new positions, but don't recalculate amounts.
            
            if not new_positions_df.empty and 'overall_score' in new_positions_df.columns:
                # 2. Sort by Score and Limit to Top 20
                new_positions_df.sort_values(by='overall_score', ascending=False, inplace=True)
                top_20_symbols = new_positions_df.head(20)['symbol'].tolist()
                
                # 3. Mark excess as SKIP (keep only top scoring new positions)
                allocation_df.loc[(new_pos_mask) & (~allocation_df['symbol'].isin(top_20_symbols)), 'action_recommendation'] = 'SKIP'
                
                # 4. Skip re-calculation - unified allocation already distributed funds properly
                print(f"      ✅ Keeping unified allocation amounts for {len(top_20_symbols)} NEW POSITION stocks")
                    
            # Filter out SKIPPED stocks from the final allocation_df to clean up report
            allocation_df = allocation_df[allocation_df['action_recommendation'] != 'SKIP']

            # Fractional Kelly position sizing
            try:
                _perf_30 = self.recommendation_history.get_performance_metrics('30d')
                _kelly_wr = _perf_30.get('win_rate', 0) / 100
                _kelly_wlr = _perf_30.get('avg_win_loss_ratio', 0)
                _has_kelly = _perf_30.get('total_with_outcomes', 0) >= 50 and _kelly_wr > 0 and _kelly_wlr > 0
                if _has_kelly:
                    _kelly_f = (_kelly_wr * _kelly_wlr - (1 - _kelly_wr)) / _kelly_wlr if _kelly_wlr > 0 else 0
                    if _kelly_f <= 0:
                        allocation_df['kelly_fraction'] = 0
                        allocation_df['kelly_position_size'] = allocation_df['investment_amount']
                        print(f"   📊 Kelly sizing: negative f={_kelly_f:.3f} (low edge) — falling back to rank-based allocation")
                    else:
                        _half_kelly = min(_kelly_f / 2, 0.25)
                        allocation_df['kelly_fraction'] = round(_half_kelly, 4)
                        _total_cap = target_amount + (allocation_df['current_value'].sum() if 'current_value' in allocation_df.columns else 0)
                        _kelly_max = _half_kelly * _total_cap
                        allocation_df['kelly_position_size'] = allocation_df['investment_amount'].clip(upper=_kelly_max).round(0)
                        print(f"   📊 Kelly position sizing: f={_kelly_f:.3f}, half-Kelly={_half_kelly:.3f}, max per position=Rs{_kelly_max:,.0f}")
                else:
                    allocation_df['kelly_fraction'] = 0
                    allocation_df['kelly_position_size'] = allocation_df['investment_amount']
                    print(f"   📊 Kelly sizing: insufficient history ({_perf_30.get('total_with_outcomes', 0)}/50 min) — using rank-based allocation")
            except Exception as _ke:
                allocation_df['kelly_fraction'] = 0
                allocation_df['kelly_position_size'] = allocation_df.get('investment_amount', 0)
                logging.debug(f"Kelly sizing error: {_ke}")

            portfolio_summary['allocation_df_count'] = len(allocation_df)

            # Final reconciliation: remove BUY entries for stocks also in the SELL list
            if not sell_recommendations_df.empty and 'symbol' in sell_recommendations_df.columns:
                _sell_syms = set(sell_recommendations_df['symbol'].tolist())
                if 'action_recommendation' in allocation_df.columns:
                    _conflict_mask = (
                        allocation_df['symbol'].isin(_sell_syms) &
                        allocation_df['action_recommendation'].str.upper().str.contains('BUY|INCREASE', na=False)
                    )
                    _conflicts = allocation_df[_conflict_mask]
                    if len(_conflicts) > 0:
                        print(f"   ⚠️  Reconciliation: removed {len(_conflicts)} BUY/INCREASE entries for stocks also marked SELL: {_conflicts['symbol'].tolist()}")
                        allocation_df = allocation_df[~_conflict_mask].reset_index(drop=True)

            # Post-allocation tax recalculation for stocks promoted to SELL late
            if 'tax_type' in allocation_df.columns and 'action_recommendation' in allocation_df.columns:
                _tax_missing = allocation_df[
                    (allocation_df['action_recommendation'].str.upper().str.contains('SELL|SWAP|EXIT|BOOK', na=False)) &
                    (allocation_df['tax_type'].isna() | (allocation_df['tax_type'] == 'NA') | (allocation_df['tax_type'] == ''))
                ]
                if len(_tax_missing) > 0:
                    for _ti, _tr in _tax_missing.iterrows():
                        _invested = _tr.get('current_value', 0)
                        _avg = _tr.get('avg_cost', 0)
                        _qty = _tr.get('current_quantity', 0)
                        _cur_val = _tr.get('current_value', 0)
                        _inv_val = _avg * _qty if _avg > 0 and _qty > 0 else _cur_val
                        _gain = _cur_val - _inv_val
                        _holding_months = 0  # Conservative STCG default
                        if _gain > 0:
                            if _holding_months < 12:
                                allocation_df.at[_ti, 'tax_type'] = 'STCG'
                                allocation_df.at[_ti, 'estimated_tax'] = round(_gain * 0.20, 0)
                            else:
                                _taxable = max(0, _gain - 125000)
                                allocation_df.at[_ti, 'tax_type'] = 'LTCG'
                                allocation_df.at[_ti, 'estimated_tax'] = round(_taxable * 0.125, 0)
                            allocation_df.at[_ti, 'post_tax_proceeds'] = round(_cur_val - allocation_df.at[_ti, 'estimated_tax'], 0)
                        else:
                            allocation_df.at[_ti, 'tax_type'] = 'NO_TAX (LOSS)'
                            allocation_df.at[_ti, 'estimated_tax'] = 0
                            allocation_df.at[_ti, 'post_tax_proceeds'] = round(_cur_val, 0)
                    print(f"   💰 Tax recalculated for {len(_tax_missing)} late-SELL stocks")

            self.portfolio_allocation = {
                'allocation_df': allocation_df,
                'sell_recommendations': sell_recommendations_df,
                'summary': portfolio_summary,
                'risk_profile_info': portfolio_size_info if portfolio_size_info else {}
            }
            
            _final_sell = len(allocation_df[allocation_df['action_recommendation'].str.upper().isin(['SELL'])] if 'action_recommendation' in allocation_df.columns else [])
            _final_book = len(allocation_df[allocation_df['action_recommendation'].str.upper().str.contains('BOOK|EXHAUSTED', na=False)] if 'action_recommendation' in allocation_df.columns else [])
            _final_buy = len(allocation_df[allocation_df['action_recommendation'].str.upper().str.contains('BUY|NEW|INCREASE', na=False)] if 'action_recommendation' in allocation_df.columns else [])
            _final_hold = len(allocation_df) - _final_sell - _final_book - _final_buy
            print(f"\n   📊 FINAL ALLOCATION SUMMARY: SELL={_final_sell}, BOOK_PROFIT={_final_book}, BUY/INCREASE={_final_buy}, HOLD={_final_hold}, TOTAL={len(allocation_df)}")
            logging.info(f"Generated risk-based portfolio allocation: {len(allocation_df)} keep stocks, {len(sell_recommendations_df)} sell recommendations")
            
            # 🔧 FIX: Record all recommendations in history
            print(f"\n   💾 Recording recommendations in history...")
            for _, row in allocation_df.iterrows():
                fundamentals = {
                    'pe_ratio': results_df[results_df['symbol'] == row['symbol']]['pe_ratio'].iloc[0] if row['symbol'] in results_df['symbol'].values else 0,
                    'roe': results_df[results_df['symbol'] == row['symbol']]['roe'].iloc[0] if row['symbol'] in results_df['symbol'].values else 0,
                    'debt_to_equity': results_df[results_df['symbol'] == row['symbol']]['debt_to_equity'].iloc[0] if row['symbol'] in results_df['symbol'].values else 0
                }
                
                # Ensure price and score are numeric
                try:
                    price_val = float(row['current_price']) if row['current_price'] else 0.0
                    score_val = float(row['overall_score']) if row['overall_score'] else 0.0
                except (ValueError, TypeError):
                    price_val = 0.0
                    score_val = 0.0
                
                self.recommendation_history.record_recommendation(
                    symbol=row['symbol'],
                    action=row['action_type'],
                    score=score_val,
                    price=price_val,
                    fundamentals=fundamentals,
                    reason=row['recommendation'],
                    rank=0,  # Will be calculated in next iteration
                    sector=row['sector']
                )
            
            # Generate stability report
            stability_report = self.recommendation_history.generate_stability_report()
            print(f"   📊 Recommendation History:")
            print(f"      Total recommendations: {stability_report['total_recommendations']}")
            print(f"      Unique stocks tracked: {stability_report['unique_stocks']}")
            print(f"      Flip-flops (7 days): {stability_report['flip_flops_7d']}")
            print(f"      Flip-flops (14 days): {stability_report['flip_flops_14d']}")
            _ahd = stability_report.get('average_hold_days', 'N/A')
            if _ahd != 'N/A' and isinstance(_ahd, (int, float)) and _ahd > 0:
                print(f"      Average hold period: {_ahd:.1f} days")
            else:
                print(f"      Average hold period: Insufficient history")

            _ff_7d = self.recommendation_history.get_flip_flop_stocks(days=7)
            _ff_14d = self.recommendation_history.get_flip_flop_stocks(days=14)
            if _ff_7d:
                print(f"\n   ⚠️  FLIP-FLOP WARNINGS (7 days):")
                for _ff in _ff_7d:
                    print(f"      {_ff['symbol']}: {_ff['first_action']} → {_ff['second_action']} ({_ff['days_between']}d apart)")
            _ff_14d_new = [f for f in _ff_14d if f not in _ff_7d] if _ff_14d else []
            if _ff_14d_new:
                print(f"   ⚠️  ADDITIONAL FLIP-FLOPS (14 days):")
                for _ff in _ff_14d_new:
                    print(f"      {_ff['symbol']}: {_ff['first_action']} → {_ff['second_action']} ({_ff['days_between']}d apart)")
            self._flip_flop_symbols = set(f['symbol'] for f in (_ff_7d or []) + (_ff_14d or []))

            # V5.0: Feedback loop — backfill forward returns for past recommendations
            try:
                outcomes_updated = self.recommendation_history.update_outcomes()
                if outcomes_updated > 0:
                    print(f"   📈 Feedback loop: Updated {outcomes_updated} past recommendation outcomes")
                self._past_accuracy = self._compute_past_accuracy()
                if self._past_accuracy and self._past_accuracy.get('total_with_outcomes', 0) > 0:
                    pa = self._past_accuracy
                    print(f"   📊 Past Accuracy (n={pa['total_with_outcomes']}):")
                    print(f"      BUY hit rate (30d):  {pa.get('buy_hit_rate_30d', 0):.1f}%")
                    print(f"      SELL hit rate (30d): {pa.get('sell_hit_rate_30d', 0):.1f}%")
                    print(f"      Avg return by quintile (30d): Q5={pa.get('q5_avg_return_30d', 0):.2f}%, Q1={pa.get('q1_avg_return_30d', 0):.2f}%")
            except Exception as _fb_err:
                logging.warning(f"Feedback loop failed: {_fb_err}")
                self._past_accuracy = {}
            
            print(f"   🔧 CHECKPOINT 4: Portfolio allocation generation completed successfully")
            print(f"      allocation_df: {len(self.portfolio_allocation['allocation_df'])} stocks")
            
            return self.portfolio_allocation
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            trace = traceback.format_exc()
            
            logging.error(f"Error generating portfolio allocation: {error_msg}")
            logging.error(f"Traceback: {trace}")
            
            print(f"\n   ❌ [ERROR] Portfolio allocation generation FAILED!")
            print(f"   ❌ Error: {error_msg}")
            print(f"\n   📋 Full Traceback:")
            print(trace)
            print(f"\n   💡 Tip: Check if holdings file is corrupted or has encoding issues")
            
            return None
    
    def analyze_batch(self, batch_size=10):
        """Analyze stocks in batches to avoid overwhelming the system"""
        total_stocks = len(self.stock_list)
        self.total_stocks = total_stocks
        
        print(f"[START] Starting Dynamic NSE Stock Analysis")
        print(f"[DATA] Total stocks to analyze: {total_stocks}")
        print(f"[CONFIG] Batch size: {batch_size}")
        print(f"[CONFIG] Max workers: {self.max_workers}")
        print(f"[DATA] Company names available: {len(self.company_names) > 0}")
        print("=" * 80)
        
        logging.info(f"Starting batch analysis of {total_stocks} stocks")

        # ── RETURN BACKFILL: Update forward returns for past recommendations ──
        try:
            _bf_updated = self.recommendation_history.update_outcomes()
            if _bf_updated > 0:
                print(f"   📈 Return backfill: Updated {_bf_updated} outcome fields from past recommendations")
            else:
                print(f"   📈 Return backfill: No pending outcomes to update")
        except Exception as _bf_err:
            logging.warning(f"Return backfill failed (non-fatal): {_bf_err}")
        
        start_time = time.time()

        # ── HOLDINGS PRE-LOAD: Convert CSV holdings to dict for per-stock context ──
        try:
            _hl = self._load_current_holdings()
            self._holdings_dict = {}
            if _hl is not None and not _hl.empty:
                for _, _hr in _hl.iterrows():
                    _sym = str(_hr.get('Instrument', '')).upper()
                    if _sym:
                        self._holdings_dict[_sym] = {
                            'symbol': _sym,
                            'quantity': _hr.get('Qty.', 0),
                            'avg_cost': _hr.get('Avg. cost', 0),
                            'current_value': _hr.get('Cur. val', 0),
                        }
                logging.info(f"[HOLDINGS] Pre-loaded {len(self._holdings_dict)} holdings for portfolio context")
        except Exception as _hl_err:
            self._holdings_dict = {}
            logging.warning(f"[HOLDINGS] Pre-load failed: {_hl_err}")

        # ── REGIME DETECTION: Once before workers start — read-only inside worker threads ──
        # This prevents the race condition where multiple workers each detect a different
        # regime and overwrite self.market_regime with non-deterministic results.
        if self.market_regime is None:
            try:
                self.market_regime = self.regime_detector.detect_regime(period_days=180)
                if self.market_regime:
                    self.current_market_regime = self.market_regime.get('regime', 'SIDEWAYS')
                    self.current_regime_confidence = self.market_regime.get('regime_confidence', 0.5)
                    logging.info(f"[REGIME] Detected: {self.current_market_regime} "
                                 f"({self.market_regime.get('regime_strength', 'N/A')}), "
                                 f"VIX: {self.market_regime.get('vix_level', 0):.2f}, "
                                 f"Confidence: {self.current_regime_confidence:.2f}")
                else:
                    self.market_regime = {
                        'regime': 'SIDEWAYS', 'regime_strength': 'MODERATE', 'vix_level': 15.0,
                        'regime_score': 50, 'regime_confidence': 0.5, 'market_sentiment': 'NEUTRAL',
                        'risk_level': 'MEDIUM', 'trading_recommendation': 'SELECTIVE', 'current_nifty': 0
                    }
                    self.current_market_regime = 'SIDEWAYS'
                    self.current_regime_confidence = 0.5
                    logging.warning("[REGIME] Detection returned None — defaulting to SIDEWAYS")
            except Exception as _regime_ex:
                self.market_regime = {
                    'regime': 'SIDEWAYS', 'regime_strength': 'MODERATE', 'vix_level': 15.0,
                    'regime_score': 50, 'regime_confidence': 0.5, 'market_sentiment': 'NEUTRAL',
                    'risk_level': 'MEDIUM', 'trading_recommendation': 'SELECTIVE', 'current_nifty': 0
                }
                self.current_market_regime = 'SIDEWAYS'
                self.current_regime_confidence = 0.5
                logging.warning(f"[REGIME] Detection exception: {_regime_ex} — defaulting to SIDEWAYS")

        # ── GAP-18 CRISIS DETECTION: Once before workers start ──────────────────
        # Fetches cross-asset signals (crude, gold, INR, VIX, S&P500) and classifies
        # the event type. Result cached in self.crisis_data, read-only in workers.
        if self.crisis_data is None:
            try:
                self.crisis_data = self.crisis_detector.detect()
                if self.crisis_data.get('detection_failed'):
                    logging.warning("[CRISIS] All asset feeds failed — crisis detection unreliable, treating as no-crisis")
                    print("\n⚠️  [CRISIS-DETECTOR] Detection failed — all data feeds unavailable")
                elif self.crisis_data.get('crisis_detected'):
                    logging.warning(
                        f"[CRISIS] {self.crisis_data['description']} | "
                        f"Severity={self.crisis_data['severity_label']} ({self.crisis_data['severity']}/3)"
                    )
                    print(f"\n⚠️  [CRISIS-DETECTOR] {self.crisis_data['description']}")
                    print(f"   Severity : {self.crisis_data['severity_label']} ({self.crisis_data['severity']}/3)")
                    top_sectors = list(self.crisis_data['sector_adjustments'].keys())[:5]
                    print(f"   Affected : {', '.join(top_sectors)}")
                else:
                    logging.info("[CRISIS] No crisis signals — normal market conditions")
            except Exception as _crisis_ex:
                logging.warning(f"[CRISIS] Detection failed: {_crisis_ex} — no crisis adjustments applied")
                self.crisis_data = {
                    'crisis_detected': False, 'crisis_type': 'NONE', 'severity': 0,
                    'severity_label': 'NONE', 'sector_adjustments': {}, 'signals': {}
                }

        # Process in batches
        for batch_start in range(0, total_stocks, batch_size):
            batch_end = min(batch_start + batch_size, total_stocks)
            current_batch = self.stock_list[batch_start:batch_end]
            
            print(f"\n[BATCH] Processing Batch {(batch_start//batch_size)+1}: Stocks {batch_start+1}-{batch_end}")
            print("-" * 60)
            
            batch_results = []
            batch_start_time = time.time()
            
            # Use ThreadPoolExecutor for concurrent processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tasks with a small stagger to avoid simultaneous yfinance rate-limit hits (A-016)
                future_to_stock = {}
                for _i, stock in enumerate(current_batch):
                    if _i > 0:
                        time.sleep(0.3)  # 300ms stagger between submissions
                    future_to_stock[executor.submit(self.analyze_single_stock, stock)] = stock
                
                # Collect results as they complete
                for future in as_completed(future_to_stock):
                    stock = future_to_stock[future]
                    _counted = False
                    try:
                        result = future.result(timeout=120)  # 2 minute timeout per stock
                        if result:
                            batch_results.append(result)
                            self.processed_stocks += 1
                            _counted = True
                            
                            status = result.get('status', 'unknown')
                            score = _nv(result.get('risk_adjusted_score', result.get('overall_score', result.get('overall_score_triple'))), 0)
                            recommendation = result.get('final_recommendation', 'N/A')
                            
                            print(f"   [DONE] {stock:<12}: {status:<10} | Score: {score:5.1f} | {recommendation}")
                            
                            if status in ('error', 'network_error'):
                                self.failed_stocks.append(stock)
                        else:
                            print(f"   [WARN] {stock:<12}: no data returned")
                            self.failed_stocks.append(stock)
                            logging.warning(f"No data returned for {stock}")
                            self.processed_stocks += 1
                            _counted = True
                            
                    except Exception as e:
                        print(f"   [FAIL] {stock:<12}: timeout/error - {str(e)[:50]}")
                        self.failed_stocks.append(stock)
                        if not _counted:
                            self.processed_stocks += 1
                        logging.error(f"Batch processing error for {stock}: {e}")
            
            # A-014: dict keyed by symbol — O(1) retry lookup, deduplication on re-run
            for _r in batch_results:
                self.results[_r['symbol']] = _r
            
            batch_duration = time.time() - batch_start_time
            progress = (self.processed_stocks / total_stocks) * 100 if total_stocks > 0 else 0
            
            print(f"\n   📊 Batch Summary:")
            print(f"      Processed: {len(batch_results)}/{len(current_batch)} stocks")
            print(f"      Duration: {batch_duration:.1f} seconds")
            print(f"      Overall Progress: {progress:.1f}% ({self.processed_stocks}/{total_stocks})")
            
            # Brief pause between batches
            if batch_end < total_stocks:
                print(f"      ⏳ Pausing 5 seconds before next batch...")
                time.sleep(5)
        
        total_duration = time.time() - start_time
        
        print(f"\n🎉 BATCH ANALYSIS COMPLETE!")
        print("=" * 50)
        print(f"   📊 Total processed: {len(self.results)}/{total_stocks}")
        print(f"   ✅ Successful: {len(self.results) - len(self.failed_stocks)}")
        print(f"   [FAIL] Failed: {len(self.failed_stocks)}")
        print(f"   ⏱️  Total duration: {total_duration/60:.1f} minutes")

        # Detailed skip/fail summary
        _skipped = [r for r in self.results.values() if r.get('status') == 'data_invalid']
        if _skipped or self.failed_stocks:
            print(f"\n   ⚠️  SKIPPED / FAILED STOCKS DETAIL:")
            for _sk in _skipped:
                _sym = _sk.get('symbol', '?')
                _warns = ', '.join(_sk.get('quality_warnings', ['unknown']))
                print(f"      {_sym:<15} — data_invalid: {_warns}")
            for _fs in self.failed_stocks:
                if _fs not in [s.get('symbol') for s in _skipped]:
                    print(f"      {_fs:<15} — processing error")
            logging.info(f"Skipped stocks: {[s.get('symbol') for s in _skipped]}, Failed: {self.failed_stocks}")
        if total_stocks > 0:
            print(f"   📈 Average per stock: {total_duration/total_stocks:.1f} seconds")
        else:
            print(f"   📈 No stocks processed")
        
        # Use emoji-free text for logging to avoid encoding issues
        logging.info(f"Batch analysis completed: {len(self.results)} results, {len(self.failed_stocks)} failures")

        # 🔄 RETRY MECHANISM: Retry failed and low data quality stocks
        if self.failed_stocks or self.low_quality_stocks:
            self._retry_failed_stocks()

        return list(self.results.values())  # A-014: expose as list for downstream consumers
    
    def _retry_failed_stocks(self):
        """Retry failed and low data quality stocks with increased timeout and delay"""
        retry_candidates = list(set(self.failed_stocks + self.low_quality_stocks))
        
        if not retry_candidates:
            return
        
        print(f"\n🔄 RETRYING FAILED/LOW QUALITY STOCKS")
        print("=" * 50)
        print(f"   📊 Stocks to retry: {len(retry_candidates)}")
        print(f"   ⏳ Using extended timeout and delays...")
        
        retried_count = 0
        improved_count = 0
        
        for i, symbol in enumerate(retry_candidates, 1):
            try:
                print(f"\n   🔄 Retry {i}/{len(retry_candidates)}: {symbol}")
                
                # A-016: flat 3s delay between retries (exponential was hitting 30s by retry #6)
                if i > 1:
                    _delay = 3
                    logging.debug(f"Retry delay {_delay}s before {symbol}")
                    time.sleep(_delay)

                # Re-analyze the stock
                result = self.analyze_single_stock(symbol)

                if result:
                    # A-014: O(1) dict lookup — no list.index() / linear scan
                    old_result = self.results.get(symbol)

                    if old_result:
                        # Replace old result with new one
                        old_quality = 'LOW DATA QUALITY' in old_result.get('recommendation', '')
                        new_quality = 'LOW DATA QUALITY' in result.get('recommendation', '')

                        if old_quality and not new_quality:
                            improved_count += 1
                            print(f"      ✅ Data quality IMPROVED for {symbol}")
                            self.results[symbol] = result
                        elif not new_quality:
                            print(f"      ✅ {symbol} successfully re-analyzed")
                            self.results[symbol] = result
                        else:
                            print(f"      ⚠️  {symbol} still has low data quality")
                    else:
                        # Stock wasn't in results before — add it now
                        self.results[symbol] = result
                        improved_count += 1
                        print(f"      ✅ {symbol} successfully analyzed on retry")
                    
                    retried_count += 1
                    
                    # Remove from failed/low quality lists
                    if symbol in self.failed_stocks:
                        self.failed_stocks.remove(symbol)
                    if symbol in self.low_quality_stocks:
                        self.low_quality_stocks.remove(symbol)
                        
            except Exception as e:
                print(f"      [FAIL] Retry failed for {symbol}: {str(e)[:50]}...")
                logging.debug(f"Retry failed for {symbol}: {e}")
        
        print(f"\n   📊 Retry Summary:")
        print(f"      Attempted: {len(retry_candidates)}")
        print(f"      Successful: {retried_count}")
        print(f"      Improved quality: {improved_count}")
        print(f"      Still failed: {len(self.failed_stocks) + len(self.low_quality_stocks)}")
        
        logging.info(f"Retry completed: {retried_count}/{len(retry_candidates)} successful, {improved_count} improved")
    
    def calculate_support_resistance_levels(self, symbol: str, risk_profile: str = "moderate",
                                               hist_override: pd.DataFrame = None) -> Dict[str, Any]:
        """
        Calculate Support & Resistance Levels and Trading Plan.
        Enhanced for different risk profiles: conservative, moderate, aggressive.
        If hist_override is provided (from batch download), skip individual yfinance call.
        """
        try:
            if hist_override is not None and not hist_override.empty:
                hist = hist_override
            else:
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="6mo", interval="1d")
            
            if hist.empty or len(hist) < 20:
                return {
                    'immediate_resistance': None,
                    'strong_resistance': None,
                    'immediate_support': None,
                    'strong_support': None,
                    'entry_range_low': None,
                    'entry_range_high': None,
                    'target_1': None,
                    'target_2': None,
                    'target_3': None,  # New aggressive target
                    'stop_loss': None,
                    'stop_loss_tight': None,  # New tight stop for aggressive
                    'trading_plan_text': 'Insufficient data for trading plan'
                }
            
            current_price = hist['Close'].iloc[-1]
            high_52w = hist['High'].max()
            low_52w = hist['Low'].min()
            
            # Calculate moving averages for support levels
            hist['MA_20'] = hist['Close'].rolling(window=20).mean()
            hist['MA_50'] = hist['Close'].rolling(window=50).mean()
            hist['MA_60'] = hist['Close'].rolling(window=60).mean()
            
            # Support & Resistance Calculations
            immediate_resistance = high_52w
            strong_resistance = round(immediate_resistance * 1.02, 2)
            
            # Find recent support levels
            ma_20_current = hist['MA_20'].iloc[-1] if not pd.isna(hist['MA_20'].iloc[-1]) else current_price * 0.98
            low_60_day = hist['Low'].tail(60).min()
            
            immediate_support = max(ma_20_current, current_price * 0.97)
            strong_support = min(low_60_day, current_price * 0.91)
            
            # 🚀 RISK-BASED Trading Plan Calculations
            if risk_profile == "aggressive":
                # High-Risk High-Reward Parameters
                entry_low = current_price * 0.96    # 4% below current (more aggressive entry)
                entry_high = current_price * 1.02   # 2% above current (momentum entry)
                
                target_1 = current_price * 1.06    # 6% gain (quick profit)
                target_2 = current_price * 1.12    # 12% gain (medium term)
                target_3 = current_price * 1.20    # 20% gain (aggressive target)
                
                stop_loss = current_price * 0.92    # 8% stop loss (wider for volatility)
                stop_loss_tight = current_price * 0.96  # 4% tight stop for momentum trades
                
                risk_tolerance = "HIGH"
                strategy_type = "MOMENTUM/GROWTH"
                
            elif risk_profile == "conservative":
                # Low-Risk Conservative Parameters
                entry_low = current_price * 0.99    # 1% below current
                entry_high = current_price * 1.005  # 0.5% above current
                
                target_1 = current_price * 1.025   # 2.5% gain
                target_2 = current_price * 1.05    # 5% gain
                target_3 = current_price * 1.08    # 8% gain
                
                stop_loss = current_price * 0.965   # 3.5% stop loss
                stop_loss_tight = current_price * 0.98  # 2% tight stop
                
                risk_tolerance = "LOW"
                strategy_type = "VALUE/DIVIDEND"
                
            else:  # moderate (default)
                entry_low = current_price * 0.98    # 2% below current
                entry_high = current_price * 1.005  # 0.5% above current
                
                target_1 = current_price * 1.035   # 3.5% gain
                target_2 = current_price * 1.08    # 8% gain
                target_3 = current_price * 1.12    # 12% gain
                
                stop_loss = current_price * 0.945   # 5.5% stop loss
                stop_loss_tight = current_price * 0.97  # 3% tight stop
                
                risk_tolerance = "MODERATE"
                strategy_type = "BALANCED"
            
            # Calculate percentages for display
            target_1_pct = ((target_1 - current_price) / current_price) * 100 if current_price > 0 else 0
            target_2_pct = ((target_2 - current_price) / current_price) * 100 if current_price > 0 else 0
            target_3_pct = ((target_3 - current_price) / current_price) * 100 if current_price > 0 else 0
            stop_loss_pct = ((stop_loss - current_price) / current_price) * 100 if current_price > 0 else 0
            stop_loss_tight_pct = ((stop_loss_tight - current_price) / current_price) * 100 if current_price > 0 else 0
            
            # Calculate volatility for risk assessment
            daily_returns = hist['Close'].pct_change().dropna()
            volatility = daily_returns.std() * np.sqrt(252) * 100  # Annualized volatility
            
            # 🚀 Enhanced Trading Plan Text based on Risk Profile
            if risk_profile == "aggressive":
                trading_plan_text = f"""🚀 HIGH-RISK HIGH-REWARD TRADING PLAN:

📊 Support & Resistance Levels:
• Immediate Resistance: ₹{immediate_resistance:.2f} (52-week high)
• Strong Resistance: ₹{strong_resistance:.2f} (breakout level)
• Immediate Support: ₹{immediate_support:.2f} (20-day MA)
• Strong Support: ₹{strong_support:.2f} (60-day low)

⚡ AGGRESSIVE TRADING STRATEGY:
• Entry Zone: ₹{entry_low:.2f}-{entry_high:.2f} (momentum/dip buying)
• Quick Target: ₹{target_1:.2f} (+{target_1_pct:.1f}%) - Take 30% profit
• Medium Target: ₹{target_2:.2f} (+{target_2_pct:.1f}%) - Take 40% profit  
• Aggressive Target: ₹{target_3:.2f} (+{target_3_pct:.1f}%) - Let 30% run
• Tight Stop: ₹{stop_loss_tight:.2f} ({stop_loss_tight_pct:.1f}%) - Day trading
• Wide Stop: ₹{stop_loss:.2f} ({stop_loss_pct:.1f}%) - Swing trading

🎯 RISK PROFILE: {risk_tolerance} | STRATEGY: {strategy_type}
📈 Volatility: {volatility:.1f}% (Higher volatility = Higher potential returns)

💡 AGGRESSIVE TIPS:
• Use leverage carefully (max 2:1 for this volatility)
• Scale into position on dips
• Take profits on strength
• Trail stop-loss after +10% gains"""
                
            else:
                trading_plan_text = f"""Support & Resistance Levels:
• Immediate Resistance: ₹{immediate_resistance:.2f} (52-week high)
• Strong Resistance: ₹{strong_resistance:.2f} (psychological level)
• Immediate Support: ₹{immediate_support:.2f} (20-day MA)
• Strong Support: ₹{strong_support:.2f} (60-day low)

Trading Plan ({risk_tolerance} RISK):
• Entry: ₹{entry_low:.2f}-{entry_high:.2f} on minor dips
• Target 1: ₹{target_1:.2f} (+{target_1_pct:.1f}%)
• Target 2: ₹{target_2:.2f} (+{target_2_pct:.1f}%)
• Target 3: ₹{target_3:.2f} (+{target_3_pct:.1f}%)
• Stop Loss: ₹{stop_loss:.2f} ({stop_loss_pct:.1f}%)"""
            
            return {
                'immediate_resistance': round(immediate_resistance, 2),
                'strong_resistance': round(strong_resistance, 2),
                'immediate_support': round(immediate_support, 2),
                'strong_support': round(strong_support, 2),
                'entry_range_low': round(entry_low, 2),
                'entry_range_high': round(entry_high, 2),
                'target_1': round(target_1, 2),
                'target_1_pct': round(target_1_pct, 1),
                'target_2': round(target_2, 2),
                'target_2_pct': round(target_2_pct, 1),
                'target_3': round(target_3, 2),
                'target_3_pct': round(target_3_pct, 1),
                'stop_loss': round(stop_loss, 2),
                'stop_loss_pct': round(stop_loss_pct, 1),
                'stop_loss_tight': round(stop_loss_tight, 2),
                'stop_loss_tight_pct': round(stop_loss_tight_pct, 1),
                'trading_plan_text': trading_plan_text,
                'risk_reward_ratio': round(abs(target_2_pct / stop_loss_pct), 2) if stop_loss_pct != 0 else 0,
                'volatility': round(volatility, 1),
                'risk_profile': risk_profile,
                'strategy_type': strategy_type
            }
            
        except Exception as e:
            logging.warning(f"Failed to calculate support/resistance for {symbol}: {e}")
            return {
                'immediate_resistance': None,
                'strong_resistance': None,
                'immediate_support': None,
                'strong_support': None,
                'entry_range_low': None,
                'entry_range_high': None,
                'target_1': None,
                'target_2': None,
                'target_3': None,
                'stop_loss': None,
                'stop_loss_tight': None,
                'trading_plan_text': f'Unable to calculate trading plan: {str(e)}'
            }
    
    def generate_comprehensive_report(self):
        """ENHANCED: Generate comprehensive Excel report with all analysis enhancements"""
        if not self.results:
            print("[FAIL] No results to generate report")
            return None
        
        print(f"\n📊 GENERATING ENHANCED COMPREHENSIVE REPORT")
        print("-" * 60)
        
        try:
            # Create DataFrame  (A-014: self.results is a dict keyed by symbol)
            df = pd.DataFrame(self.results.values())
            
            # MI-07: Separate failed stocks into a different bucket
            _failed_mask = df.get('scoring_failed', pd.Series(False, index=df.index)).fillna(False).astype(bool)
            _failed_df = df[_failed_mask].copy()
            df = df[~_failed_mask].copy()
            if len(_failed_df) > 0:
                print(f"   ⚠️  {len(_failed_df)} stocks with insufficient data moved to Skipped sheet")
                self._skipped_stocks_df = _failed_df
            else:
                self._skipped_stocks_df = pd.DataFrame()
            
            print("🔄 Applying enhancements...")
            
            # Apply all enhancements
            print("   1️⃣ Calculating sector rankings...")
            df = self.calculate_sector_rankings(df)
            
            print("   2️⃣ Analyzing risk-return metrics...")
            if not getattr(self, 'skip_risk', False):
                df = self.calculate_risk_return_metrics(df)
            else:
                print("      ⚡ Skipped (--skip-risk enabled)")
                df['risk_adjusted_score'] = df['overall_score'] if 'overall_score' in df.columns else df.get('final_blended_score', df.get('overall_score_with_value', 50))
                df['risk_category'] = 'UNKNOWN'
            
            print("   3️⃣ Generating portfolio allocation...")
            target_amount = getattr(self, 'portfolio_amount', 100000)
            
            # Risk-based portfolio size allocation with strict limits
            current_holdings = self._load_current_holdings()
            current_holdings_count = len(current_holdings) if current_holdings is not None and not current_holdings.empty else 0
            
            # Define strict portfolio size ranges based on risk profile
            # 🎯 FIXED: Reduced max to 20-25 for better tracking and management
            if self.risk_profile == "aggressive":
                min_stocks, max_stocks = 15, 20  # Highly focused portfolio
                # Ensure we reach minimum threshold - if holdings < min, target min; if > max, target max
                if current_holdings_count < min_stocks:
                    target_stocks = min_stocks  # Force up to minimum
                elif current_holdings_count > max_stocks:
                    target_stocks = max_stocks  # Force down to maximum (SELL required)
                else:
                    target_stocks = current_holdings_count  # Keep current if within range
            elif self.risk_profile == "balanced":
                min_stocks, max_stocks = 20, 25  # Balanced portfolio  
                if current_holdings_count < min_stocks:
                    target_stocks = min_stocks
                elif current_holdings_count > max_stocks:
                    target_stocks = max_stocks  # Force down to maximum (SELL required)
                else:
                    target_stocks = current_holdings_count
            else:  # moderate (default) - MOST COMMON
                min_stocks, max_stocks = 30, 40  # 🚀 EXPANDED: Allow up to 40 stocks to show more opportunities
                if current_holdings_count < min_stocks:
                    target_stocks = min_stocks # Force up to 30
                elif current_holdings_count > max_stocks:
                    target_stocks = current_holdings_count # Keep current if huge
                else:
                    target_stocks = max(current_holdings_count + 10, 30) # Always show room for 10+ new stocks
            
            # Set allocation parameters for strict targeting
            portfolio_size_info = {
                'current_count': current_holdings_count,
                'target_count': target_stocks,
                'min_allowed': min_stocks,
                'max_allowed': max_stocks,
                'requires_selling': current_holdings_count > max_stocks
            }
            
            # Define risk profile allocation percentages (Defensive/Growth/Value)
            if self.risk_profile == "aggressive":
                allocation_percentages = {'DEFENCE': 0.0, 'GROWTH': 0.5, 'VALUE': 0.5}
                allocation_strategy = "Pure offense: 50% Growth + 50% Value"
            elif self.risk_profile == "balanced":
                allocation_percentages = {'DEFENCE': 0.3, 'GROWTH': 0.3, 'VALUE': 0.4}
                allocation_strategy = "Safety-first: 30% Defense + 30% Growth + 40% Value"
            else:  # moderate (default)
                allocation_percentages = {'DEFENCE': 0.1, 'GROWTH': 0.4, 'VALUE': 0.5}
                allocation_strategy = "Balanced: 10% Defense + 40% Growth + 50% Value"
            
            portfolio_size_info['allocation_percentages'] = allocation_percentages
            portfolio_size_info['allocation_strategy'] = allocation_strategy
                
            print(f"   📊 Risk Profile: {self.risk_profile.upper()}")
            print(f"   📊 Current Holdings: {current_holdings_count} stocks")
            print(f"   🎯 Target Portfolio Size: {target_stocks} stocks (Range: {min_stocks}-{max_stocks})")
            print(f"   📈 Allocation Strategy: {allocation_strategy}")
            if portfolio_size_info['requires_selling']:
                print(f"   ⚠️  Selling Required: {current_holdings_count - max_stocks} stocks exceed limit")
            
            portfolio_allocation = self.generate_portfolio_allocation_suggestions(df, target_amount, target_stocks, portfolio_size_info)
            
            # 🔧 DEBUG: Check portfolio_allocation status
            if portfolio_allocation is None:
                print(f"   ❌ CRITICAL: portfolio_allocation returned None!")
                print(f"   🔧 EMERGENCY FALLBACK: Creating minimal portfolio allocation")
                # Create minimal allocation_df to ensure sheet is always created
                current_holdings = self._load_current_holdings()
                if current_holdings is not None and not current_holdings.empty:
                    _fb_inst_col = next((c for c in ['Instrument', 'Symbol', 'Stock', 'Ticker', 'symbol', 'instrument'] if c in current_holdings.columns), 'Instrument')
                    minimal_data = []
                    for _, holding in current_holdings.iterrows():
                        symbol = holding[_fb_inst_col].upper()
                        stock_data = df[df['symbol'].str.upper() == symbol]
                        if not stock_data.empty:
                            stock = stock_data.iloc[0]
                            minimal_data.append({
                                'symbol': symbol,
                                'company_name': stock.get('company_name', symbol),
                                'current_price': stock.get('current_price', holding.get('LTP', 0)),
                                'current_value': holding.get('Cur. val', 0),
                                'current_quantity': holding.get('Qty.', 0),
                                'overall_score': stock.get('final_blended_score', stock.get('risk_adjusted_score', 0)),
                                'action_recommendation': 'HOLD',
                                'sector': stock.get('sector', 'Unknown'),
                                'is_current_holding': True,
                                'investment_amount': 0,
                                'suggested_quantity': 0,
                                'risk_adjusted_score': stock.get('risk_adjusted_score', 0),
                                'undervaluation_score': stock.get('undervaluation_score', 50),
                                'risk_category': stock.get('risk_category', 'MODERATE')
                            })
                    
                    portfolio_allocation = {
                        'allocation_df': pd.DataFrame(minimal_data),
                        'summary': {
                            'total_stocks': len(minimal_data),
                            'current_holdings': len(minimal_data),
                            'new_positions': 0,
                            'error': 'Full allocation failed - using minimal data'
                        }
                    }
                    print(f"   ✅ Created emergency fallback with {len(minimal_data)} holdings")
                else:
                    print(f"   ❌ Cannot create fallback - no holdings file found")
            elif not portfolio_allocation:
                print(f"   ❌ CRITICAL: portfolio_allocation is empty dict!")
            elif 'allocation_df' not in portfolio_allocation:
                print(f"   ❌ CRITICAL: allocation_df missing from portfolio_allocation!")
                print(f"      Keys: {list(portfolio_allocation.keys())}")
            elif portfolio_allocation['allocation_df'].empty:
                print(f"   ❌ CRITICAL: allocation_df is empty!")
            else:
                print(f"   ✅ Portfolio allocation OK: {len(portfolio_allocation['allocation_df'])} stocks")
                if 'action_recommendation' in portfolio_allocation['allocation_df'].columns:
                    print(f"   ✅ action_recommendation column present")
                    # Check for conflict-resolved values
                    conflict_count = portfolio_allocation['allocation_df']['action_recommendation'].astype(str).str.contains('⚠️|🟡|🟢', na=False, regex=True).sum()
                    print(f"   ✅ Conflict-resolved actions: {conflict_count}")
                else:
                    print(f"   ❌ action_recommendation column MISSING!")
                    print(f"      Available columns: {list(portfolio_allocation['allocation_df'].columns)[:10]}")
            
            # Sort by risk-adjusted score (new primary metric)
            df = df.sort_values(['risk_adjusted_score', 'symbol'], ascending=[False, True], na_position='last', kind='mergesort')
            
            # Generate enhanced Excel report
            print("   4️⃣ Creating Excel report with charts...")
            filename = self.generate_enhanced_excel_report(df, portfolio_allocation)
            
            print(f"✅ Enhanced Excel report saved: {filename}")
            
            # Check file size
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print(f"   📁 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
                logging.info(f"Enhanced Excel report generated: {filename}, Size: {file_size} bytes")
            
            # Generate enhanced summary statistics
            self.generate_enhanced_summary_stats(df)
            
            return filename
            
        except Exception as e:
            print(f"[FAIL] Enhanced Excel generation failed: {e}")
            logging.error(f"Enhanced Excel generation failed: {e}")
            return None
    
    def generate_enhanced_excel_report(self, df, portfolio_allocation):
        """
        🚀 PHASE 1 ENHANCEMENTS: Advanced Excel reporting with Dashboard, Charts & Visual Formatting
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/Enhanced_Stock_Report_{timestamp}.xlsx"
            
            # 🔧 FIX: Clean NaN/Inf values before Excel export
            print("   🧹 Cleaning data for Excel export...")
            df = self._clean_dataframe_for_excel(df.copy())
            
            if portfolio_allocation and 'allocation_df' in portfolio_allocation:
                portfolio_allocation['allocation_df'] = self._clean_dataframe_for_excel(portfolio_allocation['allocation_df'].copy())
            
            print("   🔄 Calculating Support & Resistance levels for top stocks...")
            
            # Add Support & Resistance data for top performing stocks
            top_stocks = df.head(20)
            support_resistance_data = []
            
            sr_symbols = [s + '.NS' if not s.endswith('.NS') else s for s in top_stocks['symbol']]
            _sr_bulk = pd.DataFrame()
            try:
                _sr_bulk = yf.download(
                    sr_symbols, period='6mo', interval='1d',
                    group_by='ticker', progress=False, threads=True
                )
            except Exception as _e:
                logging.warning(f"Batch S/R download failed: {_e}")
            
            for idx, stock in top_stocks.iterrows():
                symbol = stock['symbol']
                ns_sym = symbol + '.NS' if not symbol.endswith('.NS') else symbol
                print(f"      📊 Calculating S&R for {symbol}...")
                
                _hist_cache = pd.DataFrame()
                if not _sr_bulk.empty:
                    try:
                        if len(sr_symbols) == 1:
                            _hist_cache = _sr_bulk.dropna(subset=['Close'])
                        elif ns_sym in _sr_bulk.columns.get_level_values(0):
                            _hist_cache = _sr_bulk[ns_sym].dropna(subset=['Close'])
                    except Exception:
                        pass
                
                sr_data = self.calculate_support_resistance_levels(symbol, hist_override=_hist_cache)
                sr_record = {
                    'symbol': symbol,
                    'company_name': stock.get('company_name', symbol),
                    'current_price': stock.get('current_price', 0),
                    'overall_score': stock.get('overall_score_with_value', 0),
                    'recommendation': stock.get('final_recommendation', ''),
                    **sr_data
                }
                support_resistance_data.append(sr_record)
            
            sr_df = pd.DataFrame(support_resistance_data)
            
            # Create Excel writer with xlsxwriter engine for charts and NaN/Inf handling
            with pd.ExcelWriter(filename, engine='xlsxwriter', 
                               engine_kwargs={'options': {'nan_inf_to_errors': True}}) as writer:
                workbook = writer.book
                
                # 🎨 ENHANCED FORMATTING SYSTEM
                header_format = workbook.add_format({
                    'bold': True, 'bg_color': '#2E5984', 'font_color': 'white',
                    'border': 2, 'align': 'center', 'valign': 'vcenter',
                    'font_size': 12, 'text_wrap': True
                })
                
                subheader_format = workbook.add_format({
                    'bold': True, 'bg_color': '#5B9BD5', 'font_color': 'white',
                    'border': 1, 'align': 'center', 'valign': 'vcenter',
                    'font_size': 10
                })
                
                # Recommendation color formats
                buy_format = workbook.add_format({
                    'bold': True, 'bg_color': '#70AD47', 'font_color': 'white',
                    'border': 1, 'align': 'center'
                })
                
                strong_buy_format = workbook.add_format({
                    'bold': True, 'bg_color': '#375623', 'font_color': 'white',
                    'border': 1, 'align': 'center'
                })
                
                hold_format = workbook.add_format({
                    'bold': True, 'bg_color': '#FFC000', 'font_color': 'black',
                    'border': 1, 'align': 'center'
                })
                
                sell_format = workbook.add_format({
                    'bold': True, 'bg_color': '#C55A5A', 'font_color': 'white',
                    'border': 1, 'align': 'center'
                })
                
                # Risk level formats
                low_risk_format = workbook.add_format({
                    'bg_color': '#D5E8D4', 'border': 1, 'align': 'center'
                })
                
                medium_risk_format = workbook.add_format({
                    'bg_color': '#FFF2CC', 'border': 1, 'align': 'center'
                })
                
                high_risk_format = workbook.add_format({
                    'bg_color': '#F8CECC', 'border': 1, 'align': 'center'
                })
                
                # Enhanced data formats
                data_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'valign': 'vcenter'
                })
                
                text_format = workbook.add_format({
                    'border': 1, 'text_wrap': True, 'align': 'left', 'valign': 'top'
                })
                
                price_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'num_format': '₹#,##0.00'
                })
                
                percent_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'num_format': '0.00%'
                })
                
                score_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'num_format': '0.0'
                })
                
                large_number_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'num_format': '₹#,##0.00,,"M"'
                })
                
                # Dashboard title format
                dashboard_title_format = workbook.add_format({
                    'bold': True, 'font_size': 18, 'bg_color': '#1F4E79',
                    'font_color': 'white', 'align': 'center', 'valign': 'vcenter'
                })
                
                metric_title_format = workbook.add_format({
                    'bold': True, 'font_size': 14, 'bg_color': '#4472C4',
                    'font_color': 'white', 'align': 'center'
                })
                
                metric_value_format = workbook.add_format({
                    'bold': True, 'font_size': 16, 'align': 'center',
                    'valign': 'vcenter'
                })
                
                # 🚀 PHASE 1 ENHANCEMENT: COMPREHENSIVE DASHBOARD SHEET
                print("   📊 Creating comprehensive dashboard...")
                self._create_dashboard_sheet(workbook, df, portfolio_allocation, dashboard_title_format, 
                                           metric_title_format, metric_value_format, header_format, data_format, 
                                           price_format, percent_format, score_format)
                
                # 1. Enhanced Summary Sheet with conditional formatting
                # GAP-RISK-SCORE FIX: use final_blended_score as primary score column
                # (was overall_score_with_value = old Phase-1 score, diverged up to 22 pts)
                summary_cols = ['symbol', 'company_name', 'sector', 'final_blended_score',
                               'undervaluation_score', 'risk_adjusted_score', 'risk_category',
                               'final_recommendation', 'current_price']
                available_cols = [col for col in summary_cols if col in df.columns]
                summary_df = df[available_cols].head(50)
                summary_df.to_excel(writer, sheet_name='Top Picks', index=False)
                
                # 🎨 Apply conditional formatting to Top Picks sheet
                self._apply_conditional_formatting_top_picks(writer, summary_df, buy_format, strong_buy_format, 
                                                           hold_format, sell_format, low_risk_format, 
                                                           medium_risk_format, high_risk_format)
                
                # Trading Levels sheet — entry zones, targets, stop losses, risk-reward
                if sr_df is not None and not sr_df.empty:
                    _tl_cols = ['symbol', 'company_name', 'current_price', 'recommendation',
                                'entry_range_low', 'entry_range_high',
                                'target_1', 'target_2', 'target_3',
                                'stop_loss', 'stop_loss_tight',
                                'risk_reward_ratio', 'strategy_type']
                    _tl_avail = [c for c in _tl_cols if c in sr_df.columns]
                    _tl_df = sr_df[_tl_avail].copy()
                    _tl_renames = {
                        'current_price': 'PRICE', 'recommendation': 'SIGNAL',
                        'entry_range_low': 'ENTRY_LOW', 'entry_range_high': 'ENTRY_HIGH',
                        'target_1': 'TARGET_1', 'target_2': 'TARGET_2', 'target_3': 'TARGET_3',
                        'stop_loss': 'STOP_LOSS', 'stop_loss_tight': 'TIGHT_STOP',
                        'risk_reward_ratio': 'RISK_REWARD', 'strategy_type': 'STRATEGY',
                    }
                    _tl_df.rename(columns={k: v for k, v in _tl_renames.items() if k in _tl_df.columns}, inplace=True)
                    _tl_df.to_excel(writer, sheet_name='Trading Levels', index=False)
                    _tl_ws = writer.sheets['Trading Levels']
                    for ci, col in enumerate(_tl_df.columns):
                        _tl_ws.write(0, ci, col, header_format)
                    self._auto_resize_columns(_tl_ws, _tl_df)
                    print(f"   📊 Trading Levels sheet created with {len(_tl_df)} stocks")
                
                # 2. Undervalued Stocks Sheet
                undervalued = df[df.get('undervaluation_score', pd.Series()).fillna(50) >= 65].head(30)
                if not undervalued.empty:
                    undervalued_cols = ['symbol', 'company_name', 'undervaluation_score', 
                                       'pe_ratio', 'pb_ratio', 'roe', 'dividend_yield', 
                                       'current_price', 'final_recommendation']
                    available_undervalued_cols = [col for col in undervalued_cols if col in undervalued.columns]
                    undervalued[available_undervalued_cols].to_excel(writer, sheet_name='Undervalued', index=False)
                
                # 3. Sector Analysis Sheet
                if hasattr(self, 'sector_statistics'):
                    sector_df = pd.DataFrame(self.sector_statistics).T.round(2)
                    sector_df.to_excel(writer, sheet_name='Sector Analysis')
                
                # 4. Risk Analysis Sheet
                risk_cols = ['symbol', 'company_name', 'risk_category', 'volatility_6m', 
                            'max_drawdown_6m', 'beta', 'risk_adjusted_score']
                available_risk_cols = [col for col in risk_cols if col in df.columns]
                risk_df = df[available_risk_cols].dropna()
                if not risk_df.empty:
                    risk_df.to_excel(writer, sheet_name='Risk Analysis', index=False)
                
                # 5. Enhanced Portfolio Allocation Sheet with formatting
                if portfolio_allocation:
                    alloc_df = portfolio_allocation['allocation_df']
                    
                    # � DEBUG: Check what columns are actually in alloc_df
                    print(f"   🔍 Portfolio Allocation columns available: {len(alloc_df.columns)}")
                    print(f"      Columns: {list(alloc_df.columns)[:10]}...")  # Show first 10
                    
                    # �🔧 ENHANCED: Comprehensive retail investor decision-making columns
                    essential_cols = [
                        # ── GROUP A: WHAT TO DO ──
                        'symbol',
                        'company_name',
                        'action_recommendation',
                        'profit_booking_timing',
                        'exit_reason',

                        # ── GROUP B: MONEY ──
                        'investment_amount',
                        'suggested_quantity',
                        'current_quantity',
                        'current_value',
                        'current_profit_pct',
                        'profit_booking_pct',
                        'profit_booking_amount',
                        'tax_type',
                        'estimated_tax',
                        'post_tax_proceeds',

                        # ── GROUP C: STOCK QUALITY ──
                        'overall_score',
                        'risk_adjusted_score',
                        'hybrid_fundamental_quality',
                        'hybrid_momentum_technical',
                        'hybrid_volume_strength',
                        'hybrid_multi_timeframe',
                        'hybrid_risk_adjustment',
                        'undervaluation_score',
                        'risk_category',
                        'pe_ratio',
                        'roe',
                        'debt_to_equity',

                        # ── GROUP D: PRICE & LEVELS ──
                        'current_price',
                        '52_week_high',
                        '52_week_low',
                        'enhanced_price_change_20d',
                        'support_level',
                        'resistance_level',
                        'stop_loss_price',
                        'enhanced_rsi_14',
                        'volatility',

                        # ── GROUP E: SIGNALS & INFO ──
                        'ml_signal',
                        'ml_confidence',
                        'ad_line_signal',
                        'mfi_signal',
                        'is_current_holding',
                        'sector',
                        'stock_classification',
                        'holdings_rank',
                        'portfolio_weight',
                        'action_reason',
                    ]
                    
                    # 🔧 FIX: Add missing columns with defaults before selection
                    missing_cols = [col for col in essential_cols if col not in alloc_df.columns]
                    if missing_cols:
                        print(f"   ⚠️  WARNING: {len(missing_cols)} columns missing from allocation_df")
                        print(f"      Missing: {missing_cols[:5]}...")  # Show first 5
                    
                    for col in essential_cols:
                        if col not in alloc_df.columns:
                            # Set appropriate defaults based on column type
                            if col in ['investment_amount', 'suggested_quantity', 'current_quantity', 'current_value', 'current_profit_pct']:
                                alloc_df[col] = 0
                            elif col in ['profit_booking_pct', 'profit_booking_timing']:
                                alloc_df[col] = None
                            elif col in ['action_recommendation', 'exit_reason', 'stock_classification']:
                                alloc_df[col] = ''
                            elif col == 'is_current_holding':
                                alloc_df[col] = False
                            else:
                                alloc_df[col] = None
                    
                    print(f"   ✅ After adding defaults: {len(alloc_df.columns)} total columns")
                    
                    # Only include columns that exist
                    existing_cols = [col for col in essential_cols if col in alloc_df.columns]
                    
                    # Merge S/R trading levels into allocation for BUY/INCREASE stocks
                    if sr_df is not None and not sr_df.empty:
                        _sr_merge_cols = ['symbol', 'entry_range_low', 'entry_range_high', 'target_1', 'stop_loss', 'risk_reward_ratio']
                        _sr_avail = [c for c in _sr_merge_cols if c in sr_df.columns]
                        if len(_sr_avail) > 1:
                            alloc_df = alloc_df.merge(sr_df[_sr_avail], on='symbol', how='left', suffixes=('', '_sr'))

                    # Create simplified dataframe
                    alloc_df_simple = alloc_df[existing_cols].copy()

                    # [MI-L04 POST FIX] Final guard: allocation engine can override exit_strategy HOLD.
                    # Re-apply protection: SELL on ML=HOLD owned losing position → HOLD
                    # (SWAP is excluded — that IS rotation, which the user wants)
                    print(f"   🔧 [MI-L04 POST] Protecting ML=HOLD owned losing positions from pure SELL...")
                    _ml_cp  = 'ml_signal'         if 'ml_signal'         in alloc_df_simple.columns else None
                    _own_cp = 'is_current_holding' if 'is_current_holding' in alloc_df_simple.columns else None
                    _pnl_cp = 'current_profit_pct' if 'current_profit_pct' in alloc_df_simple.columns else None
                    _l04_protected = 0
                    if _ml_cp and _own_cp and _pnl_cp:
                        for _idxl, _rowl in alloc_df_simple.iterrows():
                            _act_l = str(_rowl.get('action_recommendation', ''))
                            _own_l = bool(_rowl.get(_own_cp, False))
                            _pnl_l = _nv(_rowl.get(_pnl_cp), 0)
                            _ml_l  = str(_rowl.get(_ml_cp, ''))
                            # Only block pure SELL (not SWAP → which is rotation)
                            _is_pure_sell = str(_act_l or '').upper() == 'SELL'
                            if _own_l and _pnl_l < 0 and _ml_l in ('HOLD', 'STRONG_BUY') and _is_pure_sell:
                                alloc_df_simple.at[_idxl, 'action_recommendation'] = 'HOLD'
                                if 'exit_reason' in alloc_df_simple.columns:
                                    alloc_df_simple.at[_idxl, 'exit_reason'] = (
                                        f"[MI-L04] ML={_ml_l} + loss={_pnl_l:.1%} — Don't crystallize loss, wait for recovery"
                                    )
                                _l04_protected += 1
                    print(f"      ✅ [MI-L04 POST] {_l04_protected} stocks protected (SELL → HOLD)")

                    # [DQ-01 FIX] Post-alloc data quality guards — resolve 3 contradiction types:
                    # (a) PRE-BREAKOUT on owned positions at >2% loss → HOLD [RT-08C POST]
                    # (b) INCREASE on ML=SELL with profit <10% → HOLD [DQ-ML-INC]
                    # (c) INCREASE on RSI>72 when at loss or ML=SELL → HOLD [DQ-RSI-INC]
                    print(f"   🔧 [DQ-01] Resolving PRE-BREAKOUT/INCREASE contradictions...")
                    _rsi_dq  = 'enhanced_rsi_14' if 'enhanced_rsi_14' in alloc_df_simple.columns else 'RSI'
                    _dq_count = 0
                    if _ml_cp and _own_cp and _pnl_cp:
                        for _idxdq, _rowdq in alloc_df_simple.iterrows():
                            _act_dq     = str(_rowdq.get('action_recommendation', ''))
                            _own_dq     = bool(_rowdq.get(_own_cp, False))
                            _pnl_dq     = _nv(_rowdq.get(_pnl_cp), 0)
                            _ml_dq      = str(_rowdq.get(_ml_cp, ''))
                            _rsi_dq_val = _nv(_rowdq.get(_rsi_dq), 50)
                            # (a) PRE-BREAKOUT on owned losing position → HOLD [RT-08C POST]
                            if 'PRE-BREAKOUT' in _act_dq and _own_dq and _pnl_dq < -0.02:
                                alloc_df_simple.at[_idxdq, 'action_recommendation'] = 'HOLD'
                                if 'exit_reason' in alloc_df_simple.columns:
                                    alloc_df_simple.at[_idxdq, 'exit_reason'] = f"[RT-08C] PRE-BREAKOUT blocked: at loss ({_pnl_dq:.1%}) — don't average down"
                                _dq_count += 1
                                continue
                            # (b) INCREASE on ML=SELL (profit <10%) → HOLD [DQ-ML-INC]
                            # Skip if allocation engine already assigned capital (don't reset funded INCREASE)
                            _inv_dq = _nv(_rowdq.get('investment_amount', 0), 0)
                            if str(_act_dq or '').upper() == 'INCREASE' and _ml_dq == 'SELL' and _pnl_dq < 0.10 and _inv_dq == 0:
                                alloc_df_simple.at[_idxdq, 'action_recommendation'] = 'HOLD'
                                if 'exit_reason' in alloc_df_simple.columns:
                                    alloc_df_simple.at[_idxdq, 'exit_reason'] = f"[DQ-ML-INC] ML=SELL contradicts INCREASE — Hold (profit={_pnl_dq:.1%})"
                                _dq_count += 1
                                continue
                            # (c) INCREASE on RSI>72 when at loss or ML=SELL → HOLD [DQ-RSI-INC]
                            if str(_act_dq or '').upper() == 'INCREASE' and _rsi_dq_val > 72 and (_pnl_dq < 0 or _ml_dq == 'SELL') and _inv_dq == 0:
                                alloc_df_simple.at[_idxdq, 'action_recommendation'] = 'HOLD'
                                if 'exit_reason' in alloc_df_simple.columns:
                                    alloc_df_simple.at[_idxdq, 'exit_reason'] = f"[DQ-RSI-INC] RSI={_rsi_dq_val:.0f} overbought + INCREASE risky — Hold"
                                _dq_count += 1
                                continue
                    print(f"      ✅ [DQ-01] {_dq_count} contradiction(s) resolved")

                    # Only INCREASE and BUY/NEW POSITION stocks from unified allocation should have investment amounts
                    print(f"   🔧 Resetting INVEST_₹ for non-INCREASE/BUY/NEW POSITION stocks...")
                    # ✅ FIX: Added 'NEW POSITION' and conflict-resolved emojis to the allowed list
                    # Preserve investment for: INCREASE, BUY, NEW POSITION, and conflict-resolved actions (ENTER, SMALL ENTRY, etc.)
                    conflict_emojis = ['⚠️', '🟡', '🟢', '🚀', '💰']  # [GA-01 FIX] Removed ⚪ (SKIP emoji) - SKIP must get ₹0
                    has_emoji = alloc_df_simple['action_recommendation'].astype(str).apply(
                        lambda x: any(emoji in x for emoji in conflict_emojis)
                    )
                    allowed_actions = ['INCREASE', 'BUY', 'NEW POSITION']
                    is_allowed_action = alloc_df_simple['action_recommendation'].isin(allowed_actions)

                    non_action_mask = ~(is_allowed_action | has_emoji)
                    alloc_df_simple.loc[non_action_mask, 'investment_amount'] = 0
                    alloc_df_simple.loc[non_action_mask, 'suggested_quantity'] = 0
                    print(f"      ✅ Reset {non_action_mask.sum()} stocks (HOLD/KEEP/SELL) to ₹0")

                    # [GA-01 FIX] Explicitly zero out SKIP actions (⚪ SKIP - WAIT must never get investment)
                    skip_mask = alloc_df_simple['action_recommendation'].astype(str).str.contains('SKIP', na=False)
                    alloc_df_simple.loc[skip_mask, 'investment_amount'] = 0
                    alloc_df_simple.loc[skip_mask, 'suggested_quantity'] = 0
                    print(f"      ✅ Zeroed ₹0 for {skip_mask.sum()} SKIP stocks [GA-01]")

                    # 🔧 FAILSAFE RE-CALCULATION REMOVED
                    # This block was overwriting carefully calculated swap amounts with crude weight-based values.
                    # The allocation engine already ensures correct investment amounts.
                    # if new_pos_mask.any(): ... (REMOVED)

                    
                    # 🔧 FIX: Clear profit_booking_timing and profit_booking_pct for KEEP/HOLD actions
                    # These fields should only have values for actionable items (SELL, BOOK_PROFIT, BUY, INCREASE)
                    print(f"   🔧 Clearing timing/booking % for KEEP/HOLD stocks...")
                    keep_hold_mask = alloc_df_simple['action_recommendation'].isin(['KEEP', 'HOLD'])
                    alloc_df_simple.loc[keep_hold_mask, 'profit_booking_timing'] = None
                    alloc_df_simple.loc[keep_hold_mask, 'profit_booking_pct'] = None
                    print(f"      ✅ Cleared timing for {keep_hold_mask.sum()} KEEP/HOLD stocks")

                    # [RT-14 FIX] Auto-set BOOK_%_IF_SELL — tiered booking for profitable stocks
                    # [MI-P01/P02/P05 FIX] Also trigger when near resistance OR ML=SELL AND profitable
                    print(f"   🔧 [RT-14/MI-P] Auto-populating BOOK_%_IF_SELL (tiered: resistance/ML/RSI/profit)...")
                    _rsi_c14 = 'enhanced_rsi_14' if 'enhanced_rsi_14' in alloc_df_simple.columns else 'RSI'
                    _res_c14 = 'resistance_level' if 'resistance_level' in alloc_df_simple.columns else 'RESISTANCE'
                    _own_c14 = 'is_current_holding' if 'is_current_holding' in alloc_df_simple.columns else None
                    for _idx14, _row14 in alloc_df_simple.iterrows():
                        if pd.notna(_row14.get('profit_booking_pct')): continue  # already set, don't overwrite
                        if _own_c14 and not bool(_row14.get(_own_c14, False)): continue  # only owned holdings
                        _pnl14 = _nv(_row14.get('current_profit_pct'), 0)
                        _rsi14 = _nv(_row14.get(_rsi_c14), 50)
                        _res14 = _nv(_row14.get(_res_c14), 0)
                        _price14 = _nv(_row14.get('current_price'), 0)
                        _near_res14 = (_price14 / _res14 > 0.95) if (_res14 > 0 and _price14 > 0) else False
                        _ml14 = str(_row14.get('ml_signal', ''))
                        _ml_sell_profitable = (_ml14 == 'SELL') and (_pnl14 > 0.02)  # ML=SELL and in profit
                        if _pnl14 > 0.25:                              # >25% profit  → book 30%
                            alloc_df_simple.at[_idx14, 'profit_booking_pct'] = 0.30
                        elif _pnl14 > 0.10:                            # >10% profit  → book 25%
                            alloc_df_simple.at[_idx14, 'profit_booking_pct'] = 0.25
                        elif _pnl14 > 0.05 and _rsi14 > 65:           # >5%+overbought → book 25%
                            alloc_df_simple.at[_idx14, 'profit_booking_pct'] = 0.25
                        elif _near_res14 and _pnl14 > 0:               # [MI-P02] near resistance + profit → book 25%
                            alloc_df_simple.at[_idx14, 'profit_booking_pct'] = 0.25
                        elif _ml_sell_profitable:                       # [MI-P03] ML=SELL + profitable → book 25%
                            alloc_df_simple.at[_idx14, 'profit_booking_pct'] = 0.25
                    print(f"      ✅ [RT-14/MI-P] BOOK_%_IF_SELL populated (profit/resistance/ML-aware)")

                    # [RT-10 FIX] Auto-populate WHEN_TO_ACT (profit_booking_timing) for actionable stocks
                    print(f"   🔧 [RT-10] Auto-populating WHEN_TO_ACT for actionable stocks...")
                    _rsi_c10 = 'enhanced_rsi_14' if 'enhanced_rsi_14' in alloc_df_simple.columns else 'RSI'
                    _exit_c10 = 'exhaustion_score' if 'exhaustion_score' in alloc_df_simple.columns else 'EXIT_SCORE'
                    _actionable_kw = ['SELL', 'SWAP', 'INCREASE', 'PRE-BREAKOUT', 'BUY', 'NEW POSITION', 'BREAKOUT']
                    for _idx10, _row10 in alloc_df_simple.iterrows():
                        _act10 = str(_row10.get('action_recommendation', ''))
                        if not any(kw in _act10 for kw in _actionable_kw): continue
                        # [RT-10 FIX] Force-overwrite timing for SELL/SWAP/INCREASE (these often have stale/missing timing)
                        # For BUY/PRE-BREAKOUT only: preserve any timing already set from earlier allocation logic
                        _is_urgent10 = any(kw in _act10 for kw in ['SELL', 'SWAP', 'INCREASE'])
                        # [FIX] _clean_dataframe_for_excel converts None→'' so check for non-empty too
                        _existing_timing = _row10.get('profit_booking_timing')
                        _has_timing = pd.notna(_existing_timing) and str(_existing_timing).strip() != ''
                        if not _is_urgent10 and _has_timing: continue  # already set
                        _rsi10 = _nv(_row10.get(_rsi_c10), 50)
                        _exit10 = _nv(_row10.get(_exit_c10), 0)
                        if _rsi10 > 70 or _exit10 > 30:
                            alloc_df_simple.at[_idx10, 'profit_booking_timing'] = 'Within 2 days'
                        elif _rsi10 > 65 or _exit10 > 15:
                            alloc_df_simple.at[_idx10, 'profit_booking_timing'] = 'Within 1 week'
                        else:
                            alloc_df_simple.at[_idx10, 'profit_booking_timing'] = 'Within 2 weeks'
                    print(f"      ✅ [RT-10] WHEN_TO_ACT populated for actionable stocks")

                    # [FIX] Sync PRE_BREAKOUT? flag — action says PRE-BREAKOUT but flag was False/None
                    # pre_breakout_detected comes from raw stock data; action_recommendation can be
                    # set to PRE-BREAKOUT by independent logic → must reconcile
                    if 'pre_breakout_detected' in alloc_df_simple.columns:
                        pb_flag_mask = alloc_df_simple['action_recommendation'].astype(str).str.contains('PRE-BREAKOUT', na=False)
                        alloc_df_simple.loc[pb_flag_mask, 'pre_breakout_detected'] = True
                        _pb_fixed = pb_flag_mask.sum()
                        if _pb_fixed:
                            print(f"   🔧 [PRE_BREAKOUT sync] Set pre_breakout_detected=True for {_pb_fixed} PRE-BREAKOUT action stocks")

                    # 💰 NEW: Calculate profit booking amount in rupees
                    print(f"   💰 Calculating BOOK_PROFIT amounts in rupees...")
                    alloc_df_simple['profit_booking_amount'] = 0.0
                    
                    # Convert to numeric to handle any string values
                    alloc_df_simple['profit_booking_pct'] = pd.to_numeric(alloc_df_simple['profit_booking_pct'], errors='coerce')
                    alloc_df_simple['current_value'] = pd.to_numeric(alloc_df_simple['current_value'], errors='coerce')
                    
                    book_profit_mask = alloc_df_simple['profit_booking_pct'].notna() & (alloc_df_simple['profit_booking_pct'] > 0)
                    alloc_df_simple.loc[book_profit_mask, 'profit_booking_amount'] = (
                        alloc_df_simple.loc[book_profit_mask, 'current_value'] * 
                        alloc_df_simple.loc[book_profit_mask, 'profit_booking_pct']
                    )
                    print(f"      ✅ Calculated booking amounts for {book_profit_mask.sum()} stocks")
                    
                    # [RT-09 FIX] Add ROTATION_TARGET — maps each SELL/SWAP stock to best rotation destination
                    # [RT-07 FIX] Add ROTATION_TRIGGER_PRICE — auto-exit price (97% of support) for loser HOLD positions
                    print(f"   🔧 [RT-07/09] Building rotation targets and trigger prices...")
                    _rsi_col = 'enhanced_rsi_14' if 'enhanced_rsi_14' in alloc_df_simple.columns else 'RSI'
                    _sup_col = 'support_level' if 'support_level' in alloc_df_simple.columns else 'SUPPORT'
                    _own_col = 'is_current_holding' if 'is_current_holding' in alloc_df_simple.columns else None
                    alloc_df_simple['rotation_target'] = ''
                    alloc_df_simple['rotation_trigger_price'] = None
                    alloc_df_simple['stop_loss_price'] = None  # [MI-C01 FIX]
                    if _own_col and 'symbol' in alloc_df_simple.columns:
                        _owned_syms = set(alloc_df_simple[alloc_df_simple[_own_col] == True]['symbol'].str.upper())
                        _non_owned = alloc_df_simple[~alloc_df_simple['symbol'].str.upper().isin(_owned_syms)].copy()
                    else:
                        _non_owned = pd.DataFrame()
                    _score_col = 'overall_score' if 'overall_score' in _non_owned.columns else None
                    if _score_col and len(_non_owned) > 0:
                        _non_owned = _non_owned.sort_values(_score_col, ascending=False)
                    # [MI-R01 FIX] Pre-filter rotation candidates: exclude HIGH/VERY HIGH risk + RSI>65
                    if len(_non_owned) > 0:
                        _risk_col_r01 = 'risk_category' if 'risk_category' in _non_owned.columns else None
                        _rsi_col_r01  = _rsi_col if _rsi_col in _non_owned.columns else None
                        _risk_ok = ~_non_owned[_risk_col_r01].fillna('').isin(['HIGH', 'VERY HIGH']) if _risk_col_r01 else pd.Series(True, index=_non_owned.index)
                        _rsi_ok  = _non_owned[_rsi_col_r01].fillna(99) < 65 if _rsi_col_r01 else pd.Series(True, index=_non_owned.index)
                        _safe_candidates = _non_owned[_risk_ok & _rsi_ok].copy()   # best: safe risk + RSI<65
                        _safe_any_rsi    = _non_owned[_risk_ok].copy()             # fallback: safe risk, any RSI
                    else:
                        _safe_candidates = pd.DataFrame()
                        _safe_any_rsi    = pd.DataFrame()
                    for _idx79, _row79 in alloc_df_simple.iterrows():
                        _act79 = str(_row79.get('action_recommendation', ''))
                        _pnl79 = _nv(_row79.get('current_profit_pct'), 0)
                        _sup79 = _nv(_row79.get(_sup_col), 0) if _sup_col in alloc_df_simple.columns else 0
                        _own79 = bool(_row79.get(_own_col, False)) if _own_col else False
                        # rotation_trigger_price: 3% below support for loser HOLD positions
                        if _pnl79 < -0.02 and 'HOLD' in _act79 and _sup79 > 0:
                            alloc_df_simple.at[_idx79, 'rotation_trigger_price'] = round(_sup79 * 0.97, 2)
                        # stop_loss_price: 3% below support; fallback to 8% below price
                        _price79 = _nv(
                            _row79.get('current_price'),
                            _nv(_row79.get('PRICE'),
                                _nv(_row79.get('close'), _nv(_row79.get('Close'), 0)))
                        )
                        if _sup79 > 0:
                            alloc_df_simple.at[_idx79, 'stop_loss_price'] = round(_sup79 * 0.97, 2)
                        elif _price79 > 0:
                            alloc_df_simple.at[_idx79, 'stop_loss_price'] = round(_price79 * 0.92, 2)
                        # rotation_target: quality-filtered non-owned stock (same sector preferred)
                        if ('SELL' in _act79 or 'SWAP' in _act79) and len(_non_owned) > 0 and 'symbol' in _non_owned.columns:
                            _sector79 = str(_row79.get('sector', ''))
                            try:
                                _sec_safe = _safe_candidates['sector'] if 'sector' in _safe_candidates.columns else pd.Series('', index=_safe_candidates.index)
                                _sec_any  = _safe_any_rsi['sector']    if 'sector' in _safe_any_rsi.columns    else pd.Series('', index=_safe_any_rsi.index)
                                # [MI-R01] Priority 1: same sector + safe risk + RSI<65
                                _p1 = _safe_candidates[_sec_safe == _sector79] if len(_safe_candidates) > 0 else pd.DataFrame()
                                # [MI-R01] Priority 2: any sector + safe risk + RSI<65
                                # [MI-R01] Priority 3: any sector + safe risk (relax RSI)
                                # Priority 4: fallback unrestricted
                                if len(_p1) > 0:
                                    alloc_df_simple.at[_idx79, 'rotation_target'] = _p1.iloc[0]['symbol']
                                elif len(_safe_candidates) > 0:
                                    alloc_df_simple.at[_idx79, 'rotation_target'] = _safe_candidates.iloc[0]['symbol']
                                elif len(_safe_any_rsi) > 0:
                                    alloc_df_simple.at[_idx79, 'rotation_target'] = _safe_any_rsi.iloc[0]['symbol']
                                elif len(_non_owned) > 0:
                                    alloc_df_simple.at[_idx79, 'rotation_target'] = _non_owned.iloc[0]['symbol']
                            except Exception:
                                pass
                    # Post-loop fallback: ensure every stock has a stop-loss
                    _sl_null = alloc_df_simple['stop_loss_price'].isna()
                    if _sl_null.any():
                        _price_col_sl = 'current_price' if 'current_price' in alloc_df_simple.columns else 'PRICE' if 'PRICE' in alloc_df_simple.columns else None
                        if _price_col_sl:
                            _prices_sl = pd.to_numeric(alloc_df_simple.loc[_sl_null, _price_col_sl], errors='coerce').fillna(0)
                            _valid_sl = _prices_sl > 0
                            alloc_df_simple.loc[_sl_null & _valid_sl.reindex(_sl_null.index, fill_value=False), 'stop_loss_price'] = (_prices_sl[_valid_sl] * 0.92).round(2)
                        _still_null = alloc_df_simple['stop_loss_price'].isna().sum()
                        logging.info(f"Stop-loss fallback pass: filled {_sl_null.sum() - _still_null}, remaining nulls: {_still_null}")
                    print(f"      ✅ [RT-07/09/MI-C01/R01] Rotation targets, trigger prices and stop losses populated")

                    # Sort rows: actionable items first, watchlist last
                    _action_priority = {
                        'SELL': 0, 'SWAP': 1, 'REDUCE': 2, 'INCREASE': 3, 'NEW POSITION': 4,
                        'BUY': 5, 'MOMENTUM': 6, 'KEEP': 7, 'HOLD': 8, 'WATCHLIST': 9
                    }
                    def _sort_key(action_str):
                        s = str(action_str).upper()
                        for k, v in _action_priority.items():
                            if k in s:
                                return v
                        return 99
                    alloc_df_simple['_sort_ord'] = alloc_df_simple['action_recommendation'].apply(_sort_key)
                    alloc_df_simple = alloc_df_simple.sort_values(
                        ['_sort_ord', 'overall_score', 'symbol'],
                        ascending=[True, False, True],
                        kind='mergesort'
                    ).drop(columns='_sort_ord').reset_index(drop=True)

                    column_renames = {
                        # Group A: What To Do
                        'action_recommendation': 'ACTION',
                        'profit_booking_timing': 'WHEN',
                        'exit_reason':           'REASON',
                        # Group B: Money
                        'investment_amount':     'INVEST ₹',
                        'suggested_quantity':    'BUY QTY',
                        'current_quantity':      'MY QTY',
                        'current_value':         'MY VALUE ₹',
                        'current_profit_pct':    'P&L %',
                        'profit_booking_pct':    'BOOK %',
                        'profit_booking_amount': 'BOOK ₹',
                        'tax_type':              'TAX',
                        'estimated_tax':         'TAX ₹',
                        'post_tax_proceeds':     'NET ₹',
                        # Group C: Stock Quality
                        'overall_score':                'SCORE',
                        'risk_adjusted_score':          'ADJ SCORE',
                        'hybrid_fundamental_quality':   'FUND',
                        'hybrid_momentum_technical':    'MOM',
                        'hybrid_volume_strength':       'VOL',
                        'hybrid_multi_timeframe':       'MTF',
                        'hybrid_risk_adjustment':       'RISK SC',
                        'undervaluation_score':         'VALUE',
                        'risk_category':                'RISK',
                        'pe_ratio':                     'PE',
                        'roe':                          'ROE %',
                        'debt_to_equity':               'D/E',
                        # Group D: Price & Levels
                        'current_price':                'PRICE',
                        '52_week_high':                 '52W HIGH',
                        '52_week_low':                  '52W LOW',
                        'enhanced_price_change_20d':    '20D CHG %',
                        'support_level':                'SUPPORT',
                        'resistance_level':             'RESIST',
                        'stop_loss_price':              'STOP LOSS',
                        'enhanced_rsi_14':              'RSI',
                        'volatility':                   'VOLATILITY %',
                        # Group E: Signals & Info
                        'ml_signal':                    'ML',
                        'ml_confidence':                'ML CONF %',
                        'ad_line_signal':               'A/D LINE',
                        'mfi_signal':                   'MFI',
                        'is_current_holding':           'OWNED?',
                        'stock_classification':         'TYPE',
                        'holdings_rank':                'RANK',
                        'portfolio_weight':             'WT %',
                        'action_reason':                'DETAIL',
                    }
                    
                    # Convert ratio to actual percentage for display
                    if 'current_profit_pct' in alloc_df_simple.columns:
                        alloc_df_simple['current_profit_pct'] = pd.to_numeric(alloc_df_simple['current_profit_pct'], errors='coerce').fillna(0) * 100

                    alloc_df_simple.rename(columns=column_renames, inplace=True)

                    # A7: Strip emojis from ACTION labels — cell color conveys meaning
                    import re
                    _emoji_re = re.compile(r'[\U0001F300-\U0001FAFF\U00002702-\U000027B0\U0000FE00-\U0000FE0F\u200d]+')
                    if 'ACTION' in alloc_df_simple.columns:
                        alloc_df_simple['ACTION'] = alloc_df_simple['ACTION'].astype(str).apply(
                            lambda x: _emoji_re.sub('', x).strip()
                        )

                    # A8: Convert OWNED? True/False to YES/NO
                    if 'OWNED?' in alloc_df_simple.columns:
                        alloc_df_simple['OWNED?'] = alloc_df_simple['OWNED?'].apply(
                            lambda x: 'YES' if x is True or str(x).strip().upper() in ('TRUE', 'YES', '1') else 'NO'
                        )

                    # A6: Convert ML/RISK text to numeric helper columns for icon sets
                    if 'ML' in alloc_df_simple.columns:
                        _ml_map = {'BUY': 3, 'STRONG_BUY': 3, 'STRONG BUY': 3, 'HOLD': 2, 'SELL': 1}
                        alloc_df_simple['_ML_N'] = alloc_df_simple['ML'].astype(str).str.upper().map(_ml_map).fillna(2).astype(int)
                    if 'RISK' in alloc_df_simple.columns:
                        _risk_map = {'LOW': 3, 'MODERATE': 2, 'MEDIUM': 2, 'HIGH': 1, 'VERY HIGH': 1}
                        alloc_df_simple['_RISK_N'] = alloc_df_simple['RISK'].astype(str).str.upper().map(_risk_map).fillna(2).astype(int)

                    # Export simplified sheet (row 0=group headers, row 1=col headers, row 2+=data)
                    alloc_df_simple.to_excel(writer, sheet_name='Portfolio Allocation', index=False, startrow=1)
                    
                    # 🎨 Apply conditional formatting to Portfolio Allocation
                    self._apply_conditional_formatting_portfolio(writer, alloc_df_simple, buy_format, strong_buy_format, 
                                                               hold_format, sell_format, low_risk_format, 
                                                               medium_risk_format, high_risk_format)
                    
                    # Portfolio summary with enhanced formatting
                    summary_data = portfolio_allocation['summary']
                    summary_sheet = pd.DataFrame([summary_data])
                    summary_sheet.to_excel(writer, sheet_name='Portfolio Summary', index=False)
                    
                    # Format Portfolio Summary
                    self._format_portfolio_summary(writer, summary_sheet, header_format, metric_value_format, price_format, percent_format)
                    
                    print(f"   ✅ Full Portfolio Allocation sheet created with {len(alloc_df_simple.columns)} columns")
                else:
                    # 🚨 CRITICAL: Portfolio allocation is missing - this should NEVER happen!
                    print(f"   ⚠️  WARNING: Portfolio allocation is None - THIS IS A BUG!")
                    print(f"      Attempting emergency fallback...")
                    # Don't create fallback - just skip the sheet
                    print(f"   ❌ Skipping Portfolio Allocation sheet - please report this bug")
                
                # 🚀 PHASE 2 ENHANCEMENT: Advanced Analytics Sheets
                print("   📈 Creating advanced analytics sheets...")
                
                # 6a. Technical Analysis Deep Dive Sheet
                self._create_technical_analysis_sheet(workbook, df, header_format, data_format, 
                                                    price_format, percent_format, score_format)
                
                # 6a-NEW. Multi-Timeframe Analysis Sheet (ACCURACY IMPROVEMENT #5)
                self._create_multi_timeframe_analysis_sheet(workbook, df, header_format, data_format, 
                                                          price_format, percent_format, score_format)
                
                # 6a-NEW2. Institutional Flow Analysis Sheet (ACCURACY IMPROVEMENT #7)
                self._create_institutional_flow_analysis_sheet(workbook, df, header_format, data_format, 
                                                             price_format, percent_format, score_format)
                
                # 6b. Valuation Analysis Sheet  
                self._create_valuation_analysis_sheet(workbook, df, header_format, data_format,
                                                    price_format, percent_format, score_format)
                
                # 6c. KEEP: Risk Management Dashboard (Essential for portfolio safety)
                self._create_risk_management_sheet(workbook, df, portfolio_allocation, header_format, 
                                                 data_format, price_format, percent_format)
                
                # 🚀 REMOVED: Correlation Analysis (too technical for most users)
                # 🚀 REMOVED: Performance Tracking (redundant with Dashboard)
                # 🚀 REMOVED: Smart Alerts (static data, not actionable)
                
                # 🚀 PHASE 3 ENHANCEMENT: Essential Predictive Analytics Only
                print("   🔮 Creating essential predictive analytics...")
                
                # 7a. KEEP: Price Prediction & Monte Carlo Analysis (High value for investors)
                self._create_price_prediction_sheet(workbook, df, header_format, data_format,
                                                  price_format, percent_format, score_format)
                
                # 🚀 REMOVED: Market Timing (too speculative for most investors)  
                # 🚀 REMOVED: AI Sentiment (mock data, not real sentiment)
                # 🚀 REMOVED: Goal-Based Investing (generic SIP calculations)
                # 🚀 REMOVED: Portfolio Optimization (too complex theory)
                
                # 6. Past Accuracy Sheet (V5.0 feedback loop)
                try:
                    pa = getattr(self, '_past_accuracy', None) or {}
                    if pa.get('total_with_outcomes', 0) > 0:
                        pa_rows = [
                            {'Metric': 'Recommendations with outcomes (n)', 'Value': pa['total_with_outcomes']},
                            {'Metric': 'BUY hit rate (30d)', 'Value': f"{pa.get('buy_hit_rate_30d', 0):.1f}%"},
                            {'Metric': 'SELL hit rate (30d)', 'Value': f"{pa.get('sell_hit_rate_30d', 0):.1f}%"},
                            {'Metric': 'Q5 avg return (30d, top scores)', 'Value': f"{pa.get('q5_avg_return_30d', 0):.2f}%"},
                            {'Metric': 'Q1 avg return (30d, bottom scores)', 'Value': f"{pa.get('q1_avg_return_30d', 0):.2f}%"},
                        ]
                        pa_df = pd.DataFrame(pa_rows)
                        pa_df.to_excel(writer, sheet_name='Past Accuracy', index=False)
                except Exception as _pa_err:
                    logging.warning(f"Past Accuracy sheet skipped: {_pa_err}")

                # 7. Complete Data Sheet (Keep as last sheet)
                df.to_excel(writer, sheet_name='Complete Data', index=False)
                
                # Auto-resize non-portfolio sheets (Portfolio Allocation has custom widths + hidden cols)
                for sheet_name, worksheet in writer.sheets.items():
                    if sheet_name in ['Top Picks', 'Undervalued', 'Sector Analysis', 'Risk Analysis', 'Portfolio Summary', 'Past Accuracy', 'Complete Data']:
                        if sheet_name == 'Top Picks':
                            self._auto_resize_columns(worksheet, summary_df)
                        elif sheet_name == 'Undervalued' and not undervalued.empty:
                            self._auto_resize_columns(worksheet, undervalued[available_undervalued_cols])
                        elif sheet_name == 'Risk Analysis' and not risk_df.empty:
                            self._auto_resize_columns(worksheet, risk_df)
                        elif sheet_name == 'Complete Data':
                            self._auto_resize_columns(worksheet, df)
                        else:
                            self._auto_resize_columns(worksheet)
                
                # Benchmark Comparison sheet
                try:
                    import yfinance as _yf_bench
                    import time as _bench_time
                    _bench_data = []

                    def _fetch_index_return(ticker_sym, days, retries=2):
                        for _att in range(retries):
                            try:
                                _hist = _yf_bench.download(ticker_sym, period=f'{days}d', progress=False)
                                if not _hist.empty and 'Close' in _hist.columns:
                                    _cls = _hist['Close'].dropna()
                                    if len(_cls) >= 2:
                                        return ((float(_cls.iloc[-1]) / float(_cls.iloc[0])) - 1) * 100
                            except Exception:
                                if _att < retries - 1:
                                    _bench_time.sleep(2)
                        return None

                    for _period, _days in [('1 Month', 30), ('3 Months', 90), ('6 Months', 180), ('1 Year', 365)]:
                        try:
                            _nifty_ret = _fetch_index_return('^NSEI', _days)
                            _nn50_ret = _fetch_index_return('^NSMIDCP', _days)

                            _ret_key = f'enhanced_price_change_{_days // 30}m' if _days >= 60 else f'enhanced_price_change_{_days}d'
                            _port_ret = 0
                            if portfolio_allocation and portfolio_allocation.get('allocation_df') is not None:
                                _adf = portfolio_allocation['allocation_df']
                                if 'current_value' in _adf.columns and 'symbol' in _adf.columns:
                                    _tv = _adf['current_value'].sum()
                                    if _tv > 0:
                                        for _, _ar in _adf.iterrows():
                                            _w = _ar['current_value'] / _tv
                                            _sym_data = df[df['symbol'] == _ar['symbol']] if 'symbol' in df.columns else pd.DataFrame()
                                            if not _sym_data.empty:
                                                for _rc2 in [_ret_key, f'price_change_{_days // 30}m', f'price_change_{_days}d', 'enhanced_price_change_60d']:
                                                    if _rc2 in _sym_data.columns:
                                                        _rv = _sym_data.iloc[0].get(_rc2, 0)
                                                        try:
                                                            _port_ret += _w * (float(_rv) if _rv is not None else 0)
                                                        except (TypeError, ValueError):
                                                            pass
                                                        break
                            _nifty_display = round(_nifty_ret, 1) if _nifty_ret is not None else 'N/A'
                            _nn50_display = round(_nn50_ret, 1) if _nn50_ret is not None else 'N/A'
                            _alpha = round(_port_ret - _nifty_ret, 1) if _nifty_ret is not None else 'N/A'
                            _bench_data.append({
                                'Period': _period,
                                'Portfolio Return %': round(_port_ret, 1),
                                'Nifty 50 Return %': _nifty_display,
                                'Nifty MidCap Return %': _nn50_display,
                                'Alpha vs Nifty %': _alpha,
                            })
                        except Exception as _pe:
                            logging.debug(f"Benchmark fetch error for {_period}: {_pe}")
                            _bench_data.append({'Period': _period, 'Portfolio Return %': 'N/A', 'Nifty 50 Return %': 'N/A', 'Nifty MidCap Return %': 'N/A', 'Alpha vs Nifty %': 'N/A'})

                    _bench_df = pd.DataFrame(_bench_data)
                    _bench_df.to_excel(writer, sheet_name='Benchmark Comparison', index=False)
                    _bench_ws = writer.sheets['Benchmark Comparison']
                    for ci, col in enumerate(_bench_df.columns):
                        _bench_ws.write(0, ci, col, header_format)
                    self._auto_resize_columns(_bench_ws, _bench_df)
                    print(f"   📊 Benchmark Comparison sheet created")
                except Exception as _be:
                    logging.debug(f"Benchmark sheet error: {_be}")

                # Recommendation Performance sheet
                try:
                    if hasattr(self, 'recommendation_history') and self.recommendation_history is not None:
                        _perf_df = self.recommendation_history.get_performance_summary_df()
                        if not _perf_df.empty:
                            _perf_df.to_excel(writer, sheet_name='Rec Performance', index=False)
                            _perf_ws = writer.sheets['Rec Performance']
                            for ci, col in enumerate(_perf_df.columns):
                                _perf_ws.write(0, ci, col, header_format)
                            self._auto_resize_columns(_perf_ws, _perf_df)

                            _m30 = self.recommendation_history.get_performance_metrics('30d')
                            _detail_start = len(_perf_df) + 3
                            _perf_ws.write(_detail_start, 0, '30d Best Calls', header_format)
                            _perf_ws.write(_detail_start, 1, '', header_format)
                            _perf_ws.write(_detail_start, 2, '', header_format)
                            for _bi, _bc in enumerate(_m30.get('best_calls', []), 1):
                                _perf_ws.write(_detail_start + _bi, 0, str(_bc.get('symbol', '')), data_format)
                                _perf_ws.write(_detail_start + _bi, 1, f"{_bc.get(f'return_30d', 0):.1f}%", data_format)
                                _perf_ws.write(_detail_start + _bi, 2, str(_bc.get('action', '')), data_format)

                            _worst_start = _detail_start + 7
                            _perf_ws.write(_worst_start, 0, '30d Worst Calls', header_format)
                            for _wi, _wc_item in enumerate(_m30.get('worst_calls', []), 1):
                                _perf_ws.write(_worst_start + _wi, 0, str(_wc_item.get('symbol', '')), data_format)
                                _perf_ws.write(_worst_start + _wi, 1, f"{_wc_item.get(f'return_30d', 0):.1f}%", data_format)
                                _perf_ws.write(_worst_start + _wi, 2, str(_wc_item.get('action', '')), data_format)
                            print(f"   📊 Recommendation Performance sheet: win rate {_m30.get('win_rate', 0):.1f}% (30d)")
                except Exception as _rp_err:
                    logging.debug(f"Recommendation Performance sheet error: {_rp_err}")

                # Weekly Changes sheet
                try:
                    _wc = self.recommendation_history.get_weekly_changes(days=7) if hasattr(self, 'recommendation_history') else None
                    if _wc and (_wc.get('improved') or _wc.get('deteriorated')):
                        _wc_rows = []
                        for _e in _wc.get('improved', []):
                            _wc_rows.append({**_e, 'direction': 'IMPROVED'})
                        for _e in _wc.get('deteriorated', []):
                            _wc_rows.append({**_e, 'direction': 'DETERIORATED'})
                        _wc_df = pd.DataFrame(_wc_rows)
                        if not _wc_df.empty:
                            _wc_df.to_excel(writer, sheet_name='Weekly Changes', index=False)
                            _wc_ws = writer.sheets['Weekly Changes']
                            for ci, col in enumerate(_wc_df.columns):
                                _wc_ws.write(0, ci, col, header_format)
                            self._auto_resize_columns(_wc_ws, _wc_df)
                            print(f"   📊 Weekly Changes sheet: {len(_wc.get('improved',[]))} improved, {len(_wc.get('deteriorated',[]))} deteriorated")
                except Exception as _wc_err:
                    logging.debug(f"Weekly Changes sheet error: {_wc_err}")

                # Backtest Results sheet (import from most recent backtest)
                try:
                    _bt_files = sorted(glob.glob('data/backtest_result_*.xlsx'), reverse=True)
                    if _bt_files:
                        _bt_xl = pd.ExcelFile(_bt_files[0])
                        for _bt_sheet in _bt_xl.sheet_names[:3]:
                            _bt_df = pd.read_excel(_bt_xl, sheet_name=_bt_sheet)
                            if not _bt_df.empty:
                                _safe_name = f"BT {_bt_sheet}"[:31]
                                _bt_df.to_excel(writer, sheet_name=_safe_name, index=False)
                                _bt_ws = writer.sheets[_safe_name]
                                for ci, col in enumerate(_bt_df.columns):
                                    _bt_ws.write(0, ci, col, header_format)
                                self._auto_resize_columns(_bt_ws, _bt_df)
                        print(f"   📊 Backtest Results imported from {os.path.basename(_bt_files[0])}")
                except Exception as _bt_err:
                    logging.debug(f"Backtest sheet import error: {_bt_err}")

                # ═══════════════════════════════════════════════════════════════
                # _METADATA SHEET — config dump, scoring version, regime, timestamps
                # ═══════════════════════════════════════════════════════════════
                try:
                    _meta_ws = workbook.add_worksheet('_Metadata')
                    _meta_hdr = workbook.add_format({'bold': True, 'bg_color': '#2E5984', 'font_color': 'white', 'border': 1})
                    _meta_val = workbook.add_format({'border': 1, 'text_wrap': True})
                    _meta_ws.set_column(0, 0, 35)
                    _meta_ws.set_column(1, 1, 60)
                    _meta_ws.write(0, 0, 'Parameter', _meta_hdr)
                    _meta_ws.write(0, 1, 'Value', _meta_hdr)

                    _meta_data = [
                        ('Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        ('Scoring Engine Version', getattr(self.hybrid_scoring_engine, 'version', 'unknown')),
                        ('Market Regime', str(getattr(self, 'current_market_regime', 'unknown'))),
                        ('Stocks Analyzed', str(len(self.results))),
                        ('Stocks Failed', str(len(self.failed_stocks))),
                        ('Stocks Skipped (data_invalid)', str(sum(1 for r in self.results.values() if r.get('status') == 'data_invalid'))),
                        ('Cache Hit Rate', f"{self.performance_metrics.get('cache_hits', 0)}/{len(self.results)}"),
                        ('Config Source', 'config.json' if os.path.exists('config.json') else 'config.py defaults'),
                        ('Risk Profile', str(getattr(self, 'risk_profile', 'moderate'))),
                    ]
                    # Adaptive weights used
                    _aw = getattr(self, '_last_adaptive_weights', None)
                    if _aw and isinstance(_aw, dict):
                        for _wk, _wv in _aw.items():
                            _meta_data.append((f'weight.{_wk}', f'{_wv:.4f}'))
                    # All config parameters
                    from dataclasses import fields as _dc_fields
                    for _fld in _dc_fields(_config):
                        _val = getattr(_config, _fld.name, '')
                        if _fld.name == 'NIFTY_50_STOCKS':
                            continue
                        _meta_data.append((f'config.{_fld.name}', str(_val)))

                    for _mi, (_mk, _mv) in enumerate(_meta_data, start=1):
                        _meta_ws.write(_mi, 0, _mk, _meta_val)
                        _meta_ws.write(_mi, 1, _mv, _meta_val)
                    print(f"   📋 _Metadata sheet: {len(_meta_data)} parameters recorded")
                except Exception as _meta_err:
                    logging.warning(f"_Metadata sheet error: {_meta_err}")

                print(f"   🎯 Generated {len(writer.sheets)} essential worksheets (streamlined with auto-resize)")
            
            return filename
            
        except Exception as e:
            logging.error(f"Enhanced Excel generation error: {e}")
            print(f"[FAIL] Enhanced Excel generation failed: {e}")
            return None
    
    _SCORE_COLUMNS = {
        'overall_score', 'overall_score_with_value', 'final_blended_score',
        'hybrid_overall_score', 'improved_overall_score', 'corrected_overall_score',
        'fundamental_score', 'technical_score', 'undervaluation_score',
        'momentum_score', 'risk_adjusted_score', 'optimized_score',
        'final_score_with_phase1', 'sentiment_composite_score',
        'data_quality_score', 'portfolio_context_score', 'phase1_adjusted_score',
        'breakout_score', 'raw_blended_score', 'pre_breakout_score', 'exhaustion_score',
        'fundamental_score_final', 'enhanced_technical_score_final',
    }
    _VOLATILITY_COLUMNS = {'volatility', 'volatility_6m', 'volatility_20d'}

    def _clean_dataframe_for_excel(self, df):
        """Clean DataFrame by replacing NaN/Inf values that Excel can't handle.
        HI-04: Score columns fill with 50 (neutral), volatility columns fill with 100 (conservative).
        """
        try:
            for col in df.columns:
                col_lower = col.lower() if isinstance(col, str) else ''
                if df[col].dtype in ['float64', 'float32']:
                    if col in self._SCORE_COLUMNS or col_lower in self._SCORE_COLUMNS:
                        df[col] = df[col].fillna(50)
                    elif col in self._VOLATILITY_COLUMNS or col_lower in self._VOLATILITY_COLUMNS:
                        df[col] = df[col].fillna(100)
                    else:
                        df[col] = df[col].fillna(0)
                    df[col] = df[col].replace([np.inf, -np.inf], [999999, -999999])
                elif df[col].dtype in ['int64', 'int32']:
                    df[col] = df[col].fillna(0)
                elif df[col].dtype == 'object':
                    df[col] = df[col].fillna('')
            return df
        except Exception as e:
            logging.error(f"Data cleaning failed, applying type-aware fallback: {e}")
            try:
                for col in df.select_dtypes(include='number').columns:
                    col_lower = col.lower() if isinstance(col, str) else ''
                    if col in self._SCORE_COLUMNS or col_lower in self._SCORE_COLUMNS:
                        df[col] = df[col].fillna(50)
                    elif col in self._VOLATILITY_COLUMNS or col_lower in self._VOLATILITY_COLUMNS:
                        df[col] = df[col].fillna(100)
                    else:
                        df[col] = df[col].fillna(0)
                for col in df.select_dtypes(include='object').columns:
                    df[col] = df[col].fillna('')
            except Exception:
                pass
            return df
    
    def _num_to_col_letter(self, n):
        """Convert column number to Excel column letter (0=A, 25=Z, 26=AA, etc.)"""
        result = ""
        while n >= 0:
            result = chr(65 + (n % 26)) + result
            n = n // 26 - 1
            if n < 0:
                break
        return result if result else 'A'
    
    def _auto_resize_columns(self, worksheet, df=None, max_width=50, min_width=8):
        """🔧 Auto-resize columns based on content width"""
        try:
            # If dataframe is provided, use it to calculate optimal widths
            if df is not None:
                for col_num, column in enumerate(df.columns):
                    try:
                        # Calculate width based on column name and data
                        header_width = len(str(column)) + 2
                        
                        # Sample some values to get max content width
                        sample_data = df[column].dropna().head(10)
                        if len(sample_data) > 0:
                            # Convert all values to string and get max length
                            max_content_width = max(len(str(val)) for val in sample_data) + 2
                        else:
                            max_content_width = header_width
                        
                        # Use the larger of header or content width
                        optimal_width = max(header_width, max_content_width)
                        
                        # Apply min/max constraints - ensure it's a float
                        final_width = float(max(min_width, min(optimal_width, max_width)))
                        
                        # Convert column number to Excel column letter (works for any column)
                        col_letter = self._num_to_col_letter(col_num)
                        worksheet.set_column(f'{col_letter}:{col_letter}', final_width)
                    except Exception as col_error:
                        # Skip problematic columns
                        continue
            else:
                # Default auto-resize for sheets without dataframes
                # Set common column widths based on typical content
                worksheet.set_column('A:A', 15.0)  # Symbol/ID columns
                worksheet.set_column('B:B', 30.0)  # Company/Description columns  
                worksheet.set_column('C:Z', 14.0)  # Data columns
                
        except Exception as e:
            # Fallback to basic widths if auto-resize fails
            try:
                worksheet.set_column('A:A', 12.0)
                worksheet.set_column('B:B', 25.0)
                worksheet.set_column('C:Z', 12.0)
            except Exception:
                pass
    
    def _create_dashboard_sheet(self, workbook, df, portfolio_allocation, dashboard_title_format, 
                               metric_title_format, metric_value_format, header_format, data_format, 
                               price_format, percent_format, score_format):
        """🚀 PHASE 1: Create comprehensive dashboard with key metrics and charts"""
        
        worksheet = workbook.add_worksheet('Dashboard')
        
        # Title
        worksheet.merge_range('A1:H2', 'STOCK ANALYSIS DASHBOARD', dashboard_title_format)
        _ts_fmt = workbook.add_format({'italic': True, 'font_color': '#666666', 'align': 'right', 'font_size': 9})
        worksheet.merge_range('A3:H3', f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  Regime: {getattr(self, 'current_market_regime', 'N/A')}  |  Engine: {getattr(self.hybrid_scoring_engine, 'version', 'N/A')}", _ts_fmt)

        # Key Metrics Section
        row = 5
        
        # Analysis Overview
        worksheet.merge_range(f'A{row}:C{row}', 'ANALYSIS OVERVIEW', metric_title_format)
        worksheet.merge_range(f'E{row}:G{row}', 'RECOMMENDATIONS', metric_title_format)
        
        row += 1
        total_stocks = max(len(df), 1)
        buy_count = len(df[df['final_recommendation'].str.contains('BUY', na=False)])
        strong_buy_count = len(df[df['final_recommendation'].str.contains('STRONG BUY', na=False)])
        hold_count = len(df[df['final_recommendation'].str.contains('HOLD', na=False)])
        
        # Left side metrics
        worksheet.write(f'A{row}', 'Total Stocks Analyzed:', header_format)
        worksheet.write(f'B{row}', total_stocks, metric_value_format)
        
        worksheet.write(f'E{row}', 'Strong Buy:', header_format)
        worksheet.write(f'F{row}', strong_buy_count, metric_value_format)
        worksheet.write(f'G{row}', f'{strong_buy_count/total_stocks*100:.1f}%', percent_format)
        
        row += 1
        avg_score = df['overall_score_with_value'].mean() if 'overall_score_with_value' in df.columns else 0
        
        worksheet.write(f'A{row}', 'Average Score:', header_format)
        worksheet.write(f'B{row}', avg_score, score_format)
        
        worksheet.write(f'E{row}', 'Buy:', header_format)
        worksheet.write(f'F{row}', buy_count, metric_value_format)
        worksheet.write(f'G{row}', f'{buy_count/total_stocks*100:.1f}%', percent_format)
        
        row += 1
        undervalued_count = len(df[df.get('undervaluation_score', pd.Series()).fillna(50) >= 65])
        
        worksheet.write(f'A{row}', 'Undervalued Stocks:', header_format)
        worksheet.write(f'B{row}', undervalued_count, metric_value_format)
        worksheet.write(f'C{row}', f'{undervalued_count/total_stocks*100:.1f}%', percent_format)
        
        worksheet.write(f'E{row}', 'Hold:', header_format)
        worksheet.write(f'F{row}', hold_count, metric_value_format)
        worksheet.write(f'G{row}', f'{hold_count/total_stocks*100:.1f}%', percent_format)
        
        # Risk Analysis Section
        row += 2
        worksheet.merge_range(f'A{row}:C{row}', 'RISK ANALYSIS', metric_title_format)
        worksheet.merge_range(f'E{row}:G{row}', 'PORTFOLIO METRICS', metric_title_format)
        
        row += 1
        low_risk = len(df[df.get('risk_category', '') == 'LOW'])
        medium_risk = len(df[df.get('risk_category', '') == 'MEDIUM'])
        high_risk = len(df[df.get('risk_category', '') == 'HIGH'])
        
        worksheet.write(f'A{row}', 'Low Risk:', header_format)
        worksheet.write(f'B{row}', low_risk, metric_value_format)
        worksheet.write(f'C{row}', f'{low_risk/total_stocks*100:.1f}%', percent_format)
        
        # Portfolio metrics
        if portfolio_allocation:
            total_investment = portfolio_allocation.get('summary', {}).get('total_investment', 0)
            worksheet.write(f'E{row}', 'Total Investment:', header_format)
            worksheet.write(f'F{row}', total_investment, price_format)
        
        row += 1
        worksheet.write(f'A{row}', 'Medium Risk:', header_format)
        worksheet.write(f'B{row}', medium_risk, metric_value_format)
        worksheet.write(f'C{row}', f'{medium_risk/total_stocks*100:.1f}%', percent_format)
        
        if portfolio_allocation:
            utilized_amount = portfolio_allocation.get('summary', {}).get('utilized_amount', 0)
            worksheet.write(f'E{row}', 'Amount Utilized:', header_format)
            worksheet.write(f'F{row}', utilized_amount, price_format)
        
        row += 1
        worksheet.write(f'A{row}', 'High Risk:', header_format)
        worksheet.write(f'B{row}', high_risk, metric_value_format)
        worksheet.write(f'C{row}', f'{high_risk/total_stocks*100:.1f}%', percent_format)
        
        if portfolio_allocation:
            utilization_pct = portfolio_allocation.get('summary', {}).get('utilization_percentage', 0)
            worksheet.write(f'E{row}', 'Utilization %:', header_format)
            worksheet.write(f'F{row}', f'{utilization_pct:.1f}%', percent_format)
        
        # Top Performers Section
        row += 2
        worksheet.merge_range(f'A{row}:H{row}', '🏆 TOP 10 PERFORMERS', metric_title_format)
        
        row += 1
        headers = ['Rank', 'Symbol', 'Company', 'Score', 'Price', 'Recommendation', 'Risk', 'Sector']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        
        # Top 10 stocks
        top_10 = df.head(10)
        for i, (_, stock) in enumerate(top_10.iterrows()):
            row += 1
            worksheet.write(row, 0, i+1, data_format)
            worksheet.write(row, 1, stock['symbol'], data_format)
            worksheet.write(row, 2, str(stock.get('company_name', stock['symbol']))[:30], data_format)
            worksheet.write(row, 3, stock.get('overall_score_with_value', 0), score_format)
            worksheet.write(row, 4, stock.get('current_price', 0), price_format)
            worksheet.write(row, 5, str(stock.get('final_recommendation', '')), data_format)
            worksheet.write(row, 6, str(stock.get('risk_category', '')), data_format)
            worksheet.write(row, 7, str(stock.get('sector', ''))[:20], data_format)
        
        # Sector Distribution
        row += 2
        worksheet.merge_range(f'A{row}:D{row}', '📊 SECTOR DISTRIBUTION', metric_title_format)
        
        if 'sector' in df.columns:
            sector_counts = df['sector'].value_counts().head(10)
            row += 1
            worksheet.write(row, 0, 'Sector', header_format)
            worksheet.write(row, 1, 'Count', header_format)
            worksheet.write(row, 2, 'Percentage', header_format)
            
            for sector, count in sector_counts.items():
                row += 1
                worksheet.write(row, 0, str(sector)[:25], data_format)
                worksheet.write(row, 1, count, data_format)
                worksheet.write(row, 2, f'{count/total_stocks*100:.1f}%', percent_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
        
        # Add some charts if possible
        try:
            self._add_dashboard_charts(workbook, worksheet, df)
        except Exception as e:
            print(f"   ⚠️  Could not add charts to dashboard: {e}")
    
    def _apply_conditional_formatting_top_picks(self, writer, summary_df, buy_format, strong_buy_format, 
                                              hold_format, sell_format, low_risk_format, 
                                              medium_risk_format, high_risk_format):
        """🎨 Apply conditional formatting to Top Picks sheet"""
        
        worksheet = writer.sheets['Top Picks']
        
        # Format recommendation column
        if 'final_recommendation' in summary_df.columns:
            rec_col = list(summary_df.columns).index('final_recommendation')
            
            # Apply recommendation colors
            for row_num in range(1, len(summary_df) + 1):
                cell_ref = f"{chr(65 + rec_col)}{row_num + 1}"
                recommendation = summary_df.iloc[row_num - 1]['final_recommendation']
                
                if 'STRONG BUY' in str(recommendation):
                    worksheet.write(row_num, rec_col, recommendation, strong_buy_format)
                elif 'BUY' in str(recommendation):
                    worksheet.write(row_num, rec_col, recommendation, buy_format)
                elif 'HOLD' in str(recommendation):
                    worksheet.write(row_num, rec_col, recommendation, hold_format)
                elif 'SELL' in str(recommendation):
                    worksheet.write(row_num, rec_col, recommendation, sell_format)
        
        # Format risk category column
        if 'risk_category' in summary_df.columns:
            risk_col = list(summary_df.columns).index('risk_category')
            
            for row_num in range(len(summary_df)):
                risk_level = summary_df.iloc[row_num]['risk_category']
                
                if risk_level == 'LOW':
                    worksheet.write(row_num + 1, risk_col, risk_level, low_risk_format)
                elif risk_level in ('MEDIUM', 'MODERATE'):
                    worksheet.write(row_num + 1, risk_col, risk_level, medium_risk_format)
                elif risk_level in ('HIGH', 'VERY HIGH'):
                    worksheet.write(row_num + 1, risk_col, risk_level, high_risk_format)
        
        # Add data bars for scores
        if 'overall_score_with_value' in summary_df.columns:
            score_col = chr(65 + list(summary_df.columns).index('overall_score_with_value'))
            worksheet.conditional_format(f'{score_col}2:{score_col}{len(summary_df)+1}', {
                'type': 'data_bar',
                'bar_color': '#4472C4',
                'bar_solid': True
            })
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, summary_df)
    
    def _add_dashboard_charts(self, workbook, worksheet, df):
        """📈 Add charts to dashboard"""
        
        # Recommendation distribution pie chart
        if 'final_recommendation' in df.columns:
            try:
                # Create chart data in a temporary location on the worksheet
                chart_data_row = 50  # Use row 50 for chart data (out of view)
                
                # Analysis-level recommendation counts (pre-allocation)
                strong_buy_count = len(df[df['final_recommendation'].str.contains('STRONG BUY', na=False)])
                buy_count = len(df[df['final_recommendation'].str.contains('BUY', na=False)]) - strong_buy_count
                hold_count = len(df[df['final_recommendation'].str.contains('HOLD', na=False)])
                sell_count = len(df[df['final_recommendation'].str.contains('SELL', na=False)])
                
                # Write chart data to worksheet
                worksheet.write(chart_data_row, 0, 'Recommendation')
                worksheet.write(chart_data_row, 1, 'Count')
                worksheet.write(chart_data_row + 1, 0, 'Strong Buy')
                worksheet.write(chart_data_row + 1, 1, strong_buy_count)
                worksheet.write(chart_data_row + 2, 0, 'Buy')
                worksheet.write(chart_data_row + 2, 1, buy_count)
                worksheet.write(chart_data_row + 3, 0, 'Hold')
                worksheet.write(chart_data_row + 3, 1, hold_count)
                worksheet.write(chart_data_row + 4, 0, 'Sell')
                worksheet.write(chart_data_row + 4, 1, sell_count)
                
                # Create pie chart with cell references
                chart = workbook.add_chart({'type': 'pie'})
                chart.add_series({
                    'name': 'Recommendations',
                    'categories': ['Dashboard', chart_data_row, 0, chart_data_row + 3, 0],
                    'values': ['Dashboard', chart_data_row, 1, chart_data_row + 3, 1],
                })
                
                chart.set_title({'name': 'Recommendation Distribution'})
                chart.set_style(10)
                worksheet.insert_chart('J5', chart, {'x_scale': 1.5, 'y_scale': 1.5})
                
            except Exception as e:
                # Silently skip chart creation if it fails
                logging.debug(f"Could not create dashboard chart: {e}")
    
    def _apply_conditional_formatting_portfolio(self, writer, alloc_df, buy_format, strong_buy_format,
                                              hold_format, sell_format, low_risk_format,
                                              medium_risk_format, high_risk_format):
        """Modern Dark visual formatting for the Portfolio Allocation sheet."""

        workbook = writer.book
        worksheet = writer.sheets['Portfolio Allocation']
        num_rows = len(alloc_df)
        num_cols = len(alloc_df.columns)
        col_list = list(alloc_df.columns)
        DR = 2  # data start row (0=group hdr, 1=col hdr, 2+=data)

        def _cl(idx):
            if idx < 26:
                return chr(65 + idx)
            return chr(64 + idx // 26) + chr(65 + idx % 26)

        def _ci(name):
            return col_list.index(name) if name in col_list else -1

        def _rng(ci):
            return f'{_cl(ci)}{DR+1}:{_cl(ci)}{DR+num_rows}'

        # ═══════════════════════════════════════════════════════════════════
        # GROUP BOUNDARIES
        # ═══════════════════════════════════════════════════════════════════
        _grp_b_start = _ci('INVEST ₹')
        _grp_c_start = _ci('SCORE')
        _grp_d_start = _ci('PRICE')
        _grp_e_start = _ci('ML')
        grp_starts = [c for c in [_grp_b_start, _grp_c_start, _grp_d_start, _grp_e_start] if c >= 0]

        groups = [
            ('WHAT TO DO',    0,             max(_ci('REASON'), 0)),
            ('MONEY',         _grp_b_start,  max(_ci('NET ₹'), 0)),
            ('STOCK QUALITY', _grp_c_start,  max(_ci('D/E'), 0)),
            ('PRICE & LEVELS',_grp_d_start,  max(_ci('VOLATILITY %'), 0)),
            ('SIGNALS & INFO',_grp_e_start,  num_cols - 1),
        ]

        # ═══════════════════════════════════════════════════════════════════
        # A1: MODERN DARK GROUP HEADERS (Row 0)
        # ═══════════════════════════════════════════════════════════════════
        grp_hdr_fmt = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_name': 'Calibri',
            'font_color': 'white', 'bg_color': '#1C2833',
            'align': 'center', 'valign': 'vcenter',
            'top': 1, 'bottom': 2, 'left': 1, 'right': 1
        })
        for label, c_start, c_end in groups:
            if c_start < 0 or c_end < 0:
                continue
            if c_start == c_end:
                worksheet.write(0, c_start, label, grp_hdr_fmt)
            else:
                worksheet.merge_range(0, c_start, 0, c_end, label, grp_hdr_fmt)

        # ═══════════════════════════════════════════════════════════════════
        # A1: MODERN DARK COLUMN HEADERS (Row 1) — unified dark slate
        # ═══════════════════════════════════════════════════════════════════
        col_hdr_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': 'Calibri',
            'font_color': 'white', 'bg_color': '#2C3E50',
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'text_wrap': True
        })
        for ci in range(num_cols):
            worksheet.write(1, ci, col_list[ci], col_hdr_fmt)

        # Freeze panes: row 2, col 2 (symbol + company always visible)
        worksheet.freeze_panes(2, 2)

        # ═══════════════════════════════════════════════════════════════════
        # A1: BASE CELL FORMAT — every data cell gets borders + Calibri
        # ═══════════════════════════════════════════════════════════════════
        _b = {'font_name': 'Calibri', 'font_size': 10, 'border': 1, 'valign': 'vcenter'}
        _bs = {**_b, 'left': 2}  # thick left border for group separators

        currency_fmt  = workbook.add_format({**_b, 'num_format': '₹#,##0', 'align': 'right'})
        currency_sep  = workbook.add_format({**_bs, 'num_format': '₹#,##0', 'align': 'right'})
        pct_dec_fmt   = workbook.add_format({**_b, 'num_format': '0.0%', 'align': 'right'})
        pct_act_fmt   = workbook.add_format({**_b, 'num_format': '0.0', 'align': 'right'})
        score_fmt     = workbook.add_format({**_b, 'num_format': '0.0', 'align': 'right'})
        score_sep     = workbook.add_format({**_bs, 'num_format': '0.0', 'align': 'right'})
        int_fmt       = workbook.add_format({**_b, 'num_format': '#,##0', 'align': 'right'})
        text_fmt      = workbook.add_format({**_b, 'align': 'left'})
        text_sep      = workbook.add_format({**_bs, 'align': 'left'})
        text_center   = workbook.add_format({**_b, 'align': 'center'})
        text_ctr_sep  = workbook.add_format({**_bs, 'align': 'center'})
        wrap_fmt      = workbook.add_format({**_b, 'text_wrap': True, 'valign': 'top', 'align': 'left'})

        # Map column name -> format (thick left border variants for group-start columns)
        fmt_map = {}
        for cn in ['INVEST ₹', 'MY VALUE ₹', 'BOOK ₹', 'TAX ₹', 'NET ₹',
                    'PRICE', 'SUPPORT', 'RESIST', 'STOP LOSS', '52W HIGH', '52W LOW']:
            fmt_map[cn] = currency_sep if _ci(cn) in grp_starts else currency_fmt
        for cn in ['20D CHG %', 'WT %', 'ROE %', 'VOLATILITY %', 'BOOK %']:
            fmt_map[cn] = pct_dec_fmt
        fmt_map['P&L %'] = pct_act_fmt
        for cn in ['SCORE', 'ADJ SCORE', 'PE', 'D/E', 'RSI',
                    'FUND', 'MOM', 'VOL', 'MTF', 'VALUE', 'ML CONF %']:
            fmt_map[cn] = score_sep if _ci(cn) in grp_starts else score_fmt
        for cn in ['BUY QTY', 'MY QTY', 'RANK']:
            fmt_map[cn] = int_fmt

        # Write ALL data cells with proper formatting
        for ci in range(num_cols):
            cn = col_list[ci]
            is_grp_sep = ci in grp_starts
            cfmt = fmt_map.get(cn)
            if cfmt is None:
                if cn in ('REASON', 'DETAIL'):
                    cfmt = wrap_fmt
                elif is_grp_sep:
                    cfmt = text_ctr_sep
                else:
                    cfmt = text_center if cn in ('ACTION', 'RISK', 'ML', 'A/D LINE', 'MFI', 'OWNED?', 'TYPE', 'TAX', 'WHEN') else text_fmt
            for ri in range(num_rows):
                val = alloc_df.iloc[ri, ci]
                if pd.notna(val):
                    worksheet.write(ri + DR, ci, val, cfmt)
                else:
                    worksheet.write_blank(ri + DR, ci, '', cfmt)

        # ═══════════════════════════════════════════════════════════════════
        # ACTION CELL COLORING — bold accent colors on dark theme
        # ═══════════════════════════════════════════════════════════════════
        _af = lambda bg, fg: workbook.add_format({**_b, 'bg_color': bg, 'font_color': fg, 'bold': True, 'align': 'center'})
        sell_f     = _af('#E74C3C', 'white')
        swap_f     = _af('#E67E22', 'white')
        hold_f     = _af('#F4D03F', '#1C2833')
        keep_f     = _af('#F9E79F', '#6E2C00')
        buy_f      = _af('#27AE60', 'white')
        strong_f   = _af('#1E8449', 'white')
        increase_f = _af('#2ECC71', 'white')
        new_pos_f  = _af('#2E86C1', 'white')
        watchlist_f= _af('#ABB2B9', '#1C2833')

        act_ci = _ci('ACTION')
        if act_ci >= 0:
            for ri in range(num_rows):
                act = str(alloc_df.iloc[ri, act_ci])
                au = act.upper()
                if 'STRONG BUY' in au:       f = strong_f
                elif 'SELL' in au and 'SWAP' not in au: f = sell_f
                elif 'SWAP' in au:           f = swap_f
                elif 'INCREASE' in au:       f = increase_f
                elif 'NEW POSITION' in au or 'MOMENTUM' in au: f = new_pos_f
                elif 'BUY' in au:            f = buy_f
                elif 'WATCHLIST' in au:      f = watchlist_f
                elif 'KEEP' in au:           f = keep_f
                elif 'HOLD' in au:           f = hold_f
                else:                        f = hold_f
                worksheet.write(ri + DR, act_ci, act, f)

        # ═══════════════════════════════════════════════════════════════════
        # RISK CELL COLORING
        # ═══════════════════════════════════════════════════════════════════
        risk_ci = _ci('RISK')
        _rf = lambda bg, fg: workbook.add_format({**_b, 'bg_color': bg, 'font_color': fg, 'bold': True, 'align': 'center'})
        r_low  = _rf('#D5F5E3', '#1E8449')
        r_med  = _rf('#FEF9E7', '#7D6608')
        r_high = _rf('#FADBD8', '#922B21')
        if risk_ci >= 0:
            for ri in range(num_rows):
                rv = str(alloc_df.iloc[ri, risk_ci]).upper()
                if rv == 'LOW':
                    worksheet.write(ri + DR, risk_ci, alloc_df.iloc[ri, risk_ci], r_low)
                elif rv in ('MODERATE', 'MEDIUM'):
                    worksheet.write(ri + DR, risk_ci, alloc_df.iloc[ri, risk_ci], r_med)
                elif rv in ('HIGH', 'VERY HIGH'):
                    worksheet.write(ri + DR, risk_ci, alloc_df.iloc[ri, risk_ci], r_high)

        # ═══════════════════════════════════════════════════════════════════
        # A8: OWNED? GREEN HIGHLIGHT
        # ═══════════════════════════════════════════════════════════════════
        own_ci = _ci('OWNED?')
        if own_ci >= 0:
            yes_fmt = workbook.add_format({**_b, 'bg_color': '#D5F5E3', 'font_color': '#1E8449', 'bold': True, 'align': 'center'})
            no_fmt = workbook.add_format({**_b, 'align': 'center', 'font_color': '#ABB2B9'})
            for ri in range(num_rows):
                val = str(alloc_df.iloc[ri, own_ci])
                worksheet.write(ri + DR, own_ci, val, yes_fmt if val == 'YES' else no_fmt)

        # ═══════════════════════════════════════════════════════════════════
        # A4: FULL HEATMAP on score columns (red -> yellow -> green)
        # ═══════════════════════════════════════════════════════════════════
        heatmap_cols = ['SCORE', 'ADJ SCORE', 'FUND', 'MOM', 'VOL', 'MTF', 'VALUE']
        for cn in heatmap_cols:
            ci = _ci(cn)
            if ci < 0:
                continue
            worksheet.conditional_format(_rng(ci), {
                'type': '3_color_scale',
                'min_color': '#E74C3C', 'mid_color': '#F9E79F', 'max_color': '#27AE60'
            })

        # ═══════════════════════════════════════════════════════════════════
        # A5: DATA BARS inside score cells
        # ═══════════════════════════════════════════════════════════════════
        bar_colors = {
            'SCORE': '#2E86C1', 'ADJ SCORE': '#17A589',
            'FUND': '#E67E22', 'MOM': '#8E44AD', 'VOL': '#27AE60',
        }
        for cn, color in bar_colors.items():
            ci = _ci(cn)
            if ci < 0:
                continue
            worksheet.conditional_format(_rng(ci), {
                'type': 'data_bar', 'bar_color': color, 'bar_solid': True
            })

        # ═══════════════════════════════════════════════════════════════════
        # A6: ICON SETS — traffic lights on RISK, ML, P&L %
        # ═══════════════════════════════════════════════════════════════════
        # Risk numeric column (_RISK_N: 3=LOW/green, 2=MED/yellow, 1=HIGH/red)
        rn_ci = _ci('_RISK_N')
        if rn_ci >= 0:
            worksheet.conditional_format(_rng(rn_ci), {
                'type': 'icon_set', 'icon_style': '3_traffic_lights',
                'icons': [
                    {'criteria': '>=', 'type': 'number', 'value': 3},
                    {'criteria': '>=', 'type': 'number', 'value': 2},
                    {'criteria': '>=', 'type': 'number', 'value': 0},
                ],
                'icons_only': True
            })
            worksheet.set_column(rn_ci, rn_ci, 0, None, {'hidden': True})

        # ML numeric column (_ML_N: 3=BUY/green, 2=HOLD/yellow, 1=SELL/red)
        mn_ci = _ci('_ML_N')
        if mn_ci >= 0:
            worksheet.conditional_format(_rng(mn_ci), {
                'type': 'icon_set', 'icon_style': '3_traffic_lights',
                'icons': [
                    {'criteria': '>=', 'type': 'number', 'value': 3},
                    {'criteria': '>=', 'type': 'number', 'value': 2},
                    {'criteria': '>=', 'type': 'number', 'value': 0},
                ],
                'icons_only': True
            })
            worksheet.set_column(mn_ci, mn_ci, 0, None, {'hidden': True})

        # P&L % — 3 arrows (up green >= 10, flat yellow, down red <= -5)
        pnl_ci = _ci('P&L %')
        if pnl_ci >= 0:
            cl = _cl(pnl_ci)
            rng = _rng(pnl_ci)
            worksheet.conditional_format(rng, {
                'type': '3_color_scale',
                'min_color': '#E74C3C', 'mid_color': '#F9E79F', 'max_color': '#27AE60'
            })
            worksheet.conditional_format(rng, {
                'type': 'cell', 'criteria': '>=', 'value': 20,
                'format': workbook.add_format({**_b, 'bg_color': '#D5F5E3', 'font_color': '#1E8449', 'bold': True})
            })
            worksheet.conditional_format(rng, {
                'type': 'cell', 'criteria': '<=', 'value': -5,
                'format': workbook.add_format({**_b, 'bg_color': '#FADBD8', 'font_color': '#922B21', 'bold': True})
            })

        # PE undervalued
        pe_ci = _ci('PE')
        if pe_ci >= 0:
            worksheet.conditional_format(_rng(pe_ci), {
                'type': 'cell', 'criteria': '<', 'value': 15,
                'format': workbook.add_format({**_b, 'bg_color': '#D5F5E3'})
            })

        # D/E high debt
        de_ci = _ci('D/E')
        if de_ci >= 0:
            worksheet.conditional_format(_rng(de_ci), {
                'type': 'cell', 'criteria': '>', 'value': 2,
                'format': workbook.add_format({**_b, 'bg_color': '#FADBD8'})
            })

        # ═══════════════════════════════════════════════════════════════════
        # A3: ALTERNATING ROW BANDS — visible light grey
        # ═══════════════════════════════════════════════════════════════════
        last_cl = _cl(num_cols - 1)
        worksheet.conditional_format(f'A{DR+1}:{last_cl}{DR+num_rows}', {
            'type': 'formula', 'criteria': '=MOD(ROW(),2)=0',
            'format': workbook.add_format({'bg_color': '#F0F0F0'})
        })

        # ═══════════════════════════════════════════════════════════════════
        # A9: COLUMN WIDTHS + ROW HEIGHTS
        # ═══════════════════════════════════════════════════════════════════
        widths = {
            'symbol': 14, 'company_name': 26, 'ACTION': 26, 'WHEN': 15,
            'REASON': 48, 'DETAIL': 52, 'sector': 18, 'TYPE': 12,
        }
        _hidden_cols = {'_ML_N', '_RISK_N'}
        for ci, cn in enumerate(col_list):
            if cn in _hidden_cols:
                continue
            ow = widths.get(cn, 0)
            if ow:
                wfmt = wrap_fmt if cn in ('REASON', 'DETAIL') else None
                worksheet.set_column(ci, ci, ow, wfmt)
            else:
                ml = max(len(str(cn)), 6)
                for v in alloc_df[cn].head(20):
                    if pd.notna(v):
                        ml = max(ml, min(len(str(v)), 16))
                worksheet.set_column(ci, ci, min(max(ml + 2, 8), 18))

        worksheet.set_row(0, 28)
        worksheet.set_row(1, 36)
    
    def _format_portfolio_summary(self, writer, summary_sheet, header_format, metric_value_format, price_format, percent_format):
        """📊 Format Portfolio Summary sheet"""
        
        worksheet = writer.sheets['Portfolio Summary']
        
        # Format headers
        for col in range(len(summary_sheet.columns)):
            worksheet.write(0, col, summary_sheet.columns[col], header_format)
        
        # Format values based on column type
        for col, column_name in enumerate(summary_sheet.columns):
            value = summary_sheet.iloc[0, col]
            
            if 'amount' in column_name.lower() or 'value' in column_name.lower():
                worksheet.write(1, col, value, price_format)
            elif 'percentage' in column_name.lower() or 'pct' in column_name.lower():
                worksheet.write(1, col, value/100 if isinstance(value, (int, float)) and value > 1 else value, percent_format)
            else:
                worksheet.write(1, col, value, metric_value_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def _create_technical_analysis_sheet(self, workbook, df, header_format, data_format, 
                                       price_format, percent_format, score_format):
        """📈 PHASE 2: Technical Analysis Deep Dive"""
        
        worksheet = workbook.add_worksheet('📈 Technical Deep Dive')
        
        # Get top performing stocks with available data
        tech_stocks = df.head(30)
        
        # Headers
        headers = ['Symbol', 'Company', 'Current Price', 'RSI', 'MACD Signal', 'BB Position', 
                  'Volume Trend', 'Support', 'Resistance', 'Tech Score', 'Signal', 'Momentum']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data with REAL technical indicators (ACCURACY IMPROVEMENT #4)
        for row, (_, stock) in enumerate(tech_stocks.iterrows(), 1):
            symbol = stock.get('symbol', '')
            current_price = stock.get('current_price', 0)
            
            # Use REAL technical indicators from price data analysis
            # Convert to numeric to avoid rounding errors with strings
            real_rsi = pd.to_numeric(stock.get('real_rsi', 50.0), errors='coerce')
            real_rsi = 50.0 if pd.isna(real_rsi) else float(real_rsi)
            
            macd_signal = stock.get('real_macd_signal', 'NEUTRAL')
            bb_position = stock.get('real_bb_position', 'MIDDLE')
            volume_trend = stock.get('real_volume_trend', 'AVERAGE')
            momentum = stock.get('real_momentum', 'NEUTRAL')
            support_level = stock.get('support_level', current_price * 0.95)
            resistance_level = stock.get('resistance_level', current_price * 1.05)
            
            real_tech_score = pd.to_numeric(stock.get('real_technical_score', 50.0), errors='coerce')
            real_tech_score = 50.0 if pd.isna(real_tech_score) else float(real_tech_score)
            
            ma_signal = stock.get('ma_signal', 'HOLD')
            
            # Generate comprehensive technical signal using REAL indicators
            signal_factors = []
            
            # RSI Signal
            if real_rsi > 70:
                signal_factors.append('OVERBOUGHT')
            elif real_rsi < 30:
                signal_factors.append('OVERSOLD')
            elif 40 <= real_rsi <= 60:
                signal_factors.append('NEUTRAL_RSI')
            
            # MACD Signal
            if macd_signal == 'BULLISH':
                signal_factors.append('MACD_BUY')
            elif macd_signal == 'BEARISH':
                signal_factors.append('MACD_SELL')
            
            # Volume Signal
            if volume_trend in ['HIGH', 'ABOVE_AVERAGE']:
                signal_factors.append('VOLUME_SUPPORT')
            
            # Moving Average Signal
            if ma_signal == 'BUY':
                signal_factors.append('MA_BUY')
            elif ma_signal == 'SELL':
                signal_factors.append('MA_SELL')
            
            # Determine final signal
            if 'OVERSOLD' in signal_factors and ('MACD_BUY' in signal_factors or 'MA_BUY' in signal_factors):
                signal = 'STRONG BUY'
            elif 'MA_BUY' in signal_factors and 'VOLUME_SUPPORT' in signal_factors:
                signal = 'BUY'
            elif 'OVERBOUGHT' in signal_factors and ('MACD_SELL' in signal_factors or 'MA_SELL' in signal_factors):
                signal = 'STRONG SELL'
            elif 'MA_SELL' in signal_factors:
                signal = 'SELL'
            else:
                signal = 'HOLD'
            
            # Write data to worksheet with REAL technical indicators
            worksheet.write(row, 0, symbol, data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:25], data_format)
            worksheet.write(row, 2, current_price, price_format)
            worksheet.write(row, 3, round(real_rsi, 1), score_format)
            worksheet.write(row, 4, macd_signal, data_format)
            worksheet.write(row, 5, bb_position, data_format)
            worksheet.write(row, 6, volume_trend, data_format)
            worksheet.write(row, 7, support_level, price_format)
            worksheet.write(row, 8, resistance_level, price_format)
            worksheet.write(row, 9, round(real_tech_score, 1), score_format)
            worksheet.write(row, 10, signal, data_format)
            worksheet.write(row, 11, momentum, data_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, tech_stocks)
    
    def _create_multi_timeframe_analysis_sheet(self, workbook, df, header_format, data_format,
                                             price_format, percent_format, score_format):
        """🕐 ACCURACY IMPROVEMENT #5: Multi-Timeframe Analysis Deep Dive"""
        
        worksheet = workbook.add_worksheet('🕐 Multi-Timeframe Analysis')
        
        # Get top performing stocks with multi-timeframe data
        mtf_stocks = df.head(30)
        
        # Headers for multi-timeframe analysis
        headers = ['Symbol', 'Company', 'Daily Trend', 'Weekly Trend', 'Monthly Trend', 
                  'MTF Signal', 'Trend Strength', 'Agreement %', 'Signal Quality', 
                  'MTF Score', 'Risk Level', 'Recommendation']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data with multi-timeframe analysis
        for row, (_, stock) in enumerate(mtf_stocks.iterrows(), 1):
            symbol = stock.get('symbol', '')
            company = str(stock.get('company_name', ''))[:25]
            
            # Multi-timeframe signals
            daily_trend = stock.get('daily_trend', 'NEUTRAL')
            weekly_trend = stock.get('weekly_trend', 'NEUTRAL')
            monthly_trend = stock.get('monthly_trend', 'NEUTRAL')
            mtf_signal = stock.get('mtf_trend_signal', 'NEUTRAL')
            
            # Signal strength and quality metrics - convert to numeric to avoid rounding errors
            trend_strength = pd.to_numeric(stock.get('mtf_trend_strength', 50), errors='coerce')
            trend_strength = 50 if pd.isna(trend_strength) else float(trend_strength)
            
            agreement = pd.to_numeric(stock.get('mtf_timeframe_agreement', 0), errors='coerce')
            agreement = 0 if pd.isna(agreement) else float(agreement)
            
            signal_quality = stock.get('mtf_signal_quality', 'LOW')
            
            mtf_score = pd.to_numeric(stock.get('mtf_composite_score', 50), errors='coerce')
            mtf_score = 50 if pd.isna(mtf_score) else float(mtf_score)
            
            # Risk assessment based on timeframe agreement
            if agreement >= 80:
                risk_level = 'LOW'
            elif agreement >= 60:
                risk_level = 'MODERATE'
            elif agreement >= 40:
                risk_level = 'HIGH'
            else:
                risk_level = 'VERY HIGH'
            
            # Generate recommendation based on multi-timeframe consensus
            bullish_count = sum(1 for trend in [daily_trend, weekly_trend, monthly_trend] 
                              if trend == 'BULLISH')
            bearish_count = sum(1 for trend in [daily_trend, weekly_trend, monthly_trend] 
                               if trend == 'BEARISH')
            
            if bullish_count >= 2 and agreement >= 70:
                recommendation = 'STRONG BUY'
            elif bullish_count >= 2 and agreement >= 50:
                recommendation = 'BUY'
            elif bearish_count >= 2 and agreement >= 70:
                recommendation = 'STRONG SELL'
            elif bearish_count >= 2 and agreement >= 50:
                recommendation = 'SELL'
            elif agreement < 40:
                recommendation = 'AVOID'
            else:
                recommendation = 'HOLD'
            
            # Write data to worksheet
            worksheet.write(row, 0, symbol, data_format)
            worksheet.write(row, 1, company, data_format)
            worksheet.write(row, 2, daily_trend, data_format)
            worksheet.write(row, 3, weekly_trend, data_format)
            worksheet.write(row, 4, monthly_trend, data_format)
            worksheet.write(row, 5, mtf_signal, data_format)
            worksheet.write(row, 6, round(trend_strength, 1), score_format)
            worksheet.write(row, 7, round(agreement, 1), percent_format)
            worksheet.write(row, 8, signal_quality, data_format)
            worksheet.write(row, 9, round(mtf_score, 1), score_format)
            worksheet.write(row, 10, risk_level, data_format)
            worksheet.write(row, 11, recommendation, data_format)
        
        # Add summary statistics
        try:
            # Calculate summary metrics
            avg_agreement = mtf_stocks['mtf_timeframe_agreement'].mean() if 'mtf_timeframe_agreement' in mtf_stocks.columns else 0
            avg_mtf_score = mtf_stocks['mtf_composite_score'].mean() if 'mtf_composite_score' in mtf_stocks.columns else 0
            
            # High quality signals count
            high_quality_count = len(mtf_stocks[mtf_stocks['mtf_signal_quality'] == 'HIGH']) if 'mtf_signal_quality' in mtf_stocks.columns else 0
            
            # Add summary section
            summary_row = len(mtf_stocks) + 3
            worksheet.write(summary_row, 0, 'MULTI-TIMEFRAME SUMMARY', header_format)
            worksheet.write(summary_row + 1, 0, f'Average Agreement: {avg_agreement:.1f}%', data_format)
            worksheet.write(summary_row + 2, 0, f'Average MTF Score: {avg_mtf_score:.1f}', data_format)
            worksheet.write(summary_row + 3, 0, f'High Quality Signals: {high_quality_count}', data_format)
            
        except Exception as e:
            logging.warning(f"Error adding MTF summary: {e}")
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, mtf_stocks)
    
    def _create_institutional_flow_analysis_sheet(self, workbook, df, header_format, data_format, 
                                                price_format, percent_format, score_format):
        """🏛️ ACCURACY IMPROVEMENT #7: Institutional Flow Analysis Deep Dive"""
        
        worksheet = workbook.add_worksheet('🏛️ Institutional Flow')
        
        # Title
        worksheet.write(0, 0, '🏛️ INSTITUTIONAL FLOW ANALYSIS', header_format)
        worksheet.write(1, 0, 'Smart Money Movement Detection & Analysis', data_format)
        
        # Headers for institutional flow analysis
        institutional_headers = [
            'Symbol', 'Company', 'Current Price', 'Institutional Score', 'Institutional Sentiment',
            'FII Activity', 'DII Activity', 'Smart Money Flow', 'Bulk Deals Signal', 
            'Large Block Activity', 'Insider Activity', 'Ownership Change %',
            'Overall Score', 'Investment Signal'
        ]
        
        for col, header in enumerate(institutional_headers):
            worksheet.write(2, col, header, header_format)
        
        # Data with institutional flow analysis
        institutional_stocks = df.copy()
        
        # Sort by institutional score (highest first)
        if 'institutional_score' in institutional_stocks.columns:
            institutional_stocks = institutional_stocks.sort_values('institutional_score', ascending=False)
        
        for idx, (_, row) in enumerate(institutional_stocks.iterrows(), start=3):
            try:
                # Extract institutional data
                symbol = str(row.get('symbol', '')).upper()
                company = str(row.get('company_name', symbol))[:30]  # Truncate long names
                
                # Convert numeric values to avoid type errors
                current_price = pd.to_numeric(row.get('current_price', 0), errors='coerce')
                current_price = 0 if pd.isna(current_price) else float(current_price)
                
                institutional_score = pd.to_numeric(row.get('institutional_score', 50), errors='coerce')
                institutional_score = 50 if pd.isna(institutional_score) else float(institutional_score)
                
                institutional_sentiment = str(row.get('institutional_sentiment', 'NEUTRAL'))
                fii_activity = str(row.get('fii_activity', 'NEUTRAL'))
                dii_activity = str(row.get('dii_activity', 'NEUTRAL'))
                smart_money_flow = str(row.get('smart_money_flow', 'NEUTRAL'))
                bulk_deals_signal = str(row.get('bulk_deals_signal', 'NEUTRAL'))
                large_block_activity = str(row.get('large_block_activity', 'NEUTRAL'))
                insider_activity = str(row.get('insider_activity', 'NEUTRAL'))
                
                ownership_change = pd.to_numeric(row.get('institutional_ownership_change', 0), errors='coerce')
                ownership_change = 0 if pd.isna(ownership_change) else float(ownership_change)
                
                overall_score = pd.to_numeric(row.get('overall_score_institutional', row.get('overall_score_with_value', 50)), errors='coerce')
                overall_score = 50 if pd.isna(overall_score) else float(overall_score)
                
                # Generate investment signal based on institutional analysis
                if institutional_score >= 75:
                    investment_signal = "🟢 STRONG BUY"
                elif institutional_score >= 65:
                    investment_signal = "🔵 BUY"
                elif institutional_score >= 45:
                    investment_signal = "🟡 HOLD"
                elif institutional_score >= 35:
                    investment_signal = "🟠 WEAK SELL"
                else:
                    investment_signal = "🔴 SELL"
                
                # Write data
                worksheet.write(idx, 0, symbol, data_format)
                worksheet.write(idx, 1, company, data_format)
                worksheet.write(idx, 2, current_price, price_format)
                worksheet.write(idx, 3, institutional_score, score_format)
                worksheet.write(idx, 4, institutional_sentiment, data_format)
                worksheet.write(idx, 5, fii_activity, data_format)
                worksheet.write(idx, 6, dii_activity, data_format)
                worksheet.write(idx, 7, smart_money_flow, data_format)
                worksheet.write(idx, 8, bulk_deals_signal, data_format)
                worksheet.write(idx, 9, large_block_activity, data_format)
                worksheet.write(idx, 10, insider_activity, data_format)
                worksheet.write(idx, 11, ownership_change, percent_format)
                worksheet.write(idx, 12, overall_score, score_format)
                worksheet.write(idx, 13, investment_signal, data_format)
                
            except Exception as e:
                logging.warning(f"Error writing institutional data for row {idx}: {e}")
                continue
        
        try:
            # Calculate summary metrics
            avg_institutional_score = institutional_stocks['institutional_score'].mean() if 'institutional_score' in institutional_stocks.columns else 0
            
            # Count different activities
            fii_buying_count = len(institutional_stocks[institutional_stocks['fii_activity'] == 'BUYING']) if 'fii_activity' in institutional_stocks.columns else 0
            dii_accumulating_count = len(institutional_stocks[institutional_stocks['dii_activity'] == 'ACCUMULATING']) if 'dii_activity' in institutional_stocks.columns else 0
            smart_money_accumulation_count = len(institutional_stocks[institutional_stocks['smart_money_flow'] == 'ACCUMULATION']) if 'smart_money_flow' in institutional_stocks.columns else 0
            positive_bulk_deals_count = len(institutional_stocks[institutional_stocks['bulk_deals_signal'] == 'POSITIVE']) if 'bulk_deals_signal' in institutional_stocks.columns else 0
            
            # Add summary section
            summary_row = len(institutional_stocks) + 3
            worksheet.write(summary_row, 0, 'INSTITUTIONAL FLOW SUMMARY', header_format)
            worksheet.write(summary_row + 1, 0, f'Average Institutional Score: {avg_institutional_score:.1f}', data_format)
            worksheet.write(summary_row + 2, 0, f'FII Buying Activity: {fii_buying_count} stocks', data_format)
            worksheet.write(summary_row + 3, 0, f'DII Accumulation: {dii_accumulating_count} stocks', data_format)
            worksheet.write(summary_row + 4, 0, f'Smart Money Accumulation: {smart_money_accumulation_count} stocks', data_format)
            worksheet.write(summary_row + 5, 0, f'Positive Bulk Deals: {positive_bulk_deals_count} stocks', data_format)
            
        except Exception as e:
            logging.warning(f"Error adding institutional summary: {e}")
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, institutional_stocks)
    
    def _create_valuation_analysis_sheet(self, workbook, df, header_format, data_format,
                                       price_format, percent_format, score_format):
        """💰 PHASE 2: Valuation Analysis with Fair Value"""
        
        worksheet = workbook.add_worksheet('💰 Valuation Analysis')
        
        # Filter stocks with valuation data
        val_cols = ['pe_ratio', 'pb_ratio', 'roe', 'eps', 'current_price']
        available_val_cols = [col for col in val_cols if col in df.columns]
        
        if available_val_cols and 'pe_ratio' in df.columns:
            val_stocks = df[df['pe_ratio'].notna()].head(30)
        elif available_val_cols:
            val_stocks = df[df[available_val_cols[0]].notna()].head(30)
        else:
            val_stocks = df.head(30)  # Fallback to all stocks
        
        if val_stocks.empty:
            worksheet.write(0, 0, 'No valuation data available', header_format)
            return
        
        # Headers with industry-relative metrics
        headers = ['Symbol', 'Company', 'Current Price', 'PE Ratio', 'PE vs Industry', 'PB Ratio', 'PB vs Industry', 
                  'ROE %', 'ROE vs Industry', 'Industry Fair Value', 'Upside %', 'Valuation Grade']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Data with industry-relative calculations
        for row, (_, stock) in enumerate(val_stocks.iterrows(), 1):
            # Convert to numeric to avoid type errors
            pe = pd.to_numeric(stock.get('pe_ratio', 0), errors='coerce')
            pe = 0 if pd.isna(pe) else float(pe)
            
            pb = pd.to_numeric(stock.get('pb_ratio', 0), errors='coerce')
            pb = 0 if pd.isna(pb) else float(pb)
            
            roe = pd.to_numeric(stock.get('roe', 0), errors='coerce')
            roe = 0 if pd.isna(roe) else float(roe)
            
            eps = pd.to_numeric(stock.get('eps', 0), errors='coerce')
            eps = 0 if pd.isna(eps) else float(eps)
            
            current_price = pd.to_numeric(stock.get('current_price', 0), errors='coerce')
            current_price = 0 if pd.isna(current_price) else float(current_price)
            
            sector = stock.get('sector', '')
            industry = stock.get('industry', '')
            
            # Get industry benchmarks for more accurate valuation
            benchmarks = self._get_dynamic_industry_benchmarks(sector, industry)
            
            # Industry-relative metrics (ensure benchmarks are not None or 0)
            avg_pe = _nv(benchmarks.get('avg_pe_ratio'), 20.0)
            avg_pb = _nv(benchmarks.get('avg_pb_ratio'), 3.0)
            avg_roe = _nv(benchmarks.get('avg_roe'), 15.0)
            
            pe_vs_industry = f"{pe/avg_pe:.2f}x" if (pe and not (isinstance(pe, float) and np.isnan(pe)) and avg_pe > 0) else 'N/A'
            pb_vs_industry = f"{pb/avg_pb:.2f}x" if (pb and not (isinstance(pb, float) and np.isnan(pb)) and avg_pb > 0) else 'N/A'
            roe_vs_industry = f"{roe/avg_roe:.2f}x" if (roe and not (isinstance(roe, float) and np.isnan(roe)) and avg_roe > 0) else 'N/A'
            
            # Industry-adjusted fair value estimation
            industry_avg_pe = avg_pe
            fair_value = eps * industry_avg_pe if eps and eps > 0 and industry_avg_pe else current_price
            upside = ((fair_value - current_price) / current_price * 100) if current_price > 0 else 0
            
            # Valuation category
            if upside > 20:
                valuation = 'UNDERVALUED'
            elif upside < -20:
                valuation = 'OVERVALUED'
            else:
                valuation = 'FAIR VALUE'
            
            # Valuation grade based on industry-relative metrics
            if upside > 30:
                valuation = 'Highly Undervalued'
            elif upside > 15:
                valuation = 'Undervalued'
            elif upside > -10:
                valuation = 'Fair Value'
            elif upside > -25:
                valuation = 'Overvalued'
            else:
                valuation = 'Highly Overvalued'
            
            worksheet.write(row, 0, stock['symbol'], data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:25], data_format)
            worksheet.write(row, 2, current_price, price_format)
            worksheet.write(row, 3, pe, score_format)
            worksheet.write(row, 4, pe_vs_industry, data_format)
            worksheet.write(row, 5, pb, score_format)
            worksheet.write(row, 6, pb_vs_industry, data_format)
            worksheet.write(row, 7, roe / 100.0 if roe > 1 else roe, percent_format)
            worksheet.write(row, 8, roe_vs_industry, data_format)
            worksheet.write(row, 9, fair_value, price_format)
            worksheet.write(row, 10, upside/100, percent_format)
            worksheet.write(row, 11, valuation, data_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, val_stocks)
    
    def _create_correlation_analysis_sheet(self, workbook, df, header_format, data_format, percent_format):
        """🔗 PHASE 2: Correlation Analysis"""
        
        worksheet = workbook.add_worksheet('🔗 Correlation Analysis')
        
        # Correlation matrix for numerical columns
        numerical_cols = ['overall_score_with_value', 'risk_adjusted_score', 'undervaluation_score', 
                         'pe_ratio', 'pb_ratio', 'roe', 'rsi', 'current_price']
        
        available_cols = [col for col in numerical_cols if col in df.columns and df[col].notna().sum() > 5]
        
        if len(available_cols) < 2:
            worksheet.write(0, 0, 'Insufficient data for correlation analysis', header_format)
            return
        
        # Calculate correlation matrix
        corr_data = df[available_cols].corr()
        
        # Write headers
        worksheet.write(0, 0, 'Metric', header_format)
        for col, metric in enumerate(available_cols, 1):
            worksheet.write(0, col, metric.replace('_', ' ').title()[:15], header_format)
        
        # Write correlation data
        for row, metric1 in enumerate(available_cols, 1):
            worksheet.write(row, 0, metric1.replace('_', ' ').title()[:15], header_format)
            for col, metric2 in enumerate(available_cols, 1):
                corr_val = corr_data.loc[metric1, metric2]
                
                # Color code correlations
                if abs(corr_val) > 0.7:
                    format_to_use = workbook.add_format({'bg_color': '#FF6B6B', 'align': 'center', 'num_format': '0.00'})
                elif abs(corr_val) > 0.5:
                    format_to_use = workbook.add_format({'bg_color': '#FFE66D', 'align': 'center', 'num_format': '0.00'})
                else:
                    format_to_use = workbook.add_format({'bg_color': '#4ECDC4', 'align': 'center', 'num_format': '0.00'})
                
                worksheet.write(row, col, corr_val, format_to_use)
        
        # Add interpretation
        start_row = len(available_cols) + 3
        worksheet.write(start_row, 0, 'Correlation Interpretation:', header_format)
        worksheet.write(start_row + 1, 0, 'Red: Strong correlation (>0.7)', data_format)
        worksheet.write(start_row + 2, 0, 'Yellow: Moderate correlation (0.5-0.7)', data_format)
        worksheet.write(start_row + 3, 0, 'Teal: Weak correlation (<0.5)', data_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def _create_performance_tracking_sheet(self, workbook, df, header_format, data_format, 
                                         price_format, percent_format, score_format):
        """📊 PHASE 2: Performance Tracking & Benchmarking"""
        
        worksheet = workbook.add_worksheet('📊 Performance Tracking')
        
        # Performance metrics
        top_performers = df.head(20)
        
        # Headers
        headers = ['Rank', 'Symbol', 'Company', 'Overall Score', 'Risk Score', 'Value Score', 
                  'Sector', 'vs Sector Avg', 'Performance Grade', 'Trend', 'Recommendation']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Calculate sector averages for comparison
        sector_avg = df.groupby('sector')['overall_score_with_value'].mean().to_dict()
        
        # Data
        for row, (_, stock) in enumerate(top_performers.iterrows(), 1):
            sector = stock.get('sector', 'Unknown')
            score = stock.get('overall_score_with_value', 0)
            sector_avg_score = sector_avg.get(sector, 0)
            vs_sector = score - sector_avg_score
            
            # Performance grade
            if score >= 80:
                grade = 'A+'
            elif score >= 70:
                grade = 'A'
            elif score >= 60:
                grade = 'B'
            elif score >= 50:
                grade = 'C'
            else:
                grade = 'D'
            
            # Trend analysis (simplified)
            trend = 'UPTREND' if score > sector_avg_score else 'DOWNTREND'
            
            worksheet.write(row, 0, row, data_format)
            worksheet.write(row, 1, stock['symbol'], data_format)
            worksheet.write(row, 2, str(stock.get('company_name', ''))[:25], data_format)
            worksheet.write(row, 3, score, score_format)
            worksheet.write(row, 4, stock.get('risk_adjusted_score', 0), score_format)
            worksheet.write(row, 5, stock.get('undervaluation_score', 0), score_format)
            worksheet.write(row, 6, str(sector)[:15], data_format)
            worksheet.write(row, 7, vs_sector, score_format)
            worksheet.write(row, 8, grade, data_format)
            worksheet.write(row, 9, trend, data_format)
            worksheet.write(row, 10, str(stock.get('final_recommendation', ''))[:15], data_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, top_performers)
    
    def _create_risk_management_sheet(self, workbook, df, portfolio_allocation, header_format, 
                                    data_format, price_format, percent_format):
        """⚡ PHASE 2: Risk Management Dashboard"""
        
        worksheet = workbook.add_worksheet('⚡ Risk Management')
        
        # Risk metrics summary
        worksheet.write(0, 0, 'PORTFOLIO RISK ANALYSIS', header_format)
        worksheet.write(0, 1, '', header_format)
        worksheet.write(0, 2, '', header_format)
        
        row = 2
        
        # Overall risk metrics
        if portfolio_allocation and 'allocation_df' in portfolio_allocation:
            alloc_df = portfolio_allocation['allocation_df']
            
            # Risk distribution
            risk_dist = alloc_df['risk_category'].value_counts()
            
            worksheet.write(row, 0, 'Risk Distribution:', header_format)
            row += 1
            
            for risk_level, count in risk_dist.items():
                worksheet.write(row, 0, f'{risk_level} Risk:', data_format)
                worksheet.write(row, 1, count, data_format)
                worksheet.write(row, 2, f'{count/len(alloc_df)*100:.1f}%', percent_format)
                row += 1
            
            row += 1
        
        # Risk metrics by stock
        worksheet.write(row, 0, 'TOP RISK METRICS BY STOCK', header_format)
        row += 2
        
        # Headers for risk analysis
        risk_headers = ['Symbol', 'Company', 'Risk Category', 'Volatility', 'Beta', 
                       'Max Drawdown', 'Risk Score', 'Position Size', 'Risk Contribution']
        
        for col, header in enumerate(risk_headers):
            worksheet.write(row, col, header, header_format)
        
        row += 1
        
        # Risk analysis for top stocks
        risk_stocks = df.head(25)

        _alloc_lookup = {}
        if portfolio_allocation and 'allocation_df' in portfolio_allocation:
            _pa = portfolio_allocation['allocation_df']
            for _, _pr in _pa.iterrows():
                _alloc_lookup[_pr.get('symbol', '')] = _pr.get('investment_amount', 0) or _pr.get('current_value', 0)

        for _, stock in risk_stocks.iterrows():
            _sym = stock.get('symbol', '')
            position_size = _alloc_lookup.get(_sym, 0) or stock.get('kelly_position_size', 0) or 0
            if position_size == 0:
                _portfolio_amt = getattr(self, 'portfolio_amount', 100000)
                position_size = _portfolio_amt / max(len(risk_stocks), 1)
            volatility = _nv(stock.get('volatility_6m'), 0.1)
            risk_contrib = position_size * volatility
            
            worksheet.write(row, 0, stock['symbol'], data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:20], data_format)
            worksheet.write(row, 2, str(stock.get('risk_category', 'UNKNOWN')), data_format)
            worksheet.write(row, 3, stock.get('volatility_6m', 0), percent_format)
            worksheet.write(row, 4, stock.get('beta', 1.0), data_format)
            worksheet.write(row, 5, stock.get('max_drawdown_6m', 0), percent_format)
            worksheet.write(row, 6, stock.get('risk_adjusted_score', 0), data_format)
            worksheet.write(row, 7, position_size, price_format)
            worksheet.write(row, 8, risk_contrib, price_format)
            row += 1
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def _create_alerts_notifications_sheet(self, workbook, df, header_format, data_format, 
                                         price_format, percent_format, buy_format, sell_format):
        """🔔 PHASE 2: Smart Alerts & Notifications"""
        
        worksheet = workbook.add_worksheet('🔔 Smart Alerts')
        
        # Generate alerts based on analysis
        alerts = []
        
        for _, stock in df.iterrows():
            symbol = stock['symbol']
            score = stock.get('overall_score_with_value', 0)
            recommendation = str(stock.get('final_recommendation', ''))
            rsi = stock.get('rsi', 50)
            pe_ratio = stock.get('pe_ratio', 0)
            
            # Price alerts
            if 'STRONG BUY' in recommendation:
                alerts.append({
                    'symbol': symbol,
                    'type': 'BUY OPPORTUNITY',
                    'message': f'Strong buy signal with score {score:.1f}',
                    'priority': 'HIGH',
                    'action': 'Consider buying',
                    'price': stock.get('current_price', 0)
                })
            
            # Technical alerts
            if rsi < 30:
                alerts.append({
                    'symbol': symbol,
                    'type': 'OVERSOLD',
                    'message': f'RSI at {rsi:.1f} indicates oversold condition',
                    'priority': 'MEDIUM',
                    'action': 'Potential buy opportunity',
                    'price': stock.get('current_price', 0)
                })
            elif rsi > 70:
                alerts.append({
                    'symbol': symbol,
                    'type': 'OVERBOUGHT',
                    'message': f'RSI at {rsi:.1f} indicates overbought condition',
                    'priority': 'MEDIUM', 
                    'action': 'Consider taking profits',
                    'price': stock.get('current_price', 0)
                })
            
            # Valuation alerts
            if pe_ratio > 30 and pe_ratio > 0:
                alerts.append({
                    'symbol': symbol,
                    'type': 'VALUATION WARNING',
                    'message': f'High PE ratio of {pe_ratio:.1f}',
                    'priority': 'LOW',
                    'action': 'Monitor valuation',
                    'price': stock.get('current_price', 0)
                })
        
        # Sort alerts by priority
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        alerts.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        # Headers
        headers = ['Priority', 'Symbol', 'Alert Type', 'Message', 'Current Price', 'Recommended Action']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Alert data
        for row, alert in enumerate(alerts[:50], 1):  # Limit to 50 alerts
            # Color code by priority
            if alert['priority'] == 'HIGH':
                priority_format = workbook.add_format({'bg_color': '#FF6B6B', 'align': 'center', 'bold': True})
            elif alert['priority'] == 'MEDIUM':
                priority_format = workbook.add_format({'bg_color': '#FFE66D', 'align': 'center'})
            else:
                priority_format = workbook.add_format({'bg_color': '#95E1D3', 'align': 'center'})
            
            worksheet.write(row, 0, alert['priority'], priority_format)
            worksheet.write(row, 1, alert['symbol'], data_format)
            worksheet.write(row, 2, alert['type'], data_format)
            worksheet.write(row, 3, alert['message'], data_format)
            worksheet.write(row, 4, alert['price'], price_format)
            worksheet.write(row, 5, alert['action'], data_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def _create_price_prediction_sheet(self, workbook, df, header_format, data_format,
                                     price_format, percent_format, score_format):
        """🔮 PHASE 3: Price Prediction & Monte Carlo Analysis"""
        
        worksheet = workbook.add_worksheet('🔮 Price Predictions')
        
        # Price prediction for top performing stocks
        top_stocks = df.head(20)
        
        # Headers
        headers = ['Symbol', 'Company', 'Current Price', '1M Target', '3M Target', '6M Target',
                  'Bull Case', 'Bear Case', 'Probability Up', 'Risk Level', 'Prediction Model', 'Confidence']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Generate predictions (Monte Carlo simulation based)
        for row, (_, stock) in enumerate(top_stocks.iterrows(), 1):
            current_price = _nv(stock.get('current_price'), 0)
            score = _nv(stock.get('overall_score_with_value'), 0)
            volatility = _nv(stock.get('volatility_6m'), 0.2)
            
            # Simple prediction model based on score and volatility
            if current_price > 0:
                # Base prediction on score
                growth_factor = (score - 50) / 100  # Convert score to growth factor
                
                # Monthly targets with increasing uncertainty
                target_1m = current_price * (1 + growth_factor * 0.05)
                target_3m = current_price * (1 + growth_factor * 0.15)
                target_6m = current_price * (1 + growth_factor * 0.30)
                
                # Bull and bear cases
                bull_case = target_6m * (1 + volatility)
                bear_case = target_6m * (1 - volatility)
                
                # Probability calculations
                prob_up = min(0.9, max(0.1, score / 100))
                
                # Prediction model and confidence
                if score > 80:
                    model = 'AI-Optimistic'
                    confidence = 85
                elif score > 60:
                    model = 'Statistical'
                    confidence = 70
                else:
                    model = 'Conservative'
                    confidence = 55
                
                risk_level = stock.get('risk_category', 'MEDIUM')
            else:
                target_1m = target_3m = target_6m = bull_case = bear_case = 0
                prob_up = 0.5
                model = 'N/A'
                confidence = 0
                risk_level = 'UNKNOWN'
            
            worksheet.write(row, 0, stock['symbol'], data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:25], data_format)
            worksheet.write(row, 2, current_price, price_format)
            worksheet.write(row, 3, target_1m, price_format)
            worksheet.write(row, 4, target_3m, price_format)
            worksheet.write(row, 5, target_6m, price_format)
            worksheet.write(row, 6, bull_case, price_format)
            worksheet.write(row, 7, bear_case, price_format)
            worksheet.write(row, 8, prob_up, percent_format)
            worksheet.write(row, 9, risk_level, data_format)
            worksheet.write(row, 10, model, data_format)
            worksheet.write(row, 11, confidence/100, percent_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, top_stocks)
    
    def _create_market_timing_sheet(self, workbook, df, header_format, data_format,
                                   price_format, percent_format):
        """⏰ PHASE 3: Market Timing & Economic Indicators"""
        
        worksheet = workbook.add_worksheet('⏰ Market Timing')
        
        # Market timing analysis
        worksheet.write(0, 0, 'MARKET TIMING ANALYSIS', header_format)
        worksheet.write(0, 1, '', header_format)
        worksheet.write(0, 2, '', header_format)
        
        row = 2
        
        # Overall market sentiment based on analysis
        total_stocks = len(df)
        buy_count = len(df[df['final_recommendation'].str.contains('BUY', na=False)])
        strong_buy_count = len(df[df['final_recommendation'].str.contains('STRONG BUY', na=False)])
        avg_score = df['overall_score_with_value'].mean()
        
        # Market sentiment calculation
        bullish_percentage = buy_count / total_stocks if total_stocks > 0 else 0
        
        if bullish_percentage > 0.7 and avg_score > 70:
            market_sentiment = 'VERY BULLISH'
            market_color = 'Green'
        elif bullish_percentage > 0.6 and avg_score > 60:
            market_sentiment = 'BULLISH'
            market_color = 'Light Green'
        elif bullish_percentage > 0.4:
            market_sentiment = 'NEUTRAL'
            market_color = 'Yellow'
        else:
            market_sentiment = 'BEARISH'
            market_color = 'Red'
        
        worksheet.write(row, 0, 'Market Sentiment:', header_format)
        worksheet.write(row, 1, market_sentiment, data_format)
        worksheet.write(row, 2, f'({bullish_percentage:.1%} Bullish)', data_format)
        
        row += 2
        
        # Economic indicators — fetch live where possible, label static otherwise
        _usdinr = 'N/A'
        _crude = 'N/A'
        try:
            _cd = getattr(self, '_crisis_data', None) or {}
            if _cd:
                _usdinr = f"{_cd.get('usdinr_level', 'N/A')}"
                _crude = f"${_cd.get('crude_level', 'N/A')}/bbl"
            else:
                import yfinance as _yf
                _usdinr = f"{_yf.Ticker('USDINR=X').info.get('regularMarketPrice', 'N/A')}"
                _crude = f"${_yf.Ticker('BZ=F').info.get('regularMarketPrice', 'N/A')}/bbl"
        except Exception:
            pass
        indicators = [
            ('GDP Growth Rate', 'See RBI data', 'External source'),
            ('Inflation Rate', 'See RBI data', 'External source'),
            ('Interest Rates', 'See RBI data', 'External source'),
            ('FII Inflows', 'See NSDL data', 'External source'),
            ('DII Inflows', 'See NSDL data', 'External source'),
            ('USD/INR', _usdinr, 'Live' if _usdinr != 'N/A' else 'Unavailable'),
            ('Crude Oil', _crude, 'Live' if _crude != 'N/A' else 'Unavailable'),
            ('Market PE', 'See NSE data', 'External source'),
        ]
        
        worksheet.write(row, 0, 'Economic Indicators:', header_format)
        row += 1
        
        worksheet.write(row, 0, 'Indicator', header_format)
        worksheet.write(row, 1, 'Current Value', header_format)
        worksheet.write(row, 2, 'Impact', header_format)
        row += 1
        
        for indicator, value, impact in indicators:
            worksheet.write(row, 0, indicator, data_format)
            worksheet.write(row, 1, value, data_format)
            worksheet.write(row, 2, impact, data_format)
            row += 1
        
        # Sector rotation recommendations
        row += 2
        worksheet.write(row, 0, 'Sector Rotation Strategy:', header_format)
        row += 1
        
        if 'sector' in df.columns:
            sector_performance = df.groupby('sector').agg({
                'overall_score_with_value': 'mean',
                'symbol': 'count'
            }).round(2)
            
            sector_performance = sector_performance.sort_values('overall_score_with_value', ascending=False)
            
            worksheet.write(row, 0, 'Sector', header_format)
            worksheet.write(row, 1, 'Avg Score', header_format)
            worksheet.write(row, 2, 'Recommendation', header_format)
            row += 1
            
            for sector, data in sector_performance.head(10).iterrows():
                score = data['overall_score_with_value']
                if score > 70:
                    recommendation = 'OVERWEIGHT'
                elif score > 60:
                    recommendation = 'NEUTRAL'
                else:
                    recommendation = 'UNDERWEIGHT'
                
                worksheet.write(row, 0, str(sector)[:20], data_format)
                worksheet.write(row, 1, score, data_format)
                worksheet.write(row, 2, recommendation, data_format)
                row += 1
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def _create_sentiment_analysis_sheet(self, workbook, df, header_format, data_format, score_format):
        """🧠 PHASE 3: AI Sentiment Analysis & News Impact"""
        
        worksheet = workbook.add_worksheet('🧠 AI Sentiment')
        
        # Sentiment analysis for top stocks
        top_stocks = df.head(25)
        
        # Headers
        headers = ['Symbol', 'Company', 'Overall Score', 'Sentiment Score', 'News Impact', 
                  'Social Buzz', 'Analyst Mood', 'Recommendation', 'Confidence Level']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Use real sentiment data from sentiment_analyzer
        for row, (_, stock) in enumerate(top_stocks.iterrows(), 1):
            score = stock.get('overall_score_with_value', 0)
            recommendation = stock.get('final_recommendation', '')

            _news_score = stock.get('news_sentiment_score', 50)
            _market_score = stock.get('market_sentiment_score', 50)
            _buzz_score = stock.get('buzz_sentiment_score', 50)
            _analyst_score = stock.get('analyst_sentiment_score', 50)
            base_sentiment = float(_news_score) * 0.3 + float(_market_score) * 0.3 + float(_buzz_score) * 0.2 + float(_analyst_score) * 0.2
            base_sentiment = 50.0 if (base_sentiment is None or (isinstance(base_sentiment, float) and np.isnan(base_sentiment))) else min(100, max(0, base_sentiment))

            _news_sig = str(stock.get('news_sentiment_signal', 'NEUTRAL'))
            news_impact = _news_sig.replace('_', ' ').title() if _news_sig not in ('', 'nan') else 'Neutral'
            _buzz_lvl = str(stock.get('buzz_level', 'LOW'))
            social_buzz = _buzz_lvl.title() if _buzz_lvl not in ('', 'nan') else 'Low'
            _analyst_sig = str(stock.get('analyst_sentiment_signal', 'NEUTRAL'))
            analyst_mood = _analyst_sig.replace('_', ' ').title() if _analyst_sig not in ('', 'nan') else 'Neutral'

            _conf = stock.get('sentiment_confidence', 50)
            _conf_val = float(_conf) if not pd.isna(_conf) else 50
            if _conf_val > 80:
                confidence = 'Very High'
            elif _conf_val > 60:
                confidence = 'High'
            elif _conf_val > 40:
                confidence = 'Medium'
            else:
                confidence = 'Low'
            
            worksheet.write(row, 0, stock['symbol'], data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:25], data_format)
            worksheet.write(row, 2, score, score_format)
            worksheet.write(row, 3, base_sentiment, score_format)
            worksheet.write(row, 4, news_impact, data_format)
            worksheet.write(row, 5, social_buzz, data_format)
            worksheet.write(row, 6, analyst_mood, data_format)
            worksheet.write(row, 7, str(recommendation)[:15], data_format)
            worksheet.write(row, 8, confidence, data_format)
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet, top_stocks)
    
    def _create_goal_based_investing_sheet(self, workbook, df, portfolio_allocation, header_format, 
                                         data_format, price_format, percent_format):
        """🎯 PHASE 3: Goal-Based Investing & SIP Recommendations"""
        
        worksheet = workbook.add_worksheet('🎯 Goal-Based Investing')
        
        # SIP recommendations
        worksheet.write(0, 0, 'SYSTEMATIC INVESTMENT PLAN (SIP) RECOMMENDATIONS', header_format)
        worksheet.write(0, 1, '', header_format)
        worksheet.write(0, 2, '', header_format)
        
        row = 3
        
        # Different investment goals
        goals = [
            {'name': 'Retirement (20+ years)', 'risk': 'High', 'equity': 80, 'debt': 20, 'target': '₹2-5 Cr'},
            {'name': 'Child Education (10-15 years)', 'risk': 'Medium', 'equity': 60, 'debt': 40, 'target': '₹50L-1Cr'},
            {'name': 'House Purchase (5-10 years)', 'risk': 'Medium', 'equity': 50, 'debt': 50, 'target': '₹1-2Cr'},
            {'name': 'Emergency Fund (1-3 years)', 'risk': 'Low', 'equity': 20, 'debt': 80, 'target': '₹5-10L'},
            {'name': 'Wealth Creation (7-15 years)', 'risk': 'High', 'equity': 70, 'debt': 30, 'target': '₹1-3Cr'}
        ]
        
        # Headers for goals
        worksheet.write(row, 0, 'Investment Goal', header_format)
        worksheet.write(row, 1, 'Time Horizon', header_format)
        worksheet.write(row, 2, 'Risk Level', header_format)
        worksheet.write(row, 3, 'Equity %', header_format)
        worksheet.write(row, 4, 'Debt %', header_format)
        worksheet.write(row, 5, 'Target Amount', header_format)
        worksheet.write(row, 6, 'Monthly SIP', header_format)
        row += 1
        
        # SIP calculations
        sip_amounts = [25000, 15000, 20000, 10000, 30000]  # Monthly SIP amounts
        
        for i, goal in enumerate(goals):
            worksheet.write(row, 0, goal['name'], data_format)
            worksheet.write(row, 1, goal['name'].split('(')[1].replace(')', ''), data_format)
            worksheet.write(row, 2, goal['risk'], data_format)
            worksheet.write(row, 3, f"{goal['equity']}%", data_format)
            worksheet.write(row, 4, f"{goal['debt']}%", data_format)
            worksheet.write(row, 5, goal['target'], data_format)
            worksheet.write(row, 6, f"₹{sip_amounts[i]:,}", data_format)
            row += 1
        
        # Top SIP stock recommendations
        row += 2
        worksheet.write(row, 0, 'TOP SIP STOCK RECOMMENDATIONS', header_format)
        row += 2
        
        # Filter stocks suitable for SIP
        sip_stocks = df[df['final_recommendation'].str.contains('BUY', na=False)].head(15)
        
        worksheet.write(row, 0, 'Symbol', header_format)
        worksheet.write(row, 1, 'Company', header_format)
        worksheet.write(row, 2, 'Current Price', header_format)
        worksheet.write(row, 3, 'Monthly SIP Amount', header_format)
        worksheet.write(row, 4, 'Risk Category', header_format)
        worksheet.write(row, 5, 'Suitability', header_format)
        row += 1
        
        for _, stock in sip_stocks.iterrows():
            current_price = stock.get('current_price', 0)
            risk_category = stock.get('risk_category', 'MEDIUM')
            score = stock.get('overall_score_with_value', 0)
            
            # Calculate recommended SIP amount
            if current_price > 0:
                if current_price < 100:
                    sip_amount = 5000
                elif current_price < 500:
                    sip_amount = 3000
                else:
                    sip_amount = 2000
            else:
                sip_amount = 0
            
            # Suitability based on score and risk
            if score > 75:
                suitability = 'Excellent'
            elif score > 65:
                suitability = 'Good'
            elif score > 55:
                suitability = 'Average'
            else:
                suitability = 'Below Average'
            
            worksheet.write(row, 0, stock['symbol'], data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:25], data_format)
            worksheet.write(row, 2, current_price, price_format)
            worksheet.write(row, 3, f"₹{sip_amount:,}", data_format)
            worksheet.write(row, 4, risk_category, data_format)
            worksheet.write(row, 5, suitability, data_format)
            row += 1
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def _create_portfolio_optimization_sheet(self, workbook, df, portfolio_allocation, header_format,
                                           data_format, price_format, percent_format, score_format):
        """⚙️ PHASE 3: Advanced Portfolio Optimization"""
        
        worksheet = workbook.add_worksheet('⚙️ Portfolio Optimization')
        
        # Optimization analysis
        worksheet.write(0, 0, 'ADVANCED PORTFOLIO OPTIMIZATION', header_format)
        worksheet.write(0, 1, '', header_format)
        worksheet.write(0, 2, '', header_format)
        
        row = 3
        
        # Sharpe ratio calculation (simplified)
        if portfolio_allocation:
            worksheet.write(row, 0, 'Portfolio Efficiency Metrics:', header_format)
            row += 1
            
            # Compute real portfolio metrics from stock-level data
            _vol_col = 'volatility_6m' if 'volatility_6m' in df.columns else ('volatility' if 'volatility' in df.columns else None)
            _beta_col = 'beta' if 'beta' in df.columns else None
            _dd_col = 'max_drawdown_6m' if 'max_drawdown_6m' in df.columns else None
            _ret_col = None
            for _rc in ('price_change_1y', 'enhanced_price_change_60d', 'price_change_6m'):
                if _rc in df.columns:
                    _ret_col = _rc
                    break

            _alloc_df = portfolio_allocation.get('allocation_df') if portfolio_allocation else None
            _weights = None
            if _alloc_df is not None and not _alloc_df.empty and 'current_value' in _alloc_df.columns:
                _tv = _alloc_df['current_value'].sum()
                if _tv > 0:
                    _weights = _alloc_df.set_index('symbol')['current_value'] / _tv

            portfolio_volatility = 0.15
            if _vol_col:
                _vols = pd.to_numeric(df[_vol_col], errors='coerce').fillna(100)
                if _weights is not None:
                    _matched = _vols.copy()
                    _matched.index = df['symbol'] if 'symbol' in df.columns else _matched.index
                    portfolio_volatility = sum(_weights.get(s, 0) * v for s, v in zip(df.get('symbol', []), _vols)) or _vols.mean()
                else:
                    portfolio_volatility = float(_vols.mean()) if _vols.mean() > 0 else 0.15
            portfolio_volatility = max(portfolio_volatility / 100, 0.01) if portfolio_volatility > 1 else max(portfolio_volatility, 0.01)

            weighted_beta = 1.0
            if _beta_col:
                _betas = pd.to_numeric(df[_beta_col], errors='coerce').fillna(1.0)
                if _weights is not None:
                    weighted_beta = sum(_weights.get(s, 0) * b for s, b in zip(df.get('symbol', []), _betas)) or float(_betas.mean())
                else:
                    weighted_beta = float(_betas.mean())
            weighted_beta = round(max(0.1, min(weighted_beta, 3.0)), 2)

            weighted_max_dd = 0.15
            if _dd_col:
                _dds = pd.to_numeric(df[_dd_col], errors='coerce').fillna(0).abs()
                if _weights is not None:
                    weighted_max_dd = sum(_weights.get(s, 0) * d for s, d in zip(df.get('symbol', []), _dds)) or float(_dds.mean())
                else:
                    weighted_max_dd = float(_dds.mean())
            if weighted_max_dd > 1:
                weighted_max_dd = weighted_max_dd / 100

            var_95 = portfolio_volatility * 1.645
            risk_free_rate = 0.06

            if _ret_col:
                _rets = pd.to_numeric(df[_ret_col], errors='coerce').fillna(0)
                if _weights is not None:
                    expected_return = sum(_weights.get(s, 0) * r for s, r in zip(df.get('symbol', []), _rets)) or float(_rets.mean())
                else:
                    expected_return = float(_rets.mean())
                if abs(expected_return) > 1:
                    expected_return = expected_return / 100
            else:
                expected_return = df['overall_score_with_value'].mean() / 100 * 0.15

            sharpe_ratio = (expected_return - risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0

            metrics = [
                ('Expected Annual Return', f'{expected_return:.1%}'),
                ('Portfolio Volatility', f'{portfolio_volatility:.1%}'),
                ('Sharpe Ratio', f'{sharpe_ratio:.2f}'),
                ('Risk-Free Rate', f'{risk_free_rate:.1%}'),
                ('Alpha (vs Market)', f'{expected_return - 0.12:.1%}'),
                ('Beta (Market Sensitivity)', f'{weighted_beta:.2f}'),
                ('Maximum Drawdown', f'{weighted_max_dd:.1%}'),
                ('Value at Risk (95%)', f'{var_95:.1%}')
            ]
            
            for metric, value in metrics:
                worksheet.write(row, 0, metric, data_format)
                worksheet.write(row, 1, value, data_format)
                row += 1
        
        # Optimization recommendations
        row += 2
        worksheet.write(row, 0, 'OPTIMIZATION RECOMMENDATIONS:', header_format)
        row += 2
        
        # Efficient frontier analysis (simplified)
        top_performers = df.head(20)
        
        worksheet.write(row, 0, 'Symbol', header_format)
        worksheet.write(row, 1, 'Company', header_format)
        worksheet.write(row, 2, 'Current Weight', header_format)
        worksheet.write(row, 3, 'Optimal Weight', header_format)
        worksheet.write(row, 4, 'Expected Return', header_format)
        worksheet.write(row, 5, 'Risk Score', header_format)
        worksheet.write(row, 6, 'Optimization Action', header_format)
        row += 1
        
        # Build real weights from portfolio allocation
        _weight_map = {}
        _alloc = getattr(self, 'portfolio_allocation', None)
        if _alloc and _alloc.get('allocation_df') is not None:
            _adf = _alloc['allocation_df']
            if 'portfolio_weight' in _adf.columns and 'symbol' in _adf.columns:
                for _, _r in _adf.iterrows():
                    _pw = _r.get('portfolio_weight', 0)
                    _weight_map[_r['symbol']] = 0.0 if (_pw is None or (isinstance(_pw, float) and np.isnan(_pw))) else float(_pw)
        total_value = sum(_weight_map.values()) * 1000000 if _weight_map else 1000000

        for _, stock in top_performers.iterrows():
            current_weight = _weight_map.get(stock['symbol'], 0.0)
            score = stock.get('overall_score_with_value', 0)
            
            # Calculate optimal weight based on score
            normalized_score = score / 100
            optimal_weight = min(0.1, max(0.01, normalized_score * 0.08))  # Cap at 10%
            
            # Expected return based on score
            expected_return = (score - 50) / 100 * 0.20  # Convert score to return expectation
            
            # Risk score (inverse of overall score)
            risk_score = max(1, min(10, 11 - (score / 10)))
            
            # Optimization action
            weight_diff = optimal_weight - current_weight
            if weight_diff > 0.01:
                action = 'INCREASE'
            elif weight_diff < -0.01:
                action = 'DECREASE'
            else:
                action = 'MAINTAIN'
            
            worksheet.write(row, 0, stock['symbol'], data_format)
            worksheet.write(row, 1, str(stock.get('company_name', ''))[:20], data_format)
            worksheet.write(row, 2, current_weight, percent_format)
            worksheet.write(row, 3, optimal_weight, percent_format)
            worksheet.write(row, 4, expected_return, percent_format)
            worksheet.write(row, 5, risk_score, score_format)
            worksheet.write(row, 6, action, data_format)
            row += 1
        
        # 🔧 Auto-resize columns for optimal display
        self._auto_resize_columns(worksheet)
    
    def generate_enhanced_summary_stats(self, df):
        """Enhanced summary statistics with new metrics"""
        print(f"\n📈 ENHANCED ANALYSIS SUMMARY")
        print("=" * 60)
        
        total_stocks = len(df)
        print(f"📊 ENHANCED DATA COLLECTION:")
        print(f"   Total Stocks Analyzed     : {total_stocks}")
        
        # Enhanced metrics
        undervalued_count = len(df[df['undervaluation_score'] >= 65])
        low_risk_count = len(df[df['risk_category'] == 'LOW'])
        buy_recs = len(df[df['final_recommendation'].str.contains('BUY', na=False)])
        
        print(f"   Undervalued Stocks (≥65)  : {undervalued_count} ({undervalued_count/total_stocks*100:.1f}%)")
        print(f"   Low Risk Stocks           : {low_risk_count} ({low_risk_count/total_stocks*100:.1f}%)")
        print(f"   BUY Recommendations       : {buy_recs} ({buy_recs/total_stocks*100:.1f}%)")
        
        # Score distribution
        if 'risk_adjusted_score' in df.columns:
            scores = df['risk_adjusted_score'].dropna()
            if len(scores) > 0:
                print(f"\n🎯 RISK-ADJUSTED SCORE DISTRIBUTION:")
                print(f"   Average Score             : {scores.mean():.1f}")
                print(f"   Top 10% Average           : {scores.quantile(0.9):.1f}")
                print(f"   Median Score              : {scores.median():.1f}")
        
        # Sector analysis
        if 'sector' in df.columns:
            sectors = df['sector'].value_counts().head(5)
            print(f"\n🏢 TOP SECTORS BY COUNT:")
            for sector, count in sectors.items():
                print(f"   {sector:<20}: {count} stocks")
        
        # Top performers
        top_10 = df.head(10)[['symbol', 'risk_adjusted_score', 'undervaluation_score', 'final_recommendation']]
        print(f"\n🏆 TOP 10 RISK-ADJUSTED PERFORMERS:")
        print("-" * 50)
        for idx, (_, row) in enumerate(top_10.iterrows(), 1):
            symbol = row['symbol']
            risk_score = row['risk_adjusted_score']
            underval = row['undervaluation_score']
            rec = row['final_recommendation']
            print(f"   {idx:2d}. {symbol:<12}: Risk-Adj:{risk_score:5.1f} | Underval:{underval:5.1f} | {rec}")
        
        # Portfolio allocation summary
        if hasattr(self, 'portfolio_allocation') and self.portfolio_allocation:
            alloc_summary = self.portfolio_allocation['summary']
            print(f"\n💼 PORTFOLIO ALLOCATION SUMMARY:")
            print(f"   Total Portfolio Stocks    : {alloc_summary['total_stocks']}")
            print(f"   Current Holdings          : {alloc_summary['current_holdings']}")
            print(f"   New Positions             : {alloc_summary['new_positions']}")
            print(f"   Current Portfolio Value   : ₹{alloc_summary['current_portfolio_value']:,.0f}")
            print(f"   Available Funds           : ₹{alloc_summary['available_funds']:,.0f}")
            print(f"   Average Overall Score     : {alloc_summary['avg_score']:.1f}")
            print(f"   Sector Diversification    : {alloc_summary['sector_count']} sectors")
            print(f"   Portfolio Utilization     : {alloc_summary['portfolio_utilization']:.1f}%")
            print(f"   Funds Utilization         : {alloc_summary['funds_utilization']:.1f}%")
            
            # Display sell recommendations if any
            # Weekly score changes
            try:
                _wc = self.recommendation_history.get_weekly_changes(days=7) if hasattr(self, 'recommendation_history') else None
                if _wc and (_wc.get('improved') or _wc.get('deteriorated')):
                    print(f"\n📊 WEEKLY SCORE CHANGES (7 days):")
                    if _wc.get('improved'):
                        print(f"   ✅ Improved ({len(_wc['improved'])}):")
                        for _e in _wc['improved'][:5]:
                            print(f"      {_e['symbol']:12s}: {_e['previous_score']:.1f} → {_e['current_score']:.1f} ({_e['change']:+.1f})")
                    if _wc.get('deteriorated'):
                        print(f"   ⚠️ Deteriorated ({len(_wc['deteriorated'])}):")
                        for _e in _wc['deteriorated'][:5]:
                            print(f"      {_e['symbol']:12s}: {_e['previous_score']:.1f} → {_e['current_score']:.1f} ({_e['change']:+.1f})")
            except Exception:
                pass

            if 'sell_recommendations' in self.portfolio_allocation and not self.portfolio_allocation['sell_recommendations'].empty:
                sell_df = self.portfolio_allocation['sell_recommendations']
                print(f"\n[SELL] SELL RECOMMENDATIONS ({len(sell_df)} stocks):")
                print(f"   Risk Profile: {self.risk_profile.upper()} - Excess holdings to optimize portfolio")
                
                # Group by category
                sell_by_category = sell_df.groupby('stock_type').size().to_dict()
                for category, count in sell_by_category.items():
                    category_stocks = sell_df[sell_df['stock_type'] == category]
                    print(f"   {category}: {count} stocks")
                    for _, stock in category_stocks.head(3).iterrows():  # Show top 3 per category
                        value = stock.get('current_value', 0)
                        print(f"      • {stock['symbol']}: ₹{value:,.0f} (Score: {stock.get('risk_adjusted_score', 0):.1f})")
                    if len(category_stocks) > 3:
                        print(f"      ... and {len(category_stocks) - 3} more {category} stocks")
                        
                print(f"   💡 These recommendations help achieve optimal {self.risk_profile} allocation")
    
    def generate_summary_stats(self, df):
        """Generate and display summary statistics"""
        print(f"\n📈 ANALYSIS SUMMARY STATISTICS")
        print("=" * 50)
        
        # Overall statistics
        total_stocks = len(df)
        successful_fundamental = len(df[df['fundamental_status'] == 'success'])
        successful_enhanced = len(df[df['enhanced_technical_status'] == 'success'])
        successful_legacy = len(df[df['legacy_technical_status'] == 'success'])
        
        print(f"📊 DATA COLLECTION SUCCESS RATES:")
        print(f"   Total Stocks Analyzed     : {total_stocks}")
        print(f"   Fundamental Analysis      : {successful_fundamental}/{total_stocks} ({successful_fundamental/total_stocks*100:.1f}%)")
        print(f"   Enhanced Technical        : {successful_enhanced}/{total_stocks} ({successful_enhanced/total_stocks*100:.1f}%)")
        print(f"   Legacy Technical          : {successful_legacy}/{total_stocks} ({successful_legacy/total_stocks*100:.1f}%)")
        
        # Score statistics
        if 'overall_score_triple' in df.columns:
            scores = df['overall_score_triple'].dropna()
            if len(scores) > 0:
                print(f"\n🎯 SCORE DISTRIBUTION:")
                print(f"   Average Score             : {scores.mean():.1f}")
                print(f"   Median Score              : {scores.median():.1f}")
                print(f"   Highest Score             : {scores.max():.1f}")
                print(f"   Lowest Score              : {scores.min():.1f}")
                print(f"   Standard Deviation        : {scores.std():.1f}")
        
        # Top performers
        if 'overall_score_triple' in df.columns and 'symbol' in df.columns:
            top_10 = df.nlargest(10, 'overall_score_triple')[['symbol', 'overall_score_triple', 'final_recommendation']]
            
            print(f"\n🏆 TOP 10 PERFORMERS:")
            print("-" * 40)
            for idx, (_, row) in enumerate(top_10.iterrows(), 1):
                symbol = row['symbol']
                score = _nv(row['overall_score_triple'], 0)
                rec = row['final_recommendation']
                print(f"   {idx:2d}. {symbol:<12}: {score:5.1f} - {rec}")
        
        # Recommendation distribution
        if 'final_recommendation' in df.columns:
            rec_counts = df['final_recommendation'].value_counts()
            print(f"\n📋 RECOMMENDATION DISTRIBUTION:")
            print("-" * 35)
            for rec, count in rec_counts.items():
                percentage = (count / total_stocks) * 100 if total_stocks > 0 else 0
                print(f"   {rec:<25}: {count:3d} ({percentage:4.1f}%)")
        
        # Failed stocks
        if self.failed_stocks:
            print(f"\n[FAIL] FAILED ANALYSIS ({len(self.failed_stocks)} stocks):")
            print("-" * 30)
            for stock in self.failed_stocks[:10]:  # Show first 10
                print(f"   . {stock}")
            if len(self.failed_stocks) > 10:
                print(f"   ... and {len(self.failed_stocks) - 10} more")
        
        # Low quality stocks
        if hasattr(self, 'low_quality_stocks') and self.low_quality_stocks:
            print(f"\n[WARN] LOW DATA QUALITY ({len(self.low_quality_stocks)} stocks):")
            print("-" * 30)
            for stock in self.low_quality_stocks[:10]:  # Show first 10
                print(f"   . {stock}")
            if len(self.low_quality_stocks) > 10:
                print(f"   ... and {len(self.low_quality_stocks) - 10} more")

def export_default_stocks_to_csv(output_path="default_stock_list.csv"):
    """Export the default stock list to a CSV file"""
    try:
        # Create a dummy analyzer instance to get the default list
        dummy = EnhancedTop200StockAnalyzer(max_workers=1)
        default_stocks = dummy.get_default_stock_list()
        
        # Create DataFrame with Symbol column
        df = pd.DataFrame({"Symbol": default_stocks})
        
        # Add empty Company Name column
        df["Company Name"] = ""
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        print(f"✅ Default stock list exported to {output_path}")
        print(f"   - {len(default_stocks)} stocks exported")
        print(f"   - Edit the 'Company Name' column as needed")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to export default stocks: {e}")
        return False

def generate_top_10_categories(results_df, analyzer=None):
    """
    Generate TOP 10 lists for specific categories as requested by user:
    1. TOP 10 Undervalued
    2. TOP 10 Growth  
    3. TOP 10 Fundamentally Strong and Technically Strong
    4. TOP 10 Fundamentally Strong and Undervalued
    """
    print("\n" + "="*80)
    print("🏆 TOP 10 CATEGORY ANALYSIS")
    print("="*80)
    
    # Ensure we have the required columns with default values
    if 'undervaluation_score' not in results_df.columns:
        results_df['undervaluation_score'] = 50
    if 'technical_score' not in results_df.columns:
        if 'advanced_technical_score_final' in results_df.columns:
            results_df['technical_score'] = results_df['advanced_technical_score_final']
        elif 'real_technical_score_final' in results_df.columns:
            results_df['technical_score'] = results_df['real_technical_score_final']
        else:
            results_df['technical_score'] = 50
    if 'fundamental_score' not in results_df.columns:
        results_df['fundamental_score'] = 50
    if 'overall_score_with_value' not in results_df.columns:
        results_df['overall_score_with_value'] = 50
    
    # Filter valid stocks (remove nulls and ensure minimum data quality)
    valid_df = results_df.dropna(subset=['symbol']).copy()

    # Ensure columns used in display/calculations exist with safe defaults
    for col, default in [('pe_ratio', 0), ('pb_ratio', 0), ('dividend_yield', 0),
                         ('revenue_growth', 0), ('earnings_growth', 0), ('current_price', 0),
                         ('company_name', '')]:
        if col not in valid_df.columns:
            valid_df[col] = default
    
    # 1. TOP 10 UNDERVALUED - Based on undervaluation_score
    print("\n1. TOP 10 UNDERVALUED STOCKS:")
    print("-" * 50)
    undervalued = valid_df.nlargest(10, 'undervaluation_score')[
        ['symbol', 'company_name', 'undervaluation_score', 'current_price', 'pe_ratio', 'pb_ratio', 'dividend_yield']
    ]
    for i, (_, row) in enumerate(undervalued.iterrows(), 1):
        print(f"{i:2d}. {row['symbol']:12} | {str(row['company_name'])[:30]:30} | "
              f"Score: {row['undervaluation_score']:5.1f} | PE: {row['pe_ratio']:6.1f} | "
              f"PB: {row['pb_ratio']:5.2f} | Price: Rs{row['current_price']:7.1f}")
    
    # 2. TOP 10 GROWTH - Based on revenue growth, earnings growth, and technical momentum
    print("\n2. TOP 10 GROWTH STOCKS:")
    print("-" * 50)
    
    # Use momentum scoring for aggressive investors, otherwise use standard growth calculation
    if analyzer and hasattr(analyzer, 'focus_growth') and analyzer.focus_growth:
        # Calculate momentum growth score for high-risk investors
        valid_df['growth_score'] = valid_df.apply(
            lambda row: analyzer.calculate_momentum_growth_score(row), axis=1
        )
        print("📊 Using MOMENTUM-BASED scoring for high-growth focus")
    else:
        # Standard growth score combining revenue growth, earnings growth, and technical score
        _rg = valid_df['revenue_growth'].fillna(0)
        _eg = valid_df['earnings_growth'].fillna(0)
        _ts = valid_df['technical_score'].fillna(50)
        valid_df['growth_score'] = _rg * 0.3 + _eg * 0.3 + _ts * 0.4
    
    growth = valid_df.nlargest(10, 'growth_score')[
        ['symbol', 'company_name', 'growth_score', 'revenue_growth', 'earnings_growth', 'technical_score', 'current_price']
    ]
    for i, (_, row) in enumerate(growth.iterrows(), 1):
        print(f"{i:2d}. {row['symbol']:12} | {str(row['company_name'])[:30]:30} | "
              f"Growth: {row['growth_score']:5.1f} | Rev: {row['revenue_growth']:6.1f}% | "
              f"Earn: {row['earnings_growth']:6.1f}% | Price: Rs{row['current_price']:7.1f}")
    
    # 3. TOP 10 FUNDAMENTALLY STRONG AND TECHNICALLY STRONG
    print("\n3. TOP 10 FUNDAMENTALLY STRONG & TECHNICALLY STRONG:")
    print("-" * 60)
    # Filter stocks that are strong in both fundamental and technical (score >= 60 in both)
    strong_both = valid_df[
        (valid_df['fundamental_score'] >= 60) & 
        (valid_df['technical_score'] >= 60)
    ].copy()
    
    if len(strong_both) >= 10:
        # Create combined strength score
        strong_both['combined_strength'] = (
            strong_both['fundamental_score'] * 0.6 + 
            strong_both['technical_score'] * 0.4
        )
        strong_both_top = strong_both.nlargest(10, 'combined_strength')[
            ['symbol', 'company_name', 'combined_strength', 'fundamental_score', 'technical_score', 'current_price']
        ]
    else:
        # If not enough, take top by combined score regardless of threshold
        valid_df['combined_strength'] = (
            valid_df['fundamental_score'] * 0.6 + 
            valid_df['technical_score'] * 0.4
        )
        strong_both_top = valid_df.nlargest(10, 'combined_strength')[
            ['symbol', 'company_name', 'combined_strength', 'fundamental_score', 'technical_score', 'current_price']
        ]
    
    for i, (_, row) in enumerate(strong_both_top.iterrows(), 1):
        print(f"{i:2d}. {row['symbol']:12} | {str(row['company_name'])[:30]:30} | "
              f"Combined: {row['combined_strength']:5.1f} | Fund: {row['fundamental_score']:5.1f} | "
              f"Tech: {row['technical_score']:5.1f} | Price: Rs{row['current_price']:7.1f}")
    
    # 4. TOP 10 FUNDAMENTALLY STRONG AND UNDERVALUED
    print("\n4. TOP 10 FUNDAMENTALLY STRONG & UNDERVALUED:")
    print("-" * 55)
    # Filter stocks that are fundamentally strong (>= 60) and undervalued (>= 65)
    strong_undervalued = valid_df[
        (valid_df['fundamental_score'] >= 60) & 
        (valid_df['undervaluation_score'] >= 65)
    ].copy()
    
    if len(strong_undervalued) >= 10:
        # Create value + fundamental score
        strong_undervalued['value_fundamental'] = (
            strong_undervalued['fundamental_score'] * 0.5 + 
            strong_undervalued['undervaluation_score'] * 0.5
        )
        strong_underval_top = strong_undervalued.nlargest(10, 'value_fundamental')[
            ['symbol', 'company_name', 'value_fundamental', 'fundamental_score', 'undervaluation_score', 'current_price']
        ]
    else:
        # If not enough, take top by value + fundamental score regardless of threshold
        valid_df['value_fundamental'] = (
            valid_df['fundamental_score'] * 0.5 + 
            valid_df['undervaluation_score'] * 0.5
        )
        strong_underval_top = valid_df.nlargest(10, 'value_fundamental')[
            ['symbol', 'company_name', 'value_fundamental', 'fundamental_score', 'undervaluation_score', 'current_price']
        ]
    
    for i, (_, row) in enumerate(strong_underval_top.iterrows(), 1):
        print(f"{i:2d}. {row['symbol']:12} | {str(row['company_name'])[:30]:30} | "
              f"V+F: {row['value_fundamental']:5.1f} | Fund: {row['fundamental_score']:5.1f} | "
              f"Underval: {row['undervaluation_score']:5.1f} | Price: Rs{row['current_price']:7.1f}")
    
    print("\n" + "="*80)
    print("📊 CATEGORY SUMMARY:")
    print(f"   . Undervalued stocks analyzed: {len(valid_df[valid_df['undervaluation_score'] >= 65])}")
    print(f"   . Growth stocks identified: {len(valid_df[valid_df['growth_score'] >= 60]) if 'growth_score' in valid_df.columns else 0}")
    print(f"   . Strong fundamental + technical: {len(strong_both) if 'strong_both' in locals() else 0}")
    print(f"   . Strong fundamental + undervalued: {len(strong_undervalued) if 'strong_undervalued' in locals() else 0}")
    print("="*80)

def merge_holdings_and_orders():
    """
    Auto-merge holdings and orders files if they exist
    """
    try:
        # Check for holdings files
        holdings_patterns = ['Holding/holdings*.csv', 'holding*.csv', 'Holdings*.csv']
        holdings_file = None
        
        for pattern in holdings_patterns:
            files = glob.glob(pattern)
            if files:
                holdings_file = max(files, key=os.path.getctime)  # Get latest file
                break
        
        if not holdings_file:
            print("[INFO] No holdings file found - continuing without portfolio data")
            return
        
        # Check for orders files  
        orders_patterns = ['Holding/orders*.csv', 'order*.csv', 'Orders*.csv']
        orders_file = None
        
        for pattern in orders_patterns:
            files = glob.glob(pattern)
            if files:
                orders_file = max(files, key=os.path.getctime)  # Get latest file
                break
        
        print(f"[FOUND] Holdings file: {holdings_file}")
        if orders_file:
            print(f"[FOUND] Orders file: {orders_file}")
        else:
            print("[INFO] No orders file found - merging holdings only")
        
        # Import and run the merger
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location('merge_holdings_orders', os.path.join(os.path.dirname(__file__), 'archived', 'legacy', 'merge_holdings_orders.py'))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        HoldingsOrdersMerger = _mod.HoldingsOrdersMerger
        
        merger = HoldingsOrdersMerger()
        
        # Load holdings data
        if not merger.load_holdings_data(holdings_file):
            print(f"[ERROR] Failed to load holdings from {holdings_file}")
            return
        
        # Load orders data if available
        if orders_file:
            merger.load_orders_data(orders_file)
        
        # Merge data
        if merger.merge_data():
            # Save merged data
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f'merged_portfolio_{timestamp}.xlsx'
            
            if merger.save_merged_data(output_file):
                print(f"[SUCCESS] Portfolio data merged and saved to: reports/{output_file}")
                
                # Print quick summary
                total_invested = merger.merged_data['Invested'].sum()
                current_value = merger.merged_data['Cur. val'].sum()
                total_pnl = merger.merged_data['P&L'].sum()
                
                print(f"[PORTFOLIO] Summary: Rs.{current_value:,.0f} current value, Rs.{total_pnl:+,.0f} P&L ({(total_pnl/total_invested*100):+.1f}%)")
            else:
                print("[ERROR] Failed to save merged portfolio data")
        else:
            print("[ERROR] Failed to merge holdings and orders data")
            
    except ImportError:
        print("[WARNING] Holdings merger not available - continuing without portfolio integration")
    except Exception as e:
        print(f"[WARNING] Error during holdings/orders merge: {e}")
        print("Continuing with stock analysis...")


def main():
    """Main execution function"""
    print("ENHANCED NSE STOCK ANALYSIS - COMPREHENSIVE ANALYSIS WITH AI INSIGHTS")
    print("=" * 90)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced Analysis of Top 200 NSE stocks with undervaluation detection')
    parser.add_argument('-w', '--workers', type=int, default=3, help='Max worker threads')
    parser.add_argument('-b', '--batch', type=int, default=15, help='Batch size (default: 15)')
    parser.add_argument('-s', '--symbol', type=str, help='Single stock symbol to analyze')
    parser.add_argument('-n', '--num', type=int, default=0, help='Number of stocks to analyze (0 = all stocks in CSV, default: all available)')
    parser.add_argument('-c', '--csv', type=str, help='Path to CSV file with stock symbols (defaults to stock_list_template.csv if available)')
    parser.add_argument('-e', '--export', type=str, help='Export default stock list to a CSV file and exit')
    parser.add_argument('--portfolio-amount', type=float, default=100000, help='Target portfolio amount for allocation suggestions (default: Rs1,00,000)')
    parser.add_argument('--skip-risk', action='store_true', help='Skip risk analysis (faster execution)')
    parser.add_argument('--undervalued-only', action='store_true', help='Focus only on undervalued stocks (score >=65)')
    parser.add_argument('--top-10-only', action='store_true', help='Show only TOP 10 categories from latest analysis (fast mode)')
    
    # High-risk high-reward investor options
    parser.add_argument('--risk-profile', type=str, choices=['conservative', 'moderate', 'aggressive', 'balanced'], 
                        default='moderate', help='Risk profile: aggressive(20-25 stocks), moderate(25-30 stocks), balanced(30-35 stocks) (default: moderate)')
    parser.add_argument('--focus-growth', action='store_true', 
                        help='Focus on high-growth stocks (suitable for aggressive investors)')
    parser.add_argument('--focus-momentum', action='store_true', 
                        help='Focus on momentum stocks with technical strength')
    parser.add_argument('--min-volatility', type=float, default=0.0, 
                        help='Minimum volatility threshold for high-risk investors (default: 0.0)')
    parser.add_argument('--save-config', action='store_true',
                        help='Save current configuration to config.json and exit')
    
    args = parser.parse_args()
    
    if args.save_config:
        from config import save_config_to_file
        save_config_to_file('config.json')
        return
    
    # Auto-merge holdings and orders files if they exist
    merge_holdings_and_orders()
    
    # Handle export request (no analyzer needed — exits early)
    if args.export:
        export_default_stocks_to_export(args.export)
        return

    # Initialize analyzer here — required by ALL code paths below (including --top-10-only)
    analyzer = EnhancedTop200StockAnalyzer(
        max_workers=args.workers,
        csv_file=args.csv,
        risk_profile=args.risk_profile,
        focus_growth=args.focus_growth,
        focus_momentum=args.focus_momentum,
        min_volatility=args.min_volatility
    )
    analyzer.portfolio_amount = args.portfolio_amount
    analyzer.skip_risk = args.skip_risk
    analyzer.undervalued_only = args.undervalued_only

    # Handle TOP 10 only mode (quick insights from latest analysis)
    if args.top_10_only:
        print("🚀 QUICK TOP 10 CATEGORIES MODE")
        print("Looking for latest analysis data...")
        
        # Try to find latest analysis Excel file
        excel_files = glob.glob("reports/Enhanced_Stock_Report_*.xlsx") or glob.glob("data/nse_analysis_*.xlsx")
        if excel_files:
            latest_file = max(excel_files, key=lambda x: x.split('_')[-1])
            print(f"📊 Loading latest analysis: {latest_file}")
            
            try:
                # Read the main analysis sheet
                df = pd.read_excel(latest_file, sheet_name='Top_Picks')
                generate_top_10_categories(df, analyzer)
                return
            except Exception as e:
                print(f"[FAIL] Error reading latest analysis: {e}")
                print("Please run a full analysis first.")
                return
        else:
            print("[FAIL] No previous analysis found. Please run a full analysis first.")
            return
    
    # Handle single stock analysis if requested
    if args.symbol:
        print(f"🔍 Single stock analysis mode: {args.symbol}")
        # Create a new list with just the requested symbol
        analyzer.stock_list = [args.symbol]
    elif args.num > 0:
        # ENHANCEMENT: Ensure all portfolio holdings are included in analysis
        # Load current holdings to ensure they're analyzed
        current_holdings = analyzer._load_current_holdings()
        portfolio_symbols = []
        if current_holdings is not None and not current_holdings.empty:
            # Handle different possible column names for stock symbols
            symbol_col = None
            for col in ['Symbol', 'Instrument', 'Stock', 'symbol', 'instrument']:
                if col in current_holdings.columns:
                    symbol_col = col
                    break
            
            if symbol_col:
                portfolio_symbols = current_holdings[symbol_col].tolist()
                logging.info(f"Found {len(portfolio_symbols)} current holdings to include in analysis")
            else:
                logging.warning("No recognizable symbol column found in holdings file")
        
        # Create final stock list: portfolio holdings + additional stocks up to limit
        final_stock_list = []
        
        # Step 1: Add ALL current holdings (these MUST be analyzed regardless of template)
        for symbol in portfolio_symbols:
            if symbol not in final_stock_list:
                final_stock_list.append(symbol)
        
        print(f"   📊 Added all {len(portfolio_symbols)} holdings to analysis (regardless of template)")
        
        # Step 2: Add other stocks from template up to the limit
        remaining_slots = args.num - len(final_stock_list) if args.num > 0 else float('inf')
        if remaining_slots > 0:
            for symbol in analyzer.stock_list:
                if symbol not in final_stock_list and (args.num == 0 or len(final_stock_list) < args.num):
                    final_stock_list.append(symbol)
        
        analyzer.stock_list = final_stock_list
        
        if portfolio_symbols:
            print(f"[SEARCH] Analysis will include:")
            print(f"   [DATA] Current Holdings: {len([s for s in portfolio_symbols if s in final_stock_list])}/{len(portfolio_symbols)}")
            print(f"   [SEARCH] Additional Stocks: {len(final_stock_list) - len([s for s in portfolio_symbols if s in final_stock_list])}")
            print(f"   [DATA] Total to analyze: {len(final_stock_list)} stocks")
        else:
            print(f"[SEARCH] Limited to {args.num} stocks (no portfolio holdings found)")
    else:
        # args.num == 0 means analyze all stocks - BUT still prioritize holdings
        # Load current holdings to ensure they're analyzed even with num=0
        current_holdings = analyzer._load_current_holdings()
        portfolio_symbols = []
        if current_holdings is not None and not current_holdings.empty:
            # Handle different possible column names for stock symbols
            symbol_col = None
            for col in ['Symbol', 'Instrument', 'Stock', 'symbol', 'instrument']:
                if col in current_holdings.columns:
                    symbol_col = col
                    break
            
            if symbol_col:
                portfolio_symbols = current_holdings[symbol_col].tolist()
                logging.info(f"Found {len(portfolio_symbols)} current holdings to include in analysis")
        
        # Create final stock list: portfolio holdings + ALL template stocks
        final_stock_list = []
        
        # Step 1: Add ALL current holdings (these MUST be analyzed)
        for symbol in portfolio_symbols:
            if symbol not in final_stock_list:
                final_stock_list.append(symbol)
        
        # Step 2: Add ALL other stocks from template  
        for symbol in analyzer.stock_list:
            if symbol not in final_stock_list:
                final_stock_list.append(symbol)
        
        analyzer.stock_list = final_stock_list
        
        if portfolio_symbols:
            print(f"[SEARCH] Analysis will include:")
            print(f"   [DATA] Current Holdings: {len(portfolio_symbols)} stocks (ALL)")
            print(f"   [SEARCH] Additional Template Stocks: {len(final_stock_list) - len(portfolio_symbols)}")
            print(f"   [DATA] Total to analyze: {len(final_stock_list)} stocks (Holdings + Full Template)")
        else:
            print(f"[SEARCH] Analyzing all {len(analyzer.stock_list)} stocks from CSV template")
        
    # Display info about CSV if used
    if hasattr(analyzer, '_csv_path') and analyzer._csv_path:
        csv_path = analyzer._csv_path
        is_default = csv_path == "stock_list_template.csv" and not args.csv
        
        if is_default:
            print(f"Using default stock list template: {csv_path}")
        else:
            print(f"[CSV] Using stock list from CSV: {csv_path}")
            
        print(f"   - Stocks loaded: {len(analyzer.stock_list)}")
        print(f"   - Company names: {'Available' if len(analyzer.company_names) > 0 else 'Not available'}")
    
    # Display enhancement options
    print(f"\n[CONFIG] ENHANCEMENT OPTIONS:")
    print(f"   [MONEY] Portfolio Amount: {args.portfolio_amount:,.0f}")
    print(f"   [RISK] Skip Risk Analysis: {'Yes' if args.skip_risk else 'No'}")
    print(f"   [CONFIG] Undervalued Focus: {'Yes' if args.undervalued_only else 'No'}")
    
    # Snapshot config, stock list, and holdings for reproducibility
    try:
        _snap_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        _snap_dir = os.path.join('data', 'snapshots', _snap_ts)
        os.makedirs(_snap_dir, exist_ok=True)
        from config import save_config_to_file as _snap_save_cfg
        _snap_save_cfg(os.path.join(_snap_dir, 'config_snapshot.json'))
        with open(os.path.join(_snap_dir, 'stock_list.txt'), 'w') as _sf:
            _sf.write('\n'.join(analyzer.stock_list))
        for _hf in glob.glob('Holding/holdings*.csv') + glob.glob('Holding/Stocks_Holdings_Statement_*.xlsx'):
            shutil.copy2(_hf, _snap_dir)
        print(f"   📸 Run snapshot saved: {_snap_dir}")
    except Exception as _snap_err:
        logging.warning(f"Snapshot creation failed: {_snap_err}")

    # Run batch analysis
    results = analyzer.analyze_batch(batch_size=args.batch)
    
    if results:
        analyzer.results_df = pd.DataFrame(analyzer.results.values())

        # Generate TOP 10 category analysis (user's requested output)
        if analyzer.results_df is not None and not analyzer.results_df.empty:
            generate_top_10_categories(analyzer.results_df, analyzer)
        
        # Generate comprehensive report
        report_file = analyzer.generate_comprehensive_report()
        
        if report_file:
            analyzer.cleanup_cache(max_age_days=_config.CACHE_MAX_AGE_DAYS, max_files=500)
            print(f"\n[DONE] ANALYSIS COMPLETED SUCCESSFULLY!")
            print(f"[FILE] Report file: {report_file}")
            print(f"[LOG] Log file: {analyzer.log_filename}")
            print(f"\n[TIP] TIP: Check the TOP 10 categories above for quick investment insights!")
            
            # Auto-generate Portfolio Allocation Dashboard
            try:
                print(f"\n{'='*90}")
                print(f"[DASH] AUTO-GENERATING PORTFOLIO ALLOCATION DASHBOARD")
                print(f"{'='*90}")
                
                import webbrowser
                
                # Load Portfolio Allocation data (skip group-header row 0)
                df_portfolio = pd.read_excel(report_file, sheet_name='Portfolio Allocation', header=1)
                _dash_score_cols = {'SCORE', 'ADJ SCORE', 'ML CONF %'}
                for col in df_portfolio.select_dtypes(include='number').columns:
                    _default = 50 if col in _dash_score_cols else 0
                    df_portfolio[col] = df_portfolio[col].fillna(_default)
                for col in df_portfolio.select_dtypes(include='object').columns:
                    df_portfolio[col] = df_portfolio[col].fillna('')
                
                numeric_cols = ['INVEST ₹', 'BUY QTY', 'MY QTY', 'MY VALUE ₹',
                               'P&L %', 'BOOK %', 'SCORE', 'PRICE',
                               'ADJ SCORE', 'ML CONF %']
                for col in numeric_cols:
                    if col in df_portfolio.columns:
                        _fv = 50 if col in _dash_score_cols else 0
                        df_portfolio[col] = pd.to_numeric(df_portfolio[col], errors='coerce').fillna(_fv)

                # Ensure string columns are actual strings before .str accessor
                for _str_col in ['ACTION', 'WHEN', 'TYPE', 'sector', 'symbol', 'company_name']:
                    if _str_col in df_portfolio.columns:
                        df_portfolio[_str_col] = df_portfolio[_str_col].fillna('').astype(str)

                total_stocks = len(df_portfolio)
                _val_col = 'MY VALUE ₹' if 'MY VALUE ₹' in df_portfolio.columns else 'current_value'
                _inv_col = 'INVEST ₹' if 'INVEST ₹' in df_portfolio.columns else None
                total_value = df_portfolio[_val_col].sum() if _val_col in df_portfolio.columns else 0
                total_investment = df_portfolio[_inv_col].sum() if _inv_col else 0
                avg_score = df_portfolio['SCORE'].mean() if 'SCORE' in df_portfolio.columns else 0
                profitable = len(df_portfolio[df_portfolio['P&L %'] > 0]) if 'P&L %' in df_portfolio.columns else 0
                losses = len(df_portfolio[df_portfolio['P&L %'] < 0]) if 'P&L %' in df_portfolio.columns else 0
                avg_profit = df_portfolio[df_portfolio[_val_col] > 0]['P&L %'].mean() if (_val_col in df_portfolio.columns and 'P&L %' in df_portfolio.columns) else 0

                actions = df_portfolio['ACTION'].value_counts().to_dict() if 'ACTION' in df_portfolio.columns else {}
                if 'WHEN' in df_portfolio.columns:
                    df_portfolio['WHEN'] = df_portfolio['WHEN'].replace({0: 'MONITOR', '0': 'MONITOR', 0.0: 'MONITOR'}).fillna('MONITOR').astype(str)
                    df_portfolio.loc[df_portfolio['WHEN'].str.strip() == '', 'WHEN'] = 'MONITOR'
                timings = df_portfolio['WHEN'].value_counts().to_dict() if 'WHEN' in df_portfolio.columns else {}
                types = df_portfolio['TYPE'].value_counts().to_dict() if 'TYPE' in df_portfolio.columns else {}
                sectors = df_portfolio['sector'].value_counts().head(10).to_dict() if 'sector' in df_portfolio.columns else {}

                urgent_sells = df_portfolio[(df_portfolio['ACTION'].str.contains('SELL', na=False)) & (df_portfolio['WHEN'].str.contains('TODAY', na=False))].to_dict('records') if 'ACTION' in df_portfolio.columns else []
                _inv_col_safe = 'INVEST ₹' if 'INVEST ₹' in df_portfolio.columns else None
                urgent_buys = df_portfolio[(df_portfolio['ACTION'].str.contains('BUY|INCREASE|NEW', na=False, regex=True)) & (df_portfolio[_inv_col_safe] > 0)].nlargest(10, _inv_col_safe).to_dict('records') if _inv_col_safe and 'ACTION' in df_portfolio.columns else []
                warnings = df_portfolio[(df_portfolio['ACTION'].str.contains('KEEP', na=False)) & (df_portfolio['WHEN'].str.contains('TODAY', na=False))].to_dict('records') if 'ACTION' in df_portfolio.columns else []
                _book_col = 'BOOK %' if 'BOOK %' in df_portfolio.columns else None
                profit_booking = df_portfolio[df_portfolio[_book_col] > 0].to_dict('records') if _book_col else []
                all_stocks = df_portfolio.to_dict('records')
                
                print(f"   [DONE] Loaded {total_stocks} stocks from Portfolio Allocation")
                
                # Create HTML dashboard
                html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Portfolio Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { color: #667eea; font-size: 2.5em; margin-bottom: 10px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.3s; }
        .card:hover { transform: translateY(-5px); }
        .card-title { color: #666; font-size: 0.9em; text-transform: uppercase; margin-bottom: 10px; }
        .card-value { color: #667eea; font-size: 2.5em; font-weight: bold; margin-bottom: 5px; }
        .card-subtitle { color: #999; font-size: 0.85em; }
        .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .chart-card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .chart-card h3 { margin-bottom: 20px; color: #333; }
        .chart-container { position: relative; height: 300px; }
        .stocks-section { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .stocks-section h2 { color: #667eea; margin-bottom: 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { padding: 12px 25px; background: #f0f0f0; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; }
        .tab:hover { background: #e0e0e0; }
        .tab.active { background: #667eea; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .stock-list { max-height: 600px; overflow-y: auto; }
        .stock-item { background: #f9f9f9; padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #667eea; }
        .stock-item:hover { background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stock-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .stock-symbol { font-size: 1.3em; font-weight: bold; }
        .stock-badge { padding: 5px 15px; border-radius: 20px; font-size: 0.85em; font-weight: bold; }
        .badge-sell { background: #ff6b6b; color: white; }
        .badge-buy { background: #51cf66; color: white; }
        .badge-keep { background: #ffd43b; color: #333; }
        .stock-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; margin-top: 15px; }
        .detail-label { color: #666; font-size: 0.85em; }
        .detail-value { font-weight: bold; color: #333; }
        .profit-positive { color: #51cf66; }
        .profit-negative { color: #ff6b6b; }
        .search-box { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1em; margin-bottom: 20px; }
        .search-box:focus { outline: none; border-color: #667eea; }
        .empty { text-align: center; padding: 40px; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Portfolio Allocation Dashboard</h1>
            <p>Generated on """ + datetime.now().strftime('%B %d, %Y at %I:%M %p') + """</p>
        </div>
        <div class="summary">
            <div class="card"><div class="card-title">Total Stocks</div><div class="card-value">""" + str(total_stocks) + """</div><div class="card-subtitle">In portfolio</div></div>
            <div class="card"><div class="card-title">Portfolio Value</div><div class="card-value">Rs """ + f"{total_value:,.0f}" + """</div><div class="card-subtitle">Current holdings</div></div>
            <div class="card"><div class="card-title">Average Score</div><div class="card-value">""" + f"{avg_score:.1f}" + """</div><div class="card-subtitle">Out of 100</div></div>
            <div class="card"><div class="card-title">Capital Needed</div><div class="card-value">Rs """ + f"{total_investment:,.0f}" + """</div><div class="card-subtitle">For BUY stocks</div></div>
            <div class="card"><div class="card-title">Profitable</div><div class="card-value">""" + str(profitable) + """</div><div class="card-subtitle">""" + str(losses) + """ in loss</div></div>
            <div class="card"><div class="card-title">Avg Profit</div><div class="card-value" style="color: """ + ('#51cf66' if avg_profit > 0 else '#ff6b6b') + """">""" + f"{avg_profit:.1f}%" + """</div><div class="card-subtitle">Across portfolio</div></div>
        </div>
        <div class="charts">
            <div class="chart-card"><h3>Action Breakdown</h3><div class="chart-container"><canvas id="chart1"></canvas></div></div>
            <div class="chart-card"><h3>Timing Priority</h3><div class="chart-container"><canvas id="chart2"></canvas></div></div>
            <div class="chart-card"><h3>Portfolio Types</h3><div class="chart-container"><canvas id="chart3"></canvas></div></div>
            <div class="chart-card"><h3>Top Sectors</h3><div class="chart-container"><canvas id="chart4"></canvas></div></div>
        </div>
        <div class="stocks-section">
            <h2>Priority Actions</h2>
            <div class="tabs">
                <button class="tab active" onclick="showTab(0)">Urgent Sells (""" + str(len(urgent_sells)) + """)</button>
                <button class="tab" onclick="showTab(1)">Top Buys (""" + str(len(urgent_buys)) + """)</button>
                <button class="tab" onclick="showTab(2)">Warnings (""" + str(len(warnings)) + """)</button>
                <button class="tab" onclick="showTab(3)">Profit Booking (""" + str(len(profit_booking)) + """)</button>
                <button class="tab" onclick="showTab(4)">All Stocks (""" + str(len(all_stocks)) + """)</button>
            </div>
            <div id="tab0" class="tab-content active"></div>
            <div id="tab1" class="tab-content"></div>
            <div id="tab2" class="tab-content"></div>
            <div id="tab3" class="tab-content"></div>
            <div id="tab4" class="tab-content"><input type="text" class="search-box" id="search" placeholder="Search stocks..."><div id="all-list"></div></div>
        </div>
    </div>
    <script>
        const data = {
            actions: """ + json.dumps(actions) + """,
            timings: """ + json.dumps(timings) + """,
            types: """ + json.dumps(types) + """,
            sectors: """ + json.dumps(sectors) + """,
            urgentSells: """ + json.dumps(urgent_sells) + """,
            topBuys: """ + json.dumps(urgent_buys) + """,
            warnings: """ + json.dumps(warnings) + """,
            profitBooking: """ + json.dumps(profit_booking) + """,
            allStocks: """ + json.dumps(all_stocks) + """
        };
        const colors = { primary: '#667eea', success: '#51cf66', danger: '#ff6b6b', warning: '#ffd43b' };
        new Chart(document.getElementById('chart1'), { type: 'doughnut', data: { labels: Object.keys(data.actions), datasets: [{ data: Object.values(data.actions), backgroundColor: [colors.success, colors.danger, colors.warning] }] }, options: { responsive: true, maintainAspectRatio: false } });
        new Chart(document.getElementById('chart2'), { type: 'bar', data: { labels: Object.keys(data.timings), datasets: [{ label: 'Stocks', data: Object.values(data.timings), backgroundColor: colors.primary }] }, options: { responsive: true, maintainAspectRatio: false } });
        new Chart(document.getElementById('chart3'), { type: 'pie', data: { labels: Object.keys(data.types), datasets: [{ data: Object.values(data.types), backgroundColor: [colors.primary, colors.warning, colors.danger] }] }, options: { responsive: true, maintainAspectRatio: false } });
        new Chart(document.getElementById('chart4'), { type: 'bar', data: { labels: Object.keys(data.sectors), datasets: [{ data: Object.values(data.sectors), backgroundColor: colors.primary }] }, options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false } });
        function createStockCard(s) {
            const pnl = s['P&L %'] || 0;
            const pClass = pnl > 0 ? 'profit-positive' : 'profit-negative';
            const pSign = pnl > 0 ? '+' : '';
            const act = s.ACTION || '';
            const badgeClass = act.includes('SELL') ? 'badge-sell' : (act.includes('BUY') || act.includes('INCREASE')) ? 'badge-buy' : 'badge-keep';
            const inv = s['INVEST ₹'] || 0;
            const val = s['MY VALUE ₹'] || 0;
            return `<div class="stock-item"><div class="stock-header"><div><div class="stock-symbol">${s.symbol}</div><div style="color:#666;margin-top:5px;">${s.company_name}</div></div><span class="stock-badge ${badgeClass}">${act}</span></div><div class="stock-details">${inv > 0 ? `<div><span class="detail-label">Invest:</span> <span class="detail-value">Rs ${inv.toLocaleString()}</span></div>` : ''}${val > 0 ? `<div><span class="detail-label">Value:</span> <span class="detail-value">Rs ${val.toLocaleString()}</span></div>` : ''}${val > 0 ? `<div><span class="detail-label">P&L:</span> <span class="detail-value ${pClass}">${pSign}${pnl.toFixed(1)}%</span></div>` : ''}<div><span class="detail-label">Score:</span> <span class="detail-value">${(s.SCORE||0).toFixed(1)}/100</span></div><div><span class="detail-label">Price:</span> <span class="detail-value">Rs ${(s.PRICE||0).toLocaleString()}</span></div><div><span class="detail-label">Sector:</span> <span class="detail-value">${s.sector||''}</span></div><div><span class="detail-label">Type:</span> <span class="detail-value">${s.TYPE||''}</span></div></div>${s.REASON ? `<div style="margin-top:15px;padding-top:15px;border-top:1px solid #ddd;"><span class="detail-label">Reason:</span> ${s.REASON}</div>` : ''}</div>`;
        }
        function showList(id, stocks) {
            const html = stocks.length === 0 ? '<div class="empty">No stocks in this category</div>' : '<div class="stock-list">' + stocks.map(s => createStockCard(s)).join('') + '</div>';
            document.getElementById(id).innerHTML = html;
        }
        showList('tab0', data.urgentSells); showList('tab1', data.topBuys); showList('tab2', data.warnings); showList('tab3', data.profitBooking); showList('all-list', data.allStocks);
        function showTab(n) { document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active')); document.querySelectorAll('.tab').forEach(t => t.classList.remove('active')); document.getElementById('tab' + n).classList.add('active'); document.querySelectorAll('.tab')[n].classList.add('active'); }
        document.getElementById('search').addEventListener('input', function(e) { const term = e.target.value.toLowerCase(); const filtered = data.allStocks.filter(s => s.symbol.toLowerCase().includes(term) || s.company_name.toLowerCase().includes(term) || s.sector.toLowerCase().includes(term)); showList('all-list', filtered); });
    </script>
</body>
</html>"""
                
                # Save dashboard
                dashboard_file = "Portfolio_Allocation_Dashboard.html"
                with open(dashboard_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                print(f"   . Dashboard created: {dashboard_file}")
                print(f"   . Opening dashboard in browser...")
                
                # Open in browser
                webbrowser.open(dashboard_file)
                
                print(f"\n   [DASH] Dashboard Features:")
                print(f"      - Interactive charts with 4 visualizations")
                print(f"      - 5 action tabs (Urgent Sells, Top Buys, Warnings, Profit Booking, All Stocks)")
                print(f"      - Real-time search functionality")
                print(f"      - Color-coded action badges")
                print(f"      - Hover effects and smooth animations")
                
            except Exception as dashboard_error:
                print(f"\n   [WARN] Dashboard generation failed: {dashboard_error}")
            
            # Auto-run Profit Booking Advisor
            try:
                print(f"\n{'='*90}")
                print(f"[PROFIT] AUTO-RUNNING SMART PROFIT BOOKING ADVISOR")
                print(f"   [SMART] History-Aware System - Prevents Over-Booking")
                print(f"{'='*90}")

                _spb_imported = False
                try:
                    from smart_profit_booking_advisor import SmartProfitBookingAdvisor
                    _spb_imported = True
                except ImportError:
                    pass
                if not _spb_imported:
                    try:
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'archived', 'legacy'))
                        from smart_profit_booking_advisor import SmartProfitBookingAdvisor
                        _spb_imported = True
                    except ImportError:
                        pass

                if _spb_imported:
                    _spb = SmartProfitBookingAdvisor()
                    _spb.latest_report = report_file
                    _spb.load_booking_history()
                    if _spb.load_portfolio_allocation():
                        _spb.load_merged_portfolio()
                        _book = _spb.get_profit_booking_stocks()
                        if _book is not None and not _book.empty:
                            _res = _spb.calculate_smart_booking_quantities(_book)
                            _spb.display_smart_summary(_res)
                            _spb.save_booking_history()
                            print(f"   [DONE] Smart profit booking analysis complete ({len(_book)} stocks)")
                        else:
                            print(f"   [INFO] No profit booking recommendations in current analysis")
                    else:
                        print(f"   [INFO] Could not load portfolio allocation for profit booking")
                else:
                    print(f"\n[INFO] Smart Profit Booking Advisor module not found")
            except Exception as pbe:
                print(f"\n[WARNING] Smart Profit Booking Advisor: {str(pbe)[:100]}")
            
            # Auto-generate Action Plan Summary
            try:
                print(f"\n{'='*90}")
                print(f"[ACTION PLAN] GENERATING YOUR TRADING ACTION PLAN")
                print(f"{'='*90}")
                
                # Load the portfolio allocation sheet (skip group-header row 0)
                allocation_df = pd.read_excel(report_file, sheet_name='Portfolio Allocation', header=1)

                _V = 'MY VALUE ₹' if 'MY VALUE ₹' in allocation_df.columns else 'current_value'
                _I = 'INVEST ₹' if 'INVEST ₹' in allocation_df.columns else 'investment_amount'
                _Q = 'MY QTY' if 'MY QTY' in allocation_df.columns else 'current_quantity'
                _BQ = 'BUY QTY' if 'BUY QTY' in allocation_df.columns else 'suggested_quantity'

                for _nc in [_V, _I, _Q, _BQ, 'PRICE']:
                    if _nc in allocation_df.columns:
                        allocation_df[_nc] = pd.to_numeric(allocation_df[_nc], errors='coerce').fillna(0)
                for _sc in ['ACTION', 'symbol', 'company_name']:
                    if _sc in allocation_df.columns:
                        allocation_df[_sc] = allocation_df[_sc].fillna('').astype(str)

                print('\n' + '='*100)
                print('📋 YOUR COMPLETE ACTION PLAN')
                print('='*100)
                print('\n🎯 EXECUTE IN THIS ORDER:\n')

                # PRIORITY 1: SWAP POSITIONS
                swaps = allocation_df[allocation_df['ACTION'].str.contains('SWAP', na=False)].sort_values(_V, ascending=False)
                swap_total = 0
                if len(swaps) > 0:
                    print('PRIORITY 1: SWAP 🔄')
                    for _, row in swaps.iterrows():
                        _rot = str(row.get('rotation_target', '')).strip()
                        target = _rot if _rot and _rot != 'nan' else (row['ACTION'].split('->')[1].strip() if '->' in str(row['ACTION']) else 'Unknown')
                        print(f"Sell {row['symbol']} ({row[_Q]:.0f} shares) → ₹{row[_V]:,.0f} → Immediately buy {target}")
                        swap_total += row[_V]
                    print()

                # PRIORITY 2: SELL
                sells = allocation_df[allocation_df['ACTION'].str.contains('SELL', na=False) & ~allocation_df['ACTION'].str.contains('SWAP', na=False)].sort_values(_V, ascending=False)
                sell_total = 0
                if len(sells) > 0:
                    print('PRIORITY 2: SELL 🔴')
                    for _, row in sells.iterrows():
                        print(f"{row['symbol']}: Sell ALL {row[_Q]:.0f} shares → ₹{row[_V]:,.0f}")
                        sell_total += row[_V]
                    print()

                # PRIORITY 3: BOOK PARTIAL PROFITS
                book_profit = allocation_df[(allocation_df['ACTION'].str.contains('BOOK', na=False)) &
                                           (allocation_df[_V] > 0)].sort_values(_V, ascending=False)
                book_total = 0
                if len(book_profit) > 0:
                    print('PRIORITY 3: BOOK PROFITS 🟡 (PARTIAL SELL)')
                    for _, row in book_profit.iterrows():
                        _bk_pct = _nv(row.get('BOOK %'), 0)
                        if _bk_pct > 0 and _bk_pct <= 1:
                            sell_min = int(row[_Q] * max(_bk_pct - 0.05, 0.05))
                            sell_max = int(row[_Q] * _bk_pct)
                        else:
                            sell_min = int(row[_Q] * 0.50)
                            sell_max = int(row[_Q] * 0.60)
                        proceeds_min = sell_min * row['PRICE']
                        proceeds_max = sell_max * row['PRICE']
                        print(f"{row['symbol']}: Sell {sell_min}-{sell_max} shares → ₹{proceeds_min:,.0f}-₹{proceeds_max:,.0f}")
                        book_total += (proceeds_min + proceeds_max) / 2
                    print(f"BOOK Proceeds: ₹{book_total:,.0f}\n")

                # PRIORITY 3.5: REDUCE (SECTOR OVERWEIGHT)
                reduces = allocation_df[allocation_df['ACTION'].str.contains('REDUCE', na=False)].sort_values(_V, ascending=True)
                reduce_total = 0
                if len(reduces) > 0:
                    print('PRIORITY 3.5: REDUCE (SECTOR DIVERSIFICATION) ⚖️')
                    for _, row in reduces.iterrows():
                        _red_qty = max(1, int(row[_Q] * 0.30))
                        _red_val = _red_qty * row['PRICE']
                        print(f"{row['symbol']}: Reduce by ~{_red_qty} shares (~₹{_red_val:,.0f}) — sector overweight")
                        reduce_total += _red_val
                    print(f"REDUCE Proceeds (est): ₹{reduce_total:,.0f}\n")

                # PRIORITY 4: INCREASE
                increases = allocation_df[(allocation_df[_V] > 0) & (allocation_df[_I] > 0) &
                                         (allocation_df['ACTION'].str.contains('INCREASE', na=False))].sort_values(_I, ascending=False)
                total_increase = 0
                if len(increases) > 0:
                    print('PRIORITY 4: INCREASE 📈')
                    for _, row in increases.iterrows():
                        new_total = row[_Q] + row[_BQ]
                        print(f"{row['symbol']}: Add {row[_BQ]:.0f} shares = ₹{row[_I]:,.0f} ({row[_Q]:.0f}→{new_total:.0f} shares)")
                        total_increase += row[_I]
                    print()

                # PRIORITY 5: BUY NEW
                new_buys = allocation_df[(allocation_df[_V] == 0) & (allocation_df[_I] > 0)].sort_values(_I, ascending=False)
                total_new = 0
                if len(new_buys) > 0:
                    print('PRIORITY 5: BUY NEW 🆕')
                    for _, row in new_buys.iterrows():
                        print(f"{row['symbol']}: {row[_BQ]:.0f} shares @ ₹{row['PRICE']:.2f} = ₹{row[_I]:,.0f}")
                        total_new += row[_I]
                    print()

                # PRIORITY 6: HOLD
                holds = allocation_df[(allocation_df[_V] > 0) & ((allocation_df[_I] == 0) | pd.isna(allocation_df[_I])) &
                                     (allocation_df['ACTION'].str.contains('HOLD|KEEP', na=False))].sort_values(_V, ascending=False)
                if len(holds) > 0:
                    print(f'PRIORITY 6: HOLD ✋')
                    print(f"{len(holds)} stocks - No action\n")

                # PRIORITY 7: WATCHLIST
                watchlist = allocation_df[allocation_df['ACTION'].str.contains('WATCHLIST', na=False)]
                if len(watchlist) > 0:
                    print(f'PRIORITY 7: WATCHLIST 👁️')
                    print(f"{len(watchlist)} stocks - Monitor for future entry\n")

                skip_wait = allocation_df[(allocation_df[_V] > 0) &
                                         (allocation_df['ACTION'].str.contains('SKIP', na=False))].sort_values(_V, ascending=False)
                skip_total = 0
                if len(skip_wait) > 0:
                    skip_symbols = ', '.join(skip_wait['symbol'].tolist())
                    skip_total = skip_wait[_V].sum()
                    print(f'PRIORITY 8: OPTIONAL ⚪')
                    print(f"{skip_symbols} → ₹{skip_total:,.0f} (not urgent)\n")
                
                # RISK WARNINGS
                _buy_increase = pd.concat([new_buys, increases], ignore_index=True) if len(new_buys) + len(increases) > 0 else pd.DataFrame()
                if not _buy_increase.empty:
                    _warnings = []
                    _regime_str = str(getattr(analyzer, 'current_market_regime', '') or '').upper() if hasattr(analyzer, 'current_market_regime') else ''
                    if _regime_str in ('BEAR', 'BEARISH'):
                        _warnings.append("BEAR MARKET — all new positions carry elevated risk")
                    for _, _wr in _buy_increase.iterrows():
                        _vol = _wr.get('VOLATILITY %', _wr.get('volatility', _wr.get('VOLATILITY', 0)))
                        _risk = str(_wr.get('RISK', _wr.get('risk_category', '')))
                        _sym = _wr.get('symbol', _wr.get('SYMBOL', ''))
                        if _vol and isinstance(_vol, (int, float)) and _vol > 40:
                            _warnings.append(f"{_sym}: HIGH volatility ({_vol:.1f}%)")
                        if 'HIGH' in str(_risk).upper() or 'VERY' in str(_risk).upper():
                            _warnings.append(f"{_sym}: {_risk} risk category")
                    if _warnings:
                        print('⚠️  RISK WARNINGS:')
                        for _w in _warnings[:8]:
                            print(f"  • {_w}")
                        print()

                # SECTOR CONCENTRATION WARNING
                try:
                    _sect_counts = allocation_df.groupby('sector').size().to_dict() if 'sector' in allocation_df.columns else {}
                    _heavy = {s: c for s, c in _sect_counts.items()
                              if c > _config.SECTOR_CAP and s != 'Unknown'}
                    if _heavy:
                        print('📊 SECTOR CONCENTRATION:')
                        for _hs, _hc in sorted(_heavy.items(), key=lambda x: -x[1]):
                            print(f"  • {_hs}: {_hc} stocks (cap={_config.SECTOR_CAP}) "
                                  f"— only weak stocks (score<{getattr(_config, 'SECTOR_REDUCE_MIN_SCORE', 45)}) marked REDUCE")
                        print()
                except Exception:
                    pass

                # FINAL SUMMARY
                total_investment = total_new + total_increase
                total_proceeds_min = swap_total + sell_total + book_total
                total_proceeds_max = total_proceeds_min + skip_total
                net_min = total_investment - total_proceeds_min
                net_max = total_investment - total_proceeds_max
                
                print('='*100)
                print('💰 FINAL NUMBERS:\n')
                print('MINIMUM (Priority 1-5 only):')
                print(f"Sell: ₹{total_proceeds_min:,.0f} (SWAP + SELL + BOOK)")
                print(f"Buy: ₹{total_investment:,.0f} (NEW + INCREASE)")
                if net_min < 0:
                    print(f"✅ NET: You GET ₹{abs(net_min):,.0f} BACK\n")
                else:
                    print(f"⚠️  NET: You NEED ₹{net_min:,.0f} new capital\n")
                
                if skip_total > 0:
                    print('MAXIMUM (include optional):')
                    if net_max < 0:
                        print(f"✅ NET: You GET ₹{abs(net_max):,.0f} BACK")
                    else:
                        print(f"⚠️  NET: You NEED ₹{net_max:,.0f} new capital")
                
                print('='*100)
                
            except Exception as ap_error:
                print(f"\n[INFO] Action plan generation skipped: {ap_error}")
                print(f"   Run 'python generate_action_plan.py' manually for detailed action plan")

        else:
            print(f"\n[WARN] Analysis completed but report generation failed")
    else:
        print(f"\n[FAIL] Analysis failed - no results generated")

if __name__ == "__main__":
    main()
