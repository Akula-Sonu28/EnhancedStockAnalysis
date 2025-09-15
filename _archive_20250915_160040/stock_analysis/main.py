#!/usr/bin/env python3
"""
Stock Analysis Package
Main entry point with high-level functions for stock analysis
"""

from .analyzers.technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from .analyzers.fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from .analyzers.enhanced_technical_analyzer import get_short_term_technical_analysis
from .analyzers.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from .data_providers.nse_scraper import get_top_150_stock_data
from .exporters.data_exporter import export_data
from .exporters.json_export import export_to_json
from .exporters.excel_exporter import ExcelExporter
from .core.config import TECHNICAL_WEIGHTS, FUNDAMENTAL_WEIGHTS

import os
import logging
from datetime import datetime
import pandas as pd

def setup_logging(log_dir='logs'):
    """Setup logging with proper configuration"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return log_file

def analyze_stock(symbol, company_name=None, include_fundamental=True, include_technical=True, include_enhanced=True):
    """
    Complete analysis of a single stock
    
    Args:
        symbol (str): Stock symbol
        company_name (str, optional): Company name
        include_fundamental (bool): Whether to include fundamental analysis
        include_technical (bool): Whether to include technical analysis
        include_enhanced (bool): Whether to include enhanced analysis
        
    Returns:
        dict: Stock analysis results
    """
    logging.info(f"Starting analysis for {symbol}")
    
    result = {
        'symbol': symbol,
        'company_name': company_name or symbol,
        'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Technical Analysis
    if include_technical:
        try:
            ohlcv = get_ohlcv(symbol)
            if ohlcv is not None:
                indicators = calculate_indicators(ohlcv)
                if indicators:
                    tech_score, tech_analysis = compute_technical_score(indicators)
                    result['technical_score'] = tech_score
                    result['technical_analysis'] = tech_analysis
                    result.update(indicators)
                    logging.info(f"Technical analysis complete for {symbol}, score: {tech_score}")
                else:
                    logging.warning(f"Failed to calculate technical indicators for {symbol}")
            else:
                logging.warning(f"Failed to get price data for {symbol}")
        except Exception as e:
            logging.error(f"Technical analysis error for {symbol}: {str(e)}")
    
    # Fundamental Analysis
    if include_fundamental:
        try:
            fund_data = extract_fundamental_metrics({'symbol': symbol})
            if fund_data:
                fund_score = compute_fundamental_score(fund_data)
                result.update(fund_data)
                result['fundamental_score'] = fund_score
                logging.info(f"Fundamental analysis complete for {symbol}, score: {fund_score}")
            else:
                logging.warning(f"No fundamental data for {symbol}")
        except Exception as e:
            logging.error(f"Fundamental analysis error for {symbol}: {str(e)}")
    
    # Enhanced Analysis
    if include_enhanced:
        try:
            # Enhanced Technical
            enh_tech = get_short_term_technical_analysis(symbol)
            if enh_tech:
                for k, v in enh_tech.items():
                    result[f'enhanced_{k}'] = v
                logging.info(f"Enhanced technical analysis complete for {symbol}")
                
            # Enhanced Fundamental
            enh_fund = get_comprehensive_stock_data(symbol)
            if enh_fund:
                for k, v in enh_fund.items():
                    if k not in result:
                        result[f'enhanced_{k}'] = v
                logging.info(f"Enhanced fundamental analysis complete for {symbol}")
        except Exception as e:
            logging.error(f"Enhanced analysis error for {symbol}: {str(e)}")
    
    # Calculate overall score if available
    if 'technical_score' in result and 'fundamental_score' in result:
        t_score = result['technical_score']
        f_score = result['fundamental_score']
        result['overall_score'] = (t_score * 0.6) + (f_score * 0.4)
        
    return result

def batch_analyze_stocks(symbols, batch_size=5, max_workers=3):
    """
    Analyze multiple stocks in batches
    
    Args:
        symbols (list): List of stock symbols to analyze
        batch_size (int): Number of stocks to process in parallel
        max_workers (int): Maximum number of worker threads
        
    Returns:
        list: Analysis results for all stocks
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time
    
    results = []
    failed = []
    total = len(symbols)
    processed = 0
    
    logging.info(f"Starting batch analysis of {total} stocks")
    start_time = time.time()
    
    for i in range(0, total, batch_size):
        batch = symbols[i:i+batch_size]
        logging.info(f"Processing batch {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}")
        
        batch_results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(analyze_stock, symbol): symbol for symbol in batch}
            
            for future in as_completed(futures):
                symbol = futures[future]
                processed += 1
                try:
                    data = future.result()
                    if data:
                        batch_results.append(data)
                        logging.info(f"Completed analysis for {symbol} ({processed}/{total})")
                    else:
                        failed.append(symbol)
                        logging.warning(f"Failed to analyze {symbol} ({processed}/{total})")
                except Exception as e:
                    failed.append(symbol)
                    logging.error(f"Error analyzing {symbol}: {str(e)}")
        
        results.extend(batch_results)
        
        # Progress update
        elapsed = time.time() - start_time
        avg_time_per_stock = elapsed / processed if processed > 0 else 0
        remaining_stocks = total - processed
        eta_seconds = avg_time_per_stock * remaining_stocks
        
        logging.info(f"Progress: {processed}/{total} stocks ({processed/total*100:.1f}%)")
        if processed < total:
            logging.info(f"ETA: {eta_seconds/60:.1f} minutes remaining")
            time.sleep(2)  # Brief pause between batches
    
    return results

def load_stock_list(csv_path=None):
    """
    Load stock symbols from a CSV file
    
    Args:
        csv_path (str, optional): Path to CSV file, defaults to data/nifty200_stocks.csv
        
    Returns:
        list: List of stock symbols
    """
    default_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'nifty200_stocks.csv')
    csv_path = csv_path or default_path
    
    try:
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if 'Symbol' in df.columns:
                symbols = df['Symbol'].dropna().tolist()
                logging.info(f"Loaded {len(symbols)} stock symbols from {csv_path}")
                return symbols
            else:
                logging.error(f"CSV file {csv_path} does not contain 'Symbol' column")
        else:
            logging.error(f"CSV file not found: {csv_path}")
    except Exception as e:
        logging.error(f"Error loading stock list: {str(e)}")
    
    # Return a small default list if loading fails
    default_symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
    logging.info(f"Using default list of {len(default_symbols)} stocks")
    return default_symbols
