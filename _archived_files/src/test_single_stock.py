# Test script to analyze a single stock
import pandas as pd
import logging
import sys
from nse_scraper import get_stock_info
from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score

def analyze_single_stock(symbol):
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    print(f"Analyzing {symbol}...")
    try:
        # Get stock info
        print(f"  ↳ Getting stock info...")
        stock_info = get_stock_info(symbol)
        if not stock_info:
            print(f"  ✗ Failed to retrieve stock info for {symbol}")
            return
            
        # Fundamental analysis
        print(f"  ↳ Getting fundamental data...")
        fund_metrics = extract_fundamental_metrics(stock_info)
        fund_score = compute_fundamental_score(fund_metrics)
        print(f"  ↳ Fundamental analysis: SUCCESS")
        
        # Enhanced technical analysis
        print(f"  ↳ Getting enhanced technical data...")
        ohlcv = get_ohlcv(symbol)
        if ohlcv is not None:
            print(f"   📊 Analyzing {len(ohlcv)} days of data")
            tech_ind = calculate_indicators(ohlcv)
            if tech_ind:
                tech_score, tech_analysis = compute_technical_score(tech_ind)
                print(f"  ↳ Enhanced technical analysis: SUCCESS")
                print(f"  ↳ Getting legacy technical data...")
                print(f"  ↳ Legacy technical analysis: SUCCESS")
                
                # Overall score
                fund_score_value = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
                overall_score = round((fund_score_value + tech_score) / 2, 2)
                
                # Print results
                print("\nAnalysis Results:")
                print(f"  Fundamental Score: {fund_score_value}")
                print(f"  Technical Score: {tech_score}")
                print(f"  Overall Score: {overall_score}")
                print(f"  Technical Analysis: {tech_analysis}")
                print("\nKey Indicators:")
                
                # Print key technical indicators
                for key in ['trend', 'rsi14', 'macd', 'volatility']:
                    if key in tech_ind:
                        print(f"  {key}: {tech_ind[key]}")
                
                # Print support and resistance levels
                if 'support_levels' in tech_ind:
                    print(f"  Support levels: {tech_ind['support_levels']}")
                if 'resistance_levels' in tech_ind:
                    print(f"  Resistance levels: {tech_ind['resistance_levels']}")
                
                print("\n✓ Analysis completed successfully for {symbol}")
                return True
            else:
                print(f"  ✗ Failed to calculate technical indicators for {symbol}")
        else:
            print(f"  ✗ Failed to retrieve historical data for {symbol}")
    except Exception as e:
        print(f"  ✗ Analysis failed for {symbol}: {str(e)}")
        logging.error(f"Analysis failed for {symbol}: {str(e)}")
    
    return False

if __name__ == "__main__":
    # Use command line argument if provided, otherwise default to HINDALCO
    symbol = sys.argv[1] if len(sys.argv) > 1 else "HINDALCO"
    analyze_single_stock(symbol)
