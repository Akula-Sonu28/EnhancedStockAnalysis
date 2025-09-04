#!/usr/bin/env python3
"""
Data Quality Assessment for Stock Analysis
Comprehensive data quality checks and reporting
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import logging

@dataclass
class QualityMetrics:
    """Data quality metrics for a dataset"""
    total_records: int = 0
    complete_records: int = 0
    missing_data_percentage: float = 0.0
    outliers_count: int = 0
    data_freshness_hours: float = 0.0
    accuracy_score: float = 0.0
    completeness_score: float = 0.0
    consistency_score: float = 0.0
    overall_quality_score: float = 0.0

class DataQualityAssessor:
    """Assess and report on data quality for stock analysis"""
    
    def __init__(self):
        self.required_fields = {
            'fundamental': [
                'symbol', 'current_price', 'market_cap', 'pe_ratio', 'pb_ratio',
                'debt_to_equity', 'roe', 'revenue_growth', 'profit_growth'
            ],
            'technical': [
                'symbol', 'current_price', 'rsi', 'macd', 'moving_avg_20', 
                'moving_avg_50', 'volume', 'volatility'
            ],
            'comprehensive': [
                'symbol', 'current_price', 'fundamental_score', 'technical_score',
                'undervaluation_score', 'overall_score', 'final_recommendation'
            ]
        }
    
    def assess_data_quality(self, df: pd.DataFrame, analysis_type: str = 'comprehensive') -> QualityMetrics:
        """Assess overall data quality of the dataset"""
        metrics = QualityMetrics()
        
        if df.empty:
            return metrics
        
        metrics.total_records = len(df)
        
        # Get required fields for analysis type
        required_fields = self.required_fields.get(analysis_type, 
                                                 self.required_fields['comprehensive'])
        
        # Check completeness
        available_fields = [field for field in required_fields if field in df.columns]
        missing_fields = [field for field in required_fields if field not in df.columns]
        
        if missing_fields:
            logging.warning(f"Missing required fields: {missing_fields}")
        
        # Calculate completeness for available fields
        if available_fields:
            complete_mask = df[available_fields].notna().all(axis=1)
            metrics.complete_records = complete_mask.sum()
            metrics.completeness_score = (metrics.complete_records / metrics.total_records) * 100
        
        # Calculate missing data percentage
        total_cells = len(df) * len(available_fields)
        missing_cells = df[available_fields].isna().sum().sum()
        metrics.missing_data_percentage = (missing_cells / total_cells) * 100 if total_cells > 0 else 100
        
        # Detect outliers in numeric fields
        numeric_fields = df[available_fields].select_dtypes(include=[np.number]).columns
        outliers_count = 0
        
        for field in numeric_fields:
            if field in df.columns:
                outliers_count += self.detect_outliers(df[field]).sum()
        
        metrics.outliers_count = outliers_count
        
        # Assess data consistency
        metrics.consistency_score = self.assess_consistency(df, available_fields)
        
        # Calculate accuracy score (based on data validation)
        metrics.accuracy_score = self.assess_accuracy(df, available_fields)
        
        # Calculate overall quality score
        metrics.overall_quality_score = (
            metrics.completeness_score * 0.4 +
            metrics.consistency_score * 0.3 +
            metrics.accuracy_score * 0.3
        )
        
        return metrics
    
    def detect_outliers(self, series: pd.Series, method: str = 'iqr') -> pd.Series:
        """Detect outliers in a numeric series"""
        if series.empty or not pd.api.types.is_numeric_dtype(series):
            return pd.Series(False, index=series.index)
        
        if method == 'iqr':
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            return (series < lower_bound) | (series > upper_bound)
        
        elif method == 'zscore':
            z_scores = np.abs((series - series.mean()) / series.std())
            return z_scores > 3
        
        return pd.Series(False, index=series.index)
    
    def assess_consistency(self, df: pd.DataFrame, fields: List[str]) -> float:
        """Assess data consistency across related fields"""
        consistency_checks = []
        
        # Check if PE ratio is consistent with market cap and earnings
        if all(field in df.columns for field in ['pe_ratio', 'market_cap', 'current_price']):
            # Basic sanity checks
            valid_pe = (df['pe_ratio'] > 0) & (df['pe_ratio'] < 1000)
            valid_market_cap = df['market_cap'] > 0
            valid_price = df['current_price'] > 0
            
            consistency_score = (valid_pe & valid_market_cap & valid_price).mean() * 100
            consistency_checks.append(consistency_score)
        
        # Check if scores are within valid ranges (0-100)
        score_fields = [f for f in fields if 'score' in f.lower()]
        for field in score_fields:
            if field in df.columns:
                valid_scores = (df[field] >= 0) & (df[field] <= 100)
                consistency_checks.append(valid_scores.mean() * 100)
        
        # Check if recommendations align with scores
        if all(field in df.columns for field in ['overall_score', 'final_recommendation']):
            buy_mask = df['final_recommendation'].str.contains('BUY', na=False)
            high_score_mask = df['overall_score'] >= 60
            
            # Should have high correlation between high scores and buy recommendations
            alignment = (buy_mask == high_score_mask).mean() * 100
            consistency_checks.append(alignment)
        
        return np.mean(consistency_checks) if consistency_checks else 0.0
    
    def assess_accuracy(self, df: pd.DataFrame, fields: List[str]) -> float:
        """Assess data accuracy based on validation rules"""
        accuracy_checks = []
        
        # Symbol format validation
        if 'symbol' in df.columns:
            valid_symbols = df['symbol'].str.match(r'^[A-Z0-9&-]{1,20}$', na=False)
            accuracy_checks.append(valid_symbols.mean() * 100)
        
        # Price positivity
        price_fields = [f for f in fields if 'price' in f.lower()]
        for field in price_fields:
            if field in df.columns:
                positive_prices = (df[field] > 0) & (df[field] < 100000)  # Reasonable upper bound
                accuracy_checks.append(positive_prices.mean() * 100)
        
        # Ratio reasonableness
        if 'pe_ratio' in df.columns:
            reasonable_pe = (df['pe_ratio'] > 0) & (df['pe_ratio'] < 200)
            accuracy_checks.append(reasonable_pe.mean() * 100)
        
        if 'pb_ratio' in df.columns:
            reasonable_pb = (df['pb_ratio'] > 0) & (df['pb_ratio'] < 20)
            accuracy_checks.append(reasonable_pb.mean() * 100)
        
        return np.mean(accuracy_checks) if accuracy_checks else 0.0
    
    def generate_quality_report(self, df: pd.DataFrame, analysis_type: str = 'comprehensive') -> str:
        """Generate a comprehensive data quality report"""
        metrics = self.assess_data_quality(df, analysis_type)
        
        report = f"""
📊 DATA QUALITY ASSESSMENT REPORT
{'=' * 50}

🔢 DATASET OVERVIEW:
   Total Records: {metrics.total_records:,}
   Complete Records: {metrics.complete_records:,}
   Missing Data: {metrics.missing_data_percentage:.1f}%
   Outliers Detected: {metrics.outliers_count:,}

📈 QUALITY SCORES:
   Completeness: {metrics.completeness_score:.1f}%
   Consistency: {metrics.consistency_score:.1f}%
   Accuracy: {metrics.accuracy_score:.1f}%
   
🎯 OVERALL QUALITY: {metrics.overall_quality_score:.1f}%

📋 QUALITY ASSESSMENT:
"""
        
        if metrics.overall_quality_score >= 85:
            report += "   ✅ EXCELLENT - Data is high quality and reliable\n"
        elif metrics.overall_quality_score >= 70:
            report += "   ✅ GOOD - Data quality is acceptable for analysis\n"
        elif metrics.overall_quality_score >= 50:
            report += "   ⚠️  FAIR - Some data quality issues detected\n"
        else:
            report += "   ❌ POOR - Significant data quality issues found\n"
        
        # Add recommendations
        report += "\n🔧 RECOMMENDATIONS:\n"
        
        if metrics.completeness_score < 80:
            report += "   • Improve data collection to reduce missing values\n"
        
        if metrics.consistency_score < 70:
            report += "   • Review data validation rules for consistency\n"
        
        if metrics.accuracy_score < 75:
            report += "   • Implement stricter data validation and cleaning\n"
        
        if metrics.outliers_count > (metrics.total_records * 0.1):
            report += "   • Investigate and handle outliers in the dataset\n"
        
        return report
    
    def identify_data_gaps(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """Identify specific data gaps and missing information"""
        gaps = {
            'missing_symbols': [],
            'incomplete_fundamental': [],
            'incomplete_technical': [],
            'missing_scores': []
        }
        
        # Check for missing symbols
        if 'symbol' in df.columns:
            missing_symbol_mask = df['symbol'].isna() | (df['symbol'] == '')
            gaps['missing_symbols'] = df[missing_symbol_mask].index.tolist()
        
        # Check for incomplete fundamental data
        fundamental_fields = ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity']
        available_fundamental = [f for f in fundamental_fields if f in df.columns]
        
        if available_fundamental:
            incomplete_fundamental = df[available_fundamental].isna().any(axis=1)
            gaps['incomplete_fundamental'] = df[incomplete_fundamental]['symbol'].tolist() if 'symbol' in df.columns else []
        
        # Check for incomplete technical data
        technical_fields = ['rsi', 'macd', 'moving_avg_20', 'volume']
        available_technical = [f for f in technical_fields if f in df.columns]
        
        if available_technical:
            incomplete_technical = df[available_technical].isna().any(axis=1)
            gaps['incomplete_technical'] = df[incomplete_technical]['symbol'].tolist() if 'symbol' in df.columns else []
        
        # Check for missing scores
        score_fields = ['fundamental_score', 'technical_score', 'overall_score']
        available_scores = [f for f in score_fields if f in df.columns]
        
        if available_scores:
            missing_scores = df[available_scores].isna().any(axis=1)
            gaps['missing_scores'] = df[missing_scores]['symbol'].tolist() if 'symbol' in df.columns else []
        
        return gaps

# Global instance
quality_assessor = DataQualityAssessor()
