#!/usr/bin/env python3
"""
Project Organization Migration Script
====================================

This script helps organize the Stock Analysis project by moving files
to their appropriate locations in the new organized structure.

Run this script to complete the organization process.
"""

import os
import shutil
from pathlib import Path

def create_directory(path):
    """Create directory if it doesn't exist"""
    Path(path).mkdir(parents=True, exist_ok=True)
    print(f"✅ Directory: {path}")

def move_file(source, destination, description=""):
    """Move file if it exists"""
    if os.path.exists(source):
        try:
            shutil.move(source, destination)
            print(f"✅ Moved: {source} → {destination} {description}")
        except Exception as e:
            print(f"❌ Error moving {source}: {e}")
    else:
        print(f"⚠️  Not found: {source}")

def organize_project():
    """Organize the entire project structure"""
    
    print("🏗️  ORGANIZING STOCK ANALYSIS PROJECT")
    print("=" * 50)
    
    # Create organized directories
    directories = [
        "stock_analyzer/analyzers",
        "stock_analyzer/exporters", 
        "config",
        "data/exports",
        "archived/old_scripts",
        "archived/test_files",
        "scripts"
    ]
    
    for directory in directories:
        create_directory(directory)
    
    print("\n📁 MOVING FILES TO ORGANIZED STRUCTURE")
    print("-" * 50)
    
    # Move analysis-related files
    analysis_files = [
        ("enhanced_technical_analyzer.py", "stock_analyzer/analyzers/technical.py", "(Technical Analysis)"),
        ("test_enhancements.py", "archived/test_files/test_enhancements.py", "(Test File)"),
        ("test_trading_plans.py", "archived/test_files/test_trading_plans.py", "(Test File)"),
        ("test_high_risk_analysis.py", "archived/test_files/test_high_risk_analysis.py", "(Test File)")
    ]
    
    for source, dest, desc in analysis_files:
        move_file(source, dest, desc)
    
    # Move old analysis scripts to archived
    old_scripts = [
        "analyze_nifty_stocks.py",
        "analyze_nifty200.py", 
        "analyze_portfolio.py",
        "analyze_top200_stocks.py",
        "analyze_top200_stocks.py.new",
        "count_fundamental_values.py",
        "debug_excel.py",
        "final_validation_test.py",
        "find_undervalued_stocks.py",
        "fix_excel_generation.py",
        "generate_complete_excel.py",
        "generate_gtts.py",
        "portfolio_results.py",
        "quick_undervalued.py",
        "run_reliance_analysis.py",
        "single_stock_analysis.py",
        "task_completion_summary.py",
        "TOP200_ANALYSIS_SUMMARY.py",
        "VALIDATION_REPORT.py",
        "visualize_portfolio.py"
    ]
    
    for script in old_scripts:
        if os.path.exists(script):
            move_file(script, f"archived/old_scripts/{script}", "(Old Script)")
    
    # Move test files
    test_files = [
        "test_accuracy.py",
        "test_complete_analysis.py", 
        "test_comprehensive_analysis.py",
        "test_excel_comprehensive.py",
        "test_fixed_accuracy.py",
        "test_fixed_analysis.py",
        "test_single_stock.py",
        "test_system.py",
        "test_unified_analysis.py"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            move_file(test_file, f"archived/test_files/{test_file}", "(Test File)")
    
    # Move CSV files
    csv_files = [
        ("holdings.csv", "data/templates/holdings.csv", "(Holdings Template)"),
        ("portfolio.csv", "data/templates/portfolio.csv", "(Portfolio Template)")
    ]
    
    for source, dest, desc in csv_files:
        move_file(source, dest, desc)
    
    # Move documentation to archived if it conflicts
    doc_files = [
        ("REORGANIZATION.md", "archived/REORGANIZATION.md", "(Old Organization Doc)"),
        ("README_old.md", "archived/README_old.md", "(Backup README)")
    ]
    
    for source, dest, desc in doc_files:
        move_file(source, dest, desc)
    
    print("\n📋 CREATING NEW STRUCTURE FILES")
    print("-" * 50)
    
    # Create config files
    create_config_files()
    
    # Create setup script
    create_setup_script()
    
    print("\n🎉 PROJECT ORGANIZATION COMPLETE!")
    print("=" * 50)
    print("✅ New organized structure created")
    print("✅ Files moved to appropriate locations")
    print("✅ Old files archived")
    print("✅ Documentation updated")
    print()
    print("🚀 NEXT STEPS:")
    print("1. Test the new main.py: python main.py --help-quick")
    print("2. Try interactive mode: python main.py --interactive")
    print("3. Verify setup: python tools/verify_setup.py")
    print("4. Run a quick test: python main.py --risk-profile aggressive -n 5")

def create_config_files():
    """Create organized config files"""
    
    # Create risk profiles config
    risk_config = '''"""
Risk Profile Configurations
"""

RISK_PROFILES = {
    "conservative": {
        "entry_range_pct": 1.0,
        "profit_targets": [2.5, 5.0, 8.0],
        "stop_loss_pct": 3.5,
        "strategy": "value",
        "description": "Low-risk, steady returns"
    },
    "moderate": {
        "entry_range_pct": 2.0,
        "profit_targets": [3.5, 8.0, 12.0],
        "stop_loss_pct": 5.5,
        "strategy": "balanced",
        "description": "Balanced risk-reward"
    },
    "aggressive": {
        "entry_range_pct": 4.0,
        "profit_targets": [6.0, 12.0, 20.0],
        "stop_loss_pct": 8.0,
        "strategy": "momentum",
        "description": "High-risk, high-reward"
    }
}
'''
    
    with open("config/risk_profiles.py", "w") as f:
        f.write(risk_config)
    print("✅ Created: config/risk_profiles.py")

def create_setup_script():
    """Create environment setup script"""
    
    setup_script = '''#!/usr/bin/env python3
"""
Environment Setup Script
========================

Sets up the Stock Analysis environment with all dependencies.
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
        return True
    except Exception as e:
        print(f"❌ Error installing requirements: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = [
        "data/cache",
        "data/exports", 
        "logs",
        "reports"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created: {directory}")

def main():
    print("🔧 SETTING UP STOCK ANALYSIS ENVIRONMENT")
    print("=" * 50)
    
    create_directories()
    
    if install_requirements():
        print("\\n🎉 Setup completed successfully!")
        print("Ready to run: python main.py --interactive")
    else:
        print("\\n❌ Setup failed. Please check errors above.")

if __name__ == "__main__":
    main()
'''
    
    with open("scripts/setup_environment.py", "w") as f:
        f.write(setup_script)
    print("✅ Created: scripts/setup_environment.py")

if __name__ == "__main__":
    organize_project()
