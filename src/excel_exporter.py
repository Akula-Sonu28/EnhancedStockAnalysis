
"""
Excel Report Generator using openpyxl
"""
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils.dataframe import dataframe_to_rows
from datetime import datetime
import os
import logging

class ExcelReportGenerator:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Define colors
        self.colors = {
            'buy': 'FF90EE90',      # Light Green
            'hold': 'FFFFFF00',     # Yellow
            'sell': 'FFFF6B6B',     # Light Red
            'header': 'FF4472C4',   # Blue
            'neutral': 'FFF2F2F2'   # Light Gray
        }
    
    def generate_daily_report(self, summary_data, technical_data=None, 
                            fundamental_data=None, sentiment_data=None):
        """Generate comprehensive daily Excel report"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"Stock_Report_{date_str}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        
        # Create workbook
        wb = openpyxl.Workbook()
        
        # Remove default sheet
        wb.remove(wb.active)
        
        # Ensure we have DataFrame format
        if not isinstance(summary_data, pd.DataFrame):
            summary_df = pd.DataFrame(summary_data)
        else:
            summary_df = summary_data.copy()
        
        # Fill any missing values with appropriate defaults
        summary_df = self._fill_missing_values(summary_df)
        
        # Create sheets with comprehensive data
        self._create_summary_sheet(wb, summary_df)
        self._create_detailed_analysis_sheet(wb, summary_df)
        
        if technical_data is not None:
            tech_df = technical_data if isinstance(technical_data, pd.DataFrame) else pd.DataFrame(technical_data)
            tech_df = self._fill_missing_values(tech_df)
            self._create_technical_sheet(wb, tech_df)
        else:
            # Create technical sheet from summary data
            tech_cols = [col for col in summary_df.columns if any(tech in col.lower() for tech in ['rsi', 'macd', 'sma', 'ema', 'bb_', 'adx', 'atr', 'technical'])]
            if tech_cols:
                tech_df = summary_df[['symbol'] + tech_cols].copy()
                self._create_technical_sheet(wb, tech_df)
        
        if fundamental_data is not None:
            fund_df = fundamental_data if isinstance(fundamental_data, pd.DataFrame) else pd.DataFrame(fundamental_data)
            fund_df = self._fill_missing_values(fund_df)
            self._create_fundamental_sheet(wb, fund_df)
        else:
            # Create fundamental sheet from summary data
            fund_cols = [col for col in summary_df.columns if any(fund in col.lower() for fund in ['pe_', 'pb_', 'roe', 'debt', 'margin', 'growth', 'ratio', 'fundamental', 'market_cap', 'revenue', 'earnings'])]
            if fund_cols:
                fund_df = summary_df[['symbol'] + fund_cols].copy()
                self._create_fundamental_sheet(wb, fund_df)
        
        if sentiment_data is not None:
            sent_df = sentiment_data if isinstance(sentiment_data, pd.DataFrame) else pd.DataFrame(sentiment_data)
            sent_df = self._fill_missing_values(sent_df)
            self._create_sentiment_sheet(wb, sent_df)
        else:
            # Create sentiment sheet from summary data if available
            sent_cols = [col for col in summary_df.columns if any(sent in col.lower() for sent in ['sentiment', 'news', 'headline'])]
            if sent_cols:
                sent_df = summary_df[['symbol'] + sent_cols].copy()
                self._create_sentiment_sheet(wb, sent_df)
        
        self._create_combined_score_sheet(wb, summary_df)
        self._create_company_overview_sheet(wb, summary_df)
        
        # Save workbook
        wb.save(filepath)
        logging.info(f"Comprehensive Excel report saved: {filepath}")
        return filepath
    
    def _fill_missing_values(self, df):
        """Fill missing values with appropriate defaults"""
        df_filled = df.copy()
        
        # Numeric columns - fill with 0
        numeric_cols = df_filled.select_dtypes(include=[np.number]).columns
        df_filled[numeric_cols] = df_filled[numeric_cols].fillna(0)
        
        # String columns - fill with appropriate defaults
        string_cols = df_filled.select_dtypes(include=['object']).columns
        for col in string_cols:
            if 'symbol' in col.lower():
                df_filled[col] = df_filled[col].fillna('N/A')
            elif 'name' in col.lower():
                df_filled[col] = df_filled[col].fillna('Unknown')
            elif 'sector' in col.lower() or 'industry' in col.lower():
                df_filled[col] = df_filled[col].fillna('Unknown')
            elif 'recommendation' in col.lower():
                df_filled[col] = df_filled[col].fillna('HOLD')
            elif 'rating' in col.lower():
                df_filled[col] = df_filled[col].fillna('Neutral')
            elif 'analysis' in col.lower():
                df_filled[col] = df_filled[col].fillna('No analysis available')
            else:
                df_filled[col] = df_filled[col].fillna('N/A')
        
        return df_filled
    
    def _create_summary_sheet(self, wb, data):
        """Create summary sheet with signals and final scores"""
        ws = wb.create_sheet("Summary", 0)
        
        # Add title
        ws['A1'] = f"Stock Analysis Summary - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        ws.merge_cells('A1:H1')
        
        # Convert data to DataFrame if it's not already
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Add recommendation column based on available score if not present
        if 'Recommendation' not in df.columns:
            # Try to find an overall score or use fundamental score
            score_column = None
            if 'OverallScore' in df.columns:
                score_column = 'OverallScore'
            elif 'overall_score' in df.columns:
                score_column = 'overall_score'
            elif 'fundamental_score' in df.columns:
                score_column = 'fundamental_score'
            elif 'FundamentalScore' in df.columns:
                score_column = 'FundamentalScore'
            
            if score_column:
                df['Recommendation'] = df[score_column].apply(self._get_recommendation)
            else:
                # Default recommendation if no score is available
                df['Recommendation'] = 'HOLD'
        
        # Define columns to display in summary with flexible naming
        column_mapping = {
            'symbol': 'Symbol',
            'company_name': 'Company',
            'sector': 'Sector',
            'industry': 'Industry',
            'current_price': 'Price (₹)',
            'market_cap': 'Market Cap',
            'pe_ratio': 'PE Ratio',
            'pb_ratio': 'PB Ratio',
            'roe': 'ROE (%)',
            'debt_to_equity': 'Debt/Equity',
            'revenue_growth': 'Revenue Growth (%)',
            'earnings_growth': 'Earnings Growth (%)',
            'dividend_yield': 'Dividend Yield (%)',
            'beta': 'Beta',
            '52_week_high': '52W High',
            '52_week_low': '52W Low',
            'fundamental_score': 'Fundamental Score',
            'FundamentalScore': 'Fundamental Score',
            'fundamental_score_final': 'Fundamental Score',
            'TechnicalScore': 'Technical Score',
            'enhanced_technical_score_final': 'Technical Score',
            'legacy_technical_score_final': 'Legacy Technical Score',
            'legacy_technical_score': 'Legacy Technical Score',
            'SentimentScore': 'Sentiment Score',
            'OverallScore': 'Overall Score',
            'overall_score': 'Overall Score',
            'overall_score_triple': 'Overall Score',
            'overall_score_balanced': 'Balanced Score',
            'Recommendation': 'Recommendation'
        }
        
        # Build summary DataFrame with available columns
        summary_data = {}
        for col_key, display_name in column_mapping.items():
            if col_key in df.columns:
                summary_data[display_name] = df[col_key]
        
        # Add any additional important columns that might be available
        important_cols = ['eps', 'book_value', 'enterprise_value', 'employees', 'country']
        for col in important_cols:
            if col in df.columns and col not in column_mapping:
                summary_data[col.replace('_', ' ').title()] = df[col]
        
        summary_df = pd.DataFrame(summary_data)

        # If no unified Technical Score column yet but we have enhanced one, promote it
        if 'Technical Score' not in summary_df.columns:
            if 'enhanced_technical_score_final' in df.columns:
                summary_df['Technical Score'] = df['enhanced_technical_score_final']
            elif 'legacy_technical_score_final' in df.columns:
                summary_df['Technical Score'] = df['legacy_technical_score_final']

        # If no Overall Score column yet but overall_score_triple exists, promote it
        if 'Overall Score' not in summary_df.columns and 'overall_score_triple' in df.columns:
            summary_df['Overall Score'] = df['overall_score_triple']
        
        # Sort by available score if possible
        sort_column = None
        for col in ['Overall Score', 'Fundamental Score', 'Symbol']:
            if col in summary_df.columns:
                sort_column = col
                break
        
        if sort_column and sort_column != 'Symbol':
            summary_df = summary_df.sort_values(sort_column, ascending=False)
        elif 'Symbol' in summary_df.columns:
            summary_df = summary_df.sort_values('Symbol')
        
        # Add headers starting from row 3
        for col_num, column_title in enumerate(summary_df.columns, 1):
            cell = ws.cell(row=3, column=col_num)
            cell.value = column_title
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color=self.colors['header'], 
                                  end_color=self.colors['header'], fill_type='solid')
            cell.alignment = Alignment(horizontal='center')
        
        # Add data
        for r_idx, row in enumerate(dataframe_to_rows(summary_df, index=False, header=False), 4):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.value = value
                
                # Format numbers appropriately
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if c_idx == summary_df.columns.get_loc('Price (₹)') + 1 if 'Price (₹)' in summary_df.columns else -1:
                        cell.number_format = '₹#,##0.00'
                    elif 'Market Cap' in summary_df.columns and c_idx == summary_df.columns.get_loc('Market Cap') + 1:
                        cell.number_format = '#,##0'
                    elif any(x in str(summary_df.columns[c_idx-1]) for x in ['%', 'Ratio', 'Score']):
                        cell.number_format = '0.00'
                
                # Color code recommendations
                if 'Recommendation' in summary_df.columns and c_idx == summary_df.columns.get_loc('Recommendation') + 1:
                    if value == 'BUY':
                        cell.fill = PatternFill(start_color=self.colors['buy'], 
                                              end_color=self.colors['buy'], fill_type='solid')
                    elif value == 'SELL':
                        cell.fill = PatternFill(start_color=self.colors['sell'], 
                                              end_color=self.colors['sell'], fill_type='solid')
                    elif value == 'HOLD':
                        cell.fill = PatternFill(start_color=self.colors['hold'], 
                                              end_color=self.colors['hold'], fill_type='solid')
        
        # Auto-adjust column widths
        self._auto_adjust_columns(ws)
        
        # Add borders
        if len(summary_df) > 0:
            self._add_borders(ws, 3, len(summary_df) + 3, len(summary_df.columns))
    
    def _create_technical_sheet(self, wb, data):
        """Create comprehensive technical indicators sheet"""
        ws = wb.create_sheet("Technicals")
        
        # Add title
        ws['A1'] = f"Technical Indicators - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        
        # Convert to DataFrame
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Define comprehensive technical indicators
        technical_metrics = [
            ('symbol', 'Symbol'),
            ('TechnicalScore', 'Technical Score'),
            ('rsi', 'RSI (14)'),
            ('macd', 'MACD'),
            ('macd_signal', 'MACD Signal'),
            ('macd_histogram', 'MACD Histogram'),
            ('sma_20', 'SMA 20'),
            ('sma_50', 'SMA 50'),
            ('sma_200', 'SMA 200'),
            ('ema_12', 'EMA 12'),
            ('ema_26', 'EMA 26'),
            ('bb_upper', 'Bollinger Upper'),
            ('bb_middle', 'Bollinger Middle'),
            ('bb_lower', 'Bollinger Lower'),
            ('bb_width', 'Bollinger Width'),
            ('adx', 'ADX'),
            ('atr', 'ATR'),
            ('stoch_k', 'Stochastic %K'),
            ('stoch_d', 'Stochastic %D'),
            ('williams_r', 'Williams %R'),
            ('momentum', 'Momentum'),
            ('roc', 'Rate of Change'),
            ('cci', 'CCI'),
            ('obv', 'On Balance Volume'),
            ('vwap', 'VWAP'),
            ('current_price', 'Current Price'),
            ('volume', 'Volume'),
            ('avg_volume', 'Average Volume')
        ]
        
        # Create detailed technical analysis for each stock
        row = 3
        for stock_idx in range(len(df)):
            # Stock header
            if 'symbol' in df.columns:
                stock_symbol = df.iloc[stock_idx]['symbol']
                ws.cell(row=row, column=1).value = f"TECHNICAL ANALYSIS - {stock_symbol}"
            else:
                ws.cell(row=row, column=1).value = f"TECHNICAL ANALYSIS - Stock {stock_idx + 1}"
            
            ws.cell(row=row, column=1).font = Font(bold=True, size=12, color='FFFFFF')
            ws.cell(row=row, column=1).fill = PatternFill(start_color=self.colors['header'], 
                                                        end_color=self.colors['header'], fill_type='solid')
            ws.merge_cells(f'A{row}:D{row}')
            row += 2
            
            # Headers
            headers = ['Indicator', 'Value', 'Signal', 'Description']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=row, column=col)
                cell.value = header
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill(start_color=self.colors['header'], 
                                      end_color=self.colors['header'], fill_type='solid')
            row += 1
            
            # Add technical indicators
            data_added = 0
            for col_key, display_name in technical_metrics:
                if col_key in df.columns:
                    value = df.iloc[stock_idx][col_key]
                    
                    # Skip empty values
                    if pd.isna(value) or value == 0:
                        continue
                    
                    ws.cell(row=row, column=1).value = display_name
                    
                    # Format value
                    if isinstance(value, (int, float)):
                        if 'Price' in display_name or 'SMA' in display_name or 'EMA' in display_name or 'Bollinger' in display_name:
                            ws.cell(row=row, column=2).value = f"₹{value:.2f}"
                        elif 'Volume' in display_name:
                            ws.cell(row=row, column=2).value = f"{value:,.0f}"
                        else:
                            ws.cell(row=row, column=2).value = f"{value:.2f}"
                    else:
                        ws.cell(row=row, column=2).value = str(value)
                    
                    # Add signal interpretation
                    signal = self._interpret_technical_signal(col_key, value)
                    ws.cell(row=row, column=3).value = signal['signal']
                    ws.cell(row=row, column=4).value = signal['description']
                    
                    # Color code signals
                    if signal['signal'] == 'BUY':
                        ws.cell(row=row, column=3).fill = PatternFill(start_color=self.colors['buy'], 
                                                                    end_color=self.colors['buy'], fill_type='solid')
                    elif signal['signal'] == 'SELL':
                        ws.cell(row=row, column=3).fill = PatternFill(start_color=self.colors['sell'], 
                                                                    end_color=self.colors['sell'], fill_type='solid')
                    elif signal['signal'] == 'HOLD':
                        ws.cell(row=row, column=3).fill = PatternFill(start_color=self.colors['hold'], 
                                                                    end_color=self.colors['hold'], fill_type='solid')
                    
                    row += 1
                    data_added += 1
            
            if data_added == 0:
                ws.cell(row=row, column=1).value = "No technical data available"
                ws.cell(row=row, column=2).value = "N/A"
                ws.cell(row=row, column=3).value = "N/A"
                ws.cell(row=row, column=4).value = "Technical analysis not available"
                row += 1
            
            row += 2
        
        self._auto_adjust_columns(ws)
    
    def _interpret_technical_signal(self, indicator, value):
        """Interpret technical indicator signals"""
        if indicator == 'rsi':
            if value > 70:
                return {'signal': 'SELL', 'description': 'Overbought condition'}
            elif value < 30:
                return {'signal': 'BUY', 'description': 'Oversold condition'}
            else:
                return {'signal': 'HOLD', 'description': 'Neutral momentum'}
        elif indicator == 'macd':
            if value > 0:
                return {'signal': 'BUY', 'description': 'Above signal line - bullish'}
            else:
                return {'signal': 'SELL', 'description': 'Below signal line - bearish'}
        elif indicator == 'adx':
            if value > 25:
                return {'signal': 'HOLD', 'description': 'Strong trend'}
            else:
                return {'signal': 'HOLD', 'description': 'Weak trend'}
        elif 'sma' in indicator or 'ema' in indicator:
            return {'signal': 'HOLD', 'description': 'Moving average level'}
        else:
            return {'signal': 'HOLD', 'description': 'Technical indicator'}
    
    def _create_fundamental_sheet(self, wb, data):
        """Create detailed fundamental analysis sheet with comprehensive data"""
        ws = wb.create_sheet("Fundamentals")
        
        # Add title
        ws['A1'] = f"Fundamental Analysis - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        
        # Convert to DataFrame
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Define comprehensive fundamental columns with proper display names
        fundamental_metrics = [
            ('symbol', 'Symbol'),
            ('company_name', 'Company Name'),
            ('sector', 'Sector'),
            ('industry', 'Industry'),
            ('current_price', 'Current Price (₹)'),
            ('market_cap', 'Market Cap (₹)'),
            ('pe_ratio', 'PE Ratio'),
            ('pb_ratio', 'PB Ratio'),
            ('ps_ratio', 'PS Ratio'),
            ('roe', 'ROE (%)'),
            ('roa', 'ROA (%)'),
            ('roic', 'ROIC (%)'),
            ('debt_to_equity', 'Debt/Equity Ratio'),
            ('current_ratio', 'Current Ratio'),
            ('quick_ratio', 'Quick Ratio'),
            ('revenue_growth', 'Revenue Growth (%)'),
            ('earnings_growth', 'Earnings Growth (%)'),
            ('book_value', 'Book Value per Share'),
            ('eps', 'Earnings per Share'),
            ('dividend_yield', 'Dividend Yield (%)'),
            ('payout_ratio', 'Payout Ratio (%)'),
            ('beta', 'Beta'),
            ('52w_high', '52 Week High'),
            ('52w_low', '52 Week Low'),
            ('price_change_1d', '1 Day Change (%)'),
            ('price_change_1w', '1 Week Change (%)'),
            ('price_change_1m', '1 Month Change (%)'),
            ('price_change_3m', '3 Month Change (%)'),
            ('price_change_6m', '6 Month Change (%)'),
            ('price_change_1y', '1 Year Change (%)'),
            ('volume', 'Current Volume'),
            ('avg_volume', 'Average Volume'),
            ('shares_outstanding', 'Shares Outstanding'),
            ('float_shares', 'Float Shares'),
            ('net_margin', 'Net Profit Margin (%)'),
            ('operating_margin', 'Operating Margin (%)'),
            ('gross_margin', 'Gross Margin (%)'),
            ('asset_turnover', 'Asset Turnover'),
            ('inventory_turnover', 'Inventory Turnover'),
            ('revenue_per_share', 'Revenue per Share'),
            ('cashflow_per_share', 'Operating Cash Flow per Share'),
            ('FundamentalScore', 'Fundamental Score'),
            ('fundamental_score', 'Fundamental Score (Alt)')
        ]
        
        # Create a detailed fundamental analysis for each stock
        row = 3
        for stock_idx in range(len(df)):
            # Stock header
            if 'symbol' in df.columns:
                stock_symbol = df.iloc[stock_idx]['symbol']
                ws.cell(row=row, column=1).value = f"FUNDAMENTAL ANALYSIS - {stock_symbol}"
            else:
                ws.cell(row=row, column=1).value = f"FUNDAMENTAL ANALYSIS - Stock {stock_idx + 1}"
            
            ws.cell(row=row, column=1).font = Font(bold=True, size=12, color='FFFFFF')
            ws.cell(row=row, column=1).fill = PatternFill(start_color=self.colors['header'], 
                                                        end_color=self.colors['header'], fill_type='solid')
            ws.merge_cells(f'A{row}:C{row}')
            row += 2
            
            # Headers for the detailed data
            headers = ['Metric', 'Value', 'Category']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=row, column=col)
                cell.value = header
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill(start_color=self.colors['header'], 
                                      end_color=self.colors['header'], fill_type='solid')
            row += 1
            
            # Add all available fundamental data
            data_added = 0
            for col_key, display_name in fundamental_metrics:
                if col_key in df.columns:
                    value = df.iloc[stock_idx][col_key]
                    
                    # Skip completely empty or zero values for score fields
                    if pd.isna(value) or (col_key in ['FundamentalScore', 'fundamental_score'] and value == 0):
                        continue
                    
                    # Add the metric
                    ws.cell(row=row, column=1).value = display_name
                    
                    # Format the value
                    if isinstance(value, (int, float)):
                        if 'Price' in display_name or 'Market Cap' in display_name:
                            if 'Market Cap' in display_name:
                                ws.cell(row=row, column=2).value = f"₹{value:,.0f}"
                            else:
                                ws.cell(row=row, column=2).value = f"₹{value:,.2f}"
                        elif '%' in display_name:
                            ws.cell(row=row, column=2).value = f"{value:.2f}%"
                        elif 'Volume' in display_name or 'Shares' in display_name:
                            ws.cell(row=row, column=2).value = f"{value:,.0f}"
                        else:
                            ws.cell(row=row, column=2).value = f"{value:.2f}"
                    else:
                        ws.cell(row=row, column=2).value = str(value)
                    
                    # Add category
                    if any(x in display_name for x in ['Ratio', 'PE', 'PB', 'PS']):
                        category = "Valuation"
                    elif any(x in display_name for x in ['Growth', 'Change']):
                        category = "Growth & Performance"
                    elif any(x in display_name for x in ['Margin', 'ROE', 'ROA', 'ROIC']):
                        category = "Profitability"
                    elif any(x in display_name for x in ['Debt', 'Current', 'Quick']):
                        category = "Financial Health"
                    elif any(x in display_name for x in ['Volume', 'Shares', 'Float']):
                        category = "Market Data"
                    elif 'Score' in display_name:
                        category = "Overall Rating"
                    else:
                        category = "Company Info"
                    
                    ws.cell(row=row, column=3).value = category
                    row += 1
                    data_added += 1
            
            # Add summary if no data was found
            if data_added == 0:
                ws.cell(row=row, column=1).value = "No fundamental data available"
                ws.cell(row=row, column=2).value = "N/A"
                ws.cell(row=row, column=3).value = "Data Issue"
                row += 1
            
            row += 2  # Space between stocks
        
        # Auto-adjust column widths
        self._auto_adjust_columns(ws)
    
    def _create_sentiment_sheet(self, wb, data):
        """Create sentiment analysis sheet"""
        ws = wb.create_sheet("Sentiment")
        
        # Add title
        ws['A1'] = f"News Sentiment Analysis - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        
        # Convert to DataFrame
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Select sentiment columns
        sent_cols = ['symbol', 'SentimentScore', 'headline', 'source', 'sentiment_label']
        available_cols = [col for col in sent_cols if col in df.columns]
        
        if available_cols:
            sent_df = df[available_cols]
            # Sort by sentiment score if available
            if 'SentimentScore' in sent_df.columns:
                sent_df = sent_df.sort_values('SentimentScore', ascending=False)
            elif 'sentiment_score' in sent_df.columns:
                sent_df = sent_df.sort_values('sentiment_score', ascending=False)
            self._add_data_to_sheet(ws, sent_df, start_row=3)
        
        self._auto_adjust_columns(ws)
    
    def _create_combined_score_sheet(self, wb, data):
        """Create combined scoring methodology sheet"""
        ws = wb.create_sheet("Combined Score")
        
        # Add title
        ws['A1'] = f"Combined Scoring Methodology - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        
        # Add explanation
        ws['A3'] = "Scoring Methodology:"
        ws['A3'].font = Font(bold=True)
        
        methodology = [
            "• Overall Score = (Fundamental Score + Technical Score + Sentiment Score) / 3",
            "• Score > 70: BUY recommendation",
            "• Score 40-70: HOLD recommendation", 
            "• Score < 40: SELL recommendation",
            "",
            "Top Performers:"
        ]
        
        for i, text in enumerate(methodology, 4):
            ws[f'A{i}'] = text
            if "BUY" in text:
                ws[f'A{i}'].font = Font(color='008000')  # Green
            elif "SELL" in text:
                ws[f'A{i}'].font = Font(color='FF0000')  # Red
            elif "HOLD" in text:
                ws[f'A{i}'].font = Font(color='FFA500')  # Orange
        
        # Add top performers
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Find available score column
        score_column = None
        for col in ['OverallScore', 'overall_score', 'fundamental_score', 'FundamentalScore']:
            if col in df.columns:
                score_column = col
                break
        
        if score_column and 'symbol' in df.columns:
            top_10 = df.nlargest(10, score_column)[['symbol', score_column]]
            self._add_data_to_sheet(ws, top_10, start_row=len(methodology) + 5)
        else:
            # Add message if no score data available
            ws[f'A{len(methodology) + 5}'] = "Score data not available for ranking"
        
        self._auto_adjust_columns(ws)
    
    def _add_data_to_sheet(self, ws, df, start_row=1):
        """Add DataFrame data to worksheet"""
        # Add headers
        for col_num, column_title in enumerate(df.columns, 1):
            cell = ws.cell(row=start_row, column=col_num)
            cell.value = column_title
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color=self.colors['header'], 
                                  end_color=self.colors['header'], fill_type='solid')
            cell.alignment = Alignment(horizontal='center')
        
        # Add data
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), start_row + 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.value = value
        
        # Add borders
        self._add_borders(ws, start_row, start_row + len(df), len(df.columns))
    
    def _get_recommendation(self, score):
        """Get recommendation based on overall score"""
        if score > 70:
            return 'BUY'
        elif score >= 40:
            return 'HOLD'
        else:
            return 'SELL'
    
    def _auto_adjust_columns(self, ws):
        """Auto-adjust column widths"""
        for column_cells in ws.columns:
            max_length = 0
            column_letter = None
            
            for cell in column_cells:
                # Skip merged cells
                if hasattr(cell, 'coordinate') and cell.coordinate in ws.merged_cells:
                    continue
                
                # Get column letter
                if column_letter is None:
                    column_letter = cell.column_letter
                
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            if column_letter:
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
    
    def _add_borders(self, ws, start_row, end_row, num_cols):
        """Add borders to table"""
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for row in range(start_row, end_row + 1):
            for col in range(1, num_cols + 1):
                ws.cell(row=row, column=col).border = thin_border
    
    def _create_detailed_analysis_sheet(self, wb, data):
        """Create detailed analysis sheet with all available data"""
        ws = wb.create_sheet("Detailed Analysis")
        
        # Add title
        ws['A1'] = f"Detailed Stock Analysis - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        
        # Convert to DataFrame
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Select all available columns (exclude very long text fields)
        exclude_cols = ['business_summary', 'website']
        available_cols = [col for col in df.columns if col not in exclude_cols]
        
        if available_cols:
            detailed_df = df[available_cols]
            self._add_data_to_sheet(ws, detailed_df, start_row=3)
        
        self._auto_adjust_columns(ws)
    
    def _create_company_overview_sheet(self, wb, data):
        """Create company overview sheet"""
        ws = wb.create_sheet("Company Overview")
        
        # Add title
        ws['A1'] = f"Company Overview - {datetime.now().strftime('%Y-%m-%d')}"
        ws['A1'].font = Font(bold=True, size=16)
        
        # Convert to DataFrame
        if not isinstance(data, pd.DataFrame):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        
        # Select overview columns
        overview_cols = ['symbol', 'company_name', 'sector', 'industry', 'current_price', 
                        'market_cap', 'employees', 'country', '52_week_high', '52_week_low']
        available_cols = [col for col in overview_cols if col in df.columns]
        
        if available_cols:
            overview_df = df[available_cols]
            self._add_data_to_sheet(ws, overview_df, start_row=3)
        
        self._auto_adjust_columns(ws)

# Alias for backwards compatibility
ExcelExporter = ExcelReportGenerator
