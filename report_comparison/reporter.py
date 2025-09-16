#!/usr/bin/env python3
"""
Report Comparison Excel Generator
================================

Generates detailed Excel reports comparing two Enhanced Stock Reports
with visual indicators, charts, and actionable insights.

Author: Enhanced Stock Analysis System
Version: 1.0.0
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import BarChart, Reference
from typing import Dict, List
import logging

class ComparisonReportGenerator:
    """Generate Excel reports for stock comparison analysis"""
    
    def __init__(self):
        self.output_dir = "reports/comparisons"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Define color schemes
        self.colors = {
            'gain': '92D050',      # Green
            'loss': 'FF6B6B',      # Red  
            'new': '4BACC6',       # Blue
            'removed': 'FFC000',   # Orange
            'neutral': 'F2F2F2',   # Light Gray
            'header': '4472C4'     # Dark Blue
        }
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def create_summary_sheet(self, wb: openpyxl.Workbook, results: Dict):
        """Create executive summary sheet"""
        ws = wb.create_sheet("Executive_Summary", 0)
        
        market = results['market_insights']
        insights = results['performance_insights']
        
        # Title
        ws['A1'] = "📊 STOCK REPORT COMPARISON - EXECUTIVE SUMMARY"
        ws['A1'].font = Font(size=16, bold=True)
        ws.merge_cells('A1:F1')
        
        # Report info
        ws['A3'] = "Report Comparison Details:"
        ws['A3'].font = Font(bold=True)
        
        ws['A4'] = f"Previous Report: {os.path.basename(results['old_report'])}"
        ws['A5'] = f"Current Report: {os.path.basename(results['new_report'])}"
        ws['A6'] = f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Market insights
        ws['A8'] = "🎯 MARKET INSIGHTS"
        ws['A8'].font = Font(size=14, bold=True)
        
        ws['A10'] = "Market Sentiment:"
        ws['B10'] = market['market_sentiment']
        ws['B10'].font = Font(bold=True)
        
        ws['A11'] = "Dominant Trend:"
        ws['B11'] = market['dominant_trend']
        
        ws['A12'] = "Risk Appetite:"
        ws['B12'] = market['risk_appetite']
        
        # Performance summary
        ws['A14'] = "📈 PERFORMANCE SUMMARY"
        ws['A14'].font = Font(size=14, bold=True)
        
        ws['A16'] = "Top Gainers Count:"
        ws['B16'] = len(insights['biggest_gainers'])
        
        ws['A17'] = "Top Losers Count:"
        ws['B17'] = len(insights['biggest_losers'])
        
        ws['A18'] = "New Entries:"
        ws['B18'] = len(insights['new_entries'])
        
        ws['A19'] = "Removed Stocks:"
        ws['B19'] = len(insights['removed_stocks'])
        
        # Key observations
        ws['A21'] = "📋 KEY OBSERVATIONS"
        ws['A21'].font = Font(size=14, bold=True)
        
        row = 23
        for obs in market['key_observations']:
            ws[f'A{row}'] = f"• {obs}"
            row += 1
        
        # Apply styling
        self._apply_header_styling(ws, 'A1:F1')
        
        # Set column widths
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 40
    
    def create_detailed_comparison_sheet(self, wb: openpyxl.Workbook, results: Dict):
        """Create detailed stock-by-stock comparison"""
        ws = wb.create_sheet("Detailed_Comparison")
        
        comparison_df = results['comparison_data']
        
        # Headers
        headers = ['Symbol', 'Old_Rank', 'New_Rank', 'Rank_Change', 'Rank_Movement']
        
        # Add additional columns if they exist in the data
        for col in comparison_df.columns:
            if col not in headers and not col.endswith('_Old') and not col.endswith('_New'):
                if 'Price' in col or 'Return' in col or 'Score' in col:
                    headers.append(f"{col}_Old")
                    headers.append(f"{col}_New")
        
        # Write headers
        for idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=idx, value=header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color=self.colors['header'], end_color=self.colors['header'], fill_type="solid")
        
        # Write data
        for row_idx, (_, row) in enumerate(comparison_df.iterrows(), 2):
            for col_idx, header in enumerate(headers, 1):
                if header in comparison_df.columns:
                    value = row[header]
                    cell = ws.cell(row=row_idx, column=col_idx, value=value)
                    
                    # Apply conditional formatting
                    if header == 'Rank_Change':
                        if pd.notna(value):
                            if value > 0:
                                cell.fill = PatternFill(start_color=self.colors['gain'], end_color=self.colors['gain'], fill_type="solid")
                            elif value < 0:
                                cell.fill = PatternFill(start_color=self.colors['loss'], end_color=self.colors['loss'], fill_type="solid")
                    
                    elif header == 'Rank_Movement':
                        if 'Rise' in str(value):
                            cell.fill = PatternFill(start_color=self.colors['gain'], end_color=self.colors['gain'], fill_type="solid")
                        elif 'Fall' in str(value):
                            cell.fill = PatternFill(start_color=self.colors['loss'], end_color=self.colors['loss'], fill_type="solid")
                        elif 'New' in str(value):
                            cell.fill = PatternFill(start_color=self.colors['new'], end_color=self.colors['new'], fill_type="solid")
        
        # Auto-adjust column widths
        for col_idx in range(1, len(headers) + 1):
            max_length = 0
            column_letter = openpyxl.utils.get_column_letter(col_idx)
            
            # Check header length
            max_length = len(str(headers[col_idx - 1]))
            
            # Check data lengths
            for row_idx in range(2, len(comparison_df) + 2):
                cell = ws.cell(row=row_idx, column=col_idx)
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 20)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    def create_gainers_losers_sheet(self, wb: openpyxl.Workbook, results: Dict):
        """Create focused gainers and losers sheet"""
        ws = wb.create_sheet("Gainers_Losers")
        
        insights = results['performance_insights']
        
        # Top Gainers section
        ws['A1'] = "🚀 TOP GAINERS (Ranking Improved)"
        ws['A1'].font = Font(size=14, bold=True, color='006100')
        ws.merge_cells('A1:E1')
        
        # Gainers headers
        gainers_headers = ['Symbol', 'Old Rank', 'New Rank', 'Rank Change', 'Movement']
        for idx, header in enumerate(gainers_headers, 1):
            cell = ws.cell(row=3, column=idx, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color=self.colors['gain'], end_color=self.colors['gain'], fill_type="solid")
        
        # Gainers data
        for idx, stock in enumerate(insights['biggest_gainers'][:10], 4):
            ws.cell(row=idx, column=1, value=stock['Symbol'])
            ws.cell(row=idx, column=2, value=stock['Old_Rank'])
            ws.cell(row=idx, column=3, value=stock['New_Rank'])
            ws.cell(row=idx, column=4, value=stock['Rank_Change'])
            ws.cell(row=idx, column=5, value=f"↗️ +{stock['Rank_Change']}")
        
        # Top Losers section
        start_row = len(insights['biggest_gainers']) + 7
        ws[f'A{start_row}'] = "💥 TOP DECLINERS (Ranking Dropped)"
        ws[f'A{start_row}'].font = Font(size=14, bold=True, color='9C0006')
        ws.merge_cells(f'A{start_row}:E{start_row}')
        
        # Losers headers
        header_row = start_row + 2
        for idx, header in enumerate(gainers_headers, 1):
            cell = ws.cell(row=header_row, column=idx, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color=self.colors['loss'], end_color=self.colors['loss'], fill_type="solid")
        
        # Losers data
        for idx, stock in enumerate(insights['biggest_losers'][:10], header_row + 1):
            ws.cell(row=idx, column=1, value=stock['Symbol'])
            ws.cell(row=idx, column=2, value=stock['Old_Rank'])
            ws.cell(row=idx, column=3, value=stock['New_Rank'])
            ws.cell(row=idx, column=4, value=stock['Rank_Change'])
            ws.cell(row=idx, column=5, value=f"↘️ {stock['Rank_Change']}")
        
        # New Entries section
        new_start = start_row + len(insights['biggest_losers']) + 5
        if insights['new_entries']:
            ws[f'A{new_start}'] = "🌟 NEW ENTRIES"
            ws[f'A{new_start}'].font = Font(size=14, bold=True, color='0070C0')
            
            for idx, stock in enumerate(insights['new_entries'][:5], new_start + 2):
                ws.cell(row=idx, column=1, value=stock['Symbol'])
                ws.cell(row=idx, column=2, value="New")
                ws.cell(row=idx, column=3, value=stock['New_Rank'])
        
        # Auto-adjust column widths - safer approach
        column_widths = {'A': 15, 'B': 12, 'C': 12, 'D': 15, 'E': 20}
        for col_letter, width in column_widths.items():
            ws.column_dimensions[col_letter].width = width
    
    def _apply_header_styling(self, ws, range_str):
        """Apply header styling to a range"""
        for row in ws[range_str]:
            for cell in row:
                cell.fill = PatternFill(start_color=self.colors['header'], end_color=self.colors['header'], fill_type="solid")
                cell.font = Font(bold=True, color='FFFFFF')
                cell.alignment = Alignment(horizontal='center')
    
    def generate_comparison_report(self, results: Dict) -> str:
        """Generate complete Excel comparison report"""
        try:
            timestamp = results['timestamp']
            filename = f"Stock_Comparison_Report_{timestamp}.xlsx"
            filepath = os.path.join(self.output_dir, filename)
            
            # Create workbook
            wb = openpyxl.Workbook()
            wb.remove(wb.active)  # Remove default sheet
            
            # Create sheets
            self.create_summary_sheet(wb, results)
            self.create_detailed_comparison_sheet(wb, results)
            self.create_gainers_losers_sheet(wb, results)
            
            # Save workbook
            wb.save(filepath)
            
            file_size = os.path.getsize(filepath)
            
            print(f"✅ Comparison report generated: {filename}")
            print(f"   📁 File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
            print(f"   📂 Location: {self.output_dir}")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error generating Excel report: {e}")
            raise


if __name__ == "__main__":
    # Test the report generator
    from analyzer import ReportComparator
    
    try:
        # Run comparison
        comparator = ReportComparator()
        results = comparator.compare_reports()
        
        # Generate Excel report
        generator = ComparisonReportGenerator()
        report_path = generator.generate_comparison_report(results)
        
        print(f"\n🎉 Complete comparison analysis finished!")
        print(f"📊 Excel Report: {report_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")