"""
Stock Analyzer Package
=====================

A comprehensive stock analysis tool for NSE stocks with advanced features
for high-risk high-reward investors.

Features:
- Fundamental and technical analysis
- Risk-based trading strategies
- Portfolio optimization
- Excel report generation
- Real-time data scraping

Author: Enhanced by AI Assistant
Version: 2.0.0
"""

from .core.analyzer import EnhancedStockAnalyzer
from .analyzers import fundamental, technical, risk, momentum
from .exporters import excel, portfolio
from .utils import validation, data_quality

__version__ = "2.0.0"
__author__ = "Enhanced Stock Analysis System"

# Main exports
__all__ = [
    'EnhancedStockAnalyzer',
    'fundamental',
    'technical', 
    'risk',
    'momentum',
    'excel',
    'portfolio',
    'validation',
    'data_quality'
]
