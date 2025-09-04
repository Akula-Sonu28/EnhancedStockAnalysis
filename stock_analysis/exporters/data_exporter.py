# Data Exporter: Export results to CSV/Excel and create summaries
import os
import pandas as pd
import logging
from datetime import datetime
from config import CSV_OUTPUT, EXCEL_OUTPUT

def export_data(df):
    """
    Export analyzed stock data to CSV and Excel files
    df: DataFrame with stock analysis results
    """
    try:
        print("\nPreparing to export data...")
        # Ensure output directory exists
        os.makedirs(os.path.dirname(CSV_OUTPUT), exist_ok=True)
        
        # Sort by overall score
        print("Sorting stocks by overall score...")
        df = df.sort_values('OverallScore', ascending=False)
        
        # Export to CSV
        print(f"Exporting to CSV: {CSV_OUTPUT}")
        df.to_csv(CSV_OUTPUT, index=False)
        print("✓ CSV export complete")
        
        # Export to Excel with formatting
        print(f"Exporting to Excel: {EXCEL_OUTPUT}")
        with pd.ExcelWriter(EXCEL_OUTPUT, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Stock Analysis')
        
        # Get the xlsxwriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Stock Analysis']
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'bg_color': '#D9D9D9',
            'border': 1
        })
        
        # Write headers with format
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Auto-adjust columns width
        for idx, col in enumerate(df):
            series = df[col]
            max_len = max(
                series.astype(str).apply(len).max(),
                len(str(series.name))
            ) + 1
            worksheet.set_column(idx, idx, max_len)
        
        # Save Excel file
        writer.close()
        logging.info(f"Data exported to {EXCEL_OUTPUT}")
        
    except Exception as e:
        logging.error(f"Error exporting data: {str(e)}")
