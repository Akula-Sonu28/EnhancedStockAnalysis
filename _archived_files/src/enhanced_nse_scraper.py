"""
Enhanced NSE Scraper with Bhavcopy CSV download
"""
import requests
import pandas as pd
import zipfile
import io
import logging
from datetime import datetime, timedelta
import os
from bs4 import BeautifulSoup
import time

class NSEDataScraper:
    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Create data directory
        os.makedirs("data/raw", exist_ok=True)
    
    def download_bhavcopy(self, date=None):
        """Download NSE Bhavcopy CSV for given date"""
        if date is None:
            date = datetime.now().date()
        
        # Format date for NSE URL
        date_str = date.strftime("%d%m%Y")
        month_str = date.strftime("%b").upper()
        year_str = date.strftime("%Y")
        
        # Bhavcopy URL pattern
        filename = f"cm{date_str}bhav.csv.zip"
        url = f"https://www1.nseindia.com/content/historical/EQUITIES/{year_str}/{month_str}/{filename}"
        
        try:
            logging.info(f"Downloading Bhavcopy for {date}: {url}")
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                # Extract CSV from ZIP
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                    csv_filename = f"cm{date_str}bhav.csv"
                    if csv_filename in zip_file.namelist():
                        csv_content = zip_file.read(csv_filename)
                        
                        # Save to local file
                        local_path = f"data/raw/bhavcopy_{date_str}.csv"
                        with open(local_path, 'wb') as f:
                            f.write(csv_content)
                        
                        # Read as DataFrame
                        df = pd.read_csv(io.StringIO(csv_content.decode('utf-8')))
                        logging.info(f"Successfully downloaded Bhavcopy with {len(df)} records")
                        return df
                    else:
                        logging.error(f"CSV file not found in ZIP: {csv_filename}")
                        return None
            else:
                logging.error(f"Failed to download Bhavcopy: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Error downloading Bhavcopy: {str(e)}")
            return None
    
    def get_top_stocks_list(self, index_name="NIFTY 500"):
        """Get list of top stocks from NSE indices"""
        try:
            # Try to get from NSE API
            url = f"{self.base_url}/api/equity-stockIndices?index={index_name.replace(' ', '%20')}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    stocks = []
                    for stock in data['data']:
                        stocks.append({
                            'symbol': stock.get('symbol', ''),
                            'companyName': stock.get('companyName', ''),
                            'lastPrice': stock.get('lastPrice', 0),
                            'change': stock.get('change', 0),
                            'pChange': stock.get('pChange', 0)
                        })
                    return stocks
            
            # Fallback: Use predefined list of top stocks
            return self._get_fallback_stock_list()
            
        except Exception as e:
            logging.error(f"Error fetching stock list: {str(e)}")
            return self._get_fallback_stock_list()
    
    def _get_fallback_stock_list(self):
        """Fallback list of top Indian stocks"""
        top_stocks = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'HINDUNILVR', 'INFY', 'HDFC', 'ICICIBANK',
            'KOTAKBANK', 'BHARTIARTL', 'ITC', 'SBIN', 'BAJFINANCE', 'LT', 'ASIANPAINT',
            'AXISBANK', 'MARUTI', 'NESTLEIND', 'HCLTECH', 'WIPRO', 'ULTRACEMCO',
            'SUNPHARMA', 'TITAN', 'BAJAJFINSV', 'TECHM', 'POWERGRID', 'NTPC',
            'TATASTEEL', 'COALINDIA', 'HDFCLIFE', 'SBILIFE', 'INDUSINDBK',
            'ADANIPORTS', 'UPL', 'GRASIM', 'BRITANNIA', 'DRREDDY', 'EICHERMOT',
            'BPCL', 'CIPLA', 'JSWSTEEL', 'TATAMOTORS', 'HINDALCO', 'IOC',
            'DIVISLAB', 'HEROMOTOCO', 'BAJAJ-AUTO', 'SHREECEM', 'VEDL', 'GODREJCP'
        ]
        
        return [{'symbol': symbol, 'companyName': symbol} for symbol in top_stocks]
    
    def get_corporate_filings(self, symbol):
        """Get recent corporate filings for a stock"""
        try:
            url = f"{self.base_url}/api/corporate-filings?index=equities&symbol={symbol}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            
        except Exception as e:
            logging.error(f"Error fetching corporate filings for {symbol}: {str(e)}")
        
        return []
    
    def get_stock_info(self, symbol):
        """Get detailed stock information"""
        try:
            url = f"{self.base_url}/api/quote-equity?symbol={symbol}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            
        except Exception as e:
            logging.error(f"Error fetching stock info for {symbol}: {str(e)}")
        
        return {}

# Legacy function compatibility
def get_top_150_stock_data():
    """Legacy compatibility function"""
    scraper = NSEDataScraper()
    stocks = scraper.get_top_stocks_list()
    
    result = []
    for stock in stocks[:150]:  # Limit to 150
        symbol = stock['symbol']
        info = scraper.get_stock_info(symbol)
        result.append((symbol, info))
        time.sleep(0.1)  # Rate limiting
    
    return result
