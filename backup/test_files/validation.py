#!/usr/bin/env python3
"""
Enhanced Validation and Error Handling
Comprehensive validation for stock analysis inputs and data
"""

import re
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from functools import wraps
import time

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class StockDataValidator:
    """Comprehensive validator for stock analysis data"""
    
    # Valid NSE stock symbol pattern
    NSE_SYMBOL_PATTERN = re.compile(r'^[A-Z0-9&-]{1,20}$')
    
    @staticmethod
    def validate_stock_symbol(symbol: str) -> bool:
        """Validate NSE stock symbol format"""
        if not isinstance(symbol, str):
            return False
        
        symbol = symbol.strip().upper()
        
        # Check basic pattern
        if not StockDataValidator.NSE_SYMBOL_PATTERN.match(symbol):
            return False
        
        # Additional checks
        if len(symbol) < 1 or len(symbol) > 20:
            return False
            
        return True
    
    @staticmethod
    def validate_stock_list(symbols: List[str]) -> Tuple[List[str], List[str]]:
        """Validate a list of stock symbols"""
        valid_symbols = []
        invalid_symbols = []
        
        for symbol in symbols:
            if StockDataValidator.validate_stock_symbol(symbol):
                valid_symbols.append(symbol.strip().upper())
            else:
                invalid_symbols.append(symbol)
        
        return valid_symbols, invalid_symbols
    
    @staticmethod
    def validate_financial_ratio(value: Any, ratio_name: str, 
                                min_val: float = -1000, max_val: float = 1000) -> bool:
        """Validate financial ratios with reasonable bounds"""
        try:
            if value is None or pd.isna(value):
                return True  # Allow None/NaN values
            
            value = float(value)
            
            # Check for infinite values
            if not pd.isfinite(value):
                logging.warning(f"Invalid {ratio_name}: {value} (infinite)")
                return False
            
            # Check bounds
            if value < min_val or value > max_val:
                logging.warning(f"Invalid {ratio_name}: {value} (out of bounds)")
                return False
            
            return True
            
        except (ValueError, TypeError):
            logging.warning(f"Invalid {ratio_name}: {value} (conversion error)")
            return False
    
    @staticmethod
    def validate_stock_data(stock_data: Dict) -> Dict[str, Any]:
        """Validate and clean stock analysis data"""
        validated_data = stock_data.copy()
        issues = []
        
        # Validate symbol
        symbol = stock_data.get('symbol', '')
        if not StockDataValidator.validate_stock_symbol(symbol):
            issues.append(f"Invalid symbol: {symbol}")
        
        # Validate financial ratios
        financial_ratios = {
            'pe_ratio': (0, 500),
            'pb_ratio': (0, 50),
            'debt_to_equity': (0, 10),
            'current_ratio': (0, 20),
            'roe': (-100, 100),
            'roa': (-100, 100),
            'profit_margin': (-100, 100),
            'dividend_yield': (0, 50)
        }
        
        for ratio, (min_val, max_val) in financial_ratios.items():
            value = stock_data.get(ratio)
            if value is not None:
                if not StockDataValidator.validate_financial_ratio(value, ratio, min_val, max_val):
                    issues.append(f"Invalid {ratio}: {value}")
                    validated_data[ratio] = None
        
        # Validate scores (should be 0-100)
        score_fields = [
            'fundamental_score', 'technical_score', 'undervaluation_score',
            'overall_score', 'risk_adjusted_score'
        ]
        
        for field in score_fields:
            value = stock_data.get(field)
            if value is not None:
                try:
                    value = float(value)
                    if not (0 <= value <= 100):
                        issues.append(f"Score out of range {field}: {value}")
                        validated_data[field] = max(0, min(100, value))  # Clamp to 0-100
                except (ValueError, TypeError):
                    issues.append(f"Invalid score {field}: {value}")
                    validated_data[field] = 50  # Default neutral score
        
        # Validate prices (should be positive)
        price_fields = ['current_price', '52w_high', '52w_low', 'market_cap']
        for field in price_fields:
            value = stock_data.get(field)
            if value is not None:
                try:
                    value = float(value)
                    if value <= 0:
                        issues.append(f"Invalid price {field}: {value}")
                        validated_data[field] = None
                except (ValueError, TypeError):
                    issues.append(f"Invalid price {field}: {value}")
                    validated_data[field] = None
        
        # Add validation summary
        validated_data['validation_issues'] = issues
        validated_data['validation_status'] = 'clean' if not issues else 'issues_found'
        
        if issues:
            logging.warning(f"Validation issues for {symbol}: {'; '.join(issues)}")
        
        return validated_data

def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, 
                    backoff_factor: float = 2.0):
    """Decorator for retrying functions on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff_factor ** attempt)
                        logging.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                                      f"Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                    else:
                        logging.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")
            
            raise last_exception
        return wrapper
    return decorator

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default on division by zero"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        return float(numerator) / float(denominator)
    except (ValueError, TypeError, ZeroDivisionError):
        return default

def safe_percentage(value: float, total: float, default: float = 0.0) -> float:
    """Safely calculate percentage"""
    return safe_divide(value * 100, total, default)

def clean_numeric_value(value: Any, default: float = 0.0) -> float:
    """Clean and convert value to numeric, handling various edge cases"""
    if value is None or pd.isna(value):
        return default
    
    if isinstance(value, (int, float)):
        if pd.isfinite(value):
            return float(value)
        else:
            return default
    
    if isinstance(value, str):
        # Remove common non-numeric characters
        cleaned = re.sub(r'[^\d.-]', '', value.strip())
        try:
            return float(cleaned) if cleaned else default
        except ValueError:
            return default
    
    return default

class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.metrics = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.metrics[operation] = {'start_time': time.time()}
    
    def end_timer(self, operation: str):
        """End timing an operation and log duration"""
        if operation in self.metrics:
            duration = time.time() - self.metrics[operation]['start_time']
            self.metrics[operation]['duration'] = duration
            logging.info(f"Operation '{operation}' completed in {duration:.2f} seconds")
            return duration
        return None
    
    def get_summary(self) -> Dict[str, float]:
        """Get summary of all timed operations"""
        return {op: data.get('duration', 0) for op, data in self.metrics.items()}

# Global performance monitor instance
performance_monitor = PerformanceMonitor()
