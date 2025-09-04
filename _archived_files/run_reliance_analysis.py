"""
Direct Single Stock Analysis - No Input Required
"""

import pandas as pd
import logging
from datetime import datetime
import os
import sys

# Add src to path
sys.path.append('src')

from src.enhanced_fundamental_analyzer import get_comprehensive_stock_data
from src.excel_exporter import ExcelReportGenerator
from enhanced_technical_analyzer import get_short_term_technical_analysis

def setup_logging():
    """Setup logging for single stock analysis"""
    os.makedirs('data', exist_ok=True)
    
    log_filename = f"data/single_stock_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    return log_filename

def analyze_stock_direct():
    """Analyze RELIANCE stock directly"""
    symbol = "RELIANCE.NS"
    
    print(f"🔍 Starting analysis for {symbol}")
    log_file = setup_logging()
    
    try:
        # Initialize Excel generator
        logging.info("Initializing Excel generator...")
        excel_generator = ExcelReportGenerator()
        
        print(f"\n📊 Analyzing {symbol}...")
        logging.info(f"Starting analysis for {symbol}")
        
        # Fundamental Analysis
        print("🔢 Running fundamental analysis...")
        fund_data = get_comprehensive_stock_data("RELIANCE")  # Remove .NS for the function
        
        if fund_data:
            print(f"✅ Fundamental analysis completed - {len(fund_data)} data points")
            logging.info(f"Fundamental analysis completed for {symbol} with {len(fund_data)} data points")
        else:
            print("❌ Fundamental analysis failed")
            logging.warning(f"Fundamental analysis failed for {symbol}")
            fund_data = {}
        
        # Technical Analysis
        print("📈 Running technical analysis...")
        tech_data = get_short_term_technical_analysis("RELIANCE")
        
        if tech_data:
            print(f"✅ Technical analysis completed - {len(tech_data)} indicators")
            logging.info(f"Technical analysis completed for {symbol} with {len(tech_data)} indicators")
        else:
            print("❌ Technical analysis failed")
            logging.warning(f"Technical analysis failed for {symbol}")
            tech_data = {}
        
        # Combine data
        combined_data = {
            'Symbol': symbol,
            'Analysis_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Add fundamental data
        if fund_data:
            combined_data.update(fund_data)
        
        # Add technical data
        if tech_data:
            combined_data.update(tech_data)
        
        # Create DataFrame
        df = pd.DataFrame([combined_data])
        
        print(f"\n📊 Analysis Summary for {symbol}:")
        print(f"   • Total data points: {len(combined_data)}")
        print(f"   • Fundamental fields: {len(fund_data) if fund_data else 0}")
        print(f"   • Technical fields: {len(tech_data) if tech_data else 0}")
        
        if 'OverallScore' in combined_data:
            print(f"   • Overall Score: {combined_data.get('OverallScore', 'N/A')}")
        if 'FundamentalScore' in combined_data:
            print(f"   • Fundamental Score: {combined_data.get('FundamentalScore', 'N/A')}")
        if 'TechnicalScore' in combined_data:
            print(f"   • Technical Score: {combined_data.get('TechnicalScore', 'N/A')}")
        
        # Generate Excel report
        print(f"\n📁 Generating Excel report...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"data/RELIANCE_analysis_{timestamp}.xlsx"
        
        try:
            excel_generator.create_comprehensive_report(df, excel_filename)
            print(f"✅ Excel report created: {excel_filename}")
            logging.info(f"Excel report created: {excel_filename}")
            
            # Check file size
            if os.path.exists(excel_filename):
                file_size = os.path.getsize(excel_filename)
                print(f"   • File size: {file_size:,} bytes")
                logging.info(f"Excel file size: {file_size} bytes")
                
                # Show some key data
                print(f"\n📋 Key Data Points:")
                if 'current_price' in combined_data:
                    print(f"   • Current Price: ₹{combined_data.get('current_price', 'N/A')}")
                if 'market_cap' in combined_data:
                    market_cap = combined_data.get('market_cap', 0)
                    if market_cap > 0:
                        print(f"   • Market Cap: ₹{market_cap:,.0f}")
                if 'pe_ratio' in combined_data:
                    print(f"   • P/E Ratio: {combined_data.get('pe_ratio', 'N/A')}")
                if 'rsi_14' in combined_data:
                    print(f"   • RSI (14): {combined_data.get('rsi_14', 'N/A')}")
        
        except Exception as e:
            print(f"❌ Excel generation failed: {str(e)}")
            logging.error(f"Excel generation failed: {str(e)}")
            
            # Fallback: save as CSV
            csv_filename = f"data/RELIANCE_analysis_{timestamp}.csv"
            df.to_csv(csv_filename, index=False)
            print(f"📄 Saved as CSV instead: {csv_filename}")
        
        return df
        
    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        logging.error(f"Analysis failed for {symbol}: {str(e)}")
        return None
    
    finally:
        logging.info("Analysis completed")

if __name__ == "__main__":
    print("🎯 RELIANCE Stock Analysis")
    print("="*50)
    result = analyze_stock_direct()
    if result is not None:
        print(f"\n🎉 Analysis completed successfully!")
    else:
        print(f"\n❌ Analysis failed")
