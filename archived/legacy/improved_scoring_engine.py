"""
IMPROVED SCORING ENGINE V3.0
Based on backtest optimization results

KEY CHANGES:
1. REMOVED contrarian_technical (was -60% correlation!)
2. REMOVED value_opportunity (was -28% correlation!)
3. KEPT fundamental_quality (+28% correlation)
4. KEPT contrarian_momentum (+5.5% spread)
5. ADDED momentum_technical (INVERTED from old contrarian - high RSI = good)
6. ADDED quality_multiplier (good companies deserve premium)
"""

import pandas as pd
import numpy as np
from datetime import datetime

class ImprovedScoringEngine:
    """
    Improved scoring based on what ACTUALLY predicts returns
    """
    
    def __init__(self, risk_profile='moderate'):
        # NEW WEIGHTS - adjusted by risk profile
        if risk_profile == 'aggressive':
            self.component_weights = {
                'fundamental_quality': 0.20,      # Less focus on fundamentals
                'momentum_technical': 0.40,       # High focus on momentum
                'contrarian_momentum': 0.30,      # Now measures momentum strength
                'quality_multiplier': 0.10        # Reward good companies
            }
        elif risk_profile == 'conservative':
            self.component_weights = {
                'fundamental_quality': 0.50,      # High focus on fundamentals
                'momentum_technical': 0.20,       # Lower focus on momentum
                'contrarian_momentum': 0.15,      # Lower focus on momentum strength
                'quality_multiplier': 0.15        # Reward good companies
            }
        else: # moderate
            self.component_weights = {
                'fundamental_quality': 0.40,      # Original was best predictor
                'momentum_technical': 0.30,       # Follow momentum, not contrarian
                'contrarian_momentum': 0.20,      # Now measures momentum strength
                'quality_multiplier': 0.10        # Reward good companies
            }
        
        # Sector multipliers (keep from before)
        self.sector_multipliers = {
            'Banking': 1.00,        # Changed from 0.85 (was penalizing banks)
            'Financial Services': 1.15,
            'Capital Goods': 1.10,
            'Consumer Durables': 1.05,
            'IT': 1.05,
            'Pharma': 1.00,
            'Auto': 1.00,
            'FMCG': 0.95,
            'default': 1.00
        }
    
    def calculate_momentum_technical_score(self, stock_data):
        """
        MOMENTUM APPROACH (opposite of old contrarian)
        High RSI = Strong stock = GOOD
        Rising price = Momentum = GOOD
        """
        score = 50  # Start neutral
        
        try:
            # RSI - HIGH is good (not low!)
            rsi = stock_data.get('enhanced_rsi_14') or stock_data.get('real_rsi', 50)
            if pd.notna(rsi):
                if rsi > 60:      # Strong momentum
                    score += 20
                elif rsi > 50:    # Positive momentum
                    score += 10
                elif rsi < 30:    # Oversold (AVOID, not buy!)
                    score -= 20
                elif rsi < 40:    # Weak
                    score -= 10
            
            # Price trend - Rising is GOOD
            price_change_20d = stock_data.get('enhanced_price_change_20d', 0)
            if pd.notna(price_change_20d):
                if price_change_20d > 5:      # Strong uptrend
                    score += 15
                elif price_change_20d > 2:    # Uptrend
                    score += 8
                elif price_change_20d < -5:   # Downtrend (AVOID)
                    score -= 15
                elif price_change_20d < -2:   # Weak
                    score -= 8
            
            # MACD - Positive is GOOD
            macd_histogram = stock_data.get('enhanced_macd_histogram', 0)
            if pd.notna(macd_histogram):
                if macd_histogram > 0:
                    score += 10
                else:
                    score -= 10
            
            # Volume trend - Rising volume with rising price is GOOD
            volume_ratio = stock_data.get('enhanced_volume_ratio', 1.0)
            if pd.notna(volume_ratio) and price_change_20d > 0:
                if volume_ratio > 1.2:    # High volume on up move
                    score += 5
            
            score = max(0, min(100, score))
            return score if not np.isnan(score) else 50
            
        except Exception as e:
            return 50
    
    def calculate_contrarian_momentum_score(self, stock_data):
        """
        TREND STRENGTH — reward uptrends, penalize downtrends.
        Strong uptrend with volume confirmation = GOOD
        Flat/sideways or downtrend = BAD
        """
        score = 50
        
        try:
            price_change_20d = stock_data.get('enhanced_price_change_20d', 0)
            if pd.notna(price_change_20d):
                # Halved vs momentum to reduce overlap with calculate_momentum_technical_score
                if price_change_20d >= 15:
                    score += 12
                elif price_change_20d >= 8:
                    score += 10
                elif price_change_20d >= 3:
                    score += 6
                elif price_change_20d >= -1:
                    score += 0
                elif price_change_20d >= -5:
                    score -= 5
                elif price_change_20d >= -10:
                    score -= 9
                else:
                    score -= 12

            # Volume surge — confirms trend validity
            volume_ratio = stock_data.get('enhanced_volume_ratio', 1.0)
            if pd.notna(volume_ratio):
                if volume_ratio > 1.5:    # Strong volume surge
                    score += 15
                elif volume_ratio > 1.2:  # Above-average volume
                    score += 8
                elif volume_ratio < 0.7:  # Low volume — weak trend
                    score -= 10

            # ADX (trend strength) — if available
            adx = stock_data.get('enhanced_adx', stock_data.get('adx_14', 0))
            if pd.notna(adx) and adx > 0:
                if adx > 30:             # Strong trend
                    score += 10
                elif adx > 20:           # Moderate trend
                    score += 5
                elif adx < 15:           # No trend
                    score -= 10
            
            score = max(0, min(100, score))
            return score if not np.isnan(score) else 50
            
        except Exception as e:
            return 50
    
    def calculate_fundamental_quality_score(self, stock_data):
        """
        FUNDAMENTAL QUALITY - Keep this (best predictor +28% correlation)
        Good fundamentals = GOOD returns
        """
        score = 50
        
        try:
            # PE Ratio - Lower is better (but not too low)
            pe_ratio = stock_data.get('pe_ratio')
            if pd.notna(pe_ratio) and pe_ratio > 0:
                if 10 <= pe_ratio <= 20:      # Sweet spot
                    score += 20
                elif 8 <= pe_ratio < 10 or 20 < pe_ratio <= 25:
                    score += 10
                elif pe_ratio > 40:           # Too expensive
                    score -= 15
                elif pe_ratio < 5:            # Value trap
                    score -= 10
            
            # ROE - Higher is better
            roe = stock_data.get('roe', 0)
            if pd.notna(roe):
                if roe > 20:       # Excellent
                    score += 20
                elif roe > 15:     # Good
                    score += 15
                elif roe > 10:     # Okay
                    score += 8
                elif roe < 5:      # Poor
                    score -= 15
            
            # Debt to Equity - Lower is better
            debt_to_equity = stock_data.get('debt_to_equity', 0)
            if pd.notna(debt_to_equity):
                if debt_to_equity < 50:       # Very low debt
                    score += 15
                elif debt_to_equity < 100:    # Moderate debt
                    score += 8
                elif debt_to_equity > 200:    # High debt
                    score -= 15
                elif debt_to_equity > 150:    # Elevated debt
                    score -= 8
            
            # PB Ratio - Lower is better
            pb_ratio = stock_data.get('pb_ratio', 0)
            if pd.notna(pb_ratio) and pb_ratio > 0:
                if pb_ratio < 2:       # Undervalued
                    score += 10
                elif pb_ratio < 3:     # Fair
                    score += 5
                elif pb_ratio > 5:     # Overvalued
                    score -= 10
            
            score = max(0, min(100, score))
            return score if not np.isnan(score) else 50
            
        except Exception as e:
            return 50
    
    def calculate_quality_multiplier(self, stock_data):
        """
        QUALITY PREMIUM - Reward consistently good companies
        Multiple quality signals = Higher confidence
        """
        score = 50
        quality_signals = 0
        
        try:
            # High ROE
            roe = stock_data.get('roe', 0)
            if pd.notna(roe) and roe > 15:
                quality_signals += 1
            
            # Low debt
            debt_to_equity = stock_data.get('debt_to_equity', 999)
            if pd.notna(debt_to_equity) and debt_to_equity < 100:
                quality_signals += 1
            
            # Reasonable PE (not value trap, not bubble)
            pe_ratio = stock_data.get('pe_ratio', 0)
            if pd.notna(pe_ratio) and 8 <= pe_ratio <= 30:
                quality_signals += 1
            
            # Good margins
            net_margin = stock_data.get('net_margin', 0)
            if pd.notna(net_margin) and net_margin > 10:
                quality_signals += 1
            
            # Growth
            revenue_growth = stock_data.get('revenue_growth', 0)
            if pd.notna(revenue_growth) and revenue_growth > 10:
                quality_signals += 1
            
            # Award points for each quality signal
            score = 50 + (quality_signals * 10)  # 0-5 signals = 50-100 score
            
            score = max(0, min(100, score))
            return score if not np.isnan(score) else 50
            
        except Exception as e:
            return 50
    
    def get_sector_classification(self, symbol):
        """Get sector for the stock"""
        sector_map = {
            'HDFCBANK': 'Banking', 'ICICIBANK': 'Banking', 'SBIN': 'Banking',
            'KOTAKBANK': 'Banking', 'AXISBANK': 'Banking', 'INDUSINDBK': 'Banking',
            'FEDERALBNK': 'Banking', 'BANDHANBNK': 'Banking', 'IDFCFIRSTB': 'Banking',
            'PNB': 'Banking', 'CANBK': 'Banking', 'BANKBARODA': 'Banking',
            'UNIONBANK': 'Banking', 'INDIANB': 'Banking', 'BANKINDIA': 'Banking',
            'MAHABANK': 'Banking', 'CUB': 'Banking', 'KARURVYSYA': 'Banking',
            'J&KBANK': 'Banking', 'CENTRALBK': 'Banking', 'IDBI': 'Banking',
            'YESBANK': 'Banking', 'UCOBANK': 'Banking', 'IOB': 'Banking',
            'AUBANK': 'Banking',
            
            'BAJFINANCE': 'Financial Services', 'BAJAJFINSV': 'Financial Services',
            'CHOLAFIN': 'Financial Services', 'MUTHOOTFIN': 'Financial Services',
            'UJJIVANSFB': 'Financial Services', 'LICHSGFIN': 'Financial Services',
            'RECLTD': 'Financial Services', 'PFC': 'Financial Services',
            'ICICIGI': 'Financial Services', 'GICRE': 'Financial Services',
            
            'BAJAJHLDNG': 'Financial Services',
            'DRREDDY': 'Pharma',
            'NMDC': 'Capital Goods'
        }
        return sector_map.get(symbol, 'default')
    
    def calculate_sector_adjustment(self, symbol, base_score, stock_data=None):
        """Apply sector multiplier — prefer live sector from stock_data"""
        if stock_data and stock_data.get('sector'):
            live = str(stock_data['sector'] or '').lower()
            live_map = {
                'financial services': 'Financial Services', 'banks': 'Banking',
                'energy': 'default', 'basic materials': 'Capital Goods',
                'industrials': 'Capital Goods', 'technology': 'IT',
                'consumer cyclical': 'Consumer Durables', 'consumer defensive': 'FMCG',
                'healthcare': 'Pharma', 'utilities': 'default',
                'real estate': 'default', 'communication services': 'IT',
            }
            sector = live_map.get(live, 'default')
        else:
            sector = self.get_sector_classification(symbol)
        multiplier = self.sector_multipliers.get(sector, 1.0)
        return base_score * multiplier
    
    def calculate_timing_factor(self):
        """Timing adjustments based on month"""
        current_month = datetime.now().month
        
        # Historical patterns
        favorable_months = [10, 11, 12, 1, 4]  # Oct-Jan, April
        unfavorable_months = [5, 6]             # May-June (sell in May)
        
        if current_month in favorable_months:
            return 1.05
        elif current_month in unfavorable_months:
            return 0.95
        else:
            return 1.0
    
    def calculate_improved_overall_score(self, symbol, stock_data):
        """
        Calculate improved score using only components that predict returns
        """
        try:
            # Calculate working components
            fundamental_quality = self.calculate_fundamental_quality_score(stock_data)
            momentum_technical = self.calculate_momentum_technical_score(stock_data)
            contrarian_momentum = self.calculate_contrarian_momentum_score(stock_data)
            quality_multiplier = self.calculate_quality_multiplier(stock_data)
            
            # Calculate base score
            base_score = (
                fundamental_quality * self.component_weights['fundamental_quality'] +
                momentum_technical * self.component_weights['momentum_technical'] +
                contrarian_momentum * self.component_weights['contrarian_momentum'] +
                quality_multiplier * self.component_weights['quality_multiplier']
            )
            
            # Apply sector adjustment
            sector_adjusted_score = self.calculate_sector_adjustment(symbol, base_score, stock_data)
            
            # Apply timing factor
            timing_factor = self.calculate_timing_factor()
            final_score = sector_adjusted_score * timing_factor
            
            # Ensure score is in valid range
            final_score = min(100, max(0, final_score))
            if np.isnan(final_score):
                final_score = 50.0
            
            return {
                'improved_overall_score': final_score,
                'fundamental_quality': fundamental_quality,
                'momentum_technical': momentum_technical,
                'contrarian_momentum': contrarian_momentum,
                'quality_multiplier': quality_multiplier,
                'sector': self.get_sector_classification(symbol),
                'timing_factor': timing_factor,
                'component_breakdown': {
                    'fundamental_weight': fundamental_quality * self.component_weights['fundamental_quality'],
                    'momentum_weight': momentum_technical * self.component_weights['momentum_technical'],
                    'stability_weight': contrarian_momentum * self.component_weights['contrarian_momentum'],
                    'quality_weight': quality_multiplier * self.component_weights['quality_multiplier']
                }
            }
            
        except Exception as e:
            print(f"❌ Error calculating improved score for {symbol}: {e}")
            return {
                'improved_overall_score': 50,
                'fundamental_quality': 50,
                'momentum_technical': 50,
                'contrarian_momentum': 50,
                'quality_multiplier': 50,
                'sector': 'default',
                'timing_factor': 1.0
            }
