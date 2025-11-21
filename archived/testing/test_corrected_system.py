#!/usr/bin/env python3
"""
CORRECTED SYSTEM VALIDATION TEST
Tests the integrated corrected scoring algorithm on real stocks from your portfolio
"""

import sys
sys.path.append('.')

from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer
import pandas as pd
from datetime import datetime

def test_corrected_system():
    """Test the corrected scoring system on real stocks"""
    print("🧪 TESTING CORRECTED SCORING SYSTEM")
    print("="*60)
    
    # Initialize the enhanced analyzer with corrected scoring
    analyzer = EnhancedTop200StockAnalyzer(max_workers=3)
    
    # Test stocks that showed different patterns in backtest
    test_stocks = [
        'MOTILALOFS',  # Top performer but got HOLD (should be upgraded)
        'ETERNAL',     # Top performer but got SELL (should be upgraded significantly)
        'BAJAJHLDNG',  # Good performer but high score (should be adjusted)
        'SBIN',        # Banking stock that was overscored (should be downgraded)
        'AUBANK',      # Banking winner (validation case)
        'NESTLEIND',   # Got SELL but performed reasonably (should be re-evaluated)
    ]
    
    results = []
    
    print("🔍 ANALYZING TEST STOCKS WITH CORRECTED ALGORITHM:")
    print()
    
    for symbol in test_stocks:
        try:
            print(f"📊 Analyzing {symbol}...")
            
            # Get the complete analysis with corrected scoring
            stock_data = analyzer.analyze_single_stock(symbol)
            
            if stock_data and not (hasattr(stock_data, 'empty') and stock_data.empty):
                # Convert to dict if it's a pandas Series
                if hasattr(stock_data, 'to_dict'):
                    stock_data = stock_data.to_dict()
                
                # Extract key data
                result = {
                    'symbol': symbol,
                    'original_score': stock_data.get('overall_score_with_value', 0),
                    'corrected_score': stock_data.get('corrected_overall_score', 0),
                    'score_adjustment': stock_data.get('score_adjustment', 0),
                    'original_recommendation': stock_data.get('original_recommendation', 'N/A'),
                    'corrected_recommendation': stock_data.get('corrected_recommendation', 'N/A'),
                    'recommendation_changed': stock_data.get('recommendation_changed', False),
                    'sector': stock_data.get('sector_classification', 'Unknown'),
                    'contrarian_technical': stock_data.get('contrarian_technical_score', 0),
                    'contrarian_momentum': stock_data.get('contrarian_momentum_score', 0),
                    'timing_factor': stock_data.get('timing_factor', 1.0)
                }
                
                results.append(result)
                
                # Display result
                change_icon = "📈" if result['score_adjustment'] > 0 else "📉" if result['score_adjustment'] < 0 else "➡️"
                rec_change_icon = "🔄" if result['recommendation_changed'] else "✅"
                
                print(f"   {symbol:12s}: {result['original_score']:5.1f} → {result['corrected_score']:5.1f} "
                      f"({result['score_adjustment']:+5.1f}) {change_icon}")
                print(f"   {'':14s}  {result['original_recommendation']} → {result['corrected_recommendation']} {rec_change_icon}")
                print(f"   {'':14s}  Sector: {result['sector']}, Timing: {result['timing_factor']:.2f}")
                print()
                
            else:
                print(f"   ❌ Failed to analyze {symbol}")
                
        except Exception as e:
            print(f"   ❌ Error analyzing {symbol}: {e}")
    
    if results:
        # Generate summary
        print("📊 CORRECTION SUMMARY:")
        print("="*60)
        
        # Score changes
        upgrades = [r for r in results if r['score_adjustment'] > 0]
        downgrades = [r for r in results if r['score_adjustment'] < 0]
        unchanged = [r for r in results if abs(r['score_adjustment']) < 1]
        
        print(f"📈 SCORE UPGRADES: {len(upgrades)}")
        for result in upgrades:
            print(f"   {result['symbol']:12s}: +{result['score_adjustment']:5.1f} points")
        
        print(f"\n📉 SCORE DOWNGRADES: {len(downgrades)}")
        for result in downgrades:
            print(f"   {result['symbol']:12s}: {result['score_adjustment']:5.1f} points")
        
        # Recommendation changes
        rec_changes = [r for r in results if r['recommendation_changed']]
        print(f"\n🔄 RECOMMENDATION CHANGES: {len(rec_changes)}")
        for result in rec_changes:
            print(f"   {result['symbol']:12s}: {result['original_recommendation']} → {result['corrected_recommendation']}")
        
        # Sector analysis
        print(f"\n🏭 SECTOR BREAKDOWN:")
        sectors = {}
        for result in results:
            sector = result['sector']
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(result)
        
        for sector, stocks in sectors.items():
            avg_adjustment = sum(s['score_adjustment'] for s in stocks) / len(stocks)
            print(f"   {sector:12s}: {len(stocks)} stocks, avg adjustment: {avg_adjustment:+5.1f}")
        
        # Validation against backtest insights
        print(f"\n✅ VALIDATION AGAINST BACKTEST INSIGHTS:")
        
        # Check if ETERNAL (top performer that got SELL) was upgraded
        eternal_result = next((r for r in results if r['symbol'] == 'ETERNAL'), None)
        if eternal_result:
            if eternal_result['score_adjustment'] > 10:
                print(f"   ✅ ETERNAL correctly upgraded by {eternal_result['score_adjustment']:+.1f} points")
            else:
                print(f"   ⚠️ ETERNAL upgrade insufficient: {eternal_result['score_adjustment']:+.1f} points")
        
        # Check if SBIN (overscored banking stock) was downgraded
        sbin_result = next((r for r in results if r['symbol'] == 'SBIN'), None)
        if sbin_result:
            if sbin_result['score_adjustment'] < -10:
                print(f"   ✅ SBIN correctly downgraded by {sbin_result['score_adjustment']:+.1f} points")
            else:
                print(f"   ⚠️ SBIN downgrade insufficient: {sbin_result['score_adjustment']:+.1f} points")
        
        # Save results
        results_df = pd.DataFrame(results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"corrected_system_test_{timestamp}.csv"
        results_df.to_csv(filename, index=False)
        print(f"\n💾 Results saved to: {filename}")
        
        print(f"\n🎯 CORRECTED SYSTEM VALIDATION COMPLETE!")
        print(f"   - {len(results)} stocks analyzed")
        print(f"   - {len(upgrades)} score upgrades")
        print(f"   - {len(downgrades)} score downgrades")
        print(f"   - {len(rec_changes)} recommendation changes")
        
        return results_df
    
    else:
        print("❌ No results to analyze")
        return None

if __name__ == "__main__":
    test_corrected_system()