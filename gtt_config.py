"""
GTT Configuration File
=====================

Customize GTT order generation parameters by modifying this file.
This allows you to fine-tune trigger levels, position sizing, and risk management.
"""

# Support and Resistance Calculation
SUPPORT_PERCENTAGE = 5.0        # % below current price for support
RESISTANCE_PERCENTAGE = 8.0     # % above current price for resistance

# Position Sizing for Sell Orders (Existing Holdings)
SELL_FIRST_LEG_PERCENTAGE = 75  # % of total holding for first sell leg
SELL_SECOND_LEG_PERCENTAGE = 60 # % of remaining for second sell leg

# Position Sizing for Buy Orders (New Positions) 
BUY_BASE_QUANTITY = 100         # Base quantity for buy orders
BUY_FIRST_LEG_PERCENTAGE = 70   # % for first buy leg

# Risk Management
MAX_TRIGGER_SPREAD = 15.0       # Maximum % difference between triggers
MIN_TRIGGER_VALUE = 50.0        # Minimum trigger price value
SUPPORT_BUFFER = 0.99           # Buffer below support (99%)
RESISTANCE_BUFFER = 1.01        # Buffer above resistance (101%)

# GTT Order Defaults
DEFAULT_GTT_TYPE = "two-leg"
DEFAULT_STATUS = "ACTIVE" 
DEFAULT_EXCHANGE = "NSE"

# Stock Quality Filters for Buy Orders
# Only generate buy GTT for stocks with these recommendations
BUY_GTT_RECOMMENDATIONS = ["BUY", "HOLD"]
BUY_GTT_RISK_CATEGORIES = ["LOW", "MODERATE"]

# Enhanced Level Calculation Settings
USE_52_WEEK_DATA = True         # Use 52-week high/low for better levels
VOLATILITY_ADJUSTMENT = True    # Adjust levels based on stock volatility
RATING_BASED_ADJUSTMENT = True  # Adjust levels based on stock rating

# Rating Multipliers (affects trigger level width)
RATING_MULTIPLIERS = {
    "excellent": 1.2,
    "very good": 1.2, 
    "good": 1.2,
    "average": 1.0,
    "fair": 1.0,
    "below average": 0.8,
    "poor": 0.8,
    "weak": 0.8
}

# Output Settings
EXPORT_TO_EXCEL = True
INCLUDE_DETAILED_ANALYSIS = True
INCLUDE_SUMMARY_STATS = True

# File Naming
GTT_FILE_PREFIX = "GTT_Orders"
INCLUDE_TIMESTAMP = True