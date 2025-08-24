# Stock Screener: Find and suggest similar stocks
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import logging
from config import LOG_FILE
from technical_analyzer import calculate_indicators, compute_technical_score
from fundamental_analyzer import extract_fundamental_metrics, compute_fundamental_score
from news_analyzer import get_stock_news

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")

class StockScreener:
    def __init__(self):
        # Define sector mappings
        self.sector_mapping = {
            'Technology': ['IT', 'Software', 'Electronics', 'Digital Services'],
            'Finance': ['Banking', 'Insurance', 'Financial Services', 'NBFCs'],
            'Healthcare': ['Pharmaceuticals', 'Hospitals', 'Medical Equipment'],
            'Consumer': ['FMCG', 'Retail', 'Consumer Durables'],
            'Manufacturing': ['Auto', 'Capital Goods', 'Engineering'],
            'Energy': ['Oil & Gas', 'Power', 'Renewable Energy'],
            'Materials': ['Metals', 'Chemicals', 'Mining'],
            'Infrastructure': ['Construction', 'Real Estate', 'Cement']
        }

    def get_sector_peers(self, symbol):
        """Get list of stocks in the same sector"""
        try:
            stock = yf.Ticker(symbol)
            sector = stock.info.get('sector')
            if not sector:
                return []
                
            # Find related sectors
            related_sectors = []
            for main_sector, subsectors in self.sector_mapping.items():
                if any(s.lower() in sector.lower() for s in [main_sector] + subsectors):
                    related_sectors.extend(subsectors)
            
            # Get all stocks in related sectors
            # This will use our existing NIFTY_STOCKS list from nse_scraper
            from nse_scraper import NIFTY_STOCKS
            peers = []
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_symbol = {
                    executor.submit(self._get_stock_info, s): s 
                    for s in NIFTY_STOCKS if s != f"{symbol}.NS"
                }
                
                for future in future_to_symbol:
                    try:
                        result = future.result()
                        if result and result.get('sector'):
                            if any(s.lower() in result['sector'].lower() 
                                  for s in related_sectors):
                                peers.append(result['symbol'])
                    except Exception as e:
                        logging.error(f"Error processing peer: {str(e)}")
            
            return peers
            
        except Exception as e:
            logging.error(f"Error getting sector peers: {str(e)}")
            return []

    def _get_stock_info(self, symbol):
        """Helper function to get stock info"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            if info:
                return {
                    'symbol': symbol.replace('.NS', ''),
                    'sector': info.get('sector', ''),
                    'industry': info.get('industry', '')
                }
        except Exception:
            pass
        return None

    def screen_by_criteria(self, base_stock, criteria=None):
        """
        Screen stocks based on specified criteria
        Returns: DataFrame with screened stocks
        """
        if criteria is None:
            criteria = {
                'min_market_cap': 1000000000,  # 1B minimum
                'min_revenue_growth': 0.1,      # 10% minimum
                'max_pe': 30,                   # PE ratio cap
                'min_profit_margin': 0.1,       # 10% minimum
                'max_debt_to_equity': 2.0       # Leverage cap
            }
        
        try:
            # Get peers in the same sector
            peers = self.get_sector_peers(base_stock)
            if not peers:
                return pd.DataFrame()
            
            results = []
            base_metrics = self._get_complete_metrics(base_stock)
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_symbol = {
                    executor.submit(self._get_complete_metrics, symbol): symbol 
                    for symbol in peers
                }
                
                for future in future_to_symbol:
                    try:
                        metrics = future.result()
                        if self._meets_criteria(metrics, criteria):
                            results.append(metrics)
                    except Exception as e:
                        logging.error(f"Error in screening: {str(e)}")
            
            # Convert to DataFrame and sort
            df = pd.DataFrame(results)
            if not df.empty:
                df = self._rank_stocks(df, base_metrics)
            
            return df
            
        except Exception as e:
            logging.error(f"Error in screen_by_criteria: {str(e)}")
            return pd.DataFrame()

    def _get_complete_metrics(self, symbol):
        """Get comprehensive metrics for a stock"""
        try:
            stock = yf.Ticker(f"{symbol}.NS" if not symbol.endswith('.NS') else symbol)
            info = stock.info
            
            # Get fundamental metrics
            fundamental_metrics = extract_fundamental_metrics(info)
            fundamental_score = compute_fundamental_score(fundamental_metrics)
            
            # Get technical metrics
            hist = stock.history(period="1y")
            if not hist.empty:
                technical_metrics = calculate_indicators(hist)
                technical_score = compute_technical_score(technical_metrics)
            else:
                technical_score = 0
            
            # Get basic info
            metrics = {
                'symbol': symbol.replace('.NS', ''),
                'name': info.get('longName', symbol),
                'market_cap': info.get('marketCap', 0),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'fundamental_score': fundamental_score,
                'technical_score': technical_score,
                'combined_score': (fundamental_score + technical_score) / 2
            }
            
            # Add fundamental metrics
            metrics.update(fundamental_metrics)
            
            return metrics
            
        except Exception as e:
            logging.error(f"Error getting metrics for {symbol}: {str(e)}")
            return None

    def _meets_criteria(self, metrics, criteria):
        """Check if stock meets screening criteria"""
        if not metrics:
            return False
            
        try:
            checks = [
                metrics.get('market_cap', 0) >= criteria['min_market_cap'],
                metrics.get('revenue_growth', 0) >= criteria['min_revenue_growth'],
                metrics.get('pe_ratio', float('inf')) <= criteria['max_pe'],
                metrics.get('net_margin', 0) >= criteria['min_profit_margin'],
                metrics.get('debt_to_equity', float('inf')) <= criteria['max_debt_to_equity']
            ]
            
            return all(checks)
            
        except Exception:
            return False

    def _rank_stocks(self, df, base_metrics):
        """Rank stocks based on similarity to base stock"""
        try:
            # Calculate similarity scores
            df['similarity_score'] = df.apply(
                lambda row: self._calculate_similarity(row, base_metrics), axis=1
            )
            
            # Sort by similarity and combined score
            df['final_rank'] = (
                df['similarity_score'] * 0.4 + 
                df['fundamental_score'] * 0.35 + 
                df['technical_score'] * 0.25
            )
            
            return df.sort_values('final_rank', ascending=False)
            
        except Exception as e:
            logging.error(f"Error in ranking: {str(e)}")
            return df

    def _calculate_similarity(self, stock_metrics, base_metrics):
        """Calculate similarity between two stocks"""
        try:
            # Metrics to compare
            compare_metrics = [
                'pe_ratio', 'revenue_growth', 'profit_margin',
                'debt_to_equity', 'market_cap'
            ]
            
            similarities = []
            for metric in compare_metrics:
                base_val = base_metrics.get(metric)
                comp_val = stock_metrics.get(metric)
                
                if base_val and comp_val:
                    # Calculate normalized difference
                    max_val = max(abs(base_val), abs(comp_val))
                    if max_val != 0:
                        similarity = 1 - abs(base_val - comp_val) / max_val
                        similarities.append(similarity)
            
            return np.mean(similarities) if similarities else 0
            
        except Exception as e:
            logging.error(f"Error calculating similarity: {str(e)}")
            return 0

    def suggest_alternatives(self, symbol, num_suggestions=5):
        """
        Suggest alternative stocks similar to the given stock
        Returns: DataFrame with top suggestions
        """
        try:
            # Get base stock metrics
            base_metrics = self._get_complete_metrics(symbol)
            if not base_metrics:
                return pd.DataFrame()
            
            # Define screening criteria based on base stock
            criteria = {
                'min_market_cap': base_metrics.get('market_cap', 0) * 0.3,  # At least 30% of base
                'min_revenue_growth': max(0, base_metrics.get('revenue_growth', 0) - 0.1),
                'max_pe': base_metrics.get('pe_ratio', 30) * 1.5,
                'min_profit_margin': max(0, base_metrics.get('profit_margin', 0) - 0.05),
                'max_debt_to_equity': base_metrics.get('debt_to_equity', 2) * 1.5
            }
            
            # Screen and rank stocks
            results = self.screen_by_criteria(symbol, criteria)
            
            if results.empty:
                return pd.DataFrame()
            
            # Select top suggestions and format output
            suggestions = results.head(num_suggestions)
            
            return suggestions[['symbol', 'name', 'sector', 'fundamental_score', 
                              'technical_score', 'combined_score', 'similarity_score']]
                              
        except Exception as e:
            logging.error(f"Error suggesting alternatives: {str(e)}")
            return pd.DataFrame()
