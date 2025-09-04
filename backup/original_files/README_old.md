
# 🚀 Enhanced Stock Analysis System

A comprehensive, robust stock analysis system that performs technical, fundamental, and sentiment analysis on Indian stocks (NSE) and generates detailed reports.

## ✨ Features

### 📊 **Data Acquisition**
- **NSE Bhavcopy Scraper**: Downloads daily EOD prices automatically
- **YFinance Integration**: Reliable OHLCV data source with error handling
- **Fundamental Data**: Extracts ratios and metrics from multiple sources
- **Robust Error Handling**: Continues analysis even when some data sources fail

### 🗄️ **Data Storage**
- **SQLite Database**: Structured storage for prices, fundamentals, indicators, news, scores
- **Daily Appending**: No data overwriting, maintains historical records
- **Efficient Queries**: Optimized for fast analysis and reporting

### 📈 **Analysis Modules**
- **Technical Analysis**: RSI, MACD, EMA, SMA, Bollinger Bands, ADX, ATR
- **Portfolio Analysis**: Performance tracking, P&L calculation, and position management
- **GTT Recommendations**: Generate Good Till Triggered price points for buying and selling
- **Fundamental Analysis**: PE, ROE, D/E ratios with scoring system
- **Sentiment Analysis**: VADER + TextBlob for news sentiment scoring
- **Combined Scoring**: Intelligent 0-100 scoring with BUY/HOLD/SELL recommendations

### 📋 **Excel Reports**
- **Multi-Sheet Reports**: Summary, Technicals, Fundamentals, Sentiment, Combined Score
- **Professional Formatting**: Color-coded recommendations, auto-sized columns
- **Daily Generation**: Automated reports with timestamps
- **Top Performers**: Highlighted best opportunities

### ⏰ **Automation & Scheduling**
- **Price Scraper**: Daily @ 6 PM (post-market)
- **News Scraper**: Daily @ 8 AM
- **Full Analysis**: Daily @ 7 PM with report generation
- **Fundamental Update**: Weekly on Sundays

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- Windows/Linux/macOS

### Quick Setup
```bash
# Clone the repository
git clone <repository-url>
cd Stock_Analysis

# Run setup script
python setup.py

# OR install manually
pip install -r requirements.txt
```

### Manual Dependencies
```bash
pip install requests pandas numpy yfinance beautifulsoup4 lxml openpyxl matplotlib seaborn plotly alpha-vantage nsepy selenium webdriver-manager apscheduler vaderSentiment textblob
```

## 🚀 Usage

### Option 1: Analyze Top 200 NSE Stocks
```bash
python scripts/run_analysis.py
```

### Option 2: Analyze a Single Stock
```bash
python scripts/run_analysis.py -s HINDALCO
```

### Option 3: Analyze a Smaller Batch
```bash
python scripts/run_analysis.py -n 10 -b 5 -w 2
```

### Option 4: Using Python API
```python
from stock_analysis.main import analyze_stock, batch_analyze_stocks, load_stock_list

# Analyze single stock
result = analyze_stock("RELIANCE")

# Analyze multiple stocks
stocks = load_stock_list()
results = batch_analyze_stocks(stocks[:10], batch_size=5)
```

### Command Line Options

- `-s`, `--symbol`: Analyze a single stock (e.g., `-s RELIANCE`)
- `-n`, `--num`: Number of stocks to analyze (e.g., `-n 50`)
- `-b`, `--batch`: Batch size for processing (e.g., `-b 10`)
- `-w`, `--workers`: Number of worker threads (e.g., `-w 4`)

## 📁 Project Structure

```
Stock_Analysis/
├── stock_analysis/               # Main package
│   ├── core/                     # Core configuration and database
│   │   ├── config.py             # Configuration settings
│   │   └── database.py           # Database functionality
│   ├── analyzers/                # Analysis modules
│   │   ├── technical_analyzer.py           # Basic technical analysis
│   │   ├── fundamental_analyzer.py         # Basic fundamental analysis
│   │   ├── enhanced_technical_analyzer.py  # Advanced technical analysis
│   │   └── enhanced_fundamental_analyzer.py # Advanced fundamental analysis
│   ├── data_providers/           # Data retrieval modules
│   │   └── nse_scraper.py        # NSE data scraper
│   ├── exporters/                # Data export modules
│   │   ├── data_exporter.py      # Basic data export
│   │   ├── json_export.py        # JSON export
│   │   └── excel_exporter.py     # Excel report generation
│   └── utils/                    # Utility functions
├── scripts/                      # Command line scripts
│   └── run_analysis.py           # Main analysis script
├── examples/                     # Usage examples
├── data/                         # Data storage
├── docs/                         # Documentation
└── tests/                        # Unit tests
│   ├── technical_analyzer.py     # Technical indicators
│   ├── fundamental_analyzer.py   # Fundamental analysis
│   └── ...                       # Other modules
├── data/                         # Data storage
│   ├── raw/                      # Raw downloaded data
│   ├── stock_analysis.db         # SQLite database
│   └── *.log                     # Analysis logs
├── reports/                      # Generated Excel reports
│   └── Stock_Report_YYYY-MM-DD.xlsx
├── logs/                         # System logs
├── requirements.txt              # Dependencies
├── setup.py                      # Setup script
└── README.md                     # This file
```

## 📊 Sample Output

### Console Output
```
🚀 Starting Enhanced NSE Stock Analysis...
✓ Components initialized

📊 Fetching stock data...
✓ Found 50 stocks to analyze

🔍 Analyzing stocks...
Analyzing RELIANCE (1/50)...
  📈 Fundamental analysis...
  📉 Technical analysis...
  📰 Sentiment analysis...
  ✓ Overall Score: 75.2 (BUY)

🏆 Top 10 Stocks by Overall Score:
================================================================================
 1. RELIANCE     | Score:  75.2 | BUY  | F: 72.0 T: 68.5 S: 85.0
 2. TCS          | Score:  73.8 | BUY  | F: 78.0 T: 65.2 S: 78.2
 3. HDFCBANK     | Score:  71.5 | BUY  | F: 70.5 T: 72.8 S: 71.2
 ...

📊 Analysis Summary:
   Total Stocks Analyzed: 50
   BUY Recommendations:   12
   HOLD Recommendations:  28
   SELL Recommendations:  10
   Average Overall Score: 58.42

✅ Analysis completed successfully!
```

### Excel Report Structure

#### Summary Sheet
| Symbol | Overall Score | Fundamental Score | Technical Score | Sentiment Score | Recommendation |
|--------|---------------|-------------------|-----------------|-----------------|----------------|
| RELIANCE | 75.2 | 72.0 | 68.5 | 85.0 | BUY |
| TCS | 73.8 | 78.0 | 65.2 | 78.2 | BUY |

#### Technical Sheet
| Symbol | Technical Score | RSI | MACD | SMA_20 | SMA_50 | ADX |
|--------|-----------------|-----|------|--------|--------|-----|
| RELIANCE | 68.5 | 45.2 | 0.32 | 2245.5 | 2198.7 | 25.8 |

#### Fundamental Sheet
| Symbol | Fundamental Score | PE Ratio | ROE | Debt/Equity | Market Cap |
|--------|-------------------|----------|-----|-------------|------------|
| RELIANCE | 72.0 | 18.5 | 12.8 | 0.45 | 15,25,000 |

#### Sentiment Sheet
| Symbol | Sentiment Score | Headline | Source | Sentiment Label |
|--------|-----------------|----------|--------|-----------------|
| RELIANCE | 85.0 | Reliance reports strong Q3 results | Moneycontrol | Positive |

## 🔧 Configuration

### Scoring Methodology
- **Overall Score = (Fundamental + Technical + Sentiment) / 3**
- **BUY**: Score > 70
- **HOLD**: Score 40-70  
- **SELL**: Score < 40

### Customization
Edit `src/config.py` to modify:
- Stock universe (top 50, 100, 500)
- Scoring weights
- Analysis parameters
- Scheduling times

## 📅 Scheduling Details

### Default Schedule
- **6:00 PM**: Download daily Bhavcopy (price data)
- **8:00 AM**: Scrape and analyze news sentiment
- **7:00 PM**: Run full analysis + generate Excel report
- **Sunday 10:00 AM**: Update fundamental data

### Custom Scheduling
Modify `scheduler.py` to change timing:
```python
# Daily analysis at custom time
scheduler.add_job(
    func=daily_analysis_and_report,
    trigger="cron",
    hour=19,  # 7 PM
    minute=30,  # 30 minutes
    id='daily_analysis'
)
```

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt --force-reinstall
   ```

2. **NSE Data Access Issues**
   - Check internet connection
   - Verify NSE website is accessible
   - Some data sources may require VPN

3. **Excel Generation Fails**
   ```bash
   pip install openpyxl --upgrade
   ```

4. **Database Errors**
   - Delete `data/stock_analysis.db` to reset
   - Check write permissions in data folder

### Logs
Check detailed logs in:
- `logs/analysis_YYYYMMDD_HHMMSS.log`
- `logs/scheduler.log`

## 🔄 Legacy Compatibility

The system maintains backward compatibility with the original `main.py`. All existing functionality is preserved while adding new enhanced features.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📈 Roadmap

- [ ] **Advanced Alerts**: Telegram/Email notifications
- [ ] **Backtesting Module**: Historical performance testing
- [ ] **Portfolio Tracking**: Personal holdings management
- [ ] **Web Dashboard**: Real-time web interface
- [ ] **Machine Learning**: Predictive scoring models
- [ ] **Options Analysis**: Derivatives strategy recommendations

## ⚖️ Disclaimer

This tool is for educational and research purposes only. Not intended as financial advice. Always consult with qualified financial advisors before making investment decisions.

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs for detailed error information
3. Create an issue on GitHub with relevant logs

---

**Happy Analyzing! 📊✨**

## Legacy Features (Original Implementation)

### ✅ Original Features
- Extracts and analyzes the top 150 NSE stocks by market capitalization
- Fundamental analysis: 30+ financial metrics, health scoring (0-100)
- Technical analysis: 20+ indicators, trend/volatility scoring (0-100)
- Combined overall scoring and investment recommendation
- Robust error handling, API fallback, and rate limiting
- Exports results to CSV and multi-sheet Excel (top 20, sector, market cap summaries)
- Demo mode with realistic offline sample data
- Progress tracking and color-coded console output

## 📁 Project Structure
```
src/
    config.py              # Centralized configuration
    nse_scraper.py         # Data extraction (NSE API + yfinance fallback)
    fundamental_analyzer.py# Fundamental analysis logic
    technical_analyzer.py  # Technical analysis logic
    data_exporter.py       # Output to CSV/Excel
    main.py                # Main workflow
    demo.py                # Offline demo with sample data
tests/
    test_analyzers.py      # Analyzer tests
    test_scraper.py        # Scraper tests
data/                    # Output files
.github/                 # Copilot instructions
requirements.txt         # Dependencies
README.md                # This file
```

## 🚀 Installation
1. Clone this repository and navigate to the project folder.
2. Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```

## 🏃 Usage
### Live NSE Analysis
```bash
python src/main.py
```
* Fetches, analyzes, and exports the latest data for the top 150 NSE stocks.

### Demo Mode (Offline)
```bash
python src/demo.py
```
* Runs the full analysis pipeline on realistic sample data (no API calls).

## 📊 Output
- **CSV**: Full dataset in `data/` folder
- **Excel**: Multi-sheet workbook with:
    - All_stocks: Raw and analyzed data
    - Top_20: Top 20 by overall score
    - Sector_summary: Grouped by sector
    - MarketCap_summary: Grouped by market cap

## 🛠️ Troubleshooting
- **Corporate/Restricted Networks**: If NSE API fails, the tool will use fallback stock lists and yfinance for data.
- **SSL/Connection Errors**: Try running on a home network or VPN.
- **Missing Data**: Some stocks may have incomplete data; these are handled gracefully.
- **Dependencies**: Ensure all packages in `requirements.txt` are installed.

## 📚 Technical Details
- **APIs Used**: NSE India (public), yfinance (Yahoo! Finance)
- **Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, RoC, and more
- **Scoring**: Customizable weights in `config.py`
- **Cross-platform**: Works on Windows, macOS, Linux

## 🧪 Testing
Run all tests:
```bash
python -m unittest discover tests
```

## 📷 Sample Output
*See the `data/` folder after running the tool for sample files.*

---
For more details, see comments in each module and the configuration file.
