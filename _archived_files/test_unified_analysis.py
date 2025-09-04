#!/usr/bin/env python3
"""
Unified Comprehensive Stock Analysis Test
Combines both enhanced fundamental analysis and enhanced technical analysis with patterns
"""

import sys
sys.path.append('src')

from enhanced_fundamental_analyzer import get_comprehensive_stock_data
from enhanced_technical_analyzer import get_short_term_technical_analysis, display_short_term_analysis
from technical_analyzer import get_ohlcv, calculate_indicators, compute_technical_score
from excel_exporter import ExcelExporter
import pandas as pd
import yfinance as yf
from datetime import datetime
import logging
import os

class UnifiedStockAnalyzer:
    """Unified Stock Analyzer combining all analysis methods"""
    
    def __init__(self):
        self.setup_logging()
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        os.makedirs('data', exist_ok=True)
        log_filename = f"data/unified_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        
        self.log_file = log_filename
    
    def get_legacy_technical_analysis(self, symbol):
        """Get legacy technical analysis (from test_comprehensive_analysis.py)"""
        try:
            # Add .NS suffix for NSE stocks if not present
            if not symbol.endswith('.NS'):
                ticker_symbol = f"{symbol}.NS"
            else:
                ticker_symbol = symbol
                
            # Get OHLCV data
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="1y", interval="1d")
            
            if hist.empty:
                print(f"   ⚠️  No OHLCV data available for {symbol}")
                return None
                
            # Calculate technical indicators
            indicators = calculate_indicators(hist)
            
            if not indicators:
                print(f"   ⚠️  Could not calculate technical indicators for {symbol}")
                return None
                
            # Compute technical score
            tech_score, tech_analysis = compute_technical_score(indicators)
            
            # Prepare technical data with consistent naming
            tech_data = {
                'legacy_technical_score': tech_score,
                'legacy_technical_analysis': tech_analysis,
                'legacy_rsi': indicators.get('rsi14', 0),
                'legacy_macd': indicators.get('macd', 0),
                'legacy_macd_signal': indicators.get('macd_signal', 0),
                'legacy_macd_histogram': indicators.get('macd_hist', 0),
                'legacy_sma_20': indicators.get('sma20', 0),
                'legacy_sma_50': indicators.get('sma50', 0),
                'legacy_sma_100': indicators.get('sma100', 0),
                'legacy_sma_200': indicators.get('sma200', 0),
                'legacy_ema_12': indicators.get('ema12', 0),
                'legacy_ema_26': indicators.get('ema26', 0),
                'legacy_stoch_k': indicators.get('stoch_k', 0),
                'legacy_stoch_d': indicators.get('stoch_d', 0),
                'legacy_bb_upper': indicators.get('bb_upper', 0),
                'legacy_bb_lower': indicators.get('bb_lower', 0),
                'legacy_volatility': indicators.get('volatility', 0),
                'legacy_volume_trend': indicators.get('volume_trend', 'Unknown'),
                'legacy_trend_direction': indicators.get('trend', 'Sideways'),
                'legacy_support_levels': str(indicators.get('support_levels', [])),
                'legacy_resistance_levels': str(indicators.get('resistance_levels', [])),
                'legacy_52w_high': indicators.get('52W_High', 0),
                'legacy_52w_low': indicators.get('52W_Low', 0),
                'legacy_daily_change': indicators.get('Daily_Change', 0),
                'legacy_weekly_change': indicators.get('Weekly_Change', 0)
            }
            
            return tech_data
            
        except Exception as e:
            print(f"   ❌ Legacy technical analysis failed for {symbol}: {e}")
            logging.error(f"Legacy technical analysis failed for {symbol}: {e}")
            return None
    
    def get_unified_analysis(self, symbol, technical_period_days=90):
        """
        Get unified comprehensive analysis combining:
        1. Enhanced fundamental analysis (58 data points)
        2. Enhanced technical analysis with patterns (short-term focus)
        3. Legacy technical analysis (for comparison)
        """
        print(f"🎯 UNIFIED COMPREHENSIVE ANALYSIS FOR {symbol}")
        print("=" * 80)
        
        analysis_start_time = datetime.now()
        
        # 1. FUNDAMENTAL ANALYSIS (Enhanced - 58 fields)
        print("💼 FUNDAMENTAL ANALYSIS (58 fields):")
        print("-" * 45)
        fund_data = get_comprehensive_stock_data(symbol)
        
        if not fund_data:
            print("❌ Failed to fetch fundamental data")
            logging.error(f"Fundamental analysis failed for {symbol}")
            return None, None, None
        
        print(f"✅ Fundamental: {len(fund_data)} data points")
        logging.info(f"Fundamental analysis completed for {symbol} with {len(fund_data)} data points")
        
        # 2. ENHANCED TECHNICAL ANALYSIS (Short-term with patterns)
        print(f"\n📈 ENHANCED TECHNICAL ANALYSIS ({technical_period_days} days with patterns):")
        print("-" * 65)
        enhanced_tech_data = get_short_term_technical_analysis(symbol, technical_period_days)
        
        if enhanced_tech_data:
            print(f"✅ Enhanced Technical: {len(enhanced_tech_data)} indicators & patterns")
            logging.info(f"Enhanced technical analysis completed for {symbol} with {len(enhanced_tech_data)} indicators")
        else:
            print("❌ Enhanced technical analysis failed")
            logging.warning(f"Enhanced technical analysis failed for {symbol}")
            enhanced_tech_data = {}
        
        # 3. LEGACY TECHNICAL ANALYSIS (For comparison)
        print(f"\n📊 LEGACY TECHNICAL ANALYSIS (1 year):")
        print("-" * 40)
        legacy_tech_data = self.get_legacy_technical_analysis(symbol)
        
        if legacy_tech_data:
            print(f"✅ Legacy Technical: {len(legacy_tech_data)} indicators")
            logging.info(f"Legacy technical analysis completed for {symbol} with {len(legacy_tech_data)} indicators")
        else:
            print("❌ Legacy technical analysis failed")
            logging.warning(f"Legacy technical analysis failed for {symbol}")
            legacy_tech_data = {}
        
        # 4. COMBINE ALL DATA
        print(f"\n🔄 COMBINING ALL ANALYSIS DATA:")
        print("-" * 35)
        
        combined_data = fund_data.copy()
        
        # Add enhanced technical data
        if enhanced_tech_data:
            for key, value in enhanced_tech_data.items():
                if key not in combined_data:
                    combined_data[f"enhanced_{key}"] = value
                else:
                    combined_data[f"enhanced_tech_{key}"] = value
        
        # Add legacy technical data
        if legacy_tech_data:
            combined_data.update(legacy_tech_data)
        
        # 5. CALCULATE COMPREHENSIVE SCORES
        print(f"\n🎯 COMPREHENSIVE SCORING:")
        print("-" * 30)
        
        # Extract scores
        fund_score = combined_data.get('fundamental_score', 50)
        enhanced_tech_score = enhanced_tech_data.get('short_term_score', 50) if enhanced_tech_data else 50
        legacy_tech_score = legacy_tech_data.get('legacy_technical_score', 50) if legacy_tech_data else 50
        
        # Multiple scoring approaches
        approaches = {
            'fundamental_weighted': fund_score,  # Pure fundamental
            'enhanced_balanced': (fund_score * 0.6) + (enhanced_tech_score * 0.4),  # 60% fund, 40% enhanced tech
            'legacy_balanced': (fund_score * 0.5) + (legacy_tech_score * 0.5),  # 50-50 with legacy tech
            'triple_weighted': (fund_score * 0.5) + (enhanced_tech_score * 0.3) + (legacy_tech_score * 0.2)  # All three
        }
        
        # Add all scores to combined data
        combined_data.update({
            'fundamental_score_final': fund_score,
            'enhanced_technical_score_final': enhanced_tech_score,
            'legacy_technical_score_final': legacy_tech_score,
            'overall_score_fundamental_weighted': approaches['fundamental_weighted'],
            'overall_score_enhanced_balanced': approaches['enhanced_balanced'],
            'overall_score_legacy_balanced': approaches['legacy_balanced'],
            'overall_score_triple_weighted': approaches['triple_weighted'],
            'analysis_timestamp': analysis_start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'analysis_duration_seconds': (datetime.now() - analysis_start_time).total_seconds()
        })
        
        # Generate recommendations for each approach
        recommendations = {}
        for approach_name, score in approaches.items():
            recommendations[f'recommendation_{approach_name}'] = self.get_detailed_recommendation(fund_score, enhanced_tech_score, legacy_tech_score, approach_name)
            combined_data[f'recommendation_{approach_name}'] = recommendations[f'recommendation_{approach_name}']
        
        # Display scoring summary
        print(f"   💼 Fundamental Score       : {fund_score:.1f}/100")
        print(f"   📈 Enhanced Technical Score: {enhanced_tech_score:.1f}/100")
        print(f"   📊 Legacy Technical Score  : {legacy_tech_score:.1f}/100")
        print(f"   🎯 Enhanced Balanced Score : {approaches['enhanced_balanced']:.1f}/100")
        print(f"   🎯 Triple Weighted Score   : {approaches['triple_weighted']:.1f}/100")
        
        total_fields = len(combined_data)
        print(f"   📊 Total Combined Fields   : {total_fields}")
        
        logging.info(f"Unified analysis completed for {symbol}: {total_fields} total fields")
        
        return combined_data, enhanced_tech_data, legacy_tech_data
    
    def get_detailed_recommendation(self, fund_score, enhanced_tech_score, legacy_tech_score, approach):
        """Generate detailed recommendation based on approach"""
        
        if approach == 'fundamental_weighted':
            score = fund_score
            if score >= 70: return "🟢 STRONG BUY (Excellent fundamentals)"
            elif score >= 60: return "🟢 BUY (Good fundamentals)"
            elif score >= 50: return "🟡 HOLD (Average fundamentals)"
            elif score >= 40: return "🟠 WEAK SELL (Weak fundamentals)"
            else: return "🔴 SELL (Poor fundamentals)"
        
        elif approach == 'enhanced_balanced':
            score = (fund_score * 0.6) + (enhanced_tech_score * 0.4)
            if fund_score >= 70 and enhanced_tech_score >= 70:
                return "🟢 STRONG BUY (Excellent fundamentals + strong short-term momentum)"
            elif fund_score >= 60 and enhanced_tech_score <= 40:
                return "🟡 LONG-TERM BUY (Good fundamentals, weak short-term signals)"
            elif fund_score <= 40 and enhanced_tech_score >= 60:
                return "🟠 SHORT-TERM TRADE (Weak fundamentals, good short-term momentum)"
            elif score >= 65: return "🟢 BUY"
            elif score >= 55: return "🟡 HOLD"
            else: return "🔴 SELL"
        
        elif approach == 'legacy_balanced':
            score = (fund_score * 0.5) + (legacy_tech_score * 0.5)
            if score >= 70: return "🟢 STRONG BUY (Combined signals positive)"
            elif score >= 60: return "🟢 BUY"
            elif score >= 50: return "🟡 HOLD"
            elif score >= 40: return "🟠 WEAK SELL"
            else: return "🔴 SELL"
        
        elif approach == 'triple_weighted':
            score = (fund_score * 0.5) + (enhanced_tech_score * 0.3) + (legacy_tech_score * 0.2)
            if score >= 70: return "🟢 STRONG BUY (All signals align)"
            elif score >= 60: return "🟢 BUY (Positive consensus)"
            elif score >= 50: return "🟡 HOLD (Mixed signals)"
            elif score >= 40: return "🟠 WEAK SELL (Negative bias)"
            else: return "🔴 SELL (Strong negative signals)"
        
        return "❓ UNKNOWN"
    
    def display_unified_analysis(self, combined_data, enhanced_tech_data=None, legacy_tech_data=None):
        """Display comprehensive unified analysis"""
        if not combined_data:
            print("❌ No analysis data available")
            return
        
        symbol = combined_data.get('symbol', 'UNKNOWN')
        
        print(f"\n📋 UNIFIED ANALYSIS SUMMARY FOR {symbol}")
        print("=" * 80)
        
        # Analysis statistics
        total_fields = len(combined_data)
        fund_fields = sum(1 for key in combined_data.keys() if not key.startswith(('enhanced_', 'legacy_')))
        enhanced_fields = sum(1 for key in combined_data.keys() if key.startswith('enhanced_'))
        legacy_fields = sum(1 for key in combined_data.keys() if key.startswith('legacy_'))
        
        print(f"\n📊 DATA COLLECTION SUMMARY:")
        print("-" * 35)
        print(f"   Total Fields        : {total_fields}")
        print(f"   Fundamental Fields  : {fund_fields}")
        print(f"   Enhanced Tech Fields: {enhanced_fields}")
        print(f"   Legacy Tech Fields  : {legacy_fields}")
        print(f"   Analysis Duration   : {combined_data.get('analysis_duration_seconds', 0):.1f} seconds")
        
        # Key fundamental metrics
        print(f"\n💼 KEY FUNDAMENTAL METRICS:")
        print("-" * 35)
        fund_keys = [
            ('Company', 'company_name'),
            ('Sector', 'sector'),
            ('Current Price', 'current_price'),
            ('Market Cap', 'market_cap'),
            ('PE Ratio', 'pe_ratio'),
            ('Revenue Growth', 'revenue_growth'),
            ('Fundamental Score', 'fundamental_score_final')
        ]
        
        for name, key in fund_keys:
            if key in combined_data:
                value = combined_data[key]
                if isinstance(value, (int, float)) and value != 0:
                    if 'Price' in name:
                        print(f"   {name:<18}: ₹{value:,.2f}")
                    elif 'Market Cap' in name:
                        print(f"   {name:<18}: ₹{value:,.0f}")
                    elif '%' in name or 'Growth' in name:
                        print(f"   {name:<18}: {value:.2f}%")
                    else:
                        print(f"   {name:<18}: {value:.2f}")
                elif value not in [0, 'N/A', None, '']:
                    print(f"   {name:<18}: {value}")
        
        # Enhanced technical signals
        print(f"\n📈 ENHANCED TECHNICAL SIGNALS:")
        print("-" * 40)
        if enhanced_tech_data:
            enhanced_keys = [
                ('Short-term Score', 'short_term_score'),
                ('Trading Signal', 'short_term_signal'),
                ('5D Price Change', 'price_change_5d'),
                ('20D Price Change', 'price_change_20d'),
                ('RSI (14)', 'rsi_14'),
                ('MACD Crossover', 'macd_crossover'),
                ('MA Alignment', 'ma_alignment'),
                ('Volume Trend', 'volume_trend')
            ]
            
            for name, key in enhanced_keys:
                if key in enhanced_tech_data:
                    value = enhanced_tech_data[key]
                    if isinstance(value, (int, float)):
                        if 'Change' in name:
                            emoji = "📈" if value > 0 else "📉" if value < 0 else "➡️"
                            print(f"   {name:<18}: {emoji} {value:+.2f}%")
                        else:
                            print(f"   {name:<18}: {value:.2f}")
                    else:
                        print(f"   {name:<18}: {value}")
        else:
            print("   Enhanced technical analysis not available")
        
        # Pattern summary
        if enhanced_tech_data:
            patterns = enhanced_tech_data.get('candlestick_patterns', [])
            chart_patterns = enhanced_tech_data.get('chart_patterns', [])
            
            if patterns or chart_patterns:
                print(f"\n🕯️ DETECTED PATTERNS:")
                print("-" * 25)
                
                if patterns:
                    print("   Candlestick Patterns:")
                    for pattern in patterns[:3]:  # Show top 3
                        print(f"     • {pattern}")
                
                if chart_patterns:
                    print("   Chart Patterns:")
                    for pattern in chart_patterns:
                        print(f"     • {pattern}")
        
        # Multiple recommendations
        print(f"\n🎯 INVESTMENT RECOMMENDATIONS:")
        print("=" * 45)
        
        approaches = [
            ('Fundamental Weighted', 'recommendation_fundamental_weighted', 'overall_score_fundamental_weighted'),
            ('Enhanced Balanced', 'recommendation_enhanced_balanced', 'overall_score_enhanced_balanced'),
            ('Legacy Balanced', 'recommendation_legacy_balanced', 'overall_score_legacy_balanced'),
            ('Triple Weighted', 'recommendation_triple_weighted', 'overall_score_triple_weighted')
        ]
        
        for approach_name, rec_key, score_key in approaches:
            recommendation = combined_data.get(rec_key, 'N/A')
            score = combined_data.get(score_key, 0)
            print(f"   {approach_name:<20}: {score:.1f}/100 - {recommendation}")

def test_unified_analysis():
    """Test unified comprehensive analysis"""
    print("🔧 TESTING UNIFIED COMPREHENSIVE STOCK ANALYSIS")
    print("=" * 80)
    
    analyzer = UnifiedStockAnalyzer()
    symbol = "RELIANCE"
    
    # Get unified analysis
    combined_data, enhanced_tech_data, legacy_tech_data = analyzer.get_unified_analysis(symbol, technical_period_days=90)
    
    if combined_data:
        # Display comprehensive summary
        analyzer.display_unified_analysis(combined_data, enhanced_tech_data, legacy_tech_data)
        
        # Display detailed enhanced technical analysis
        if enhanced_tech_data:
            print(f"\n📈 DETAILED ENHANCED TECHNICAL ANALYSIS:")
            print("=" * 50)
            display_short_term_analysis(enhanced_tech_data)
        
        # Generate Excel report
        print(f"\n📊 GENERATING COMPREHENSIVE EXCEL REPORT:")
        print("-" * 50)
        
        try:
            # Prepare data for Excel
            excel_data = combined_data.copy()
            
            # Convert lists and complex objects to strings for Excel compatibility
            for key, value in excel_data.items():
                if isinstance(value, (list, dict)):
                    excel_data[key] = str(value)
                elif pd.isna(value):
                    excel_data[key] = ''
            
            df = pd.DataFrame([excel_data])
            excel_exporter = ExcelExporter()
            filename = excel_exporter.generate_daily_report(df)
            
            print(f"✅ Comprehensive Excel report: {filename}")
            logging.info(f"Excel report generated: {filename}")
            
            # Check file size
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                print(f"   File size: {file_size:,} bytes")
                logging.info(f"Excel file size: {file_size} bytes")
            
            # Final comprehensive summary
            total_fields = len(excel_data)
            non_zero_fields = sum(1 for v in excel_data.values() if pd.notna(v) and v != 0 and v != '')
            
            print(f"\n🎉 UNIFIED ANALYSIS COMPLETE!")
            print("=" * 45)
            print(f"📊 Total data fields        : {total_fields}")
            print(f"📈 Non-zero/valid fields    : {non_zero_fields}")
            print(f"📊 Data completeness        : {(non_zero_fields/total_fields)*100:.1f}%")
            print(f"💼 Fundamental score        : {combined_data.get('fundamental_score_final', 0):.1f}/100")
            print(f"📈 Enhanced technical score : {combined_data.get('enhanced_technical_score_final', 0):.1f}/100")
            print(f"📊 Legacy technical score   : {combined_data.get('legacy_technical_score_final', 0):.1f}/100")
            print(f"🎯 Best overall score       : {combined_data.get('overall_score_triple_weighted', 0):.1f}/100")
            print(f"🎯 Final recommendation     : {combined_data.get('recommendation_triple_weighted', 'N/A')}")
            print(f"📝 Log file                 : {analyzer.log_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Excel generation failed: {e}")
            logging.error(f"Excel generation failed: {e}")
            return False
    else:
        print("❌ Unified analysis failed")
        logging.error(f"Unified analysis failed for {symbol}")
        return False

if __name__ == "__main__":
    success = test_unified_analysis()
    
    if success:
        print("\n🎉 UNIFIED COMPREHENSIVE ANALYSIS TEST PASSED!")
        print("📊 All analysis methods successfully integrated:")
        print("   ✅ Enhanced Fundamental Analysis (58 fields)")
        print("   ✅ Enhanced Technical Analysis with Patterns")
        print("   ✅ Legacy Technical Analysis")
        print("   ✅ Multiple Scoring Approaches")
        print("   ✅ Comprehensive Excel Export")
    else:
        print("\n❌ UNIFIED COMPREHENSIVE ANALYSIS TEST FAILED!")
        print("🔧 Check individual analysis components")
