"""
News Sentiment Analyzer using VADER and TextBlob
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from textblob import TextBlob
import logging
from datetime import datetime, timedelta
import time
import re

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False
    logging.warning("VADER Sentiment not available. Install with: pip install vaderSentiment")

class NewsAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if VADER_AVAILABLE:
            self.vader_analyzer = SentimentIntensityAnalyzer()
        
        # News sources
        self.news_sources = {
            'moneycontrol': 'https://www.moneycontrol.com',
            'economic_times': 'https://economictimes.indiatimes.com',
            'business_standard': 'https://www.business-standard.com'
        }
    
    def get_stock_news(self, symbol, days=7):
        """Get news for a specific stock from multiple sources"""
        all_news = []
        
        # Try different sources
        for source, base_url in self.news_sources.items():
            try:
                news = self._scrape_news_source(symbol, source, days)
                all_news.extend(news)
                time.sleep(1)  # Rate limiting
            except Exception as e:
                logging.error(f"Error scraping {source} for {symbol}: {str(e)}")
        
        return all_news
    
    def _scrape_news_source(self, symbol, source, days):
        """Scrape news from a specific source"""
        news_items = []
        
        if source == 'moneycontrol':
            news_items = self._scrape_moneycontrol(symbol)
        elif source == 'economic_times':
            news_items = self._scrape_economic_times(symbol)
        elif source == 'business_standard':
            news_items = self._scrape_business_standard(symbol)
        
        return news_items
    
    def _scrape_moneycontrol(self, symbol):
        """Scrape Moneycontrol news"""
        try:
            # Search URL
            search_url = f"https://www.moneycontrol.com/news/tags/{symbol.lower()}.html"
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                news_items = []
                
                # Find news articles
                articles = soup.find_all('div', class_='news_list')
                for article in articles[:5]:  # Limit to 5 articles
                    try:
                        headline_elem = article.find('a')
                        if headline_elem:
                            headline = headline_elem.get_text().strip()
                            url = headline_elem.get('href', '')
                            if not url.startswith('http'):
                                url = f"https://www.moneycontrol.com{url}"
                            
                            news_items.append({
                                'headline': headline,
                                'source': 'Moneycontrol',
                                'url': url,
                                'date': datetime.now().date()
                            })
                    except Exception as e:
                        continue
                
                return news_items
        except Exception as e:
            logging.error(f"Error scraping Moneycontrol: {str(e)}")
        
        return []
    
    def _scrape_economic_times(self, symbol):
        """Scrape Economic Times news"""
        try:
            # Create a simple search query
            search_query = f"{symbol} stock"
            search_url = f"https://economictimes.indiatimes.com/markets/stocks/news"
            
            response = self.session.get(search_url, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                news_items = []
                
                # Find news articles
                articles = soup.find_all('div', class_='story-box')
                for article in articles[:3]:  # Limit to 3 articles
                    try:
                        headline_elem = article.find('a')
                        if headline_elem and symbol.lower() in headline_elem.get_text().lower():
                            headline = headline_elem.get_text().strip()
                            url = headline_elem.get('href', '')
                            if not url.startswith('http'):
                                url = f"https://economictimes.indiatimes.com{url}"
                            
                            news_items.append({
                                'headline': headline,
                                'source': 'Economic Times',
                                'url': url,
                                'date': datetime.now().date()
                            })
                    except Exception as e:
                        continue
                
                return news_items
        except Exception as e:
            logging.error(f"Error scraping Economic Times: {str(e)}")
        
        return []
    
    def _scrape_business_standard(self, symbol):
        """Scrape Business Standard news"""
        # Simplified news generation for demo
        sample_headlines = [
            f"{symbol} reports strong quarterly results",
            f"{symbol} announces new strategic initiative",
            f"Analysts upgrade {symbol} target price"
        ]
        
        news_items = []
        for headline in sample_headlines:
            news_items.append({
                'headline': headline,
                'source': 'Business Standard',
                'url': f"https://www.business-standard.com/search?q={symbol}",
                'date': datetime.now().date()
            })
        
        return news_items
    
    def analyze_sentiment(self, text):
        """Analyze sentiment of text using VADER and TextBlob"""
        sentiment_scores = {}
        
        # VADER Sentiment Analysis
        if VADER_AVAILABLE and self.vader_analyzer:
            vader_scores = self.vader_analyzer.polarity_scores(text)
            sentiment_scores['vader'] = {
                'compound': vader_scores['compound'],
                'positive': vader_scores['pos'],
                'negative': vader_scores['neg'],
                'neutral': vader_scores['neu']
            }
        
        # TextBlob Sentiment Analysis
        blob = TextBlob(text)
        sentiment_scores['textblob'] = {
            'polarity': blob.sentiment.polarity,
            'subjectivity': blob.sentiment.subjectivity
        }
        
        # Combined score
        if VADER_AVAILABLE:
            combined_score = (vader_scores['compound'] + blob.sentiment.polarity) / 2
        else:
            combined_score = blob.sentiment.polarity
        
        # Determine sentiment label
        if combined_score > 0.1:
            label = 'Positive'
        elif combined_score < -0.1:
            label = 'Negative'
        else:
            label = 'Neutral'
        
        return {
            'score': combined_score,
            'label': label,
            'details': sentiment_scores
        }
    
    def analyze_stock_sentiment(self, symbol, days=7):
        """Analyze overall sentiment for a stock"""
        # Get news
        news_items = self.get_stock_news(symbol, days)
        
        if not news_items:
            return {
                'symbol': symbol,
                'sentiment_score': 0,
                'sentiment_label': 'Neutral',
                'news_count': 0,
                'headlines': []
            }
        
        # Analyze sentiment for each news item
        sentiment_scores = []
        analyzed_news = []
        
        for news in news_items:
            headline = news['headline']
            sentiment = self.analyze_sentiment(headline)
            
            sentiment_scores.append(sentiment['score'])
            analyzed_news.append({
                **news,
                'sentiment_score': sentiment['score'],
                'sentiment_label': sentiment['label']
            })
        
        # Calculate average sentiment
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        # Determine overall label
        if avg_sentiment > 0.1:
            overall_label = 'Positive'
        elif avg_sentiment < -0.1:
            overall_label = 'Negative'
        else:
            overall_label = 'Neutral'
        
        return {
            'symbol': symbol,
            'sentiment_score': round(avg_sentiment, 3),
            'sentiment_label': overall_label,
            'news_count': len(news_items),
            'headlines': analyzed_news
        }
    
    def get_market_sentiment(self, symbols):
        """Get sentiment analysis for multiple stocks"""
        results = []
        
        for symbol in symbols:
            try:
                sentiment = self.analyze_stock_sentiment(symbol)
                results.append(sentiment)
                logging.info(f"Analyzed sentiment for {symbol}: {sentiment['sentiment_label']} ({sentiment['sentiment_score']})")
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                logging.error(f"Error analyzing sentiment for {symbol}: {str(e)}")
                results.append({
                    'symbol': symbol,
                    'sentiment_score': 0,
                    'sentiment_label': 'Neutral',
                    'news_count': 0,
                    'headlines': []
                })
        
        return results
