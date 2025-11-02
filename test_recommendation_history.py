"""
Test Recommendation History System

Simple test to verify the recommendation history tracking works correctly.
"""

from recommendation_history import RecommendationHistory
import pandas as pd
from datetime import datetime, timedelta

def test_recommendation_history():
    """Test the recommendation history system"""
    print("🧪 Testing Recommendation History System")
    print("=" * 80)
    
    # Create a test instance
    history = RecommendationHistory(history_file='data/test_recommendation_history.csv')
    
    # Test 1: Record initial BUY recommendation
    print("\n📝 Test 1: Recording initial BUY recommendation for NMDC")
    history.record_recommendation(
        symbol='NMDC',
        action='BUY',
        score=65,
        price=150,
        fundamentals={'pe_ratio': 10.5, 'roe': 18, 'debt_to_equity': 0.3},
        reason='Strong fundamentals',
        rank=5,
        sector='Metals'
    )
    print("   ✅ Recorded BUY recommendation")
    
    # Test 2: Try to SELL immediately (should be blocked by cooldown)
    print("\n📝 Test 2: Attempting to SELL NMDC immediately (should be blocked)")
    validation = history.validate_recommendation(
        symbol='NMDC',
        proposed_action='SELL',
        current_score=60,
        current_price=148,
        fundamentals={'pe_ratio': 10.5, 'roe': 18, 'debt_to_equity': 0.3},
        reason='Price dropped 2%',
        rank=10,
        sector='Metals'
    )
    print(f"   Original action: SELL")
    print(f"   Final action: {validation['final_action']}")
    print(f"   Warnings: {len(validation['warnings'])}")
    for warning in validation['warnings']:
        print(f"      - {warning}")
    
    # Test 3: Simulate 8 days later, try SELL again (should be allowed)
    print("\n📝 Test 3: Attempting to SELL NMDC after 8 days (should be allowed)")
    # Manually adjust the date in history for testing
    history.history_df.loc[history.history_df['symbol'] == 'NMDC', 'date'] = datetime.now() - timedelta(days=8)
    
    validation = history.validate_recommendation(
        symbol='NMDC',
        proposed_action='SELL',
        current_score=55,
        current_price=145,
        fundamentals={'pe_ratio': 10.5, 'roe': 18, 'debt_to_equity': 0.3},
        reason='Score dropped below 60',
        rank=15,
        sector='Metals'
    )
    print(f"   Original action: SELL")
    print(f"   Final action: {validation['final_action']}")
    print(f"   Warnings: {len(validation['warnings'])}")
    for warning in validation['warnings']:
        print(f"      - {warning}")
    
    # Test 4: Check score change detection
    print("\n📝 Test 4: Testing score change detection")
    _, score_desc = history.check_score_change('NMDC', 55)
    print(f"   {score_desc}")
    
    # Test 5: Check fundamental change detection
    print("\n📝 Test 5: Testing fundamental change detection (PE +50%)")
    has_changed, changes = history.check_fundamental_change(
        'NMDC',
        {'pe_ratio': 15.75, 'roe': 18, 'debt_to_equity': 0.3}  # PE increased 50%
    )
    print(f"   Fundamental change detected: {has_changed}")
    if changes:
        for change in changes:
            print(f"      - {change}")
    
    # Test 6: Generate stability report
    print("\n📝 Test 6: Generating stability report")
    report = history.generate_stability_report()
    print(f"   Total recommendations: {report['total_recommendations']}")
    print(f"   Unique stocks: {report['unique_stocks']}")
    print(f"   Flip-flops (7 days): {report['flip_flops_7d']}")
    print(f"   Flip-flops (14 days): {report['flip_flops_14d']}")
    
    # Test 7: Get recommendation summary
    print("\n📝 Test 7: Getting recommendation summary for NMDC")
    summary = history.get_recommendation_summary('NMDC', days=30)
    print(f"   Records found: {len(summary)}")
    if not summary.empty:
        print("\n   Recent recommendations:")
        for _, rec in summary.iterrows():
            print(f"      {rec['date'].strftime('%Y-%m-%d')}: {rec['action']} @ ₹{rec['price']:.2f} (Score: {rec['score']:.1f})")
    
    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print(f"📁 Test history file: {history.history_file}")

if __name__ == "__main__":
    test_recommendation_history()
