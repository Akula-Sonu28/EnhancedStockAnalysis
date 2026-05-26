#!/usr/bin/env python3
"""
Stock Analysis System - Main Entry Point
========================================

A comprehensive stock analysis tool for NSE stocks with advanced features
for high-risk high-reward investors.

Usage:
    python main.py [options]

Examples:
    # Quick aggressive analysis
    python main.py --risk-profile aggressive --focus-growth -n 10
    
    # Full analysis with portfolio optimization
    python main.py --risk-profile aggressive --portfolio-amount 500000
    
    # Interactive mode
    python main.py --interactive

Author: Enhanced Stock Analysis System
Version: 2.0.0
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

# Import the enhanced analyzer (keeping backward compatibility)
try:
    from analyze_top200_stocks_enhanced import main as enhanced_main
    from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
except ImportError:
    print("❌ Error: Enhanced analyzer not found. Please ensure all files are in place.")
    sys.exit(1)

def show_welcome():
    """Show welcome message and system info"""
    print("🚀 STOCK ANALYSIS SYSTEM v2.0.0")
    print("=" * 50)
    print("Advanced stock analysis for NSE with high-risk features")
    print("Organized project structure with modular components")
    print()

def show_quick_help():
    """Show quick help for common commands"""
    print("📋 QUICK COMMANDS:")
    print("-" * 30)
    print("• Quick test:     python main.py --risk-profile aggressive -n 10")
    print("• Full analysis:  python main.py --risk-profile aggressive --focus-growth")
    print("• Portfolio:      python main.py --portfolio-amount 500000 --risk-profile aggressive")
    print("• Single stock:   python main.py -s RELIANCE --risk-profile aggressive")
    print("• Interactive:    python main.py --interactive")
    print("• Tools:          python main.py --tools")
    print("• Kite + analyze: python3 scripts/run_analysis.py --dry-run --fast")
    print()

def show_tools_menu():
    """Show available tools"""
    print("🔧 AVAILABLE TOOLS:")
    print("-" * 30)
    print("1. Command Builder (Interactive)")
    print("2. Setup Verification")
    print("3. Investor Guide")
    print("4. Documentation")
    print()
    
    choice = input("Select tool (1-4) or press Enter to skip: ").strip()
    
    if choice == "1":
        print("🔧 Launching Command Builder...")
        os.system("python tools/command_builder.py")
    elif choice == "2":
        print("🔧 Running Setup Verification...")
        os.system("python tools/verify_setup.py")
    elif choice == "3":
        print("🔧 Opening Investor Guide...")
        os.system("python tools/investor_guide.py")
    elif choice == "4":
        print("📖 Documentation available in docs/ folder")
        print("• docs/COMMANDS.md - Complete command reference")
        print("• docs/HIGH_RISK_GUIDE.md - High-risk investor guide")
        print("• docs/EXAMPLES.md - Ready-to-use examples")

def interactive_mode():
    """Interactive mode for beginners"""
    print("🎯 INTERACTIVE MODE")
    print("=" * 30)
    print("This will help you build the perfect command for your needs.")
    print()
    
    # Import and run command builder
    try:
        os.system("python tools/command_builder.py")
    except Exception as e:
        print(f"❌ Error launching interactive mode: {e}")
        print("💡 Try running: python tools/command_builder.py")

def main():
    """Main entry point with enhanced features"""
    
    # Check for special flags first
    if "--interactive" in sys.argv:
        show_welcome()
        interactive_mode()
        return
    
    if "--tools" in sys.argv:
        show_welcome()
        show_tools_menu()
        return
    
    if "--help-quick" in sys.argv or len(sys.argv) == 1:
        show_welcome()
        show_quick_help()
        return
    
    # For all other cases, delegate to the enhanced analyzer
    try:
        show_welcome()
        print("🔄 Launching Enhanced Stock Analyzer...")
        print()
        enhanced_main()
    except KeyboardInterrupt:
        print("\n\n👋 Analysis cancelled by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("💡 Try running with --help for usage information")
        print("🔧 Or use --tools to access helper utilities")

if __name__ == "__main__":
    # Add custom help handling
    if len(sys.argv) == 1 or "--help" in sys.argv:
        show_welcome()
        show_quick_help()
        print("For detailed help: python analyze_top200_stocks_enhanced.py --help")
    else:
        main()
