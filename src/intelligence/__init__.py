"""
🧠 Intelligence System - Phase 1: Performance Tracking & Memory

This module provides intelligent learning and feedback capabilities to the 
stock analysis system, enabling it to learn from past recommendations and 
continuously improve.

Modules:
- intelligence_db: Centralized database for all intelligence data
- performance_tracker: Track recommendation outcomes and performance
- outcome_calculator: Calculate ROI, hit rates, and success metrics
- historical_migrator: Migrate historical reports to database

Author: Enhanced Stock Analysis System
Date: February 24, 2026
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Enhanced Stock Analysis System"

# Core components
from .intelligence_db import IntelligenceDB
from .performance_tracker import PerformanceTracker
from .outcome_calculator import OutcomeCalculator

__all__ = [
    'IntelligenceDB',
    'PerformanceTracker',
    'OutcomeCalculator',
]
