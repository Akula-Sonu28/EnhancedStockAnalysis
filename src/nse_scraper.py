# Stock Data Fetcher: Using Yahoo Finance as primary source
import logging
import pandas as pd
import yfinance as yf
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import LOG_FILE

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

# List of top 150 NSE stocks
NIFTY_STOCKS = [
    # NIFTY 50 components (top market cap)
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "HDFC.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS",
    "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS",
    "MARUTI.NS", "HCLTECH.NS", "ULTRACEMCO.NS", "SUNPHARMA.NS", "WIPRO.NS",
    "TITAN.NS", "NESTLEIND.NS", "TECHM.NS", "BAJAJFINSV.NS", "POWERGRID.NS",
    "M&M.NS", "NTPC.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "TATACONSUM.NS",
    
    # Large Cap Companies
    "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANITRANS.NS", "AMBUJACEM.NS",
    "APOLLOHOSP.NS", "AUROPHARMA.NS", "BAJAJ-AUTO.NS", "BANDHANBNK.NS", "BANKBARODA.NS",
    "BERGEPAINT.NS", "BIOCON.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS",
    "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COLPAL.NS", "DLF.NS",
    "DABUR.NS", "DMART.NS", "DRREDDY.NS", "EICHERMOT.NS", "GAIL.NS",
    "GLAND.NS", "GODREJCP.NS", "GRASIM.NS", "HAVELLS.NS", "HDFCAMC.NS",
    
    # Mid Cap Leaders
    "INDIGO.NS", "HAL.NS", "JINDALSTEL.NS", "JUBLFOOD.NS", "LICI.NS",
    "LUPIN.NS", "MCDOWELL-N.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "NMDC.NS",
    "ONGC.NS", "PIDILITIND.NS", "SAIL.NS", "SBICARD.NS", "SBILIFE.NS",
    "SIEMENS.NS", "TATACHEM.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "UPL.NS",
    
    # Banking and Financial Services
    "FEDERALBNK.NS", "IDFCFIRSTB.NS", "INDUSINDBK.NS", "CANBK.NS", "INDIANB.NS",
    "UNIONBANK.NS", "RBLBANK.NS", "PFC.NS", "RECLTD.NS", "MFSL.NS",
    
    # IT and Technology
    "LTTS.NS", "MINDTREE.NS", "MPHASIS.NS", "OFSS.NS", "PERSISTENT.NS",
    "COFORGE.NS", "L&TI.NS", "CYIENT.NS", "SONATSOFTW.NS", "RAMCOCEM.NS",
    
    # Pharma and Healthcare
    "ALKEM.NS", "ABBOTINDIA.NS", "DIVISLAB.NS", "TORNTPHARM.NS", "GLAXO.NS",
    "IPCALAB.NS", "NATCOPHARM.NS", "PFIZER.NS", "SANOFI.NS", "ASTRAZEN.NS",
    
    # Manufacturing and Industrial
    "ABB.NS", "ABFRL.NS", "ADANIPOWER.NS", "ASHOKLEY.NS", "AUBANK.NS",
    "BALKRISIND.NS", "BATAINDIA.NS", "BHEL.NS", "CUMMINSIND.NS", "ESCORTS.NS",
    
    # Consumer and Retail
    "EMAMILTD.NS", "FORTIS.NS", "GODREJPROP.NS", "HINDALCO.NS", "IPCALAB.NS",
    "JINDALSTEL.NS", "JSWSTEEL.NS", "LICHSGFIN.NS", "MFSL.NS", "MRF.NS",
    
    # Energy and Utilities
    "NHPC.NS", "NLCINDIA.NS", "NMDC.NS", "ONGC.NS", "PETRONET.NS",
    "POWERGRID.NS", "RECLTD.NS", "SJVN.NS", "TATAPOWER.NS", "THERMAX.NS",
    
    # New Age Companies
    "ZOMATO.NS", "PAYTM.NS", "NYKAA.NS", "POLICYBZR.NS", "IRCTC.NS",
    "CARTRADE.NS", "NAZARA.NS", "EASEMYTRIP.NS", "JUSTDIAL.NS", "INDIAMART.NS"
]

def get_stock_info(symbol):
    """
    Fetch comprehensive stock information from Yahoo Finance
    Returns: Tuple of (symbol, info_dict) or None if failed
    """
    try:
        print(f"Fetching data for {symbol}...")
        stock = yf.Ticker(symbol)
        info = stock.info
        if info and len(info) > 0:
            # Clean up the symbol name by removing .NS
            clean_symbol = symbol.replace(".NS", "")
            print(f"✓ Successfully fetched data for {clean_symbol}")
            logging.info(f"Successfully fetched data for {clean_symbol}")
            return (clean_symbol, info)
        else:
            print(f"✗ No data available for {symbol}")
            logging.warning(f"No data available for {symbol}")
            return None
    except Exception as e:
        print(f"✗ Error fetching data for {symbol}: {str(e)}")
        logging.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def fetch_stock_data_parallel(symbols, max_workers=10):
    """
    Fetch stock data in parallel using ThreadPoolExecutor
    Returns: List of tuples (symbol, info_dict)
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_symbol = {executor.submit(get_stock_info, symbol): symbol 
                          for symbol in symbols}
        
        # Process completed tasks
        for future in as_completed(future_to_symbol):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                symbol = future_to_symbol[future]
                logging.error(f"Task failed for {symbol}: {str(e)}")
    
    return results

def get_top_150_stock_data():
    """
    Main function to get data for top stocks
    Returns: List of tuples (symbol, data)
    """
    logging.info("Starting to fetch stock data...")
    
    results = []
    batch_size = 10  # Process stocks in smaller batches
    
    for i in range(0, len(NIFTY_STOCKS), batch_size):
        batch = NIFTY_STOCKS[i:i+batch_size]
        batch_results = fetch_stock_data_parallel(batch)
        results.extend(batch_results)
        time.sleep(2)  # Add delay between batches
    
    # Log summary
    total_fetched = len(results)
    logging.info(f"Successfully fetched data for {total_fetched} stocks")
    
    if total_fetched < len(NIFTY_STOCKS):
        logging.warning(f"Missing data for {len(NIFTY_STOCKS) - total_fetched} stocks")
    
    return results

def get_ohlcv(symbol, period="1y"):
    """
    Get historical OHLCV data for a stock
    Returns: DataFrame with OHLCV data
    """
    try:
        stock = yf.Ticker(f"{symbol}.NS")
        df = stock.history(period=period)
        if not df.empty:
            return df
        logging.warning(f"No historical data available for {symbol}")
    except Exception as e:
        logging.error(f"Error fetching historical data for {symbol}: {str(e)}")
    return None
