#!/usr/bin/env python3
"""
Configuration Management for Enhanced Stock Analysis
Centralized configuration for all analysis parameters
"""

import os
import json
import threading
from dataclasses import dataclass, fields, asdict
from typing import Dict, List, Optional

@dataclass
class AnalysisConfig:
    """Configuration class for stock analysis parameters"""
    
    # Performance Settings
    # [perf] Workers for the per-stock thread pool. Bumped from 3 -> 8 once
    # caching dominated the workload: with `_yf_ticker_with_retry` already
    # throttling per-thread network calls, 8 stays well below any sane API
    # limit. Override via --workers on the CLI or config.json.
    MAX_WORKERS: int = 8
    BATCH_SIZE: int = 5
    TIMEOUT_SECONDS: int = 120
    RETRY_ATTEMPTS: int = 3
    
    # Sentiment adjustment (capped at ±3 pts, confidence-weighted)
    ENABLE_SENTIMENT_ADJUSTMENT: bool = True
    
    # Caching Settings
    CACHE_ENABLED: bool = True
    CACHE_EXPIRY_HOURS: int = 4
    CACHE_DIR: str = "data/cache"
    
    # Scoring Weights (validation-only; hybrid_optimized_scoring.py uses regime-adaptive weights)
    FUNDAMENTAL_WEIGHT: float = 0.4
    TECHNICAL_WEIGHT: float = 0.3
    UNDERVALUATION_WEIGHT: float = 0.3
    
    # Undervaluation Thresholds (reserved for future per-metric scoring; not consumed at runtime)
    PE_EXCELLENT: float = 10
    PE_GOOD: float = 15
    PE_AVERAGE: float = 20
    PB_EXCELLENT: float = 1.0
    PB_GOOD: float = 1.5
    DIVIDEND_EXCELLENT: float = 4.0
    
    # Risk Categories (reserved for future risk bucketing; not consumed at runtime)
    VOLATILITY_LOW: float = 15
    VOLATILITY_MODERATE: float = 25
    VOLATILITY_HIGH: float = 35
    
    # Recommendation Thresholds
    STRONG_BUY_THRESHOLD: float = 70
    BUY_THRESHOLD: float = 60
    HOLD_THRESHOLD: float = 50
    SELL_THRESHOLD: float = 40
    UNDERVALUED_THRESHOLD: float = 65
    
    # Data Sources
    NSE_SUFFIX: str = ".NS"
    BSE_SUFFIX: str = ".BO"  # reserved for BSE support
    DEFAULT_EXCHANGE: str = "NSE"  # reserved for multi-exchange support
    
    # Portfolio Settings
    DEFAULT_PORTFOLIO_AMOUNT: float = 100000
    MAX_PORTFOLIO_POSITIONS: int = 15
    MIN_ALLOCATION_PERCENTAGE: float = 2.0
    MAX_SINGLE_STOCK_WEIGHT: float = 20.0  # DEPRECATED: allocation engine uses per-cap-tier limits. Changing this has NO effect.

    # Allocation Thresholds
    MIN_INVESTMENT_PER_STOCK: float = 3000
    MAX_ALLOCATION_PCT: float = 0.05  # DEPRECATED: allocation engine uses per-cap-tier limits. Changing this has NO effect.
    TARGET_PORTFOLIO_SIZE: int = 23
    SECTOR_CAP: int = 10
    CATEGORY_SECTOR_CAP: int = 5
    SECTOR_REDUCE_MIN_SCORE: float = 45.0
    CORE_CONCENTRATION_THRESHOLD: float = 0.40

    # Exit Strategy Thresholds
    EXIT_TOP_PCT: float = 0.30
    EXIT_BOTTOM_PCT: float = 0.20
    REBALANCE_PROFIT_THRESHOLD: float = 0.05
    PROFIT_BOOKING_THRESHOLD: float = 0.20
    # High-score profitable runners: cap exhaustion at partial book unless
    # exhaustion_score reaches EXHAUSTION_FULL_EXIT_MIN_SCORE (RSI extreme + volume fade).
    EXHAUSTION_QUALITY_SCORE_FLOOR: float = 58.0
    EXHAUSTION_FULL_EXIT_MIN_SCORE: float = 80.0
    # Losses worse than this bypass the graduated conviction gate (full SELL).
    GRADUATED_EXIT_BYPASS_LOSS_PCT: float = -0.08

    # VMQ (Validated Momentum-Quality): pattern-derived entry/validation (no IC gate).
    VMQ_ENABLED: bool = True
    VMQ_ENTRY_SCORE_MIN: float = 0.0  # 0 = oracle+turbo gates only (no v1 score floor)
    VMQ_ENTRY_MOM_FLOOR: float = 45.0
    VMQ_VALUE_TRAP_FUND_MIN: float = 75.0
    VMQ_VALUE_TRAP_MOM_MAX: float = 55.0
    VMQ_V1_V2_GAP_MAX: float = 15.0
    VMQ_MAX_NEW_PER_WEEK: int = 3
    VMQ_REQUIRE_V2_BUY: bool = False
    VMQ_V2_BUY_THRESHOLD: float = 60.0
    VMQ_REQUIRE_TURBO_PASS: bool = True
    VMQ_TURBO_MIN: float = 65.0
    VMQ_VALIDATION_FAIL_3D: float = -2.0
    VMQ_VALIDATION_FAIL_5D: float = -1.0
    VMQ_SWING_STOP_PCT: float = -5.0
    VMQ_HARD_STOP_PCT: float = -8.0
    VMQ_TRAIL_STOP_PCT: float = 0.08
    # Day-3/5 early validation — OFF by default (production). Hard/swing/trail remain ON.
    # Set VMQ_DAY3_ENABLED=true + VMQ_DAY3_ACTIVE_REGIMES for bear-only experiments.
    VMQ_DAY3_ENABLED: bool = False
    VMQ_DAY3_REGIME_GATED: bool = True
    VMQ_DAY3_ACTIVE_REGIMES: str = 'bear,high_vol'
    VMQ_DAY3_VIX_MIN: float = 25.0
    # Skip day-3/5 when winner / trend intact (reduces whipsaw vs flat P&L>0 skip).
    VMQ_DAY3_SMART_SKIP: bool = True
    VMQ_DAY3_SKIP_PNL_MIN: float = 5.0
    VMQ_DAY3_SKIP_MTF_MIN: float = 52.0
    VMQ_DAY3_SKIP_IF_TURBO_PASS: bool = True
    # Day-3/5 validation only for recent NEW POSITION entries (May-churn window).
    VMQ_VALIDATION_MAX_DAYS: int = 21
    VMQ_MAX_EXITS_PER_RUN: int = 5
    # Bottom-20% rebalance: full SELL only below this profit; else CONSIDER.
    REBALANCE_SELL_MAX_PROFIT_PCT: float = 0.03

    # Entry driver: turbo_mtf = timing-first (v2 + MTF + 3d confirm); vmq_v1 = legacy score gate.
    ENTRY_DRIVER: str = 'turbo_mtf'
    TURBO_ENTRY_V2_MIN: float = 60.0
    TURBO_ENTRY_MTF_MIN: float = 55.0
    TURBO_ENTRY_MOM_MIN: float = 50.0
    ENTRY_V1_SCORE_FLOOR: float = 55.0
    ENTRY_CONFIRM_3D_MIN_RET: float = 0.0
    ENTRY_CONFIRM_3D_STRONG_RET: float = 2.0
    # Extended-entry guards (ATGL-style chase / rejection after spike).
    TURBO_ENTRY_RSI_MAX: float = 75.0
    TURBO_ENTRY_RSI_HARD_BLOCK: float = 75.0
    TURBO_ENTRY_CHASE_5D_MAX: float = 15.0
    TURBO_ENTRY_REJECTION_WICK_PCT: float = 8.0

    # Path 2 — Balanced strategy (VMQ sells + soft rank trims + breakout lane).
    PATH2_BALANCED_ENABLED: bool = True
    PATH2_SOFT_SELL_PNL_MIN: float = -0.03
    PATH2_SOFT_SELL_PNL_MAX: float = 0.03
    PATH2_CONSIDER_TRIM_PCT: float = 0.25
    BREAKOUT_RADAR_ENABLED: bool = True
    BREAKOUT_FAST_TRACK_ENABLED: bool = True
    BREAKOUT_MAX_NEW_PER_WEEK: int = 1
    BREAKOUT_FAST_TRACK_SIZE_MULT: float = 0.5
    BREAKOUT_IGNITE_VOL_RATIO: float = 2.5
    BREAKOUT_IGNITE_1D_MIN: float = 2.5
    BREAKOUT_COIL_DIST_20D_MAX: float = 4.0

    EMERGENCY_EXIT_LOSS: float = -0.30
    EMERGENCY_EXIT_SCORE: float = 45.0

    # Tiered Emergency Exit (sliding scale replaces hard AND gate)
    EMERGENCY_TIER_1_LOSS: float = -0.25
    EMERGENCY_TIER_2_LOSS: float = -0.20
    EMERGENCY_TIER_2_SCORE: float = 50.0
    EMERGENCY_TIER_3_LOSS: float = -0.15
    EMERGENCY_TIER_3_SCORE: float = 45.0

    # ATR-based Stop Loss
    STOP_LOSS_ATR_MULTIPLIER: float = 2.0
    STOP_LOSS_FALLBACK_PCT: float = 0.08

    # Regime Exposure
    BEAR_EXPOSURE: float = 0.50
    SIDEWAYS_EXPOSURE: float = 0.85
    BULL_EXPOSURE: float = 1.00

    # Score Smoothing
    SCORE_SMOOTHING_WEIGHT: float = 0.55
    SCORE_SMOOTHING_WEIGHT_BEAR: float = 0.50
    SCORE_SMOOTHING_WEIGHT_DOWN: float = 0.75
    SCORE_SMOOTHING_WEIGHT_UP: float = 0.45
    SCORE_SMOOTHING_MAX_AGE_DAYS: int = 3

    # Recommendation Hysteresis (prevents flip-flops at threshold boundaries)
    HYSTERESIS_BUFFER: float = 3.0
    HYSTERESIS_PROXIMITY_BOOST: float = 1.5

    # v3 Layer 3 — unidirectional hysteresis. Default False keeps the bidirectional
    # buffer (legacy F-10 behavior: sticky in BOTH directions). When True, the
    # buffer ONLY resists upgrades (entering a higher tier) — downgrades fall
    # through immediately. Eliminates the "anchored in winning tier while losing"
    # pathology identified in the prior ROI-drawdown analysis. Shadow toggle for
    # v3 ablation; will be enabled after paper-trading review.
    UNIDIRECTIONAL_HYSTERESIS: bool = False

    # ML Tag Control (disabled until model accuracy > 60%)
    ML_TAG_IN_RECOMMENDATION: bool = False

    # Sector Cap Enforcement
    SECTOR_CAP_ENFORCE_HOLDINGS: bool = True
    SECTOR_CAP_SCORE_OVERRIDE: float = 75.0

    # Liquidity Filter
    MIN_AVG_DAILY_VOLUME: int = 50000
    ILLIQUID_SCORE_PENALTY: float = 15.0

    # Universe Filter (Phase 0): exclude ETFs/REITs/InvITs and enforce ADV minimum.
    # Permissive: missing avg_volume or current_price never drops a symbol.
    EXCLUDE_ETFS: bool = True
    MIN_ADV_CRORES: float = 10.0

    # Hard Stop Loss (Phase 3b): unified stop-loss policy.
    # HARD_STOP triggers SELL at -7% loss unless score>=65 AND no recent bearish AND RSI>40.
    # SOFT_STOP triggers REDUCE at -10% loss regardless.
    HARD_STOP_PCT: float = -0.07
    HARD_STOP_OVERRIDE_SCORE: float = 65.0
    SOFT_STOP_PCT: float = -0.10

    # v3 Layer 3 — pure-P&L hard-stop mode (action-decoupled safety layer).
    # When True, _evaluate_hard_stop ignores the score>=65 / RSI>40 / not-bearish
    # override — losing positions exit on P&L threshold breach alone.
    # Default False preserves the prior session's "hard stop=-7% with override"
    # locked tunable. Flip to True for v3 ablation / paper-trading.
    HARD_STOP_PURE_PNL: bool = False

    # v3 Layer 3 / Phase 1 — composite paper-trading flag. When True, both
    # individual v3 toggles (HARD_STOP_PURE_PNL, UNIDIRECTIONAL_HYSTERESIS)
    # behave as if set to True at runtime, regardless of their own values.
    # Single opt-in/opt-out for the entire v3 Layer 3 behaviour bundle.
    # Default False keeps the locked-tunable production behaviour.
    PAPER_TRADING_MODE: bool = False

    # [Contract Rule 7] — Macro inputs are limited to Nifty regime + India VIX.
    # The cross-asset crisis overlay (war / oil / panic / USD / crude) is kept
    # on disk for ablation but disabled by default to comply with the operating
    # contract. Flip to True to opt back in for diagnostic comparisons.
    ENABLE_CRISIS_DETECTOR: bool = False

    # [Contract Rule 6b] — Trailing stop on peak price. We persist a per-symbol
    # peak in booking_history.json each run; once price falls below
    # `peak * (1 - TRAILING_STOP_PCT)` AND the position is in profit, we emit
    # a TRAILING_STOP exit signal. BEAR regime tightens the trail to 10% via
    # TRAILING_STOP_BEAR_PCT. Set TRAILING_STOP_PCT to 0 to disable entirely.
    TRAILING_STOP_PCT: float = 0.15
    TRAILING_STOP_BEAR_PCT: float = 0.10

    # [Contract Rule 5] — Profit-booking 20% rotation rule. Fires when a
    # position is up >= 15% AND its v2 score has dropped >= 10pts from its
    # peak v2 reading. Recommended rotation target is the highest-v2
    # non-held candidate from today's universe.
    SCALE_OUT_PROFIT_THRESHOLD: float = 0.15  # 15% gain floor
    SCALE_OUT_V2_DROP_PTS: float = 10.0       # peak v2 drop required
    SCALE_OUT_FRACTION: float = 0.20          # liquidate 20% of position

    # Rotation friction (Phase 3c): minimum score advantage for capital rotation.
    ROTATION_FRICTION_POINTS: float = 5.0

    # [Investor-audit Q127] Recent-BUY Minimum-Hold Cooldown.
    # When the system issues a SELL/WEAK_SELL/REDUCE on a position that was a
    # NEW_POSITION/BUY within REGIME_FLIP_COOLDOWN_DAYS, the SELL is suppressed
    # and overridden to HOLD. Prevents whipsaws driven by regime-classifier
    # oscillation (SIDEWAYS<->BEAR within hours), bottom-20% ranking artefacts,
    # and same-day score noise.
    # Variable names retain the REGIME_FLIP_ prefix for backward compatibility,
    # but the trigger is no longer regime-dependent (Round 23a, 2026-05-18 PM).
    # EXCEPTIONS (still allow SELL):
    #   - P&L below REGIME_FLIP_HARD_STOP_PCT (true loss, not artefact)
    #   - V2 score below REGIME_FLIP_V2_COLLAPSE for REGIME_FLIP_V2_STREAK runs
    #   - Hard-stop tier already EMERGENCY/HARD_STOP/THESIS_BREAK/TRAILING_STOP
    REGIME_FLIP_COOLDOWN_ENABLED: bool = True
    REGIME_FLIP_COOLDOWN_DAYS: int = 7
    REGIME_FLIP_HARD_STOP_PCT: float = -0.10
    REGIME_FLIP_V2_COLLAPSE: float = 30.0
    REGIME_FLIP_V2_STREAK: int = 2

    DUAL_STRATEGY_PROFILES = {
        'turbo_mtf': {
            'label': 'TURBO MTF [PRIMARY]',
            'rebalance': 'weekly',
            'weights': {
                'momentum_technical': 0.10, 'volume_strength': 0.25,
                'multi_timeframe': 0.40, 'fundamental_quality': 0.05,
                'risk_adjustment': 0.0, 'growth': 0.0, 'value': 0.0,
                'ml_signal': 0.0,
            },
        },
        'monthly_stable_balanced': {
            'label': 'MONTHLY (Stable Balanced)',
            'rebalance': 'monthly',
            'weights': {
                'momentum_technical': 0.20, 'volume_strength': 0.10,
                'multi_timeframe': 0.20, 'fundamental_quality': 0.25,
                'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.07,
                'ml_signal': 0.0,
            },
        },
    }

    # V2 Scoring Engine shadow mode (Phase 1/2): when True, v2 score is computed
    # alongside v1 but does NOT drive actions. Promotion is gated by data/v2_promotion_status.json.
    V2_SHADOW_MODE: bool = True
    V2_PROMOTION_DATE: str = ""
    V2_IC_BLEND_7D: float = 0.80
    # Exclude forced-exit rows from IC calibration (improves rank-surface picking IC).
    V2_CALIBRATE_RANK_SURFACE_ONLY: bool = True
    # When 7d and 30d component IC disagree in sign, trust 30d for stock-picking horizon.
    V2_IC_DISAGREE_USE_30D: bool = True

    # Stock-picking rank for NEW candidates / funding pool.
    PICKING_RANK_DRIVER: str = 'quality_lvm'  # quality_lvm | lowvol_mom | flow_quality | turbo_mtf | auto | v2_synth

    # Oracle recovery (pick / time / exit separation).
    ORACLE_PICK_METRIC: str = 'quality_lvm'  # quality_lvm | lowvol_mom | fq_score | volume_only | fq_adapt
    ORACLE_WATCHLIST_PCT: float = 0.20
    ORACLE_ROLLING_SWITCH_ENABLED: bool = True
    ORACLE_IC_SWITCH_WINDOW_DAYS: int = 21
    # fq+turbo NEW allowed while V2_SHADOW_MODE keeps v2 rank off actions.
    ORACLE_ENTRY_LIVE: bool = True
    ORACLE_PAUSE_NEW_ON_HOLD_SHADOW: bool = True
    # Holdings exit rank + sector trim use picking_rank (fq/turbo), not v1 overall_score.
    ORACLE_STACK_ALIGN: bool = True
    ORACLE_PAUSE_NEW_IN_BEAR: bool = True
    ORACLE_DISABLE_RANK_SELL_ON_CORE: bool = True
    # When stack aligned, disable bottom-20% rank-SELL on all sleeves (VMQ exits only).
    ORACLE_DISABLE_RANK_SELL_ALL: bool = True

    # QMST master switch — layer labels, history fields, report badge.
    QMST_ENABLED: bool = True
    QMST_STATUS_BADGE: str = 'QMST-BETA'  # QMST-BETA | QMST-VALIDATED | QMST-DEMOTE
    # Pick quality floors on oracle watchlist — OFF until backtest certifies (scripts/backtest_qmst_pick_gates.py).
    QMST_PICK_GATES_ENABLED: bool = False
    QMST_PICK_FQ_MIN: float = 48.0
    QMST_PICK_RK_MIN: float = 42.0
    QMST_PICK_VL_MIN: float = 45.0
    QMST_PICK_VL_GATE: bool = False
    # Optional volume-strength floor on NEW/INCREASE turbo gate (0 = off).
    TURBO_ENTRY_VS_MIN: float = 0.0
    # Shadow NSE bhavcopy delivery/turnover columns (fq_score_nse); does not drive pick rank.
    ORACLE_USE_NSE_FLOW_SHADOW: bool = True
    ORACLE_DIST_20D_HIGH_FILTER: bool = True
    ORACLE_DIST_20D_HIGH_MIN_PCT: float = -12.0
    ORACLE_MAX_NEW_PER_FORTNIGHT: int = 3

    # LowVol→Mom strategy parameters (when ORACLE_PICK_METRIC=lowvol_mom).
    LVM_LOWVOL_POOL_SIZE: int = 40
    LVM_TOP_N: int = 20
    # Monthly capital deployment: equal-weight only the top LVM_FUND_N names from the screen list.
    LVM_FUND_N: int = 12
    LVM_REQUIRE_ABOVE_SMA50: bool = True
    LVM_STOP_PCT: float = -10.0
    LVM_SECTOR_CAP: int = 3
    LVM_BYPASS_TURBO_GATE: bool = True
    LVM_QUALITY_POOL_SIZE: int = 30
    LVM_QUALITY_MIN_ROE: float = 10.0
    LVM_QUALITY_MAX_DEBT_TO_EQUITY: float = 150.0
    LVM_QUALITY_MIN_EARNINGS_GROWTH: float = -100.0
    LVM_QUALITY_EXCLUDE_VALUE_TRAPS: bool = True
    LVM_QUALITY_REQUIRE_REAL_PIT: bool = True

    # Upstox — market data only (no holdings/orders). Token in .env only.
    UPSTOX_DATA_ENABLED: bool = False
    FQ_LAMBDA_DEFAULT: float = 0.5
    FQ_LAMBDA_LOW: float = 0.3
    FQ_LAMBDA_MID: float = 0.5
    FQ_LAMBDA_HIGH: float = 0.8
    FQ_MOM_MID_THRESHOLD: float = 50.0
    FQ_MOM_HIGH_THRESHOLD: float = 65.0
    CALIBRATION_MODE: str = 'diagnostic'  # diagnostic | production

    # Cache Retention
    CACHE_MAX_AGE_DAYS: int = 7

    # Extreme Volatility
    MAX_SAFE_VOLATILITY: float = 80.0

    # Rate Limiting (consolidated from src/config.py — CB-05; REQUEST_DELAY used by nse_scraper)
    REQUEST_DELAY: float = 0.5
    REQUESTS_PER_MIN: int = 20  # reserved; yfinance wrapper uses internal rate control
    # MTF weekly/monthly yfinance calls (separate from bundle 5y fetch storm)
    MTF_YFINANCE_DELAY_SEC: float = 0.35
    MTF_YFINANCE_RETRY_ATTEMPTS: int = 3
    RETRY_LIMIT: int = 3  # reserved; analyzer uses RETRY_ATTEMPTS
    RETRY_BACKOFF: int = 2  # reserved

    # Market Cap Thresholds in INR crores (consolidated from src/config.py — CB-05)
    MARKET_CAP_MEGA: int = 200000
    MARKET_CAP_LARGE: int = 50000
    MARKET_CAP_MID: int = 10000
    MARKET_CAP_SMALL: int = 2000

    # File Paths
    REPORTS_DIR: str = "reports"
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"
    TEMPLATES_DIR: str = "templates"
    
    # Default Stock Lists
    NIFTY_50_STOCKS: List[str] = None
    
    def __post_init__(self):
        """Initialize default stock lists"""
        self.NIFTY_50_STOCKS = [
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", 
            "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", 
            "BAJFINANCE", "ASIANPAINT", "MARUTI", "HCLTECH", "ULTRACEMCO", 
            "SUNPHARMA", "WIPRO", "TITAN", "NESTLEIND", "TECHM", "BAJAJFINSV", 
            "POWERGRID", "NTPC", "COALINDIA", "HINDALCO", "TATASTEEL", 
            "JSWSTEEL", "INDUSINDBK", "HEROMOTOCO", "BAJAJ-AUTO", "M&M", 
            "SHRIRAMFIN", "TATACONSUM", "DIVISLAB", "BRITANNIA", "DRREDDY", 
            "CIPLA", "APOLLOHOSP", "ADANIENT", "ADANIPORTS", "BPCL", 
            "GRASIM", "EICHERMOT", "TATAMOTORS", "UPL", "LTIM", "ONGC"
        ]
        
        # Create required directories
        for directory in [self.REPORTS_DIR, self.DATA_DIR, self.LOGS_DIR, 
                         self.TEMPLATES_DIR, self.CACHE_DIR]:
            os.makedirs(directory, exist_ok=True)

# Global configuration instance
CONFIG = AnalysisConfig()
_CONFIG_LOCK = threading.Lock()

def get_config() -> AnalysisConfig:
    """Get the global configuration instance"""
    return CONFIG

def update_config(**kwargs) -> None:
    """Update configuration parameters (thread-safe). Validates after mutation; rolls back on failure."""
    global CONFIG
    with _CONFIG_LOCK:
        _snapshot = {k: getattr(CONFIG, k) for k in kwargs if hasattr(CONFIG, k)}
        for key, value in kwargs.items():
            if hasattr(CONFIG, key):
                setattr(CONFIG, key, value)
            else:
                print(f"Warning: Unknown configuration parameter: {key}")
        try:
            _validate_config(CONFIG)
        except ValueError:
            for k, v in _snapshot.items():
                setattr(CONFIG, k, v)
            raise

_VALIDATION_RULES: dict = {
    'STRONG_BUY_THRESHOLD': (float, 50, 100),
    'BUY_THRESHOLD': (float, 30, 100),
    'HOLD_THRESHOLD': (float, 10, 90),
    'SECTOR_CAP': (int, 1, 50),
    'CATEGORY_SECTOR_CAP': (int, 1, 20),
    'MAX_WORKERS': (int, 1, 20),
    'BATCH_SIZE': (int, 1, 50),
    'TIMEOUT_SECONDS': (int, 10, 600),
    'RETRY_ATTEMPTS': (int, 0, 10),
    'CACHE_EXPIRY_HOURS': (int, 1, 168),
    'CACHE_MAX_AGE_DAYS': (int, 1, 30),
    'SCORE_SMOOTHING_WEIGHT': (float, 0.0, 1.0),
    'SCORE_SMOOTHING_WEIGHT_DOWN': (float, 0.0, 1.0),
    'SCORE_SMOOTHING_WEIGHT_UP': (float, 0.0, 1.0),
    'SCORE_SMOOTHING_WEIGHT_BEAR': (float, 0.0, 1.0),
    'SCORE_SMOOTHING_MAX_AGE_DAYS': (int, 1, 14),
    'HYSTERESIS_BUFFER': (float, 0.0, 10.0),
    'HYSTERESIS_PROXIMITY_BOOST': (float, 0.0, 5.0),
    'BEAR_EXPOSURE': (float, 0.0, 1.0),
    'SIDEWAYS_EXPOSURE': (float, 0.0, 1.0),
    'BULL_EXPOSURE': (float, 0.0, 1.0),
    'FUNDAMENTAL_WEIGHT': (float, 0.0, 1.0),
    'TECHNICAL_WEIGHT': (float, 0.0, 1.0),
    'UNDERVALUATION_WEIGHT': (float, 0.0, 1.0),
    'MAX_SINGLE_STOCK_WEIGHT': (float, 1.0, 100.0),
    'MAX_ALLOCATION_PCT': (float, 0.01, 1.0),
    'MIN_ALLOCATION_PERCENTAGE': (float, 0.0, 50.0),
    'TARGET_PORTFOLIO_SIZE': (int, 1, 100),
    'MAX_PORTFOLIO_POSITIONS': (int, 1, 100),
    'DEFAULT_PORTFOLIO_AMOUNT': (float, 1000, 1e9),
    'SECTOR_REDUCE_MIN_SCORE': (float, 0, 100),
    'MAX_SAFE_VOLATILITY': (float, 10, 200),
    'ILLIQUID_SCORE_PENALTY': (float, 0, 50),
    'MIN_AVG_DAILY_VOLUME': (int, 10_000, 10_000_000),
    'PROFIT_BOOKING_THRESHOLD': (float, 0.0, 1.0),
    'EXHAUSTION_QUALITY_SCORE_FLOOR': (float, 0.0, 100.0),
    'EXHAUSTION_FULL_EXIT_MIN_SCORE': (float, 0.0, 100.0),
    'GRADUATED_EXIT_BYPASS_LOSS_PCT': (float, -1.0, 0.0),
    'VMQ_ENTRY_SCORE_MIN': (float, 0.0, 100.0),
    'VMQ_ENTRY_MOM_FLOOR': (float, 0.0, 100.0),
    'VMQ_MAX_NEW_PER_WEEK': (int, 1, 20),
    'VMQ_VALIDATION_FAIL_3D': (float, -20.0, 10.0),
    'VMQ_VALIDATION_FAIL_5D': (float, -20.0, 10.0),
    'VMQ_DAY3_VIX_MIN': (float, 10.0, 80.0),
    'VMQ_DAY3_SKIP_PNL_MIN': (float, 0.0, 50.0),
    'VMQ_DAY3_SKIP_MTF_MIN': (float, 0.0, 100.0),
    'QMST_PICK_FQ_MIN': (float, 0.0, 100.0),
    'QMST_PICK_RK_MIN': (float, 0.0, 100.0),
    'QMST_PICK_VL_MIN': (float, 0.0, 100.0),
    'VMQ_SWING_STOP_PCT': (float, -30.0, 0.0),
    'VMQ_HARD_STOP_PCT': (float, -30.0, 0.0),
    'VMQ_TRAIL_STOP_PCT': (float, 0.01, 0.30),
    'REBALANCE_PROFIT_THRESHOLD': (float, 0.0, 1.0),
    'SELL_THRESHOLD': (float, 0, 100),
    'EMERGENCY_EXIT_LOSS': (float, -1.0, 0.0),
    'EMERGENCY_EXIT_SCORE': (float, 0, 100),
    'MIN_ADV_CRORES': (float, 0.0, 1000.0),
    'HARD_STOP_PCT': (float, -1.0, 0.0),
    'HARD_STOP_OVERRIDE_SCORE': (float, 0, 100),
    'SOFT_STOP_PCT': (float, -1.0, 0.0),
    'ROTATION_FRICTION_POINTS': (float, 0.0, 50.0),
    'V2_IC_BLEND_7D': (float, 0.0, 1.0),
    'TURBO_ENTRY_VS_MIN': (float, 0.0, 100.0),
}

def _validate_config(cfg: 'AnalysisConfig') -> None:
    """Validate config values are within acceptable ranges. Raises ValueError on failure."""
    errors = []
    for key, (expected_type, lo, hi) in _VALIDATION_RULES.items():
        if not hasattr(cfg, key):
            continue
        val = getattr(cfg, key)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            errors.append(f"{key}: expected numeric, got {type(val).__name__}")
            continue
        if val < lo or val > hi:
            errors.append(f"{key}={val} out of range [{lo}, {hi}]")
    thr_sb = getattr(cfg, 'STRONG_BUY_THRESHOLD', 70)
    thr_b = getattr(cfg, 'BUY_THRESHOLD', 60)
    thr_h = getattr(cfg, 'HOLD_THRESHOLD', 50)
    thr_s = getattr(cfg, 'SELL_THRESHOLD', 40)
    if not (thr_sb > thr_b > thr_h > thr_s):
        errors.append(f"Thresholds must satisfy STRONG_BUY({thr_sb}) > BUY({thr_b}) > HOLD({thr_h}) > SELL({thr_s})")
    _fw = getattr(cfg, 'FUNDAMENTAL_WEIGHT', 0.4)
    _tw = getattr(cfg, 'TECHNICAL_WEIGHT', 0.3)
    _uw = getattr(cfg, 'UNDERVALUATION_WEIGHT', 0.3)
    if _fw < 0 or _tw < 0 or _uw < 0:
        errors.append(f"Scoring weights must be non-negative: F={_fw}, T={_tw}, U={_uw}")
    _w_sum = _fw + _tw + _uw
    if abs(_w_sum - 1.0) > 0.01:
        errors.append(f"Scoring weights must sum to 1.0, got {_w_sum:.3f} (FUNDAMENTAL+TECHNICAL+UNDERVALUATION)")
    fund_n = int(getattr(cfg, 'LVM_FUND_N', 12))
    top_n = int(getattr(cfg, 'LVM_TOP_N', 20))
    if fund_n > top_n:
        errors.append(f"LVM_FUND_N={fund_n} cannot exceed LVM_TOP_N={top_n}")
    if errors:
        raise ValueError("[CONFIG] Validation failed:\n  " + "\n  ".join(errors))


def load_config_from_file(file_path: str = 'config.json') -> None:
    """Load configuration from a JSON file and update the global CONFIG instance.
    Validates inside the lock; rolls back to snapshot on validation failure.
    """
    global CONFIG
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _CONFIG_LOCK:
            valid_fields = {fld.name for fld in fields(CONFIG)}
            _snapshot = {k: getattr(CONFIG, k) for k in valid_fields}
            for key, value in data.items():
                if key in valid_fields:
                    setattr(CONFIG, key, value)
            try:
                _validate_config(CONFIG)
            except ValueError:
                for k, v in _snapshot.items():
                    setattr(CONFIG, k, v)
                raise
        print(f"[CONFIG] Loaded and validated settings from {file_path}")
    except ValueError as ve:
        print(f"[CONFIG] {ve}")
        raise
    except Exception as e:
        print(f"[CONFIG] Warning: could not load {file_path}: {e}")

def save_config_to_file(file_path: str = 'config.json') -> None:
    """Serialize current CONFIG to a JSON file."""
    try:
        with _CONFIG_LOCK:
            data = {}
            for fld in fields(CONFIG):
                val = getattr(CONFIG, fld.name)
                if isinstance(val, list) and fld.name == 'NIFTY_50_STOCKS':
                    continue
                try:
                    json.dumps(val)
                    data[fld.name] = val
                except (TypeError, ValueError):
                    pass
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[CONFIG] Saved settings to {file_path}")
    except Exception as e:
        print(f"[CONFIG] Warning: could not save {file_path}: {e}")


# Auto-load config.json at import time if it exists
load_config_from_file('config.json')

# Technical Analysis Weights (Required by technical_analyzer.py)
TECHNICAL_WEIGHTS = {
    'ma_trend': 25,      # Moving Average Trend (25%)
    'rsi': 20,           # RSI Momentum (20%)
    'macd': 20,          # MACD Signal (20%)
    'trend': 15,         # Overall Trend (15%)
    'stochastic': 10,    # Stochastic Oscillator (10%)
    'volume': 5,         # Volume Analysis (5%)
    'volatility': 5      # Volatility Analysis (5%)
}

# Fundamental Analysis Weights (for enhanced_fundamental_analyzer.py)
FUNDAMENTAL_WEIGHTS = {
    'profitability': 30,    # ROE, ROA, Profit Margin
    'valuation': 25,        # P/E, P/B, EV/EBITDA
    'growth': 20,           # Revenue Growth, Earnings Growth
    'financial_health': 15, # Debt/Equity, Current Ratio
    'efficiency': 10        # Asset Turnover, Inventory Turnover
}
