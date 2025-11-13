#!/usr/bin/env python3
"""
Stock Selection Methodology Analysis
Analyzing how stocks are selected in the portfolio system
"""

import pandas as pd
import numpy as np
from datetime import datetime
import re

def analyze_stock_selection_methodology():
    """Analyze the complete stock selection methodology"""
    
    print("=" * 80)
    print("🔍 STOCK SELECTION METHODOLOGY ANALYSIS")
    print("=" * 80)
    print()
    
    # 1. ANALYZE CURRENT PORTFOLIO SELECTION
    print("📊 CURRENT PORTFOLIO ANALYSIS:")
    print("-" * 50)
    
    try:
        # Read all sheets to understand the selection process
        xl_file = pd.ExcelFile('full_portfolio_selection.xlsx')
        sheets = xl_file.sheet_names
        
        print(f"📋 Available sheets in portfolio file:")
        for i, sheet in enumerate(sheets, 1):
            print(f"  {i}. {sheet}")
        print()
        
        # Analyze each sheet to understand the selection flow
        selection_flow = {}
        
        for sheet in sheets:
            df = pd.read_excel('full_portfolio_selection.xlsx', sheet_name=sheet)
            selection_flow[sheet] = {
                'count': len(df),
                'columns': list(df.columns),
                'has_score': 'optimized_score' in df.columns or 'score' in df.columns.str.lower().any(),
                'has_action': 'action' in df.columns,
                'sample_data': df.head(2) if len(df) > 0 else None
            }
        
        print("🔄 SELECTION WORKFLOW ANALYSIS:")
        print("-" * 40)
        
        for sheet, info in selection_flow.items():
            print(f"\n📋 {sheet}:")
            print(f"   • Stock count: {info['count']}")
            print(f"   • Has scoring: {'✅' if info['has_score'] else '❌'}")
            print(f"   • Has actions: {'✅' if info['has_action'] else '❌'}")
            
            # Show key columns
            if 'optimized_score' in info['columns']:
                df_temp = pd.read_excel('full_portfolio_selection.xlsx', sheet_name=sheet)
                if len(df_temp) > 0:
                    score_stats = df_temp['optimized_score'].describe()
                    print(f"   • Score range: {score_stats['min']:.1f} to {score_stats['max']:.1f}")
                    print(f"   • Average score: {score_stats['mean']:.1f}")
        
        print()
        
        # 2. ANALYZE SCORING CRITERIA
        print("🎯 SCORING METHODOLOGY ANALYSIS:")
        print("-" * 40)
        
        # Read the All_Stocks_Scored sheet for comprehensive analysis
        if 'All_Stocks_Scored' in sheets:
            all_stocks = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='All_Stocks_Scored')
            
            print(f"📊 Total stocks analyzed: {len(all_stocks)}")
            print(f"📋 Scoring columns available:")
            
            score_columns = [col for col in all_stocks.columns if 'score' in col.lower()]
            for col in score_columns:
                print(f"   • {col}")
            
            if 'optimized_score' in all_stocks.columns:
                print(f"\n📈 Score Distribution:")
                score_bins = pd.cut(all_stocks['optimized_score'], 
                                  bins=[0, 30, 50, 60, 70, 75, 80, 100],
                                  labels=['Very Poor (0-30)', 'Poor (30-50)', 'Below Avg (50-60)', 
                                         'Average (60-70)', 'Good (70-75)', 'Very Good (75-80)', 'Excellent (80+)'])
                
                score_dist = all_stocks.groupby(score_bins).size()
                for score_range, count in score_dist.items():
                    percentage = (count / len(all_stocks) * 100)
                    print(f"   • {score_range}: {count} stocks ({percentage:.1f}%)")
            print()
        
        # 3. SELECTION THRESHOLDS ANALYSIS
        print("🎚️ SELECTION THRESHOLDS & CRITERIA:")
        print("-" * 45)
        
        if 'Current_Holdings' in sheets:
            holdings = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
            
            if 'optimized_score' in holdings.columns:
                min_score = holdings['optimized_score'].min()
                max_score = holdings['optimized_score'].max()
                avg_score = holdings['optimized_score'].mean()
                
                print(f"📊 Current Holdings Score Profile:")
                print(f"   • Minimum score: {min_score:.2f}")
                print(f"   • Maximum score: {max_score:.2f}")
                print(f"   • Average score: {avg_score:.2f}")
                print(f"   • Score threshold appears to be: ~{min_score:.0f}+")
            
            # Portfolio type analysis
            if 'portfolio_type' in holdings.columns:
                print(f"\n📋 Portfolio Classification:")
                portfolio_types = holdings['portfolio_type'].value_counts()
                for ptype, count in portfolio_types.items():
                    avg_score_type = holdings[holdings['portfolio_type'] == ptype]['optimized_score'].mean()
                    print(f"   • {ptype}: {count} stocks (avg score: {avg_score_type:.1f})")
            
            # Action-based analysis
            if 'action' in holdings.columns:
                print(f"\n🎯 Current Action Recommendations:")
                actions = holdings['action'].value_counts()
                for action, count in actions.items():
                    avg_score_action = holdings[holdings['action'] == action]['optimized_score'].mean()
                    print(f"   • {action}: {count} stocks (avg score: {avg_score_action:.1f})")
        
        print()
        
        # 4. SECTOR SELECTION BIAS
        print("🏢 SECTOR SELECTION ANALYSIS:")
        print("-" * 35)
        
        if 'All_Stocks_Scored' in sheets and 'Current_Holdings' in sheets:
            all_stocks = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='All_Stocks_Scored')
            holdings = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
            
            # Compare sector representation
            if 'sector' in all_stocks.columns and 'sector' in holdings.columns:
                all_sector_counts = all_stocks['sector'].value_counts()
                selected_sector_counts = holdings['sector'].value_counts()
                
                print("📊 Sector Selection Rate:")
                for sector in all_sector_counts.index:
                    total_in_universe = all_sector_counts[sector]
                    selected = selected_sector_counts.get(sector, 0)
                    selection_rate = (selected / total_in_universe * 100) if total_in_universe > 0 else 0
                    
                    # Get average score for this sector
                    sector_stocks = all_stocks[all_stocks['sector'] == sector]
                    avg_sector_score = sector_stocks['optimized_score'].mean() if 'optimized_score' in all_stocks.columns else 0
                    
                    print(f"   • {sector:<20}: {selected:2d}/{total_in_universe:2d} ({selection_rate:4.1f}%) - Avg Score: {avg_sector_score:.1f}")
        
        print()
        
        # 5. FUNDAMENTAL CRITERIA ANALYSIS
        print("💰 FUNDAMENTAL SELECTION CRITERIA:")
        print("-" * 40)
        
        fundamental_columns = ['market_cap', 'pe_ratio', 'pb_ratio', 'debt_to_equity', 
                             'roe', 'roc', 'current_ratio', 'revenue_growth', 'profit_growth']
        
        if 'Current_Holdings' in sheets:
            holdings = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
            
            print("📈 Fundamental Metrics Profile (Current Holdings):")
            for col in fundamental_columns:
                if col in holdings.columns:
                    col_data = holdings[col].dropna()
                    if len(col_data) > 0:
                        print(f"   • {col:<15}: Min={col_data.min():8.2f}, Max={col_data.max():8.2f}, Avg={col_data.mean():8.2f}")
        
        print()
        
        # 6. TECHNICAL CRITERIA
        print("📊 TECHNICAL SELECTION CRITERIA:")
        print("-" * 38)
        
        technical_columns = ['rsi', 'sma_20', 'sma_50', 'volatility_6m', 'beta', 'volume_ratio']
        
        if 'Current_Holdings' in sheets:
            holdings = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
            
            print("📈 Technical Metrics Profile (Current Holdings):")
            for col in technical_columns:
                if col in holdings.columns:
                    col_data = holdings[col].dropna()
                    if len(col_data) > 0:
                        print(f"   • {col:<15}: Min={col_data.min():8.2f}, Max={col_data.max():8.2f}, Avg={col_data.mean():8.2f}")
        
        print()
        
        return selection_flow
        
    except Exception as e:
        print(f"❌ Error analyzing selection methodology: {e}")
        return None

def analyze_scoring_formula():
    """Analyze the scoring formula used for stock selection"""
    
    print("🧮 SCORING FORMULA ANALYSIS:")
    print("-" * 35)
    
    try:
        # Look for scoring-related files
        import os
        scoring_files = []
        
        for file in os.listdir('.'):
            if file.endswith('.py') and ('scor' in file.lower() or 'engine' in file.lower()):
                scoring_files.append(file)
        
        print(f"📋 Scoring-related files found:")
        for file in scoring_files:
            print(f"   • {file}")
        
        # Try to read the corrected scoring engine
        if os.path.exists('corrected_scoring_engine.py'):
            print(f"\n🔍 Analyzing corrected_scoring_engine.py...")
            
            with open('corrected_scoring_engine.py', 'r') as f:
                content = f.read()
            
            # Extract scoring components
            if 'def calculate_score' in content:
                print("✅ Found calculate_score function")
                
                # Look for scoring weights
                weight_patterns = [
                    r'(\w+)_weight\s*=\s*([\d.]+)',
                    r'weight_(\w+)\s*=\s*([\d.]+)',
                    r'(\w+)\s*\*\s*([\d.]+)',
                ]
                
                weights_found = []
                for pattern in weight_patterns:
                    matches = re.findall(pattern, content)
                    weights_found.extend(matches)
                
                if weights_found:
                    print("\n📊 Scoring Weights Found:")
                    for component, weight in weights_found[:10]:  # Show first 10
                        print(f"   • {component}: {weight}")
                
                # Look for thresholds
                threshold_patterns = [
                    r'score\s*[><=]+\s*([\d.]+)',
                    r'threshold\s*=\s*([\d.]+)',
                    r'cutoff\s*=\s*([\d.]+)',
                ]
                
                thresholds_found = []
                for pattern in threshold_patterns:
                    matches = re.findall(pattern, content)
                    thresholds_found.extend(matches)
                
                if thresholds_found:
                    print(f"\n🎚️ Thresholds Found:")
                    for threshold in set(thresholds_found):
                        print(f"   • Threshold: {threshold}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error analyzing scoring formula: {e}")

def generate_selection_summary():
    """Generate a comprehensive selection methodology summary"""
    
    print("📋 STOCK SELECTION METHODOLOGY SUMMARY:")
    print("-" * 50)
    
    try:
        # Read current holdings for analysis
        holdings = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
        
        print("🎯 SELECTION PROCESS (Based on Analysis):")
        print()
        
        print("1️⃣ UNIVERSE DEFINITION:")
        print("   • Starts with broad stock universe (NSE/BSE listed)")
        print("   • Focus on liquid, large to mid-cap stocks")
        print("   • Minimum market cap threshold applied")
        print()
        
        print("2️⃣ FUNDAMENTAL SCREENING:")
        if 'market_cap' in holdings.columns:
            min_mcap = holdings['market_cap'].min()
            print(f"   • Market Cap: Minimum ₹{min_mcap/1e9:.0f}+ Cr")
        
        # Estimate other criteria based on holdings
        fundamental_criteria = {
            'pe_ratio': 'P/E Ratio screening for value',
            'debt_to_equity': 'Debt management quality',
            'roe': 'Return on Equity threshold',
            'current_ratio': 'Liquidity requirements'
        }
        
        for criterion, description in fundamental_criteria.items():
            if criterion in holdings.columns:
                data = holdings[criterion].dropna()
                if len(data) > 0:
                    print(f"   • {description}: {data.min():.1f} to {data.max():.1f}")
        print()
        
        print("3️⃣ TECHNICAL FILTERING:")
        if 'volatility_6m' in holdings.columns:
            vol_data = holdings['volatility_6m'].dropna()
            print(f"   • Volatility range: {vol_data.min():.1f}% to {vol_data.max():.1f}%")
        
        technical_criteria = {
            'rsi': 'RSI momentum filter',
            'beta': 'Market correlation screening'
        }
        
        for criterion, description in technical_criteria.items():
            if criterion in holdings.columns:
                data = holdings[criterion].dropna()
                if len(data) > 0:
                    print(f"   • {description}: {data.min():.1f} to {data.max():.1f}")
        print()
        
        print("4️⃣ SCORING & RANKING:")
        if 'optimized_score' in holdings.columns:
            score_data = holdings['optimized_score']
            print(f"   • Composite scoring system (0-100 scale)")
            print(f"   • Current holdings score range: {score_data.min():.1f} to {score_data.max():.1f}")
            print(f"   • Average score: {score_data.mean():.1f}")
            
            # Estimate threshold
            threshold = score_data.min()
            print(f"   • Estimated selection threshold: {threshold:.0f}+")
        print()
        
        print("5️⃣ PORTFOLIO CONSTRUCTION:")
        if 'portfolio_type' in holdings.columns:
            portfolio_types = holdings['portfolio_type'].value_counts()
            print("   • Multi-tier approach:")
            for ptype, count in portfolio_types.items():
                percentage = (count / len(holdings) * 100)
                print(f"     - {ptype}: {count} stocks ({percentage:.1f}%)")
        
        if 'sector' in holdings.columns:
            sector_count = holdings['sector'].nunique()
            print(f"   • Sector diversification: {sector_count} sectors")
            
            # Show concentration
            top_sector = holdings['sector'].value_counts().iloc[0]
            top_sector_name = holdings['sector'].value_counts().index[0]
            concentration = (top_sector / len(holdings) * 100)
            print(f"   • Largest sector: {top_sector_name} ({concentration:.1f}%)")
        print()
        
        print("6️⃣ DYNAMIC REBALANCING:")
        if 'action' in holdings.columns:
            actions = holdings['action'].value_counts()
            print("   • Continuous monitoring with actions:")
            for action, count in actions.items():
                percentage = (count / len(holdings) * 100)
                print(f"     - {action}: {count} stocks ({percentage:.1f}%)")
        
        print()
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")

if __name__ == "__main__":
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run comprehensive analysis
    selection_flow = analyze_stock_selection_methodology()
    
    if selection_flow:
        analyze_scoring_formula()
        generate_selection_summary()
        
        print("✅ Stock selection methodology analysis completed!")
    else:
        print("❌ Analysis incomplete - check data files")