"""
News & Sentiment Analysis Module for Stock Analysis
Phase 2 - Task 7

This module analyzes:
1. Financial news sentiment (simulated from price action and volume)
2. Analyst ratings and target price consensus
3. Market sentiment indicators (RSI, volume trends)
4. Earnings sentiment (based on EPS surprises)
5. Social media buzz indicators (volume spikes, volatility)

Note: Uses free data sources and technical proxies for sentiment.
Can be extended with premium APIs (NewsAPI, AlphaVantage, Twitter API, etc.)
"""

import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime, timedelta

class SentimentAnalyzer:
    """
    Analyze stock sentiment from multiple sources
    """
    
    def __init__(self):
        """Initialize the sentiment analyzer"""
        self.logger = logging.getLogger(__name__)
        
    def analyze_sentiment(self, symbol: str, stock_data: Dict) -> Dict:
        """
        Comprehensive sentiment analysis combining multiple signals
        
        Args:
            symbol: Stock ticker symbol
            stock_data: Dictionary with stock information
            
        Returns:
            Dict with sentiment scores and signals
        """
        try:
            ticker = yf.Ticker(f"{symbol}.NS")

            # Reuse existing hist from stock_data bundle if available
            hist = stock_data.get('_hist_3mo') if isinstance(stock_data.get('_hist_3mo'), pd.DataFrame) else None
            if hist is None or hist.empty:
                hist = ticker.history(period="3mo")

            if hist.empty:
                return self._get_default_sentiment()
            
            # Calculate sentiment components
            news_sentiment = self._analyze_news_sentiment(hist, stock_data)
            analyst_sentiment = self._analyze_analyst_sentiment(ticker, stock_data)
            market_sentiment = self._analyze_market_sentiment(hist, stock_data)
            earnings_sentiment = self._analyze_earnings_sentiment(ticker, stock_data)
            buzz_sentiment = self._analyze_social_buzz(hist, stock_data)
            
            # Calculate composite sentiment score (0-100)
            composite_score = (
                news_sentiment['score'] * 0.30 +      # 30% weight to news
                analyst_sentiment['score'] * 0.25 +   # 25% weight to analysts
                market_sentiment['score'] * 0.20 +    # 20% weight to market
                earnings_sentiment['score'] * 0.15 +  # 15% weight to earnings
                buzz_sentiment['score'] * 0.10        # 10% weight to buzz
            )
            
            # Determine overall sentiment
            if composite_score >= 70:
                overall_sentiment = "VERY_POSITIVE"
                sentiment_signal = "STRONG_BUY"
            elif composite_score >= 60:
                overall_sentiment = "POSITIVE"
                sentiment_signal = "BUY"
            elif composite_score >= 40:
                overall_sentiment = "NEUTRAL"
                sentiment_signal = "HOLD"
            elif composite_score >= 30:
                overall_sentiment = "NEGATIVE"
                sentiment_signal = "SELL"
            else:
                overall_sentiment = "VERY_NEGATIVE"
                sentiment_signal = "STRONG_SELL"
            
            # Calculate confidence based on signal agreement
            confidence = self._calculate_confidence([
                news_sentiment['signal'],
                analyst_sentiment['signal'],
                market_sentiment['signal'],
                earnings_sentiment['signal'],
                buzz_sentiment['signal']
            ])
            
            return {
                'sentiment_composite_score': composite_score,  # A-012: renamed from 'composite_score'
                'composite_score': composite_score,            # A-012: kept as alias for backward compat
                'overall_sentiment': overall_sentiment,
                'sentiment_signal': sentiment_signal,
                'confidence': confidence,
                'news_sentiment': news_sentiment,
                'analyst_sentiment': analyst_sentiment,
                'market_sentiment': market_sentiment,
                'earnings_sentiment': earnings_sentiment,
                'buzz_sentiment': buzz_sentiment,
                'sentiment_strength': self._get_strength(composite_score)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment for {symbol}: {e}")
            return self._get_default_sentiment()
    
    def _analyze_news_sentiment(self, hist: pd.DataFrame, stock_data: Dict) -> Dict:
        """
        Analyze news sentiment from price action and volume patterns
        (Proxy for actual news sentiment in absence of news APIs)
        """
        # Use price momentum as proxy for news sentiment
        returns = hist['Close'].pct_change()
        recent_returns = returns.tail(20)
        
        # Positive news typically causes sustained upward movement
        positive_days = (recent_returns > 0.01).sum()
        negative_days = (recent_returns < -0.01).sum()
        
        # Volume spikes often accompany news
        avg_volume = hist['Volume'].mean()
        recent_volume = hist['Volume'].tail(5).mean()
        volume_surge = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Calculate news sentiment score
        momentum_score = (positive_days - negative_days) / 20 * 100
        volume_score = min(volume_surge * 20, 30)  # Cap at 30
        
        news_score = np.clip(50 + momentum_score + volume_score, 0, 100)
        
        # Determine signal
        if news_score >= 65:
            signal = "POSITIVE"
        elif news_score >= 35:
            signal = "NEUTRAL"
        else:
            signal = "NEGATIVE"
        
        return {
            'score': news_score,
            'signal': signal,
            'positive_days': int(positive_days),
            'negative_days': int(negative_days),
            'volume_surge': volume_surge,
            'description': f"{signal} news sentiment (momentum-based)"
        }
    
    def _analyze_analyst_sentiment(self, ticker: yf.Ticker, stock_data: Dict) -> Dict:
        """
        Analyze analyst recommendations and target prices
        """
        try:
            # Get analyst recommendations
            recommendations = ticker.recommendations
            
            if recommendations is not None and not recommendations.empty:
                recent_recs = recommendations.tail(10)
                
                # Count recommendations
                _grade_col = 'To Grade' if 'To Grade' in recent_recs.columns else ('ToGrade' if 'ToGrade' in recent_recs.columns else None)
                if _grade_col is None:
                    return {'score': 50, 'signal': 'NEUTRAL', 'count': 0, 'buy_pct': 0}
                buy_count = recent_recs[_grade_col].str.contains('Buy|Outperform', case=False, na=False).sum()
                sell_count = recent_recs[_grade_col].str.contains('Sell|Underperform', case=False, na=False).sum()
                hold_count = recent_recs[_grade_col].str.contains('Hold|Neutral', case=False, na=False).sum()
                
                total = buy_count + sell_count + hold_count
                
                if total > 0:
                    # Calculate score based on recommendations
                    analyst_score = ((buy_count * 100 + hold_count * 50) / total)
                    
                    if analyst_score >= 70:
                        signal = "BULLISH"
                    elif analyst_score >= 40:
                        signal = "NEUTRAL"
                    else:
                        signal = "BEARISH"
                    
                    return {
                        'score': analyst_score,
                        'signal': signal,
                        'buy_count': int(buy_count),
                        'hold_count': int(hold_count),
                        'sell_count': int(sell_count),
                        'total_recommendations': int(total),
                        'description': f"{buy_count}B/{hold_count}H/{sell_count}S"
                    }
            
            # Fallback to PE-based analyst proxy
            pe_ratio = stock_data.get('pe_ratio', 20)
            
            if pe_ratio < 15:
                analyst_score = 65  # Undervalued = positive sentiment
                signal = "BULLISH"
            elif pe_ratio < 25:
                analyst_score = 50
                signal = "NEUTRAL"
            else:
                analyst_score = 35  # Overvalued = negative sentiment
                signal = "BEARISH"
            
            return {
                'score': analyst_score,
                'signal': signal,
                'buy_count': 0,
                'hold_count': 0,
                'sell_count': 0,
                'total_recommendations': 0,
                'description': f"PE-based proxy ({signal})"
            }
            
        except Exception as e:
            self.logger.debug(f"Analyst data not available: {e}")
            return {
                'score': 50,
                'signal': "NEUTRAL",
                'buy_count': 0,
                'hold_count': 0,
                'sell_count': 0,
                'total_recommendations': 0,
                'description': "No analyst data"
            }
    
    def _analyze_market_sentiment(self, hist: pd.DataFrame, stock_data: Dict) -> Dict:
        """
        Analyze overall market sentiment from technical indicators
        """
        # RSI-based sentiment (NaN guard: np.nan is not None, would leak into market_score)
        _rsi = stock_data.get('real_rsi')
        _ersi = stock_data.get('enhanced_rsi_14')
        rsi = 50.0
        for v in (_rsi, _ersi):
            if v is not None and not (isinstance(v, (int, float)) and np.isnan(v)):
                try:
                    rsi = float(v)
                    break
                except (TypeError, ValueError):
                    pass
        
        # Volume trend
        recent_volume = hist['Volume'].tail(10).mean()
        older_volume = hist['Volume'].tail(30).mean()
        volume_trend = recent_volume / older_volume if older_volume > 0 else 1.0
        
        # Price trend
        ma_20 = hist['Close'].rolling(20).mean().iloc[-1]
        current_price = hist['Close'].iloc[-1]
        price_vs_ma = (current_price - ma_20) / ma_20 * 100 if ma_20 > 0 else 0
        
        # Calculate market sentiment score
        rsi_component = rsi  # Already 0-100
        volume_component = min(volume_trend * 50, 100)
        trend_component = np.clip(50 + price_vs_ma * 2, 0, 100)
        
        market_score = (rsi_component * 0.4 + volume_component * 0.3 + trend_component * 0.3)
        
        # Determine signal
        if market_score >= 65:
            signal = "BULLISH"
            description = "Strong buying momentum"
        elif market_score >= 35:
            signal = "NEUTRAL"
            description = "Balanced market sentiment"
        else:
            signal = "BEARISH"
            description = "Weak market sentiment"
        
        return {
            'score': market_score,
            'signal': signal,
            'rsi': rsi,
            'volume_trend': volume_trend,
            'price_vs_ma20': price_vs_ma,
            'description': description
        }
    
    def _analyze_earnings_sentiment(self, ticker: yf.Ticker, stock_data: Dict) -> Dict:
        """
        Analyze sentiment from earnings reports and surprises
        """
        try:
            # Get earnings data
            earnings = ticker.earnings
            
            _earn_col = None
            if earnings is not None and not earnings.empty:
                _earn_col = 'Earnings' if 'Earnings' in earnings.columns else ('earnings' if 'earnings' in earnings.columns else (earnings.columns[0] if len(earnings.columns) > 0 else None))
            if _earn_col is not None and len(earnings) >= 2:
                # Check earnings growth
                if len(earnings) >= 2:
                    recent_earnings = earnings[_earn_col].iloc[-1]
                    previous_earnings = earnings[_earn_col].iloc[-2]
                    
                    if previous_earnings != 0 and not (isinstance(previous_earnings, float) and np.isnan(previous_earnings)):
                        earnings_growth = (recent_earnings - previous_earnings) / abs(previous_earnings) * 100
                        
                        # Score based on earnings growth
                        if earnings_growth > 20:
                            earnings_score = 80
                            signal = "VERY_POSITIVE"
                        elif earnings_growth > 10:
                            earnings_score = 65
                            signal = "POSITIVE"
                        elif earnings_growth > 0:
                            earnings_score = 55
                            signal = "NEUTRAL"
                        elif earnings_growth > -10:
                            earnings_score = 40
                            signal = "NEGATIVE"
                        else:
                            earnings_score = 25
                            signal = "VERY_NEGATIVE"
                        
                        return {
                            'score': earnings_score,
                            'signal': signal,
                            'earnings_growth': earnings_growth,
                            'recent_earnings': recent_earnings,
                            'description': f"Earnings growth: {earnings_growth:.1f}%"
                        }
            
            # Fallback to profit margin proxy
            _pm_raw = stock_data.get('profit_margin', 0)
            _pm_raw = 0 if (_pm_raw is None or (isinstance(_pm_raw, float) and np.isnan(_pm_raw))) else _pm_raw
            profit_margin = _pm_raw * 100 if abs(_pm_raw) < 1.0 else float(_pm_raw)
            
            if profit_margin > 15:
                earnings_score = 70
                signal = "POSITIVE"
            elif profit_margin > 5:
                earnings_score = 50
                signal = "NEUTRAL"
            else:
                earnings_score = 35
                signal = "NEGATIVE"
            
            return {
                'score': earnings_score,
                'signal': signal,
                'earnings_growth': 0,
                'recent_earnings': 0,
                'description': f"Margin-based proxy: {profit_margin:.1f}%"
            }
            
        except Exception as e:
            self.logger.debug(f"Earnings data not available: {e}")
            return {
                'score': 50,
                'signal': "NEUTRAL",
                'earnings_growth': 0,
                'recent_earnings': 0,
                'description': "No earnings data"
            }
    
    def _analyze_social_buzz(self, hist: pd.DataFrame, stock_data: Dict) -> Dict:
        """
        Analyze social media buzz from volume and volatility patterns
        (Proxy for actual social sentiment in absence of social APIs)
        """
        # High volume + high volatility = high buzz
        avg_volume = hist['Volume'].mean()
        recent_volume = hist['Volume'].tail(5).mean()
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Volatility as buzz indicator
        returns = hist['Close'].pct_change().dropna()
        _vol_raw = returns.std() * np.sqrt(252) * 100
        volatility = 0.0 if (len(returns) == 0 or np.isnan(_vol_raw)) else _vol_raw
        
        # Price momentum as sentiment direction
        _mom_raw = returns.tail(5).mean() * 100
        momentum = 0.0 if np.isnan(_mom_raw) else _mom_raw
        
        # Calculate buzz score
        volume_score = min(volume_ratio * 40, 60)  # Cap at 60
        volatility_score = min(volatility * 2, 40)  # Cap at 40
        
        # Adjust by momentum direction
        if momentum > 1:
            buzz_score = np.clip(50 + volume_score + volatility_score * 0.5, 0, 100)
            signal = "POSITIVE"
        elif momentum < -1:
            buzz_score = np.clip(50 - volume_score * 0.5 - volatility_score * 0.3, 0, 100)
            signal = "NEGATIVE"
        else:
            buzz_score = 50
            signal = "NEUTRAL"
        
        # Buzz level
        if volume_ratio > 2.0:
            buzz_level = "HIGH"
        elif volume_ratio > 1.3:
            buzz_level = "MODERATE"
        else:
            buzz_level = "LOW"
        
        return {
            'score': buzz_score,
            'signal': signal,
            'buzz_level': buzz_level,
            'volume_ratio': volume_ratio,
            'volatility': volatility,
            'momentum': momentum,
            'description': f"{buzz_level} buzz, {signal} sentiment"
        }
    
    def _calculate_confidence(self, signals: list) -> float:
        """
        Calculate confidence based on signal agreement
        """
        # Map signals to numeric values
        signal_map = {
            'VERY_POSITIVE': 2, 'POSITIVE': 1, 'BULLISH': 1,
            'NEUTRAL': 0,
            'NEGATIVE': -1, 'BEARISH': -1, 'VERY_NEGATIVE': -2
        }
        
        numeric_signals = [signal_map.get(s, 0) for s in signals]
        
        # Calculate agreement (low variance = high confidence)
        if len(numeric_signals) > 0:
            mean_signal = np.mean(numeric_signals)
            variance = np.var(numeric_signals)
            
            # High confidence when signals agree (low variance)
            confidence = np.clip(100 - variance * 50, 40, 100)
            return confidence
        
        return 50.0
    
    def _get_strength(self, score: float) -> str:
        """Get strength descriptor for score"""
        if score >= 80:
            return "VERY_STRONG"
        elif score >= 65:
            return "STRONG"
        elif score >= 35:
            return "MODERATE"
        elif score >= 20:
            return "WEAK"
        else:
            return "VERY_WEAK"
    
    def _get_default_sentiment(self) -> Dict:
        """Return default neutral sentiment"""
        return {
            'sentiment_composite_score': 50.0,  # A-012: canonical name
            'composite_score': 50.0,            # A-012: backward-compat alias
            'overall_sentiment': 'NEUTRAL',
            'sentiment_signal': 'HOLD',
            'confidence': 40.0,
            'news_sentiment': {'score': 50, 'signal': 'NEUTRAL', 'description': 'No data'},
            'analyst_sentiment': {'score': 50, 'signal': 'NEUTRAL', 'description': 'No data'},
            'market_sentiment': {'score': 50, 'signal': 'NEUTRAL', 'description': 'No data'},
            'earnings_sentiment': {'score': 50, 'signal': 'NEUTRAL', 'description': 'No data'},
            'buzz_sentiment': {'score': 50, 'signal': 'NEUTRAL', 'description': 'No data'},
            'sentiment_strength': 'MODERATE'
        }
    
    def adjust_score_by_sentiment(self, base_score: float, sentiment_data: Dict) -> Dict:
        """
        Adjust stock score based on sentiment analysis
        
        Args:
            base_score: Original stock score (0-100)
            sentiment_data: Sentiment analysis results
            
        Returns:
            Dict with adjusted score and reasons
        """
        adjustment = 0.0
        reasons = []
        
        composite_score = sentiment_data.get('composite_score', 50)
        confidence = sentiment_data.get('confidence', 40)
        if composite_score is None or (isinstance(composite_score, float) and np.isnan(composite_score)):
            composite_score = 50
        if confidence is None or (isinstance(confidence, float) and np.isnan(confidence)):
            confidence = 40
        
        # Calculate sentiment adjustment (±15 points based on sentiment)
        if composite_score >= 70:
            adjustment = 12 * (confidence / 100)
            reasons.append(f"Very positive sentiment (+{adjustment:.1f})")
        elif composite_score >= 58:
            adjustment = 8 * (confidence / 100)
            reasons.append(f"Positive sentiment (+{adjustment:.1f})")
        elif composite_score >= 42:
            adjustment = 0
            reasons.append("Neutral sentiment (no adjustment)")
        elif composite_score >= 35:
            adjustment = -8 * (confidence / 100)
            reasons.append(f"Negative sentiment ({adjustment:.1f})")
        else:
            adjustment = -12 * (confidence / 100)
            reasons.append(f"Very negative sentiment ({adjustment:.1f})")
        
        # Bonus adjustments for specific signals
        news = sentiment_data.get('news_sentiment', {})
        if news.get('signal') == 'POSITIVE' and news.get('volume_surge', 1) > 2:
            adjustment += 2
            reasons.append("High-volume positive news (+2)")
        
        analyst = sentiment_data.get('analyst_sentiment', {})
        if analyst.get('total_recommendations', 0) >= 5:
            if analyst.get('signal') == 'BULLISH':
                adjustment += 2
                reasons.append("Strong analyst support (+2)")
            elif analyst.get('signal') == 'BEARISH':
                adjustment -= 2
                reasons.append("Weak analyst support (-2)")
        
        earnings = sentiment_data.get('earnings_sentiment', {})
        if earnings.get('earnings_growth', 0) > 15:
            adjustment += 2
            reasons.append("Strong earnings growth (+2)")
        
        # Cap adjustment at ±15
        adjustment = np.clip(adjustment, -15.0, 15.0)
        adjusted_score = np.clip(base_score + adjustment, 0, 100)
        
        return {
            'original_score': base_score,
            'adjusted_score': adjusted_score,
            'sentiment_adjustment': adjustment,
            'adjustment_reasons': reasons,
            'sentiment_context': f"{sentiment_data.get('overall_sentiment', 'NEUTRAL')} ({composite_score:.1f}/100)"
        }


def analyze_stock_sentiment(symbol: str, stock_data: Dict) -> Dict:
    """
    Convenience function to analyze stock sentiment
    
    Args:
        symbol: Stock ticker
        stock_data: Stock data dictionary
        
    Returns:
        Sentiment analysis results
    """
    analyzer = SentimentAnalyzer()
    return analyzer.analyze_sentiment(symbol, stock_data)


if __name__ == "__main__":
    # Test sentiment analysis
    print("=" * 80)
    print("🎭 SENTIMENT ANALYSIS TEST")
    print("=" * 80)
    
    test_symbol = "RELIANCE"
    
    # Get basic stock data for test
    ticker = yf.Ticker(f"{test_symbol}.NS")
    info = ticker.info
    
    test_data = {
        'pe_ratio': info.get('trailingPE', 20),
        'profit_margin': info.get('profitMargins', 0.1),
        'real_rsi': 55.0
    }
    
    analyzer = SentimentAnalyzer()
    sentiment = analyzer.analyze_sentiment(test_symbol, test_data)
    
    print(f"\n📊 SENTIMENT ANALYSIS: {test_symbol}")
    print("-" * 80)
    print(f"Composite Score: {sentiment['composite_score']:.1f}/100")
    print(f"Overall Sentiment: {sentiment['overall_sentiment']}")
    print(f"Signal: {sentiment['sentiment_signal']}")
    print(f"Confidence: {sentiment['confidence']:.1f}%")
    print(f"Strength: {sentiment['sentiment_strength']}")
    
    print(f"\n📰 NEWS SENTIMENT")
    print("-" * 80)
    news = sentiment['news_sentiment']
    print(f"Score: {news['score']:.1f} | Signal: {news['signal']}")
    print(f"Description: {news['description']}")
    
    print(f"\n👔 ANALYST SENTIMENT")
    print("-" * 80)
    analyst = sentiment['analyst_sentiment']
    print(f"Score: {analyst['score']:.1f} | Signal: {analyst['signal']}")
    print(f"Description: {analyst['description']}")
    
    print(f"\n📈 MARKET SENTIMENT")
    print("-" * 80)
    market = sentiment['market_sentiment']
    print(f"Score: {market['score']:.1f} | Signal: {market['signal']}")
    print(f"Description: {market['description']}")
    
    print(f"\n💰 EARNINGS SENTIMENT")
    print("-" * 80)
    earnings = sentiment['earnings_sentiment']
    print(f"Score: {earnings['score']:.1f} | Signal: {earnings['signal']}")
    print(f"Description: {earnings['description']}")
    
    print(f"\n🔥 SOCIAL BUZZ")
    print("-" * 80)
    buzz = sentiment['buzz_sentiment']
    print(f"Score: {buzz['score']:.1f} | Signal: {buzz['signal']}")
    print(f"Buzz Level: {buzz['buzz_level']}")
    print(f"Description: {buzz['description']}")
    
    print(f"\n🎯 SCORE ADJUSTMENT TEST")
    print("-" * 80)
    base_score = 75.0
    adjustment = analyzer.adjust_score_by_sentiment(base_score, sentiment)
    print(f"Base Score: {adjustment['original_score']:.1f}")
    print(f"Sentiment Adjustment: {adjustment['sentiment_adjustment']:+.1f}")
    print(f"Adjusted Score: {adjustment['adjusted_score']:.1f}")
    print(f"Reasons: {', '.join(adjustment['adjustment_reasons'])}")
    print(f"Context: {adjustment['sentiment_context']}")
    
    print("\n" + "=" * 80)
    print("✅ Sentiment analysis test completed!")
    print("=" * 80)
