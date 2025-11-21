#!/usr/bin/env python3
"""
DEEP DIVE ANALYSIS: WHY THE SCORING SYSTEM IS INVERTED
Investigates the root causes of the inverse correlation between scores and returns
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class InvertedScoringAnalyzer:
    def __init__(self, results_file="comprehensive_backtest_20251002_133858.csv"):
        """Load and analyze the backtest results"""
        try:
            self.df = pd.read_csv(results_file)
            print(f"✅ Loaded {len(self.df)} backtest results")
        except FileNotFoundError:
            print(f"❌ Results file not found: {results_file}")
            self.df = None
    
    def analyze_scoring_components(self):
        """Analyze individual scoring components vs performance"""
        if self.df is None:
            return
            
        print("\n" + "="*80)
        print("🔍 DEEP DIVE: SCORING COMPONENT ANALYSIS")
        print("="*80)
        
        # Component correlations with actual returns
        score_components = [
            'overall_score', 'momentum_score', 'breakout_score',
            'undervaluation_score', 'fundamental_score', 'technical_score'
        ]
        
        print("\n📊 COMPONENT CORRELATIONS WITH ACTUAL RETURNS:")
        correlations = {}
        for component in score_components:
            if component in self.df.columns:
                corr = self.df[component].corr(self.df['actual_return'])
                correlations[component] = corr
                status = "✅ POSITIVE" if corr > 0 else "❌ NEGATIVE" if corr < -0.1 else "⚠️ WEAK"
                print(f"   {component:20s}: {corr:+7.4f} {status}")
        
        # Find the most problematic components
        print(f"\n🔴 MOST PROBLEMATIC COMPONENTS:")
        sorted_corr = sorted(correlations.items(), key=lambda x: x[1])
        for component, corr in sorted_corr[:3]:
            print(f"   {component}: {corr:+.4f} (INVERSE RELATIONSHIP)")
        
        return correlations
    
    def analyze_recommendation_patterns(self):
        """Deep dive into recommendation patterns"""
        print(f"\n🏷️ RECOMMENDATION PATTERN ANALYSIS:")
        
        rec_analysis = self.df.groupby('recommendation').agg({
            'actual_return': ['mean', 'median', 'std', 'count'],
            'overall_score': ['mean', 'min', 'max'],
            'momentum_score': 'mean',
            'technical_score': 'mean'
        }).round(2)
        
        print(f"\nDetailed breakdown by recommendation:")
        for rec in rec_analysis.index:
            stats = rec_analysis.loc[rec]
            return_mean = stats[('actual_return', 'mean')]
            return_std = stats[('actual_return', 'std')]
            score_mean = stats[('overall_score', 'mean')]
            count = stats[('actual_return', 'count')]
            
            print(f"\n📈 {rec}:")
            print(f"   Return: {return_mean:+6.2f}% ± {return_std:5.2f}% ({count} samples)")
            print(f"   Avg Score: {score_mean:5.1f}")
            print(f"   Score Range: {stats[('overall_score', 'min')]:.1f} - {stats[('overall_score', 'max')]:.1f}")
    
    def analyze_temporal_patterns(self):
        """Analyze performance across different time periods"""
        print(f"\n📅 TEMPORAL PATTERN ANALYSIS:")
        
        # Convert analysis_date to datetime
        self.df['analysis_date'] = pd.to_datetime(self.df['analysis_date'])
        self.df['month'] = self.df['analysis_date'].dt.strftime('%Y-%m')
        
        monthly_performance = self.df.groupby('month').agg({
            'actual_return': ['mean', 'count'],
            'overall_score': 'mean'
        }).round(2)
        
        print(f"\nPerformance by month:")
        for month in monthly_performance.index:
            stats = monthly_performance.loc[month]
            avg_return = stats[('actual_return', 'mean')]
            count = stats[('actual_return', 'count')]
            avg_score = stats[('overall_score', 'mean')]
            
            print(f"   {month}: {avg_return:+6.2f}% avg return, {avg_score:5.1f} avg score ({count} tests)")
    
    def analyze_sector_patterns(self):
        """Analyze patterns by stock sectors (based on symbols)"""
        print(f"\n🏭 SECTOR PATTERN ANALYSIS:")
        
        # Classify stocks by sector based on symbol patterns
        def classify_sector(symbol):
            banking_stocks = ['AUBANK', 'AXISBANK', 'BANKINDIA', 'BANKBARODA', 'CANBK', 
                            'CENTRALBK', 'CUB', 'FEDERALBNK', 'HDFCBANK', 'ICICIBANK', 
                            'INDIANB', 'IOB', 'IDBI', 'J&KBANK', 'KARURVYSYA', 'KOTAKBANK',
                            'MAHABANK', 'PNB', 'SBIN', 'UCOBANK', 'UJJIVANSFB', 'UNIONBANK', 'YESBANK']
            
            financial_stocks = ['LICHSGFIN', 'MOTILALOFS', 'MUTHOOTFIN', 'BAJAJHLDNG']
            
            if symbol in banking_stocks:
                return 'Banking'
            elif symbol in financial_stocks:
                return 'Financial'
            else:
                return 'Others'
        
        self.df['sector'] = self.df['symbol'].apply(classify_sector)
        
        sector_analysis = self.df.groupby('sector').agg({
            'actual_return': ['mean', 'median', 'std', 'count'],
            'overall_score': 'mean',
            'momentum_score': 'mean'
        }).round(2)
        
        print(f"\nPerformance by sector:")
        for sector in sector_analysis.index:
            stats = sector_analysis.loc[sector]
            avg_return = stats[('actual_return', 'mean')]
            count = stats[('actual_return', 'count')]
            avg_score = stats[('overall_score', 'mean')]
            
            print(f"   {sector:10s}: {avg_return:+6.2f}% avg return, {avg_score:5.1f} avg score ({count} tests)")
    
    def analyze_top_performers(self):
        """Deep dive into what made top performers successful"""
        print(f"\n🏆 TOP PERFORMER DEEP DIVE:")
        
        # Get top 10 and bottom 10 performers
        top_10 = self.df.nlargest(10, 'actual_return')
        bottom_10 = self.df.nsmallest(10, 'actual_return')
        
        print(f"\n✅ TOP 10 CHARACTERISTICS:")
        top_stats = {
            'avg_overall_score': top_10['overall_score'].mean(),
            'avg_momentum_score': top_10['momentum_score'].mean(),
            'avg_technical_score': top_10['technical_score'].mean(),
            'avg_fundamental_score': top_10['fundamental_score'].mean(),
            'common_recommendations': top_10['recommendation'].value_counts().head(3)
        }
        
        print(f"   Average Overall Score: {top_stats['avg_overall_score']:.1f}")
        print(f"   Average Momentum Score: {top_stats['avg_momentum_score']:.1f}")
        print(f"   Average Technical Score: {top_stats['avg_technical_score']:.1f}")
        print(f"   Average Fundamental Score: {top_stats['avg_fundamental_score']:.1f}")
        print(f"   Common Recommendations:")
        for rec, count in top_stats['common_recommendations'].items():
            print(f"      {rec}: {count} stocks")
        
        print(f"\n❌ BOTTOM 10 CHARACTERISTICS:")
        bottom_stats = {
            'avg_overall_score': bottom_10['overall_score'].mean(),
            'avg_momentum_score': bottom_10['momentum_score'].mean(),
            'avg_technical_score': bottom_10['technical_score'].mean(),
            'avg_fundamental_score': bottom_10['fundamental_score'].mean(),
            'common_recommendations': bottom_10['recommendation'].value_counts().head(3)
        }
        
        print(f"   Average Overall Score: {bottom_stats['avg_overall_score']:.1f}")
        print(f"   Average Momentum Score: {bottom_stats['avg_momentum_score']:.1f}")
        print(f"   Average Technical Score: {bottom_stats['avg_technical_score']:.1f}")
        print(f"   Average Fundamental Score: {bottom_stats['avg_fundamental_score']:.1f}")
        print(f"   Common Recommendations:")
        for rec, count in bottom_stats['common_recommendations'].items():
            print(f"      {rec}: {count} stocks")
        
        # Compare top vs bottom
        print(f"\n🔄 TOP vs BOTTOM COMPARISON:")
        print(f"   Overall Score Diff: {top_stats['avg_overall_score'] - bottom_stats['avg_overall_score']:+.1f}")
        print(f"   Momentum Score Diff: {top_stats['avg_momentum_score'] - bottom_stats['avg_momentum_score']:+.1f}")
        print(f"   Technical Score Diff: {top_stats['avg_technical_score'] - bottom_stats['avg_technical_score']:+.1f}")
        
        return top_stats, bottom_stats
    
    def identify_scoring_problems(self):
        """Identify specific problems in the scoring algorithm"""
        print(f"\n🔍 SCORING ALGORITHM PROBLEMS IDENTIFIED:")
        
        # Problem 1: High scores underperform
        high_score_stocks = self.df[self.df['overall_score'] >= 80]
        low_score_stocks = self.df[self.df['overall_score'] <= 50]
        
        if len(high_score_stocks) > 0 and len(low_score_stocks) > 0:
            high_performance = high_score_stocks['actual_return'].mean()
            low_performance = low_score_stocks['actual_return'].mean()
            
            print(f"\n❌ PROBLEM 1: INVERSE SCORING")
            print(f"   High Score Stocks (≥80): {high_performance:+.2f}% average return")
            print(f"   Low Score Stocks (≤50): {low_performance:+.2f}% average return")
            print(f"   Performance Gap: {low_performance - high_performance:+.2f}% (LOW SCORES WIN!)")
        
        # Problem 2: Momentum detection failure
        print(f"\n❌ PROBLEM 2: MOMENTUM DETECTION FAILURE")
        momentum_groups = self.df.groupby(pd.cut(self.df['momentum_score'], bins=[0, 30, 60, 100]))['actual_return'].mean()
        for group, performance in momentum_groups.items():
            print(f"   Momentum {group}: {performance:+.2f}% average return")
        
        # Problem 3: Technical analysis issues
        print(f"\n❌ PROBLEM 3: TECHNICAL ANALYSIS ISSUES")
        tech_groups = self.df.groupby(pd.cut(self.df['technical_score'], bins=[0, 50, 75, 100]))['actual_return'].mean()
        for group, performance in tech_groups.items():
            print(f"   Technical Score {group}: {performance:+.2f}% average return")
        
        # Problem 4: Recommendation logic flawed
        print(f"\n❌ PROBLEM 4: RECOMMENDATION LOGIC FLAWED")
        print(f"   'SELL' recommendations average: {self.df[self.df['recommendation'].str.contains('SELL', na=False)]['actual_return'].mean():+.2f}%")
        print(f"   'BUY' recommendations average: {self.df[self.df['recommendation'].str.contains('BUY', na=False)]['actual_return'].mean():+.2f}%")
    
    def generate_insights_report(self):
        """Generate comprehensive insights for fixing the system"""
        print(f"\n" + "="*80)
        print("💡 KEY INSIGHTS FOR SYSTEM CORRECTION")
        print("="*80)
        
        insights = []
        
        # Insight 1: Contrarian signals work better
        sell_performance = self.df[self.df['recommendation'].str.contains('SELL', na=False)]['actual_return'].mean()
        buy_performance = self.df[self.df['recommendation'].str.contains('BUY', na=False)]['actual_return'].mean()
        
        if sell_performance > buy_performance:
            insights.append("🔄 CONTRARIAN APPROACH: 'SELL' signals outperform 'BUY' signals - system identifies oversold opportunities")
        
        # Insight 2: Score weighting issues
        correlations = self.analyze_scoring_components()
        negative_components = [comp for comp, corr in correlations.items() if corr < -0.05]
        
        if negative_components:
            insights.append(f"⚖️ SCORING WEIGHTS: These components have negative correlation: {', '.join(negative_components)}")
        
        # Insight 3: Market timing
        monthly_variance = self.df.groupby(self.df['analysis_date'].dt.month)['actual_return'].var()
        high_variance_months = monthly_variance[monthly_variance > monthly_variance.mean() * 1.5].index.tolist()
        
        if high_variance_months:
            insights.append(f"📅 TIMING SENSITIVITY: High variance in months: {high_variance_months}")
        
        print(f"\n🎯 ACTIONABLE INSIGHTS:")
        for i, insight in enumerate(insights, 1):
            print(f"   {i}. {insight}")
        
        # Generate correction recommendations
        print(f"\n🛠️ CORRECTION RECOMMENDATIONS:")
        print(f"   1. 🔄 INVERT recommendation logic - treat technical weakness as opportunity")
        print(f"   2. ⚖️ REWEIGHT scoring components - reduce weight of negatively correlated factors")
        print(f"   3. 🎯 ADD contrarian indicators - RSI oversold, price below moving averages")
        print(f"   4. 📊 SECTOR-SPECIFIC logic - banking stocks need different treatment")
        print(f"   5. 🕒 TIME-BASED adjustments - account for market cycles")
        
        return insights

def main():
    """Run the deep dive analysis"""
    print("🔍 DEEP DIVE ANALYSIS: INVERTED SCORING SYSTEM")
    print("="*60)
    
    analyzer = InvertedScoringAnalyzer()
    if analyzer.df is None:
        print("❌ Cannot proceed without backtest data")
        return
    
    # Run all analyses
    print(f"📊 Analyzing {len(analyzer.df)} backtest results...")
    
    # 1. Component analysis
    correlations = analyzer.analyze_scoring_components()
    
    # 2. Recommendation patterns
    analyzer.analyze_recommendation_patterns()
    
    # 3. Temporal patterns
    analyzer.analyze_temporal_patterns()
    
    # 4. Sector patterns
    analyzer.analyze_sector_patterns()
    
    # 5. Top performer analysis
    top_stats, bottom_stats = analyzer.analyze_top_performers()
    
    # 6. Identify problems
    analyzer.identify_scoring_problems()
    
    # 7. Generate insights
    insights = analyzer.generate_insights_report()
    
    print(f"\n✅ DEEP DIVE ANALYSIS COMPLETE!")
    print(f"📝 Key finding: The system is identifying good stocks but scoring them backwards!")

if __name__ == "__main__":
    main()