
# NSE Stock Analysis and Ranking Tool

## ✅ Features
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
