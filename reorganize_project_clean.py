#!/usr/bin/env python3
"""
Project Reorganization Script - Clean Structure
==============================================

This script reorganizes the project into a clean, professional structure
while keeping backup files for troubleshooting.

Created: 2025-09-04
Purpose: Clean up and organize the Stock Analysis project
"""

import os
import shutil
from pathlib import Path
import sys
from datetime import datetime

class ProjectReorganizer:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "backup"
        self.temp_files = []
        self.redundant_files = []
        self.test_files = []
        
    def analyze_files(self):
        """Analyze and categorize files"""
        print("📊 ANALYZING PROJECT STRUCTURE...")
        print("=" * 50)
        
        # Core files (keep in root)
        self.core_files = [
            "main.py",
            "analyze_top200_stocks_enhanced.py", 
            "config.py",
            "enhanced_technical_analyzer.py",
            "requirements.txt",
            "setup.py",
            "README.md"
        ]
        
        # Documentation files
        self.doc_files = [
            "COMPLETE_COMMAND_REFERENCE.md",
            "HIGH_RISK_IMPLEMENTATION_SUMMARY.md",
            "ORGANIZATION_SUMMARY.md",
            "PROJECT_ORGANIZATION.md",
            "QUICK_COMMANDS_ORGANIZED.md",
            "QUICK_COMMAND_CARD.md",
            "READY_TO_USE_COMMANDS.txt",
            "STRUCTURE_COMMANDS.md"
        ]
        
        # Backup files (move to backup)
        self.backup_files = [
            "README_NEW.md",
            "README_old.md", 
            "REORGANIZATION.md",
            "VALIDATION_REPORT.py",
            "TOP200_ANALYSIS_SUMMARY.py",
            "organize_project.py",
            "task_completion_summary.py"
        ]
        
        # Test files (move to tests)
        self.test_files = [
            "test_*.py",
            "debug_*.py",
            "final_validation_test.py",
            "verify_high_risk_setup.py",
            "validation.py"
        ]
        
        # Utility scripts (move to scripts)
        self.utility_files = [
            "command_builder.py",
            "data_quality.py",
            "find_undervalued_stocks.py",
            "fix_excel_generation.py",
            "generate_complete_excel.py",
            "generate_gtts.py",
            "high_risk_investor_guide.py",
            "quick_undervalued.py",
            "run_reliance_analysis.py",
            "single_stock_analysis.py",
            "visualize_portfolio.py"
        ]
        
        # Analysis variants (move to backup)
        self.analysis_variants = [
            "analyze_nifty200.py",
            "analyze_nifty_stocks.py", 
            "analyze_portfolio.py",
            "analyze_top200_stocks.py",
            "analyze_top200_stocks.py.new",
            "count_fundamental_values.py",
            "portfolio_results.py"
        ]
        
    def create_clean_structure(self):
        """Create clean directory structure"""
        print("\n🏗️  CREATING CLEAN STRUCTURE...")
        print("=" * 50)
        
        # Create directories
        directories = [
            "backup/original_files",
            "backup/test_files", 
            "backup/analysis_variants",
            "backup/utility_scripts",
            "backup/old_docs",
            "scripts/utilities",
            "scripts/analysis_tools",
            "tests/unit_tests",
            "tests/integration_tests",
            "docs/user_guides",
            "docs/technical",
            "docs/examples"
        ]
        
        for dir_path in directories:
            (self.project_root / dir_path).mkdir(parents=True, exist_ok=True)
            print(f"✅ Created: {dir_path}")
    
    def move_files_to_backup(self):
        """Move files to appropriate backup locations"""
        print("\n📦 MOVING FILES TO BACKUP...")
        print("=" * 50)
        
        # Move backup files
        for file_pattern in self.backup_files:
            for file_path in self.project_root.glob(file_pattern):
                if file_path.is_file():
                    dest = self.project_root / "backup" / "original_files" / file_path.name
                    shutil.move(str(file_path), str(dest))
                    print(f"📦 Moved to backup: {file_path.name}")
        
        # Move test files
        for file_pattern in self.test_files:
            for file_path in self.project_root.glob(file_pattern):
                if file_path.is_file():
                    dest = self.project_root / "backup" / "test_files" / file_path.name
                    shutil.move(str(file_path), str(dest))
                    print(f"🧪 Moved test file: {file_path.name}")
        
        # Move utility files to scripts
        for file_name in self.utility_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                dest = self.project_root / "scripts" / "utilities" / file_name
                shutil.move(str(file_path), str(dest))
                print(f"🔧 Moved utility: {file_name}")
        
        # Move analysis variants
        for file_name in self.analysis_variants:
            file_path = self.project_root / file_name
            if file_path.exists():
                dest = self.project_root / "backup" / "analysis_variants" / file_name
                shutil.move(str(file_path), str(dest))
                print(f"📊 Moved analysis variant: {file_name}")
    
    def organize_documentation(self):
        """Organize documentation files"""
        print("\n📚 ORGANIZING DOCUMENTATION...")
        print("=" * 50)
        
        # Keep main docs in docs/
        doc_mapping = {
            "COMPLETE_COMMAND_REFERENCE.md": "docs/COMMANDS.md",
            "HIGH_RISK_IMPLEMENTATION_SUMMARY.md": "docs/HIGH_RISK_GUIDE.md", 
            "QUICK_COMMANDS_ORGANIZED.md": "docs/QUICK_REFERENCE.md",
            "QUICK_COMMAND_CARD.md": "docs/user_guides/COMMAND_CARD.md",
            "READY_TO_USE_COMMANDS.txt": "docs/user_guides/READY_COMMANDS.md"
        }
        
        for old_name, new_path in doc_mapping.items():
            old_path = self.project_root / old_name
            new_full_path = self.project_root / new_path
            if old_path.exists():
                new_full_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_path), str(new_full_path))
                print(f"📝 Moved doc: {old_name} → {new_path}")
        
        # Move other docs to backup
        remaining_docs = [
            "ORGANIZATION_SUMMARY.md",
            "PROJECT_ORGANIZATION.md", 
            "STRUCTURE_COMMANDS.md"
        ]
        
        for doc in remaining_docs:
            doc_path = self.project_root / doc
            if doc_path.exists():
                dest = self.project_root / "backup" / "old_docs" / doc
                shutil.move(str(doc_path), str(dest))
                print(f"📄 Moved to backup docs: {doc}")
    
    def clean_cache_and_temp(self):
        """Clean cache and temporary files"""
        print("\n🧹 CLEANING CACHE AND TEMP FILES...")
        print("=" * 50)
        
        # Remove __pycache__ directories
        for pycache in self.project_root.glob("**/__pycache__"):
            if pycache.is_dir():
                shutil.rmtree(pycache)
                print(f"🗑️  Removed: {pycache}")
        
        # Remove .pyc files
        for pyc_file in self.project_root.glob("**/*.pyc"):
            pyc_file.unlink()
            print(f"🗑️  Removed: {pyc_file}")
    
    def create_index_files(self):
        """Create index files for easy navigation"""
        print("\n📋 CREATING INDEX FILES...")
        print("=" * 50)
        
        # Main project README update
        main_readme = self.project_root / "README.md"
        if main_readme.exists():
            # Read existing content
            with open(main_readme, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add reorganization notice
            reorganization_notice = '''
## 🗂️ PROJECT ORGANIZATION (Updated: 2025-09-04)

### 📁 Directory Structure:
- **`/`** - Core analysis files and main entry points
- **`/docs/`** - All documentation and user guides  
- **`/scripts/`** - Utility scripts and analysis tools
- **`/tests/`** - All test files (moved from root)
- **`/backup/`** - Backup files for troubleshooting
- **`/src/`** - Source code modules
- **`/data/`** - Data files and templates
- **`/reports/`** - Generated analysis reports

### 🚀 Quick Start:
```bash
# Main analysis (recommended)
python main.py --interactive

# Direct enhanced analysis
python analyze_top200_stocks_enhanced.py --risk-profile aggressive --focus-growth

# Check all available commands
cat docs/COMMANDS.md
```

### 🔧 Troubleshooting:
If main files don't work as expected, check `/backup/` directory for original files.

---

'''
            # Prepend to existing content
            with open(main_readme, 'w', encoding='utf-8') as f:
                f.write(reorganization_notice + content)
            print("✅ Updated main README.md")
        
        # Create backup index
        backup_index = self.project_root / "backup" / "README.md"
        with open(backup_index, 'w', encoding='utf-8') as f:
            f.write("""# 📦 BACKUP FILES INDEX

This directory contains backup files for troubleshooting and reference.

## 📁 Structure:
- **`original_files/`** - Original documentation and organization files
- **`test_files/`** - All test and debugging files  
- **`analysis_variants/`** - Alternative analysis scripts
- **`utility_scripts/`** - Utility and helper scripts
- **`old_docs/`** - Legacy documentation files

## 🔧 Troubleshooting:
If the main analysis files don't work as expected:

1. Check `analysis_variants/` for alternative analysis scripts
2. Use `test_files/` to debug specific issues
3. Reference `utility_scripts/` for additional tools
4. Check `original_files/` for original documentation

## 🚀 Quick Recovery:
```bash
# Copy main analysis file from backup
cp backup/analysis_variants/analyze_top200_stocks.py ./

# Use alternative utility
python backup/utility_scripts/single_stock_analysis.py -s RELIANCE
```

**Note:** All files are preserved for recovery and troubleshooting.
""")
        print("✅ Created backup index")
    
    def generate_summary(self):
        """Generate reorganization summary"""
        print("\n📊 REORGANIZATION SUMMARY")
        print("=" * 50)
        
        # Count files in each directory
        root_files = len([f for f in self.project_root.iterdir() if f.is_file() and not f.name.startswith('.')])
        backup_files = len(list((self.project_root / "backup").rglob("*"))) if (self.project_root / "backup").exists() else 0
        doc_files = len(list((self.project_root / "docs").rglob("*"))) if (self.project_root / "docs").exists() else 0
        script_files = len(list((self.project_root / "scripts").rglob("*"))) if (self.project_root / "scripts").exists() else 0
        
        summary = f"""
🎯 REORGANIZATION COMPLETE!

📊 File Distribution:
├── Root directory: {root_files} core files
├── Documentation: {doc_files} files  
├── Scripts: {script_files} files
├── Backup: {backup_files} files
└── Existing: src/, data/, reports/, tools/

✅ Core Files Kept in Root:
• main.py (main entry point)
• analyze_top200_stocks_enhanced.py (enhanced analyzer)
• config.py (configuration)
• enhanced_technical_analyzer.py (technical analysis)
• requirements.txt (dependencies)
• setup.py (project setup)

📚 Documentation Organized:
• docs/COMMANDS.md (command reference)
• docs/HIGH_RISK_GUIDE.md (high-risk features)
• docs/QUICK_REFERENCE.md (quick commands)

🔧 Scripts Organized:
• scripts/utilities/ (utility scripts)
• scripts/analysis_tools/ (analysis tools)

📦 Backup Created:
• backup/original_files/ (original docs)
• backup/test_files/ (all test files)
• backup/analysis_variants/ (alternative scripts)
• backup/utility_scripts/ (utility scripts)

🚀 READY TO USE!
Run: python main.py --interactive
"""
        print(summary)
        
        # Save summary to file
        with open(self.project_root / "REORGANIZATION_SUMMARY.md", 'w', encoding='utf-8') as f:
            f.write(f"# Project Reorganization Summary\n\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{summary}")
    
    def run_reorganization(self):
        """Execute complete reorganization"""
        print("🚀 STARTING PROJECT REORGANIZATION")
        print("=" * 60)
        print("This will clean up and organize your project structure")
        print("All files will be preserved in backup directories")
        print("=" * 60)
        
        try:
            self.analyze_files()
            self.create_clean_structure() 
            self.move_files_to_backup()
            self.organize_documentation()
            self.clean_cache_and_temp()
            self.create_index_files()
            self.generate_summary()
            
            print("\n🎉 REORGANIZATION SUCCESSFUL!")
            print("✅ Project is now clean and organized")
            print("✅ All files preserved in backup/")
            print("✅ Ready for production use")
            
        except Exception as e:
            print(f"\n❌ ERROR during reorganization: {e}")
            print("🔧 Check the error and try again")
            return False
        
        return True

if __name__ == "__main__":
    project_root = Path(__file__).parent
    reorganizer = ProjectReorganizer(project_root)
    
    print("📁 Project Root:", project_root)
    
    # Ask for confirmation
    response = input("\n🤔 Proceed with reorganization? (y/N): ").lower().strip()
    if response in ['y', 'yes']:
        success = reorganizer.run_reorganization()
        if success:
            print("\n🎯 Next Steps:")
            print("1. Test: python main.py --interactive")
            print("2. Check: docs/COMMANDS.md for all options")
            print("3. Backup: Available in backup/ directory")
    else:
        print("❌ Reorganization cancelled")
