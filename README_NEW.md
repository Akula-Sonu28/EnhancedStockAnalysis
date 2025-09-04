# 🚀 Stock Analysis System v2.0.0

A comprehensive, professionally organized stock analysis tool for NSE stocks with advanced features for **high-risk high-reward** investors.

## ✨ Key Features

- 🎯 **Risk-Based Analysis**: Conservative, Moderate, and Aggressive trading strategies
- 📈 **Momentum Scoring**: Advanced growth + technical momentum analysis
- 💰 **Portfolio Optimization**: Smart allocation with risk-adjusted position sizing
- 📊 **Professional Reports**: Detailed Excel reports with trading plans
- ⚡ **High-Performance**: Multi-threaded analysis with intelligent caching
- 🔧 **Interactive Tools**: Command builder, setup verification, and guides

## 🏗️ Project Structure

```
Stock_Analysis/
├── 📁 stock_analyzer/          # Main analysis package
│   ├── core/                   # Core analysis engine
│   ├── analyzers/              # Fundamental, technical, risk analysis
│   ├── exporters/              # Excel, JSON, portfolio exports
│   └── utils/                  # Validation, caching, quality checks
├── 📁 tools/                   # Interactive user tools
├── 📁 config/                  # Configuration files
├── 📁 data/                    # Data storage and templates
├── 📁 docs/                    # Comprehensive documentation
├── 📁 tests/                   # Test suite
└── main.py                     # Simple entry point
```

## 🚀 Quick Start

### 1. **Simple Entry Point**
```bash
# Interactive mode (recommended for beginners)
python main.py --interactive

# Quick help
python main.py

# Access tools
python main.py --tools
```

### 2. **Direct Analysis Commands**
```bash
# Quick aggressive test (5 minutes)
python main.py --risk-profile aggressive --focus-growth -n 10

# Full aggressive analysis (20 minutes)
python main.py --risk-profile aggressive --focus-growth --focus-momentum

# Portfolio builder (₹5 lakhs)
python main.py --portfolio-amount 500000 --risk-profile aggressive
```

### 3. **Original Enhanced Interface**
```bash
# All original commands still work
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth
```

## 🔧 Interactive Tools

### Command Builder
```bash
python tools/command_builder.py
```
Guided interface to build the perfect command for your investment style.

### Setup Verification
```bash
python tools/verify_setup.py
```
Verify all features are working correctly.

### Investor Guide
```bash
python tools/investor_guide.py
```
Interactive guide with examples and explanations.

## 📊 Risk Profiles

| Profile | Entry Range | Profit Targets | Stop Loss | Best For |
|---------|------------|----------------|-----------|----------|
| **Conservative** | 1% | 2.5%, 5%, 8% | 3.5% | Retirement funds |
| **Moderate** | 2% | 3.5%, 8%, 12% | 5.5% | Most investors |
| **Aggressive** | 4% | 6%, 12%, 20% | 8% | **High-risk high-reward** |

## 🎉 What's New in v2.0.0

- ✅ **Organized Structure**: Clean, modular architecture
- ✅ **Simple Entry Point**: Easy-to-use main.py
- ✅ **Interactive Tools**: Guided command building
- ✅ **Better Documentation**: Comprehensive guides
- ✅ **Enhanced Testing**: Verification tools
- ✅ **Backward Compatibility**: All v1.x commands work

## 🚀 Ready to Start!

**Recommended first command:**
```bash
python main.py --interactive
```

This will guide you through building the perfect analysis for your investment style!

---

*Built with ❤️ for high-risk high-reward investors who demand professional-grade analysis tools.*
