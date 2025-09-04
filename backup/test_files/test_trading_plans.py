#!/usr/bin/env python3
"""
Test Enhanced Excel Report with Trading Plans
Quick test to demonstrate the new Trading Plans functionality
"""

import sys
sys.path.append('src')
sys.path.append('.')

import pandas as pd
import numpy as np
from datetime import datetime
import os

# Create sample data that includes all the enhanced fields
def create_sample_trading_data():
    """Create sample data with trading plans"""
    
    sample_data = {
        'symbol': ['RELIANCE', 'TCS', 'HDFCBANK', 'ICICIBANK', 'INFY'],
        'company_name': ['Reliance Industries Ltd', 'Tata Consultancy Services', 'HDFC Bank Ltd', 'ICICI Bank Ltd', 'Infosys Ltd'],
        'current_price': [2485.50, 3245.75, 1632.80, 945.30, 1456.25],
        'overall_score_with_value': [78.5, 82.3, 75.8, 71.2, 76.9],
        'undervaluation_score': [72, 58, 78, 83, 65],
        'fundamental_score': [75, 85, 80, 70, 78],
        'technical_score': [68, 72, 71, 65, 69],
        'risk_adjusted_score': [76.2, 79.8, 74.5, 69.8, 75.1],
        'risk_category': ['MODERATE', 'LOW', 'LOW', 'MODERATE', 'LOW'],
        'final_recommendation': ['🟢 BUY (VALUE)', '🟢 STRONG BUY', '🟢 BUY (VALUE)', '🟢 BUY (UNDERVALUED)', '🟢 BUY'],
        'pe_ratio': [12.5, 25.8, 18.2, 15.1, 22.3],
        'pb_ratio': [1.8, 3.2, 2.1, 1.5, 2.8],
        'roe': [15.2, 35.8, 18.5, 16.2, 22.1],
        'dividend_yield': [2.5, 1.2, 3.1, 2.8, 2.0],
        'sector': ['Energy', 'IT Services', 'Banking', 'Banking', 'IT Services']
    }
    
    return pd.DataFrame(sample_data)

# Test the Support & Resistance calculation
def test_support_resistance():
    """Test support resistance calculation with sample data"""
    
    # Mock the calculator for demonstration
    sample_sr_data = {
        'RELIANCE': {
            'immediate_resistance': 2683.10,
            'strong_resistance': 2700.00,
            'immediate_support': 2462.17,
            'strong_support': 2406.00,
            'entry_range_low': 2435.79,
            'entry_range_high': 2497.93,
            'target_1': 2572.69,
            'target_1_pct': 3.5,
            'target_2': 2684.34,
            'target_2_pct': 8.0,
            'stop_loss': 2348.80,
            'stop_loss_pct': -5.5,
            'risk_reward_ratio': 0.64,
            'trading_plan_text': """Support & Resistance Levels:
• Immediate Resistance: ₹2683.10 (52-week high)
• Strong Resistance: ₹2700.00 (psychological level)
• Immediate Support: ₹2462.17 (20-day MA)
• Strong Support: ₹2406.00 (60-day low)

Trading Plan:
• Entry: ₹2435.79-2497.93 on minor dips
• Target 1: ₹2572.69 (+3.5%)
• Target 2: ₹2684.34 (+8.0%)
• Stop Loss: ₹2348.80 (-5.5%)"""
        },
        'TCS': {
            'immediate_resistance': 3456.25,
            'strong_resistance': 3525.38,
            'immediate_support': 3198.27,
            'strong_support': 3067.15,
            'entry_range_low': 3180.84,
            'entry_range_high': 3261.99,
            'target_1': 3359.35,
            'target_1_pct': 3.5,
            'target_2': 3505.41,
            'target_2_pct': 8.0,
            'stop_loss': 3067.23,
            'stop_loss_pct': -5.5,
            'risk_reward_ratio': 0.64,
            'trading_plan_text': """Support & Resistance Levels:
• Immediate Resistance: ₹3456.25 (52-week high)
• Strong Resistance: ₹3525.38 (psychological level)
• Immediate Support: ₹3198.27 (20-day MA)
• Strong Support: ₹3067.15 (60-day low)

Trading Plan:
• Entry: ₹3180.84-3261.99 on minor dips
• Target 1: ₹3359.35 (+3.5%)
• Target 2: ₹3505.41 (+8.0%)
• Stop Loss: ₹3067.23 (-5.5%)"""
        }
    }
    
    return sample_sr_data

def create_sample_excel_report():
    """Create a sample Excel report with trading plans"""
    try:
        # Create sample data
        df = create_sample_trading_data()
        sr_data = test_support_resistance()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reports/Sample_Trading_Plan_Report_{timestamp}.xlsx"
        
        # Ensure reports directory exists
        os.makedirs('reports', exist_ok=True)
        
        # Create enhanced trading plans data
        trading_plans_data = []
        for _, stock in df.iterrows():
            symbol = stock['symbol']
            if symbol in sr_data:
                sr_info = sr_data[symbol]
                trading_plan_record = {
                    'symbol': symbol,
                    'company_name': stock['company_name'],
                    'current_price': stock['current_price'],
                    'overall_score': stock['overall_score_with_value'],
                    'recommendation': stock['final_recommendation'],
                    **sr_info
                }
                trading_plans_data.append(trading_plan_record)
        
        # Create Excel file with trading plans
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
                'border': 1, 'align': 'center'
            })
            
            data_format = workbook.add_format({
                'border': 1, 'align': 'center'
            })
            
            price_format = workbook.add_format({
                'border': 1, 'align': 'center', 'num_format': '₹#,##0.00'
            })
            
            percent_format = workbook.add_format({
                'border': 1, 'align': 'center', 'num_format': '0.0%'
            })
            
            text_format = workbook.add_format({
                'border': 1, 'text_wrap': True, 'align': 'left', 'valign': 'top'
            })
            
            # 1. Main summary sheet
            df.to_excel(writer, sheet_name='Stock Analysis', index=False)
            
            # 2. Trading Plans Sheet
            if trading_plans_data:
                worksheet = workbook.add_worksheet('Trading Plans')
                
                # Headers
                headers = ['Symbol', 'Company', 'Current Price', 'Score', 'Recommendation',
                          'Immediate Resistance', 'Strong Resistance', 'Immediate Support', 'Strong Support',
                          'Entry Low', 'Entry High', 'Target 1', 'Target 1 %', 'Target 2', 'Target 2 %',
                          'Stop Loss', 'Stop Loss %', 'Risk/Reward', 'Trading Plan Details']
                
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header, header_format)
                
                # Data
                for row, plan in enumerate(trading_plans_data, 1):
                    worksheet.write(row, 0, plan['symbol'], data_format)
                    worksheet.write(row, 1, plan['company_name'], data_format)
                    worksheet.write(row, 2, plan['current_price'], price_format)
                    worksheet.write(row, 3, plan['overall_score'], data_format)
                    worksheet.write(row, 4, plan['recommendation'], data_format)
                    worksheet.write(row, 5, plan['immediate_resistance'], price_format)
                    worksheet.write(row, 6, plan['strong_resistance'], price_format)
                    worksheet.write(row, 7, plan['immediate_support'], price_format)
                    worksheet.write(row, 8, plan['strong_support'], price_format)
                    worksheet.write(row, 9, plan['entry_range_low'], price_format)
                    worksheet.write(row, 10, plan['entry_range_high'], price_format)
                    worksheet.write(row, 11, plan['target_1'], price_format)
                    worksheet.write(row, 12, plan['target_1_pct']/100, percent_format)
                    worksheet.write(row, 13, plan['target_2'], price_format)
                    worksheet.write(row, 14, plan['target_2_pct']/100, percent_format)
                    worksheet.write(row, 15, plan['stop_loss'], price_format)
                    worksheet.write(row, 16, plan['stop_loss_pct']/100, percent_format)
                    worksheet.write(row, 17, plan['risk_reward_ratio'], data_format)
                    worksheet.write(row, 18, plan['trading_plan_text'], text_format)
                
                # Set column widths
                worksheet.set_column('A:A', 12)  # Symbol
                worksheet.set_column('B:B', 25)  # Company
                worksheet.set_column('C:R', 12)  # Other columns
                worksheet.set_column('S:S', 80)  # Trading plan text
                
                # Set row heights
                worksheet.set_row(0, 20)  # Header
                for row in range(1, len(trading_plans_data) + 1):
                    worksheet.set_row(row, 120)  # Data rows
        
        print(f"✅ Sample Excel report created: {filename}")
        print("\n📊 TRADING PLANS SHEET INCLUDES:")
        print("   • Support & Resistance Levels")
        print("   • Entry Points with Price Ranges")
        print("   • Target Levels with % Gains")
        print("   • Stop Loss Levels with % Risk")
        print("   • Risk/Reward Ratios")
        print("   • Detailed Trading Plan Text")
        
        return filename
        
    except Exception as e:
        print(f"❌ Error creating sample report: {e}")
        return None

if __name__ == "__main__":
    print("🎯 TESTING ENHANCED EXCEL REPORT WITH TRADING PLANS")
    print("=" * 60)
    
    result = create_sample_excel_report()
    
    if result:
        print(f"\n🎉 SUCCESS! Check the file: {result}")
        print("\nThis demonstrates the new Trading Plans sheet that will be")
        print("included in your enhanced stock analysis reports!")
    else:
        print("\n❌ Test failed")
