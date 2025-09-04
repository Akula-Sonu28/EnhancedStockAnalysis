#!/usr/bin/env python3
"""
Main script to run stock analysis
"""
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from stock_analysis.main import setup_logging, batch_analyze_stocks, load_stock_list
from stock_analysis.exporters.json_export import export_to_json
from stock_analysis.exporters.data_exporter import export_data

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Stock Analysis')
    parser.add_argument('-s', '--symbol', type=str, help='Single stock symbol to analyze')
    parser.add_argument('-n', '--num', type=int, default=200, help='Number of stocks to analyze')
    parser.add_argument('-b', '--batch', type=int, default=5, help='Batch size')
    parser.add_argument('-w', '--workers', type=int, default=3, help='Maximum worker threads')
    args = parser.parse_args()
    
    # Setup logging
    log_file = setup_logging()
    
    # Get stock list
    if args.symbol:
        stock_list = [args.symbol]
    else:
        stock_list = load_stock_list()
        if args.num and args.num < len(stock_list):
            stock_list = stock_list[:args.num]
    
    print(f"Starting analysis of {len(stock_list)} stocks...")
    
    # Run analysis
    results = batch_analyze_stocks(stock_list, args.batch, args.workers)
    
    # Export results
    if results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_data(results, f"analysis_{timestamp}")
        json_file = export_to_json(results, f"analysis_{timestamp}")
        print(f"Analysis complete. Results saved to {json_file}")
    else:
        print("No results to export.")

if __name__ == "__main__":
    main()
