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
from typing import Dict, Optional, Tuple, List
import logging
from datetime import datetime, timedelta
import re
try:
    import requests
    import xml.etree.ElementTree as ET
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

_POSITIVE_WORDS = frozenset([
    'surge', 'surges', 'rally', 'rallies', 'jump', 'jumps', 'gain', 'gains',
    'profit', 'profits', 'growth', 'grows', 'up', 'rise', 'rises', 'rising',
    'record', 'high', 'beat', 'beats', 'strong', 'bullish', 'boom', 'upgrade',
    'outperform', 'buy', 'positive', 'soar', 'soars', 'recovery', 'improving',
    'robust', 'expand', 'expansion', 'breakout', 'upside', 'momentum',
    'optimistic', 'confidence', 'dividend', 'bonus', 'approval', 'deal', 'win',
    'award', 'order', 'contract', 'launch', 'innovation', 'milestone'
])
_NEGATIVE_WORDS = frozenset([
    'crash', 'crashes', 'fall', 'falls', 'drop', 'drops', 'decline', 'declines',
    'loss', 'losses', 'down', 'low', 'miss', 'misses', 'weak', 'bearish',
    'slump', 'plunge', 'sell', 'selling', 'negative', 'warn', 'warning',
    'downgrade', 'underperform', 'cut', 'cuts', 'risk', 'probe', 'fraud',
    'debt', 'default', 'bankruptcy', 'layoff', 'layoffs', 'fine', 'penalty',
    'investigation', 'scandal', 'recall', 'lawsuit', 'shutdown', 'suspend',
    'concern', 'disappointing', 'volatile', 'uncertainty', 'fear'
])


class SentimentAnalyzer:
    """
    Analyze stock sentiment from multiple sources including real news headlines.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._news_cache: Dict[str, Dict] = {}
        self._cache_ttl = 3600
        
    def analyze_sentiment(self, symbol: str, stock_data: Dict, bundle=None) -> Dict:
        """
        Comprehensive sentiment analysis combining multiple signals.
        
        Args:
            symbol: Stock ticker symbol
            stock_data: Dictionary with stock information
            bundle: Optional StockDataBundle to reuse pre-fetched data
            
        Returns:
            Dict with sentiment scores and signals
        """
        try:
            # Reuse bundle data when available to avoid redundant API calls
            hist = None
            ticker = None
            if bundle is not None:
                _h3m = getattr(bundle, 'hist_3mo', None)
                if _h3m is not None and isinstance(_h3m, pd.DataFrame) and not _h3m.empty:
                    hist = _h3m
                elif hasattr(bundle, 'hist_1y') and isinstance(bundle.hist_1y, pd.DataFrame) and not bundle.hist_1y.empty:
                    hist = bundle.hist_1y.tail(63)
                ticker = getattr(bundle, 'ticker', None)

            if hist is None or (isinstance(hist, pd.DataFrame) and hist.empty):
                hist = stock_data.get('_hist_3mo') if isinstance(stock_data.get('_hist_3mo'), pd.DataFrame) else None

            if ticker is None:
                ticker = yf.Ticker(f"{symbol}.NS")

            if hist is None or (isinstance(hist, pd.DataFrame) and hist.empty):
                hist = ticker.history(period="3mo")

            if hist.empty:
                return self._get_default_sentiment()

            _data_age_days = 0
            _is_stale = False
            try:
                _last_date = pd.Timestamp(hist.index[-1])
                _data_age_days = (pd.Timestamp.now(tz=_last_date.tz) - _last_date).days
                _is_stale = _data_age_days > 3
            except Exception:
                pass

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
            
            _sub_results = [news_sentiment, analyst_sentiment, market_sentiment, earnings_sentiment, buzz_sentiment]
            _fallback_count = sum(1 for s in _sub_results if s.get('is_fallback'))
            _detection_failed = _fallback_count >= 3

            return {
                'sentiment_composite_score': composite_score,
                'composite_score': composite_score,
                'overall_sentiment': overall_sentiment,
                'sentiment_signal': sentiment_signal,
                'confidence': confidence,
                'is_fallback': False,
                'detection_failed': _detection_failed,
                'fallback_count': _fallback_count,
                'news_sentiment': news_sentiment,
                'analyst_sentiment': analyst_sentiment,
                'market_sentiment': market_sentiment,
                'earnings_sentiment': earnings_sentiment,
                'buzz_sentiment': buzz_sentiment,
                'sentiment_strength': self._get_strength(composite_score),
                'data_age_days': _data_age_days,
                'is_stale': _is_stale,
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment for {symbol}: {e}")
            return self._get_default_sentiment()
    
    def _fetch_news_headlines(self, symbol: str) -> List[str]:
        """Fetch recent news headlines from Google News RSS (free, no API key)."""
        if not _HAS_REQUESTS:
            return []
        cached = self._news_cache.get(symbol)
        if cached and (datetime.now() - cached['ts']).total_seconds() < self._cache_ttl:
            return cached['headlines']
        try:
            company = symbol.replace('&', '%26')
            url = f"https://news.google.com/rss/search?q={company}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
            resp = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                return []
            root = ET.fromstring(resp.content)
            headlines = []
            for item in root.findall('.//item')[:15]:
                title = item.findtext('title', '')
                if title:
                    title = re.sub(r'<[^>]+>', '', title).strip()
                    headlines.append(title)
            self._news_cache[symbol] = {'ts': datetime.now(), 'headlines': headlines}
            return headlines
        except Exception as e:
            self.logger.debug(f"News fetch for {symbol} failed: {e}")
            return []

    @staticmethod
    def _headline_sentiment_score(headlines: List[str]) -> float:
        """Keyword-based sentiment scoring on headlines. Returns 0-100."""
        if not headlines:
            return 50.0
        pos_total, neg_total = 0, 0
        for h in headlines:
            words = set(re.findall(r'[a-z]+', h.lower()))
            pos_total += len(words & _POSITIVE_WORDS)
            neg_total += len(words & _NEGATIVE_WORDS)
        total = pos_total + neg_total
        if total == 0:
            return 50.0
        ratio = (pos_total - neg_total) / total
        return float(np.clip(50 + ratio * 40, 10, 90))

    def _analyze_news_sentiment(self, hist: pd.DataFrame, stock_data: Dict) -> Dict:
        """
        Analyze news sentiment — uses real headlines when available,
        falls back to multi-window price-action proxy.
        """
        symbol = stock_data.get('symbol', '')
        headlines = self._fetch_news_headlines(symbol) if symbol else []
        headline_score = self._headline_sentiment_score(headlines)
        has_real_news = len(headlines) >= 3

        returns = hist['Close'].pct_change()
        r5 = returns.tail(5)
        r10 = returns.tail(10)
        r20 = returns.tail(20)

        pos_20 = (r20 > 0.01).sum()
        neg_20 = (r20 < -0.01).sum()
        avg_volume = hist['Volume'].mean()
        recent_volume = hist['Volume'].tail(5).mean()
        volume_surge = recent_volume / avg_volume if avg_volume > 0 else 1.0

        mom_5  = float(r5.mean() * 100) if len(r5) > 0 else 0
        mom_10 = float(r10.mean() * 100) if len(r10) > 0 else 0
        mom_20 = float(r20.mean() * 100) if len(r20) > 0 else 0
        mom_5 = 0 if np.isnan(mom_5) else mom_5
        mom_10 = 0 if np.isnan(mom_10) else mom_10
        mom_20 = 0 if np.isnan(mom_20) else mom_20
        multi_mom = mom_5 * 0.5 + mom_10 * 0.3 + mom_20 * 0.2

        momentum_score = np.clip(multi_mom * 15, -30, 30)
        volume_bonus = min(volume_surge * 10, 20)
        proxy_score = float(np.clip(50 + momentum_score + volume_bonus, 0, 100))

        if has_real_news:
            news_score = headline_score * 0.6 + proxy_score * 0.4
        else:
            news_score = proxy_score

        if news_score >= 65:
            signal = "POSITIVE"
        elif news_score >= 35:
            signal = "NEUTRAL"
        else:
            signal = "NEGATIVE"

        desc = f"{signal} ({len(headlines)} headlines)" if has_real_news else f"{signal} (proxy)"
        return {
            'score': float(np.clip(news_score, 0, 100)),
            'signal': signal,
            'positive_days': int(pos_20),
            'negative_days': int(neg_20),
            'volume_surge': volume_surge,
            'headline_count': len(headlines),
            'headline_score': headline_score if has_real_news else None,
            'description': desc
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
        try:
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

            recent_volume = hist['Volume'].tail(10).mean()
            older_volume = hist['Volume'].tail(30).mean()
            volume_trend = recent_volume / older_volume if older_volume > 0 else 1.0

            ma_20 = hist['Close'].rolling(20).mean().iloc[-1]
            current_price = hist['Close'].iloc[-1]
            price_vs_ma = (current_price - ma_20) / ma_20 * 100 if ma_20 > 0 else 0

            rsi_component = rsi
            volume_component = min(volume_trend * 50, 100)
            trend_component = np.clip(50 + price_vs_ma * 2, 0, 100)

            market_score = (rsi_component * 0.4 + volume_component * 0.3 + trend_component * 0.3)

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
        except Exception as _e:
            logging.debug(f"_analyze_market_sentiment failed: {_e}")
            return {'score': 50, 'signal': 'NEUTRAL', 'is_fallback': True, 'description': 'Market sentiment analysis failed'}
    
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
        """Return default neutral sentiment with is_fallback flag."""
        return {
            'sentiment_composite_score': 50.0,
            'composite_score': 50.0,
            'overall_sentiment': 'NEUTRAL',
            'sentiment_signal': 'HOLD',
            'confidence': 40.0,
            'is_fallback': True,
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
        
        # Cap adjustment at ±3 (confidence-weighted, avoids oversized sentiment swings)
        adjustment = np.clip(adjustment, -3.0, 3.0)
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
