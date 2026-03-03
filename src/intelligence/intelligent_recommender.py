"""
Smart Recommendation Engine - Uses YOUR historical data to personalize recommendations
This is Phase 2: Context Awareness
"""
import sqlite3
import pandas as pd
from typing import Dict, List, Tuple

class IntelligentRecommender:
    def __init__(self, db_path: str = "data/intelligence.db"):
        self.db_path = db_path
    
    def enhance_recommendation(self, symbol: str, base_action: str, base_score: float, 
                               sector: str, current_price: float) -> Dict:
        """
        Takes a base recommendation and enhances it with YOUR historical intelligence
        
        Returns:
            {
                'action': 'BUY',  # May be adjusted based on your patterns
                'score': 72.5,  # May be boosted/reduced
                'confidence': 'HIGH',
                'ai_insights': [list of personalized insights],
                'warnings': [list of warnings based on your history]
            }
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        insights = []
        warnings = []
        score_adjustment = 0
        confidence = "MEDIUM"
        
        # 1. Check YOUR history with this specific stock
        stock_history = pd.read_sql(f"""
            SELECT 
                COUNT(*) as times_seen,
                SUM(CASE WHEN user_owns_it = 1 THEN 1 ELSE 0 END) as times_owned,
                AVG(CASE WHEN user_owns_it = 1 THEN my_profit_pct ELSE NULL END) as your_avg_profit,
                SUM(CASE WHEN followed_recommendation = 0 THEN 1 ELSE 0 END) as times_ignored
            FROM user_portfolio
            WHERE symbol = '{symbol}'
        """, conn).iloc[0]
        
        if stock_history['times_seen'] > 0:
            follow_rate = (stock_history['times_owned'] / stock_history['times_seen']) * 100
            
            if stock_history['times_ignored'] >= 3:
                warnings.append(f"⚠️ You ignored {symbol} {int(stock_history['times_ignored'])} times before")
                score_adjustment -= 5
            
            if stock_history['your_avg_profit'] is not None:
                profit = stock_history['your_avg_profit']
                if profit > 0.15:
                    insights.append(f"💰 {symbol}: You made +{profit:.2f}% avg profit (winner for you!)")
                    score_adjustment += 10
                    confidence = "HIGH"
                elif profit < -0.05:
                    warnings.append(f"📉 {symbol}: Your avg loss: {profit:.2f}% (avoid?)")
                    score_adjustment -= 10
        
        # 2. Check YOUR sector performance
        sector_history = pd.read_sql(f"""
            SELECT 
                COUNT(*) as sector_recs,
                SUM(CASE WHEN followed_recommendation = 1 THEN 1 ELSE 0 END) as sector_followed,
                AVG(CASE WHEN user_owns_it = 1 THEN my_profit_pct ELSE NULL END) as sector_profit,
                SUM(CASE WHEN followed_recommendation = 0 THEN 1 ELSE 0 END) as sector_ignored
            FROM user_portfolio
            WHERE sector = '{sector}'
        """, conn).iloc[0]
        
        if sector_history['sector_recs'] > 10:  # Need meaningful data
            sector_follow_rate = (sector_history['sector_followed'] / sector_history['sector_recs']) * 100
            
            if sector_follow_rate < 50:
                warnings.append(f"⚠️ {sector}: You only follow {sector_follow_rate:.0f}% of recommendations here")
            
            if sector_history['sector_profit'] is not None:
                profit = sector_history['sector_profit']
                if profit > 0.20:
                    insights.append(f"🎯 {sector} is YOUR BEST sector (+{profit:.2f}% avg)")
                    score_adjustment += 8
                    confidence = "HIGH"
                elif profit < 0:
                    warnings.append(f"📊 {sector}: You're losing {profit:.2f}% avg in this sector")
                    score_adjustment -= 5
        
        # 3. Check similar past recommendations (same action, similar score range)
        similar_recs = pd.read_sql(f"""
            SELECT 
                COUNT(*) as similar_count,
                AVG(CASE WHEN followed_recommendation = 1 THEN my_profit_pct ELSE NULL END) as similar_profit
            FROM user_portfolio
            WHERE system_action = '{base_action}'
              AND system_score BETWEEN {base_score - 10} AND {base_score + 10}
              AND user_owns_it = 1
        """, conn).iloc[0]
        
        if similar_recs['similar_count'] >= 5 and similar_recs['similar_profit'] is not None:
            profit = similar_recs['similar_profit']
            if profit > 0.10:
                insights.append(f"📈 {base_action} recommendations at ~{base_score:.0f} score: You made +{profit:.2f}% avg")
                confidence = "HIGH"
            elif profit < 0:
                warnings.append(f"⚠️ Similar {base_action} recommendations lost you {profit:.2f}% avg")
                score_adjustment -= 5
        
        # 4. Behavioral patterns
        overall_behavior = pd.read_sql("""
            SELECT 
                SUM(CASE WHEN followed_recommendation = 1 THEN 1 ELSE 0 END) as total_followed,
                COUNT(*) as total_recs,
                AVG(CASE WHEN followed_recommendation = 1 THEN my_profit_pct ELSE NULL END) as profit_when_followed,
                AVG(CASE WHEN followed_recommendation = 0 THEN my_profit_pct ELSE NULL END) as profit_when_ignored
            FROM user_portfolio
        """, conn).iloc[0]
        
        follow_rate = (overall_behavior['total_followed'] / overall_behavior['total_recs']) * 100
        
        if follow_rate > 85:
            insights.append(f"✅ You're disciplined ({follow_rate:.0f}% follow rate)")
        
        if overall_behavior['profit_when_followed'] > overall_behavior['profit_when_ignored']:
            diff = overall_behavior['profit_when_followed'] - overall_behavior['profit_when_ignored']
            insights.append(f"💡 Following system = +{diff:.2f}% better profit for you")
        
        conn.close()
        
        # Adjust final score
        adjusted_score = max(0, min(100, base_score + score_adjustment))
        
        # Adjust confidence
        if abs(score_adjustment) >= 15:
            confidence = "HIGH" if score_adjustment > 0 else "LOW"
        
        return {
            'original_action': base_action,
            'original_score': base_score,
            'enhanced_action': base_action,  # Could change based on strong signals
            'enhanced_score': adjusted_score,
            'score_adjustment': score_adjustment,
            'confidence': confidence,
            'ai_insights': insights,
            'warnings': warnings,
            'personalized': len(insights) + len(warnings) > 0
        }
    
    def get_portfolio_insights(self) -> List[str]:
        """Get high-level insights about YOUR portfolio behavior"""
        conn = sqlite3.connect(self.db_path)
        
        insights = []
        
        # Best and worst sectors
        sector_performance = pd.read_sql("""
            SELECT 
                sector,
                COUNT(*) as count,
                AVG(CASE WHEN user_owns_it = 1 THEN my_profit_pct ELSE NULL END) as avg_profit
            FROM user_portfolio
            WHERE user_owns_it = 1
            GROUP BY sector
            HAVING count >= 10
            ORDER BY avg_profit DESC
        """, conn)
        
        if len(sector_performance) > 0:
            best = sector_performance.iloc[0]
            insights.append(f"🏆 YOUR BEST SECTOR: {best['sector']} (+{best['avg_profit']:.2f}% avg)")
            
            worst = sector_performance.iloc[-1]
            if worst['avg_profit'] < 0:
                insights.append(f"⚠️ YOUR WORST SECTOR: {worst['sector']} ({worst['avg_profit']:.2f}% avg loss)")
        
        # Stocks you keep ignoring
        ignored_stocks = pd.read_sql("""
            SELECT 
                symbol,
                sector,
                COUNT(*) as ignore_count,
                AVG(system_score) as avg_score
            FROM user_portfolio
            WHERE followed_recommendation = 0
            GROUP BY symbol
            HAVING ignore_count >= 3
            ORDER BY ignore_count DESC
            LIMIT 5
        """, conn)
        
        if len(ignored_stocks) > 0:
            insights.append(f"\n📋 STOCKS YOU CONSISTENTLY IGNORE:")
            for _, stock in ignored_stocks.iterrows():
                insights.append(f"   • {stock['symbol']} ({stock['sector']}): Ignored {int(stock['ignore_count'])} times (avg score {stock['avg_score']:.0f})")
        
        # Follow rate by action type
        action_behavior = pd.read_sql("""
            SELECT 
                system_action,
                COUNT(*) as total,
                SUM(CASE WHEN followed_recommendation = 1 THEN 1 ELSE 0 END) as followed
            FROM user_portfolio
            GROUP BY system_action
        """, conn)
        
        if len(action_behavior) > 0:
            insights.append(f"\n🎯 YOUR FOLLOW RATES BY ACTION:")
            for _, row in action_behavior.iterrows():
                rate = (row['followed'] / row['total']) * 100
                insights.append(f"   • {row['system_action']}: {rate:.0f}% ({int(row['followed'])}/{int(row['total'])})")
        
        conn.close()
        return insights


def test_intelligent_recommender():
    """Test the intelligent recommender with some stocks from current portfolio"""
    recommender = IntelligentRecommender()
    
    print("="*70)
    print("INTELLIGENT RECOMMENDATION ENGINE - DEMO")
    print("="*70)
    
    # Test stocks (mix of ones user owns and new ones)
    test_stocks = [
        ("AXISBANK", "BUY", 75.5, "Financial Services", 1387),
        ("INFY", "SELL", 45.2, "Technology", 1276),
        ("COALINDIA", "SELL", 42.8, "Energy", 431),
        ("SBIN", "BUY", 82.3, "Financial Services", 1224),
    ]
    
    print("\n📊 ENHANCED RECOMMENDATIONS (Using YOUR 2-month history):\n")
    
    for symbol, action, score, sector, price in test_stocks:
        result = recommender.enhance_recommendation(symbol, action, score, sector, price)
        
        print(f"{'='*70}")
        print(f"🏢 {symbol} ({sector}) - ₹{price}")
        print(f"{'='*70}")
        print(f"Base Recommendation: {result['original_action']} | Score: {result['original_score']:.1f}")
        
        if result['score_adjustment'] != 0:
            arrow = "↑" if result['score_adjustment'] > 0 else "↓"
            print(f"AI-Enhanced: {result['enhanced_action']} | Score: {result['enhanced_score']:.1f} {arrow} ({result['score_adjustment']:+.1f})")
        else:
            print(f"AI-Enhanced: {result['enhanced_action']} | Score: {result['enhanced_score']:.1f} (no change)")
        
        print(f"Confidence: {result['confidence']}")
        
        if result['ai_insights']:
            print(f"\n💡 Insights:")
            for insight in result['ai_insights']:
                print(f"   {insight}")
        
        if result['warnings']:
            print(f"\n⚠️ Warnings:")
            for warning in result['warnings']:
                print(f"   {warning}")
        
        print()
    
    # Portfolio-level insights
    print("\n" + "="*70)
    print("📈 YOUR OVERALL PORTFOLIO INTELLIGENCE")
    print("="*70)
    
    portfolio_insights = recommender.get_portfolio_insights()
    for insight in portfolio_insights:
        print(insight)
    
    print("\n" + "="*70)
    print("NEXT STEP: Integrate this into analyze_top200_stocks_enhanced.py")
    print("="*70)


if __name__ == "__main__":
    test_intelligent_recommender()
