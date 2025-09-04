# Stock Analysis Documentation

## Project Structure

`
stock_analysis/
 core/               # Core configuration and database
    config.py       # Configuration settings
¦   +-- database.py     # Database functionality
+-- analyzers/          # Analysis modules
¦   +-- technical_analyzer.py          # Basic technical analysis
    fundamental_analyzer.py        # Basic fundamental analysis
    enhanced_technical_analyzer.py # Advanced technical analysis
    enhanced_fundamental_analyzer.py # Advanced fundamental analysis
 data_providers/     # Data retrieval modules
    nse_scraper.py  # NSE data scraper
 exporters/          # Data export modules
¦   +-- data_exporter.py # Basic data export
¦   +-- json_export.py  # JSON export
    excel_exporter.py # Excel report generation
 utils/              # Utility functions
`

## Main Components

1. **Core**: Configuration settings and database functionality
2. **Analyzers**: Technical and fundamental analysis modules
3. **Data Providers**: Stock data retrieval from various sources
4. **Exporters**: Export data to various formats (Excel, JSON)
5. **Utils**: Utility functions for the project

## Usage Examples

Check the examples directory for usage examples.
