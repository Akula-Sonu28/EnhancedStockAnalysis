#!/usr/bin/env python3
"""
Example: Batch Stock Analysis with Export
This example demonstrates how to analyze multiple stocks and export results
"""
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path to import from stock_analysis
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_analysis.main import batch_analyze_stocks, load_stock_list
from stock_analysis.exporters.json_export import export_to_json
from stock_analysis.exporters.data_exporter import export_data

def main():
    """Run batch analysis and export results"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Batch Stock Analysis Example')
    parser.add_argument('-n', '--num', type=int, default=10, help='Number of stocks to analyze')
    parser.add_argument('-b', '--batch', type=int, default=5, help='Batch size')
    args = parser.parse_args()
    
    # Load stock symbols
    all_symbols = load_stock_list()
    symbols = all_symbols[:args.num]  # Take only the requested number
    
    print(f"Running batch analysis for {len(symbols)} stocks...")
    print(f"Stocks to analyze: {', '.join(symbols)}")
    
    # Run the analysis
    results = batch_analyze_stocks(symbols, batch_size=args.batch)
    
    if results:
        # Sort by overall score if available
        if all('overall_score' in result for result in results):
            sorted_results = sorted(results, key=lambda x: x.get('overall_score', 0), reverse=True)
        else:
            sorted_results = results
        
        # Display top stocks
        print("\nTop Analyzed Stocks:")
        for i, result in enumerate(sorted_results[:5], 1):
            symbol = result['symbol']
            tech_score = result.get('technical_score', 'N/A')
            fund_score = result.get('fundamental_score', 'N/A')
            overall = result.get('overall_score', 'N/A')
            
            if isinstance(tech_score, (int, float)):
                tech_score = f"{tech_score:.2f}"
            if isinstance(fund_score, (int, float)):
                fund_score = f"{fund_score:.2f}"
            if isinstance(overall, (int, float)):
                overall = f"{overall:.2f}"
                
            print(f"{i}. {symbol}: Technical={tech_score}, Fundamental={fund_score}, Overall={overall}")
        
        # Export results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = export_to_json(results, f"batch_analysis_{timestamp}")
        excel_file = export_data(results, f"batch_analysis_{timestamp}")
        
        print(f"\nResults exported to:")
        print(f"- JSON: {json_file}")
        print(f"- Excel: {excel_file}")
    else:
        print("No results to display or export")

if __name__ == "__main__":
    main()
