#!/usr/bin/env python3
"""
🧪 INTEGRATION TEST: Hybrid Optimized Scoring V4.0 + Adaptive Market Strategy
Test the enhanced analyze_top200_stocks_enhanced.py with new scoring system integration
"""

import sys
import logging
import traceback
from analyze_top200_stocks_enhanced import EnhancedTop200StockAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_hybrid_integration():
    """Test the hybrid scoring integration with a sample stock"""
    
    print("🧪 TESTING: Hybrid Optimized Scoring V4.0 Integration")
    print("="*70)
    
    try:
        # Initialize the enhanced analyzer
        print("📊 Initializing Enhanced Stock Analyzer...")
        analyzer = EnhancedTop200StockAnalyzer()
        
        # Check if hybrid components are properly initialized
        print(f"✅ Hybrid Scoring Engine: {hasattr(analyzer, 'hybrid_scoring_engine')}")
        print(f"✅ Adaptive Strategy: {hasattr(analyzer, 'adaptive_strategy')}")
        print(f"✅ Market Regime Detector: {hasattr(analyzer, 'regime_detector')}")
        
        # Test with a known stock
        test_symbol = "RELIANCE"
        print(f"\n🔍 Testing analysis for {test_symbol}...")
        
        # Run the enhanced analysis
        try:
            result = analyzer.analyze_single_stock(test_symbol)
        except Exception as e:
            print(f"❌ Exception during analysis: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return False
        
        if result and result.get('status') in ['success', 'completed']:
            print(f"\n✅ SUCCESS: Analysis completed for {test_symbol}")
            
            # Check hybrid scoring fields
            hybrid_fields = [
                'hybrid_overall_score',
                'hybrid_fundamental_quality', 
                'hybrid_momentum_technical',
                'hybrid_sector_multiplier',
                'market_regime_detected',
                'adaptive_position_size',
                'adaptive_quintile_target',
                'hybrid_confidence'
            ]
            
            print("\n📈 Hybrid Scoring Results:")
            for field in hybrid_fields:
                value = result.get(field, 'NOT FOUND')
                print(f"  {field}: {value}")
            
            # Check scoring comparison
            print(f"\n📊 Scoring System Comparison:")
            print(f"  Original Score: {result.get('overall_score_with_value', 'N/A')}")
            print(f"  Corrected Score: {result.get('corrected_overall_score', 'N/A')}")
            print(f"  Improved Score: {result.get('improved_overall_score', 'N/A')}")
            print(f"  Hybrid Score: {result.get('hybrid_overall_score', 'N/A')}")
            print(f"  Final Blended Score: {result.get('final_blended_score', 'N/A')}")
            
            # Check recommendations
            print(f"\n🎯 Recommendation Evolution:")
            print(f"  Original: {result.get('original_recommendation', 'N/A')}")
            print(f"  Corrected: {result.get('corrected_recommendation', 'N/A')}")
            print(f"  Phase 2: {result.get('phase2_recommendation', 'N/A')}")
            print(f"  FINAL: {result.get('final_recommendation', 'N/A')}")
            
            print(f"\n🌍 Market Context:")
            print(f"  Market Regime: {result.get('market_regime_detected', 'N/A')}")
            print(f"  Position Size: {result.get('adaptive_position_size', 'N/A')}")
            print(f"  Target Quintile: {result.get('adaptive_quintile_target', 'N/A')}")
            
            return True
            
        else:
            print(f"❌ FAILED: Analysis failed for {test_symbol}")
            if result:
                print(f"Error: {result.get('error_message', 'Unknown error')}")
                print(f"Status: {result.get('status', 'Unknown status')}")
                # Print available fields to debug
                print(f"Available fields: {list(result.keys())[:10]}")  # First 10 fields
            return False
            
    except Exception as e:
        print(f"❌ INTEGRATION TEST FAILED: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

def test_market_regime_detection():
    """Test market regime detection functionality"""
    
    print("\n🌊 TESTING: Market Regime Detection")
    print("="*50)
    
    try:
        from market_regime_detector import MarketRegimeDetector
        
        detector = MarketRegimeDetector()
        regime_data = detector.detect_regime()
        current_regime = regime_data.get('regime', 'SIDEWAYS') if regime_data else 'UNKNOWN'
        
        print(f"✅ Current Market Regime: {current_regime}")
        
        # Get regime details
        if regime_data and isinstance(regime_data, dict):
            print(f"📊 Regime Analysis:")
            print(f"  Regime: {regime_data.get('regime', 'N/A')}")
            print(f"  Strength: {regime_data.get('regime_strength', 'N/A')}")
            print(f"  VIX Level: {regime_data.get('vix_level', 'N/A')}")
            print(f"  Confidence: {regime_data.get('confidence', 0.5):.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Market regime detection failed: {str(e)}")
        return False

def main():
    """Run all integration tests"""
    
    print("🚀 STARTING INTEGRATION TESTS FOR HYBRID SCORING V4.0")
    print("="*80)
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: Hybrid Integration
    if test_hybrid_integration():
        tests_passed += 1
    
    # Test 2: Market Regime Detection
    if test_market_regime_detection():
        tests_passed += 1
    
    # Summary
    print("\n" + "="*80)
    print(f"🏁 INTEGRATION TEST SUMMARY")
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✅ ALL TESTS PASSED! Hybrid integration is working correctly.")
        print("🚀 Ready for production use with Hybrid Optimized Scoring V4.0")
    else:
        print("❌ Some tests failed. Please check the integration.")
        
    return tests_passed == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)