# Demo Script: Run complete stock analysis
from stock_analyzer_dashboard import StockAnalyzerDashboard
import yfinance as yf
import json
import logging
from config import LOG_FILE

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

def run_analysis(symbol):
    """Run complete analysis for a stock"""
    try:
        print(f"\nAnalyzing {symbol}...")
        
        # Initialize analyzer
        print("Initializing analyzer...")
        analyzer = StockAnalyzerDashboard()
        
        # Get basic stock info first
        print("Fetching basic stock info...")
        stock = yf.Ticker(symbol)
        info = stock.info
        if not info:
            print(f"Could not fetch basic info for {symbol}")
            return False
        print(f"Successfully fetched basic info for {symbol}")
        
        # Generate complete analysis
        print("Generating complete analysis...")
        analysis = analyzer.generate_complete_analysis(symbol, export_format='json')
        
        if not analysis:
            print(f"No analysis data available for {symbol}")
            return False
            
        # Pretty print the JSON output
        print("\nAnalysis Results:")
        parsed = json.loads(analysis)
        
        # Print Executive Summary
        print("\n=== EXECUTIVE SUMMARY ===")
        summary = parsed['summary']
        print(f"Overall Score: {summary['overall_score']}")
        print(f"Rating: {summary['rating']}")
        print(f"Recommendation: {summary['recommendation']}")
        
        # Print Technical Analysis Summary
        print("\n=== TECHNICAL ANALYSIS ===")
        tech = parsed['technical_analysis']
        print(f"Technical Score: {tech['technical_score']}")
        print(f"Trend Analysis: {tech['analysis']}")
        print("\nTrading Plan:")
        plan = tech['trading_plan']
        print(f"Trade Type: {plan['trade_type']}")
        print(f"Risk/Reward Ratio: {plan['risk_reward_ratio']}")
        
        # Print Fundamental Analysis Highlights
        print("\n=== FUNDAMENTAL ANALYSIS ===")
        fund = parsed['fundamental_analysis']
        print(f"Fundamental Score: {fund['fundamental_score']['score']}")
        print("\nGrowth Analysis:")
        growth = fund['growth_analysis']
        print(f"Growth Score: {growth['growth_score']}")
        
        # Print News Sentiment
        print("\n=== NEWS SENTIMENT ===")
        news = parsed['news_sentiment']
        sentiment = news['sentiment_analysis']
        print(f"Overall Sentiment Score: {sentiment['overall_score']}/10")
        print(f"Interpretation: {sentiment['interpretation']}")
        
        # Print Alternative Suggestions
        print("\n=== ALTERNATIVE STOCKS ===")
        alternatives = parsed['peer_analysis']['alternative_stocks']
        for alt in alternatives[:3]:  # Show top 3 alternatives
            print(f"{alt['symbol']}: Score {alt['combined_score']}, Similarity {alt['similarity_score']}")
        
        return True
        
    except Exception as e:
        print(f"Error running analysis: {str(e)}")
        logging.error(f"Error analyzing {symbol}: {str(e)}")
        return False

if __name__ == "__main__":
    # Test with some popular stocks (with NSE suffix)
    test_stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "SBIN.NS"]
    
    for symbol in test_stocks:
        print(f"\nTrying analysis with {symbol}...")
        try:
            success = run_analysis(symbol)
            if success:
                print(f"\nAnalysis completed successfully for {symbol}!")
                break  # Stop after first successful analysis
            else:
                print(f"\nAnalysis failed for {symbol}. Trying next stock...")
        except Exception as e:
            print(f"Error with {symbol}: {str(e)}")
            continue
