# Fundamental Analyzer: Extract metrics and compute score
import numpy as np
import pandas as pd
import logging
from config import FUNDAMENTAL_WEIGHTS

def safe_float(val):
    """Convert pandas Series or scalar to float"""
    if isinstance(val, pd.Series):
        return float(val.iloc[0]) if not val.empty else None
    return float(val) if val is not None else None

def extract_fundamental_metrics(info):
    """
    Extracts fundamental metrics from yfinance info dict.
    Returns: dict of metrics (with None for missing values)
    """
    metrics = {}
    
    # Comprehensive metrics mapping
    key_metrics = {
        # Company Overview
        'longBusinessSummary': 'business_summary',
        'sector': 'sector',
        'industry': 'industry',
        'fullTimeEmployees': 'employees',
        'website': 'website',
        
        # Financial Health
        'revenueGrowth': 'revenue_growth',
        'earningsGrowth': 'earnings_growth',
        'revenuePerShare': 'revenue_per_share',
        'grossMargins': 'gross_margin',
        'operatingMargins': 'operating_margin',
        'profitMargins': 'net_margin',
        'returnOnEquity': 'roe',
        'returnOnAssets': 'roa',
        'debtToEquity': 'debt_to_equity',
        'currentRatio': 'current_ratio',
        'quickRatio': 'quick_ratio',
        'operatingCashflow': 'operating_cashflow',
        'freeCashflow': 'free_cashflow',
        
        # Valuation Metrics
        'trailingPE': 'pe_ratio',
        'forwardPE': 'forward_pe',
        'priceToBook': 'pb_ratio',
        'enterpriseToEbitda': 'ev_ebitda',
        'enterpriseToRevenue': 'ev_revenue',
        'dividendYield': 'dividend_yield',
        'marketCap': 'market_cap',
        'enterpriseValue': 'enterprise_value',
        
        # Growth & Efficiency
        'earningsQuarterlyGrowth': 'quarterly_earnings_growth',
        'revenueQuarterlyGrowth': 'quarterly_revenue_growth',
        'pegRatio': 'peg_ratio',
        'priceToSalesTrailing12Months': 'ps_ratio',
        
        # Additional Metrics
        'beta': 'beta',
        'bookValue': 'book_value',
        'earningsPerShare': 'eps',
        'forwardEps': 'forward_eps',
        'sharesOutstanding': 'shares_outstanding',
        'heldPercentInsiders': 'insider_ownership',
        'heldPercentInstitutions': 'institutional_ownership'
    }
    
    # Extract and convert metrics
    for yf_key, our_key in key_metrics.items():
        value = info.get(yf_key)
        if value is not None:
            try:
                metrics[our_key] = safe_float(value)
            except (ValueError, TypeError) as e:
                logging.warning(f"Could not convert {yf_key}: {str(e)}")
                metrics[our_key] = None
        else:
            metrics[our_key] = None
    
    return metrics

def analyze_growth_potential(metrics):
    """
    Analyze company's growth potential and competitive position
    Returns: dict with growth analysis
    """
    analysis = {
        'growth_metrics': {
            'revenue_growth': metrics.get('revenue_growth'),
            'earnings_growth': metrics.get('earnings_growth'),
            'quarterly_revenue_growth': metrics.get('quarterly_revenue_growth'),
            'quarterly_earnings_growth': metrics.get('quarterly_earnings_growth')
        },
        'efficiency_metrics': {
            'roe': metrics.get('roe'),
            'roa': metrics.get('roa'),
            'operating_margin': metrics.get('operating_margin'),
            'net_margin': metrics.get('net_margin')
        },
        'valuation_metrics': {
            'peg_ratio': metrics.get('peg_ratio'),
            'forward_pe': metrics.get('forward_pe'),
            'ev_revenue': metrics.get('ev_revenue')
        }
    }
    
    # Growth Score (0-100)
    growth_score = 0
    if metrics.get('revenue_growth'):
        growth_score += min(max(metrics['revenue_growth'] * 100, 0), 30)
    if metrics.get('earnings_growth'):
        growth_score += min(max(metrics['earnings_growth'] * 100, 0), 40)
    if metrics.get('quarterly_earnings_growth'):
        growth_score += min(max(metrics['quarterly_earnings_growth'] * 100, 0), 30)
    
    analysis['growth_score'] = min(growth_score, 100)
    
    return analysis

def analyze_risks(metrics):
    """
    Analyze company's risk factors
    Returns: dict with risk analysis
    """
    risks = {
        'financial_risks': [],
        'market_risks': [],
        'efficiency_risks': [],
        'risk_score': 0  # 0-100, higher means more risky
    }
    
    # Financial Risk Analysis
    if metrics.get('debt_to_equity', 0) > 2:
        risks['financial_risks'].append('High debt levels')
        risks['risk_score'] += 20
    if metrics.get('current_ratio', 0) < 1:
        risks['financial_risks'].append('Poor liquidity')
        risks['risk_score'] += 15
    if metrics.get('operating_cashflow', 0) < 0:
        risks['financial_risks'].append('Negative operating cash flow')
        risks['risk_score'] += 25
        
    # Market Risk Analysis
    if metrics.get('beta', 1) > 1.5:
        risks['market_risks'].append('High market sensitivity')
        risks['risk_score'] += 10
    if metrics.get('institutional_ownership', 0) < 0.2:
        risks['market_risks'].append('Low institutional ownership')
        risks['risk_score'] += 5
        
    # Efficiency Risk Analysis
    if metrics.get('operating_margin', 0) < 0.05:
        risks['efficiency_risks'].append('Low operating margins')
        risks['risk_score'] += 15
    if metrics.get('roe', 0) < 0.08:
        risks['efficiency_risks'].append('Poor return on equity')
        risks['risk_score'] += 10
        
    risks['risk_score'] = min(risks['risk_score'], 100)
    return risks

def generate_investment_thesis(metrics, growth_analysis, risk_analysis):
    """
    Generate comprehensive investment thesis
    Returns: dict with bull and bear cases
    """
    thesis = {
        'bull_case': [],
        'bear_case': [],
        'short_term_outlook': None,  # 3-6 months
        'long_term_outlook': None,   # 3-5 years
        'buffett_analysis': None     # Would Warren Buffett invest?
    }
    
    # Bull Case Factors
    if metrics.get('revenue_growth', 0) > 0.15:
        thesis['bull_case'].append('Strong revenue growth')
    if metrics.get('operating_margin', 0) > 0.2:
        thesis['bull_case'].append('Excellent operating margins')
    if metrics.get('roe', 0) > 0.15:
        thesis['bull_case'].append('Strong return on equity')
    if growth_analysis['growth_score'] > 70:
        thesis['bull_case'].append('Compelling growth prospects')
        
    # Bear Case Factors
    if risk_analysis['risk_score'] > 60:
        thesis['bear_case'].append('High risk profile')
    if metrics.get('debt_to_equity', 0) > 2:
        thesis['bear_case'].append('High debt burden')
    if metrics.get('pe_ratio', 0) > 30:
        thesis['bear_case'].append('Rich valuation')
        
    # Outlook
    growth_score = growth_analysis['growth_score']
    risk_score = risk_analysis['risk_score']
    combined_score = growth_score - (risk_score * 0.5)
    
    thesis['short_term_outlook'] = 'Positive' if combined_score > 50 else 'Neutral' if combined_score > 30 else 'Negative'
    thesis['long_term_outlook'] = 'Positive' if growth_score > 60 and risk_score < 50 else 'Neutral' if growth_score > 40 else 'Negative'
    
    # Buffett Analysis
    buffett_criteria = {
        'consistent_earnings': metrics.get('earnings_growth', 0) > 0.07,
        'low_debt': metrics.get('debt_to_equity', float('inf')) < 1.5,
        'high_margins': metrics.get('operating_margin', 0) > 0.15,
        'strong_moat': metrics.get('roe', 0) > 0.15 and metrics.get('operating_margin', 0) > 0.2
    }
    
    if sum(buffett_criteria.values()) >= 3:
        thesis['buffett_analysis'] = "Likely to interest Buffett due to " + ", ".join(k for k, v in buffett_criteria.items() if v)
    else:
        thesis['buffett_analysis'] = "Unlikely to interest Buffett due to " + ", ".join(k for k, v in buffett_criteria.items() if not v)
    
    return thesis

def compute_fundamental_score(metrics):
    """
    Compute a 0-100 fundamental score based on weighted metrics.
    """
    score = 0
    total_weight = sum(FUNDAMENTAL_WEIGHTS.values())
    
    # Profitability Metrics (30% of total score)
    if metrics.get('roe') is not None:
        score += min(max(metrics['roe'], 0), 0.25) / 0.25 * FUNDAMENTAL_WEIGHTS.get('roe', 10)
    
    if metrics.get('operating_margin') is not None:
        score += min(max(metrics['operating_margin'], 0), 0.3) / 0.3 * FUNDAMENTAL_WEIGHTS.get('operating_margin', 10)
        
    if metrics.get('net_margin') is not None:
        score += min(max(metrics['net_margin'], 0), 0.2) / 0.2 * FUNDAMENTAL_WEIGHTS.get('net_margin', 10)
        
    # Growth Metrics (25% of total score)
    if metrics.get('revenue_growth') is not None:
        score += min(max(metrics['revenue_growth'], 0), 0.3) / 0.3 * FUNDAMENTAL_WEIGHTS.get('revenue_growth', 8)
        
    if metrics.get('earnings_growth') is not None:
        score += min(max(metrics['earnings_growth'], 0), 0.3) / 0.3 * FUNDAMENTAL_WEIGHTS.get('earnings_growth', 9)
        
    if metrics.get('quarterly_earnings_growth') is not None:
        score += min(max(metrics['quarterly_earnings_growth'], 0), 0.3) / 0.3 * FUNDAMENTAL_WEIGHTS.get('quarterly_growth', 8)
        
    # Valuation Metrics (25% of total score)
    if metrics.get('pe_ratio') is not None and metrics['pe_ratio'] > 0:
        score += min(25/metrics['pe_ratio'], 1) * FUNDAMENTAL_WEIGHTS.get('pe_ratio', 8)
        
    if metrics.get('pb_ratio') is not None and metrics['pb_ratio'] > 0:
        score += min(4/metrics['pb_ratio'], 1) * FUNDAMENTAL_WEIGHTS.get('pb_ratio', 8)
        
    if metrics.get('ev_ebitda') is not None and metrics['ev_ebitda'] > 0:
        score += min(15/metrics['ev_ebitda'], 1) * FUNDAMENTAL_WEIGHTS.get('ev_ebitda', 9)
        
    # Financial Health Metrics (20% of total score)
    if metrics.get('debt_to_equity') is not None and metrics['debt_to_equity'] > 0:
        score += min(2/metrics['debt_to_equity'], 1) * FUNDAMENTAL_WEIGHTS.get('debt_to_equity', 5)
        
    if metrics.get('current_ratio') is not None:
        score += min(max(metrics['current_ratio'], 1), 3) / 3 * FUNDAMENTAL_WEIGHTS.get('current_ratio', 5)
        
    if metrics.get('operating_cashflow') is not None:
        normalized_ocf = metrics['operating_cashflow'] / (metrics.get('market_cap', 1) or 1)
        score += min(max(normalized_ocf, 0), 0.2) / 0.2 * FUNDAMENTAL_WEIGHTS.get('operating_cashflow', 5)
        
    if metrics.get('dividend_yield') is not None:
        score += min(max(metrics['dividend_yield'], 0), 0.08) / 0.08 * FUNDAMENTAL_WEIGHTS.get('dividend_yield', 5)
    
    normalized_score = round(score / total_weight * 100, 2)
    
    # Add score interpretation
    interpretation = {
        'score': normalized_score,
        'rating': 'Strong Buy' if normalized_score >= 80 else
                 'Buy' if normalized_score >= 60 else
                 'Hold' if normalized_score >= 40 else
                 'Sell' if normalized_score >= 20 else 'Strong Sell',
        'strengths': [],
        'weaknesses': []
    }
    
    # Identify key strengths and weaknesses
    if metrics.get('roe', 0) > 0.15:
        interpretation['strengths'].append('Strong ROE')
    if metrics.get('debt_to_equity', float('inf')) > 2:
        interpretation['weaknesses'].append('High Debt')
    if metrics.get('operating_margin', 0) > 0.2:
        interpretation['strengths'].append('Excellent Margins')
    if metrics.get('revenue_growth', 0) > 0.15:
        interpretation['strengths'].append('Strong Growth')
    if metrics.get('pe_ratio', float('inf')) > 30:
        interpretation['weaknesses'].append('Rich Valuation')
    
    return interpretation

def compare_with_peers(stock_metrics, peer_symbols):
    """
    Compare company metrics with peers
    Returns: dict with comparative analysis
    """
    comparison = {
        'metrics': {
            'growth': {
                'revenue_growth': [],
                'earnings_growth': []
            },
            'profitability': {
                'operating_margin': [],
                'net_margin': [],
                'roe': []
            },
            'valuation': {
                'pe_ratio': [],
                'pb_ratio': [],
                'ev_ebitda': []
            },
            'financial_health': {
                'debt_to_equity': [],
                'current_ratio': [],
                'quick_ratio': []
            }
        },
        'rankings': {},
        'peer_analysis': None
    }
    
    # Add the main stock's metrics
    for category in comparison['metrics']:
        for metric in comparison['metrics'][category]:
            if metric in stock_metrics:
                comparison['metrics'][category][metric].append({
                    'symbol': 'TARGET',
                    'value': stock_metrics[metric]
                })
    
    # Calculate rankings
    for category in comparison['metrics']:
        for metric in comparison['metrics'][category]:
            values = [item['value'] for item in comparison['metrics'][category][metric] if item['value'] is not None]
            if values:
                comparison['rankings'][metric] = {
                    'avg': sum(values) / len(values),
                    'median': sorted(values)[len(values)//2],
                    'percentile': (sorted(values).index(stock_metrics.get(metric, 0)) + 1) / len(values) * 100
                }
    
    # Generate peer analysis summary
    strengths = []
    weaknesses = []
    for metric, ranking in comparison['rankings'].items():
        if ranking['percentile'] >= 75:
            strengths.append(f"Top quartile in {metric}")
        elif ranking['percentile'] <= 25:
            weaknesses.append(f"Bottom quartile in {metric}")
    
    comparison['peer_analysis'] = {
        'strengths': strengths,
        'weaknesses': weaknesses,
        'summary': f"Relative to peers, the company shows {len(strengths)} areas of strength and {len(weaknesses)} areas needing improvement."
    }
    
    return comparison
