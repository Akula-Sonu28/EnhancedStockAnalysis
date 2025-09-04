# Stock Analyzer Dashboard: Comprehensive stock analysis tool
import yfinance as yf
import pandas as pd
from datetime import datetime
import logging
from config import LOG_FILE
from technical_analyzer import calculate_indicators, compute_technical_score, generate_technical_summary
from fundamental_analyzer import (
    extract_fundamental_metrics, compute_fundamental_score, analyze_growth_potential,
    analyze_risks, generate_investment_thesis, compare_with_peers
)
from news_analyzer import generate_news_summary
from stock_screener import StockScreener
import json

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

class StockAnalyzerDashboard:
    def __init__(self):
        self.screener = StockScreener()
        
    def generate_complete_analysis(self, symbol, export_format='dict'):
        """
        Generate comprehensive stock analysis including technical, fundamental,
        news analysis and alternative suggestions.
        
        Parameters:
        - symbol: Stock symbol (e.g., 'RELIANCE')
        - export_format: 'dict', 'json', or 'df' for DataFrame
        
        Returns: Complete analysis in specified format
        """
        try:
            print("Starting complete analysis...")
            
            # Normalize symbol
            symbol = symbol.replace('.NS', '')
            stock = yf.Ticker(f"{symbol}.NS")
            print(f"Created Ticker object for {symbol}")
            
            # Get basic info with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"Fetching stock info (attempt {attempt + 1})...")
                    info = stock.info
                    if info and len(info) > 0:
                        print("Successfully fetched stock info")
                        break
                    else:
                        print("Empty info received")
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        raise
            
            if not info or len(info) == 0:
                logging.error(f"Could not fetch info for {symbol}")
                return None
                
            print("Starting analysis components...")
            
            # 1. Company Overview
            print("Generating company overview...")
            overview = self._get_company_overview(info)
            if not overview:
                print("Failed to generate company overview")
                return None
            print("Company overview generated successfully")
            
            # 2. Technical Analysis
            print("Starting technical analysis...")
            technical = self._get_technical_analysis(stock)
            if not technical:
                print("Failed to generate technical analysis")
                return None
            print("Technical analysis completed successfully")
            
            # 3. Fundamental Analysis
            print("Starting fundamental analysis...")
            fundamental = self._get_fundamental_analysis(info)
            if not fundamental:
                print("Failed to generate fundamental analysis")
                return None
            print("Fundamental analysis completed successfully")
            
            # 4. News & Sentiment
            news = generate_news_summary(symbol)
            
            # 5. Peer Analysis & Alternatives
            peer_analysis = self._get_peer_analysis(symbol)
            
            # Combine all analyses
            analysis = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol,
                'name': info.get('longName', symbol),
                'overview': overview,
                'technical_analysis': technical,
                'fundamental_analysis': fundamental,
                'news_sentiment': news,
                'peer_analysis': peer_analysis,
                'summary': self._generate_executive_summary(
                    technical, fundamental, news, peer_analysis
                )
            }
            
            # Format output
            if export_format == 'json':
                return json.dumps(analysis, indent=2)
            elif export_format == 'df':
                return pd.json_normalize(analysis)
            else:
                return analysis
                
        except Exception as e:
            logging.error(f"Error generating analysis for {symbol}: {str(e)}")
            return None
            
    def _get_company_overview(self, info):
        """Generate company overview"""
        return {
            'business_model': {
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'business_summary': info.get('longBusinessSummary', 'N/A'),
                'website': info.get('website', 'N/A'),
                'employees': info.get('fullTimeEmployees', 'N/A')
            },
            'key_stats': {
                'market_cap': info.get('marketCap', 'N/A'),
                'enterprise_value': info.get('enterpriseValue', 'N/A'),
                'shares_outstanding': info.get('sharesOutstanding', 'N/A'),
                'float_shares': info.get('floatShares', 'N/A'),
                'beta': info.get('beta', 'N/A')
            },
            'corporate_governance': {
                'insider_ownership': info.get('heldPercentInsiders', 'N/A'),
                'institutional_ownership': info.get('heldPercentInstitutions', 'N/A')
            }
        }
        
    def _get_technical_analysis(self, stock):
        """Generate technical analysis"""
        try:
            print("Fetching historical data...")
            hist = stock.history(period="1y")
            if hist.empty:
                print("No historical data available")
                return None
            print(f"Got {len(hist)} historical data points")
            
            print("Calculating technical indicators...")
            indicators = calculate_indicators(hist)
            if not indicators:
                print("Failed to calculate indicators")
                return None
            print("Technical indicators calculated successfully")
            
            print("Computing technical score...")
            score, analysis = compute_technical_score(indicators)
            print(f"Technical score computed: {score}")
            
            print("Generating technical summary...")
            summary = generate_technical_summary(indicators)
            if not summary:
                print("Failed to generate technical summary")
                return None
            print("Technical summary generated successfully")
            
            print("Preparing final technical analysis...")
            return {
                'indicators': indicators,
                'technical_score': score,
                'analysis': analysis,
                'summary': summary,
                'support_resistance': {
                    'support_levels': indicators.get('support_levels', []),
                    'resistance_levels': indicators.get('resistance_levels', [])
                },
                'trading_plan': self._generate_trading_plan(indicators)
            }
            
        except Exception as e:
            print(f"Error in technical analysis: {str(e)}")
            return None
        
    def _get_fundamental_analysis(self, info):
        """Generate fundamental analysis"""
        metrics = extract_fundamental_metrics(info)
        score = compute_fundamental_score(metrics)
        growth = analyze_growth_potential(metrics)
        risks = analyze_risks(metrics)
        thesis = generate_investment_thesis(metrics, growth, risks)
        
        return {
            'metrics': metrics,
            'fundamental_score': score,
            'growth_analysis': growth,
            'risk_analysis': risks,
            'investment_thesis': thesis,
            'financial_health': self._analyze_financial_health(metrics)
        }
        
    def _get_peer_analysis(self, symbol):
        """Generate peer analysis and alternatives"""
        peer_metrics = compare_with_peers(symbol)
        alternatives = self.screener.suggest_alternatives(symbol)
        
        return {
            'peer_comparison': peer_metrics,
            'alternative_stocks': alternatives.to_dict('records') if not alternatives.empty else [],
            'sector_position': self._analyze_sector_position(symbol, peer_metrics)
        }
        
    def _generate_trading_plan(self, indicators):
        """Generate trading plan based on technical indicators"""
        current_price = indicators['Close']
        
        # Define entry points
        entry_points = []
        for support in indicators.get('support_levels', []):
            if support < current_price:
                entry_points.append({
                    'type': 'Support',
                    'price': support,
                    'strength': 'Strong' if abs(current_price - support) / current_price < 0.05 else 'Moderate'
                })
        
        # Define target points
        target_points = []
        for resistance in indicators.get('resistance_levels', []):
            if resistance > current_price:
                target_points.append({
                    'type': 'Resistance',
                    'price': resistance,
                    'strength': 'Strong' if abs(current_price - resistance) / current_price < 0.05 else 'Moderate'
                })
        
        # Calculate stop loss
        stop_loss = min(indicators.get('support_levels', [current_price * 0.95])[0], current_price * 0.95)
        
        return {
            'entry_points': entry_points,
            'target_points': target_points,
            'stop_loss': stop_loss,
            'risk_reward_ratio': round((target_points[0]['price'] - current_price) / (current_price - stop_loss), 2) if target_points else round((current_price * 1.05 - current_price) / (current_price - stop_loss), 2),
            'trade_type': 'Long' if indicators.get('trend') in ['Strong Uptrend', 'Uptrend'] else 
                         'Short' if indicators.get('trend') in ['Strong Downtrend', 'Downtrend'] else 'Neutral'
        }
        
    def _analyze_financial_health(self, metrics):
        """Detailed financial health analysis"""
        return {
            'profitability': {
                'gross_margin': metrics.get('gross_margin'),
                'operating_margin': metrics.get('operating_margin'),
                'net_margin': metrics.get('net_margin'),
                'roe': metrics.get('roe'),
                'roa': metrics.get('roa')
            },
            'liquidity': {
                'current_ratio': metrics.get('current_ratio'),
                'quick_ratio': metrics.get('quick_ratio'),
                'cash_ratio': metrics.get('cash_ratio')
            },
            'solvency': {
                'debt_to_equity': metrics.get('debt_to_equity'),
                'interest_coverage': metrics.get('interest_coverage'),
                'debt_service_coverage': metrics.get('debt_service_coverage')
            },
            'efficiency': {
                'asset_turnover': metrics.get('asset_turnover'),
                'inventory_turnover': metrics.get('inventory_turnover'),
                'receivables_turnover': metrics.get('receivables_turnover')
            }
        }
        
    def _analyze_sector_position(self, symbol, peer_metrics):
        """Analyze company's position in its sector"""
        rankings = peer_metrics.get('rankings', {})
        return {
            'market_position': {
                'market_share': rankings.get('market_share', 'N/A'),
                'revenue_rank': rankings.get('revenue_rank', 'N/A'),
                'profitability_rank': rankings.get('profitability_rank', 'N/A')
            },
            'competitive_advantages': peer_metrics.get('peer_analysis', {}).get('strengths', []),
            'competitive_disadvantages': peer_metrics.get('peer_analysis', {}).get('weaknesses', [])
        }
        
    def _generate_executive_summary(self, technical, fundamental, news, peer_analysis):
        """Generate executive summary of all analyses"""
        # Combine scores
        technical_score = technical.get('technical_score', 0)
        fundamental_score = fundamental.get('fundamental_score', {}).get('score', 0)
        sentiment_score = news.get('sentiment_analysis', {}).get('overall_score', 5) * 10
        
        overall_score = (technical_score * 0.3 + 
                        fundamental_score * 0.4 + 
                        sentiment_score * 0.3)
        
        rating = ('Strong Buy' if overall_score >= 80 else
                 'Buy' if overall_score >= 60 else
                 'Hold' if overall_score >= 40 else
                 'Sell' if overall_score >= 20 else 'Strong Sell')
        
        return {
            'overall_score': round(overall_score, 2),
            'rating': rating,
            'technical_outlook': technical.get('analysis', 'N/A'),
            'fundamental_outlook': fundamental.get('investment_thesis', {}).get('long_term_outlook', 'N/A'),
            'market_sentiment': news.get('sentiment_analysis', {}).get('interpretation', 'N/A'),
            'key_strengths': fundamental.get('investment_thesis', {}).get('bull_case', []),
            'key_risks': fundamental.get('risk_analysis', {}).get('financial_risks', []),
            'recommendation': f"{rating} - {self._generate_recommendation_text(overall_score, technical, fundamental, news)}"
        }
        
    def _generate_recommendation_text(self, overall_score, technical, fundamental, news):
        """Generate detailed recommendation text"""
        if overall_score >= 80:
            return "Strong fundamentals, positive technicals, and favorable market sentiment suggest significant upside potential"
        elif overall_score >= 60:
            return "Solid fundamentals with some technical support indicate good investment opportunity"
        elif overall_score >= 40:
            return "Mixed signals suggest waiting for better entry points or reducing exposure"
        elif overall_score >= 20:
            return "Weak fundamentals and deteriorating technicals indicate reducing positions"
        else:
            return "Significant risks and negative indicators suggest avoiding or exiting positions"
