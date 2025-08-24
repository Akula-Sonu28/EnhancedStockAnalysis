
# Main Orchestration Script
import pandas as pd
import logging
from nse_scraper import get_top_150_stock_data
from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from data_exporter import export_data

def main():
    # Configure logging with a context manager for proper cleanup
    log_file = 'data/analysis.log'
    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[file_handler, stream_handler]
    )
    print("Starting NSE Stock Analysis...")
    
    try:
        logging.info("Starting analysis of NSE stocks...")
        stock_data = get_top_150_stock_data()
        total_stocks = len(stock_data)
        logging.info(f"Found {total_stocks} stocks to analyze")
        
        results = []
        for idx, (symbol, info) in enumerate(stock_data, 1):
            try:
                print(f"\nAnalyzing {symbol} ({idx}/{total_stocks})...")
                # Fundamental
                print(f"Computing fundamental metrics for {symbol}...")
                fund_metrics = extract_fundamental_metrics(info)
                fund_score = compute_fundamental_score(fund_metrics)
                print(f"✓ Fundamental score: {fund_score}")
                
                # Technical
                print(f"Computing technical metrics for {symbol}...")
                ohlcv = get_ohlcv(symbol)
                if ohlcv is not None:
                    tech_ind = calculate_indicators(ohlcv)
                    if tech_ind:
                        tech_score, tech_analysis = compute_technical_score(tech_ind)
                        tech_ind['technical_score'] = tech_score
                        tech_ind['technical_analysis'] = tech_analysis
                        print(f"✓ Technical score: {tech_score}")
                    else:
                        tech_ind = {}
                        tech_score = 0
                        tech_analysis = "No technical data available"
                        print("✗ Failed to calculate technical indicators")
                else:
                    tech_ind = {}
                    tech_score = 0
                    tech_analysis = "No technical data available"
                    print("✗ No technical data available")
                # Overall Score
                fund_score_value = fund_score.get('score', 0) if isinstance(fund_score, dict) else 0
                overall_score = round((fund_score_value + tech_score) / 2, 2)
                # Combine all data
                row = {
                    "symbol": symbol,
                    "FundamentalScore": fund_score_value,
                    "TechnicalScore": tech_score,
                    "OverallScore": overall_score,
                    "FundamentalRating": fund_score.get('rating', 'N/A') if isinstance(fund_score, dict) else 'N/A',
                    "TechnicalAnalysis": tech_analysis
                }
                # Add any available fundamental metrics
                if fund_metrics:
                    row.update(fund_metrics)
                # Add any available technical indicators
                if tech_ind:
                    row.update(tech_ind)
                results.append(row)
            except Exception as e:
                logging.error(f"Error processing {symbol}: {str(e)}")
                # Add the stock with basic information even if there's an error
                results.append({
                    "symbol": symbol,
                    "FundamentalScore": 0,
                    "TechnicalScore": 0,
                    "OverallScore": 0,
                    "FundamentalRating": "Error",
                    "TechnicalAnalysis": f"Error: {str(e)}"
                })
        
        if results:
            df = pd.DataFrame(results)
            logging.info("\nTop 10 stocks by overall score:")
            top_10 = df[['symbol', 'OverallScore']].sort_values('OverallScore', ascending=False).head(10)
            for _, row in top_10.iterrows():
                logging.info(f"{row['symbol']}: {row['OverallScore']}")
            export_data(df)
        else:
            logging.error("No results to process")
            
    except Exception as e:
        logging.error(f"Analysis failed: {str(e)}")
    finally:
        # Cleanup
        logging.info("Cleaning up...")
        file_handler.close()
        stream_handler.close()
        logging.shutdown()

if __name__ == "__main__":
    main()
