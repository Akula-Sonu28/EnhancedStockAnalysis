# News and Sentiment Analyzer
import yfinance as yf
from bs4 import BeautifulSoup
import requests
import pandas as pd
from datetime import datetime, timedelta
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from config import LOG_FILE

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

def get_stock_news(symbol, num_articles=10):
    """
    Get recent news articles for a stock from Yahoo Finance
    Returns: List of news articles with sentiment analysis
    """
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        
        if not news:
            logging.warning(f"No news found for {symbol}")
            return []
            
        processed_news = []
        for article in news[:num_articles]:
            # Extract relevant information
            news_item = {
                'date': datetime.fromtimestamp(article.get('providerPublishTime', 0)),
                'title': article.get('title', ''),
                'summary': article.get('summary', ''),
                'link': article.get('link', ''),
                'source': article.get('publisher', '')
            }
            
            # Add sentiment analysis
            sentiment = analyze_sentiment(news_item['title'] + " " + news_item['summary'])
            news_item.update(sentiment)
            
            processed_news.append(news_item)
            
        return processed_news
        
    except Exception as e:
        logging.error(f"Error fetching news for {symbol}: {str(e)}")
        return []

def analyze_sentiment(text):
    """
    Basic sentiment analysis using keyword matching
    Returns: dict with sentiment score and classification
    """
    # Positive and negative word lists
    positive_words = {
        'buy', 'bullish', 'upgrade', 'growth', 'profit', 'positive', 'strong',
        'surge', 'gain', 'upbeat', 'improve', 'success', 'growing', 'opportunity',
        'outperform', 'beat', 'exceeded', 'higher', 'record', 'innovation'
    }
    
    negative_words = {
        'sell', 'bearish', 'downgrade', 'decline', 'loss', 'negative', 'weak',
        'fall', 'drop', 'downbeat', 'worsen', 'fail', 'shrinking', 'risk',
        'underperform', 'miss', 'lower', 'warning', 'investigation', 'lawsuit'
    }
    
    # Convert to lowercase for comparison
    text = text.lower()
    words = set(re.findall(r'\w+', text))
    
    # Count sentiment words
    pos_count = len(words.intersection(positive_words))
    neg_count = len(words.intersection(negative_words))
    
    # Calculate sentiment score (-1 to 1)
    total = pos_count + neg_count
    if total == 0:
        score = 0
    else:
        score = (pos_count - neg_count) / total
    
    # Determine sentiment category
    if score > 0.3:
        sentiment = 'Positive'
    elif score < -0.3:
        sentiment = 'Negative'
    else:
        sentiment = 'Neutral'
    
    return {
        'sentiment_score': round(score * 5 + 5, 2),  # Convert to 0-10 scale
        'sentiment': sentiment,
        'positive_words': pos_count,
        'negative_words': neg_count
    }

def get_market_news():
    """
    Get overall market news (Nifty, Sensex, global markets)
    Returns: Dict with categorized market news
    """
    try:
        market_news = {
            'indices': [],      # Nifty, Sensex news
            'global': [],       # Global market news
            'commodities': [],  # Commodity market news
            'forex': []         # Currency market news
        }
        
        # Get Nifty news
        nifty = yf.Ticker('^NSEI')
        nifty_news = nifty.news
        if nifty_news:
            for article in nifty_news[:5]:
                market_news['indices'].append({
                    'date': datetime.fromtimestamp(article.get('providerPublishTime', 0)),
                    'title': article.get('title', ''),
                    'summary': article.get('summary', ''),
                    'link': article.get('link', '')
                })
        
        return market_news
        
    except Exception as e:
        logging.error(f"Error fetching market news: {str(e)}")
        return None

def identify_news_themes(news_items):
    """
    Identify recurring themes in news
    Returns: Dict with theme analysis
    """
    themes = {
        'expansion': 0,
        'litigation': 0,
        'earnings': 0,
        'management': 0,
        'products': 0,
        'partnerships': 0,
        'regulatory': 0,
        'market_share': 0
    }
    
    # Theme keywords
    theme_keywords = {
        'expansion': ['expand', 'growth', 'new market', 'facility', 'acquisition'],
        'litigation': ['lawsuit', 'legal', 'court', 'settlement', 'dispute'],
        'earnings': ['revenue', 'profit', 'earnings', 'financial results', 'quarterly'],
        'management': ['ceo', 'executive', 'appointed', 'resigned', 'management'],
        'products': ['launch', 'product', 'innovation', 'release', 'new offering'],
        'partnerships': ['partnership', 'collaboration', 'deal', 'agreement', 'joint venture'],
        'regulatory': ['regulation', 'compliance', 'approved', 'clearance', 'regulatory'],
        'market_share': ['market leader', 'competitor', 'industry position', 'market share']
    }
    
    # Analyze each news item
    for news in news_items:
        text = (news['title'] + ' ' + news['summary']).lower()
        for theme, keywords in theme_keywords.items():
            if any(keyword in text for keyword in keywords):
                themes[theme] += 1
    
    # Calculate percentages and identify primary themes
    total_mentions = sum(themes.values()) or 1  # Avoid division by zero
    theme_analysis = {
        'theme_distribution': {theme: round(count/total_mentions * 100, 2) 
                             for theme, count in themes.items()},
        'primary_themes': [theme for theme, count in themes.items() 
                          if count/total_mentions > 0.2],  # Themes mentioned in >20% of news
        'theme_count': themes
    }
    
    return theme_analysis

def generate_news_summary(symbol):
    """
    Generate comprehensive news analysis for a stock
    Returns: Dict with news analysis
    """
    # Get stock-specific news
    stock_news = get_stock_news(symbol)
    
    # Get market news
    market_news = get_market_news()
    
    # Calculate overall sentiment
    if stock_news:
        avg_sentiment = sum(news['sentiment_score'] for news in stock_news) / len(stock_news)
        sentiment_dist = {
            'Positive': sum(1 for news in stock_news if news['sentiment'] == 'Positive'),
            'Neutral': sum(1 for news in stock_news if news['sentiment'] == 'Neutral'),
            'Negative': sum(1 for news in stock_news if news['sentiment'] == 'Negative')
        }
    else:
        avg_sentiment = 5.0  # Neutral
        sentiment_dist = {'Positive': 0, 'Neutral': 0, 'Negative': 0}
    
    # Identify themes
    themes = identify_news_themes(stock_news)
    
    summary = {
        'stock_specific_news': stock_news,
        'market_news': market_news,
        'sentiment_analysis': {
            'overall_score': round(avg_sentiment, 2),
            'distribution': sentiment_dist,
            'interpretation': 'Bullish' if avg_sentiment > 6.5 else 
                            'Bearish' if avg_sentiment < 3.5 else 'Neutral'
        },
        'themes': themes,
        'latest_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return summary
