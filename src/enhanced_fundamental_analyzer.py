"""
Enhanced Fundamental Analyzer with comprehensive data extraction
"""
import yfinance as yf
import requests
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import time

def get_comprehensive_stock_data(symbol, bundle=None):
    """Get comprehensive stock data. If *bundle* (StockDataBundle) is supplied,
    reuse its pre-fetched info & hist to avoid duplicate API calls."""
    data = {
        'symbol': symbol,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        if bundle is not None:
            info = bundle.info
            hist = bundle.hist_1y
        else:
            ticker = yf.Ticker(symbol + ".NS")
            info = ticker.info
            hist = ticker.history(period="1y")

        if not info:
            info = {}
        
        # Basic company info
        # Keep company_name for display but ensure symbol stays as-is
        company_full_name = info.get('longName') or symbol
        data.update({
            'company_name': company_full_name if company_full_name != symbol else symbol,
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'website': info.get('website', ''),
            'business_summary': info.get('longBusinessSummary', '')[:200] + '...' if info.get('longBusinessSummary') else '',
            'employees': info.get('fullTimeEmployees', 0),
            'country': info.get('country', 'India')
        })
        
        # Market data
        data.update({
            'current_price': info.get('currentPrice', 0) or info.get('regularMarketPrice', 0),
            'market_cap': info.get('marketCap', 0),
            'enterprise_value': info.get('enterpriseValue', 0),
            'shares_outstanding': info.get('sharesOutstanding', 0),
            'float_shares': info.get('floatShares', 0),
            'beta': info.get('beta', 1.0),
            '52_week_high': info.get('fiftyTwoWeekHigh', 0),
            '52_week_low': info.get('fiftyTwoWeekLow', 0),
            'avg_volume': info.get('averageVolume', 0)
        })
        
        # Valuation ratios
        data.update({
            'pe_ratio': info.get('trailingPE', 0) or info.get('forwardPE', 0),
            'forward_pe': info.get('forwardPE', 0),
            'pb_ratio': info.get('priceToBook', 0),
            'ps_ratio': info.get('priceToSalesTrailing12Months', 0),
            'peg_ratio': info.get('pegRatio', 0),
            'ev_ebitda': info.get('enterpriseToEbitda', 0),
            'ev_revenue': info.get('enterpriseToRevenue', 0),
            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        })
        
        # Profitability metrics
        data.update({
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0,
            'gross_margin': info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0,
            'operating_margin': info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0,
            'net_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
            'ebitda_margin': info.get('ebitdaMargins', 0) * 100 if info.get('ebitdaMargins') else 0
        })
        
        # Growth metrics
        data.update({
            'revenue_growth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
            'earnings_growth': info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0,
            'quarterly_revenue_growth': info.get('revenueQuarterlyGrowth', 0) * 100 if info.get('revenueQuarterlyGrowth') else 0,
            'quarterly_earnings_growth': info.get('earningsQuarterlyGrowth', 0) * 100 if info.get('earningsQuarterlyGrowth') else 0
        })
        
        # Financial strength
        data.update({
            'debt_to_equity': info.get('debtToEquity', 0),
            'current_ratio': info.get('currentRatio', 0),
            'quick_ratio': info.get('quickRatio', 0),
            'total_cash': info.get('totalCash', 0),
            'total_debt': info.get('totalDebt', 0),
            'operating_cashflow': info.get('operatingCashflow', 0),
            'free_cashflow': info.get('freeCashflow', 0)
        })
        
        # Per share metrics
        data.update({
            'eps': info.get('trailingEps', 0) or info.get('forwardEps', 0),
            'forward_eps': info.get('forwardEps', 0),
            'book_value': info.get('bookValue', 0),
            'revenue_per_share': info.get('revenuePerShare', 0),
            'cash_per_share': info.get('totalCashPerShare', 0)
        })
        
        # Ownership structure
        data.update({
            'insider_ownership': info.get('heldPercentInsiders', 0) * 100 if info.get('heldPercentInsiders') else 0,
            'institutional_ownership': info.get('heldPercentInstitutions', 0) * 100 if info.get('heldPercentInstitutions') else 0
        })
        
        # Calculate additional metrics from historical data
        if not hist.empty and len(hist) > 0:
            def _safe_pct(series, offset):
                if len(series) < offset: return 0
                d = series.iloc[-offset]
                if pd.isna(d) or d == 0: return 0
                return ((series.iloc[-1] - d) / d * 100)
            _vol_raw = hist['Close'].pct_change().std() * 100 * (252**0.5) if len(hist) > 1 else 0
            _cummax = hist['Close'].cummax().replace(0, np.nan)
            _drawdown = (hist['Close'] - _cummax) / _cummax * 100
            _max_dd = float(_drawdown.min()) if len(_drawdown) > 0 else 0
            data.update({
                'price_change_1m': _safe_pct(hist['Close'], 22),
                'price_change_3m': _safe_pct(hist['Close'], 66),
                'price_change_6m': _safe_pct(hist['Close'], 132),
                'price_change_1y': _safe_pct(hist['Close'], len(hist)) if len(hist) > 1 else 0,
                'volatility': 0 if pd.isna(_vol_raw) else _vol_raw,
                'max_drawdown_6m': 0 if pd.isna(_max_dd) else round(_max_dd, 2)
            })
        
        # Calculate fundamental score
        fund_score = calculate_comprehensive_fundamental_score(data)
        data['fundamental_score'] = fund_score['score']
        data['fundamental_rating'] = fund_score['rating']
        data['fundamental_analysis'] = fund_score['analysis']
        
        logging.info(f"Comprehensive data extracted for {symbol}")
        return data
        
    except Exception as e:
        logging.error(f"Error getting comprehensive data for {symbol}: {str(e)}")
        # Return basic structure with zeros to avoid empty values
        return get_default_stock_data(symbol)

def get_default_stock_data(symbol):
    """Return default data structure with zero values"""
    return {
        'symbol': symbol,
        'company_name': symbol,
        'sector': 'Unknown',
        'industry': 'Unknown',
        'current_price': 0,
        'market_cap': 0,
        'pe_ratio': 0,
        'pb_ratio': 0,
        'roe': 0,
        'debt_to_equity': 0,
        'revenue_growth': 0,
        'earnings_growth': 0,
        'dividend_yield': 0,
        'fundamental_score': 50,
        'fundamental_rating': 'Neutral',
        'fundamental_analysis': 'Insufficient data for analysis'
    }

def calculate_comprehensive_fundamental_score(data):
    """Calculate comprehensive fundamental score"""
    score = 50  # Start with neutral
    analysis_points = []
    
    try:
        # Valuation Score (25 points)
        pe_ratio = data.get('pe_ratio', 0)
        pb_ratio = data.get('pb_ratio', 0)
        
        if 0 < pe_ratio < 15:
            score += 15
            analysis_points.append("Attractive valuation (low PE)")
        elif 15 <= pe_ratio < 25:
            score += 8
            analysis_points.append("Reasonable valuation")
        elif pe_ratio >= 30:
            score -= 8
            analysis_points.append("High valuation (high PE)")
        
        if 0 < pb_ratio < 1:
            score += 10
            analysis_points.append("Trading below book value")
        elif 1 <= pb_ratio < 3:
            score += 5
        elif pb_ratio >= 5:
            score -= 5
        
        # Profitability Score (25 points)
        roe = data.get('roe', 0)
        net_margin = data.get('net_margin', 0)
        
        if roe > 20:
            score += 15
            analysis_points.append("Excellent ROE")
        elif roe > 15:
            score += 10
            analysis_points.append("Good ROE")
        elif roe > 10:
            score += 5
        elif roe < 5:
            score -= 10
            analysis_points.append("Poor ROE")
        
        if net_margin > 15:
            score += 10
            analysis_points.append("High profit margins")
        elif net_margin > 10:
            score += 5
        elif net_margin < 5:
            score -= 5
        
        # Growth Score (25 points)
        revenue_growth = data.get('revenue_growth', 0)
        earnings_growth = data.get('earnings_growth', 0)
        
        if revenue_growth > 20:
            score += 15
            analysis_points.append("Strong revenue growth")
        elif revenue_growth > 10:
            score += 10
            analysis_points.append("Good revenue growth")
        elif revenue_growth > 5:
            score += 5
        elif revenue_growth < 0:
            score -= 10
            analysis_points.append("Declining revenue")
        
        if earnings_growth > 20:
            score += 10
            analysis_points.append("Strong earnings growth")
        elif earnings_growth > 10:
            score += 5
        elif earnings_growth < 0:
            score -= 10
        
        # Financial Health Score (25 points)
        debt_to_equity = data.get('debt_to_equity', 0)
        if isinstance(debt_to_equity, (int, float)) and 0 < debt_to_equity < 5:
            debt_to_equity = debt_to_equity * 100  # normalize ratio to percentage
        current_ratio = data.get('current_ratio', 0)
        
        if debt_to_equity < 30:
            score += 15
            analysis_points.append("Low debt levels")
        elif debt_to_equity < 60:
            score += 8
        elif debt_to_equity > 100:
            score -= 10
            analysis_points.append("High debt levels")
        
        if current_ratio > 2:
            score += 10
            analysis_points.append("Strong liquidity")
        elif current_ratio > 1.5:
            score += 5
        elif current_ratio < 1:
            score -= 10
            analysis_points.append("Liquidity concerns")
        
        # Ensure score is within bounds
        if isinstance(score, float) and np.isnan(score):
            score = 50.0
        score = max(0, min(100, score))
        
        # Determine rating
        if score >= 80:
            rating = "Excellent"
        elif score >= 70:
            rating = "Good"
        elif score >= 60:
            rating = "Average"
        elif score >= 40:
            rating = "Below Average"
        else:
            rating = "Poor"
        
        analysis = "; ".join(analysis_points) if analysis_points else "Limited fundamental data available"
        
        return {
            'score': round(score, 1),
            'rating': rating,
            'analysis': analysis
        }
        
    except Exception as e:
        logging.error(f"Error calculating fundamental score: {str(e)}")
        return {
            'score': 50,
            'rating': 'Neutral',
            'analysis': 'Error in fundamental analysis'
        }

# Legacy compatibility functions
def extract_fundamental_metrics(info):
    """Legacy compatibility function"""
    if not info:
        return get_default_stock_data('UNKNOWN')
    
    symbol = info.get('symbol', 'UNKNOWN')
    return get_comprehensive_stock_data(symbol)

def compute_fundamental_score(metrics):
    """Legacy compatibility function"""
    if not metrics:
        return {'score': 50, 'rating': 'Neutral'}
    
    return {
        'score': metrics.get('fundamental_score', 50),
        'rating': metrics.get('fundamental_rating', 'Neutral')
    }
