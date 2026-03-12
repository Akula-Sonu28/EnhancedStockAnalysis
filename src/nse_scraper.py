#!/usr/bin/env python3
"""
Modified NSE Scraper to dynamically load stock symbols from a CSV file
"""

import os
import sys
import logging
import pandas as pd
import yfinance as yf
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import LOG_FILE, REQUEST_DELAY

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

# Function to get stock info for a single stock
def get_stock_info(symbol):
    """
    Get stock information for a single stock
    Returns: stock info dict or None if not found
    """
    try:
        time.sleep(REQUEST_DELAY)

        if not symbol.endswith('.NS'):
            ticker_name = f"{symbol}.NS"
        else:
            ticker_name = symbol
            
        # Check for ticker corrections
        if ticker_name in TICKER_CORRECTIONS:
            ticker_name = TICKER_CORRECTIONS[ticker_name]
            
        stock = yf.Ticker(ticker_name)
        info = stock.info
        if info:
            logging.info(f"Successfully fetched data for {symbol}")
            return info
        else:
            logging.warning(f"No data available for {symbol}")
            return None
    except Exception as e:
        logging.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

# Ticker corrections mapping
TICKER_CORRECTIONS = {
    "HDFC.NS": "HDFCBANK.NS",  # HDFC merged with HDFC Bank
    "MCDOWELL-N.NS": "MCDHOLDING.NS",  # Updated name
    "L&TI.NS": "LTIM.NS",  # L&T Infotech is now LTIM
    "MINDTREE.NS": "LTIM.NS",  # Mindtree merged with L&T Infotech to form LTIM
    "ZOMATO.NS": "ETERNAL.NS",  # Updated ticker
    "IDFC.NS": "IDFCFIRSTB.NS",  # Correct ticker for IDFC First Bank
    "ADANITRANS.NS": "ADANIENT.NS",  # Updated ticker
    "LAXMIMACH.NS": "LXMACHIN.NS",  # Correct ticker for Lakshmi Machine Works
}

def load_stock_list_from_csv(csv_path=None):
    """
    Load stock symbols and company names from a CSV file
    Returns: List of tuples (symbol, company_name)
    """
    stock_list = []
    
    try:
        # Default path if none provided
        if csv_path is None:
            # Try to find CSV in multiple locations
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ind_nifty200list (2).csv'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ind_nifty200list (2).csv'),
                os.path.join(os.getcwd(), 'ind_nifty200list (2).csv')
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    csv_path = path
                    break
        
        if csv_path and os.path.exists(csv_path):
            logging.info(f"Loading stock list from {csv_path}")
            df = pd.read_csv(csv_path)
            
            # Check if required columns exist
            if 'Symbol' in df.columns and 'Company Name' in df.columns:
                # Extract symbols and company names
                for _, row in df.iterrows():
                    symbol = row['Symbol']
                    company = row['Company Name']
                    if pd.notna(symbol) and pd.notna(company):
                        stock_list.append((symbol, company))
                        
                logging.info(f"Successfully loaded {len(stock_list)} stocks from CSV")
                return stock_list
            else:
                logging.error("Required columns 'Symbol' and 'Company Name' not found in CSV")
                return _get_fallback_stock_list()
        else:
            logging.error(f"CSV file not found at {csv_path}")
            return _get_fallback_stock_list()
            
    except Exception as e:
        logging.error(f"Error loading stocks from CSV: {str(e)}")
        return _get_fallback_stock_list()

def _get_fallback_stock_list():
    """
    Return a fallback list of top stocks if CSV loading fails
    """
    logging.info("Using fallback stock list")
    
    # Return a small list of key stocks with company names
    return [
        ("RELIANCE", "Reliance Industries Ltd."),
        ("TCS", "Tata Consultancy Services Ltd."),
        ("HDFCBANK", "HDFC Bank Ltd."),
        ("INFY", "Infosys Ltd."),
        ("ICICIBANK", "ICICI Bank Ltd."),
        ("HINDUNILVR", "Hindustan Unilever Ltd."),
        ("ITC", "ITC Ltd."),
        ("SBIN", "State Bank of India"),
        ("BHARTIARTL", "Bharti Airtel Ltd."),
        ("HINDALCO", "Hindalco Industries Ltd."),
        ("TATASTEEL", "Tata Steel Ltd."),
        ("TATAMOTORS", "Tata Motors Ltd.")
    ]

def get_top_150_stock_data(max_workers=10):
    """
    Get data for top 150 NSE stocks in parallel with error handling
    Returns: List of tuples with (symbol, data)
    """
    # Load stock list from CSV
    stocks = load_stock_list_from_csv()
    
    # Limit to top 150 if needed
    stocks = stocks[:150]
    
    total_stocks = len(stocks)
    logging.info(f"Starting data collection for {total_stocks} stocks")
    print(f"Fetching data for {total_stocks} stocks with {max_workers} parallel workers...")
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks for all stocks
        future_to_stock = {executor.submit(get_stock_info, symbol): (symbol, company) 
                           for symbol, company in stocks}
        
        # Process results as they complete
        count = 0
        for future in as_completed(future_to_stock):
            symbol, company = future_to_stock[future]
            count += 1
            
            try:
                data = future.result()
                if data:
                    # Add company name to data if not present
                    if 'longName' not in data or not data['longName']:
                        data['longName'] = company
                        
                    results.append((symbol, data))
                    sys.stdout.write(f"\rFetched {count}/{total_stocks}: {symbol} ✓")
                else:
                    sys.stdout.write(f"\rFetched {count}/{total_stocks}: {symbol} ✗")
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")
                sys.stdout.write(f"\rFetched {count}/{total_stocks}: {symbol} ✗ (Error: {str(e)})")
            
            sys.stdout.flush()
    
    print(f"\nCompleted fetching data for {len(results)} stocks")
    return results

def get_stock_historical_data(symbol, period="1y", interval="1d"):
    """Get historical OHLCV data for a stock"""
    try:
        if not symbol.endswith('.NS'):
            symbol_ns = f"{symbol}.NS"
        else:
            symbol_ns = symbol
            
        ticker = yf.Ticker(symbol_ns)
        data = ticker.history(period=period, interval=interval)
        
        if not data.empty:
            logging.info(f"Retrieved {len(data)} historical records for {symbol}")
            return data
        else:
            logging.warning(f"No historical data retrieved for {symbol}")
            return None
    except Exception as e:
        logging.error(f"Error retrieving historical data for {symbol}: {str(e)}")
        return None

if __name__ == "__main__":
    # Test the functionality
    print("Testing NSE stock data fetcher...")
    results = get_top_150_stock_data(max_workers=5)
    
    print(f"Successfully fetched data for {len(results)} stocks")
    
    if results:
        sample = results[0]
        print(f"\nSample data for {sample[0]}:")
        print(f"Company: {sample[1].get('longName', 'Unknown')}")
        print(f"Sector: {sample[1].get('sector', 'Unknown')}")
        print(f"Industry: {sample[1].get('industry', 'Unknown')}")
        print(f"Current Price: {sample[1].get('currentPrice', 'Unknown')}")
