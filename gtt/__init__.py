"""
GTT (Good Till Triggered) Module for Portfolio Management
=======================================================

This module provides GTT order generation functionality for portfolio holdings.
Creates two-leg GTT orders with support/resistance levels for automated trading.

Key Features:
- Automatic support/resistance level calculation
- Two-leg GTT orders (buy low, sell high)
- Integration with portfolio analysis
- Risk-based position sizing
- Excel sheet generation for broker upload

Author: Enhanced Stock Analysis System
Version: 1.0.0
"""

from .generator import GTTOrderGenerator
from .config import GTTConfig
from .analyzer import GTTAnalyzer

__all__ = ['GTTOrderGenerator', 'GTTConfig', 'GTTAnalyzer']