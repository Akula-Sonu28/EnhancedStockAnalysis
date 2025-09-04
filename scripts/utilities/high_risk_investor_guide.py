#!/usr/bin/env python3
"""
HIGH-RISK HIGH-REWARD INVESTOR GUIDE
====================================

This guide shows you how to use the enhanced stock analyzer for aggressive 
investment strategies with higher risk tolerance and growth focus.

🔥 HIGH-RISK INVESTOR FEATURES:
- Aggressive risk profile with wider trading ranges
- Momentum-based stock scoring
- Growth-focused analysis
- Higher volatility thresholds
- Advanced trading plans with larger profit targets

📊 NEW COMMAND LINE OPTIONS:
--risk-profile aggressive    : Use aggressive trading strategies
--focus-growth              : Focus on high-growth momentum stocks  
--focus-momentum             : Emphasize technical momentum signals
--min-volatility X           : Set minimum volatility threshold

🚀 EXAMPLE COMMANDS FOR HIGH-RISK INVESTORS:
"""

import os
import sys

def show_high_risk_examples():
    """Display command examples for high-risk investors"""
    
    examples = [
        {
            "scenario": "🔥 AGGRESSIVE GROWTH HUNTER",
            "description": "Find high-growth stocks with strong momentum for maximum returns",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 15",
            "benefits": [
                "Uses momentum-based scoring algorithm",
                "Targets stocks with 20%+ growth potential", 
                "8% stop-loss with 20% profit targets",
                "Filters for high-volatility opportunities"
            ]
        },
        {
            "scenario": "⚡ MOMENTUM TRADER SETUP",
            "description": "Technical analysis focused on short-term momentum plays",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20",
            "benefits": [
                "Emphasizes technical momentum signals",
                "Higher volatility = higher profit potential",
                "4% entry range for quick positioning",
                "Momentum strategy recommendations"
            ]
        },
        {
            "scenario": "🎯 BALANCED AGGRESSIVE APPROACH",
            "description": "Combined growth + momentum for diversified high-risk portfolio",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --focus-momentum",
            "benefits": [
                "Best of both growth and momentum analysis",
                "Diversified risk across different stock types",
                "Advanced scoring combines multiple factors",
                "Suitable for ₹1-5 lakh portfolios"
            ]
        },
        {
            "scenario": "💰 HIGH-VALUE PORTFOLIO (₹5+ LAKHS)",
            "description": "Large portfolio allocation with aggressive strategies",
            "command": "python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth --focus-momentum",
            "benefits": [
                "Professional portfolio allocation",
                "Risk-adjusted position sizing",
                "Detailed Excel reports with trading plans",
                "Support/resistance levels for each stock"
            ]
        },
        {
            "scenario": "🔍 SINGLE STOCK DEEP DIVE",
            "description": "Detailed analysis of specific stock with aggressive parameters",
            "command": "python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive --focus-growth",
            "benefits": [
                "Complete fundamental + technical analysis",
                "Aggressive trading plan with specific targets",
                "Support/resistance levels calculated", 
                "Risk-reward ratios for position sizing"
            ]
        }
    ]
    
    print(__doc__)
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['scenario']}")
        print(f"   {example['description']}")
        print(f"   \n   📋 COMMAND:")
        print(f"   {example['command']}")
        print(f"   \n   ✅ BENEFITS:")
        for benefit in example['benefits']:
            print(f"   • {benefit}")
        print("\n" + "─" * 80)

def show_risk_profile_comparison():
    """Show differences between risk profiles"""
    
    print("\n📊 RISK PROFILE COMPARISON")
    print("=" * 50)
    
    profiles = {
        "CONSERVATIVE": {
            "Entry Range": "1% (tight entry)",
            "Profit Targets": "2.5%, 5%, 8%",
            "Stop Loss": "3.5%",
            "Strategy": "Value-based, dividend focus",
            "Best For": "Retirement funds, steady income"
        },
        "MODERATE": {
            "Entry Range": "2% (balanced entry)",
            "Profit Targets": "3.5%, 8%, 12%", 
            "Stop Loss": "5.5%",
            "Strategy": "Balanced growth + value",
            "Best For": "Most retail investors"
        },
        "AGGRESSIVE": {
            "Entry Range": "4% (wide entry for momentum)",
            "Profit Targets": "6%, 12%, 20%",
            "Stop Loss": "8%",
            "Strategy": "Momentum + growth focused",
            "Best For": "High-risk high-reward investors"
        }
    }
    
    for profile, details in profiles.items():
        print(f"\n🎯 {profile}:")
        for key, value in details.items():
            print(f"   {key}: {value}")

def show_momentum_scoring_details():
    """Explain the momentum scoring algorithm for aggressive investors"""
    
    print("\n🚀 MOMENTUM SCORING ALGORITHM (--focus-growth)")
    print("=" * 55)
    print("For aggressive investors, the system uses advanced momentum scoring:")
    print()
    print("📈 SCORING COMPONENTS:")
    print("• Revenue Growth (20%): Year-over-year revenue increase")
    print("• Earnings Growth (20%): Profit margin improvements") 
    print("• Technical Momentum (25%): RSI, MACD, price trends")
    print("• Price Performance (15%): Recent price momentum")
    print("• ROE Analysis (10%): Return on equity efficiency")
    print("• Market Cap Bias (10%): Growth vs large-cap balance")
    print("• VOLATILITY BONUS: Extra points for high-vol stocks")
    print()
    print("⚡ RESULT: Stocks with both fundamental strength AND technical momentum")
    print("🎯 TARGET: Identify stocks with 15-25% annual return potential")

if __name__ == "__main__":
    print("🔥 HIGH-RISK HIGH-REWARD INVESTOR GUIDE")
    print("=" * 50)
    print()
    print("Choose what you want to see:")
    print("1. Command examples for different scenarios")
    print("2. Risk profile comparison") 
    print("3. Momentum scoring algorithm details")
    print("4. All of the above")
    
    try:
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice in ['1', '4']:
            show_high_risk_examples()
            
        if choice in ['2', '4']:
            show_risk_profile_comparison()
            
        if choice in ['3', '4']:
            show_momentum_scoring_details()
            
        print("\n" + "=" * 80)
        print("🎉 READY TO START? Use any of the commands above!")
        print("💡 TIP: Start with a small test: -n 10 for quick results")
        print("📊 RECOMMENDED: python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 20")
        
    except KeyboardInterrupt:
        print("\n\n👋 See you later! Happy investing!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
