#!/usr/bin/env python3
"""
Test script for high-risk high-reward investor analysis
Demonstrates how to run the enhanced stock analyzer with aggressive settings
"""

import os
import sys
import subprocess
from datetime import datetime

def test_aggressive_investor_modes():
    """Test different high-risk investor configurations"""
    
    print("🚀 HIGH-RISK HIGH-REWARD INVESTOR ANALYSIS TEST")
    print("=" * 60)
    print(f"⏰ Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test configurations for aggressive investors
    test_configs = [
        {
            "name": "🔥 AGGRESSIVE GROWTH FOCUS",
            "description": "High-growth stocks with momentum focus",
            "args": ["--risk-profile", "aggressive", "--focus-growth", "--min-volatility", "15"]
        },
        {
            "name": "⚡ MOMENTUM TRADER",
            "description": "Technical momentum with aggressive risk",
            "args": ["--risk-profile", "aggressive", "--focus-momentum", "--min-volatility", "10"]
        },
        {
            "name": "🎯 BALANCED AGGRESSIVE",
            "description": "Balanced approach with aggressive risk tolerance",
            "args": ["--risk-profile", "aggressive", "--focus-growth", "--focus-momentum"]
        }
    ]
    
    base_script = "analyze_top200_stocks_enhanced.py"
    
    # Check if script exists
    if not os.path.exists(base_script):
        print(f"❌ Script not found: {base_script}")
        return False
    
    success_count = 0
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n{i}. {config['name']}")
        print(f"   {config['description']}")
        print(f"   Command args: {' '.join(config['args'])}")
        
        # Build command
        cmd = [
            "python", base_script,
            "-n", "10",  # Analyze only 10 stocks for quick test
            "-w", "2",   # Use 2 workers
            "-b", "5"    # Small batch size
        ] + config['args']
        
        print(f"   Running: {' '.join(cmd)}")
        
        try:
            # Run the analysis
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print(f"   ✅ SUCCESS: Analysis completed")
                # Look for key output indicators
                if "TOP 10 GROWTH STOCKS" in result.stdout:
                    print(f"   📊 Found growth analysis in output")
                if "MOMENTUM-BASED scoring" in result.stdout:
                    print(f"   🚀 Momentum scoring activated")
                if "aggressive" in result.stdout.lower():
                    print(f"   ⚡ Aggressive mode detected")
                
                success_count += 1
            else:
                print(f"   ❌ FAILED: Return code {result.returncode}")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}...")
                    
        except subprocess.TimeoutExpired:
            print(f"   ⏰ TIMEOUT: Analysis took too long")
        except Exception as e:
            print(f"   💥 EXCEPTION: {str(e)}")
    
    print(f"\n📊 TEST SUMMARY")
    print(f"   Total tests: {len(test_configs)}")
    print(f"   Successful: {success_count}")
    print(f"   Failed: {len(test_configs) - success_count}")
    
    if success_count == len(test_configs):
        print(f"\n🎉 ALL TESTS PASSED! High-risk analysis is ready!")
    else:
        print(f"\n⚠️  Some tests failed. Check error messages above.")
    
    return success_count == len(test_configs)

def show_usage_examples():
    """Show example commands for high-risk investors"""
    
    print("\n📖 USAGE EXAMPLES FOR HIGH-RISK INVESTORS")
    print("=" * 60)
    
    examples = [
        {
            "title": "🔥 Aggressive Growth Hunter",
            "description": "Find high-growth stocks with momentum",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth --min-volatility 15"
        },
        {
            "title": "⚡ Day Trader Setup", 
            "description": "High volatility stocks for quick profits",
            "command": "python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-momentum --min-volatility 20"
        },
        {
            "title": "🎯 Single Stock Deep Dive",
            "description": "Analyze one stock with aggressive parameters",
            "command": "python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive --focus-growth"
        },
        {
            "title": "💰 High-Risk Portfolio",
            "description": "₹5 lakh portfolio with aggressive allocation",
            "command": "python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth --focus-momentum"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['title']}")
        print(f"   Description: {example['description']}")
        print(f"   Command: {example['command']}")

if __name__ == "__main__":
    print("Select test mode:")
    print("1. Run automated tests")
    print("2. Show usage examples")
    print("3. Both")
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice in ['1', '3']:
        success = test_aggressive_investor_modes()
    
    if choice in ['2', '3']:
        show_usage_examples()
    
    print(f"\n🏁 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
