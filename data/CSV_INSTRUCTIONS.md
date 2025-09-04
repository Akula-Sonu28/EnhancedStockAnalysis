# Using CSV Files for Stock Lists

This guide explains how to use CSV files to provide your own list of stocks for analysis.

## CSV File Format

Create a CSV file with the following columns:

1. `Symbol` (required): The stock symbol/ticker (e.g., "RELIANCE", "TCS")
2. `Company Name` (optional): Full company name (e.g., "Reliance Industries Ltd")

Example:
```
Symbol,Company Name
RELIANCE,Reliance Industries Ltd
TCS,Tata Consultancy Services Ltd
HDFCBANK,HDFC Bank Ltd
```

## Using Your CSV File

Run the analyzer with the `-c` or `--csv` parameter:

```
python analyze_top200_stocks.py --csv data/your_stock_list.csv
```

You can combine this with other parameters:

```
python analyze_top200_stocks.py --csv data/your_stock_list.csv -n 20 -b 5
```

## Template

A template CSV file is provided at `data/stock_list_template.csv`. You can:

1. Use this template directly
2. Copy and modify it
3. Create your own CSV following the format above

## Notes

- If the CSV file cannot be loaded or lacks a `Symbol` column, the default stock list will be used
- Only the first 200 stocks from your CSV will be used (use `-n` parameter to analyze fewer)
- Company names from the CSV will be included in the analysis reports if available
