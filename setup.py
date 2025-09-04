"""
Setup script for Stock Analysis Package
"""
from setuptools import setup, find_packages
import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip()]
    
    for package in requirements:
        try:
            print(f"Installing {package}...")
            if package.startswith('#'):
                continue  # Skip comments
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    print("✅ All packages installed successfully!")
    return True

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")
    
    directories = [
        'data',
        'logs',
        'reports',
        'examples'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created {directory}")
    
    print("✅ All directories created!")

def setup_textblob():
    """Download TextBlob corpora"""
    print("📚 Setting up TextBlob...")
    try:
        import textblob
        from textblob import download_corpora
        download_corpora.download_all()
        print("✅ TextBlob corpora downloaded!")
    except Exception as e:
        print(f"⚠️  TextBlob setup warning: {e}")

def run_setup_py():
    """Run setuptools setup"""
    try:
        setup(
            name="stock_analysis",
            version="1.0.0",
            author="Stock Analysis Team",
            author_email="example@example.com",
            description="A comprehensive stock analysis package for Indian markets",
            long_description=open('README.md', 'r', encoding='utf-8').read(),
            long_description_content_type="text/markdown",
            url="https://github.com/yourusername/stock_analysis",
            packages=find_packages(),
            classifiers=[
                "Programming Language :: Python :: 3",
                "License :: OSI Approved :: MIT License",
                "Operating System :: OS Independent",
            ],
            python_requires=">=3.7",
            install_requires=[line.strip() for line in open('requirements.txt', 'r', encoding='utf-8') if line.strip() and not line.startswith('#')],
            entry_points={
                'console_scripts': [
                    'stock-analysis=scripts.run_analysis:main',
                ],
            },
        )
        print("✅ Package setup complete!")
        return True
    except Exception as e:
        print(f"❌ Package setup failed: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Stock Analysis Package Setup")
    print("=" * 50)
    
    # Create directories
    create_directories()
    
    # Install packages
    if install_requirements():
        # Setup TextBlob
        setup_textblob()
        
        # Run setuptools setup
        run_setup_py()
        
        print("\n✅ Setup completed successfully!")
        print("\nYou can now run:")
        print("  python scripts/run_analysis.py        - For full analysis")
        print("  python -m stock_analysis.main         - To use as a module")
        print("  stock-analysis                        - If installed via pip")
    else:
        print("\n❌ Setup failed. Please check the errors above.")

if __name__ == "__main__":
    main()
