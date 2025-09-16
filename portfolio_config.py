"""
Portfolio Analysis Configuration File

Configure your portfolio analysis parameters here:
- Risk thresholds
- Allocation targets
- Investment preferences
- Reporting settings
"""

# Investment Parameters
DEFAULT_AVAILABLE_FUNDS = 114129.60  # Your available funds

# Risk Management Thresholds
LOSS_THRESHOLD = -10.0  # Exit stocks with loss > 10%
PROFIT_BOOKING_THRESHOLD = 25.0  # Consider profit booking above 25%
CONCENTRATION_LIMIT = 20.0  # Maximum single stock/sector allocation
MIN_POSITION_SIZE = 5000  # Minimum investment amount per stock

# Ideal Sector Allocation (percentages)
TARGET_SECTOR_ALLOCATION = {
    'Financial Services': 25,  # Reduce from current 55.6%
    'IT': 20,
    'Consumer Goods': 15,
    'Healthcare': 10,
    'Infrastructure': 10,
    'Energy': 8,
    'Basic Materials': 7,
    'Others': 5
}

# Portfolio Health Score Weights
HEALTH_SCORE_WEIGHTS = {
    'performance': 30,      # Out of 30 points
    'diversification': 25,  # Out of 25 points  
    'risk_management': 25,  # Out of 25 points
    'allocation': 20        # Out of 20 points
}

# File Patterns (for automatic detection)
HOLDINGS_PATTERN = "Holding/holdings*.csv"
ENHANCED_REPORT_PATTERN = "reports/Enhanced_Stock_Report_*.xlsx"

# Reporting Settings
REPORTS_DIRECTORY = "reports/portfolio"
AUTO_BACKUP_ENABLED = True
EXCEL_REPORTS_ENABLED = True

# Investment Style Configuration
INVESTMENT_STYLE = {
    'risk_tolerance': 'MODERATE',  # CONSERVATIVE, MODERATE, AGGRESSIVE
    'investment_horizon': 'LONG_TERM',  # SHORT_TERM, MEDIUM_TERM, LONG_TERM
    'focus': 'GROWTH_AND_VALUE',  # GROWTH, VALUE, GROWTH_AND_VALUE, DIVIDEND
    'max_stocks_per_sector': 5,  # Maximum number of stocks per sector
    'preferred_market_cap': 'ALL'  # LARGE_CAP, MID_CAP, SMALL_CAP, ALL
}

# Alert Thresholds
ALERT_THRESHOLDS = {
    'high_concentration_risk': 30.0,  # Alert if any sector > 30%
    'low_diversification': 10,  # Alert if < 10 stocks total
    'high_single_stock_weight': 15.0,  # Alert if single stock > 15%
    'cash_deployment_threshold': 10.0  # Alert if cash > 10% of portfolio
}

# Technical Analysis Parameters
TECHNICAL_INDICATORS = {
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'momentum_period': 14,
    'volatility_threshold': 20.0
}