"""
Hybrid Scoring Engine v2
========================

Subclass of `HybridOptimizedScoringEngine` that:

1. Calibrates weights from a 7d / 30d Information Coefficient blend (default
   80/20, auto-shifting to 60/40 when 30d sample size >= 100).
2. ALLOWS negative weights so a chronically anti-predictive component is
   actively penalised instead of silently zeroed.
3. Persists to its own file (`data/calibrated_weights_v2.json`) so v1 outputs
   are completely unchanged when v2 is in shadow mode.
4. Computes a hybrid score using v2 weights but otherwise reuses v1's
   per-component scoring so we do not introduce new component computations.

This module is import-time safe: importing it does not change any v1 behaviour.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from hybrid_optimized_scoring import HybridOptimizedScoringEngine


class HybridOptimizedScoringEngineV2(HybridOptimizedScoringEngine):
    """v2 scoring engine. Drop-in replacement for v1; isolated state."""

    _CALIBRATED_WEIGHTS_PATH = 'data/calibrated_weights_v2.json'
    # Tier C2 regime-conditional weight files. When present, the loader prefers
    # the regime-specific file matching the current market regime, then falls
    # back to the global path above. Filenames key off the upper-cased regime.
    _REGIME_WEIGHT_PATH_TEMPLATE = 'data/calibrated_weights_v2_{regime}.json'
    _SUPPORTED_REGIMES = ('BULL', 'BEAR', 'SIDEWAYS')

    DEFAULT_BLEND_7D = 0.80
    BLEND_30D_TRIGGER_SAMPLES = 100
    DEFAULT_BLEND_7D_AT_TRIGGER = 0.60
    MIN_SAMPLES = 50
    # Per-regime calibration uses a relaxed sample-size floor so each regime
    # bucket has a chance of producing weights; global path keeps MIN_SAMPLES.
    MIN_SAMPLES_PER_REGIME = 30
    MIN_ABS_IC = 0.01
    MAX_ABS_SINGLE_WEIGHT = 0.45

    WEIGHT_BOUNDS = {
        'risk_adjustment':      (-0.25, +0.40),
        'fundamental_quality':  (+0.05, +0.30),
        'momentum_technical':   (+0.05, +0.35),
        'volume_strength':      (+0.02, +0.20),
        'multi_timeframe':      (-0.10, +0.25),
        'growth':               (+0.00, +0.20),
        'value':                (+0.00, +0.15),
        'ml_signal':            ( 0.00,  0.00),
    }

    @classmethod
    def calibrate_weights_from_outcomes(cls, history_df: pd.DataFrame,
                                        blend_7d: Optional[float] = None) -> Optional[dict]:
        """Calibrate v2 weights using a 7d/30d IC blend that ALLOWS negatives.

        Algorithm:
            1. Compute Spearman IC of each component vs return_7d and vs return_30d.
            2. Blend per component:  IC_blend = w7 * IC_7d + (1-w7) * IC_30d
               where w7 starts at 0.80 and shifts to 0.60 once 30d sample size
               crosses 100.
            3. Drop components with |IC_blend| below MIN_ABS_IC.
            4. Normalize by sum of |IC| so signed weights sum to a meaningful
               magnitude. Cap any |weight| to MAX_ABS_SINGLE_WEIGHT.
            5. Persist to v2 JSON path with full diagnostics.

        Returns the calibrated weight dict on success, else None.
        """
        from scipy.stats import spearmanr

        if history_df is None or len(history_df) == 0:
            logging.info('[v2 calibrate] empty history_df')
            return None

        ret_7d = pd.to_numeric(history_df.get('return_7d'), errors='coerce') if 'return_7d' in history_df.columns else None
        ret_30d = pd.to_numeric(history_df.get('return_30d'), errors='coerce') if 'return_30d' in history_df.columns else None

        n_7d = int(ret_7d.notna().sum()) if ret_7d is not None else 0
        n_30d = int(ret_30d.notna().sum()) if ret_30d is not None else 0

        if n_7d < cls.MIN_SAMPLES and n_30d < cls.MIN_SAMPLES:
            logging.info(f'[v2 calibrate] insufficient samples: 7d={n_7d}, 30d={n_30d} (need {cls.MIN_SAMPLES})')
            return None

        if blend_7d is None:
            try:
                from config import get_config
                blend_7d = float(get_config().V2_IC_BLEND_7D)
            except Exception:
                blend_7d = cls.DEFAULT_BLEND_7D

        if n_30d >= cls.BLEND_30D_TRIGGER_SAMPLES:
            blend_7d = cls.DEFAULT_BLEND_7D_AT_TRIGGER

        # [v3 Layer 4] component_map keys = weight keys used in calculate_hybrid_score;
        # values = column names in recommendation_history.csv that carry the per-stock
        # component score at recommendation time. The hybrid_* names match the
        # source-of-truth fields in stock_data (set by HybridOptimizedScoringEngine
        # at line 477-487). For backward-compat, fall back to the older flat names
        # (used by an earlier history schema variant) when hybrid_* is missing.
        component_map = {
            'fundamental_quality': ['hybrid_fundamental_quality', 'fundamental_score'],
            'momentum_technical':  ['hybrid_momentum_technical',  'momentum_score'],
            'volume_strength':     ['hybrid_volume_strength',     'volume_composite_score'],
            'multi_timeframe':     ['hybrid_multi_timeframe',     'mtf_composite_score'],
            'ml_signal':           ['hybrid_ml_signal',            'ml_expected_return'],
            'risk_adjustment':     ['hybrid_risk_adjustment',      'risk_adjusted_score'],
            # [Rule 3a] New factors. Columns absent in older history rows -> IC=0
            # and weight skipped at calibration (kept=0 path).
            'growth':              ['hybrid_growth',               'growth_score'],
            'value':               ['hybrid_value',                'value_score'],
        }

        ics_7d: dict = {}
        ics_30d: dict = {}
        ics_blended: dict = {}

        for weight_key, col_candidates in component_map.items():
            if isinstance(col_candidates, str):
                col_candidates = [col_candidates]
            col = next((c for c in col_candidates if c in history_df.columns), None)
            if col is None:
                ics_7d[weight_key] = 0.0
                ics_30d[weight_key] = 0.0
                ics_blended[weight_key] = 0.0
                continue
            comp = pd.to_numeric(history_df[col], errors='coerce')
            ic_7d = 0.0
            ic_30d = 0.0
            if ret_7d is not None:
                joint_7 = pd.concat([comp, ret_7d], axis=1).dropna()
                if len(joint_7) >= 20:
                    corr, _ = spearmanr(joint_7.iloc[:, 0], joint_7.iloc[:, 1])
                    ic_7d = float(corr) if not np.isnan(corr) else 0.0
            if ret_30d is not None:
                joint_30 = pd.concat([comp, ret_30d], axis=1).dropna()
                if len(joint_30) >= 20:
                    corr, _ = spearmanr(joint_30.iloc[:, 0], joint_30.iloc[:, 1])
                    ic_30d = float(corr) if not np.isnan(corr) else 0.0
            ics_7d[weight_key] = round(ic_7d, 4)
            ics_30d[weight_key] = round(ic_30d, 4)
            ics_blended[weight_key] = round(blend_7d * ic_7d + (1.0 - blend_7d) * ic_30d, 4)

        kept = {k: v for k, v in ics_blended.items() if abs(v) >= cls.MIN_ABS_IC}
        if not kept:
            logging.info('[v2 calibrate] no components above MIN_ABS_IC — skipping')
            return None

        total_abs = sum(abs(v) for v in kept.values())
        weights = {k: v / total_abs for k, v in kept.items()}

        for _ in range(5):
            capped = False
            for k in list(weights.keys()):
                lo, hi = cls.WEIGHT_BOUNDS.get(k, (-cls.MAX_ABS_SINGLE_WEIGHT,
                                                     cls.MAX_ABS_SINGLE_WEIGHT))
                if weights[k] < lo:
                    weights[k] = lo
                    capped = True
                elif weights[k] > hi:
                    weights[k] = hi
                    capped = True
            current_abs = sum(abs(v) for v in weights.values())
            if current_abs > 0 and abs(current_abs - 1.0) > 0.01:
                weights = {k: v / current_abs for k, v in weights.items()}
            if not capped:
                break

        weights = {k: round(v, 4) for k, v in weights.items()}
        for k in component_map.keys():
            weights.setdefault(k, 0.0)

        result = {
            'weights': weights,
            'ics_7d': ics_7d,
            'ics_30d': ics_30d,
            'ics_blended': ics_blended,
            'blend_7d': blend_7d,
            'sample_size_7d': n_7d,
            'sample_size_30d': n_30d,
            'updated': datetime.now().isoformat(),
            'engine': 'v2',
        }

        try:
            os.makedirs(os.path.dirname(cls._CALIBRATED_WEIGHTS_PATH) or '.', exist_ok=True)
            with open(cls._CALIBRATED_WEIGHTS_PATH, 'w') as fp:
                json.dump(result, fp, indent=2)
            logging.info(f'[v2 calibrate] saved -> {cls._CALIBRATED_WEIGHTS_PATH}; weights={weights}')
        except Exception as e:
            logging.warning(f'[v2 calibrate] failed to persist: {e}')

        return weights

    @classmethod
    def calibrate_weights_per_regime_from_outcomes(cls, history_df: pd.DataFrame) -> dict:
        """Tier C2 - regime-conditional v2 weight calibration.

        Splits `history_df` by the `regime` column and runs the standard
        signed-weight IC calibration on each subset, persisting the result to
        `data/calibrated_weights_v2_{REGIME}.json`. The runtime loader will pick
        the matching file based on the live market regime; absence of a regime
        file falls back to the global file written by
        `calibrate_weights_from_outcomes`.

        Returns a dict mapping regime -> weights (or None when a regime had
        insufficient data to produce a result).
        """
        out: dict = {}
        if history_df is None or len(history_df) == 0:
            return out
        if 'regime' not in history_df.columns:
            logging.info('[v2 per-regime] no regime column in history_df')
            return out

        regimes = history_df['regime'].astype(str).str.upper().fillna('UNKNOWN')
        # Lower the sample floor temporarily for the per-regime path to give
        # smaller buckets a chance. The signed-weight math is unchanged.
        prev_min = cls.MIN_SAMPLES
        try:
            cls.MIN_SAMPLES = cls.MIN_SAMPLES_PER_REGIME
            for rg in cls._SUPPORTED_REGIMES:
                mask = regimes == rg
                sub = history_df[mask]
                if len(sub) < cls.MIN_SAMPLES_PER_REGIME:
                    logging.info(f'[v2 per-regime] {rg}: n={len(sub)} below floor '
                                 f'{cls.MIN_SAMPLES_PER_REGIME} - skipping')
                    out[rg] = None
                    continue
                target_path = cls._REGIME_WEIGHT_PATH_TEMPLATE.format(regime=rg)
                # Re-route the persist path for this call only.
                prev_path = cls._CALIBRATED_WEIGHTS_PATH
                try:
                    cls._CALIBRATED_WEIGHTS_PATH = target_path
                    weights = cls.calibrate_weights_from_outcomes(sub)
                    out[rg] = weights
                finally:
                    cls._CALIBRATED_WEIGHTS_PATH = prev_path
        finally:
            cls.MIN_SAMPLES = prev_min
        return out

    def _load_calibrated_weights(self, regime_hint: str = None):
        """v2 loader. When a regime hint is supplied, prefer the regime-specific
        weights file `data/calibrated_weights_v2_{REGIME}.json`; fall back to
        the global file `data/calibrated_weights_v2.json`. Both files have a
        3-day TTL. Signed weights are allowed."""
        candidates = []
        if regime_hint:
            rg = str(regime_hint).upper().strip()
            if rg in self._SUPPORTED_REGIMES:
                candidates.append(
                    (rg, self._REGIME_WEIGHT_PATH_TEMPLATE.format(regime=rg))
                )
        candidates.append(('GLOBAL', self._CALIBRATED_WEIGHTS_PATH))

        # [Stale-weights fix] TTL extended from 3 days to 14 days. The 3-day
        # window caused silent failures: if calibration wasn't re-run for a
        # weekend + 1 weekday, the file expired and the engine quietly fell
        # back to v1 regime defaults - producing v2 == v1 scores with no error.
        # 14 days lets weekly recalibration cover the gap; ages > 7d emit a
        # warning so the operator knows recalibration is overdue.
        _STALE_AFTER_DAYS = 14
        _WARN_AFTER_DAYS = 7
        for label, path in candidates:
            try:
                if not os.path.exists(path):
                    continue
                with open(path) as fp:
                    data = json.load(fp)
                updated = datetime.fromisoformat(data['updated'])
                age_days = (datetime.now() - updated).days
                if age_days > _STALE_AFTER_DAYS:
                    logging.warning(
                        f'[v2] {label} weights at {path} are {age_days}d old '
                        f'(>{_STALE_AFTER_DAYS}d TTL) - skipping. Run '
                        f'scripts/calibrate_v2_weights.py to refresh.'
                    )
                    continue
                w = data.get('weights')
                if w:
                    log_fn = logging.warning if age_days > _WARN_AFTER_DAYS else logging.info
                    log_fn(
                        f'[v2] loaded {label} calibrated weights from {path} '
                        f'(age={age_days}d): {w}'
                    )
                    return w
            except Exception as _load_err:
                logging.debug(f'[v2] could not load {path}: {_load_err}')
                continue
        logging.warning(
            '[v2] NO calibrated weights loaded - v2 will silently fall back to '
            'v1 regime defaults. Run scripts/calibrate_v2_weights.py to fix.'
        )
        return None
