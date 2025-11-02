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
    
    def __init__(self):
        # NEW WEIGHTS - Only components that work
        self.component_weights = {
            'fundamental_quality': 0.40,      # Doubled (was best predictor)
            'momentum_technical': 0.30,       # NEW - follow momentum, not contrarian
            'contrarian_momentum': 0.20,      # Keep (5.5% spread)
            'quality_multiplier': 0.10        # NEW - reward good companies
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
            
            return max(0, min(100, score))
            
        except Exception as e:
            return 50
    
    def calculate_contrarian_momentum_score(self, stock_data):
        """
        STABILITY - Keep this (it worked in backtest)
        Low volatility = Stable = GOOD
        """
        score = 50
        
        try:
            # Low volatility is good
            volatility = stock_data.get('volatility', 0)
            if pd.notna(volatility):
                if volatility < 1.5:
                    score += 20
                elif volatility < 2.0:
                    score += 10
                elif volatility > 3.0:
                    score -= 15
                elif volatility > 2.5:
                    score -= 5
            
            # Moderate price changes (stability)
            price_change_20d = abs(stock_data.get('enhanced_price_change_20d', 0))
            if pd.notna(price_change_20d):
                if price_change_20d < 3:      # Very stable
                    score += 15
                elif price_change_20d < 5:    # Stable
                    score += 8
                elif price_change_20d > 15:   # Too volatile
                    score -= 10
            
            return max(0, min(100, score))
            
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
                if debt_to_equity < 0.5:      # Very low debt
                    score += 15
                elif debt_to_equity < 1.0:    # Moderate debt
                    score += 8
                elif debt_to_equity > 2.0:    # High debt
                    score -= 15
                elif debt_to_equity > 1.5:    # Elevated debt
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
            
            return max(0, min(100, score))
            
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
            if pd.notna(debt_to_equity) and debt_to_equity < 1.0:
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
            
            return max(0, min(100, score))
            
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
    
    def calculate_sector_adjustment(self, symbol, base_score):
        """Apply sector multiplier"""
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
            sector_adjusted_score = self.calculate_sector_adjustment(symbol, base_score)
            
            # Apply timing factor
            timing_factor = self.calculate_timing_factor()
            final_score = sector_adjusted_score * timing_factor
            
            # Ensure score is in valid range
            final_score = min(100, max(0, final_score))
            
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
