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


def _nv(val, default=0):
    """Return val if it is not None and not NaN, else default."""
    if val is None:
        return default
    try:
        if val != val:
            return default
    except (TypeError, ValueError):
        pass
    return val


def _safe_pe(info: dict) -> float:
    """Return PE ratio. For loss-making stocks (negative EPS, no PE from yfinance),
    return -1 as a sentinel so downstream scoring can distinguish 'no data' (0) from 'loss-making' (-1)."""
    pe = info.get('trailingPE')
    if pe and pe > 0:
        return pe
    fwd = info.get('forwardPE')
    if fwd and fwd > 0:
        return fwd
    eps = info.get('trailingEps', 0)
    if eps is not None and eps < 0:
        return -1.0
    return 0.0


def _safe_dividend_yield(info: dict) -> float:
    """Return dividend yield as a percentage, with sanity checks.
    yfinance returns dividendYield as a ratio (e.g. 0.02 = 2%).
    Some NSE stocks return anomalous values that would exceed 20% — treat those
    as suspect and fall back to computing from dividendRate / currentPrice."""
    raw = info.get('dividendYield')
    if not raw:
        return 0.0
    pct = raw * 100
    if pct <= 20:
        return round(pct, 4)
    div_rate = info.get('dividendRate') or info.get('trailingAnnualDividendRate')
    price = _nv(info.get('currentPrice'), _nv(info.get('regularMarketPrice'), 0))
    if div_rate and price and price > 0:
        computed = (div_rate / price) * 100
        if 0 < computed <= 20:
            return round(computed, 4)
    return 0.0


def _safe_roe(info: dict, bundle=None) -> float:
    """Return ROE as a percentage. Falls back to computing from financials
    (netIncomeToCommon / totalStockholderEquity) when returnOnEquity is missing."""
    raw = info.get('returnOnEquity')
    if raw:
        return round(raw * 100, 4)
    try:
        if bundle is not None:
            ticker_obj = bundle._ticker if hasattr(bundle, '_ticker') else None
        else:
            ticker_obj = None
        if ticker_obj is None:
            sym = info.get('symbol', '')
            if not sym:
                return 0.0
            if not sym.endswith('.NS'):
                sym = sym + '.NS'
            ticker_obj = yf.Ticker(sym)
        bs = ticker_obj.balance_sheet
        inc = ticker_obj.income_stmt
        if bs is not None and not bs.empty and inc is not None and not inc.empty:
            equity = None
            for label in ['Total Stockholder Equity', 'Stockholders Equity',
                          'Total Equity Gross Minority Interest', 'Common Stock Equity']:
                if label in bs.index:
                    equity = bs.loc[label].iloc[0]
                    break
            net_income = None
            for label in ['Net Income', 'Net Income Common Stockholders',
                          'Net Income From Continuing Operations']:
                if label in inc.index:
                    net_income = inc.loc[label].iloc[0]
                    break
            if equity and net_income and not pd.isna(equity) and not pd.isna(net_income) and equity != 0:
                return round((net_income / equity) * 100, 4)
    except Exception as e:
        logging.debug(f"ROE fallback calculation failed: {e}")
    return 0.0


def _calculate_piotroski(data: dict, info: dict, bundle=None) -> int:
    """Piotroski F-Score (0-9): 9 binary signals for value investing.
    Uses yfinance info + financial statements when available."""
    score = 0
    try:
        roa = data.get('roa', 0) / 100 if data.get('roa') else 0
        ocf = data.get('operating_cashflow', 0)
        net_margin = data.get('net_margin', 0) / 100 if data.get('net_margin') else 0
        fcf = data.get('free_cashflow', 0)
        _d2e_raw = data.get('debt_to_equity')
        d2e = 0 if _d2e_raw is None or (isinstance(_d2e_raw, float) and _d2e_raw != _d2e_raw) else _d2e_raw
        cr = data.get('current_ratio', 0)
        shares = data.get('shares_outstanding', 0)
        gross_margin = data.get('gross_margin', 0) / 100 if data.get('gross_margin') else 0
        revenue_growth = data.get('revenue_growth', 0) / 100 if data.get('revenue_growth') else 0

        # 1. Net income positive (ROA > 0)
        if roa > 0:
            score += 1
        # 2. Operating cash flow positive
        if ocf and ocf > 0:
            score += 1
        # 3. ROA improving (use earnings_growth as proxy)
        if data.get('earnings_growth', 0) > 0:
            score += 1
        # 4. Cash flow > Net income (accruals quality)
        net_income = info.get('netIncomeToCommon', 0) or 0
        if ocf and ocf > net_income:
            score += 1
        # 5. Long-term debt decreasing (use D/E as proxy — lower is better; skip if unknown)
        if d2e and d2e > 0 and d2e < 50:
            score += 1
        # 6. Current ratio improving (> 1 is healthy)
        if cr > 1:
            score += 1
        # 7. No share dilution (shares_outstanding not increasing — assume OK if available)
        if shares > 0:
            score += 1
        # 8. Gross margin improving
        if gross_margin > 0 and revenue_growth > 0:
            score += 1
        # 9. Asset turnover improving (revenue growth > 0)
        if revenue_growth > 0:
            score += 1
    except Exception as e:
        logging.debug(f"Piotroski F-Score calculation error: {e}")
    return score


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
            'pe_ratio': _safe_pe(info),
            'forward_pe': info.get('forwardPE', 0),
            'pb_ratio': info.get('priceToBook', 0),
            'ps_ratio': info.get('priceToSalesTrailing12Months', 0),
            'peg_ratio': _nv(info.get('pegRatio'), _nv(info.get('trailingPegRatio'), 0)),
            'ev_ebitda': info.get('enterpriseToEbitda', 0),
            'ev_revenue': info.get('enterpriseToRevenue', 0),
            'dividend_yield': _safe_dividend_yield(info)
        })
        
        # Profitability metrics
        data.update({
            'roe': _safe_roe(info, bundle),
            'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0,
            'gross_margin': info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0,
            'operating_margin': info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0,
            'net_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
            'ebitda_margin': info.get('ebitdaMargins', 0) * 100 if info.get('ebitdaMargins') else 0
        })
        
        # Growth metrics — with fallback from ticker.financials for Indian stocks
        _eg = _nv(info.get('earningsGrowth'), 0) * 100 if _nv(info.get('earningsGrowth'), 0) else 0
        _qeg = _nv(info.get('earningsQuarterlyGrowth'), 0) * 100 if _nv(info.get('earningsQuarterlyGrowth'), 0) else 0
        if _eg == 0:
            try:
                _ticker = bundle._ticker if (bundle is not None and hasattr(bundle, '_ticker')) else yf.Ticker(symbol + '.NS')
                _fin = _ticker.financials
                if _fin is not None and not _fin.empty:
                    _ni_row = None
                    for _ni_key in ['Net Income', 'Net Income From Continuing Operations', 'Net Income Common Stockholders']:
                        if _ni_key in _fin.index:
                            _ni_row = _fin.loc[_ni_key].dropna()
                            break
                    if _ni_row is not None and len(_ni_row) >= 2:
                        _ni_latest = float(_ni_row.iloc[0])
                        _ni_prev = float(_ni_row.iloc[1])
                        if _ni_prev != 0 and _ni_latest != 0:
                            _eg = round((_ni_latest - _ni_prev) / abs(_ni_prev) * 100, 2)
            except Exception:
                pass
        data.update({
            'revenue_growth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
            'earnings_growth': _eg,
            'quarterly_revenue_growth': info.get('revenueQuarterlyGrowth', 0) * 100 if info.get('revenueQuarterlyGrowth') else 0,
            'quarterly_earnings_growth': _qeg
        })

        if data['peg_ratio'] == 0 and _eg > 0 and data.get('pe_ratio', 0) > 0:
            data['peg_ratio'] = round(data['pe_ratio'] / _eg, 2)
        
        # Financial strength — with fallback from financial statements
        _ocf = info.get('operatingCashflow') or 0
        _fcf = info.get('freeCashflow') or 0
        _cr = _nv(info.get('currentRatio'), 0)
        _qr = _nv(info.get('quickRatio'), 0)
        if not _ocf or not _fcf or not _cr:
            try:
                _ticker = (bundle._ticker if (bundle is not None and hasattr(bundle, '_ticker'))
                           else yf.Ticker(symbol + '.NS'))
                if not _ocf or not _fcf:
                    _cf = _ticker.cashflow
                    if _cf is not None and not _cf.empty:
                        for _ocf_key in ['Operating Cash Flow', 'Cash Flow From Continuing Operating Activities', 'Total Cash From Operating Activities']:
                            if _ocf_key in _cf.index and not _ocf:
                                _vals = _cf.loc[_ocf_key].dropna()
                                if len(_vals) > 0:
                                    _ocf = int(_vals.iloc[0])
                                    break
                        for _fcf_key in ['Free Cash Flow']:
                            if _fcf_key in _cf.index and not _fcf:
                                _vals = _cf.loc[_fcf_key].dropna()
                                if len(_vals) > 0:
                                    _fcf = int(_vals.iloc[0])
                                    break
                if not _cr or not _qr:
                    _bs = _ticker.balance_sheet
                    if _bs is not None and not _bs.empty:
                        _ca = _bs.loc['Current Assets'].dropna().iloc[0] if 'Current Assets' in _bs.index else 0
                        _cl = _bs.loc['Current Liabilities'].dropna().iloc[0] if 'Current Liabilities' in _bs.index else 0
                        if _cl and _cl > 0:
                            _cr = _cr or round(float(_ca / _cl), 3)
                            _inv = _bs.loc['Inventory'].dropna().iloc[0] if 'Inventory' in _bs.index else 0
                            _qr = _qr or round(float((_ca - _inv) / _cl), 3)
            except Exception:
                pass

        data.update({
            'debt_to_equity': info.get('debtToEquity', 0),
            'current_ratio': _cr,
            'quick_ratio': _qr,
            'total_cash': info.get('totalCash', 0),
            'total_debt': info.get('totalDebt', 0),
            'operating_cashflow': _ocf,
            'free_cashflow': _fcf
        })

        data['analyst_count'] = info.get('numberOfAnalystOpinions', 0) or 0
        
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
        
        # Piotroski F-Score and FCF yield
        data['piotroski_f_score'] = _calculate_piotroski(data, info, bundle)
        mcap = data.get('market_cap', 0)
        fcf = data.get('free_cashflow', 0)
        data['fcf_yield'] = round((fcf / mcap) * 100, 2) if mcap and mcap > 0 and fcf else 0.0

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
        'piotroski_f_score': 0,
        'fcf_yield': 0,
        'fundamental_score': 50,
        'fundamental_rating': 'Neutral',
        'fundamental_analysis': 'Insufficient data for analysis',
        'fundamental_data_failed': True
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
        debt_to_equity = data.get('debt_to_equity')
        current_ratio = data.get('current_ratio', 0)
        
        if debt_to_equity is not None and isinstance(debt_to_equity, (int, float)) and debt_to_equity > 0:
            if debt_to_equity < 30:
                score += 15
                analysis_points.append("Low debt levels")
            elif debt_to_equity < 60:
                score += 8
            elif debt_to_equity > 100:
                score -= 10
                analysis_points.append("High debt levels")
        # debt_to_equity is None, 0, or non-numeric (no data) — no score adjustment
        
        if current_ratio > 2:
            score += 10
            analysis_points.append("Strong liquidity")
        elif current_ratio > 1.5:
            score += 5
        elif current_ratio < 1:
            score -= 10
            analysis_points.append("Liquidity concerns")
        
        # Piotroski F-Score bonus (up to 8 points)
        f_score = data.get('piotroski_f_score', 0)
        if f_score >= 7:
            score += 8
            analysis_points.append(f"Strong Piotroski F-Score ({f_score}/9)")
        elif f_score >= 5:
            score += 4
        elif f_score <= 2:
            score -= 5
            analysis_points.append(f"Weak Piotroski F-Score ({f_score}/9)")

        # FCF Yield bonus (up to 5 points)
        fcf_yield = data.get('fcf_yield', 0)
        if fcf_yield > 8:
            score += 5
            analysis_points.append(f"High FCF yield ({fcf_yield:.1f}%)")
        elif fcf_yield > 4:
            score += 3
        elif fcf_yield < 0:
            score -= 3
            analysis_points.append("Negative FCF yield")
        
        # PE = -1 means loss-making
        if pe_ratio == -1:
            score -= 5
            analysis_points.append("Loss-making (negative EPS)")

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
