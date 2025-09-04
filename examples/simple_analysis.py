#!/usr/bin/env python3
"""
Example: Basic Stock Analysis
This example demonstrates how to analyze a single stock with the package
"""
import sys
import os

# Add parent directory to path to import from stock_analysis
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_analysis.main import analyze_stock

def main():
    """Run a simple analysis on a single stock"""
    # Stock symbol to analyze
    symbol = "RELIANCE"
    
    print(f"Running analysis for {symbol}...")
    result = analyze_stock(symbol)
    
    if result:
        print("\nAnalysis Results:")
        print(f"Symbol: {result['symbol']}")
        print(f"Analysis Time: {result.get('analysis_timestamp', 'N/A')}")
        
        # Display technical analysis if available
        if 'technical_score' in result:
            print(f"\nTechnical Score: {result['technical_score']:.2f}/10")
            
            # Display some indicators
            if 'rsi' in result:
                print(f"RSI: {result['rsi']:.2f}")
            if 'sma_50' in result and 'sma_200' in result:
                print(f"SMA 50: {result['sma_50']:.2f}")
                print(f"SMA 200: {result['sma_200']:.2f}")
                
            # Technical analysis details
            if 'technical_analysis' in result:
                print("\nTechnical Analysis Details:")
                for key, value in result['technical_analysis'].items():
                    print(f"- {key}: {value}")
        
        # Display fundamental analysis if available
        if 'fundamental_score' in result:
            print(f"\nFundamental Score: {result['fundamental_score']:.2f}/10")
            
            # Display some fundamental metrics
            for key in ['pe_ratio', 'pb_ratio', 'eps_growth', 'revenue_growth', 'dividend_yield']:
                if key in result:
                    print(f"{key.replace('_', ' ').title()}: {result[key]}")
        
        # Overall score if available
        if 'overall_score' in result:
            print(f"\nOverall Score: {result['overall_score']:.2f}/10")
            
            # Simple recommendation
            score = result['overall_score']
            if score >= 7.5:
                recommendation = "Strong Buy"
            elif score >= 6.0:
                recommendation = "Buy"
            elif score >= 4.5:
                recommendation = "Hold"
            elif score >= 3.0:
                recommendation = "Sell"
            else:
                recommendation = "Strong Sell"
            
            print(f"Recommendation: {recommendation}")
    else:
        print(f"Failed to analyze {symbol}")

if __name__ == "__main__":
    main()
