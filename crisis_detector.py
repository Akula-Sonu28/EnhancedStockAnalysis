"""
GAP-18: Crisis & Global Event Detector
======================================
Identifies market crises using cross-asset signal fingerprinting.
All data sourced from yfinance — no premium API required.

Detects 5 event types:
  GEOPOLITICAL_WAR  — crude + gold spike, INR weakens (Middle East / regional war)
  OIL_SHOCK         — crude spikes >5% alone (OPEC cut, supply disruption)
  US_MARKET_CRISIS  — S&P 500 leads crash (US recession / Fed shock / US geopolitical)
  CURRENCY_CRISIS   — INR depreciates >1.5% in a day (capital flight)
  MARKET_PANIC      — VIX spike + Nifty crash, undefined cause

Fingerprint Logic (why each signal means what):
  crude↑ + gold↑ = geopolitical risk premium (both go up in wars)
  gold↑ alone    = pure safe-haven flight (recession fear, not supply shock)
  INR↓           = capital leaving India (war near India, sanctions, FII exit)
  sp500↓ leads   = US-originated problem (not commodity driven)
  VIX spike      = pure panic (algo liquidation, margin calls)

Author: GAP-18 fix — March 2026
"""

import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict
import logging


class CrisisDetector:
    """
    Cross-asset crisis event detector.
    Designed to be initialized once per analysis run.
    crisis_data = detector.detect()  →  cached, passed read-only to all stock workers.
    """

    # ── Cross-asset tickers (all free via yfinance) ─────────────────────────
    ASSETS = {
        'nifty':  '^NSEI',       # Indian market benchmark
        'vix':    '^INDIAVIX',   # India fear gauge
        'crude':  'BZ=F',        # Brent crude (India imports Brent, not WTI)
        'gold':   'GC=F',        # Gold futures (safe-haven signal)
        'usdinr': 'USDINR=X',   # USD/INR — higher value = INR weakening
        'sp500':  '^GSPC',       # US market (global contagion signal)
    }

    # ── Known defence stocks — no reliable "Defence" sector in yfinance ─────
    DEFENCE_SYMBOLS = {
        'HAL', 'BEL', 'BHEL', 'BEML', 'MIDHANI', 'GRSE', 'MDL',
        'COCHINSHIP', 'MAZDOCK', 'PARAS', 'IDEAFORGE', 'DATACPAT',
        'ZENTEC', 'MTAR', 'AEROINFRA',
    }

    # ── Upstream oil producers — benefit when crude spikes ──────────────────
    OIL_UPSTREAM_SYMBOLS = {'ONGC', 'OIL', 'VEDL'}

    # ── Symbol → conceptual sector override ─────────────────────────────────
    # yfinance uses broad sector labels (Industrials, Energy) that don't map
    # cleanly to our crisis keywords. Override table forces the right match.
    # These are the most impactful stocks for each crisis type.
    SYMBOL_SECTOR_OVERRIDES = {
        # Ports / Logistics (yfinance: 'Industrials')
        'ADANIPORTS': 'PORT',
        'CONCOR':     'PORT',
        'JSWINFRA':   'PORT',
        'ESMSEA':     'PORT',
        # Airlines (yfinance: 'Industrials')
        'INDIGO':     'AVIATION',
        'SPICEJET':   'AVIATION',
        'AIRINDIA':   'AVIATION',
        # OMC crude importers (yfinance: 'Energy' — need negative adjustment)
        'IOC':        'OIL',
        'BPCL':       'OIL',
        'HPCL':       'OIL',
        'MRPL':       'OIL',
        'CHENNPETRO': 'OIL',
        # Pharma (yfinance: 'Healthcare' — need positive adjustment in GEOPOLITICAL)
        'SUNPHARMA':  'PHARMA',
        'DRREDDY':    'PHARMA',
        'CIPLA':      'PHARMA',
        'DIVISLAB':   'PHARMA',
        'AUROPHARMA': 'PHARMA',
        'LUPIN':      'PHARMA',
        'BIOCON':     'PHARMA',
    }

    # ── Sector keyword → score adjustment per crisis type ───────────────────
    # Keys are substrings matched case-insensitively against stock_data['sector']
    # Highest-magnitude match wins (most specific rule)
    SECTOR_RULES: Dict[str, Dict[str, float]] = {

        'GEOPOLITICAL_WAR': {
            # ✅ Winners
            'DEFENCE':                +10.0,   # Direct war beneficiary
            'AEROSPACE':              +8.0,
            'BANK':                   +5.0,    # PSU Banks — govt backstop, safe haven
            'FINANCIAL':              +3.0,    # yfinance: 'Financial Services'
            'FINANCE':                +3.0,
            'PHARMA':                 +2.0,    # Domestic defensive
            'HEALTH':                 +2.0,    # yfinance: 'Healthcare'
            'FMCG':                   +2.0,    # Domestic defensive
            'CONSUMER STAPLES':       +2.0,    # yfinance tag for FMCG
            'CONSUMER DEFENSIVE':     +2.0,    # yfinance tag for FMCG
            'CONSUMER':               +2.0,
            # ❌ Losers
            'PORT':                   -10.0,   # Strait of Hormuz closure
            'SHIPPING':               -8.0,    # yfinance ships under Industrials sometimes
            'LOGISTICS':              -8.0,
            'TRANSPORT':              -6.0,
            'AVIATION':               -8.0,    # Airspace closures + fuel cost
            'AIRLINE':                -8.0,
            'OIL':                    -6.0,    # OMC importers (IOC/BPCL/HPCL via symbol override)
            'ENERGY':                 -4.0,    # yfinance tag covering oil/gas companies
            'GAS':                    -4.0,
            'PETROCHEM':              -5.0,
            'INFORMATION TECHNOLOGY': -5.0,   # US client freeze
            'SOFTWARE':               -5.0,
            'TECHNOLOGY':             -4.0,
            'INDUSTRIAL':             -3.0,    # yfinance: ports/logistics often tagged here
        },

        'OIL_SHOCK': {
            # ❌ Losers — crude consumers
            'OIL':              -8.0,    # IOC, BPCL, HPCL (refiners/marketers)
            'ENERGY':           -6.0,    # yfinance tag for oil/gas sector
            'REFINERY':         -8.0,
            'AVIATION':         -8.0,
            'AIRLINE':          -8.0,
            'PAINT':            -6.0,    # Linseed oil, solvents
            'FERTILIZER':       -5.0,    # Natural gas feedstock
            'CHEMICAL':         -4.0,
            'BASIC MATERIALS':  -3.0,    # yfinance tag covering chemicals/fertilizers
            'FMCG':             -3.0,    # Palm oil, packaging cost
            'CONSUMER STAPLES': -2.0,    # yfinance FMCG tag
        },

        'US_MARKET_CRISIS': {
            # ❌ Losers — US-exposed exporters
            'INFORMATION TECHNOLOGY': -10.0,
            'SOFTWARE':              -10.0,
            'TECHNOLOGY':             -8.0,
            'PHARMA':                  -5.0,   # US generics revenue
            'HEALTH':                  -4.0,   # yfinance: 'Healthcare'
            # ✅ Winners — domestic plays
            'BANK':                   +3.0,   # Domestic banks less affected
            'FINANCIAL':              +2.0,   # yfinance: 'Financial Services'
            'FINANCE':                +2.0,
            'FMCG':                   +3.0,
            'CONSUMER STAPLES':       +3.0,   # yfinance FMCG tag
            'CONSUMER DEFENSIVE':     +3.0,   # yfinance FMCG tag
            'CONSUMER':               +2.0,
        },

        'CURRENCY_CRISIS': {
            # ✅ Winners — USD earners, exports revenue up in INR terms
            'INFORMATION TECHNOLOGY': +8.0,
            'SOFTWARE':               +8.0,
            'TECHNOLOGY':             +6.0,   # yfinance tag
            'PHARMA':                 +6.0,   # US generics in USD
            'HEALTH':                 +5.0,   # yfinance: 'Healthcare'
            'TEXTILE':                +4.0,
            'ENGINEERING':            +3.0,   # Export machinery
            # ❌ Losers — import cost surges in INR
            'OIL':              -6.0,    # Crude import bill
            'ENERGY':           -5.0,    # yfinance tag
            'AVIATION':         -5.0,    # Fuel in USD
            'AIRLINE':          -5.0,
            'ELECTRONICS':      -5.0,    # Component imports
            'CAPITAL GOODS':    -3.0,    # Imported machinery
            'INDUSTRIAL':       -2.0,    # yfinance tag — partial exposure
        },

        'MARKET_PANIC': {
            # ✅ Winners — defensives / low beta
            'FMCG':               +3.0,
            'CONSUMER STAPLES':   +3.0,   # yfinance FMCG tag
            'CONSUMER DEFENSIVE': +3.0,
            'PHARMA':             +3.0,
            'HEALTH':             +3.0,   # yfinance: 'Healthcare'
            'BANK':               +3.0,   # Perceived safe (flight to quality)
            'FINANCIAL':          +2.0,
            'FINANCE':            +2.0,
            'CONSUMER':           +2.0,
            # ❌ Losers — high beta / speculative
            'REAL ESTATE':        -6.0,
            'REALTY':             -6.0,
            'METAL':              -5.0,
            'BASIC MATERIALS':    -4.0,   # yfinance tag for metals/mining
            'STEEL':              -4.0,
            'MEDIA':              -4.0,
            'COMMUNICATION':      -3.0,   # yfinance tag for telecom/media
            'TELECOM':            -3.0,
        },
    }

    DESCRIPTIONS = {
        'GEOPOLITICAL_WAR': '⚔️  Geopolitical War — crude+gold spike, INR weakened',
        'OIL_SHOCK':        '🛢️  Oil Shock — crude spike alone (no war signals)',
        'US_MARKET_CRISIS': '🇺🇸 US Market Crisis — S&P 500 leading the crash',
        'CURRENCY_CRISIS':  '💸 Currency Crisis — INR sharp depreciation',
        'MARKET_PANIC':     '😱 Market Panic — VIX spike + Nifty crash (cause TBD)',
        'NONE':             '✅ Normal — no crisis signals detected',
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ────────────────────────── Public API ──────────────────────────────────

    def detect(self) -> Dict:
        """
        Main entry point. Fetches cross-asset signals and classifies the event.

        Returns:
            Dict with keys:
                crisis_detected  (bool)
                crisis_type      (str)  — GEOPOLITICAL_WAR | OIL_SHOCK | US_MARKET_CRISIS |
                                          CURRENCY_CRISIS | MARKET_PANIC | NONE
                severity         (int)  — 0=none, 1=mild, 2=moderate, 3=severe
                severity_label   (str)
                description      (str)
                sector_adjustments (Dict[str, float]) — raw pts before severity scaling
                signals          (Dict)
                timestamp        (str)
        """
        try:
            signals = self._fetch_signals()
            _fetch_failures = signals.pop('_fetch_failures', 0)
            _total_assets = len(self.ASSETS) + 1  # +1 for VIX
            _all_failed = _fetch_failures >= _total_assets

            crisis_type = self._classify_event(signals)
            severity = self._calculate_severity(signals, crisis_type)

            result = {
                'crisis_detected':    crisis_type != 'NONE',
                'crisis_type':        crisis_type,
                'severity':           severity,
                'severity_label':     ['NONE', 'MILD', 'MODERATE', 'SEVERE'][min(severity, 3)],
                'description':        self.DESCRIPTIONS.get(crisis_type, 'Unknown event'),
                'sector_adjustments': self.SECTOR_RULES.get(crisis_type, {}),
                'signals':            signals,
                'detection_failed':   _all_failed,
                'timestamp':          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

            if _all_failed:
                self.logger.error(
                    f"[CRISIS-DETECTOR] ALL {_total_assets} asset feeds failed — "
                    f"detection_failed=True, result is unreliable"
                )

            if crisis_type != 'NONE':
                sig = signals
                self.logger.warning(
                    f"[CRISIS-DETECTOR] {self.DESCRIPTIONS[crisis_type]} | "
                    f"Severity={result['severity_label']} | "
                    f"Nifty={sig.get('nifty', {}).get('change_pct', 0):+.2f}% | "
                    f"Crude={sig.get('crude', {}).get('change_pct', 0):+.2f}% | "
                    f"Gold={sig.get('gold', {}).get('change_pct', 0):+.2f}% | "
                    f"INR(USD/INR)={sig.get('usdinr', {}).get('change_pct', 0):+.3f}% | "
                    f"SP500={sig.get('sp500', {}).get('change_pct', 0):+.2f}% | "
                    f"VIX_spike={sig.get('vix_spike_pct', 0):+.0f}%"
                )
            else:
                self.logger.info("[CRISIS-DETECTOR] No crisis signals — normal market conditions")

            return result

        except Exception as e:
            self.logger.error(f"[CRISIS-DETECTOR] Detection failed: {e}")
            return self._no_crisis(detection_failed=True)

    def get_stock_crisis_adjustment(self, symbol: str, sector: str, crisis_data: Dict) -> float:
        """
        Returns the score adjustment (+ or −) for a specific stock given the
        current crisis type. Thread-safe: read-only on crisis_data.

        Special overrides (bypass sector tag, which can be unreliable):
          - Defence symbols always +10 in GEOPOLITICAL_WAR
          - Oil upstream (ONGC/OIL) always +8 in OIL_SHOCK / GEOPOLITICAL_WAR

        Severity scaling: severity 1 → 33%, severity 2 → 67%, severity 3 → 100%
        Cap: ±10 pts

        Args:
            symbol:      Stock ticker, e.g. 'HAL' or 'HAL.NS'
            sector:      Sector string from yfinance info, e.g. 'Information Technology'
            crisis_data: Output from detect()

        Returns:
            float: Adjustment to add to final_blended_score
        """
        if not crisis_data.get('crisis_detected', False):
            return 0.0

        crisis_type = crisis_data.get('crisis_type', 'NONE')
        severity = crisis_data.get('severity', 0)

        if crisis_type == 'NONE' or severity == 0:
            return 0.0

        # Severity scale: 1 = 33%, 2 = 67%, 3 = 100%
        scale = severity / 3.0

        symbol_upper = (str(symbol) if symbol else '').upper().replace('.NS', '').strip()
        sector_upper = (sector or '').upper()

        # ── Symbol-level overrides (independent of yfinance sector tag) ─────
        # Priority 1: Defence symbols — always boost in war
        if crisis_type == 'GEOPOLITICAL_WAR':
            if symbol_upper in self.DEFENCE_SYMBOLS:
                return round(10.0 * scale, 1)
        # Priority 2: Oil upstream producers — benefit from crude spike
        if crisis_type in ('OIL_SHOCK', 'GEOPOLITICAL_WAR'):
            if symbol_upper in self.OIL_UPSTREAM_SYMBOLS:
                return round(8.0 * scale, 1)

        # ── Symbol→sector override: fix yfinance broad labels ───────────────
        # e.g. ADANIPORTS → 'PORT', IOC → 'OIL', INDIGO → 'AVIATION'
        # Replaces the raw yfinance sector string for keyword matching only.
        if symbol_upper in self.SYMBOL_SECTOR_OVERRIDES:
            sector_upper = self.SYMBOL_SECTOR_OVERRIDES[symbol_upper].upper()

        # ── Sector keyword matching ──────────────────────────────────────────
        sector_rules = self.SECTOR_RULES.get(crisis_type, {})
        best_pts = 0.0
        for keyword, points in sector_rules.items():
            if keyword in sector_upper:
                # Highest magnitude match wins (most specific rule)
                if abs(points) > abs(best_pts):
                    best_pts = points

        raw_adj = best_pts * scale
        return round(max(-10.0, min(10.0, raw_adj)), 1)

    # ─────────────────────────── Private helpers ────────────────────────────

    def _fetch_signals(self) -> Dict:
        """Fetch 1-day % change for all cross-asset tickers.
        Returns signals dict with `_fetch_failures` count for downstream failure detection.
        """
        signals = {}
        _fail_count = 0

        for name, sym in self.ASSETS.items():
            try:
                hist = yf.Ticker(sym).history(period='5d', interval='1d')
                if len(hist) >= 2:
                    today     = float(hist['Close'].iloc[-1])
                    yesterday = float(hist['Close'].iloc[-2])
                    pct = (today - yesterday) / yesterday * 100 if pd.notna(yesterday) and yesterday != 0 else 0.0
                    signals[name] = {'value': round(today, 4), 'change_pct': round(pct, 3)}
                else:
                    signals[name] = {'value': 0.0, 'change_pct': 0.0}
                    _fail_count += 1
            except Exception as e:
                self.logger.debug(f"[CRISIS] {name}/{sym} fetch error: {e}")
                signals[name] = {'value': 0.0, 'change_pct': 0.0}
                _fail_count += 1

        # VIX spike = today vs 5-day rolling average (more sensitive than raw 1-day change)
        try:
            vh = yf.Ticker('^INDIAVIX').history(period='10d', interval='1d')
            if len(vh) >= 5:
                avg5 = float(vh['Close'].iloc[-5:-1].mean())
                now  = float(vh['Close'].iloc[-1])
                signals['vix_spike_pct'] = round((now - avg5) / avg5 * 100 if avg5 > 0 else 0.0, 1)
                signals['vix_absolute']  = round(now, 2)
            else:
                signals['vix_spike_pct'] = 0.0
                signals['vix_absolute']  = 15.0
                _fail_count += 1
        except Exception as e:
            self.logger.debug(f"[CRISIS] VIX fetch failed: {e}")
            signals['vix_spike_pct'] = 0.0
            signals['vix_absolute']  = 15.0
            _fail_count += 1

        signals['_fetch_failures'] = _fail_count
        return signals

    def _classify_event(self, signals: Dict) -> str:
        """
        Classify event type from cross-asset signal fingerprints.

        Priority order (most specific first):
        1. GEOPOLITICAL_WAR  → crude AND gold both up (war premium)
        2. OIL_SHOCK         → crude up alone (supply disruption, no safe-haven)
        3. US_MARKET_CRISIS  → S&P 500 leads, no commodity spike
        4. CURRENCY_CRISIS   → INR falls sharply (capital flight)
        5. MARKET_PANIC      → VIX spike + Nifty crash (undefined cause)
        """
        nifty  = signals.get('nifty',  {}).get('change_pct', 0.0)
        crude  = signals.get('crude',  {}).get('change_pct', 0.0)
        gold   = signals.get('gold',   {}).get('change_pct', 0.0)
        usdinr = signals.get('usdinr', {}).get('change_pct', 0.0)  # +ve = INR weakens
        sp500  = signals.get('sp500',  {}).get('change_pct', 0.0)
        vix_sp = signals.get('vix_spike_pct', 0.0)

        # 1. GEOPOLITICAL_WAR: crude AND gold both surge, INR weakens
        #    Gold and crude rising together = supply shock + safe-haven = war/conflict
        if crude > 3.0 and gold > 1.0 and usdinr > 0.3:
            return 'GEOPOLITICAL_WAR'

        # 2. OIL_SHOCK: crude spikes significantly but gold is flat
        #    Supply cut / single-country disruption, not systemic geopolitical panic
        if crude > 5.0 and gold < 1.0:
            return 'OIL_SHOCK'

        # 3. US_MARKET_CRISIS: S&P 500 down >2% (US-led), no commodity spike
        #    Fed shock, US bank failure, US recession signal
        if sp500 < -2.0 and nifty < -1.5 and crude < 2.0:
            return 'US_MARKET_CRISIS'

        # 4. CURRENCY_CRISIS: INR depreciates >1.5% in a single day = capital flight
        if usdinr > 1.5 and nifty < -1.0:
            return 'CURRENCY_CRISIS'

        # 5. MARKET_PANIC: VIX spikes >30% above 5-day avg + Nifty falls >2%
        if vix_sp > 30.0 and nifty < -2.0:
            return 'MARKET_PANIC'

        return 'NONE'

    def _calculate_severity(self, signals: Dict, crisis_type: str) -> int:
        """
        Severity 0-3 based on magnitude of signals.
        0 = no crisis, 1 = mild, 2 = moderate, 3 = severe
        """
        if crisis_type == 'NONE':
            return 0

        nifty_drop = abs(signals.get('nifty', {}).get('change_pct', 0.0))
        vix_spike  = signals.get('vix_spike_pct', 0.0)
        crude_move = abs(signals.get('crude',  {}).get('change_pct', 0.0))

        score = 0

        # Nifty crash contribution
        if   nifty_drop > 3.0:  score += 3
        elif nifty_drop > 2.0:  score += 2
        elif nifty_drop > 1.0:  score += 1

        # VIX spike contribution
        if   vix_spike > 50: score += 2
        elif vix_spike > 30: score += 1

        # Crude shock contribution (relevant for WAR / OIL_SHOCK)
        if   crude_move > 8: score += 2
        elif crude_move > 4: score += 1

        # Map to 0-3
        if   score >= 5: return 3   # SEVERE
        elif score >= 3: return 2   # MODERATE
        elif score >= 1: return 1   # MILD
        return 1  # Crisis was detected so at least MILD

    def _no_crisis(self, detection_failed: bool = False) -> Dict:
        """Safe fallback when detection throws an exception."""
        return {
            'crisis_detected':    False,
            'crisis_type':        'NONE',
            'severity':           0,
            'severity_label':     'NONE',
            'description':        '⚠️ Detection failed — assuming no crisis (conservative)' if detection_failed else '✅ Normal — no crisis signals detected',
            'sector_adjustments': {},
            'signals':            {},
            'detection_failed':   detection_failed,
            'timestamp':          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')

    print("=" * 72)
    print("  GAP-18: CRISIS DETECTOR — LIVE CROSS-ASSET SIGNAL SCAN")
    print("=" * 72)

    detector = CrisisDetector()
    result = detector.detect()

    icon = '🚨' if result['crisis_detected'] else '✅'
    print(f"\n{icon} Status   : {result['description']}")
    print(f"   Type     : {result['crisis_type']}")
    print(f"   Severity : {result['severity_label']} ({result['severity']}/3)")

    print(f"\n📡 CROSS-ASSET SIGNALS:")
    print(f"   {'Asset':12s}  {'Value':>12s}  {'1-day chg':>10s}")
    print(f"   {'-'*12}  {'-'*12}  {'-'*10}")
    for asset, data in result['signals'].items():
        if isinstance(data, dict):
            chg = data.get('change_pct', 0)
            val = data.get('value', 0)
            arrow = '▲' if chg > 0.1 else ('▼' if chg < -0.1 else '→')
            print(f"   {asset:12s}  {val:>12.3f}  {arrow} {chg:+.2f}%")
        else:
            label = 'VIX spike%' if 'spike' in asset else asset
            print(f"   {label:12s}  {data:>12.2f}")

    if result['crisis_detected']:
        print(f"\n⚙️  SECTOR ADJUSTMENTS (raw pts × severity scale = applied pts):")
        scale = result['severity'] / 3.0
        for sector, pts in sorted(result['sector_adjustments'].items(), key=lambda x: -abs(x[1])):
            applied = round(pts * scale, 1)
            bar = '▲' if pts > 0 else '▼'
            print(f"   {bar} {sector:35s}: {pts:+5.1f} raw  →  {applied:+5.1f} applied")

        print(f"\n📋 RECOMMENDED ACTIONS:")
        adj_map = {
            'GEOPOLITICAL_WAR': [
                '  BUY  → HAL, BEL (Defence rally)',
                '  BUY  → PSUBNKBEES (Govt backstop)',
                '  HOLD → ONGC/OIL (crude producers benefit)',
                '  WAIT → IOC/BPCL (crude import cost rises)',
                '  SELL → ADANIPORTS / Logistics (Strait risk)',
                '  AVOID→ IT stocks (US client freeze)',
            ],
            'OIL_SHOCK': [
                '  BUY  → ONGC, OIL India (producers)',
                '  SELL → IOC, BPCL, HPCL (refiner margin squeeze)',
                '  AVOID→ IndiGo/SpiceJet (jet fuel cost spike)',
            ],
            'US_MARKET_CRISIS': [
                '  AVOID→ TCS, Infosys, Wipro (US revenue freeze)',
                '  BUY  → Domestic banks, FMCG (India-centric)',
            ],
            'CURRENCY_CRISIS': [
                '  BUY  → TCS, Infosys (USD earnings go up in INR)',
                '  SELL → Import-heavy sectors',
            ],
            'MARKET_PANIC': [
                '  BUY  → NIFTYBEES at support levels (staggered entry)',
                '  BUY  → FMCG, Pharma (defensives)',
                '  AVOID→ Small caps, Real estate',
            ],
        }
        for action in adj_map.get(result['crisis_type'], []):
            print(action)

    print(f"\n⏰ {result['timestamp']}")
    print("=" * 72)
