"""
🧪 Phase 1 Test Script - Intelligence System

Tests the core components of Phase 1:
- IntelligenceDB
- PerformanceTracker
- OutcomeCalculator

This script will be deleted after testing is complete.
"""

import sys
sys.path.append('src')

from intelligence.intelligence_db import IntelligenceDB
from intelligence.performance_tracker import PerformanceTracker
from intelligence.outcome_calculator import OutcomeCalculator
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_database():
    """Test database initialization and operations"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Database Initialization")
    print("="*60)
    
    db = IntelligenceDB("data/test_intelligence.db")
    
    # Test recording a recommendation
    test_rec = {
        'date': datetime.now() - timedelta(days=35),
        'symbol': 'TESTSTOCK',
        'action': 'BUY',
        'score': 75.5,
        'price': 1000.0,
        'technical_score': 70.0,
        'fundamental_score': 80.0,
        'ml_prediction': 0.75,
        'sentiment_score': 65.0,
        'pe_ratio': 15.5,
        'pb_ratio': 2.3,
        'roe': 18.0,
        'market_regime': 'BULLISH',
        'sector': 'Technology',
        'reason': 'Test recommendation',
        'report_file': 'test_report.xlsx'
    }
    
    rec_id = db.record_recommendation(test_rec)
    print(f"✅ Recorded test recommendation (ID: {rec_id})")
    
    # Test recording an outcome
    test_outcome = {
        'recommendation_id': rec_id,
        'check_date': datetime.now() - timedelta(days=5),
        'days_elapsed': 30,
        'price_at_check': 1080.0,
        'return_pct': 8.0,
        'was_correct': True,
        'outcome_type': 'WIN',
        'benchmark_return': 5.5,
        'outperformance': 2.5
    }
    
    outcome_id = db.record_outcome(test_outcome)
    print(f"✅ Recorded test outcome (ID: {outcome_id})")
    
    # Test querying
    recs = db.get_recommendations(symbol='TESTSTOCK')
    print(f"✅ Retrieved {len(recs)} recommendations for TESTSTOCK")
    
    # Test statistics
    stats = db.get_statistics(period_days=90)
    print(f"✅ Statistics: {stats}")
    
    print("\n✅ Database tests passed!")
    return db

def test_performance_tracker():
    """Test performance tracking"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Performance Tracker")
    print("="*60)
    
    tracker = PerformanceTracker("data/test_intelligence.db")
    
    # Record a few test recommendations
    test_recs = [
        {
            'date': datetime.now() - timedelta(days=10),
            'symbol': 'TCS',
            'action': 'BUY',
            'score': 82.0,
            'price': 3500.0,
            'market_regime': 'BULLISH',
            'sector': 'Technology'
        },
        {
            'date': datetime.now() - timedelta(days=35),
            'symbol': 'RELIANCE',
            'action': 'INCREASE POSITION',
            'score': 78.5,
            'price': 2400.0,
            'market_regime': 'BULLISH',
            'sector': 'Energy'
        }
    ]
    
    for rec in test_recs:
        rec_id = tracker.record_new_recommendation(rec)
        print(f"✅ Recorded {rec['symbol']} (ID: {rec_id})")
    
    # Get performance summary
    summary = tracker.get_recent_performance_summary(days=90)
    print(f"\n📊 Performance Summary (90 days):")
    print(f"   Total Recommendations: {summary.get('total_recommendations', 0)}")
    print(f"   Total Outcomes: {summary.get('total_outcomes', 0)}")
    print(f"   Hit Rate: {summary.get('hit_rate', 0):.1f}%")
    print(f"   Average Return: {summary.get('avg_return', 0):+.2f}%")
    
    print("\n✅ Performance Tracker tests passed!")

def test_outcome_calculator():
    """Test outcome calculations"""
    print("\n" + "="*60)
    print("🧪 TEST 3: Outcome Calculator")
    print("="*60)
    
    calculator = OutcomeCalculator("data/test_intelligence.db")
    
    # Test hit rates
    hit_rates = calculator.calculate_hit_rates(period_days=90, check_period=30)
    print(f"\n📈 Hit Rates by Action (30-day):")
    for action, metrics in hit_rates.items():
        print(f"   {action}: {metrics['hit_rate']:.1f}% ({metrics['correct']}/{metrics['total']})")
    
    # Test sector performance
    sector_perf = calculator.calculate_sector_performance(period_days=90, check_period=30)
    print(f"\n🏢 Sector Performance:")
    for sector, metrics in sector_perf.items():
        print(f"   {sector}: {metrics['hit_rate']:.1f}% | Avg Return: {metrics['avg_return']:+.2f}%")
    
    # Generate full report
    report = calculator.generate_performance_report(period_days=90)
    print(f"\n📄 Performance Report Generated:")
    print(f"   Period: {report['period_days']} days")
    print(f"   Total Recommendations: {report['statistics'].get('total_recommendations', 0)}")
    print(f"   Best Performers: {len(report['best_performers'])}")
    print(f"   Worst Performers: {len(report['worst_performers'])}")
    
    print("\n✅ Outcome Calculator tests passed!")

def cleanup():
    """Clean up test data"""
    print("\n" + "="*60)
    print("🧹 CLEANUP: Removing Test Data")
    print("="*60)
    
    import os
    test_db = "data/test_intelligence.db"
    
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"✅ Removed {test_db}")
    else:
        print(f"ℹ️  No test database found")

def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧠 INTELLIGENCE SYSTEM - PHASE 1 TESTS")
    print("="*70)
    
    try:
        # Run tests
        test_database()
        test_performance_tracker()
        test_outcome_calculator()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nPhase 1 core components are working correctly.")
        print("Ready to proceed with historical migration and integration.")
        
        # Ask before cleanup
        print("\n" + "="*70)
        response = input("Clean up test files? (y/n): ").lower()
        if response == 'y':
            cleanup()
            print("✅ Cleanup complete!")
        else:
            print("ℹ️  Test files kept for inspection")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
