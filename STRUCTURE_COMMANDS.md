# 📁 ORGANIZED STRUCTURE QUICK COMMANDS
# ====================================

## 🚀 NEW ORGANIZED INTERFACE (v2.0.0)

### **📂 MAIN ENTRY POINTS**
```bash
# Primary entry point (NEW!)
python main.py --interactive                    # Interactive guided mode
python main.py --tools                         # Tools and utilities menu
python main.py --help-quick                    # Quick command reference
python main.py                                 # Show main help menu

# Advanced entry point
python main.py --risk-profile aggressive --focus-growth -n 10
```

### **🛠️ INTERACTIVE TOOLS DIRECTORY**
```bash
# Command builder (builds commands for you)
python tools/command_builder.py               # Interactive command construction

# Setup verification (tests all features)
python tools/verify_setup.py                  # Comprehensive system test

# Investor guide (examples and tutorials)
python tools/investor_guide.py                # Risk-based examples and guides

# Project organizer
python organize_project.py                    # Reorganize project structure
```

### **⚙️ CORE ANALYZER DIRECTORY**
```bash
# Main analyzer (organized)
python stock_analyzer/core/analyzer.py        # Direct analyzer access

# Utilities
python stock_analyzer/utils/validation.py     # Data validation utilities
python stock_analyzer/utils/data_quality.py   # Data quality assessment
```

### **📊 CONFIGURATION DIRECTORY**
```bash
# Settings configuration
config/settings.py                            # Risk weights and thresholds
config/templates/                             # CSV templates directory
```

### **📈 DATA DIRECTORY STRUCTURE**
```bash
data/
├── analysis_results/                         # Excel output files
├── exports/                                  # CSV export files  
├── templates/                                # Stock list templates
├── cache/                                    # Performance cache
└── raw/                                      # Raw data files
```

## 🔄 BACKWARD COMPATIBLE COMMANDS

### **📜 ORIGINAL INTERFACE (Still Works!)**
```bash
# Original enhanced analyzer (unchanged)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth -n 10

# All original commands still work exactly the same
python analyze_top200_stocks_enhanced.py -s RELIANCE --risk-profile aggressive
python analyze_top200_stocks_enhanced.py --portfolio-amount 500000 --risk-profile aggressive
```

## 🎯 DIRECTORY-SPECIFIC QUICK ACTIONS

### **📁 FROM ROOT DIRECTORY**
```bash
# Main commands (recommended)
python main.py --risk-profile aggressive --focus-growth -n 10
python main.py --tools
python main.py --interactive

# Tools
python tools/command_builder.py
python tools/verify_setup.py
python tools/investor_guide.py

# Original (still works)
python analyze_top200_stocks_enhanced.py --risk-profile aggressive -n 10
```

### **📂 FROM TOOLS DIRECTORY**
```bash
cd tools
python command_builder.py                     # Interactive command builder
python verify_setup.py                       # Verify all systems
python investor_guide.py                     # Risk-based guides
cd ..
```

### **⚙️ FROM STOCK_ANALYZER DIRECTORY**
```bash
cd stock_analyzer
python -m core.analyzer --help               # Direct analyzer access
cd ..
```

### **📊 FROM CONFIG DIRECTORY**
```bash
# View configuration files
type config\settings.py                      # Windows
cat config/settings.py                       # Linux/Mac

# Copy templates
copy config\templates\*.csv data\templates\
```

## 🎪 ORGANIZED WORKFLOW PATTERNS

### **🔥 AGGRESSIVE INVESTOR WORKFLOW**
```bash
# 1. Daily morning scan
python main.py --risk-profile aggressive --focus-growth -n 15

# 2. Individual stock research
python main.py -s RELIANCE --risk-profile aggressive --focus-growth

# 3. Portfolio optimization
python main.py --portfolio-amount 500000 --risk-profile aggressive --focus-growth

# 4. Momentum opportunities
python main.py --risk-profile aggressive --focus-momentum --min-volatility 20 -n 20
```

### **📈 SYSTEMATIC ANALYSIS WORKFLOW**
```bash
# 1. Setup verification
python tools/verify_setup.py

# 2. Build custom command
python tools/command_builder.py

# 3. Execute analysis
python main.py [CUSTOM_COMMAND_FROM_BUILDER]

# 4. Review results in data/analysis_results/
```

### **⚡ SPEED-OPTIMIZED WORKFLOW**
```bash
# 1. Quick test (30 seconds)
python main.py --risk-profile aggressive -n 5

# 2. Medium scan (2 minutes)  
python main.py --risk-profile aggressive --focus-growth -n 15

# 3. Full analysis (15 minutes)
python main.py --risk-profile aggressive --focus-growth --focus-momentum
```

## 📱 MOBILE-FRIENDLY COMMANDS

### **📲 SHORT COMMANDS FOR MOBILE TERMINALS**
```bash
# Ultra-short for mobile typing
python main.py -r aggressive -n 5            # Quick test
python main.py -r aggressive -g -n 10        # Growth focus
python main.py -r aggressive -m -n 10        # Momentum focus
python main.py -r aggressive -g -m -n 15     # Both focus
python main.py -s RELIANCE -r aggressive     # Single stock
```

## 🚀 AUTOMATION SCRIPTS

### **🤖 BATCH AUTOMATION**
```bash
# Create batch file for Windows
echo python main.py --risk-profile aggressive --focus-growth -n 10 > quick_analysis.bat

# Create shell script for Linux/Mac
echo "python main.py --risk-profile aggressive --focus-growth -n 10" > quick_analysis.sh
chmod +x quick_analysis.sh

# Run automation
quick_analysis.bat        # Windows
./quick_analysis.sh       # Linux/Mac
```

### **⏰ SCHEDULED COMMANDS**
```bash
# Windows Task Scheduler command
python "C:\Path\To\Stock_Analysis\main.py" --risk-profile aggressive --focus-growth -n 20

# Linux Cron job command  
0 9 * * 1-5 cd /path/to/Stock_Analysis && python main.py --risk-profile aggressive --focus-growth -n 20
```

## 📊 OUTPUT MANAGEMENT COMMANDS

### **📁 RESULT ACCESS**
```bash
# View latest Excel report
start data\analysis_results\*.xlsx           # Windows
open data/analysis_results/*.xlsx            # Mac
xdg-open data/analysis_results/*.xlsx        # Linux

# Access log files
type logs\*.log                              # Windows latest log
tail -f logs/*.log                           # Linux/Mac live log

# Export management
dir data\exports\                            # Windows list exports
ls -la data/exports/                         # Linux/Mac list exports
```

### **🧹 CLEANUP COMMANDS**
```bash
# Clear cache (improves performance)
rmdir /s data\cache                          # Windows
rm -rf data/cache                            # Linux/Mac

# Clear old logs (older than 7 days)
forfiles /p logs /m *.log /d -7 /c "cmd /c del @path"  # Windows
find logs -name "*.log" -mtime +7 -delete   # Linux/Mac

# Clear old reports (older than 30 days)
forfiles /p reports /m *.xlsx /d -30 /c "cmd /c del @path"  # Windows
find reports -name "*.xlsx" -mtime +30 -delete  # Linux/Mac
```

## 🎯 POWER USER COMMANDS

### **🔧 ADVANCED CUSTOMIZATION**
```bash
# Custom stock list analysis
python main.py -c data/templates/my_watchlist.csv --risk-profile aggressive

# Force fresh data (bypass cache)
python main.py --risk-profile aggressive --force --focus-growth -n 20

# Maximum performance mode
python main.py --risk-profile aggressive -w 8 -b 20 -n 50

# Detailed logging mode
python main.py --risk-profile aggressive --focus-growth -n 15 --verbose
```

### **📊 ANALYSIS COMBINATIONS**
```bash
# Value + Growth + Momentum
python main.py --risk-profile aggressive --focus-growth --focus-momentum --undervalued-only

# High volatility breakout scanner
python main.py --risk-profile aggressive --focus-momentum --min-volatility 30 -n 15

# Portfolio diversification optimizer
python main.py --portfolio-amount 1000000 --risk-profile aggressive --focus-growth --focus-momentum
```

## 🎉 GETTING STARTED PATHS

### **🔰 BEGINNER PATH**
```bash
1. python main.py                            # See main menu
2. python main.py --tools                    # Access tools
3. python tools/verify_setup.py              # Test everything works
4. python main.py --interactive              # Try interactive mode
5. python main.py --risk-profile aggressive -n 5  # First real analysis
```

### **⚡ EXPERT PATH**
```bash
1. python main.py --risk-profile aggressive --focus-growth --focus-momentum -n 15
2. python main.py -s RELIANCE --risk-profile aggressive --focus-growth  
3. python main.py --portfolio-amount 500000 --risk-profile aggressive
4. python main.py --risk-profile aggressive --min-volatility 20 -n 25
```

---

**🎯 THE ORGANIZED STRUCTURE GIVES YOU MAXIMUM FLEXIBILITY WITH MINIMUM COMPLEXITY! 🚀📈**

*Choose your path: Interactive tools for guidance or direct commands for speed!*
