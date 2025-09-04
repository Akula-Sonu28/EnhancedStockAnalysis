#!/usr/bin/env python3
"""
Portfolio Analysis Script
Analyzes your stock portfolio and generates trading recommendations and GTTs
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add both src directory and project root to Python path
sys.path.append('src')
sys.path.append('.')

# Import the portfolio analyzer
from src.portfolio_analyzer import PortfolioAnalyzer

def main():
    """Main function to run portfolio analysis"""
    
    parser = argparse.ArgumentParser(description='Analyze your stock portfolio and generate recommendations')
    parser.add_argument('-p', '--portfolio', type=str, default="holdings.csv", 
                      help='Path to portfolio CSV file (default: holdings.csv)')
    parser.add_argument('-o', '--output', type=str, default=None,
                      help='Output directory for reports (default: reports/)')
    parser.add_argument('-g', '--gtt', action='store_true',
                      help='Generate GTT (Good Till Triggered) recommendations')
    parser.add_argument('--entries', action='store_true',
                      help='Generate entry & exit point recommendations')
    parser.add_argument('-t', '--template', action='store_true',
                      help='Create a portfolio template file')
    parser.add_argument('-u', '--update-prices', action='store_true',
                      help='Update current market prices')
    parser.add_argument('--rebalance', action='store_true',
                      help='Compute a rebalance plan based on scores')
    parser.add_argument('--capital', type=float, default=0.0,
                      help='Additional capital (₹) to deploy during rebalance')
    parser.add_argument('--max-positions', type=int, default=None,
                      help='Maximum number of positions to keep after rebalance')
    parser.add_argument('--min-weight', type=float, default=0.0,
                      help='Minimum target weight per kept position (0-1)')
    parser.add_argument('--max-weight', type=float, default=0.25,
                      help='Maximum target weight per position (0-1)')
    parser.add_argument('--exit-threshold', type=float, default=0.0,
                      help='Exit positions with target weight below this (0-1)')
    parser.add_argument('--lot', type=int, default=1,
                      help='Round trade quantities to this lot size (default 1)')
    parser.add_argument('--use-top200', action='store_true',
                      help='Use latest Stock_Report_*.xlsx to derive actions for holdings and new opportunities')
    parser.add_argument('--top200-file', type=str, default=None,
                      help='Explicit path to a Stock_Report_*.xlsx file')
    parser.add_argument('--add-threshold', type=float, default=70.0,
                      help='Minimum score to consider a new BUY opportunity (default 70)')
    parser.add_argument('--hold-threshold', type=float, default=55.0,
                      help='Minimum score to maintain HOLD instead of TRIM (default 55)')
    parser.add_argument('--max-new', type=int, default=5,
                      help='Maximum number of new opportunities to list (default 5)')
    
    args = parser.parse_args()
    
    # Create a portfolio template if requested
    if args.template:
        analyzer = PortfolioAnalyzer()
        template_path = args.portfolio if args.portfolio != "holdings.csv" else "portfolio_template.csv"
        analyzer.create_portfolio_template(template_path)
        return
    
    # Initialize the portfolio analyzer
    analyzer = PortfolioAnalyzer(args.portfolio)
    
    if analyzer.portfolio_data is None:
        print("Failed to load portfolio. Check if the file exists and is in the correct format.")
        return
    
    print(f"Successfully loaded portfolio with {len(analyzer.portfolio_data)} positions")
    
    # Update current market prices if requested
    if args.update_prices:
        print("Updating current market prices...")
        analyzer.update_current_prices()
        
    # Run full portfolio analysis
    print("Running comprehensive portfolio analysis...")
    analyzer.analyze_portfolio()
    
    # Generate GTT recommendations if requested
    if args.gtt:
        print("Generating GTT recommendations...")
        analyzer.generate_gtt_recommendations()

    # Generate entry/exit points if requested
    if args.entries:
        print("Generating entry & exit points...")
        analyzer.generate_entry_exit_points()

    # Compute rebalance plan if requested
    if args.rebalance:
        print("Computing rebalance plan...")
        plan = analyzer.compute_rebalance_plan(additional_capital=args.capital,
                                               max_positions=args.max_positions,
                                               min_weight=args.min_weight,
                                               max_weight=args.max_weight,
                                               score_field='overall_score',
                                               exit_threshold=args.exit_threshold,
                                               round_lots=args.lot)
        if plan:
            print("Rebalance plan generated.")

    # Derive recommendations from top200 report if requested
    if args.use_top200:
        print("Loading top200 analysis report for actionable recommendations...")
        report_df = analyzer.load_top200_report(args.top200_file)
        if report_df is not None:
            analyzer.generate_recommendations_from_report(report_df,
                                                          max_new=args.max_new,
                                                          min_add_score=args.add_threshold,
                                                          min_hold_score=args.hold_threshold)
            print("Portfolio actions & new opportunities generated from report.")
        else:
            print("Failed to load top200 report.")
        
    # Generate reports
    output_dir = args.output if args.output else "reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save analysis results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save portfolio analysis report
    excel_path = f"{output_dir}/portfolio_analysis_{timestamp}.xlsx"
    analyzer.save_analysis_report(excel_path)
    print(f"Portfolio analysis report saved to: {excel_path}")
    
    # Save GTT recommendations if generated
    if args.gtt:
        json_path = f"{output_dir}/portfolio_gtt_{timestamp}.json"
        csv_path = f"{output_dir}/portfolio_gtt_{timestamp}.csv"
        
        analyzer.save_gtt_recommendations(json_path)
        print(f"GTT recommendations saved to: {json_path}")
        
        analyzer.export_gtt_csv(csv_path)
        print(f"GTT recommendations exported to CSV: {csv_path}")

    # Save entry/exit points if generated
    if args.entries and hasattr(analyzer, 'entry_exit_points'):
        ee_path = f"{output_dir}/entry_exit_points_{timestamp}.csv"
        analyzer.export_entry_exit_points(ee_path)
        print(f"Entry/Exit points exported to: {ee_path}")

    # Save rebalance plan if generated
    if args.rebalance and hasattr(analyzer, 'rebalance_plan'):
        rb_path = f"{output_dir}/rebalance_plan_{timestamp}.csv"
        analyzer.export_rebalance_plan(rb_path)
        print(f"Rebalance plan exported to: {rb_path}")

    # Save portfolio actions & opportunities from report if generated
    if args.use_top200 and hasattr(analyzer, 'portfolio_actions'):
        act_path = f"{output_dir}/portfolio_actions_{timestamp}.csv"
        opp_path = f"{output_dir}/new_opportunities_{timestamp}.csv"
        analyzer.export_recommendations(act_path, opp_path)
        print(f"Portfolio actions exported to: {act_path}")
        print(f"New opportunities exported to: {opp_path}")
        
    print(f"Analysis complete. All reports saved to {output_dir}/ directory.")

if __name__ == "__main__":
    main()
