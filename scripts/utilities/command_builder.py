#!/usr/bin/env python3
"""
Interactive Command Builder for High-Risk Stock Analysis
========================================================
This script helps you build the perfect command for your investment needs
"""

import os

def show_welcome():
    print("🚀 HIGH-RISK STOCK ANALYSIS - COMMAND BUILDER")
    print("=" * 60)
    print("This tool helps you build the perfect command for your needs!")
    print()

def get_risk_profile():
    print("1️⃣ RISK PROFILE SELECTION:")
    print("1. Conservative (2.5%-8% targets, 3.5% stop-loss)")
    print("2. Moderate (3.5%-12% targets, 5.5% stop-loss)") 
    print("3. Aggressive (6%-20% targets, 8% stop-loss) 🔥")
    
    while True:
        choice = input("\nSelect risk profile (1-3, default=3): ").strip()
        if choice == "" or choice == "3":
            return "aggressive"
        elif choice == "1":
            return "conservative"
        elif choice == "2":
            return "moderate"
        else:
            print("Invalid choice. Please select 1, 2, or 3.")

def get_analysis_focus():
    print("\n2️⃣ ANALYSIS FOCUS:")
    print("1. Growth Focus (revenue/earnings growth + momentum)")
    print("2. Momentum Focus (technical signals + price action)")
    print("3. Both Growth + Momentum (maximum aggressive) 🔥")
    print("4. Standard Analysis (balanced approach)")
    
    while True:
        choice = input("\nSelect focus (1-4, default=3): ").strip()
        if choice == "" or choice == "3":
            return True, True  # focus_growth, focus_momentum
        elif choice == "1":
            return True, False
        elif choice == "2":
            return False, True
        elif choice == "4":
            return False, False
        else:
            print("Invalid choice. Please select 1, 2, 3, or 4.")

def get_stock_count():
    print("\n3️⃣ NUMBER OF STOCKS:")
    print("1. Quick Test (5-10 stocks, 2-3 minutes)")
    print("2. Medium Analysis (25-50 stocks, 5-8 minutes)")
    print("3. Extended Analysis (100-200 stocks, 15-25 minutes)")
    print("4. Large Scale Analysis (300-500 stocks, 45-60 minutes)")
    print("5. All Available Stocks (process entire CSV)")
    print("6. Custom number")
    
    while True:
        choice = input("\nSelect stock count (1-6, default=2): ").strip()
        if choice == "" or choice == "2":
            return 25
        elif choice == "1":
            return 10
        elif choice == "3":
            return 200
        elif choice == "4":
            return 500
        elif choice == "5":
            return 0  # 0 means all available stocks
        elif choice == "6":
            try:
                custom = int(input("Enter custom number (1-5000, or 0 for all): "))
                if custom == 0:
                    print("Will analyze all stocks in your CSV file.")
                    return 0
                elif 1 <= custom <= 5000:
                    return custom
                else:
                    print("Number must be between 1 and 5000, or 0 for all stocks.")
            except ValueError:
                print("Please enter a valid number.")
        else:
            print("Invalid choice. Please select 1, 2, 3, 4, 5, or 6.")

def get_volatility_filter():
    print("\n4️⃣ VOLATILITY FILTER (for high-risk traders):")
    print("1. No filter (include all stocks)")
    print("2. Medium volatility (≥10%)")
    print("3. High volatility (≥15%) 🔥")
    print("4. Ultra-high volatility (≥20%) ⚡")
    print("5. Custom volatility")
    
    while True:
        choice = input("\nSelect volatility filter (1-5, default=1): ").strip()
        if choice == "" or choice == "1":
            return 0.0
        elif choice == "2":
            return 10.0
        elif choice == "3":
            return 15.0
        elif choice == "4":
            return 20.0
        elif choice == "5":
            try:
                custom = float(input("Enter minimum volatility % (0-50): "))
                if 0 <= custom <= 50:
                    return custom
                else:
                    print("Volatility must be between 0 and 50%.")
            except ValueError:
                print("Please enter a valid number.")
        else:
            print("Invalid choice. Please select 1, 2, 3, 4, or 5.")

def get_portfolio_amount():
    print("\n5️⃣ PORTFOLIO AMOUNT (for position sizing):")
    print("1. ₹50,000 (starter portfolio)")
    print("2. ₹1,00,000 (small portfolio)")
    print("3. ₹2,00,000 (medium portfolio)")
    print("4. ₹5,00,000 (large portfolio)")
    print("5. ₹10,00,000+ (premium portfolio)")
    print("6. Custom amount")
    print("7. Skip portfolio analysis")
    
    while True:
        choice = input("\nSelect portfolio amount (1-7, default=2): ").strip()
        if choice == "" or choice == "2":
            return 100000
        elif choice == "1":
            return 50000
        elif choice == "3":
            return 200000
        elif choice == "4":
            return 500000
        elif choice == "5":
            return 1000000
        elif choice == "6":
            try:
                custom = float(input("Enter portfolio amount (₹): "))
                if custom > 0:
                    return int(custom)
                else:
                    print("Amount must be positive.")
            except ValueError:
                print("Please enter a valid number.")
        elif choice == "7":
            return None
        else:
            print("Invalid choice. Please select 1-7.")

def get_additional_options():
    print("\n6️⃣ ADDITIONAL OPTIONS:")
    options = []
    
    undervalued = input("Focus only on undervalued stocks? (y/N): ").strip().lower()
    if undervalued in ['y', 'yes']:
        options.append('--undervalued-only')
    
    fast_mode = input("Skip detailed risk analysis for faster execution? (y/N): ").strip().lower()
    if fast_mode in ['y', 'yes']:
        options.append('--skip-risk')
    
    # Note: Cache is managed automatically by the enhanced analyzer
    # Fresh data is fetched when cache expires (4 hours)
    
    return options

def build_command(risk_profile, focus_growth, focus_momentum, stock_count, min_volatility, portfolio_amount, additional_options):
    """Build the complete command string"""
    
    cmd_parts = ["python", "analyze_top200_stocks_enhanced.py"]
    
    # Risk profile
    cmd_parts.extend(["--risk-profile", risk_profile])
    
    # Focus options
    if focus_growth:
        cmd_parts.append("--focus-growth")
    if focus_momentum:
        cmd_parts.append("--focus-momentum")
    
    # Stock count
    if stock_count != 200:  # Only add if not default
        cmd_parts.extend(["-n", str(stock_count)])
    
    # Volatility filter
    if min_volatility > 0:
        cmd_parts.extend(["--min-volatility", str(min_volatility)])
    
    # Portfolio amount
    if portfolio_amount:
        cmd_parts.extend(["--portfolio-amount", str(portfolio_amount)])
    
    # Additional options
    cmd_parts.extend(additional_options)
    
    return " ".join(cmd_parts)

def show_command_summary(command, risk_profile, focus_growth, focus_momentum, stock_count, min_volatility, portfolio_amount):
    """Show a summary of what the command will do"""
    
    print("\n🎯 COMMAND SUMMARY:")
    print("=" * 40)
    print(f"Risk Profile: {risk_profile.upper()}")
    
    focus_desc = []
    if focus_growth:
        focus_desc.append("Growth")
    if focus_momentum:
        focus_desc.append("Momentum")
    if not focus_growth and not focus_momentum:
        focus_desc.append("Standard")
    print(f"Focus: {' + '.join(focus_desc)}")
    
    print(f"Stocks to Analyze: {stock_count}")
    
    if min_volatility > 0:
        print(f"Minimum Volatility: {min_volatility}%")
    
    if portfolio_amount:
        print(f"Portfolio Amount: ₹{portfolio_amount:,}")
    
    # Estimate execution time
    if stock_count <= 10:
        time_estimate = "2-3 minutes"
    elif stock_count <= 50:
        time_estimate = "5-8 minutes"
    else:
        time_estimate = "15-25 minutes"
    
    print(f"Estimated Time: {time_estimate}")
    
    print(f"\n📋 YOUR COMMAND:")
    print("-" * 50)
    print(command)
    print("-" * 50)

def show_expected_output():
    """Show what output to expect"""
    print("\n📊 EXPECTED OUTPUT:")
    print("• TOP 10 Categories (Undervalued, Growth, Value, etc.)")
    print("• Detailed Excel report with trading plans")
    print("• Support/resistance levels for each stock")
    print("• Portfolio allocation recommendations")
    print("• Risk-reward analysis for positions")

def main():
    show_welcome()
    
    try:
        # Collect user preferences
        risk_profile = get_risk_profile()
        focus_growth, focus_momentum = get_analysis_focus()
        stock_count = get_stock_count()
        min_volatility = get_volatility_filter()
        portfolio_amount = get_portfolio_amount()
        additional_options = get_additional_options()
        
        # Build command
        command = build_command(risk_profile, focus_growth, focus_momentum, stock_count, min_volatility, portfolio_amount, additional_options)
        
        # Show summary
        show_command_summary(command, risk_profile, focus_growth, focus_momentum, stock_count, min_volatility, portfolio_amount)
        show_expected_output()
        
        print(f"\n🚀 READY TO RUN?")
        run_now = input("Execute this command now? (y/N): ").strip().lower()
        
        if run_now in ['y', 'yes']:
            print(f"\n▶️  Executing command...")
            print(f"Command: {command}")
            os.system(command)
        else:
            print(f"\n💾 Command saved! Copy the command above and run it when ready.")
            
            # Also save to file
            with open("my_analysis_command.txt", "w") as f:
                f.write(command)
            print(f"💾 Command also saved to: my_analysis_command.txt")
        
    except KeyboardInterrupt:
        print(f"\n\n👋 Command builder cancelled. Come back anytime!")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
