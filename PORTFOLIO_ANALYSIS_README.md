# 🏦 Portfolio Analysis System

A comprehensive portfolio analysis and optimization system that provides actionable insights for your stock investments.

## 📊 Key Features

### 📈 **Portfolio Performance Analysis**
- Current P&L analysis with percentage returns
- Individual stock performance vs market benchmarks
- Sector-wise allocation and concentration analysis
- Risk-adjusted returns calculation
- Holdings value distribution and diversification metrics

### 🚨 **Smart Exit Strategy Recommendations**
- Identify overvalued/underperforming stocks from your holdings
- Technical analysis-based exit timing signals
- Profit booking recommendations for high-gain positions
- Stop-loss suggestions for risky positions
- Tax-efficient exit planning (LTCG vs STCG optimization)

### 💡 **Intelligent Buy Recommendations**
- Match Enhanced Stock Report recommendations with available funds
- Sector gap analysis for better diversification
- Risk-adjusted stock suggestions based on your portfolio profile
- Position sizing recommendations based on available capital
- Entry timing based on technical indicators

### ⚖️ **Portfolio Rebalancing Strategies**
- Sector concentration analysis and rebalancing suggestions
- Risk category distribution optimization
- Underweight/overweight sector identification
- Capital allocation optimization for new investments
- Portfolio correlation analysis to reduce risk

### 🤖 **Advanced Insights & Automation**
- Dynamic file detection (latest holdings & Enhanced Stock Report)
- Automated portfolio health scoring
- Benchmark comparison capabilities
- Dividend yield and income analysis
- Portfolio beta and volatility analysis

### 📋 **Actionable Reports Generation**
- **Executive Summary**: Key metrics and immediate actions needed
- **Detailed Analysis**: Stock-by-stock recommendations with reasoning
- **Action Plan**: Specific buy/sell/hold recommendations with timelines
- **Risk Assessment**: Portfolio risk profile and mitigation strategies
- **Performance Tracking**: Historical performance vs benchmarks

## 🚀 Quick Start

### 1. **Basic Analysis (Auto-detect files)**
```bash
python portfolio_analysis.py
```

### 2. **Full Analysis with Custom Funds**
```bash
python portfolio_analysis.py --funds 114129.60 --output both --excel
```

### 3. **Specify Custom File Paths**
```bash
python portfolio_analysis.py --funds 150000 --holdings "Holding/my_holdings.csv" --report "reports/my_report.xlsx"
```

## 📁 File Structure

```
portfolio/
├── __init__.py          # Portfolio module initialization
├── analyzer.py          # Core portfolio analysis engine
├── insights.py          # Advanced insights and recommendations
├── reporter.py          # Comprehensive report generation
└── utils.py            # Utility functions and helpers

portfolio_analysis.py    # Main analysis script
portfolio_config.py      # Configuration parameters
```

## 📊 Sample Analysis Output

```
🏦 PORTFOLIO ANALYSIS SYSTEM
════════════════════════════════════════════════════════
💰 Available Funds: ₹1,14,129.60
📅 Analysis Date: September 15, 2025

📊 PORTFOLIO SUMMARY:
├─ Total Investment: ₹6,45,209
├─ Current Value: ₹7,28,663
├─ Total P&L: ₹83,453 (+12.9%)
└─ Portfolio Health Score: 80/100

🚨 IMMEDIATE ACTIONS NEEDED:
• BUY: UNIONBANK (Strong Buy) - Allocate ₹22,826
• MONITOR: ETERNAL (+69.1% profit) - Consider profit booking
• REBALANCE: Financial Services overweight (55.6%) - Reduce allocation

📈 TOP PERFORMERS: BAJFINANCE (+∞%), ETERNAL (+69.1%), MOTILALOFS (+52.1%)
📉 NEEDS ATTENTION: TCS (-10.5%), CAMS (-5.5%)
```

## 📊 Analysis Components

### 🎯 **Portfolio Health Score (0-100)**
- **Performance Score** (0-30): Returns vs benchmarks
- **Diversification Score** (0-25): Holdings and sector spread
- **Risk Management Score** (0-25): Concentration and volatility
- **Allocation Score** (0-20): Cash utilization efficiency

### 📋 **Exit Strategy Analysis**
- **Immediate Exits**: Urgent sell recommendations
- **Consider Exits**: Stocks to monitor closely
- **Profit Booking**: High-gain positions for partial booking
- **Stop Losses**: Risk management exits

### 💡 **Buy Recommendations**
- **Priority Score**: Combined fundamental + sector gap analysis
- **Sector Gap Benefits**: Addresses portfolio imbalances
- **Risk-Adjusted Suggestions**: Aligned with your risk profile
- **Position Sizing**: Optimal investment amounts

### ⚖️ **Rebalancing Strategies**
- **Sector Concentration**: Identify overweight sectors
- **Position Sizing**: Individual stock concentration risks
- **Capital Deployment**: Optimal use of available funds
- **Risk Distribution**: Improve portfolio risk profile

## ⚙️ Configuration

Edit `portfolio_config.py` to customize:

```python
# Risk Thresholds
LOSS_THRESHOLD = -10.0  # Exit stocks with loss > 10%
PROFIT_BOOKING_THRESHOLD = 25.0  # Consider profit booking above 25%

# Target Sector Allocation
TARGET_SECTOR_ALLOCATION = {
    'Financial Services': 25,
    'IT': 20,
    'Consumer Goods': 15,
    # ... customize as needed
}

# Investment Style
INVESTMENT_STYLE = {
    'risk_tolerance': 'MODERATE',
    'investment_horizon': 'LONG_TERM',
    'focus': 'GROWTH_AND_VALUE'
}
```

## 📄 Report Formats

### 🖥️ **Console Output**
Real-time analysis with color-coded insights and immediate action items.

### 📄 **Text Report** 
Comprehensive text report saved to `reports/portfolio/Portfolio_Analysis_Report_YYYYMMDD_HHMMSS.txt`

### 📊 **Excel Report**
Multi-sheet Excel workbook with:
- Holdings Summary
- Performance Metrics  
- Sector Analysis
- Exit Recommendations
- Buy Recommendations
- Portfolio Health Dashboard

## 🔧 Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--funds` | Available funds for investment | 114129.60 |
| `--holdings` | Path to holdings CSV file | Auto-detect |
| `--report` | Path to Enhanced Stock Report | Auto-detect |
| `--output` | Output format: console/file/both | console |
| `--excel` | Generate Excel report | False |

## 📈 Key Insights Provided

### 🎯 **Immediate Actions**
- Urgent buy/sell recommendations
- Profit booking opportunities  
- Risk management alerts
- Rebalancing priorities

### 📊 **Performance Analysis**
- Individual stock returns vs portfolio
- Sector performance comparison
- Risk-adjusted return metrics
- Volatility and beta analysis

### 💰 **Investment Opportunities**
- Undervalued stocks from Enhanced Report
- Sector gap filling recommendations
- Position sizing for optimal allocation
- Entry timing considerations

### ⚠️ **Risk Management**
- Concentration risk identification
- Diversification improvement suggestions
- Stop-loss recommendations
- Portfolio correlation analysis

## 🔄 Dynamic File Detection

The system automatically detects your latest files:
- **Holdings**: `Holding/holdings*.csv` (finds most recent)
- **Enhanced Stock Report**: `reports/Enhanced_Stock_Report_*.xlsx` (finds most recent)

## 📅 Recommended Usage

1. **Weekly Analysis**: Run comprehensive analysis every week
2. **Daily Quick Check**: Use quick analysis for daily monitoring  
3. **Pre-Investment**: Run before making new investments
4. **Post-Market**: Check daily performance and alerts
5. **Monthly Review**: Deep dive into rebalancing strategies

## 🎯 Next Steps

After running the analysis:

1. **Review Executive Summary** - Focus on immediate actions
2. **Check Action Plan** - Follow timeline-based recommendations  
3. **Implement Exits** - Act on urgent sell recommendations
4. **Plan Purchases** - Prepare buy orders for recommended stocks
5. **Monitor Progress** - Track implementation of suggestions

---

**Note**: This system integrates seamlessly with your existing Enhanced Stock Analysis infrastructure, leveraging the same data sources and technical analysis engines for consistent insights across your investment workflow.