#!/usr/bin/env python3
"""
Enhanced Portfolio Analysis Demo
===============================

Demonstrates the new enhanced sell signals and capital rotation features.
"""

from portfolio.analyzer import PortfolioAnalyzer
from portfolio.insights import PortfolioInsights

def demo_enhanced_features():
    """Demo the enhanced sell signals and rotation strategies"""
    
    print("🚀 ENHANCED PORTFOLIO ANALYSIS DEMO")
    print("=" * 50)
    
    try:
        # Initialize analyzer
        analyzer = PortfolioAnalyzer()
        analyzer.load_portfolio_data()
        analyzer.load_enhanced_report()
        
        # Calculate performance
        performance = analyzer.calculate_portfolio_performance()
        print(f"📊 Portfolio Value: ₹{performance['total_value']:,.0f}")
        print(f"💰 P&L: ₹{performance['total_pnl']:,.0f} ({performance['total_return_pct']:.1f}%)")
        
        # Initialize insights
        insights = PortfolioInsights(analyzer)
        
        # Get enhanced sell recommendations
        print(f"\n🎯 ENHANCED SELL RECOMMENDATIONS:")
        print("-" * 40)
        
        enhanced_sells = insights.get_enhanced_sell_recommendations()
        
        # Immediate sells
        immediate = enhanced_sells.get('immediate_sells', [])
        if immediate:
            print(f"🚨 IMMEDIATE SELLS ({len(immediate)}):")
            for sell in immediate[:3]:  # Show top 3
                print(f"   • {sell['instrument']}: Sell at ₹{sell.get('target_price', 0):.2f}")
                print(f"     └─ Reason: {sell['rationale']}")
        
        # Profit booking
        profit_booking = enhanced_sells.get('profit_booking', [])
        if profit_booking:
            print(f"\n💰 PROFIT BOOKING ({len(profit_booking)}):")
            for book in profit_booking[:3]:  # Show top 3
                print(f"   • {book['instrument']}: Target ₹{book.get('target_price', 0):.2f}")
                print(f"     └─ Current: ₹{book.get('current_price', 0):.2f} | {book['rationale']}")
        
        # Rotation strategies
        rotations = enhanced_sells.get('rotation_strategies', [])
        total_proceeds = enhanced_sells.get('total_proceeds_available', 0)
        
        if total_proceeds > 0:
            print(f"\n💫 CAPITAL ROTATION STRATEGY:")
            print(f"   📊 Total Available: ₹{total_proceeds:,.0f}")
            
            for rotation in rotations[:2]:  # Show top 2
                source = rotation.get('source_stock', 'Unknown')
                strategies = rotation.get('rotation_strategy', [])
                
                print(f"   • From {source}:")
                for strategy in strategies[:2]:
                    if strategy.get('type') == 'SECTOR_DIVERSIFICATION':
                        sectors = ', '.join(strategy.get('target_sectors', []))
                        print(f"     └─ Diversify to {sectors}")
                    elif strategy.get('type') == 'UPGRADE_POSITIONS':
                        stocks = ', '.join(strategy.get('target_stocks', []))
                        print(f"     └─ Upgrade to {stocks}")
        
        print(f"\n✅ Enhanced analysis completed!")
        
    except Exception as e:
        print(f"❌ Error in demo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demo_enhanced_features()