#!/usr/bin/env python3
"""
Test Portfolio Consolidation System
"""

import sys
sys.path.append('.')

from portfolio.analyzer import PortfolioAnalyzer
from portfolio.consolidation import PortfolioConsolidation

def test_consolidation():
    print("🧪 Testing Portfolio Consolidation System")
    print("="*50)
    
    try:
        # Initialize analyzer
        print("1️⃣ Initializing Portfolio Analyzer...")
        analyzer = PortfolioAnalyzer(available_funds=114129.60)
        
        # Load data
        print("2️⃣ Loading portfolio data...")
        if not analyzer.load_portfolio_data("Holding/holdings*.csv", "reports/Enhanced_Stock_Report_*.xlsx"):
            print("❌ Failed to load data")
            return
        
        print(f"✅ Loaded {len(analyzer.holdings_df)} holdings")
        print(f"✅ Holdings columns: {list(analyzer.holdings_df.columns)}")
        
        # Test consolidation
        print("\n3️⃣ Testing Consolidation Engine...")
        consolidation = PortfolioConsolidation(analyzer)
        
        print("4️⃣ Running consolidation analysis...")
        result = consolidation.analyze_consolidation_opportunities()
        
        print("\n📊 CONSOLIDATION RESULTS:")
        print("="*30)
        
        if result.get('error'):
            print(f"❌ Error: {result['error']}")
            return
            
        print(f"Current Holdings: {result.get('current_holdings', 0)}")
        print(f"Target Range: {result.get('target_range', 'N/A')}")
        print(f"Action Needed: {result.get('action_needed', False)}")
        
        if result.get('action_needed'):
            print(f"Stocks to Remove: {result.get('stocks_to_remove', 0)}")
            
            removal_candidates = result.get('removal_candidates', [])
            print(f"\n🎯 TOP 5 REMOVAL CANDIDATES:")
            for i, candidate in enumerate(removal_candidates[:5], 1):
                print(f"   {i}. {candidate['symbol']} | Score: {candidate['removal_score']:.1f} | Value: ₹{candidate['current_value']:,.0f}")
                print(f"      └─ {candidate['removal_reasons']}")
            
            # Show capital rotation
            capital_rotation = result.get('capital_rotation', {})
            if capital_rotation:
                print(f"\n💰 CAPITAL ROTATION:")
                total_amount = capital_rotation.get('total_amount', 0)
                print(f"Total Proceeds: ₹{total_amount:,.0f}")
                
                allocation_plan = capital_rotation.get('allocation_plan', [])
                print(f"Top Allocation Targets:")
                for allocation in allocation_plan[:3]:
                    print(f"   • {allocation['symbol']}: +₹{allocation['allocation_amount']:,.0f} ({allocation['allocation_percentage']:.1f}%)")
                    
        else:
            print(f"✅ {result.get('message', 'Portfolio already optimized')}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_consolidation()