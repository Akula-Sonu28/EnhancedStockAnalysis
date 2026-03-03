"""
Historical Data Migrator - Migrates recommendations from CSV and Excel reports to intelligence database
"""

import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
import glob
from typing import Dict, List, Optional
from .intelligence_db import IntelligenceDB

class HistoricalMigrator:
    """
    Migrates historical recommendation data to intelligence database
    Sources: recommendation_history.csv + Excel reports
    """
    
    def __init__(self, db: IntelligenceDB):
        """
        Initialize migrator
        
        Args:
            db: IntelligenceDB instance
        """
        self.db = db
        self.stats = {
            'csv_records': 0,
            'excel_reports': 0,
            'total_migrated': 0,
            'errors': 0
        }
    
    def migrate_csv_history(self, csv_path: str = "data/recommendation_history.csv") -> int:
        """
        Migrate data from recommendation_history.csv
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Number of records migrated
        """
        if not Path(csv_path).exists():
            logging.warning(f"CSV file not found: {csv_path}")
            return 0
        
        try:
            df = pd.read_csv(csv_path)
            logging.info(f"Loading {len(df)} records from {csv_path}")
            
            migrated = 0
            for idx, row in df.iterrows():
                try:
                    # Convert date to string format for SQLite
                    date_value = pd.to_datetime(row['date']).strftime('%Y-%m-%d %H:%M:%S')
                    
                    rec_data = {
                        'date': date_value,
                        'symbol': row['symbol'],
                        'action': row['action'],
                        'score': float(row['score']) if pd.notna(row['score']) else None,
                        'price': float(row['price']) if pd.notna(row['price']) else None,
                        'pe_ratio': float(row['pe_ratio']) if pd.notna(row['pe_ratio']) else None,
                        'roe': float(row['roe']) if pd.notna(row['roe']) else None,
                        'debt_to_equity': float(row['debt_to_equity']) if pd.notna(row['debt_to_equity']) else None,
                        'reason': row['reason'] if pd.notna(row['reason']) else '',
                        'rank': int(row['rank']) if pd.notna(row['rank']) else None,
                        'sector': row['sector'] if pd.notna(row['sector']) else '',
                        'report_file': 'recommendation_history.csv',
                        'analysis_version': 'legacy'
                    }
                    
                    self.db.record_recommendation(rec_data)
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        logging.info(f"Migrated {migrated}/{len(df)} CSV records...")
                        
                except Exception as e:
                    logging.error(f"Error migrating CSV row {idx}: {e}")
                    self.stats['errors'] += 1
            
            self.stats['csv_records'] = migrated
            logging.info(f"✅ CSV migration complete: {migrated} records")
            return migrated
            
        except Exception as e:
            logging.error(f"Error reading CSV file: {e}")
            return 0
    
    def migrate_excel_reports(self, reports_dir: str = "reports/") -> int:
        """
        Migrate data from Excel reports
        
        Args:
            reports_dir: Directory containing Excel reports
            
        Returns:
            Number of records migrated
        """
        excel_files = glob.glob(str(Path(reports_dir) / "Enhanced_Stock_Report_*.xlsx"))
        
        if not excel_files:
            logging.warning(f"No Excel reports found in {reports_dir}")
            return 0
        
        logging.info(f"Found {len(excel_files)} Excel reports to migrate")
        
        total_migrated = 0
        
        for excel_file in sorted(excel_files):
            try:
                migrated = self._migrate_single_report(excel_file)
                total_migrated += migrated
                self.stats['excel_reports'] += 1
                
                if self.stats['excel_reports'] % 10 == 0:
                    logging.info(f"Processed {self.stats['excel_reports']}/{len(excel_files)} reports...")
                    
            except Exception as e:
                logging.error(f"Error migrating report {excel_file}: {e}")
                self.stats['errors'] += 1
        
        logging.info(f"✅ Excel migration complete: {total_migrated} records from {self.stats['excel_reports']} reports")
        return total_migrated
    
    def _migrate_single_report(self, excel_path: str) -> int:
        """Migrate data from a single Excel report"""
        try:
            # Extract date from filename (Enhanced_Stock_Report_YYYYMMDD_HHMMSS.xlsx)
            filename = Path(excel_path).stem
            date_str = filename.split('_')[-2] + filename.split('_')[-1]
            report_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
            
            # Try to read the Complete Data sheet first (most comprehensive)
            try:
                df = pd.read_excel(excel_path, sheet_name='Complete Data')
            except:
                # Fallback to first sheet
                df = pd.read_excel(excel_path, sheet_name=0)
            
            migrated = 0
            
            for idx, row in df.iterrows():
                try:
                    # Extract data with safe fallbacks
                    rec_data = {
                        'date': report_date,
                        'symbol': row.get('Symbol', row.get('symbol', '')),
                        'action': row.get('Action', row.get('action', row.get('Recommendation', 'HOLD'))),
                        'score': self._safe_float(row.get('Overall Score', row.get('score'))),
                        'price': self._safe_float(row.get('Current Price', row.get('price', row.get('Price')))),
                        'technical_score': self._safe_float(row.get('Technical Score')),
                        'fundamental_score': self._safe_float(row.get('Fundamental Score')),
                        'pe_ratio': self._safe_float(row.get('P/E Ratio', row.get('pe_ratio', row.get('PE')))),
                        'pb_ratio': self._safe_float(row.get('P/B Ratio', row.get('pb_ratio', row.get('PB')))),
                        'roe': self._safe_float(row.get('ROE', row.get('roe'))),
                        'debt_to_equity': self._safe_float(row.get('Debt/Equity', row.get('debt_to_equity'))),
                        'revenue_growth': self._safe_float(row.get('Revenue Growth', row.get('revenue_growth'))),
                        'sector': row.get('Sector', row.get('sector', '')),
                        'industry': row.get('Industry', row.get('industry', '')),
                        'market_regime': row.get('Market Regime', ''),
                        'reason': row.get('Reason', row.get('reason', '')),
                        'rank': self._safe_int(row.get('Rank', row.get('rank'))),
                        'report_file': Path(excel_path).name,
                        'analysis_version': 'phase2'
                    }
                    
                    # Only insert if we have symbol
                    if rec_data['symbol']:
                        self.db.record_recommendation(rec_data)
                        migrated += 1
                        
                except Exception as e:
                    logging.debug(f"Error migrating row {idx} from {excel_path}: {e}")
            
            return migrated
            
        except Exception as e:
            logging.error(f"Error reading Excel file {excel_path}: {e}")
            return 0
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert to float"""
        if pd.isna(value):
            return None
        try:
            return float(value)
        except:
            return None
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert to int"""
        if pd.isna(value):
            return None
        try:
            return int(value)
        except:
            return None
    
    def migrate_all(self, 
                   csv_path: str = "data/recommendation_history.csv",
                   reports_dir: str = "reports/") -> Dict:
        """
        Migrate all historical data
        
        Returns:
            Dictionary with migration statistics
        """
        logging.info("🚀 Starting historical data migration...")
        
        # Migrate CSV first
        csv_count = self.migrate_csv_history(csv_path)
        
        # Migrate Excel reports
        excel_count = self.migrate_excel_reports(reports_dir)
        
        self.stats['total_migrated'] = csv_count + excel_count
        
        logging.info(f"""
        ✅ Migration Complete!
        - CSV records: {csv_count}
        - Excel reports: {self.stats['excel_reports']}
        - Total records: {self.stats['total_migrated']}
        - Errors: {self.stats['errors']}
        """)
        
        return self.stats
