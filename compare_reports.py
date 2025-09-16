#!/usr/bin/env python3
"""
Stock Report Comparison Tool - Main Script
=========================================

Compare Enhanced Stock Reports to identify market trends, stock performance 
changes, and generate actionable insights.

Usage:
    python compare_reports.py [options]

Examples:
    # Compare latest two reports
    python compare_reports.py
    
    # Compare specific reports
    python compare_reports.py --old reports/Enhanced_Stock_Report_20250915.xlsx --new reports/Enhanced_Stock_Report_20250916.xlsx
    
    # Generate console output only
    python compare_reports.py --console-only
    
    # Auto-run after new analysis
    python compare_reports.py --auto

Author: Enhanced Stock Analysis System
Version: 1.0.0
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from report_comparison.analyzer import ReportComparator
from report_comparison.reporter import ComparisonReportGenerator

def main():
    """Main entry point for report comparison"""
    parser = argparse.ArgumentParser(
        description="Compare Enhanced Stock Reports and generate insights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compare_reports.py                           # Compare latest two reports
  python compare_reports.py --console-only           # Console output only
  python compare_reports.py --old report1.xlsx --new report2.xlsx  # Specific files
        """
    )
    
    parser.add_argument('--old', '--previous',
                       help='Path to older/previous Enhanced Stock Report')
    parser.add_argument('--new', '--current', 
                       help='Path to newer/current Enhanced Stock Report')
    parser.add_argument('--console-only', action='store_true',
                       help='Display insights in console only (no Excel report)')
    parser.add_argument('--excel-only', action='store_true',
                       help='Generate Excel report only (no console output)')
    parser.add_argument('--auto', action='store_true',
                       help='Auto-run mode (used after generating new reports)')
    
    args = parser.parse_args()
    
    try:
        print("🔄 STOCK REPORT COMPARISON ANALYSIS")
        print("=" * 50)
        
        # Initialize comparator
        comparator = ReportComparator()
        
        # Run comparison
        if args.old and args.new:
            if not os.path.exists(args.old):
                print(f"❌ Old report file not found: {args.old}")
                return 1
            if not os.path.exists(args.new):
                print(f"❌ New report file not found: {args.new}")
                return 1
            results = comparator.compare_reports(args.old, args.new)
        else:
            results = comparator.compare_reports()
        
        # Display console insights (unless excel-only mode)
        if not args.excel_only:
            comparator.display_console_insights(results)
        
        # Generate Excel report (unless console-only mode)
        if not args.console_only:
            generator = ComparisonReportGenerator()
            report_path = generator.generate_comparison_report(results)
            
            if not args.excel_only:
                print(f"\n📊 Detailed Excel report generated: {os.path.basename(report_path)}")
                print(f"   📂 Location: {os.path.dirname(report_path)}")
        
        print(f"\n✅ Report comparison completed successfully!")
        
        # Return insights for integration with other scripts
        return results
        
    except FileNotFoundError as e:
        print(f"❌ File Error: {e}")
        print("💡 Make sure you have at least 2 Enhanced Stock Reports generated")
        return 1
    except Exception as e:
        print(f"❌ Error during comparison: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    if isinstance(exit_code, int):
        sys.exit(exit_code)