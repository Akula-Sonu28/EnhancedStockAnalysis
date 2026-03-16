"""
Recommendation History Tracking System

Tracks all stock recommendations over time to prevent flip-flops and provide stability.
Implements cooldown periods and change detection.
"""

import pandas as pd
import numpy as np
import os
import sys
try:
    import fcntl
except ImportError:
    fcntl = None
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

class RecommendationHistory:
    """Manages historical recommendations and enforces consistency rules"""
    
    def __init__(self, history_file: str = 'data/recommendation_history.csv'):
        """
        Initialize recommendation history tracker
        
        Args:
            history_file: Path to CSV file storing recommendation history
        """
        self.history_file = history_file
        self.history_df = self._load_history()
        
        # Configuration
        self.MIN_HOLD_DAYS = 7  # Minimum days before allowing SELL after BUY
        self.SCORE_CHANGE_THRESHOLD = 10  # Minimum score change to override cooldown
        self.FUNDAMENTAL_CHANGE_THRESHOLD = 0.2  # 20% change in fundamentals
        
    def _load_history(self) -> pd.DataFrame:
        """Load recommendation history from CSV"""
        if os.path.exists(self.history_file):
            try:
                df = pd.read_csv(self.history_file)
                df['date'] = pd.to_datetime(df['date'])
                logging.info(f"Loaded recommendation history: {len(df)} records")
                return df
            except Exception as e:
                logging.warning(f"Error loading recommendation history: {e}")
                return self._create_empty_history()
        else:
            logging.info("No recommendation history found, creating new")
            return self._create_empty_history()
    
    OUTCOME_COLUMNS = [
        'price_7d', 'price_30d', 'price_90d',
        'return_7d', 'return_30d', 'return_90d',
    ]

    def _create_empty_history(self) -> pd.DataFrame:
        """Create empty history dataframe with proper schema"""
        return pd.DataFrame(columns=[
            'date', 'symbol', 'action', 'score', 'price', 'pe_ratio',
            'roe', 'debt_to_equity', 'reason', 'rank', 'sector',
        ] + self.OUTCOME_COLUMNS)
    
    def _save_history(self):
        """Save recommendation history to CSV with file locking for concurrency safety."""
        try:
            _dir = os.path.dirname(self.history_file)
            if _dir:
                os.makedirs(_dir, exist_ok=True)
            tmp_path = self.history_file + '.tmp'
            if fcntl is not None:
                lock_path = self.history_file + '.lock'
                with open(lock_path, 'w') as lock_fh:
                    fcntl.flock(lock_fh, fcntl.LOCK_EX)
                    self.history_df.to_csv(tmp_path, index=False)
                    os.replace(tmp_path, self.history_file)
            else:
                self.history_df.to_csv(tmp_path, index=False)
                os.replace(tmp_path, self.history_file)
            logging.info(f"Saved recommendation history: {len(self.history_df)} records")
        except Exception as e:
            logging.error(f"Error saving recommendation history: {e}")
    
    def update_outcomes(self) -> int:
        """
        Back-fill forward returns for past recommendations whose outcome windows
        have elapsed.  Returns the number of rows updated.
        """
        updated = 0
        now = datetime.now()
        horizons = {'7d': 7, '30d': 30, '90d': 90}

        for idx, row in self.history_df.iterrows():
            rec_date = pd.to_datetime(row['date'], errors='coerce')
            if pd.isna(rec_date):
                continue
            if hasattr(rec_date, 'tzinfo') and rec_date.tzinfo is not None:
                rec_date = rec_date.tz_localize(None)
            rec_price = row.get('price')
            if pd.isna(rec_price) or rec_price in (None, 0):
                continue

            needs_update = False
            for label, days in horizons.items():
                col_price = f'price_{label}'
                if pd.isna(row.get(col_price)) and (now - rec_date).days >= days:
                    needs_update = True
                    break

            if not needs_update:
                continue

            symbol = row['symbol']
            try:
                suffix = '.NS' if not symbol.endswith('.NS') else ''
                ticker = yf.Ticker(f"{symbol}{suffix}")
                start = rec_date - timedelta(days=1)
                end = rec_date + timedelta(days=95)
                hist = ticker.history(start=start, end=end)
                if hist.empty:
                    continue
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)

                for label, days in horizons.items():
                    col_price = f'price_{label}'
                    col_ret = f'return_{label}'
                    if pd.isna(row.get(col_price)) and (now - rec_date).days >= days:
                        target_date = rec_date + timedelta(days=days)
                        future = hist[hist.index >= target_date]
                        if not future.empty:
                            fwd_price = float(future['Close'].iloc[0])
                            fwd_ret = ((fwd_price - float(rec_price)) / float(rec_price)) * 100
                            self.history_df.at[idx, col_price] = fwd_price
                            self.history_df.at[idx, col_ret] = round(fwd_ret, 2)
                            updated += 1
            except Exception as e:
                logging.debug(f"Outcome fetch failed for {symbol}: {e}")

        if updated:
            self._save_history()
            logging.info(f"Updated {updated} outcome fields")
        return updated

    def get_last_recommendation(self, symbol: str) -> Optional[Dict]:
        """
        Get the most recent recommendation for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with last recommendation details, or None if not found
        """
        symbol_history = self.history_df[self.history_df['symbol'] == symbol]
        
        if symbol_history.empty:
            return None
        
        last_rec = symbol_history.sort_values('date', ascending=False).iloc[0]
        return last_rec.to_dict()
    
    def check_cooldown_period(self, symbol: str, proposed_action: str) -> Tuple[bool, str]:
        """
        Check if stock is within cooldown period
        
        Args:
            symbol: Stock symbol
            proposed_action: Proposed action (BUY/SELL/HOLD/INCREASE)
            
        Returns:
            Tuple of (is_allowed, warning_message)
        """
        last_rec = self.get_last_recommendation(symbol)
        
        if not last_rec:
            return True, ""  # No history, allow action
        
        last_action = last_rec.get('action', '')
        last_date = pd.to_datetime(last_rec.get('date'), errors='coerce')
        if pd.isna(last_date):
            return True, ""
        if last_date.tzinfo is not None:
            last_date = last_date.tz_localize(None)
        days_since = (datetime.now() - last_date).days
        
        # Check for flip-flops
        if last_action in ['BUY', 'INCREASE'] and proposed_action == 'SELL':
            if days_since < self.MIN_HOLD_DAYS:
                warning = (
                    f"⚠️ COOLDOWN ACTIVE: Last action was {last_action} "
                    f"{days_since} days ago (minimum {self.MIN_HOLD_DAYS} days required). "
                    f"Recommendation changed to HOLD."
                )
                return False, warning
        
        if last_action == 'SELL' and proposed_action in ['BUY', 'INCREASE']:
            if days_since < self.MIN_HOLD_DAYS:
                warning = (
                    f"⚠️ COOLDOWN ACTIVE: Last action was {last_action} "
                    f"{days_since} days ago (minimum {self.MIN_HOLD_DAYS} days required). "
                    f"Recommendation changed to HOLD."
                )
                return False, warning
        
        return True, ""
    
    def check_score_change(self, symbol: str, current_score: float) -> Tuple[bool, str]:
        """
        Check if score change is significant enough to warrant action change
        
        Args:
            symbol: Stock symbol
            current_score: Current overall score
            
        Returns:
            Tuple of (is_significant, change_description)
        """
        last_rec = self.get_last_recommendation(symbol)
        
        if not last_rec:
            return True, "New stock, no history"
        
        last_score = last_rec.get('score', 0)
        score_change = current_score - last_score
        
        is_significant = abs(score_change) >= self.SCORE_CHANGE_THRESHOLD
        
        change_desc = (
            f"Score change: {last_score:.1f} → {current_score:.1f} "
            f"({score_change:+.1f} points)"
        )
        
        if is_significant:
            if score_change > 0:
                change_desc += " ✅ SIGNIFICANT IMPROVEMENT"
            else:
                change_desc += " ⚠️ SIGNIFICANT DETERIORATION"
        else:
            change_desc += " ℹ️ Minor change (within threshold)"
        
        return is_significant, change_desc
    
    def check_fundamental_change(self, symbol: str, current_fundamentals: Dict) -> Tuple[bool, List[str]]:
        """
        Check if fundamentals have changed significantly
        
        Args:
            symbol: Stock symbol
            current_fundamentals: Dict with pe_ratio, roe, debt_to_equity
            
        Returns:
            Tuple of (has_changed, list_of_changes)
        """
        last_rec = self.get_last_recommendation(symbol)
        
        if not last_rec:
            return False, []
        
        changes = []
        has_significant_change = False
        
        # Check PE Ratio change
        last_pe = last_rec.get('pe_ratio', 0)
        current_pe = current_fundamentals.get('pe_ratio', 0)
        _lp_valid = last_pe is not None and not (isinstance(last_pe, float) and np.isnan(last_pe)) and last_pe != 0
        _cp_valid = current_pe is not None and not (isinstance(current_pe, float) and np.isnan(current_pe))
        if _lp_valid and _cp_valid:
            pe_change_pct = abs(current_pe - last_pe) / last_pe
            if pe_change_pct > self.FUNDAMENTAL_CHANGE_THRESHOLD:
                changes.append(f"PE Ratio: {last_pe:.1f} → {current_pe:.1f} ({pe_change_pct*100:+.1f}%)")
                has_significant_change = True
        
        # Check ROE change
        last_roe = last_rec.get('roe', 0)
        current_roe = current_fundamentals.get('roe', 0)
        _lr_valid = last_roe is not None and not (isinstance(last_roe, float) and np.isnan(last_roe))
        _cr_valid = current_roe is not None and not (isinstance(current_roe, float) and np.isnan(current_roe))
        if _lr_valid and _cr_valid:
            roe_change = current_roe - last_roe
            if abs(roe_change) > 5:  # 5% absolute change
                changes.append(f"ROE: {last_roe:.1f}% → {current_roe:.1f}% ({roe_change:+.1f}%)")
                has_significant_change = True
        
        # Check Debt/Equity change
        last_debt = last_rec.get('debt_to_equity', 0)
        current_debt = current_fundamentals.get('debt_to_equity', 0)
        _ld_valid = last_debt is not None and not (isinstance(last_debt, float) and np.isnan(last_debt))
        _cd_valid = current_debt is not None and not (isinstance(current_debt, float) and np.isnan(current_debt))
        if _ld_valid and _cd_valid:
            debt_change_pct = abs(current_debt - last_debt) / (last_debt if last_debt != 0 else 1)
            if debt_change_pct > self.FUNDAMENTAL_CHANGE_THRESHOLD:
                changes.append(f"Debt/Equity: {last_debt:.2f} → {current_debt:.2f} ({debt_change_pct*100:+.1f}%)")
                has_significant_change = True
        
        return has_significant_change, changes
    
    def validate_recommendation(self, 
                              symbol: str,
                              proposed_action: str,
                              current_score: float,
                              current_price: float,
                              fundamentals: Dict,
                              reason: str = "",
                              rank: int = 0,
                              sector: str = "") -> Dict:
        """
        Validate and potentially override recommendation based on history
        
        Args:
            symbol: Stock symbol
            proposed_action: Proposed action (BUY/SELL/HOLD/INCREASE)
            current_score: Current overall score
            current_price: Current stock price
            fundamentals: Dict with pe_ratio, roe, debt_to_equity
            reason: Reason for recommendation
            rank: Stock rank in portfolio
            sector: Stock sector
            
        Returns:
            Dict with validated action, warnings, and reasons
        """
        result = {
            'symbol': symbol,
            'original_action': proposed_action,
            'final_action': proposed_action,
            'warnings': [],
            'reasons': [reason] if reason else [],
            'history_checked': True
        }
        
        # Check cooldown period
        cooldown_ok, cooldown_warning = self.check_cooldown_period(symbol, proposed_action)
        if not cooldown_ok:
            result['final_action'] = 'HOLD'
            result['warnings'].append(cooldown_warning)
            result['reasons'].append("Cooldown period active")
        
        # Check score change significance
        score_significant, score_change_desc = self.check_score_change(symbol, current_score)
        result['reasons'].append(score_change_desc)
        
        # Check fundamental changes
        fundamental_changed, fundamental_changes = self.check_fundamental_change(symbol, fundamentals)
        if fundamental_changed:
            result['warnings'].append(f"⚠️ FUNDAMENTAL CHANGES DETECTED: {', '.join(fundamental_changes)}")
            result['reasons'].extend(fundamental_changes)
        
        # Override SELL if score change is minor and fundamentals unchanged
        if proposed_action == 'SELL' and not score_significant and not fundamental_changed:
            last_rec = self.get_last_recommendation(symbol)
            if last_rec and last_rec.get('action') in ['BUY', 'INCREASE', 'HOLD']:
                result['final_action'] = 'HOLD'
                result['warnings'].append(
                    "⚠️ SELL overridden to HOLD: Score change minor and fundamentals stable"
                )
                result['reasons'].append("Preventing premature exit")
        
        # Add recommendation change notification
        last_rec = self.get_last_recommendation(symbol)
        if last_rec:
            last_action = last_rec.get('action')
            if last_action != result['final_action']:
                last_date = pd.to_datetime(last_rec.get('date'), errors='coerce')
                if pd.isna(last_date):
                    days_since = 0
                else:
                    if hasattr(last_date, 'tzinfo') and last_date.tzinfo is not None:
                        last_date = last_date.tz_localize(None)
                    days_since = (datetime.now() - last_date).days
                result['warnings'].append(
                    f"📊 RECOMMENDATION CHANGED: {last_action} → {result['final_action']} "
                    f"(after {days_since} days)"
                )
        
        return result
    
    def record_recommendation(self,
                            symbol: str,
                            action: str,
                            score: float,
                            price: float,
                            fundamentals: Dict,
                            reason: str = "",
                            rank: int = 0,
                            sector: str = ""):
        """
        Record a new recommendation in history
        
        Args:
            symbol: Stock symbol
            action: Action taken (BUY/SELL/HOLD/INCREASE)
            score: Overall score
            price: Stock price
            fundamentals: Dict with pe_ratio, roe, debt_to_equity
            reason: Reason for recommendation
            rank: Stock rank
            sector: Stock sector
        """
        new_rec = pd.DataFrame([{
            'date': datetime.now(),
            'symbol': symbol,
            'action': action,
            'score': score,
            'price': price,
            'pe_ratio': fundamentals.get('pe_ratio', 0),
            'roe': fundamentals.get('roe', 0),
            'debt_to_equity': fundamentals.get('debt_to_equity', 0),
            'reason': reason,
            'rank': rank,
            'sector': sector
        }])
        
        self.history_df = pd.concat([self.history_df, new_rec], ignore_index=True)
        self._save_history()
        
        # Ensure price and score are numeric for formatting
        try:
            price_val = float(price) if price else 0.0
            score_val = float(score) if score else 0.0
            logging.info(f"Recorded recommendation: {symbol} - {action} @ {price_val:.2f} (score: {score_val:.1f})")
        except (ValueError, TypeError):
            logging.info(f"Recorded recommendation: {symbol} - {action} @ {price} (score: {score})")
    
    def get_recommendation_summary(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """
        Get recommendation history summary for a symbol
        
        Args:
            symbol: Stock symbol
            days: Number of days to look back
            
        Returns:
            DataFrame with recent recommendation history
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        symbol_history = self.history_df[
            (self.history_df['symbol'] == symbol) &
            (self.history_df['date'] >= cutoff_date)
        ].sort_values('date', ascending=False)
        
        return symbol_history
    
    def get_flip_flop_stocks(self, days: int = 14) -> List[Dict]:
        """
        Identify stocks with flip-flopping recommendations
        
        Args:
            days: Period to check for flip-flops
            
        Returns:
            List of dicts with flip-flop details
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_history = self.history_df[self.history_df['date'] >= cutoff_date]
        
        flip_flops = []
        
        for symbol in recent_history['symbol'].unique():
            symbol_recs = recent_history[recent_history['symbol'] == symbol].sort_values('date')
            
            if len(symbol_recs) < 2:
                continue
            
            # Check for BUY -> SELL or SELL -> BUY patterns
            actions = symbol_recs['action'].tolist()
            dates = symbol_recs['date'].tolist()
            
            for i in range(len(actions) - 1):
                if (actions[i] in ['BUY', 'INCREASE'] and actions[i+1] == 'SELL') or \
                   (actions[i] == 'SELL' and actions[i+1] in ['BUY', 'INCREASE']):
                    _d0 = pd.to_datetime(dates[i], errors='coerce')
                    _d1 = pd.to_datetime(dates[i+1], errors='coerce')
                    if pd.isna(_d0) or pd.isna(_d1):
                        continue
                    days_between = (_d1 - _d0).days
                    flip_flops.append({
                        'symbol': symbol,
                        'first_action': actions[i],
                        'first_date': dates[i],
                        'second_action': actions[i+1],
                        'second_date': dates[i+1],
                        'days_between': days_between,
                        'warning': f"Flip-flop detected: {actions[i]} → {actions[i+1]} in {days_between} days"
                    })
        
        return flip_flops
    
    def generate_stability_report(self) -> Dict:
        """
        Generate a report on recommendation stability
        
        Returns:
            Dict with stability metrics
        """
        if self.history_df.empty:
            return {
                'total_recommendations': 0,
                'unique_stocks': 0,
                'flip_flops_7d': 0,
                'flip_flops_14d': 0,
                'average_hold_days': 0
            }
        
        flip_flops_7d = len(self.get_flip_flop_stocks(days=7))
        flip_flops_14d = len(self.get_flip_flop_stocks(days=14))
        
        # Calculate average hold days for each stock
        hold_days = []
        for symbol in self.history_df['symbol'].unique():
            symbol_recs = self.history_df[self.history_df['symbol'] == symbol].sort_values('date')
            if len(symbol_recs) >= 2:
                for i in range(len(symbol_recs) - 1):
                    _d0 = pd.to_datetime(symbol_recs.iloc[i]['date'], errors='coerce')
                    _d1 = pd.to_datetime(symbol_recs.iloc[i+1]['date'], errors='coerce')
                    if pd.isna(_d0) or pd.isna(_d1):
                        continue
                    hold_days.append((_d1 - _d0).days)
        
        return {
            'total_recommendations': len(self.history_df),
            'unique_stocks': self.history_df['symbol'].nunique(),
            'flip_flops_7d': flip_flops_7d,
            'flip_flops_14d': flip_flops_14d,
            'average_hold_days': sum(hold_days) / len(hold_days) if hold_days else 0,
            'oldest_recommendation': self.history_df['date'].min(),
            'latest_recommendation': self.history_df['date'].max()
        }
