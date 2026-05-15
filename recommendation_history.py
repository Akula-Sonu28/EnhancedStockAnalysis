"""
Recommendation History Tracking System

Tracks all stock recommendations over time to prevent flip-flops and provide stability.
Implements cooldown periods and change detection.
"""

import pandas as pd
import numpy as np
import os
import sys
import json
try:
    import fcntl
except ImportError:
    fcntl = None
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import threading

import re as _re

try:
    from src.universe_filter import is_excluded_instrument as _is_excluded_instrument
except Exception:
    def _is_excluded_instrument(_sym: str):
        return False, ''

def _strip_annotation(raw: str) -> str:
    """Remove parenthesised annotations like '(was BUY)' and pipe-delimited suffixes
    so keyword matching operates only on the effective action token."""
    s = str(_re.sub(r'\(.*?\)', '', str(raw)))
    s = str(s.split('|')[0])
    return s.strip()


def _normalize_action(action: str) -> str:
    """Strip emojis/annotations and normalize to canonical action names."""
    if not action:
        return 'HOLD'
    cleaned = _re.sub(r'[^\w\s\->()/]', '', str(action)).strip()
    effective = _strip_annotation(cleaned).upper()
    if 'EXIT' in effective:
        return 'EXIT'
    if 'EMERGENCY' in effective or ('SELL' in effective and 'CONSIDER' not in effective and 'WEAK' not in effective):
        return 'SELL'
    if 'STOP LOSS' in effective:
        return 'SELL'
    if 'SWAP' in effective:
        return 'SWAP'
    if 'INCREASE' in effective or 'MOMENTUM PLAY' in effective:
        return 'INCREASE'
    if 'STRONG BUY' in effective or 'STRONG_BUY' in effective:
        return 'STRONG BUY'
    if 'NEW POSITION' in effective:
        return 'NEW POSITION'
    if 'BUY' in effective and 'WEAK' not in effective:
        return 'BUY'
    # [Rule 5] SCALE_OUT_20 = additive sub-action of REDUCE. We map any
    # SCALE_OUT* label (with or without the 20 suffix) to the canonical
    # SCALE_OUT_20 so audit history is stable, while REDUCE/BOOK fall
    # back to plain REDUCE. The Suite 1 action-enum contract treats this
    # as a new additive entry; check `SCALE_OUT_20` BEFORE the REDUCE
    # fallback so SCALE_OUT does not collapse into REDUCE.
    if 'SCALE_OUT' in effective or 'SCALE OUT' in effective:
        return 'SCALE_OUT_20'
    if 'REDUCE' in effective or 'BOOK' in effective:
        return 'REDUCE'
    if 'WEAK SELL' in effective or 'CONSIDER SELLING' in effective or 'CONSIDER SELL' in effective:
        return 'WEAK SELL'
    if 'HOLD' in effective or 'KEEP' in effective or 'WATCH' in effective:
        return 'HOLD'
    return cleaned

class RecommendationHistory:
    """Manages historical recommendations and enforces consistency rules"""
    
    def __init__(self, history_file: str = 'data/recommendation_history.csv'):
        """
        Initialize recommendation history tracker
        
        Args:
            history_file: Path to CSV file storing recommendation history
        """
        self.history_file = history_file
        self._lock = threading.Lock()

        # Configuration — must be set BEFORE _load_history() which references them
        self.MIN_HOLD_DAYS = 7
        self.SCORE_CHANGE_THRESHOLD = 10
        self.FUNDAMENTAL_CHANGE_THRESHOLD = 0.2
        self.HISTORY_TTL_DAYS = 90

        # [F-NEW-10] Batch-save support. When `_batch_depth > 0`, calls to
        # `_save_history` from within record_recommendation() and friends
        # only mark the dirty flag; the actual flush happens on the
        # outermost context exit. Caller usage:
        #     with rec_history.batch_saves():
        #         for stock in stocks:
        #             rec_history.record_recommendation(...)
        # Backwards-compatible: outside the context, every call flushes
        # exactly as before.
        self._batch_depth = 0
        self._batch_dirty = False

        self.history_df = self._load_history()

    def batch_saves(self):
        """Context manager that defers _save_history flushes until exit.
        Reduces 18 file flushes (1 per recommendation) to 1 per batch run.
        Reentrant via depth counter.
        """
        rec_history_self = self

        class _BatchCtx:
            def __enter__(_self):
                rec_history_self._batch_depth += 1
                return rec_history_self

            def __exit__(_self, exc_type, exc, tb):
                rec_history_self._batch_depth -= 1
                if rec_history_self._batch_depth == 0 and rec_history_self._batch_dirty:
                    rec_history_self._batch_dirty = False
                    rec_history_self._save_history(_force=True)
                return False

        return _BatchCtx()

    def _load_history(self) -> pd.DataFrame:
        """Load recommendation history from CSV, ensuring outcome columns exist."""
        if os.path.exists(self.history_file):
            try:
                df = pd.read_csv(self.history_file)
                df['date'] = pd.to_datetime(df['date'])
                for col in self.OUTCOME_COLUMNS:
                    if col not in df.columns:
                        df[col] = np.nan
                cutoff = datetime.now() - timedelta(days=self.HISTORY_TTL_DAYS)
                before = len(df)
                df = df[df['date'] >= cutoff].copy()
                dropped = before - len(df)
                if dropped > 0:
                    logging.info(
                        f"Recommendation history TTL ({self.HISTORY_TTL_DAYS}d): removed {dropped} stale rows"
                    )
                logging.debug(f"Loaded recommendation history: {len(df)} records")
                return df
            except Exception as e:
                logging.warning(f"Error loading recommendation history: {e}")
                _backup = self.history_file.replace('.csv', '_backup.csv')
                if os.path.exists(_backup):
                    try:
                        logging.info("Attempting recovery from backup history file")
                        df = pd.read_csv(_backup)
                        df['date'] = pd.to_datetime(df['date'])
                        for col in self.OUTCOME_COLUMNS:
                            if col not in df.columns:
                                df[col] = np.nan
                        logging.info(f"Recovered recommendation history from backup: {len(df)} records")
                        return df
                    except Exception:
                        pass
                return self._create_empty_history()
        else:
            _backup = self.history_file.replace('.csv', '_backup.csv')
            if os.path.exists(_backup):
                try:
                    logging.info("Primary history missing, attempting backup recovery")
                    df = pd.read_csv(_backup)
                    df['date'] = pd.to_datetime(df['date'])
                    for col in self.OUTCOME_COLUMNS:
                        if col not in df.columns:
                            df[col] = np.nan
                    logging.info(f"Recovered recommendation history from backup: {len(df)} records")
                    return df
                except Exception:
                    pass
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
    
    def _save_history(self, _force: bool = False):
        """Save recommendation history to CSV with file locking for concurrency safety.

        [F-NEW-10] When batch_saves() context is active (`_batch_depth > 0`)
        and `_force` is False, the call is deferred: the dirty flag is set
        and the actual flush waits until the outermost context exits.
        """
        if self._batch_depth > 0 and not _force:
            self._batch_dirty = True
            return
        try:
            _dir = os.path.dirname(self.history_file)
            if _dir:
                os.makedirs(_dir, exist_ok=True)
            if os.path.exists(self.history_file):
                import shutil
                _backup = self.history_file.replace('.csv', '_backup.csv')
                try:
                    shutil.copy2(self.history_file, _backup)
                except OSError:
                    pass
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
        Thread-safe: acquires self._lock during DataFrame mutation.
        """
        with self._lock:
            return self._update_outcomes_locked()

    def _update_outcomes_locked(self) -> int:
        updated = 0
        now = datetime.now()
        horizons = {'7d': 7, '30d': 30, '90d': 90}

        pending_rows = []
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
            if needs_update:
                pending_rows.append((idx, row['symbol'], rec_date, float(rec_price)))

        if not pending_rows:
            return 0

        symbols_needed = list({
            (s + '.NS' if not s.endswith('.NS') else s)
            for _, s, _, _ in pending_rows
        })
        global_start = min(rd - timedelta(days=1) for _, _, rd, _ in pending_rows)
        global_end = max(rd + timedelta(days=95) for _, _, rd, _ in pending_rows)

        try:
            bulk = yf.download(
                symbols_needed,
                start=global_start.strftime('%Y-%m-%d'),
                end=global_end.strftime('%Y-%m-%d'),
                group_by='ticker',
                progress=False,
                threads=True
            )
        except Exception as e:
            logging.warning(f"Batch yfinance download failed, falling back: {e}")
            bulk = None

        for idx, symbol, rec_date, rec_price in pending_rows:
            try:
                ns_sym = symbol + '.NS' if not symbol.endswith('.NS') else symbol
                if bulk is not None and not bulk.empty:
                    if len(symbols_needed) == 1:
                        hist = bulk
                    else:
                        hist = bulk[ns_sym] if ns_sym in bulk.columns.get_level_values(0) else pd.DataFrame()
                    if isinstance(hist, pd.DataFrame) and not hist.empty:
                        hist = hist.dropna(subset=['Close'])
                else:
                    hist = pd.DataFrame()

                if hist.empty:
                    ticker = yf.Ticker(ns_sym)
                    hist = ticker.history(
                        start=(rec_date - timedelta(days=1)),
                        end=(rec_date + timedelta(days=95))
                    )

                if hist.empty:
                    continue
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)

                for label, days in horizons.items():
                    col_price = f'price_{label}'
                    col_ret = f'return_{label}'
                    if pd.isna(self.history_df.at[idx, col_price] if col_price in self.history_df.columns else np.nan) \
                            and (now - rec_date).days >= days:
                        target_date = rec_date + timedelta(days=days)
                        future = hist[hist.index >= target_date]
                        if not future.empty:
                            fwd_price = float(future['Close'].iloc[0])
                            fwd_ret = ((fwd_price - rec_price) / rec_price) * 100 if rec_price != 0 else 0.0
                            self.history_df.at[idx, col_price] = fwd_price
                            self.history_df.at[idx, col_ret] = round(fwd_ret, 2)
                            updated += 1
            except Exception as e:
                logging.debug(f"Outcome fetch failed for {symbol}: {e}")

        if updated:
            self._save_history()
            logging.info(f"Updated {updated} outcome fields")
        return updated

    @staticmethod
    def _v2_calibration_event_dates() -> List[datetime]:
        """[F-NEW-6] Read the timestamps when v2 weights were last (re)written.

        Comparing scores across a calibration event produces false +/-N pp
        deltas that look like real moves but are actually weight refreshes.
        The suppressor below uses these timestamps to skip such comparisons.

        Returns list of datetime objects (one per known v2 weights file).
        Empty list if no files present (e.g. pre-promotion).
        """
        events: List[datetime] = []
        for _path in (
            'data/calibrated_weights_v2.json',
            'data/calibrated_weights_v2_BULL.json',
            'data/calibrated_weights_v2_BEAR.json',
            'data/calibrated_weights_v2_SIDEWAYS.json',
        ):
            try:
                with open(_path, 'r') as _fh:
                    _payload = json.load(_fh)
                _ts = _payload.get('updated')
                if _ts:
                    events.append(datetime.fromisoformat(_ts))
            except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError):
                pass
        return events

    def get_weekly_changes(self, days: int = 7) -> Dict:
        """
        Compare current scores with scores from `days` ago.
        Returns dict with 'improved', 'deteriorated', 'new' lists of dicts.
        """
        with self._lock:
            if self.history_df is None or self.history_df.empty:
                return {'improved': [], 'deteriorated': [], 'new': []}

            df = self.history_df.copy()
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            now = datetime.now()
            cutoff = now - timedelta(days=days)

            recent = df[df['date'] >= cutoff].sort_values('date', ascending=False)
            older = df[df['date'] < cutoff].sort_values('date', ascending=False)

            # [F-NEW-6] Calibration-event suppressor. Round 19 (Q122) added
            # engine-mismatch suppression (current has score_v2, prev does
            # not). That catches the v1->v2 promotion boundary but NOT
            # intra-v2 weight refreshes. Example: TORNTPHARM 2026-05-08
            # score_v2=30.3 vs 2026-05-15 score_v2=71.3 (+41 pts). Both rows
            # have valid score_v2 and same regime, but the +40 jump on
            # 2026-05-12 was a weights refresh, not a fundamentals change.
            # We suppress any comparison where the older row predates the
            # most recent calibration event AND the absolute delta exceeds
            # the suspicion threshold.
            calib_events = self._v2_calibration_event_dates()
            most_recent_calib = max(calib_events) if calib_events else None
            CALIB_DELTA_SUSPECT_PP = 15.0  # > 15pp swing across a refresh = artefact

            improved, deteriorated, new_stocks = [], [], []
            seen = set()

            # [Investor-audit Q122] When v2 engine was promoted live, the
            # `score` column shifted from v1-blended to v2-blended values.
            # Comparing today's v2-score to last week's v1-score produces
            # bogus 40+ point "deteriorations" that misleadingly show
            # 23/24 holdings collapsing overnight. Fix:
            #   1) Prefer `score_v2` on BOTH sides; search backward in
            #      `prev_rows` for an older row with valid score_v2
            #      (skip NaN rows from before v2 was logged).
            #   2) If no v2-aware older row exists at all, mark the
            #      symbol as `engine_switch_skip` and exclude from
            #      improved/deteriorated lists (don't show a misleading
            #      v1->v2 comparison).
            def _valid_num(v):
                return v is not None and not (isinstance(v, float) and np.isnan(v))

            for _, row in recent.iterrows():
                sym = row.get('symbol')
                if sym in seen:
                    continue
                seen.add(sym)
                curr_score = row.get('score', 0)
                if curr_score is None or (isinstance(curr_score, float) and np.isnan(curr_score)):
                    curr_score = 0

                prev_rows = older[older['symbol'] == sym]
                if prev_rows.empty:
                    new_stocks.append({'symbol': sym, 'score': curr_score, 'action': row.get('action', '')})
                    continue

                # Try v2-aware comparison: search prev_rows for any older
                # row with valid score_v2 (recent-first order).
                curr_v2 = row.get('score_v2')
                _cs = _ps = None
                _prev_date = None
                if _valid_num(curr_v2):
                    for _, pr in prev_rows.iterrows():
                        pv = pr.get('score_v2')
                        if _valid_num(pv):
                            _cs, _ps = float(curr_v2), float(pv)
                            _prev_date = pr.get('date')
                            break
                # If no v2 prev row, fall back to v1-on-v1 (will be
                # apples-to-apples only if current engine still produces
                # v1-comparable scores; with v2 live this can still drift,
                # but is the best we can do for pre-v2-era history).
                if _cs is None:
                    prev_row = prev_rows.iloc[0]
                    _cs = 0.0 if not _valid_num(curr_score) else float(curr_score)
                    pv1 = prev_row.get('score', 0)
                    _ps = 0.0 if not _valid_num(pv1) else float(pv1)
                    _prev_date = prev_row.get('date')
                    # If current row HAS score_v2 but older does NOT, the
                    # comparison is engine-mismatched. Suppress.
                    if _valid_num(curr_v2) and not _valid_num(prev_row.get('score_v2')):
                        continue
                delta = _cs - _ps

                # [F-NEW-6] Calibration-event suppressor. If the prev row
                # predates the most recent calibration AND delta crosses
                # the suspicion threshold, the move is most likely a
                # weights refresh artefact rather than a real fundamentals
                # shift. Skip rather than mislead.
                if (most_recent_calib is not None
                        and _prev_date is not None
                        and pd.notna(_prev_date)
                        and pd.Timestamp(_prev_date).to_pydatetime().replace(tzinfo=None)
                            < most_recent_calib.replace(tzinfo=None)
                        and abs(delta) >= CALIB_DELTA_SUSPECT_PP):
                    continue

                entry = {'symbol': sym, 'current_score': _cs, 'previous_score': _ps, 'change': round(delta, 1), 'action': row.get('action', '')}
                if delta >= 5:
                    improved.append(entry)
                elif delta <= -5:
                    deteriorated.append(entry)

            improved.sort(key=lambda x: -x['change'])
            deteriorated.sort(key=lambda x: x['change'])
            return {'improved': improved, 'deteriorated': deteriorated, 'new': new_stocks}

    def get_last_recommendation(self, symbol: str) -> Optional[Dict]:
        """
        Get the most recent recommendation for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with last recommendation details, or None if not found
        """
        with self._lock:
            symbol_history = self.history_df[self.history_df['symbol'] == symbol]
            
            if symbol_history.empty:
                return None
            
            last_rec = symbol_history.sort_values('date', ascending=False).iloc[0]
            return last_rec.to_dict()
    
    def get_previous_recommendation_tier(self, symbol: str) -> str:
        """Return the recommendation tier (BUY/HOLD/WEAK_SELL/SELL) from the last run.
        Used by hysteresis logic to prevent flip-flopping at threshold boundaries."""
        last = self.get_last_recommendation(symbol)
        if not last:
            return ''
        action = str(last.get('action', ''))
        if 'STRONG BUY' in action or 'BUY' in action:
            return 'BUY'
        elif 'SELL' in action and 'WEAK' not in action:
            return 'SELL'
        elif 'WEAK' in action:
            return 'WEAK_SELL'
        return 'HOLD'

    def get_sell_signal_streak(self, symbol: str) -> int:
        """Return number of consecutive sessions with sell-side signals for a symbol.
        Counts backward from the most recent recommendation. SELL, WEAK SELL,
        CONSIDER SELLING, and REDUCE all count as sell-side. Stops at the first
        non-sell-side action or when history is exhausted."""
        with self._lock:
            sym_hist = self.history_df[self.history_df['symbol'] == symbol].copy()
            if sym_hist.empty:
                return 0
            sym_hist = sym_hist.sort_values('date', ascending=False)
            seen_dates = set()
            streak = 0
            _sell_kw = ('SELL', 'WEAK', 'CONSIDER', 'REDUCE', 'EXIT', 'STOP')
            for _, row in sym_hist.iterrows():
                d = str(row.get('date', ''))[:10]
                if d in seen_dates:
                    continue
                seen_dates.add(d)
                action = str(row.get('action', '')).upper()
                if any(kw in action for kw in _sell_kw):
                    streak += 1
                else:
                    break
            return streak

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
        
        last_action_raw = last_rec.get('action', '')
        last_action_norm = _normalize_action(last_action_raw)
        proposed_action_norm = _normalize_action(proposed_action)
        last_date = pd.to_datetime(last_rec.get('date'), errors='coerce')
        if pd.isna(last_date):
            return True, ""
        if last_date.tzinfo is not None:
            last_date = last_date.tz_localize(None)
        days_since = (datetime.now() - last_date).days
        
        _SELL_SIDE_NORM = ('SELL', 'WEAK SELL', 'REDUCE', 'SWAP', 'EXIT')
        _BUY_SIDE_NORM = ('BUY', 'STRONG BUY', 'INCREASE', 'NEW POSITION')

        if last_action_norm in _BUY_SIDE_NORM and proposed_action_norm in _SELL_SIDE_NORM:
            if days_since < self.MIN_HOLD_DAYS:
                warning = (
                    f"⚠️ COOLDOWN ACTIVE: Last action was {last_action_raw} "
                    f"{days_since} days ago (minimum {self.MIN_HOLD_DAYS} days required). "
                    f"Recommendation changed to HOLD."
                )
                return False, warning
        
        if last_action_norm in _SELL_SIDE_NORM and proposed_action_norm in _BUY_SIDE_NORM:
            if days_since < self.MIN_HOLD_DAYS:
                warning = (
                    f"⚠️ COOLDOWN ACTIVE: Last action was {last_action_raw} "
                    f"{days_since} days ago (minimum {self.MIN_HOLD_DAYS} days required). "
                    f"Recommendation changed to HOLD."
                )
                return False, warning
        
        return True, ""
    
    def check_directional_commitment(self, symbol: str, proposed_action: str,
                                      current_score: float) -> Tuple[str, str]:
        """Enforce directional commitment to prevent flip-flops.
        
        Once a bearish signal is issued, require meaningful score improvement
        before upgrading. Once bullish, require meaningful decline before
        downgrading to full SELL.
        
        Returns:
            Tuple of (committed_action, reason) — committed_action may differ
            from proposed_action if the direction change is not justified.
        """
        _BEARISH = ('SELL', 'WEAK SELL', 'REDUCE', 'EXIT', 'SWAP')
        _BULLISH = ('BUY', 'STRONG BUY', 'INCREASE', 'NEW POSITION')
        UPGRADE_TO_HOLD_THRESHOLD = 5.0
        UPGRADE_TO_BUY_THRESHOLD = 10.0
        DOWNGRADE_TO_SELL_THRESHOLD = 5.0

        proposed_norm = _normalize_action(proposed_action)
        last_rec = self.get_last_recommendation(symbol)
        if not last_rec:
            return proposed_action, ""

        last_action_norm = _normalize_action(str(last_rec.get('action', '')))
        _ls_raw = last_rec.get('score', 0)
        last_score = float(np.nan_to_num(_ls_raw, nan=0.0)) if _ls_raw is not None else 0.0
        score_delta = current_score - last_score

        if last_action_norm in _BEARISH:
            if proposed_norm == 'HOLD' and score_delta < UPGRADE_TO_HOLD_THRESHOLD:
                return last_rec.get('action', proposed_action), (
                    f"DIRECTIONAL COMMITMENT: Score improved only {score_delta:+.1f} "
                    f"(need +{UPGRADE_TO_HOLD_THRESHOLD:.0f} to upgrade from "
                    f"{last_action_norm} to HOLD)")
            if proposed_norm in _BULLISH and score_delta < UPGRADE_TO_BUY_THRESHOLD:
                fallback = 'HOLD' if score_delta >= UPGRADE_TO_HOLD_THRESHOLD else last_rec.get('action', proposed_action)
                return fallback, (
                    f"DIRECTIONAL COMMITMENT: Score improved only {score_delta:+.1f} "
                    f"(need +{UPGRADE_TO_BUY_THRESHOLD:.0f} to upgrade from "
                    f"{last_action_norm} to {proposed_norm})")

        if last_action_norm in _BULLISH:
            if proposed_norm in ('SELL', 'EXIT', 'SWAP') and score_delta > -DOWNGRADE_TO_SELL_THRESHOLD:
                return 'HOLD', (
                    f"DIRECTIONAL COMMITMENT: Score declined only {score_delta:+.1f} "
                    f"(need -{DOWNGRADE_TO_SELL_THRESHOLD:.0f} to downgrade from "
                    f"{last_action_norm} to {proposed_norm})")

        return proposed_action, ""
    
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
        if last_score is None or (isinstance(last_score, float) and np.isnan(last_score)):
            last_score = 0.0
        if current_score is None or (isinstance(current_score, float) and np.isnan(current_score)):
            current_score = 0.0
        last_score = float(last_score)
        current_score = float(current_score)
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
                              sector: str = "",
                              hard_stop_tier: str = "NONE") -> Dict:
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
            hard_stop_tier: Output of unified hard-stop policy.
                When set to 'EMERGENCY' / 'HARD_STOP' / 'SOFT_STOP', the
                premature-exit-prevention override below is bypassed —
                a stop-loss SELL is by definition NOT premature.
                Phase 0.5 fix: prevents KOTAKBANK-class silent SELL→HOLD downgrades.
            
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
        
        # Directional commitment: prevent flip-flops by requiring meaningful
        # score improvement before reversing direction.
        if result['final_action'] == proposed_action:
            committed_action, commit_reason = self.check_directional_commitment(
                symbol, proposed_action, current_score)
            if committed_action != proposed_action:
                result['final_action'] = committed_action
                result['warnings'].append(f"⚠️ {commit_reason}")
                result['reasons'].append("Directional commitment enforced")
        
        # Check score change significance
        score_significant, score_change_desc = self.check_score_change(symbol, current_score)
        result['reasons'].append(score_change_desc)
        
        # Check fundamental changes
        fundamental_changed, fundamental_changes = self.check_fundamental_change(symbol, fundamentals)
        if fundamental_changed:
            result['warnings'].append(f"⚠️ FUNDAMENTAL CHANGES DETECTED: {', '.join(fundamental_changes)}")
            result['reasons'].extend(fundamental_changes)
        
        # Override SELL-like actions if score change is minor and fundamentals unchanged.
        # NEVER override EMERGENCY or STOP LOSS with significant score change.
        # Also do NOT override if there is a recent bearish trend or score is declining.
        # [Phase 0.5] Also do NOT override when the SELL is driven by the unified
        # hard-stop policy (EMERGENCY / HARD_STOP / SOFT_STOP) — a P&L-threshold
        # exit is by definition NOT premature, so the score-change/fundamentals
        # heuristic must not silence it (KOTAKBANK / CENTRALBK / PNB / UCOBANK fix).
        _is_sell_like = proposed_action in ('SELL', 'STOP LOSS', 'REDUCE 25%')
        _is_emergency = 'EMERGENCY' in str(proposed_action).upper()
        _is_stop_with_evidence = 'STOP LOSS' in str(proposed_action).upper() and score_significant
        # [Rule 6b/6c] THESIS_BREAK and TRAILING_STOP behave like hard-stop
        # exits - they must bypass the premature-exit override.
        _is_hard_stop_driven = str(hard_stop_tier).upper() in (
            'EMERGENCY', 'HARD_STOP', 'SOFT_STOP', 'THESIS_BREAK', 'TRAILING_STOP',
        )
        if _is_sell_like and not _is_emergency and not _is_stop_with_evidence and not _is_hard_stop_driven and not score_significant and not fundamental_changed:
            last_rec = self.get_last_recommendation(symbol)
            if last_rec and _normalize_action(str(last_rec.get('action', ''))) in ('BUY', 'INCREASE', 'HOLD'):
                _recent = self.get_recommendation_summary(symbol, days=14)
                _bearish_count = 0
                _score_declining = False
                if _recent is not None and not _recent.empty:
                    for _, _r in _recent.iterrows():
                        _a_norm = _normalize_action(str(_r.get('action', '')))
                        if _a_norm in ('SELL', 'WEAK SELL', 'REDUCE', 'EXIT'):
                            _bearish_count += 1
                    _ls = last_rec.get('score', current_score)
                    _last_score = float(np.nan_to_num(_ls, nan=current_score)) if _ls is not None else float(current_score)
                    _score_declining = current_score < _last_score
                if _bearish_count >= 2 or _score_declining:
                    pass
                else:
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
                            sector: str = "",
                            components: Optional[Dict] = None,
                            score_v2: Optional[float] = None,
                            regime: Optional[str] = None,
                            sleeve: Optional[str] = None):
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
            components: [v3 Layer 4] Optional dict of per-component scores for v2
                IC calibration. Recognised keys (any subset is fine):
                hybrid_fundamental_quality, hybrid_momentum_technical,
                hybrid_volume_strength, hybrid_multi_timeframe,
                hybrid_ml_signal, hybrid_risk_adjustment.
                These columns are appended at the right edge of history so
                Suite 1's history-schema contract (required_cols.issubset)
                still passes.
        """
        def _clean(v, d=0):
            if v is None:
                return d
            try:
                f = float(v)
                return d if (np.isnan(f) or np.isinf(f)) else f
            except (TypeError, ValueError):
                return d
        score = _clean(score, 0)
        price = _clean(price, 0)
        if price <= 0:
            logging.warning(f"Skipping recommendation for {symbol}: invalid price {price}")
            return
        _excluded, _excl_reason = _is_excluded_instrument(symbol)
        if _excluded:
            logging.info(f"Skipping recommendation for {symbol}: {_excl_reason}")
            return
        action = _normalize_action(action)
        today_str = datetime.now().strftime('%Y-%m-%d')

        # [F-NEW-3] Action vs reason divergence tag. The `action` column
        # holds the policy-mediated final decision (after CORE-sleeve
        # protection, hysteresis buffer, score smoothing). The `reason`
        # column holds the raw signal that drove the unfiltered score
        # threshold. When these CROSS FAMILY (e.g. action=HOLD but reason
        # text canonicalises to SELL-family), readers see a confusing pair
        # of opposing labels in Past Accuracy / Complete Data / dashboards.
        # We prefix the reason with [POLICY OVERRIDE] so the divergence
        # is visible without changing either column's semantics. Same-
        # family transitions (SELL vs EXIT, BUY vs NEW POSITION) are not
        # tagged because they convey the same investor intent.
        try:
            _BUY_FAMILY = {'STRONG BUY', 'BUY', 'NEW POSITION', 'INCREASE'}
            _SELL_FAMILY = {'SELL', 'WEAK SELL', 'REDUCE', 'EXIT', 'SCALE_OUT_20', 'SWAP'}
            _HOLD_FAMILY = {'HOLD'}

            def _family(_a):
                if _a in _BUY_FAMILY:
                    return 'BUY'
                if _a in _SELL_FAMILY:
                    return 'SELL'
                if _a in _HOLD_FAMILY:
                    return 'HOLD'
                return _a

            _reason_action_norm = _normalize_action(str(reason or '')) if reason else ''
            if (_reason_action_norm
                    and _family(_reason_action_norm) != _family(action)
                    and not str(reason).startswith('[POLICY OVERRIDE]')):
                reason = f"[POLICY OVERRIDE] action={action} | raw={reason}"
        except Exception:
            pass

        # [DQ-NATALUM] Same-day re-run policy: previously this method silently dropped any
        # second call for (symbol, today). That meant the Apr 25 post-fix run produced
        # EXIT 75-80% calls that NEVER reached recommendation_history.csv because the
        # earlier baseline run had already logged HOLD entries. Result: outcomes can't
        # be tracked when an intraday re-run changes the action.
        # New policy:
        #   - if same-day entry exists with the SAME normalized action → skip (idempotent)
        #   - if same-day entry exists with a DIFFERENT action → replace it (latest wins)
        #   - otherwise → append
        new_rec_row = {
            'date': datetime.now(),
            'symbol': symbol,
            'action': action,
            'score': score,
            'price': price,
            'pe_ratio': _clean(fundamentals.get('pe_ratio'), 0),
            'roe': _clean(fundamentals.get('roe'), 0),
            'debt_to_equity': _clean(fundamentals.get('debt_to_equity'), 0),
            'reason': reason,
            'rank': rank,
            'sector': sector,
        }
        # [v3 Layer 4] Per-component scores enable v2 IC calibration. Without
        # them the calibration script unconditionally returns SKIPPED.
        # Components are appended after the contracted history columns so
        # the Suite 1 schema check is unaffected.
        if components:
            for _ck in (
                'hybrid_fundamental_quality', 'hybrid_momentum_technical',
                'hybrid_volume_strength',     'hybrid_multi_timeframe',
                'hybrid_ml_signal',           'hybrid_risk_adjustment',
                # [Rule 3a] Growth + Value factors (additive, right-edge).
                'hybrid_growth',              'hybrid_value',
            ):
                _cv = components.get(_ck)
                new_rec_row[_ck] = _clean(_cv, None)

        # [Tier C2] Persist v2 shadow score + regime so forward IC measurement
        # against the v2 engine can start accumulating from today. Both columns
        # are appended at the right edge so the Suite 1 history-schema contract
        # (required_cols.issubset) is unaffected.
        if score_v2 is not None:
            new_rec_row['score_v2'] = _clean(score_v2, None)
        if regime is not None:
            new_rec_row['regime'] = str(regime)
        # [Rule 1] CORE / TACTICAL sleeve persistence (right-edge, additive).
        if sleeve is not None:
            new_rec_row['sleeve'] = str(sleeve).upper()
        with self._lock:
            same_day_idx = pd.Index([])
            if not self.history_df.empty:
                same_day_mask = (
                    (self.history_df['symbol'] == symbol) &
                    (self.history_df['date'].astype(str).str[:10] == today_str)
                )
                same_day = self.history_df[same_day_mask]
                if not same_day.empty:
                    existing_action = _normalize_action(str(same_day.iloc[-1].get('action', '')))
                    if existing_action == action:
                        # [Tier C2] Idempotent same-day re-run: action unchanged.
                        # Backfill any missing OPTIONAL columns (score_v2, regime,
                        # hybrid_* components) on the existing row so a Tier C2
                        # update or schema extension does not require an action
                        # change to populate. This preserves the original row
                        # ordering / count.
                        idx_target = same_day.index[-1]
                        for _ck, _val in new_rec_row.items():
                            if _ck in ('date', 'symbol', 'action', 'score',
                                       'price', 'reason', 'rank', 'sector'):
                                continue
                            if _ck not in self.history_df.columns:
                                self.history_df[_ck] = None
                            existing_val = self.history_df.at[idx_target, _ck] \
                                if _ck in self.history_df.columns else None
                            if pd.isna(existing_val) and _val is not None and not pd.isna(_val):
                                self.history_df.at[idx_target, _ck] = _val
                        self._save_history()
                        return
                    # Action changed within the same day — drop stale rows, append fresh.
                    same_day_idx = same_day.index
                    self.history_df = self.history_df.drop(index=same_day_idx).reset_index(drop=True)
                    logging.info(
                        f"[hist-update] {symbol}: same-day action change "
                        f"{existing_action} → {action} (replaced {len(same_day_idx)} rows)"
                    )
            new_rec = pd.DataFrame([new_rec_row])
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
        with self._lock:
            cutoff_date = datetime.now() - timedelta(days=days)
            symbol_history = self.history_df[
                (self.history_df['symbol'] == symbol) &
                (self.history_df['date'] >= cutoff_date)
            ].sort_values('date', ascending=False)
            
            return symbol_history.copy()
    
    def get_flip_flop_stocks(self, days: int = 14) -> List[Dict]:
        """
        Identify stocks with flip-flopping recommendations.

        [Investor-audit Q123] Engine-aware: when the v2 engine was promoted
        live, pre-promotion actions (v1-driven) flipping to post-promotion
        actions (v2-driven) are NOT real flip-flops - they're expected
        engine-switch artifacts (e.g., MAHABANK INCREASE -> SELL 0d apart
        because v1 said INCREASE on stale cache, v2 said SELL on fresh fetch).
        Suppress flip-flops where one leg has score_v2 and the other does
        not - these span the engine switch.

        Args:
            days: Period to check for flip-flops

        Returns:
            List of dicts with flip-flop details
        """
        with self._lock:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_history = self.history_df[self.history_df['date'] >= cutoff_date].copy()

        flip_flops = []

        def _has_v2(row):
            v = row.get('score_v2')
            return v is not None and not (isinstance(v, float) and np.isnan(v))

        for symbol in recent_history['symbol'].unique():
            symbol_recs = recent_history[recent_history['symbol'] == symbol].sort_values('date')

            if len(symbol_recs) < 2:
                continue

            rows = list(symbol_recs.to_dict('records'))
            actions = [r['action'] for r in rows]
            dates = [r['date'] for r in rows]

            def _v1_driven_action(r):
                """Detect actions taken under v1-blend when v2 disagreed
                strongly (>=15pt divergence). Such actions are NOT real
                conviction calls under v2-live - they're pre-promotion
                cache or v1 fallback artifacts."""
                s = r.get('score')
                v2 = r.get('score_v2')
                try:
                    if s is not None and not (isinstance(s, float) and np.isnan(s)) \
                       and v2 is not None and not (isinstance(v2, float) and np.isnan(v2)):
                        return abs(float(s) - float(v2)) >= 15.0
                except (TypeError, ValueError):
                    pass
                return False

            for i in range(len(actions) - 1):
                if (actions[i] in ['BUY', 'INCREASE'] and actions[i+1] == 'SELL') or \
                   (actions[i] == 'SELL' and actions[i+1] in ['BUY', 'INCREASE']):
                    # [Investor-audit Q123] engine-switch artifact?
                    if _has_v2(rows[i]) != _has_v2(rows[i+1]):
                        continue
                    # [Investor-audit Q123 cont.] v1-driven action artifact?
                    # When one leg had >=15pt v1-v2 divergence, the action
                    # was driven by v1 (the now-shadow engine). Real flip-
                    # flops happen on v2-consistent legs.
                    if _v1_driven_action(rows[i]) or _v1_driven_action(rows[i+1]):
                        continue
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
    
    # ------------------------------------------------------------------
    # Performance metrics (win/loss, expectancy, profit factor, etc.)
    # ------------------------------------------------------------------

    def get_performance_metrics(self, horizon: str = '30d') -> Dict:
        """
        Compute win/loss metrics from filled outcome columns.

        Args:
            horizon: '7d', '30d', or '90d'

        Returns:
            Dict with win_rate, avg_win, avg_loss, profit_factor,
            expectancy, max_dd_per_holding, best_calls, worst_calls.
        """
        ret_col = f'return_{horizon}'
        with self._lock:
            df = self.history_df.copy()

        if ret_col not in df.columns:
            return self._empty_performance()

        valid = df.dropna(subset=[ret_col]).copy()
        valid[ret_col] = pd.to_numeric(valid[ret_col], errors='coerce')
        valid = valid.dropna(subset=[ret_col])

        if valid.empty:
            return self._empty_performance()

        _SELL_SIDE = {'SELL', 'CONSIDER SELLING', 'WEAK SELL', 'REDUCE', 'REDUCE (SECTOR OVERWEIGHT)'}
        _action_upper = valid['action'].astype(str).str.upper().str.strip()
        _is_sell_side = _action_upper.isin(_SELL_SIDE) | _action_upper.str.contains('REDUCE', na=False)

        _effective_ret = valid[ret_col].copy()
        _effective_ret.loc[_is_sell_side] = -_effective_ret.loc[_is_sell_side]

        wins = valid[_effective_ret > 0]
        losses = valid[_effective_ret <= 0]

        win_rate = len(wins) / len(valid) * 100 if len(valid) else 0
        _win_rets = _effective_ret[_effective_ret > 0]
        _loss_rets = _effective_ret[_effective_ret <= 0]
        avg_win = float(_win_rets.mean()) if not _win_rets.empty else 0
        avg_loss = float(_loss_rets.mean()) if not _loss_rets.empty else 0
        loss_sum = abs(_loss_rets.sum()) if not _loss_rets.empty else 0
        win_sum = float(_win_rets.sum()) if not _win_rets.empty else 0
        profit_factor = win_sum / loss_sum if loss_sum > 0 else float('inf')
        loss_rate = 100 - win_rate
        expectancy = (win_rate / 100) * avg_win - (loss_rate / 100) * abs(avg_loss)

        avg_win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        worst_by_symbol = valid.groupby('symbol')[ret_col].min()

        best = valid.nlargest(5, ret_col)[['symbol', 'action', 'score', 'price', ret_col, 'date']].to_dict('records')
        worst = valid.nsmallest(5, ret_col)[['symbol', 'action', 'score', 'price', ret_col, 'date']].to_dict('records')

        return {
            'horizon': horizon,
            'total_with_outcomes': len(valid),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 1),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_win_loss_ratio': round(avg_win_loss_ratio, 2) if avg_win_loss_ratio != float('inf') else 0,
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 999,
            'expectancy': round(expectancy, 2),
            'max_drawdown_per_holding': worst_by_symbol.to_dict(),
            'best_calls': best,
            'worst_calls': worst,
        }

    @staticmethod
    def _empty_performance() -> Dict:
        return {
            'horizon': '', 'total_with_outcomes': 0, 'wins': 0, 'losses': 0,
            'win_rate': 0, 'avg_win': 0, 'avg_loss': 0, 'avg_win_loss_ratio': 0,
            'profit_factor': 0, 'expectancy': 0, 'max_drawdown_per_holding': {},
            'best_calls': [], 'worst_calls': [],
        }

    def get_performance_summary_df(self) -> pd.DataFrame:
        """Return a DataFrame summarising performance across all horizons."""
        rows = []
        _no_data = 'INSUFFICIENT DATA'
        for h in ('7d', '30d', '90d'):
            m = self.get_performance_metrics(h)
            has_data = m['total_with_outcomes'] > 0
            rows.append({
                'Horizon': h,
                'Recommendations': m['total_with_outcomes'] if has_data else _no_data,
                'Wins': m['wins'] if has_data else _no_data,
                'Losses': m['losses'] if has_data else _no_data,
                'Win Rate %': m['win_rate'] if has_data else _no_data,
                'Avg Win %': m['avg_win'] if has_data else _no_data,
                'Avg Loss %': m['avg_loss'] if has_data else _no_data,
                'Win/Loss Ratio': m['avg_win_loss_ratio'] if has_data else _no_data,
                'Profit Factor': m['profit_factor'] if has_data else _no_data,
                'Expectancy %': m['expectancy'] if has_data else _no_data,
            })
        return pd.DataFrame(rows)

    def generate_stability_report(self) -> Dict:
        """
        Generate a report on recommendation stability
        
        Returns:
            Dict with stability metrics
        """
        with self._lock:
            if self.history_df.empty:
                return {
                    'total_recommendations': 0,
                    'unique_stocks': 0,
                    'flip_flops_7d': 0,
                    'flip_flops_14d': 0,
                    'average_hold_days': 0
                }
            _df = self.history_df.copy()
        
        flip_flops_7d = len(self.get_flip_flop_stocks(days=7))
        flip_flops_14d = len(self.get_flip_flop_stocks(days=14))
        
        hold_days = []
        for symbol in _df['symbol'].unique():
            symbol_recs = _df[_df['symbol'] == symbol].sort_values('date').drop_duplicates(subset='date')
            if len(symbol_recs) >= 2:
                _first = pd.to_datetime(symbol_recs.iloc[0]['date'], errors='coerce')
                _last = pd.to_datetime(symbol_recs.iloc[-1]['date'], errors='coerce')
                if not pd.isna(_first) and not pd.isna(_last) and _last > _first:
                    hold_days.append((_last - _first).days)
        
        _avg_hold = round(sum(hold_days) / len(hold_days), 1) if hold_days else None
        
        return {
            'total_recommendations': len(_df),
            'unique_stocks': _df['symbol'].nunique(),
            'flip_flops_7d': flip_flops_7d,
            'flip_flops_14d': flip_flops_14d,
            'average_hold_days': _avg_hold if _avg_hold is not None else 'N/A',
            'oldest_recommendation': _df['date'].min(),
            'latest_recommendation': _df['date'].max()
        }
