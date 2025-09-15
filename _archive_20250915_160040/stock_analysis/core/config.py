
# Configuration for NSE Stock Analysis Tool

import os
from datetime import datetime

# No need for API endpoints as we're using Yahoo Finance directly

# Output and rate limiting preferences
MAX_WORKERS = 5  # Number of parallel workers for fetching data
REQUEST_DELAY = 0.5  # Delay between API requests to avoid rate limiting

# Directory structure
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Create directories if they don't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# File paths
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_OUTPUT = os.path.join(BASE_DIR, "data", f"nse_top150_{TIMESTAMP}.csv")
EXCEL_OUTPUT = os.path.join(BASE_DIR, "data", f"nse_top150_{TIMESTAMP}.xlsx")
LOG_FILE = os.path.join(BASE_DIR, "data", f"analysis_{TIMESTAMP}.log")

# Scoring weights (customize as needed)
FUNDAMENTAL_WEIGHTS = {
	"roe": 20,
	"pe": 15,
	"de": 15,
	"profit_margin": 15,
	"current_ratio": 10,
	"pb": 10,
	"revenue_growth": 10,
	"dividend_yield": 5
}

TECHNICAL_WEIGHTS = {
    "ma_trend": 25,
    "rsi": 15,
    "trend": 15,
    "macd": 15,
    "stochastic": 10,
    "volume": 10,
    "volatility": 10
}

# Market cap thresholds (in INR crores)
MARKET_CAP_THRESHOLDS = {
	"mega": 200000,
	"large": 50000,
	"mid": 10000,
	"small": 2000,
	"micro": 0
}

# Rate limiting and retry
REQUESTS_PER_MIN = 20
RETRY_LIMIT = 3
RETRY_BACKOFF = 2  # seconds

# Logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "data", f"nse_analysis_{TIMESTAMP}.log")
