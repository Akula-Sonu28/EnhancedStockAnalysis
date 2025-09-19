"""
Portfolio Analysis Main Script

This script provides a complete portfolio analysis system that:
1. Loads your holdings data and Enhanced Stock Report
2. Analyzes performance, sectors, and risks
3. Provides exit, buy, and rebalancing recommendations
4. Generates comprehensive actionable reports

Usage:
    python portfolio_analysis.py [--funds AMOUNT] [--holdings PATH] [--report PATH]

Example:
    python portfolio_analysis.py --funds 114129.60
"""

import argparse
import sys
import os
import warnings
import pandas as pd
from datetime import datetime

# Suppress pandas RuntimeWarnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning, module='pandas')

# Add current directory to path for imports
sys.path.append('.')

from portfolio.analyzer import PortfolioAnalyzer
from portfolio.insights import PortfolioInsights
from portfolio.reporter import PortfolioReporter
from portfolio.utils import PortfolioUtils
from portfolio.consolidation import PortfolioConsolidation
from portfolio.executor import PortfolioExecutor
from gtt.generator import GTTOrderGenerator
from gtt.config import GTTConfig


def main():
    """Main function to run portfolio analysis"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Comprehensive Portfolio Analysis')
    parser.add_argument('--funds', type=float, default=114129.60,
                       help='Available funds for new investments (default: 114129.60)')
    parser.add_argument('--holdings', type=str, default=None,
                       help='Path to holdings CSV file (auto-detected if not provided)')
    parser.add_argument('--report', type=str, default=None,
                       help='Path to Enhanced Stock Report Excel file (auto-detected if not provided)')
    parser.add_argument('--output', type=str, default='console',
                       choices=['console', 'file', 'both'],
                       help='Output format: console, file, or both (default: console)')
    parser.add_argument('--excel', action='store_true',
                       help='Generate Excel report with comprehensive trading sheet')
    parser.add_argument('--no-trading-sheet', action='store_true',
                       help='Disable trading sheet generation (faster execution)')
    parser.add_argument('--execute-buys', action='store_true',
                       help='Execute top 5 buy recommendations by adding them to portfolio')
    parser.add_argument('--execute-sells', action='store_true',
                       help='Execute consolidation sell recommendations')
    parser.add_argument('--execute-all-buys', action='store_true',
                       help='Execute all buy recommendations')
    parser.add_argument('--gtt', action='store_true',
                       help='Generate GTT (Good Till Triggered) orders for all holdings')
    parser.add_argument('--fast', action='store_true',
                       help='Fast execution mode - skip trading sheet and detailed calculations')
    parser.add_argument('--target-min', type=int, default=25,
                       help='Minimum target number of stocks for portfolio consolidation (default: 25)')
    parser.add_argument('--target-max', type=int, default=30,
                       help='Maximum target number of stocks for portfolio consolidation (default: 30)')
    
    args = parser.parse_args()
    
    # Fast mode auto-enables no-trading-sheet
    if args.fast:
        args.no_trading_sheet = True
    
    print("="*60)
    print("🏦 PORTFOLIO ANALYSIS SYSTEM")
    print("="*60)
    print(f"💰 Available Funds: ₹{args.funds:,.2f}")
    print(f"📅 Analysis Date: {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    print("="*60)
    
    try:
        # Step 1: Initialize Portfolio Analyzer
        print("📊 Initializing Portfolio Analyzer...")
        analyzer = PortfolioAnalyzer(available_funds=args.funds)
        
        # Initialize consolidation engine with target range parameters
        analyzer.consolidation_engine = PortfolioConsolidation(analyzer, 
                                                              target_min_stocks=args.target_min,
                                                              target_max_stocks=args.target_max)
        
        # Step 2: Load Portfolio Data
        print("📁 Loading portfolio data...")
        holdings_pattern = args.holdings if args.holdings else "Holding/holdings*.csv"
        report_pattern = args.report if args.report else "reports/Enhanced_Stock_Report_*.xlsx"
        
        if not analyzer.load_portfolio_data(holdings_pattern, report_pattern):
            print("❌ Failed to load portfolio data. Please check file paths.")
            return
        
        print(f"✅ Loaded {len(analyzer.holdings_df)} holdings")
        print(f"✅ Loaded Enhanced Stock Report with {len(analyzer.enhanced_report_df)} sheets")
        
        # Step 3: Calculate Portfolio Metrics
        print("📈 Calculating portfolio performance...")
        performance = analyzer.calculate_portfolio_performance()
        
        if not performance:
            print("❌ Failed to calculate portfolio performance.")
            return
        
        print(f"✅ Portfolio Value: ₹{performance.get('current_value', 0):,.0f}")
        print(f"✅ Total P&L: ₹{performance.get('total_pnl', 0):,.0f} ({performance.get('total_return_pct', 0):+.1f}%)")
        
        # Step 4: Analyze Sectors
        print("🏭 Analyzing sector allocation...")
        sector_analysis = analyzer.analyze_sector_allocation()
        
        if sector_analysis:
            print(f"✅ Analyzed {len(sector_analysis.get('sector_allocation', []))} sectors")
        
        # Step 5: Generate Insights
        print("💡 Generating portfolio insights...")
        insights = PortfolioInsights(analyzer)
        
        # Get exit strategies
        exit_analysis = insights.analyze_exit_strategies()
        immediate_exits = len(exit_analysis.get('immediate_exits', []))
        consider_exits = len(exit_analysis.get('consider_exits', []))
        
        print(f"✅ Found {immediate_exits} immediate exit recommendations")
        print(f"✅ Found {consider_exits} stocks to monitor for exit")
        
        # Get buy recommendations
        buy_analysis = insights.analyze_buy_recommendations()
        buy_recommendations = len(buy_analysis.get('top_buy_recommendations', []))
        
        print(f"✅ Generated {buy_recommendations} buy recommendations")
        
        # Get rebalancing strategies
        rebalancing = insights.analyze_rebalancing_strategies()
        concentration_risks = len(rebalancing.get('concentration_risks', []))
        
        print(f"✅ Identified {concentration_risks} concentration risks")
        
        # Calculate health score
        health_score = insights.calculate_portfolio_health_score()
        overall_score = health_score.get('overall_score', 0)
        
        print(f"✅ Portfolio Health Score: {overall_score:.0f}/100")
        
        # Enhanced Sell Analysis with Price Targets
        print("🎯 Generating enhanced sell recommendations with price targets...")
        enhanced_sells = insights.get_enhanced_sell_recommendations()
        
        immediate_sells = len(enhanced_sells.get('immediate_sells', []))
        profit_booking = len(enhanced_sells.get('profit_booking', []))
        total_proceeds = enhanced_sells.get('total_proceeds_available', 0)
        
        print(f"✅ Found {immediate_sells} immediate sell signals")
        print(f"✅ Found {profit_booking} profit booking opportunities")
        if total_proceeds > 0:
            print(f"💰 Potential proceeds from sales: ₹{total_proceeds:,.0f}")
        
        # Portfolio Consolidation Analysis
        print(f"📊 Analyzing portfolio consolidation (target: {args.target_min}-{args.target_max} stocks)...")
        consolidation_analysis = analyzer.consolidation_engine.analyze_consolidation_opportunities()
        
        if consolidation_analysis.get('action_needed', False):
            removal_count = len(consolidation_analysis.get('removal_candidates', []))
            print(f"✅ Identified {removal_count} stocks for removal to optimize portfolio")
            total_proceeds = consolidation_analysis.get('consolidation_impact', {}).get('total_proceeds', 0)
            if total_proceeds > 0:
                print(f"💰 Expected proceeds from consolidation: ₹{total_proceeds:,.0f}")
        else:
            print(f"✅ Portfolio already optimized with {consolidation_analysis.get('current_holdings', 0)} stocks")
        
        # Execute Recommendations if requested
        if args.execute_buys or args.execute_all_buys or args.execute_sells:
            print("⚡ Executing portfolio recommendations...")
            executor = PortfolioExecutor(analyzer, insights)
            
            if args.execute_buys or args.execute_all_buys:
                print("🛒 Executing buy recommendations...")
                buy_result = executor.execute_buy_recommendations(execute_all=args.execute_all_buys)
                
                if buy_result['success']:
                    print(f"✅ {buy_result['message']}")
                    print(f"💰 Total investment: ₹{buy_result['total_investment']:,.0f}")
                    print("📈 Executed buys:")
                    for buy in buy_result['executed_buys']:
                        print(f"   • {buy['symbol']}: {buy['quantity']} shares @ ₹{buy['price']:.2f} = ₹{buy['investment']:,.0f}")
                else:
                    print(f"❌ Buy execution failed: {buy_result['message']}")
            
            if args.execute_sells:
                print("💸 Executing sell recommendations...")
                sell_result = executor.execute_sell_recommendations()
                
                if sell_result['success']:
                    print(f"✅ {sell_result['message']}")
                    print(f"💰 Total proceeds: ₹{sell_result['total_proceeds']:,.0f}")
                    print("📉 Executed sells:")
                    for sell in sell_result['executed_sells']:
                        print(f"   • {sell['symbol']}: {sell['quantity']} shares = ₹{sell['proceeds']:,.0f}")
                else:
                    print(f"❌ Sell execution failed: {sell_result['message']}")
            
            print("🔄 Note: Portfolio has been updated. Re-run analysis to see updated metrics.")
        
        # Step 6: Generate Reports
        print("📋 Generating comprehensive report...")
        reporter = PortfolioReporter(analyzer, insights)
        reporter.consolidation_data = consolidation_analysis
        
        # Generate complete report
        complete_report = reporter.generate_complete_report()
        
        # Output based on user preference
        if args.output in ['console', 'both']:
            print("\n" + complete_report)
        
        if args.output in ['file', 'both']:
            # Save text report
            report_path = reporter.save_report_to_file(complete_report)
            if report_path:
                print(f"📄 Text report saved to: {report_path}")
        
        if args.excel:
            # Generate Excel report with trading sheet
            include_trading = not args.no_trading_sheet
            if include_trading:
                print("📊 Generating comprehensive Excel report with trading sheet...")
                print("   ├─ Calculating Support/Resistance levels (S1, S2, R1, R2)...")
                print("   ├─ Computing Technical Indicators (RSI, Moving Averages)...")
                print("   └─ Generating Entry/Exit signals...")
            
            excel_path = reporter.generate_excel_report(include_trading_sheet=include_trading)
            if excel_path:
                if include_trading:
                    print(f"📊 Comprehensive Excel report with trading sheet saved to: {excel_path}")
                else:
                    print(f"📊 Excel report saved to: {excel_path}")
        
        # Always generate basic trading sheet if not disabled and GTT not requested (for faster execution)
        elif not args.no_trading_sheet and not args.gtt:
            print("📊 Generating basic trading sheet...")
            excel_path = reporter.generate_excel_report(include_trading_sheet=True)
            if excel_path:
                print(f"📊 Portfolio analysis with trading sheet saved to: {excel_path}")
        elif args.gtt:
            print("📊 Skipping trading sheet generation for faster GTT processing...")
            # Generate basic Excel report for GTT integration
            excel_path = reporter.generate_excel_report(include_trading_sheet=False)
        else:
            # Default case - initialize excel_path to None
            excel_path = None
        
        # Step 6.5: Generate GTT Orders if requested
        if args.gtt:
            try:
                print("\n🎯 GENERATING GTT ORDERS")
                print("="*50)
                
                # Initialize GTT generator
                gtt_config = GTTConfig()
                
                # Get the main enhanced data from Complete Data sheet
                enhanced_data = analyzer.enhanced_report_df.get('Complete Data')
                if enhanced_data is None:
                    # Try alternative sheet names
                    for sheet_name in analyzer.enhanced_report_df.keys():
                        if 'complete' in sheet_name.lower() or 'data' in sheet_name.lower():
                            enhanced_data = analyzer.enhanced_report_df[sheet_name]
                            break
                    
                    if enhanced_data is None:
                        # Use the first available sheet
                        enhanced_data = next(iter(analyzer.enhanced_report_df.values()))
                
                # Get all trading recommendations for GTT
                buy_analysis = insights.analyze_buy_recommendations()
                buy_recommendations = buy_analysis.get('top_buy_recommendations', [])
                
                # Get consolidation sells
                consolidation_sells = []
                if hasattr(reporter, 'consolidation_data') and reporter.consolidation_data:
                    consolidation_sells = reporter.consolidation_data.get('sell_recommendations', [])
                
                # Get capital rotation plan
                capital_rotation = []
                if hasattr(reporter, 'consolidation_data') and reporter.consolidation_data:
                    rotation_data = reporter.consolidation_data.get('capital_rotation', {})
                    allocation_plan = rotation_data.get('allocation_plan', [])
                    
                    # Convert allocation plan to GTT-friendly format
                    for allocation in allocation_plan:
                        capital_rotation.append({
                            'action': 'strengthen_position',
                            'symbol': allocation.get('symbol'),
                            'amount': allocation.get('allocation_amount', 0),
                            'percentage': allocation.get('allocation_percentage', 0),
                            'rationale': allocation.get('rationale', 'Capital rotation strengthening')
                        })
                
                # Get profit booking recommendations
                profit_booking = []
                enhanced_sells = insights.get_enhanced_sell_recommendations()
                profit_booking = enhanced_sells.get('profit_booking', [])
                
                gtt_generator = GTTOrderGenerator(
                    holdings_data=analyzer.holdings_df,
                    enhanced_report_data=enhanced_data,
                    config=gtt_config,
                    buy_recommendations=buy_recommendations,
                    consolidation_sells=consolidation_sells,
                    capital_rotation=capital_rotation,
                    profit_booking=profit_booking
                )
                
                # Generate GTT orders
                gtt_orders = gtt_generator.generate_gtt_orders()
                
                if not gtt_orders.empty:
                    # Show preview
                    gtt_generator.print_orders_preview()
                    
                    # Always add GTT to main portfolio Excel report
                    if excel_path:
                        try:
                            # Add GTT sheet to existing portfolio Excel
                            with pd.ExcelWriter(excel_path, mode='a', engine='openpyxl') as writer:
                                gtt_orders[['type', 'status', 'tradingsymbol', 'exchange', 
                                           'trigger_values', 'transaction_type', 'quantity', 'last_price']].to_excel(
                                    writer, sheet_name='GTT_Orders', index=False)
                            print(f"📊 GTT Orders added to portfolio report: {excel_path}")
                        except Exception as e:
                            print(f"⚠️ Could not add GTT sheet to main report: {e}")
                            # Fallback: Export to separate file
                            gtt_excel_path = gtt_generator.export_to_excel()
                    else:
                        # No main Excel file, create dedicated GTT file
                        print("📊 No main Excel file found, creating dedicated GTT report...")
                        excel_path = reporter.generate_excel_report(include_trading_sheet=False)
                        if excel_path:
                            # Add GTT sheet to new Excel file
                            with pd.ExcelWriter(excel_path, mode='a', engine='openpyxl') as writer:
                                gtt_orders[['type', 'status', 'tradingsymbol', 'exchange', 
                                           'trigger_values', 'transaction_type', 'quantity', 'last_price']].to_excel(
                                    writer, sheet_name='GTT_Orders', index=False)
                            print(f"📊 Portfolio report with GTT orders saved to: {excel_path}")
                    
                    # Summary
                    summary = gtt_generator.get_orders_summary()
                    print(f"\n✅ GTT Orders Generated Successfully!")
                    print(f"   ├─ Total Orders: {summary['total_orders']}")
                    print(f"   ├─ Buy Orders: {summary['buy_orders']}")
                    print(f"   ├─ Sell Orders: {summary['sell_orders']}")
                    print(f"   └─ Unique Stocks: {summary['unique_stocks']}")
                else:
                    print("⚠️ No GTT orders could be generated")
                    
            except Exception as e:
                print(f"❌ Error generating GTT orders: {e}")
                import traceback
                print(f"📋 GTT Error details: {traceback.format_exc()}")
        
        # Step 7: Summary of Actions
        print("\n" + "="*60)
        print("📋 ANALYSIS COMPLETE - SUMMARY OF FINDINGS")
        print("="*60)
        
        print(f"🎯 Portfolio Health Score: {overall_score:.0f}/100")
        print(f"💰 Total Portfolio Value: ₹{performance.get('current_value', 0):,.0f}")
        print(f"📈 Total Return: {performance.get('total_return_pct', 0):+.1f}%")
        print(f"💵 Available for Investment: ₹{args.funds:,.0f}")
        
        print(f"\n🚨 Action Items:")
        print(f"   • {immediate_exits} stocks need immediate attention")
        print(f"   • {buy_recommendations} new investment opportunities identified")
        print(f"   • {concentration_risks} concentration risks to address")
        
        health_recommendations = health_score.get('recommendations', [])
        if health_recommendations:
            print(f"\n💡 Key Recommendations:")
            for i, rec in enumerate(health_recommendations[:3], 1):
                print(f"   {i}. {rec}")
        
        if not args.no_trading_sheet:
            print(f"\n📊 Trading Sheet Features Generated:")
            print(f"   ├─ Support/Resistance levels (S1, S2, R1, R2) for all holdings")
            print(f"   ├─ Entry/Exit signals based on technical analysis")
            print(f"   ├─ Stop-loss and target price recommendations")
            print(f"   ├─ RSI and trend analysis for each stock")
            print(f"   └─ Cash deployment strategy for available funds")
        
        print(f"\n⏰ Next recommended review: {(datetime.now().strftime('%B %d, %Y'))}")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        import traceback
        print(f"📋 Error details: {traceback.format_exc()}")
        return


def quick_analysis():
    """Quick analysis function for testing"""
    print("🚀 Running Quick Portfolio Analysis...")
    
    try:
        # Initialize with default settings
        analyzer = PortfolioAnalyzer(available_funds=114129.60)
        
        # Load data
        if analyzer.load_portfolio_data():
            print("✅ Data loaded successfully")
            
            # Get basic summary
            summary = analyzer.get_portfolio_summary()
            
            print(f"\n📊 QUICK SUMMARY:")
            print(f"├─ Total Investment: ₹{summary.get('total_invested', 0):,.0f}")
            print(f"├─ Current Value: ₹{summary.get('current_value', 0):,.0f}")
            print(f"├─ P&L: ₹{summary.get('total_pnl', 0):,.0f} ({summary.get('total_return_pct', 0):+.1f}%)")
            print(f"└─ Holdings: {summary.get('number_of_holdings', 0)} stocks")
            
        else:
            print("❌ Failed to load data")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    # Check if running with arguments or run quick analysis
    if len(sys.argv) > 1:
        main()
    else:
        print("🔍 No arguments provided. Running quick analysis...")
        print("💡 For full analysis, use: python portfolio_analysis.py --funds 114129.60")
        print()
        quick_analysis()