"""
GTT Technical Analysis Module
============================

Analyzes stock technical levels to determine optimal GTT trigger points.
Uses portfolio holdings and Enhanced Stock Report data for calculations.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

class GTTAnalyzer:
    """Technical analyzer for GTT trigger level calculation"""
    
    def __init__(self, enhanced_report_data: pd.DataFrame):
        """Initialize with Enhanced Stock Report data"""
        self.report_data = enhanced_report_data
        self.support_resistance_cache = {}
    
    def get_stock_data(self, symbol: str) -> Optional[Dict]:
        """Get stock data from Enhanced Stock Report"""
        try:
            # Try different symbol formats
            stock_data = self.report_data[
                (self.report_data['symbol'] == symbol) |
                (self.report_data['symbol'] == symbol.upper()) |
                (self.report_data['symbol'] == symbol.lower())
            ]
            
            if stock_data.empty:
                return None
                
            return stock_data.iloc[0].to_dict()
        except Exception as e:
            print(f"⚠️ Error getting data for {symbol}: {e}")
            return None
    
    def calculate_technical_levels(self, symbol: str, current_price: float) -> Dict[str, float]:
        """Calculate support and resistance levels using multiple methods"""
        
        # Check cache first
        cache_key = f"{symbol}_{current_price}"
        if cache_key in self.support_resistance_cache:
            return self.support_resistance_cache[cache_key]
        
        stock_data = self.get_stock_data(symbol)
        
        if not stock_data:
            # Fallback to percentage-based calculation
            support = current_price * 0.95  # 5% below
            resistance = current_price * 1.08  # 8% above
        else:
            # Use Enhanced Stock Report data for better levels
            support, resistance = self._calculate_enhanced_levels(stock_data, current_price)
        
        levels = {
            'support': round(support, 2),
            'resistance': round(resistance, 2),
            'current_price': current_price,
            'support_percentage': round((support / current_price - 1) * 100, 2),
            'resistance_percentage': round((resistance / current_price - 1) * 100, 2)
        }
        
        # Cache the result
        self.support_resistance_cache[cache_key] = levels
        return levels
    
    def _calculate_enhanced_levels(self, stock_data: Dict, current_price: float) -> Tuple[float, float]:
        """Calculate support/resistance using Enhanced Stock Report metrics"""
        
        # Get technical indicators from the report
        try:
            # Use 52-week high/low if available
            week_52_high = stock_data.get('52_week_high', current_price * 1.2)
            week_52_low = stock_data.get('52_week_low', current_price * 0.8)
            
            # Technical rating influence
            technical_rating = stock_data.get('fundamental_rating', 'Average')
            rating_multiplier = self._get_rating_multiplier(technical_rating)
            
            # Calculate dynamic levels based on volatility and rating
            price_range = week_52_high - week_52_low
            volatility_factor = price_range / current_price if current_price > 0 else 0.2
            
            # Adjust support/resistance based on stock quality
            if rating_multiplier > 1.0:  # Good stock - wider range
                support_pct = max(0.03, min(0.08, volatility_factor * 0.3)) 
                resistance_pct = max(0.05, min(0.12, volatility_factor * 0.4))
            else:  # Poor stock - tighter range
                support_pct = max(0.02, min(0.06, volatility_factor * 0.25))
                resistance_pct = max(0.04, min(0.08, volatility_factor * 0.3))
            
            support = current_price * (1 - support_pct)
            resistance = current_price * (1 + resistance_pct)
            
            # Ensure levels are within reasonable bounds
            support = max(support, week_52_low * 1.02)  # At least 2% above 52w low
            resistance = min(resistance, week_52_high * 0.98)  # At most 2% below 52w high
            
        except Exception as e:
            print(f"⚠️ Error in enhanced calculation for {stock_data.get('symbol', 'Unknown')}: {e}")
            # Fallback to simple percentage
            support = current_price * 0.95
            resistance = current_price * 1.08
        
        return support, resistance
    
    def _get_rating_multiplier(self, rating: str) -> float:
        """Get multiplier based on stock rating"""
        rating_str = str(rating).lower()
        
        if any(word in rating_str for word in ['excellent', 'very good', 'good']):
            return 1.2
        elif any(word in rating_str for word in ['average', 'fair']):
            return 1.0
        elif any(word in rating_str for word in ['below', 'poor', 'weak']):
            return 0.8
        else:
            return 1.0
    
    def validate_trigger_levels(self, support: float, resistance: float, current_price: float) -> bool:
        """Validate that trigger levels are reasonable"""
        
        # Check if levels are properly ordered
        if not (support < current_price < resistance):
            return False
        
        # Check if spread is reasonable (not too wide or too narrow)
        spread_percentage = (resistance - support) / current_price * 100
        if spread_percentage < 3 or spread_percentage > 25:
            return False
        
        # Check minimum price levels
        if support < 10 or resistance < 10:
            return False
        
        return True
    
    def get_stock_recommendation_context(self, symbol: str) -> Dict[str, str]:
        """Get additional context for GTT decision making"""
        stock_data = self.get_stock_data(symbol)
        
        if not stock_data:
            return {
                'recommendation': 'HOLD', 
                'risk': 'MEDIUM', 
                'context': f'Limited analysis data - Basic GTT for {symbol}'
            }
        
        recommendation = stock_data.get('final_recommendation', 'HOLD')
        risk_category = stock_data.get('risk_category', 'MEDIUM')
        rating = stock_data.get('fundamental_rating', 'Average')
        
        # Clean up recommendation text
        if '🔴' in str(recommendation) or 'SELL' in str(recommendation):
            clean_recommendation = 'SELL'
        elif '🟢' in str(recommendation) or 'BUY' in str(recommendation):
            clean_recommendation = 'BUY'
        else:
            clean_recommendation = 'HOLD'
        
        return {
            'recommendation': clean_recommendation,
            'risk': str(risk_category).upper(),
            'rating': str(rating),
            'context': f"{clean_recommendation} recommendation with {risk_category} risk"
        }