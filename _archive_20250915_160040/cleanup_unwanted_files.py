#!/usr/bin/env python3
"""
Safe Project Cleanup Script
Removes temporary, redundant, and unwanted files while preserving essential project structure
"""

import os
import shutil
import glob
from pathlib import Path

def cleanup_project():
    """Safely remove unwanted files from the project"""
    
    print("🧹 STARTING SAFE PROJECT CLEANUP")
    print("=" * 50)
    
    # Files and directories to remove (safe to delete)
    files_to_remove = [
        # Temporary setup/fix scripts (no longer needed)
        "fix_risk_category.py",
        "fix_risk_category_comprehensive.py", 
        "enable_dynamic_stock_count.py",
        "enable_top500_analysis.py",
        "reorganize_project_clean.py",
        
        # Redundant documentation files (keeping main README.md)
        "CRITICAL_BUG_FIX_REPORT.md",
        "CSV_UPDATE_INSTRUCTIONS.md", 
        "DYNAMIC_STOCK_COUNT_ENABLED.md",
        "PROJECT_REORGANIZATION_COMPLETE.md",
        "REORGANIZATION_SUMMARY.md",
        
        # This cleanup script itself (after execution)
        "cleanup_unwanted_files.py"
    ]
    
    # Directories to clean up (but not remove completely)
    cache_dirs = [
        "__pycache__",
        "src/__pycache__",
        "tools/__pycache__",
        "scripts/__pycache__"
    ]
    
    removed_count = 0
    
    # Remove individual files
    print("\n📁 REMOVING TEMPORARY FILES:")
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"   ✅ Removed: {file_path}")
                removed_count += 1
            except Exception as e:
                print(f"   ❌ Failed to remove {file_path}: {e}")
        else:
            print(f"   ⚠️  Not found: {file_path}")
    
    # Clean cache directories
    print(f"\n🗂️  CLEANING CACHE DIRECTORIES:")
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                # Remove all .pyc files
                pyc_files = glob.glob(f"{cache_dir}/**/*.pyc", recursive=True)
                for pyc_file in pyc_files:
                    os.remove(pyc_file)
                    removed_count += 1
                
                # Remove __pycache__ directories if empty
                for root, dirs, files in os.walk(cache_dir, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        if dir_name == "__pycache__":
                            try:
                                os.rmdir(dir_path)
                                print(f"   ✅ Removed empty cache: {dir_path}")
                                removed_count += 1
                            except OSError:
                                pass  # Directory not empty, that's fine
                                
                print(f"   ✅ Cleaned cache: {cache_dir}")
            except Exception as e:
                print(f"   ❌ Error cleaning {cache_dir}: {e}")
    
    # Find and remove any .log files older than today (keep recent logs)
    print(f"\n📝 CHECKING LOG FILES:")
    log_files = glob.glob("data/*.log") + glob.glob("logs/*.log")
    for log_file in log_files:
        # Keep recent log files, you can adjust this logic if needed
        print(f"   ℹ️  Keeping log file: {log_file}")
    
    print(f"\n🎉 CLEANUP COMPLETED!")
    print("=" * 50)
    print(f"📊 Total files removed: {removed_count}")
    print("\n✅ PRESERVED ESSENTIAL STRUCTURE:")
    print("   - Main analysis files (analyze_top200_stocks_enhanced.py, main.py)")
    print("   - All source code (src/, tools/, scripts/)")
    print("   - Documentation (docs/, README.md)")
    print("   - Data and reports (data/, reports/)")
    print("   - Backup directory (backup/) - fully preserved")
    print("   - Configuration files (requirements.txt, setup.py)")
    print("   - Stock lists and templates")
    
    print(f"\n💡 PROJECT IS NOW CLEAN AND READY TO USE!")
    
    # Show current directory structure
    print(f"\n📁 CURRENT PROJECT STRUCTURE:")
    essential_items = [
        "analyze_top200_stocks_enhanced.py",
        "main.py", 
        "src/",
        "tools/",
        "scripts/",
        "data/",
        "reports/",
        "docs/",
        "backup/",
        "README.md",
        "requirements.txt",
        "stock_list_template.csv"
    ]
    
    for item in essential_items:
        if os.path.exists(item):
            print(f"   ✅ {item}")
        else:
            print(f"   ❌ {item} (missing)")

if __name__ == "__main__":
    cleanup_project()
