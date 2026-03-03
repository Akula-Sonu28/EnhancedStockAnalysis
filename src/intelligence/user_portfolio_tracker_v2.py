"""
User Portfolio Tracker - Complete 41-Column Version
Tracks YOUR actual portfolio decisions from Portfolio Allocation sheet
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
import openpyxl
from src.intelligence.intelligence_db import IntelligenceDB

logger = logging.getLogger(__name__)

class UserPortfolioTracker:
    """Track user's actual portfolio vs system recommendations"""
    
    def __init__(self, db_path: str = "data/intelligence.db"):
        self.db = IntelligenceDB(db_path)
    
    def import_portfolio_from_report(self, excel_path: str) -> Dict:
        """
        Import portfolio data from Excel report
        Extracts ALL 41 columns from Portfolio Allocation sheet
        """
        try:
            wb = openpyxl.load_workbook(excel_path, read_only=True)
            
            if 'Portfolio Allocation' not in wb.sheetnames:
                logger.error(f"Worksheet named 'Portfolio Allocation' not found in {excel_path}")
                return {}
            
            # Read Portfolio Allocation sheet
            df = pd.read_excel(excel_path, sheet_name='Portfolio Allocation')
            
            if df.empty:
                logger.warning(f"Empty Portfolio Allocation sheet in {excel_path}")
                return {}
            
            # Extract report date from filename
            filename = Path(excel_path).stem
            try:
                date_str = filename.split("_")[3] + "_" + filename.split("_")[4]
                report_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            except:
                report_date = datetime.now()
            
            # Process each position
            total_positions = 0
            owned_positions = 0
            total_value = 0
            followed_count = 0
            
            for _, row in df.iterrows():
                position = self._extract_position_data(row)
                position['date'] = report_date
                
                # Infer user action and follow status
                position['user_action'] = self._infer_user_action(row)
                position['followed_recommendation'] = self._did_user_follow(row)
                
                # Insert into database
                self.db.insert_user_portfolio_position(position)
                
                total_positions += 1
                if position['i_own_it']:
                    owned_positions += 1
                    total_value += position['my_value']
                if position['followed_recommendation']:
                    followed_count += 1
            
            stats = {
                'report_date': report_date.strftime('%Y-%m-%d %H:%M:%S'),
                'total_positions': total_positions,
                'owned_positions': owned_positions,
                'total_value': total_value,
                'followed_count': followed_count,
                'follow_rate': (followed_count / total_positions * 100) if total_positions > 0 else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error importing portfolio from {excel_path}: {e}")
            raise
    
    def _extract_position_data(self, row: pd.Series) -> Dict:
        """
        Extract ALL 41 columns from Portfolio Allocation row
        Maps report columns to database schema
        """
        return {
            # Identity
            'symbol': str(row.get('symbol', '')).strip(),
            'company_name': str(row.get('company_name', '')).strip(),
            
            # System recommendation columns
            'action': str(row.get('ACTION', '')).strip(),
            'when_to_act': str(row.get('WHEN_TO_ACT', '')).strip(),
            'invest_amount': float(row.get('INVEST_₹', 0)) if pd.notna(row.get('INVEST_₹')) else 0,
            'buy_shares': int(row.get('BUY_SHARES', 0)) if pd.notna(row.get('BUY_SHARES')) else 0,
            
            # User's actual position (MY_ columns)
            'my_shares': int(row.get('MY_SHARES', 0)) if pd.notna(row.get('MY_SHARES')) else 0,
            'my_value': float(row.get('MY_VALUE_₹', 0)) if pd.notna(row.get('MY_VALUE_₹')) else 0,
            'my_profit_pct': float(row.get('MY_PROFIT_%', 0)) if pd.notna(row.get('MY_PROFIT_%')) else 0,
            'book_pct_if_sell': float(row.get('BOOK_%_IF_SELL', 0)) if pd.notna(row.get('BOOK_%_IF_SELL')) else 0,
            'book_amount': float(row.get('BOOK_₹_AMOUNT', 0)) if pd.notna(row.get('BOOK_₹_AMOUNT')) else 0,
            
            # Scoring columns
            'score': float(row.get('SCORE', 0)) if pd.notna(row.get('SCORE')) else 0,
            'risk_score': float(row.get('RISK_SCORE', 0)) if pd.notna(row.get('RISK_SCORE')) else None,
            'v3_score': float(row.get('V3_SCORE', 0)) if pd.notna(row.get('V3_SCORE')) else None,
            'fund_score': float(row.get('FUND_SCORE', 0)) if pd.notna(row.get('FUND_SCORE')) else None,
            'mom_score': float(row.get('MOM_SCORE', 0)) if pd.notna(row.get('MOM_SCORE')) else None,
            'value_score': float(row.get('VALUE_SCORE', 0)) if pd.notna(row.get('VALUE_SCORE')) else None,
            
            # Fundamentals
            'pe_ratio': float(row.get('PE', 0)) if pd.notna(row.get('PE')) else None,
            'roe_pct': float(row.get('ROE_%', 0)) if pd.notna(row.get('ROE_%')) else None,
            'debt_to_equity': float(row.get('DEBT/EQUITY', 0)) if pd.notna(row.get('DEBT/EQUITY')) else None,
            'risk': str(row.get('RISK', 'MEDIUM')).strip(),
            
            # Price data
            'price': float(row.get('PRICE', 0)) if pd.notna(row.get('PRICE')) else 0,
            'high_52w': float(row.get('52W_HIGH', 0)) if pd.notna(row.get('52W_HIGH')) else None,
            'low_52w': float(row.get('52W_LOW', 0)) if pd.notna(row.get('52W_LOW')) else None,
            'change_20d_pct': float(row.get('20D_CHANGE_%', 0)) if pd.notna(row.get('20D_CHANGE_%')) else None,
            
            # Technical signals
            'support': float(row.get('SUPPORT', 0)) if pd.notna(row.get('SUPPORT')) else None,
            'resistance': float(row.get('RESISTANCE', 0)) if pd.notna(row.get('RESISTANCE')) else None,
            'rsi': float(row.get('RSI', 0)) if pd.notna(row.get('RSI')) else None,
            'volatility_pct': float(row.get('VOLATILITY_%', 0)) if pd.notna(row.get('VOLATILITY_%')) else None,
            
            # Breakout & Exit signals
            'pre_breakout': str(row.get('PRE_BREAKOUT?', '')).strip(),
            'breakout_pct': float(row.get('BREAKOUT_%', 0)) if pd.notna(row.get('BREAKOUT_%')) else None,
            'setup_signals': str(row.get('SETUP_SIGNALS', '')).strip()[:500],  # Limit length
            'exhaustion': str(row.get('EXHAUSTION?', '')).strip(),
            'exit_score': float(row.get('EXIT_SCORE', 0)) if pd.notna(row.get('EXIT_SCORE')) else None,
            'exit_signals': str(row.get('EXIT_SIGNALS', '')).strip()[:500],  # Limit length
            
            # Context
            'sector': str(row.get('sector', 'Unknown')).strip(),
            'type': str(row.get('TYPE', '')).strip(),
            'rank': int(row.get('RANK', 0)) if pd.notna(row.get('RANK')) else None,
            'portfolio_pct': float(row.get('PORTFOLIO_%', 0)) if pd.notna(row.get('PORTFOLIO_%')) else 0,
            'why': str(row.get('WHY', '')).strip()[:1000],  # Limit length
            'i_own_it': 1 if row.get('I_OWN_IT?') in ['Yes', True, 1, 'TRUE', 'true'] else 0,
        }
    
    def _infer_user_action(self, row: pd.Series) -> str:
        """
        Infer what the user actually did - analyzes ALL action types
        """
        action = str(row.get('ACTION', '')).upper()
        owns_it = row.get('I_OWN_IT?') in ['Yes', True, 1, 'TRUE', 'true']
        my_shares = row.get('MY_SHARES', 0)
        exhaustion = str(row.get('EXHAUSTION?', '')).strip()
        pre_breakout = str(row.get('PRE_BREAKOUT?', '')).strip()
        exit_signals = str(row.get('EXIT_SIGNALS', '')).strip()
        
        # User owns it
        if owns_it and my_shares > 0:
            if 'SELL' in action:
                return "IGNORED SELL (holding loser/hope)"
            elif 'BOOK' in action:
                return "IGNORED BOOK (holding winner/greedy)"
            elif exhaustion:
                return f"HOLDING EXHAUSTED ({exhaustion[:30]})"
            elif exit_signals:
                return "IGNORED EXIT SIGNALS"
            elif pre_breakout == 'YES':
                return "RIDING BREAKOUT (early entry)"
            elif 'INCREASE' in action:
                return "HOLDING (follow INCREASE rec)"
            elif action == 'HOLD':
                return "HOLD (following system)"
            else:
                return f"HOLDING ({action[:20]})"
        
        # User doesn't own it
        else:
            if any(x in action for x in ['BUY', 'ENTER', 'POSITION', 'INCREASE']):
                return "IGNORED BUY (low conviction?)"
            elif pre_breakout == 'YES':
                return "MISSED BREAKOUT (risk aversion?)"
            elif 'SELL' in action:
                return "ALREADY SOLD (followed earlier)"
            else:
                return "NO POSITION (neutral)"
        
        return "UNKNOWN"
    
    def _did_user_follow(self, row: pd.Series) -> int:
        """Determine if user followed recommendation (1) or not (0)"""
        action = str(row.get('ACTION', '')).upper()
        owns_it = row.get('I_OWN_IT?') in ['Yes', True, 1, 'TRUE', 'true']
        my_shares = row.get('MY_SHARES', 0)
        exhaustion = str(row.get('EXHAUSTION?', '')).strip()
        exit_signals = str(row.get('EXIT_SIGNALS', '')).strip()
        pre_breakout = str(row.get('PRE_BREAKOUT?', '')).strip()
        
        # SELL - followed if doesn't own
        if 'SELL' in action:
            return 1 if (not owns_it or my_shares == 0) else 0
        
        # BOOK PROFIT - not following if still holding full position
        elif 'BOOK' in action:
            return 0  # Assume not following
        
        # EXHAUSTION - should exit
        elif exhaustion and owns_it:
            return 0
        
        # EXIT SIGNALS - should sell
        elif exit_signals and owns_it:
            return 0
        
        # PRE-BREAKOUT - followed if owns
        elif pre_breakout == 'YES':
            return 1 if (owns_it and my_shares > 0) else 0
        
        # BUY/INCREASE - followed if owns
        elif any(x in action for x in ['BUY', 'ENTER', 'POSITION', 'INCREASE']):
            return 1 if (owns_it and my_shares > 0) else 0
        
        # HOLD - always following
        elif action == 'HOLD':
            return 1
        
        return 1 if owns_it else 0
