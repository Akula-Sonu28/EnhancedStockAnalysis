#!/usr/bin/env python3
"""
Portfolio Allocation Analysis
Comprehensive analysis of current portfolio allocation and recommendations
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def analyze_portfolio_allocation():
    """Comprehensive portfolio allocation analysis"""
    
    print("=" * 80)
    print("🏦 COMPREHENSIVE PORTFOLIO ALLOCATION ANALYSIS")
    print("=" * 80)
    print()
    
    try:
        # Read current holdings
        df = pd.read_excel('full_portfolio_selection.xlsx', sheet_name='Current_Holdings')
        
        print(f"📊 Portfolio Overview:")
        print(f"  • Total Holdings: {len(df)} stocks")
        print(f"  • Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. SECTOR ALLOCATION ANALYSIS
        print("🏢 SECTOR ALLOCATION ANALYSIS:")
        print("-" * 50)
        
        sector_analysis = df.groupby('sector').agg({
            'symbol': 'count',
            'market_cap': ['sum', 'mean'],
            'optimized_score': 'mean',
            'volatility_6m': 'mean'
        }).round(2)
        
        sector_analysis.columns = ['Count', 'Total_MarketCap', 'Avg_MarketCap', 'Avg_Score', 'Avg_Volatility']
        sector_analysis['Allocation_%'] = (sector_analysis['Count'] / len(df) * 100).round(1)
        sector_analysis['MarketCap_%'] = (sector_analysis['Total_MarketCap'] / sector_analysis['Total_MarketCap'].sum() * 100).round(1)
        
        # Sort by allocation percentage
        sector_analysis = sector_analysis.sort_values('Allocation_%', ascending=False)
        
        print("📈 Sector Breakdown:")
        print(sector_analysis[['Count', 'Allocation_%', 'MarketCap_%', 'Avg_Score', 'Avg_Volatility']].to_string())
        print()
        
        # 2. PORTFOLIO TYPE ANALYSIS
        print("📋 PORTFOLIO TYPE ANALYSIS:")
        print("-" * 40)
        
        if 'portfolio_type' in df.columns:
            portfolio_type_analysis = df.groupby('portfolio_type').agg({
                'symbol': 'count',
                'market_cap': 'sum',
                'optimized_score': 'mean'
            }).round(2)
            
            portfolio_type_analysis.columns = ['Count', 'Total_MarketCap', 'Avg_Score']
            portfolio_type_analysis['Allocation_%'] = (portfolio_type_analysis['Count'] / len(df) * 100).round(1)
            
            print(portfolio_type_analysis.to_string())
            print()
        
        # 3. ACTION RECOMMENDATIONS ANALYSIS
        print("🎯 ACTION RECOMMENDATIONS:")
        print("-" * 35)
        
        if 'action' in df.columns:
            action_analysis = df.groupby('action').agg({
                'symbol': 'count',
                'market_cap': 'sum',
                'optimized_score': 'mean'
            }).round(2)
            
            action_analysis.columns = ['Count', 'Total_MarketCap', 'Avg_Score']
            action_analysis['Allocation_%'] = (action_analysis['Count'] / len(df) * 100).round(1)
            
            print(action_analysis.to_string())
            print()
        
        # 4. SCORE-BASED ANALYSIS
        print("🏆 SCORE-BASED PORTFOLIO ANALYSIS:")
        print("-" * 45)
        
        # Score distribution
        score_bins = pd.cut(df['optimized_score'], bins=[0, 50, 60, 70, 75, 100], 
                          labels=['Poor (0-50)', 'Below Avg (50-60)', 'Average (60-70)', 
                                 'Good (70-75)', 'Excellent (75+)'])
        
        score_distribution = df.groupby(score_bins).agg({
            'symbol': 'count',
            'market_cap': 'sum',
            'optimized_score': 'mean'
        }).round(2)
        
        score_distribution.columns = ['Count', 'Total_MarketCap', 'Avg_Score']
        score_distribution['Allocation_%'] = (score_distribution['Count'] / len(df) * 100).round(1)
        
        print("📊 Score Distribution:")
        print(score_distribution.to_string())
        print()
        
        # 5. TOP HOLDINGS ANALYSIS
        print("🔝 TOP 15 HOLDINGS BY MARKET CAP:")
        print("-" * 40)
        
        top_holdings = df.nlargest(15, 'market_cap')[['symbol', 'company_name', 'sector', 
                                                     'optimized_score', 'market_cap', 'action']]
        top_holdings['market_cap_cr'] = (top_holdings['market_cap'] / 10000000000).round(2)  # Convert to Cr
        
        print(top_holdings[['symbol', 'sector', 'optimized_score', 'market_cap_cr', 'action']].to_string(index=False))
        print()
        
        # 6. RISK ANALYSIS
        print("⚠️  PORTFOLIO RISK ANALYSIS:")
        print("-" * 35)
        
        # Concentration risk
        top_5_weight = (df.nlargest(5, 'market_cap')['market_cap'].sum() / df['market_cap'].sum() * 100)
        top_10_weight = (df.nlargest(10, 'market_cap')['market_cap'].sum() / df['market_cap'].sum() * 100)
        
        print(f"📊 Concentration Risk:")
        print(f"  • Top 5 holdings: {top_5_weight:.1f}% of portfolio")
        print(f"  • Top 10 holdings: {top_10_weight:.1f}% of portfolio")
        print()
        
        # Sector concentration
        max_sector_weight = sector_analysis['MarketCap_%'].max()
        max_sector = sector_analysis['MarketCap_%'].idxmax()
        
        print(f"📈 Sector Concentration:")
        print(f"  • Largest sector: {max_sector} ({max_sector_weight:.1f}%)")
        if max_sector_weight > 50:
            print(f"  ⚠️  HIGH CONCENTRATION RISK - Consider diversification")
        elif max_sector_weight > 30:
            print(f"  ⚡ MODERATE CONCENTRATION - Monitor sector exposure")
        else:
            print(f"  ✅ GOOD DIVERSIFICATION")
        print()
        
        # Volatility analysis
        high_vol_stocks = df[df['volatility_6m'] > 30]['symbol'].count()
        avg_volatility = df['volatility_6m'].mean()
        
        print(f"📉 Volatility Profile:")
        print(f"  • Average portfolio volatility: {avg_volatility:.1f}%")
        print(f"  • High volatility stocks (>30%): {high_vol_stocks} ({high_vol_stocks/len(df)*100:.1f}%)")
        
        if avg_volatility > 30:
            print(f"  ⚠️  HIGH RISK PORTFOLIO")
        elif avg_volatility > 25:
            print(f"  ⚡ MODERATE RISK PORTFOLIO")
        else:
            print(f"  ✅ LOW-MODERATE RISK PORTFOLIO")
        print()
        
        # 7. RECOMMENDATIONS
        print("💡 PORTFOLIO OPTIMIZATION RECOMMENDATIONS:")
        print("-" * 50)
        
        recommendations = []
        
        # Sector diversification
        if max_sector_weight > 40:
            recommendations.append(f"🔄 Reduce {max_sector} exposure from {max_sector_weight:.1f}% to <40%")
        
        # Score-based recommendations
        poor_performers = df[df['optimized_score'] < 50]['symbol'].count()
        if poor_performers > 0:
            recommendations.append(f"📉 Consider selling {poor_performers} poor performing stocks (score <50)")
        
        # Add high-score stocks
        excellent_stocks = df[df['optimized_score'] > 75]['symbol'].count()
        total_stocks = len(df)
        if excellent_stocks / total_stocks < 0.3:
            recommendations.append(f"📈 Increase allocation to high-score stocks (75+) - currently {excellent_stocks}/{total_stocks}")
        
        # Volatility management
        if high_vol_stocks > len(df) * 0.3:
            recommendations.append(f"⚡ Consider reducing high-volatility positions ({high_vol_stocks} stocks >30% vol)")
        
        # Action-based recommendations
        if 'action' in df.columns:
            increase_count = df[df['action'] == 'INCREASE']['symbol'].count()
            sell_count = df[df['action'] == 'SELL']['symbol'].count()
            
            if increase_count > 0:
                recommendations.append(f"📊 Consider increasing position in {increase_count} recommended stocks")
            if sell_count > 0:
                recommendations.append(f"💰 Consider selling {sell_count} stocks as recommended")
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        else:
            print("  ✅ Portfolio appears well-balanced - no major changes needed")
        
        print()
        
        # 8. SUMMARY METRICS
        print("📊 PORTFOLIO SUMMARY METRICS:")
        print("-" * 40)
        
        total_market_cap = df['market_cap'].sum()
        avg_score = df['optimized_score'].mean()
        score_weighted_avg = (df['optimized_score'] * df['market_cap']).sum() / total_market_cap
        
        print(f"📈 Key Metrics:")
        print(f"  • Total Portfolio Value: ₹{total_market_cap/10000000000:.1f} Lakh Cr")
        print(f"  • Average Score: {avg_score:.1f}")
        print(f"  • Market-Cap Weighted Score: {score_weighted_avg:.1f}")
        print(f"  • Number of Sectors: {df['sector'].nunique()}")
        print(f"  • Portfolio Risk Level: {'High' if avg_volatility > 30 else 'Moderate' if avg_volatility > 25 else 'Low-Moderate'}")
        print()
        
        return df, sector_analysis
        
    except Exception as e:
        print(f"❌ Error analyzing portfolio: {e}")
        return None, None

def generate_allocation_charts(df, sector_analysis):
    """Generate visualization charts for portfolio allocation"""
    
    try:
        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Portfolio Allocation Analysis Dashboard', fontsize=16, fontweight='bold')
        
        # 1. Sector Allocation Pie Chart
        ax1 = axes[0, 0]
        colors = plt.cm.Set3(np.linspace(0, 1, len(sector_analysis)))
        wedges, texts, autotexts = ax1.pie(sector_analysis['Count'], 
                                          labels=sector_analysis.index,
                                          autopct='%1.1f%%',
                                          colors=colors,
                                          startangle=90)
        ax1.set_title('Sector Allocation by Count', fontweight='bold')
        
        # 2. Market Cap Distribution
        ax2 = axes[0, 1]
        sector_analysis_sorted = sector_analysis.sort_values('MarketCap_%', ascending=True)
        bars = ax2.barh(sector_analysis_sorted.index, sector_analysis_sorted['MarketCap_%'])
        ax2.set_title('Sector Allocation by Market Cap (%)', fontweight='bold')
        ax2.set_xlabel('Allocation %')
        
        # Color bars based on allocation percentage
        for i, bar in enumerate(bars):
            if sector_analysis_sorted['MarketCap_%'].iloc[i] > 30:
                bar.set_color('red')
            elif sector_analysis_sorted['MarketCap_%'].iloc[i] > 20:
                bar.set_color('orange')
            else:
                bar.set_color('green')
        
        # 3. Score Distribution
        ax3 = axes[1, 0]
        score_bins = pd.cut(df['optimized_score'], bins=[0, 50, 60, 70, 75, 100])
        score_counts = score_bins.value_counts().sort_index()
        bars3 = ax3.bar(range(len(score_counts)), score_counts.values)
        ax3.set_title('Score Distribution', fontweight='bold')
        ax3.set_xlabel('Score Range')
        ax3.set_ylabel('Number of Stocks')
        ax3.set_xticks(range(len(score_counts)))
        ax3.set_xticklabels(['0-50', '50-60', '60-70', '70-75', '75+'])
        
        # Color bars based on score quality
        colors_score = ['red', 'orange', 'yellow', 'lightgreen', 'green']
        for bar, color in zip(bars3, colors_score):
            bar.set_color(color)
        
        # 4. Volatility vs Score Scatter
        ax4 = axes[1, 1]
        scatter = ax4.scatter(df['volatility_6m'], df['optimized_score'], 
                             s=df['market_cap']/1e10, alpha=0.6, c=df['optimized_score'], 
                             cmap='RdYlGn', edgecolors='black', linewidth=0.5)
        ax4.set_xlabel('Volatility (6M %)')
        ax4.set_ylabel('Optimized Score')
        ax4.set_title('Risk vs Score (Size = Market Cap)', fontweight='bold')
        
        # Add colorbar
        plt.colorbar(scatter, ax=ax4, label='Score')
        
        # Add quadrant lines
        ax4.axhline(y=70, color='red', linestyle='--', alpha=0.5, label='Score=70')
        ax4.axvline(x=25, color='red', linestyle='--', alpha=0.5, label='Vol=25%')
        
        plt.tight_layout()
        
        # Save the plot
        chart_filename = f"portfolio_allocation_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
        print(f"📊 Charts saved as: {chart_filename}")
        
        plt.show()
        
    except Exception as e:
        print(f"❌ Error generating charts: {e}")

if __name__ == "__main__":
    df, sector_analysis = analyze_portfolio_allocation()
    
    if df is not None and sector_analysis is not None:
        print("\n🎨 Generating visualization charts...")
        generate_allocation_charts(df, sector_analysis)
        print("\n✅ Portfolio allocation analysis completed!")
    else:
        print("❌ Analysis failed - check data availability")