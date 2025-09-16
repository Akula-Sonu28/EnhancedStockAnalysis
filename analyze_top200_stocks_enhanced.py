#!/usr/bin/env python3
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
# Add both src directory and project root to Python path
sys.path.append('src')
sys.path.append('.')

import pandas as pd
import logging
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import argparse
import glob
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# Use the proper import paths for each module
from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis
from src.technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from src.excel_exporter import ExcelExporter, ExcelReportGenerator
import yfinance as yf

class EnhancedTop200StockAnalyzer:
    """Enhanced comprehensive analyzer for top 200 NSE stocks with undervaluation detection"""
    
    def __init__(self, max_workers=5, csv_file=None, risk_profile="moderate", 
                 focus_growth=False, focus_momentum=False, min_volatility=0.0):
        self.max_workers = max_workers
        self.setup_logging()
        self.results = []
        self.failed_stocks = []
        self.total_stocks = 0
        self.processed_stocks = 0
        self.company_names = {}  # Map symbols to company names
        
        # 🚀 ENHANCEMENT: Add caching system
        self.cache_enabled = True
        self.cache_expiry_hours = 4  # Cache expires after 4 hours
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
        if self.risk_profile not in ["conservative", "moderate", "aggressive"]:
            logging.warning(f"Invalid risk profile '{self.risk_profile}', defaulting to 'moderate'")
            self.risk_profile = "moderate"
        logging.info(f"Risk profile set to: {self.risk_profile}")      # conservative, moderate, aggressive
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
    
    def load_stocks_from_csv(self, csv_file):
        """Load stock symbols from a CSV file"""
        try:
            logging.info(f"Loading stocks from CSV: {csv_file}")
            self._csv_path = csv_file  # Store path for later reference
            df = pd.read_csv(csv_file)
            
            # Check if the CSV has the required columns
            if 'Symbol' in df.columns:
                symbols = df['Symbol'].dropna().tolist()
                
                # If there's a company name column, create a mapping
                if 'Company Name' in df.columns:
                    self.company_names = dict(zip(df['Symbol'], df['Company Name']))
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
        return [
            # NIFTY 50 core stocks
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", 
            "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", 
            "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", "SUNPHARMA", "WIPRO",
            "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", "POWERGRID", "NTPC",
            # Default list reduced to 25 stocks for brevity
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
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.performance_metrics['cache_hits'] += 1
                    logging.info(f"Cache hit for {symbol} ({analysis_type})")
                    return data
            except Exception as e:
                logging.warning(f"Failed to load cache for {symbol}: {e}")
        
        return None
    
    def save_to_cache(self, symbol: str, data: Dict, analysis_type: str = "comprehensive"):
        """Save analysis data to cache"""
        if not self.cache_enabled:
            return
            
        cache_path = self.get_cache_path(symbol, analysis_type)
        
        try:
            # Ensure data is JSON serializable
            serializable_data = {}
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    serializable_data[key] = value
                elif isinstance(value, (list, dict)):
                    serializable_data[key] = str(value)
                else:
                    serializable_data[key] = str(value)
            
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
        
    def setup_logging(self):
        """Setup comprehensive logging"""
        os.makedirs('data', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        
        self.log_filename = f"data/top200_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_filename),
                logging.StreamHandler()
            ]
        )
        
        logging.info("Dynamic NSE Stock Analysis Initialized")
    
    def analyze_single_stock(self, symbol):
        """Analyze a single stock with comprehensive data"""
        try:
            start_time = time.time()
            
            # Initialize result dictionary
            stock_data = {
                'symbol': symbol,
                'company_name': self.company_names.get(symbol, symbol),  # Use company name from CSV if available
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'processing'
            }
            
            # 1. Fundamental Analysis
            fund_data = get_comprehensive_stock_data(symbol)
            if fund_data:
                stock_data.update(fund_data)
                stock_data['fundamental_status'] = 'success'
                logging.info(f"Fundamental analysis completed for {symbol}: {len(fund_data)} fields")
            else:
                stock_data['fundamental_status'] = 'failed'
                logging.warning(f"Fundamental analysis failed for {symbol}")
            
            # 2. Enhanced Technical Analysis
            enhanced_tech_data = get_short_term_technical_analysis(symbol, period_days=90)
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
            
            # 3. Legacy Technical Analysis
            try:
                ticker = yf.Ticker(f"{symbol}.NS")
                hist = ticker.history(period="1y", interval="1d")
                
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
            
            # 4. Calculate Comprehensive Scores
            fund_score = stock_data.get('fundamental_score', 50)
            enhanced_score = enhanced_tech_data.get('short_term_score', 50) if enhanced_tech_data else 50
            legacy_score = stock_data.get('legacy_technical_score', 50)
            
            # 5. ENHANCED: Undervaluation Detection
            undervaluation_score = self.calculate_undervaluation_score(stock_data)
            
            # Multiple scoring approaches
            stock_data.update({
                'fundamental_score_final': fund_score,
                'enhanced_technical_score_final': enhanced_score,
                'legacy_technical_score_final': legacy_score,
                'undervaluation_score': undervaluation_score,
                'overall_score_balanced': (fund_score * 0.6) + (enhanced_score * 0.4),
                'overall_score_triple': (fund_score * 0.5) + (enhanced_score * 0.3) + (legacy_score * 0.2),
                'overall_score_with_value': (fund_score * 0.4) + (enhanced_score * 0.3) + (undervaluation_score * 0.3),
                # Provide canonical columns some exporters/search tools expect
                'TechnicalScore': enhanced_score if enhanced_score else legacy_score,
                'FundamentalScore': fund_score,
                'OverallScore': (fund_score * 0.4) + (enhanced_score * 0.3) + (undervaluation_score * 0.3),
                'analysis_duration_seconds': round(time.time() - start_time, 2),
                'status': 'completed'
            })
            
            # Enhanced recommendation with undervaluation consideration
            best_score = stock_data['overall_score_with_value']
            is_undervalued = undervaluation_score >= 65
            
            if best_score >= 70 and is_undervalued:
                recommendation = "🟢 STRONG BUY (UNDERVALUED)"
            elif best_score >= 70:
                recommendation = "🟢 STRONG BUY"
            elif best_score >= 60 and is_undervalued:
                recommendation = "🟢 BUY (VALUE)"
            elif best_score >= 60:
                recommendation = "🟢 BUY"
            elif best_score >= 50:
                recommendation = "🟡 HOLD"
            elif best_score >= 40:
                recommendation = "🟠 WEAK SELL"
            else:
                recommendation = "🔴 SELL"
            
            stock_data['final_recommendation'] = recommendation
            
            # Convert complex objects to strings for Excel compatibility
            for key, value in stock_data.items():
                if isinstance(value, (list, dict)):
                    try:
                        stock_data[key] = str(value)
                    except Exception:
                        # Handle conversion errors
                        stock_data[key] = f"[Error converting {key}]"
                elif pd.isna(value):
                    stock_data[key] = ''
                elif value is None:
                    stock_data[key] = ''
            
            # Remove emojis from logging to avoid encoding issues in Windows console
            clean_recommendation = recommendation
            for emoji in ['🔵', '🟢', '🟡', '🟠', '🔴']:
                if emoji in clean_recommendation:
                    clean_recommendation = clean_recommendation.replace(emoji, '')
            
            logging.info(f"Completed analysis for {symbol}: Score={best_score:.1f}, Recommendation={clean_recommendation.strip()}")
            return stock_data
            
        except Exception as e:
            error_data = {
                'symbol': symbol,
                'status': 'error',
                'error_message': str(e),
                'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            logging.error(f"Analysis failed for {symbol}: {e}")
            return error_data
    
    def calculate_undervaluation_score(self, stock_data):
        """
        ENHANCEMENT 1: Advanced Undervaluation Detection
        Calculate comprehensive undervaluation score based on multiple criteria
        """
        try:
            score_components = []
            weights = []
            
            # 1. P/E Ratio Analysis (25% weight)
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
                weights.append(0.25)
            
            # 2. P/B Ratio Analysis (20% weight)
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
                weights.append(0.20)
            
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
            if roe and pb_ratio and pb_ratio > 0:
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
                if debt_eq <= 0.3:
                    debt_score = 100
                elif debt_eq <= 0.5:
                    debt_score = 80
                elif debt_eq <= 0.7:
                    debt_score = 60
                elif debt_eq <= 1.0:
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
            week_52_low = stock_data.get('52w_low', None)
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
            
            # Calculate weighted average
            if score_components:
                total_weight = sum(weights)
                if total_weight > 0:
                    weighted_score = sum(score * weight for score, weight in zip(score_components, weights)) / total_weight
                    return round(weighted_score, 1)
            
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
            profit_growth = stock_data.get('profit_growth', 0)
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
            
            # 3. Technical Momentum (25% weight) - Price action strength
            technical_score = stock_data.get('enhanced_technical_score_final', 
                                           stock_data.get('technical_score', 50))
            if technical_score and technical_score > 0:
                # Boost for strong technical momentum
                if technical_score >= 80:     # Very strong momentum
                    tech_momentum = 95
                elif technical_score >= 70:   # Strong momentum
                    tech_momentum = 85
                elif technical_score >= 60:   # Good momentum
                    tech_momentum = 70
                else:                         # Weak momentum
                    tech_momentum = 40
                score_components.append(tech_momentum)
                weights.append(0.25)
            
            # 4. Price Performance vs 52-week range (15% weight)
            current_price = stock_data.get('current_price', None)
            week_52_high = stock_data.get('52w_high', None)
            week_52_low = stock_data.get('52w_low', None)
            
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
                    (stats['strong_buy_count'] / stats['count'] * 100) * 0.3
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
                    # Get volatility data with retry logic
                    ticker = yf.Ticker(f"{symbol}.NS")
                    hist = ticker.history(period="6mo", interval="1d")  # Fixed: 6mo instead of 6m
                    
                    if not hist.empty and len(hist) > 20:
                        # Calculate daily returns
                        hist['returns'] = hist['Close'].pct_change()
                        
                        # Risk metrics
                        volatility = hist['returns'].std() * (252 ** 0.5) * 100  # Annualized volatility
                        max_drawdown = self.calculate_max_drawdown(hist['Close'])
                        beta = self.calculate_beta(hist['returns'])
                        
                        # Risk-adjusted scores
                        overall_score = row.get('overall_score_with_value', 50)
                        underval_score = row.get('undervaluation_score', 50)
                        
                        # Sharpe ratio proxy (using score as return proxy)
                        risk_free_rate = 6.5  # Approximate Indian risk-free rate
                        sharpe_proxy = (overall_score - risk_free_rate) / max(volatility, 1)
                        
                        # Risk-adjusted overall score
                        risk_penalty = min(volatility / 20, 2)  # Penalty for high volatility
                        risk_adjusted_score = overall_score - risk_penalty
                        
                        # Risk category based on user profile and volatility
                        # Adjust thresholds based on user's risk profile
                        if self.risk_profile == "conservative":
                            # Conservative: Lower volatility tolerance
                            if volatility <= 10:
                                risk_category = "LOW"
                            elif volatility <= 18:
                                risk_category = "MODERATE" 
                            elif volatility <= 28:
                                risk_category = "HIGH"
                            else:
                                risk_category = "VERY HIGH"
                        elif self.risk_profile == "aggressive":
                            # Aggressive: Higher volatility tolerance
                            if volatility <= 20:
                                risk_category = "LOW"
                            elif volatility <= 35:
                                risk_category = "MODERATE"
                            elif volatility <= 50:
                                risk_category = "HIGH" 
                            else:
                                risk_category = "VERY HIGH"
                        else:  # moderate (default)
                            # Moderate: Standard volatility tolerance
                            if volatility <= 15:
                                risk_category = "LOW"
                            elif volatility <= 25:
                                risk_category = "MODERATE"
                            elif volatility <= 35:
                                risk_category = "HIGH"
                            else:
                                risk_category = "VERY HIGH"
                        
                        # Update results
                        results_df.at[idx, 'volatility_6m'] = round(volatility, 2)
                        results_df.at[idx, 'max_drawdown_6m'] = round(max_drawdown, 2)
                        results_df.at[idx, 'beta'] = round(beta, 2)
                        results_df.at[idx, 'sharpe_proxy'] = round(sharpe_proxy, 2)
                        results_df.at[idx, 'risk_adjusted_score'] = round(risk_adjusted_score, 1)
                        results_df.at[idx, 'risk_category'] = risk_category
                        # Debug log for risk category assignment
                        logging.debug(f"{symbol}: volatility={volatility:.1f}%, profile={self.risk_profile}, risk_category={risk_category}")
                        
                    else:
                        # Default values if no data
                        results_df.at[idx, 'volatility_6m'] = None
                        results_df.at[idx, 'max_drawdown_6m'] = None
                        results_df.at[idx, 'beta'] = None
                        results_df.at[idx, 'sharpe_proxy'] = None
                        results_df.at[idx, 'risk_adjusted_score'] = row.get('overall_score_with_value', 50)
                        results_df.at[idx, 'risk_category'] = "UNKNOWN"
                        
                except Exception as e:
                    logging.warning(f"Risk calculation failed for {symbol}: {e}")
                    # Set default risk values
                    results_df.at[idx, 'volatility_6m'] = None
                    results_df.at[idx, 'max_drawdown_6m'] = None
                    results_df.at[idx, 'beta'] = None
                    results_df.at[idx, 'sharpe_proxy'] = None
                    results_df.at[idx, 'risk_adjusted_score'] = row.get('overall_score_with_value', 50)
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
        except:
            return 0
    
    def calculate_beta(self, returns):
        """Calculate beta against market (simplified)"""
        try:
            # Using a simplified beta calculation
            # In practice, you'd use NIFTY50 returns as market benchmark
            market_volatility = 0.20  # Approximate market volatility
            stock_volatility = returns.std() * (252 ** 0.5)
            return stock_volatility / market_volatility
        except:
            return 1.0
    
    def generate_portfolio_allocation_suggestions(self, results_df, target_amount=100000):
        """
        ENHANCEMENT 4: Portfolio Allocation Suggestions
        Generate optimized portfolio allocation based on risk-return analysis
        """
        try:
            # Filter for investment-worthy stocks
            investment_candidates = results_df[
                (results_df['final_recommendation'].str.contains('BUY', na=False)) &
                (results_df['overall_score_with_value'] >= 60) &
                (results_df['risk_category'].isin(['LOW', 'MODERATE'])) &
                (results_df['undervaluation_score'] >= 55)
            ].copy()
            
            if len(investment_candidates) == 0:
                logging.warning("No suitable investment candidates found")
                return None
            
            # Sort by risk-adjusted score
            investment_candidates = investment_candidates.sort_values('risk_adjusted_score', ascending=False)
            
            # Portfolio construction rules
            max_positions = min(15, len(investment_candidates))  # Maximum 15 positions
            top_candidates = investment_candidates.head(max_positions)
            
            # Calculate allocation weights based on multiple factors
            allocation_data = []
            
            for idx, stock in top_candidates.iterrows():
                # Base weight from risk-adjusted score
                base_weight = stock['risk_adjusted_score'] / 100
                
                # Sector diversification adjustment
                sector = stock.get('sector', 'Unknown')
                sector_count = len(top_candidates[top_candidates['sector'] == sector])
                sector_adjustment = 1.0 if sector_count <= 2 else 0.8  # Reduce weight if too many from same sector
                
                # Risk adjustment
                risk_cat = stock.get('risk_category', 'UNKNOWN')
                # If risk category is still unknown, calculate it based on volatility and profile
                if risk_cat in ['UNKNOWN', None, '']:
                    volatility = stock.get('volatility_6m', 0)
                    if volatility > 0:
                        # Apply same logic as risk calculation
                        if self.risk_profile == "conservative":
                            if volatility <= 10:
                                risk_cat = "LOW"
                            elif volatility <= 18:
                                risk_cat = "MODERATE"
                            elif volatility <= 28:
                                risk_cat = "HIGH"
                            else:
                                risk_cat = "VERY HIGH"
                        elif self.risk_profile == "aggressive":
                            if volatility <= 20:
                                risk_cat = "LOW"
                            elif volatility <= 35:
                                risk_cat = "MODERATE"
                            elif volatility <= 50:
                                risk_cat = "HIGH"
                            else:
                                risk_cat = "VERY HIGH"
                        else:  # moderate
                            if volatility <= 15:
                                risk_cat = "LOW"
                            elif volatility <= 25:
                                risk_cat = "MODERATE"
                            elif volatility <= 35:
                                risk_cat = "HIGH"
                            else:
                                risk_cat = "VERY HIGH"
                    else:
                        # Default based on risk profile when no volatility data
                        if self.risk_profile == "conservative":
                            risk_cat = "LOW"
                        elif self.risk_profile == "aggressive":
                            risk_cat = "HIGH"
                        else:
                            risk_cat = "MODERATE"
                if risk_cat == 'LOW':
                    risk_adjustment = 1.2
                elif risk_cat == 'MODERATE':
                    risk_adjustment = 1.0
                else:
                    risk_adjustment = 0.8
                
                # Undervaluation bonus
                underval_score = stock.get('undervaluation_score', 50)
                underval_bonus = 1.0 + (max(0, underval_score - 60) / 100)
                
                # Final weight calculation
                final_weight = base_weight * sector_adjustment * risk_adjustment * underval_bonus
                
                allocation_data.append({
                    'symbol': stock['symbol'],
                    'company_name': stock.get('company_name', stock['symbol']),
                    'sector': sector,
                    'overall_score': stock['overall_score_with_value'],
                    'risk_adjusted_score': stock['risk_adjusted_score'],
                    'undervaluation_score': stock['undervaluation_score'],
                    'risk_category': risk_cat,  # Now properly calculated above
                    'raw_weight': final_weight,
                    'current_price': stock.get('current_price', 0),
                    'recommendation': stock.get('final_recommendation', ''),
                    'volatility_6m': stock.get('volatility_6m', 0)  # Include volatility for reference
                })
            
            # Normalize weights to sum to 100%
            allocation_df = pd.DataFrame(allocation_data)
            total_weight = allocation_df['raw_weight'].sum()
            allocation_df['allocation_percentage'] = (allocation_df['raw_weight'] / total_weight * 100).round(2)
            
            # Calculate investment amounts
            allocation_df['investment_amount'] = (allocation_df['allocation_percentage'] / 100 * target_amount).round(0)
            allocation_df['suggested_quantity'] = (
                allocation_df['investment_amount'] / allocation_df['current_price']
            ).round(0)
            
            # Sort by allocation percentage
            allocation_df = allocation_df.sort_values('allocation_percentage', ascending=False)
            
            # Portfolio summary statistics
            portfolio_summary = {
                'total_stocks': len(allocation_df),
                'target_amount': target_amount,
                'avg_score': allocation_df['overall_score'].mean(),
                'avg_undervaluation': allocation_df['undervaluation_score'].mean(),
                'sector_count': allocation_df['sector'].nunique(),
                'low_risk_percentage': len(allocation_df[allocation_df['risk_category'] == 'LOW']) / len(allocation_df) * 100,
                'high_conviction_percentage': len(allocation_df[allocation_df['allocation_percentage'] >= 8]) / len(allocation_df) * 100
            }
            
            self.portfolio_allocation = {
                'allocation_df': allocation_df,
                'summary': portfolio_summary
            }
            
            logging.info(f"Generated portfolio allocation for {len(allocation_df)} stocks")
            return self.portfolio_allocation
            
        except Exception as e:
            logging.error(f"Error generating portfolio allocation: {e}")
            return None
    
    def analyze_batch(self, batch_size=10):
        """Analyze stocks in batches to avoid overwhelming the system"""
        total_stocks = len(self.stock_list)
        self.total_stocks = total_stocks
        
        print(f"🚀 Starting Dynamic NSE Stock Analysis")
        print(f"📊 Total stocks to analyze: {total_stocks}")
        print(f"🔄 Batch size: {batch_size}")
        print(f"👥 Max workers: {self.max_workers}")
        print(f"🗂️  Company names available: {len(self.company_names) > 0}")
        print("=" * 80)
        
        logging.info(f"Starting batch analysis of {total_stocks} stocks")
        
        start_time = time.time()
        
        # Process in batches
        for batch_start in range(0, total_stocks, batch_size):
            batch_end = min(batch_start + batch_size, total_stocks)
            current_batch = self.stock_list[batch_start:batch_end]
            
            print(f"\n📦 Processing Batch {(batch_start//batch_size)+1}: Stocks {batch_start+1}-{batch_end}")
            print("-" * 60)
            
            batch_results = []
            batch_start_time = time.time()
            
            # Use ThreadPoolExecutor for concurrent processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_stock = {
                    executor.submit(self.analyze_single_stock, stock): stock 
                    for stock in current_batch
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_stock):
                    stock = future_to_stock[future]
                    try:
                        result = future.result(timeout=120)  # 2 minute timeout per stock
                        if result:
                            batch_results.append(result)
                            self.processed_stocks += 1
                            
                            status = result.get('status', 'unknown')
                            score = result.get('overall_score_triple', 0)
                            recommendation = result.get('final_recommendation', 'N/A')
                            
                            print(f"   ✅ {stock:<12}: {status:<10} | Score: {score:5.1f} | {recommendation}")
                            
                            if status == 'error':
                                self.failed_stocks.append(stock)
                        else:
                            # Handle case where result is None
                            print(f"   ⚠️ {stock:<12}: no data returned")
                            self.failed_stocks.append(stock)
                            logging.warning(f"No data returned for {stock}")
                            self.processed_stocks += 1
                            
                    except Exception as e:
                        print(f"   ❌ {stock:<12}: timeout/error - {str(e)[:50]}")
                        self.failed_stocks.append(stock)
                        self.processed_stocks += 1
                        logging.error(f"Batch processing error for {stock}: {e}")
            
            # Add batch results to main results
            self.results.extend(batch_results)
            
            batch_duration = time.time() - batch_start_time
            progress = (self.processed_stocks / total_stocks) * 100
            
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
        print(f"   ❌ Failed: {len(self.failed_stocks)}")
        print(f"   ⏱️  Total duration: {total_duration/60:.1f} minutes")
        if total_stocks > 0:
            print(f"   📈 Average per stock: {total_duration/total_stocks:.1f} seconds")
        else:
            print(f"   📈 No stocks processed")
        
        # Use emoji-free text for logging to avoid encoding issues
        logging.info(f"Batch analysis completed: {len(self.results)} results, {len(self.failed_stocks)} failures")
        
        return self.results
    
    def calculate_support_resistance_levels(self, symbol: str, risk_profile: str = "moderate") -> Dict[str, Any]:
        """
        🚀 ENHANCEMENT: Calculate Support & Resistance Levels and Trading Plan
        Enhanced for different risk profiles: conservative, moderate, aggressive
        """
        try:
            # Fetch detailed price data
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
            target_1_pct = ((target_1 - current_price) / current_price) * 100
            target_2_pct = ((target_2 - current_price) / current_price) * 100
            target_3_pct = ((target_3 - current_price) / current_price) * 100
            stop_loss_pct = ((stop_loss - current_price) / current_price) * 100
            stop_loss_tight_pct = ((stop_loss_tight - current_price) / current_price) * 100
            
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
            print("❌ No results to generate report")
            return None
        
        print(f"\n📊 GENERATING ENHANCED COMPREHENSIVE REPORT")
        print("-" * 60)
        
        try:
            # Create DataFrame
            df = pd.DataFrame(self.results)
            
            print("🔄 Applying enhancements...")
            
            # Apply all enhancements
            print("   1️⃣ Calculating sector rankings...")
            df = self.calculate_sector_rankings(df)
            
            print("   2️⃣ Analyzing risk-return metrics...")
            if not getattr(self, 'skip_risk', False):
                df = self.calculate_risk_return_metrics(df)
            else:
                print("      ⚡ Skipped (--skip-risk enabled)")
                # Add default risk columns
                df['risk_adjusted_score'] = df['overall_score_with_value']
                df['risk_category'] = 'UNKNOWN'
            
            print("   3️⃣ Generating portfolio allocation...")
            target_amount = getattr(self, 'portfolio_amount', 100000)
            portfolio_allocation = self.generate_portfolio_allocation_suggestions(df, target_amount)
            
            # Sort by risk-adjusted score (new primary metric)
            df = df.sort_values('risk_adjusted_score', ascending=False, na_position='last')
            
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
            print(f"❌ Enhanced Excel generation failed: {e}")
            logging.error(f"Enhanced Excel generation failed: {e}")
            return None
            
        except Exception as e:
            print(f"❌ Enhanced Excel generation failed: {e}")
            logging.error(f"Enhanced Excel generation failed: {e}")
            return None
    
    def generate_enhanced_excel_report(self, df, portfolio_allocation):
        """
        ENHANCEMENT 5: Enhanced Excel reporting with Support/Resistance and Trading Plans
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"reports/Enhanced_Stock_Report_{timestamp}.xlsx"
            
            print("   🔄 Calculating Support & Resistance levels for top stocks...")
            
            # Add Support & Resistance data for top performing stocks
            top_stocks = df.head(20)  # Calculate for top 20 stocks
            support_resistance_data = []
            
            for idx, stock in top_stocks.iterrows():
                symbol = stock['symbol']
                print(f"      📊 Calculating S&R for {symbol}...")
                
                sr_data = self.calculate_support_resistance_levels(symbol)
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
            
            # Create Excel writer with xlsxwriter engine for charts
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Define formats
                header_format = workbook.add_format({
                    'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
                    'border': 1, 'align': 'center'
                })
                
                subheader_format = workbook.add_format({
                    'bold': True, 'bg_color': '#D9E2F3', 'font_color': 'black',
                    'border': 1, 'align': 'center'
                })
                
                data_format = workbook.add_format({
                    'border': 1, 'align': 'center'
                })
                
                text_format = workbook.add_format({
                    'border': 1, 'text_wrap': True, 'align': 'left', 'valign': 'top'
                })
                
                price_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'num_format': '₹#,##0.00'
                })
                
                percent_format = workbook.add_format({
                    'border': 1, 'align': 'center', 'num_format': '0.0%'
                })
                
                # 1. Summary Sheet with top picks
                summary_cols = ['symbol', 'company_name', 'sector', 'overall_score_with_value', 
                               'undervaluation_score', 'risk_adjusted_score', 'risk_category',
                               'final_recommendation', 'current_price']
                available_cols = [col for col in summary_cols if col in df.columns]
                summary_df = df[available_cols].head(50)
                summary_df.to_excel(writer, sheet_name='Top Picks', index=False)
                
                # 🚀 NEW: Trading Plans & Support/Resistance Sheet
                if not sr_df.empty:
                    worksheet = workbook.add_worksheet('Trading Plans')
                    
                    # Write headers
                    headers = ['Symbol', 'Company', 'Current Price', 'Score', 'Recommendation',
                              'Immediate Resistance', 'Strong Resistance', 'Immediate Support', 'Strong Support',
                              'Entry Low', 'Entry High', 'Target 1', 'Target 1 %', 'Target 2', 'Target 2 %',
                              'Stop Loss', 'Stop Loss %', 'Risk/Reward Ratio', 'Trading Plan']
                    
                    for col, header in enumerate(headers):
                        worksheet.write(0, col, header, header_format)
                    
                    # Write data
                    for row, (_, stock) in enumerate(sr_df.iterrows(), 1):
                        worksheet.write(row, 0, stock['symbol'], data_format)
                        worksheet.write(row, 1, str(stock['company_name']), data_format)
                        worksheet.write(row, 2, stock['current_price'], price_format)
                        worksheet.write(row, 3, stock['overall_score'], data_format)
                        worksheet.write(row, 4, str(stock['recommendation']), data_format)
                        worksheet.write(row, 5, stock['immediate_resistance'], price_format)
                        worksheet.write(row, 6, stock['strong_resistance'], price_format)
                        worksheet.write(row, 7, stock['immediate_support'], price_format)
                        worksheet.write(row, 8, stock['strong_support'], price_format)
                        worksheet.write(row, 9, stock['entry_range_low'], price_format)
                        worksheet.write(row, 10, stock['entry_range_high'], price_format)
                        worksheet.write(row, 11, stock['target_1'], price_format)
                        worksheet.write(row, 12, stock['target_1_pct']/100 if stock['target_1_pct'] else 0, percent_format)
                        worksheet.write(row, 13, stock['target_2'], price_format)
                        worksheet.write(row, 14, stock['target_2_pct']/100 if stock['target_2_pct'] else 0, percent_format)
                        worksheet.write(row, 15, stock['stop_loss'], price_format)
                        worksheet.write(row, 16, stock['stop_loss_pct']/100 if stock['stop_loss_pct'] else 0, percent_format)
                        worksheet.write(row, 17, stock.get('risk_reward_ratio', 0), data_format)
                        worksheet.write(row, 18, str(stock['trading_plan_text']), text_format)
                    
                    # Set column widths
                    worksheet.set_column('A:A', 12)  # Symbol
                    worksheet.set_column('B:B', 25)  # Company
                    worksheet.set_column('C:Q', 12)  # Price columns
                    worksheet.set_column('R:R', 80)  # Trading plan text
                    worksheet.set_row(0, 20)  # Header row height
                    
                    # Set row heights for data rows
                    for row in range(1, len(sr_df) + 1):
                        worksheet.set_row(row, 100)  # Make rows taller for trading plan text
                
                # 2. Undervalued Stocks Sheet
                undervalued = df[df.get('undervaluation_score', pd.Series()).fillna(0) >= 65].head(30)
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
                
                # 5. Portfolio Allocation Sheet
                if portfolio_allocation:
                    alloc_df = portfolio_allocation['allocation_df']
                    alloc_df.to_excel(writer, sheet_name='Portfolio Allocation', index=False)
                    
                    # Portfolio summary
                    summary_data = portfolio_allocation['summary']
                    summary_sheet = pd.DataFrame([summary_data])
                    summary_sheet.to_excel(writer, sheet_name='Portfolio Summary', index=False)
                
                # 6. Complete Data Sheet
                df.to_excel(writer, sheet_name='Complete Data', index=False)
                
                print(f"   📋 Generated {len(writer.sheets)} worksheets with Trading Plans")
            
            return filename
            
        except Exception as e:
            logging.error(f"Enhanced Excel generation error: {e}")
            # Fallback to basic Excel generation
            try:
                excel_generator = ExcelReportGenerator()
                return excel_generator.generate_daily_report(df)
            except:
                print(f"   ⚠️ Fallback Excel generation also failed: {e}")
                return None
    
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
            print(f"   Recommended Stocks        : {alloc_summary['total_stocks']}")
            print(f"   Average Overall Score     : {alloc_summary['avg_score']:.1f}")
            print(f"   Sector Diversification    : {alloc_summary['sector_count']} sectors")
            print(f"   Low Risk Allocation       : {alloc_summary['low_risk_percentage']:.1f}%")
    
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
                score = row['overall_score_triple']
                rec = row['final_recommendation']
                print(f"   {idx:2d}. {symbol:<12}: {score:5.1f} - {rec}")
        
        # Recommendation distribution
        if 'final_recommendation' in df.columns:
            rec_counts = df['final_recommendation'].value_counts()
            print(f"\n📋 RECOMMENDATION DISTRIBUTION:")
            print("-" * 35)
            for rec, count in rec_counts.items():
                percentage = (count / total_stocks) * 100
                print(f"   {rec:<25}: {count:3d} ({percentage:4.1f}%)")
        
        # Failed stocks
        if self.failed_stocks:
            print(f"\n❌ FAILED ANALYSIS ({len(self.failed_stocks)} stocks):")
            print("-" * 30)
            for stock in self.failed_stocks[:10]:  # Show first 10
                print(f"   • {stock}")
            if len(self.failed_stocks) > 10:
                print(f"   ... and {len(self.failed_stocks) - 10} more")

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
        print(f"❌ Failed to export default stocks: {e}")
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
        results_df['technical_score'] = 50
    if 'fundamental_score' not in results_df.columns:
        results_df['fundamental_score'] = 50
    if 'overall_score_with_value' not in results_df.columns:
        results_df['overall_score_with_value'] = 50
    
    # Filter valid stocks (remove nulls and ensure minimum data quality)
    valid_df = results_df.dropna(subset=['symbol']).copy()
    
    # 1. TOP 10 UNDERVALUED - Based on undervaluation_score
    print("\n1️⃣ TOP 10 UNDERVALUED STOCKS:")
    print("-" * 50)
    undervalued = valid_df.nlargest(10, 'undervaluation_score')[
        ['symbol', 'company_name', 'undervaluation_score', 'current_price', 'pe_ratio', 'pb_ratio', 'dividend_yield']
    ]
    for i, (_, row) in enumerate(undervalued.iterrows(), 1):
        print(f"{i:2d}. {row['symbol']:12} | {str(row['company_name'])[:30]:30} | "
              f"Score: {row['undervaluation_score']:5.1f} | PE: {row['pe_ratio']:6.1f} | "
              f"PB: {row['pb_ratio']:5.2f} | Price: ₹{row['current_price']:7.1f}")
    
    # 2. TOP 10 GROWTH - Based on revenue growth, earnings growth, and technical momentum
    print("\n2️⃣ TOP 10 GROWTH STOCKS:")
    print("-" * 50)
    
    # Use momentum scoring for aggressive investors, otherwise use standard growth calculation
    if analyzer and hasattr(analyzer, 'focus_growth') and analyzer.focus_growth:
        # Calculate momentum growth score for high-risk investors
        valid_df['growth_score'] = valid_df.apply(
            lambda row: analyzer.calculate_momentum_growth_score(row), axis=1
        )
        print("📊 Using MOMENTUM-BASED scoring for high-growth focus")
    else:
        # Standard growth score combining revenue growth, profit growth, and technical score
        valid_df['growth_score'] = (
            valid_df.get('revenue_growth', 0).fillna(0) * 0.3 +
            valid_df.get('profit_growth', 0).fillna(0) * 0.3 +
            valid_df.get('technical_score', 50).fillna(50) * 0.4
        )
    
    growth = valid_df.nlargest(10, 'growth_score')[
        ['symbol', 'company_name', 'growth_score', 'revenue_growth', 'profit_growth', 'technical_score', 'current_price']
    ]
    for i, (_, row) in enumerate(growth.iterrows(), 1):
        print(f"{i:2d}. {row['symbol']:12} | {str(row['company_name'])[:30]:30} | "
              f"Growth: {row['growth_score']:5.1f} | Rev↗: {row['revenue_growth']:6.1f}% | "
              f"Profit↗: {row['profit_growth']:6.1f}% | Price: ₹{row['current_price']:7.1f}")
    
    # 3. TOP 10 FUNDAMENTALLY STRONG AND TECHNICALLY STRONG
    print("\n3️⃣ TOP 10 FUNDAMENTALLY STRONG & TECHNICALLY STRONG:")
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
              f"Tech: {row['technical_score']:5.1f} | Price: ₹{row['current_price']:7.1f}")
    
    # 4. TOP 10 FUNDAMENTALLY STRONG AND UNDERVALUED
    print("\n4️⃣ TOP 10 FUNDAMENTALLY STRONG & UNDERVALUED:")
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
              f"Underval: {row['undervaluation_score']:5.1f} | Price: ₹{row['current_price']:7.1f}")
    
    print("\n" + "="*80)
    print("📊 CATEGORY SUMMARY:")
    print(f"   • Undervalued stocks analyzed: {len(valid_df[valid_df['undervaluation_score'] >= 65])}")
    print(f"   • Growth stocks identified: {len(valid_df[valid_df.get('growth_score', 0) >= 60])}")
    print(f"   • Strong fundamental + technical: {len(strong_both) if 'strong_both' in locals() else 0}")
    print(f"   • Strong fundamental + undervalued: {len(strong_undervalued) if 'strong_undervalued' in locals() else 0}")
    print("="*80)

def main():
    """Main execution function"""
    print("🎯 ENHANCED NSE STOCK ANALYSIS - COMPREHENSIVE ANALYSIS WITH AI INSIGHTS")
    print("=" * 90)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Enhanced Analysis of Top 200 NSE stocks with undervaluation detection')
    parser.add_argument('-w', '--workers', type=int, default=3, help='Max worker threads')
    parser.add_argument('-b', '--batch', type=int, default=5, help='Batch size')
    parser.add_argument('-s', '--symbol', type=str, help='Single stock symbol to analyze')
    parser.add_argument('-n', '--num', type=int, default=0, help='Number of stocks to analyze (0 = all stocks in CSV, default: all available)')
    parser.add_argument('-c', '--csv', type=str, help='Path to CSV file with stock symbols (defaults to stock_list_template.csv if available)')
    parser.add_argument('-e', '--export', type=str, help='Export default stock list to a CSV file and exit')
    parser.add_argument('--portfolio-amount', type=float, default=100000, help='Target portfolio amount for allocation suggestions (default: ₹1,00,000)')
    parser.add_argument('--skip-risk', action='store_true', help='Skip risk analysis (faster execution)')
    parser.add_argument('--undervalued-only', action='store_true', help='Focus only on undervalued stocks (score ≥65)')
    parser.add_argument('--top-10-only', action='store_true', help='Show only TOP 10 categories from latest analysis (fast mode)')
    
    # High-risk high-reward investor options
    parser.add_argument('--risk-profile', type=str, choices=['conservative', 'moderate', 'aggressive'], 
                        default='moderate', help='Risk profile for trading strategies (default: moderate)')
    parser.add_argument('--focus-growth', action='store_true', 
                        help='Focus on high-growth stocks (suitable for aggressive investors)')
    parser.add_argument('--focus-momentum', action='store_true', 
                        help='Focus on momentum stocks with technical strength')
    parser.add_argument('--min-volatility', type=float, default=0.0, 
                        help='Minimum volatility threshold for high-risk investors (default: 0.0)')
    
    args = parser.parse_args()
    
    # Handle export request
    if args.export:
        export_default_stocks_to_csv(args.export)
        return
    
    # Handle TOP 10 only mode (quick insights from latest analysis)
    if args.top_10_only:
        print("🚀 QUICK TOP 10 CATEGORIES MODE")
        print("Looking for latest analysis data...")
        
        # Try to find latest analysis Excel file
        import glob
        excel_files = glob.glob("data/nse_analysis_*.xlsx")
        if excel_files:
            latest_file = max(excel_files, key=lambda x: x.split('_')[-1])
            print(f"📊 Loading latest analysis: {latest_file}")
            
            try:
                import pandas as pd
                # Read the main analysis sheet
                df = pd.read_excel(latest_file, sheet_name='Top_Picks')
                generate_top_10_categories(df, analyzer)
                return
            except Exception as e:
                print(f"❌ Error reading latest analysis: {e}")
                print("Please run a full analysis first.")
                return
        else:
            print("❌ No previous analysis found. Please run a full analysis first.")
            return
    
    # Initialize enhanced analyzer with parameters
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
    
    # Handle single stock analysis if requested
    if args.symbol:
        print(f"🔍 Single stock analysis mode: {args.symbol}")
        # Create a new list with just the requested symbol
        analyzer.stock_list = [args.symbol]
    elif args.num > 0:
        # Limit the number of stocks (only if num > 0)
        analyzer.stock_list = analyzer.stock_list[:args.num]
        print(f"🔍 Limited to {args.num} stocks")
    else:
        # args.num == 0 means analyze all stocks
        print(f"🔍 Analyzing all {len(analyzer.stock_list)} stocks from CSV")
        
    # Display info about CSV if used
    if hasattr(analyzer, '_csv_path') and analyzer._csv_path:
        csv_path = analyzer._csv_path
        is_default = csv_path == "stock_list_template.csv" and not args.csv
        
        if is_default:
            print(f"📄 Using default stock list template: {csv_path}")
        else:
            print(f"📄 Using stock list from CSV: {csv_path}")
            
        print(f"   - Stocks loaded: {len(analyzer.stock_list)}")
        print(f"   - Company names: {'Available' if len(analyzer.company_names) > 0 else 'Not available'}")
    
    # Display enhancement options
    print(f"\n🚀 ENHANCEMENT OPTIONS:")
    print(f"   💰 Portfolio Amount: ₹{args.portfolio_amount:,.0f}")
    print(f"   ⚡ Skip Risk Analysis: {'Yes' if args.skip_risk else 'No'}")
    print(f"   💎 Undervalued Focus: {'Yes' if args.undervalued_only else 'No'}")
    
    # Run batch analysis
    results = analyzer.analyze_batch(batch_size=args.batch)
    
    if results:
        # Generate TOP 10 category analysis (user's requested output)
        if hasattr(analyzer, 'results_df') and analyzer.results_df is not None:
            generate_top_10_categories(analyzer.results_df, analyzer)
        
        # Generate comprehensive report
        report_file = analyzer.generate_comprehensive_report()
        
        if report_file:
            print(f"\n🎉 ANALYSIS COMPLETED SUCCESSFULLY!")
            print(f"📊 Report file: {report_file}")
            print(f"📝 Log file: {analyzer.log_filename}")
            print(f"\n💡 TIP: Check the TOP 10 categories above for quick investment insights!")
            
            # Auto-run report comparison if multiple reports exist
            try:
                import glob
                from pathlib import Path
                
                # Check if we have multiple Enhanced Stock Reports for comparison
                reports_pattern = "reports/Enhanced_Stock_Report_*.xlsx"
                available_reports = glob.glob(reports_pattern)
                
                if len(available_reports) >= 2:
                    print(f"\n🔄 Auto-running report comparison analysis...")
                    
                    # Import and run comparison
                    sys.path.insert(0, str(Path(__file__).parent))
                    
                    try:
                        from report_comparison.analyzer import ReportComparator
                        from report_comparison.reporter import ComparisonReportGenerator
                        
                        # Run comparison
                        comparator = ReportComparator()
                        comparison_results = comparator.compare_reports()
                        
                        # Display console insights
                        comparator.display_console_insights(comparison_results)
                        
                        # Generate Excel comparison report
                        generator = ComparisonReportGenerator()
                        comparison_report = generator.generate_comparison_report(comparison_results)
                        
                        print(f"\n🎉 Comparison analysis completed!")
                        print(f"📊 Comparison Report: {os.path.basename(comparison_report)}")
                        
                    except ImportError as ie:
                        print(f"\n💡 Report comparison module not available: {ie}")
                        print("   Run 'python compare_reports.py' manually for detailed comparison")
                    except Exception as ce:
                        print(f"\n⚠️ Report comparison failed: {ce}")
                        print("   You can run 'python compare_reports.py' manually")
                else:
                    print(f"\n💡 Generate another report to enable automatic comparison analysis")
                    
            except Exception as e:
                # Don't fail the main analysis if comparison fails
                pass
                
        else:
            print(f"\n⚠️  Analysis completed but report generation failed")
    else:
        print(f"\n❌ Analysis failed - no results generated")

if __name__ == "__main__":
    main()
