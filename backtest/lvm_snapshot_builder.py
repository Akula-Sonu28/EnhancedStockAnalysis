"""Build monthly DateSnapshots for LVM backtests (Nifty 200, OHLCV-only)."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from config import get_config

from .data.indicators import (
    annualized_volatility_12m,
    annualized_volatility_20d,
    return_12m_pct,
    sma,
)
from .data.path1_loader import DateSnapshot, first_sector_lookup
from .data.path2_rescore import _rebalance_dates, _trading_dates
from .data.prices import PriceCache, warmup

REPO_ROOT = Path(__file__).resolve().parents[1]
NIFTY200_CSV = REPO_ROOT / 'stock_list_template.csv'
CACHE_DIR = REPO_ROOT / 'backtest' / 'cache' / 'lvm_snapshots'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_nifty200_universe(path: Optional[Path] = None) -> list[str]:
    """Load symbols from Nifty 200 template only."""
    p = path or NIFTY200_CSV
    if not p.exists():
        raise FileNotFoundError(f'Nifty 200 list not found: {p}')
    if '500' in p.name:
        raise ValueError('LVM backtest requires Nifty 200 list, not 500 template')
    df = pd.read_csv(p)
    col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
    return [str(s).strip().upper() for s in df[col].dropna().tolist()]


def _cache_key(
    start: date, end: date, cadence: str, n: int, vol_mode: str, score_mode: str,
    pit_only: bool = False,
) -> Path:
    tag = '_pitonly' if pit_only else ''
    return CACHE_DIR / f'lvm_{start}_{end}_{cadence}_n{n}_{vol_mode}_{score_mode}{tag}.pkl'


class LvmSnapshotBuilder:
    """OHLCV → LVM columns → compute_lowvol_mom_score per rebalance date."""

    def __init__(
        self,
        universe: Optional[list[str]] = None,
        prices: Optional[PriceCache] = None,
        vol_mode: str = '12m',
        score_mode: str = 'lvm',
        pit_only: bool = False,
    ):
        self.universe = universe or load_nifty200_universe()
        self.prices = prices or PriceCache(refresh_days=1)
        self.vol_mode = vol_mode
        self.score_mode = score_mode
        self.pit_only = pit_only
        self.sectors = first_sector_lookup()
        self._cfg = get_config()

    def _row_for_symbol(self, sym: str, d: date, nifty_close: pd.Series) -> Optional[dict]:
        df = self.prices.get(sym, d - timedelta(days=400), d + timedelta(days=2))
        if df.empty or len(df) < 60:
            return None
        cutoff = pd.Timestamp(d)
        sub = df[df.index <= cutoff]
        if len(sub) < 60:
            return None
        close = sub['Close'].astype(float)
        price = float(close.iloc[-1])
        if price <= 0:
            return None
        vol_12m = annualized_volatility_12m(close)
        ret_12m = return_12m_pct(close)
        sma50 = sma(close, 50)
        # LVM _volatility_col prefers volatility_6m — map 12m spec into that column for backtest.
        vol_for_rank = vol_12m if self.vol_mode == '12m' else annualized_volatility_20d(close)
        return {
            'date': pd.Timestamp(d),
            'symbol': sym,
            'sector': self.sectors.get(sym, 'Unknown'),
            'current_price': price,
            'legacy_sma_50': sma50,
            'sma_50': sma50,
            'enhanced_sma_50': sma50,
            'price_change_1y': ret_12m,
            'volatility_12m': vol_12m,
            'volatility_6m': vol_for_rank,
        }

    def _attach_pit_columns(self, out: pd.DataFrame, d: date) -> pd.DataFrame:
        from backtest.data.fundamentals_pit import get_fundamental_lookup

        lookup = get_fundamental_lookup()
        roe, eg, rg, de, trap, real = [], [], [], [], [], []
        for _, row in out.iterrows():
            sym = str(row['symbol'])
            px = float(row['current_price'])
            pit = lookup.lookup(sym, d, price=px)
            roe.append(pit.get('roe'))
            eg.append(pit.get('earnings_growth'))
            rg.append(pit.get('revenue_growth'))
            de.append(pit.get('debt_to_equity'))
            trap.append(lookup.is_value_trap(sym, d, price=px))
            real.append(lookup.has_real_filing(sym, d))
        out['pit_roe'] = roe
        out['pit_earnings_growth'] = eg
        out['pit_revenue_growth'] = rg
        out['pit_debt_to_equity'] = de
        out['pit_value_trap'] = trap
        out['pit_has_real_filing'] = real
        return out

    def _apply_scoring(self, out: pd.DataFrame, d: date) -> pd.DataFrame:
        if self.score_mode == 'quality_lvm':
            from src.quality_lowvol_momentum import compute_quality_lvm_score

            out = self._attach_pit_columns(out, d)
            out = compute_quality_lvm_score(
                out, self._cfg, as_of=d, require_real_pit=self.pit_only or None,
            )
            out['score_engine'] = out['quality_lvm_score']
            return out
        from src.lowvol_momentum import compute_lowvol_mom_score
        out = compute_lowvol_mom_score(out, self._cfg)
        out['score_engine'] = out['lowvol_mom_score']
        return out

    def _build_snapshot(self, d: date) -> Optional[pd.DataFrame]:
        rows = []
        for sym in self.universe:
            row = self._row_for_symbol(sym, d, pd.Series(dtype=float))
            if row:
                rows.append(row)
        if not rows:
            return None
        out = pd.DataFrame(rows)
        return self._apply_scoring(out, d)

    def build_snapshots(
        self,
        start: date,
        end: date,
        cadence: str = 'monthly',
        use_cache: bool = True,
    ) -> list[DateSnapshot]:
        cache_path = _cache_key(
            start, end, cadence, len(self.universe), self.vol_mode, self.score_mode,
            pit_only=self.pit_only,
        )
        if use_cache and cache_path.exists():
            try:
                df_all = pd.read_pickle(cache_path)
                df_all['date'] = pd.to_datetime(df_all['date'])
                logging.info('[lvm] loaded cached snapshots: %s', cache_path)
                return self._slice_snapshots(df_all)
            except Exception as e:
                logging.warning('[lvm] cache read failed: %s', e)

        anchor = 'RELIANCE' if 'RELIANCE' in self.universe else self.universe[0]
        trading = _trading_dates(self.prices, anchor, start, end)
        rebal = _rebalance_dates(trading, cadence)
        logging.info('[lvm] %d rebalance dates, universe=%d', len(rebal), len(self.universe))

        frames = []
        t0 = time.time()
        for i, d in enumerate(rebal):
            snap = self._build_snapshot(d)
            if snap is not None and not snap.empty:
                frames.append(snap)
            if (i + 1) % 3 == 0 or i == len(rebal) - 1:
                logging.info('[lvm] %d/%d snapshots (%.1fs)', i + 1, len(rebal), time.time() - t0)

        if not frames:
            return []
        df_all = pd.concat(frames, ignore_index=True)
        try:
            df_all.to_pickle(cache_path)
        except Exception as e:
            logging.warning('[lvm] cache write failed: %s', e)
        return self._slice_snapshots(df_all)

    @staticmethod
    def _slice_snapshots(df_all: pd.DataFrame) -> list[DateSnapshot]:
        out = []
        for d, grp in df_all.groupby('date'):
            g = grp.dropna(subset=['current_price']).copy()
            if g.empty:
                continue
            out.append(DateSnapshot(decision_date=d.date(), df=g.reset_index(drop=True)))
        return out

    def warmup_prices(self, start: date, end: date) -> dict[str, bool]:
        return warmup(
            self.universe + ['^NSEI'],
            start - timedelta(days=400),
            end,
            cache=self.prices,
            sleep_between=0.05,
        )
