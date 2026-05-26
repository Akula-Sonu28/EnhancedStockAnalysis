"""Regenerate Cursor analysis canvas from the latest Excel report."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CANVAS_NAME = 'stock-analysis-dashboard.canvas.tsx'
COMP_MAP = {
    'hybrid_fundamental_quality': 'fundamental_quality',
    'hybrid_momentum_technical': 'momentum_technical',
    'hybrid_volume_strength': 'volume_strength',
    'hybrid_multi_timeframe': 'multi_timeframe',
    'hybrid_ml_signal': 'ml_signal',
    'hybrid_risk_adjustment': 'risk_adjustment',
    'hybrid_growth': 'growth',
    'hybrid_value': 'value',
}
# Portfolio Allocation sheet display columns (when raw hybrid_* cols absent)
EXCEL_COMP_MAP = {
    'QUALITY': 'fundamental_quality',
    'MOMENTUM': 'momentum_technical',
    'VOL': 'volume_strength',
    'MTF': 'multi_timeframe',
    'ML CONF %': 'ml_signal',
    'RISK': 'risk_adjustment',
    'GROWTH': 'growth',
    'VALUE': 'value',
}


def resolve_canvas_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or REPO_ROOT
    projects = Path.home() / '.cursor' / 'projects'
    if projects.is_dir():
        for cand in sorted(projects.glob('*')):
            if not cand.is_dir():
                continue
            if root.name in cand.name or 'Stock' in cand.name:
                d = cand / 'canvases'
                d.mkdir(parents=True, exist_ok=True)
                return d
    fallback = projects / f'Users-{Path.home().name}-TestNetstock-{root.name}' / 'canvases'
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _tsx_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _tsx_data(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _rescore(allocation_df: pd.DataFrame, weights: dict) -> pd.Series:
    score = pd.Series(50.0, index=allocation_df.index)
    has_hybrid = any(c in allocation_df.columns for c in COMP_MAP)
    col_map = COMP_MAP if has_hybrid else EXCEL_COMP_MAP
    for col, wkey in col_map.items():
        w = float(weights.get(wkey, 0.0))
        if w == 0.0 or col not in allocation_df.columns:
            continue
        comp = pd.to_numeric(allocation_df[col], errors='coerce').fillna(50.0)
        score += (comp - 50.0) * w
    return score.clip(0, 100)


def _normalize_allocation_df(allocation_df: pd.DataFrame) -> pd.DataFrame:
    df = allocation_df.copy()
    aliases = {
        'ACTION': 'action_recommendation',
        'INVEST ₹': 'investment_amount',
        'MY QTY': 'current_quantity',
        'BUY QTY': 'suggested_quantity',
        'MY VALUE ₹': 'current_value',
        'PRICE': 'current_price',
        'BOOK %': 'profit_booking_pct',
        'SCORE': 'hybrid_overall_score_v2',
        'P&L %': 'pnl_percent',
    }
    for excel_col, raw_col in aliases.items():
        if excel_col not in df.columns and raw_col in df.columns:
            df[excel_col] = df[raw_col]
    if 'symbol' not in df.columns and len(df.columns):
        df['symbol'] = df.iloc[:, 0]
    return df


def _prep_numeric(df: pd.DataFrame) -> pd.DataFrame:
    cols = ['INVEST ₹', 'MY QTY', 'BUY QTY', 'MY VALUE ₹', 'PRICE', 'BOOK %', 'BOOK ₹',
            'P&L %', 'SCORE', 'ADJ SCORE', 'VOLATILITY %', 'TAX ₹']
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    for c in ['ACTION', 'symbol', 'sector', 'WHEN', 'REASON', 'OWNED?', 'ML', 'RISK CAT']:
        if c in df.columns:
            df[c] = df[c].fillna('').astype(str)
    return df


def _fmt_inr(n: float) -> str:
    return f'₹{n:,.0f}'


def _signal_from_score(score: float, buy_thr: float = 60.0, hold_thr: float = 50.0) -> str:
    if score >= buy_thr:
        return 'BUY'
    if score >= hold_thr:
        return 'HOLD'
    if score >= 40:
        return 'WEAK SELL'
    return 'SELL'


def _priority_section(
    section_id: str,
    title: str,
    rows: List[dict],
    total_label: str = '',
    total_value: float = 0,
    tone: str = 'neutral',
) -> Optional[dict]:
    if not rows:
        return None
    out: dict = {'id': section_id, 'title': title, 'tone': tone, 'rows': rows}
    if total_label and total_value:
        out['totalLabel'] = total_label
        out['totalValue'] = _fmt_inr(total_value)
    return out


def _build_action_plan_sections(df: pd.DataFrame) -> List[dict]:
    """Mirror terminal priority blocks from analyze_top200 main()."""
    sym, act = 'symbol', 'ACTION'
    inv, qty, bqty, val, price = 'INVEST ₹', 'MY QTY', 'BUY QTY', 'MY VALUE ₹', 'PRICE'
    sections: List[dict] = []

    swaps = df[df[act].str.contains('SWAP', na=False)].sort_values(val, ascending=False)
    swap_rows, swap_total = [], 0.0
    for _, r in swaps.iterrows():
        rot = str(r.get('ROT TARGET', r.get('rotation_target', ''))).strip()
        if not rot or rot == 'nan':
            rot = r[act].split('->')[1].strip() if '->' in str(r[act]) else 'Unknown'
        swap_rows.append(_enrich_priority_row(
            r, sym, f"Sell {int(r[qty])} shares → buy {rot}", _fmt_inr(r[val]),
        ))
        swap_total += r[val]
    s = _priority_section('swap', 'Priority 1: SWAP', swap_rows, 'Swap proceeds', swap_total, 'info')
    if s:
        sections.append(s)

    exits = df[df[act].str.contains('EXIT', na=False)].sort_values(val, ascending=False)
    exit_rows, exit_total = [], 0.0
    for _, r in exits.iterrows():
        m = re.search(r'(\d+)-(\d+)%', str(r[act]))
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            qlo = max(1, int(r[qty] * lo / 100))
            qhi = max(1, int(r[qty] * hi / 100))
            detail = f"Exit {lo}-{hi}% → sell {qlo}-{qhi} of {int(r[qty])} shares"
            amt = f"~{_fmt_inr(qlo * r[price])}-{_fmt_inr(qhi * r[price])}"
            exit_total += (qlo * r[price] + qhi * r[price]) / 2
        elif 'NOW' in str(r[act]).upper():
            detail = f"Exit ALL {int(r[qty])} shares"
            amt = _fmt_inr(r[val])
            exit_total += r[val]
        else:
            detail = str(r[act])
            amt = _fmt_inr(r[val])
            exit_total += r[val]
        exit_rows.append(_enrich_priority_row(r, sym, detail, amt))
    s = _priority_section('exit', 'Priority 1.5: EXIT (momentum exhaustion)', exit_rows,
                          'EXIT proceeds (est)', exit_total, 'danger')
    if s:
        sections.append(s)

    sells = df[df[act].str.upper().str.strip() == 'SELL'].sort_values(val, ascending=False)
    sell_rows, sell_total = [], 0.0
    for _, r in sells.iterrows():
        sell_rows.append(_enrich_priority_row(
            r, sym, f"Sell ALL {int(r[qty])} shares", _fmt_inr(r[val]),
        ))
        sell_total += r[val]
    s = _priority_section('sell', 'Priority 2: SELL', sell_rows, 'Sell proceeds', sell_total, 'danger')
    if s:
        sections.append(s)

    considers = df[df[act].str.contains('CONSIDER', na=False)].sort_values(val, ascending=False)
    consider_rows, consider_total = [], 0.0
    for _, r in considers.iterrows():
        bk = float(r.get('BOOK %', 1.0) or 1.0)
        if 0 < bk < 1:
            cq = max(1, int(r[qty] * bk))
            detail = f"Consider ~{cq} of {int(r[qty])} shares ({bk * 100:.0f}%)"
            amt = f"~{_fmt_inr(cq * r[price])}"
            consider_total += cq * r[price]
        else:
            detail = f"Consider ALL {int(r[qty])} shares"
            amt = _fmt_inr(r[val])
            consider_total += r[val]
        consider_rows.append(_enrich_priority_row(r, sym, detail, amt))
    s = _priority_section('consider', 'Priority 2.5: CONSIDER SELLING (optional)', consider_rows, tone='warning')
    if s:
        sections.append(s)

    books = df[(df[act].str.contains('BOOK', na=False)) & (df[val] > 0)].sort_values(val, ascending=False)
    book_rows, book_total = [], 0.0
    for _, r in books.iterrows():
        bk = float(r.get('BOOK %', 0) or 0)
        if 0 < bk <= 1:
            smin = int(r[qty] * max(bk - 0.05, 0.05))
            smax = int(r[qty] * bk)
        else:
            smin, smax = int(r[qty] * 0.5), int(r[qty] * 0.6)
        book_rows.append(_enrich_priority_row(
            r, sym, f"Book profit: sell {smin}-{smax} shares",
            f"{_fmt_inr(smin * r[price])}-{_fmt_inr(smax * r[price])}",
        ))
        book_total += (smin * r[price] + smax * r[price]) / 2
    s = _priority_section('book', 'Priority 3: BOOK PROFITS (partial sell)', book_rows,
                          'Book proceeds (est)', book_total, 'warning')
    if s:
        sections.append(s)

    reduces = df[df[act].str.contains('REDUCE', na=False)].sort_values(val, ascending=True)
    reduce_rows, reduce_total = [], 0.0
    for _, r in reduces.iterrows():
        rq = max(1, int(r[qty] * 0.30))
        reduce_rows.append(_enrich_priority_row(
            r, sym, f"Reduce ~{rq} shares — sector overweight ({r.get('sector', '')})",
            _fmt_inr(rq * r[price]),
        ))
        reduce_total += rq * r[price]
    s = _priority_section('reduce', 'Priority 3.5: REDUCE (sector diversification)', reduce_rows,
                          'Reduce proceeds (est)', reduce_total, 'warning')
    if s:
        sections.append(s)

    increases = df[(df[val] > 0) & (df[inv] > 0) & df[act].str.contains('INCREASE', na=False)].sort_values(inv, ascending=False)
    inc_rows, inc_total = [], 0.0
    for _, r in increases.iterrows():
        new_total = r[qty] + r[bqty]
        inc_rows.append(_enrich_priority_row(
            r, sym, f"Add {int(r[bqty])} shares ({int(r[qty])}→{int(new_total)})", _fmt_inr(r[inv]),
        ))
        inc_total += r[inv]
    s = _priority_section('increase', 'Priority 4: INCREASE', inc_rows, 'Increase total', inc_total, 'success')
    if s:
        sections.append(s)

    new_buys = df[(df[val] == 0) & (df[inv] > 0)].sort_values(inv, ascending=False)
    buy_rows, buy_total = [], 0.0
    for _, r in new_buys.iterrows():
        buy_rows.append(_enrich_priority_row(
            r, sym, f"{int(r[bqty])} shares @ ₹{r[price]:,.2f}", _fmt_inr(r[inv]),
        ))
        buy_total += r[inv]
    s = _priority_section('buynew', 'Priority 5: BUY NEW', buy_rows, 'New buys total', buy_total, 'success')
    if s:
        sections.append(s)

    holds = df[(df[val] > 0) & ((df[inv] == 0) | pd.isna(df[inv])) &
               df[act].str.contains('HOLD|KEEP', na=False)].sort_values(val, ascending=False)
    hold_rows = [
        _enrich_priority_row(r, sym, _s(r, 'REASON', 80) or 'No change', _fmt_inr(r[val]))
        for _, r in holds.iterrows()
    ]
    s = _priority_section('hold', f'Priority 6: HOLD ({len(hold_rows)} stocks)', hold_rows, tone='neutral')
    if s:
        sections.append(s)

    watch = df[df[act].str.contains('WATCHLIST', na=False)]
    watch_rows = [
        _enrich_priority_row(r, sym, _s(r, 'REASON', 80) or 'Monitor', _fmt_inr(r[inv]) if r[inv] else '—')
        for _, r in watch.iterrows()
    ]
    s = _priority_section('watch', f'Priority 7: WATCHLIST ({len(watch_rows)})', watch_rows, tone='info')
    if s:
        sections.append(s)

    skips = df[(df[val] > 0) & df[act].str.contains('SKIP', na=False)].sort_values(val, ascending=False)
    skip_rows, skip_total = [], 0.0
    for _, r in skips.iterrows():
        skip_rows.append(_enrich_priority_row(r, sym, _s(r, 'REASON', 80) or 'Optional', _fmt_inr(r[val])))
        skip_total += r[val]
    s = _priority_section('skip', 'Priority 8: OPTIONAL / SKIP', skip_rows, 'Optional value', skip_total, 'neutral')
    if s:
        sections.append(s)

    return sections, {
        'swapTotal': swap_total,
        'sellTotal': sell_total,
        'exitTotal': exit_total,
        'bookTotal': book_total,
        'buyTotal': buy_total,
        'increaseTotal': inc_total,
        'skipTotal': skip_total,
        'considerTotal': consider_total,
    }


def _build_final_numbers(totals: dict, portfolio_amount: float) -> dict:
    sell_proceeds = totals['swapTotal'] + totals['sellTotal'] + totals['exitTotal'] + totals['bookTotal']
    buy_orders = totals['buyTotal'] + totals['increaseTotal']
    consider_proceeds = float(totals.get('considerTotal', 0) or 0)
    skip_proceeds = float(totals.get('skipTotal', 0) or 0)
    net_min = buy_orders - sell_proceeds
    net_with_trims = net_min - consider_proceeds
    net_with_skip = net_min - skip_proceeds
    user_input = float(portfolio_amount or 0)
    out = {
        'sellProceeds': int(sell_proceeds),
        'buyOrders': int(buy_orders),
        'netMin': int(net_min),
        'netMax': int(net_with_skip),
        'netWithOptionalTrims': int(net_with_trims),
        'optionalTrimProceeds': int(consider_proceeds),
        'skipProceeds': int(skip_proceeds),
        'userInput': int(user_input),
    }
    trim_names = []
    if consider_proceeds > 0:
        out['optionalTrimNote'] = (
            f"If you also do optional CONSIDER trims (~₹{consider_proceeds:,.0f} extra proceeds), "
            f"net cash deployment becomes ₹{net_with_trims:+,.0f}"
        )
    else:
        out['optionalTrimNote'] = ''
    if skip_proceeds > 0:
        out['skipNote'] = (
            f"If you also exit SKIP/optional positions (~₹{skip_proceeds:,.0f}), "
            f"net becomes ₹{net_with_skip:+,.0f}"
        )
    else:
        out['skipNote'] = ''
    if user_input > 0:
        if net_min <= 0:
            out['budgetStatus'] = 'surplus'
            out['budgetNote'] = f"SELLs cover all BUYs — surplus ₹{user_input + abs(net_min):,.0f}"
        elif net_min <= user_input:
            out['budgetStatus'] = 'within'
            out['budgetNote'] = f"Within budget — leftover ₹{user_input - net_min:,.0f}"
        else:
            out['budgetStatus'] = 'shortfall'
            out['budgetNote'] = f"Need ₹{net_min - user_input:,.0f} more on top of ₹{user_input:,.0f}"
    elif net_min < 0:
        out['budgetStatus'] = 'surplus'
        out['budgetNote'] = f"You get ₹{abs(net_min):,.0f} back (no new capital)"
    else:
        out['budgetStatus'] = 'need'
        out['budgetNote'] = f"You need ₹{net_min:,.0f} new capital"
    return out


def _build_tax_harvest(df: pd.DataFrame) -> Optional[dict]:
    if 'ACTION' not in df.columns or 'P&L %' not in df.columns:
        return None
    mask = df['ACTION'].astype(str).str.contains('SELL', case=False, na=False)
    sells = df.loc[mask]
    if sells.empty:
        return None
    bk = pd.to_numeric(sells.get('BOOK ₹'), errors='coerce').fillna(0)
    pnl_pct = pd.to_numeric(sells.get('P&L %'), errors='coerce').fillna(0)
    unit = pnl_pct / (100.0 if pnl_pct.abs().max() > 1 else 1.0)
    cost = bk / (1.0 + unit).replace(0, 1.0)
    pnl_inr = bk - cost
    losses = float(pnl_inr[pnl_inr < 0].sum())
    gains = float(pnl_inr[pnl_inr > 0].sum())
    tax = float(pd.to_numeric(sells.get('TAX ₹'), errors='coerce').fillna(0).sum())
    return {
        'losses': int(abs(losses)),
        'gains': int(gains),
        'netPnl': int(gains + losses),
        'taxPayable': int(tax),
        'note': 'Losses can offset other STCG/LTCG (8-year carry-forward)' if losses else '',
    }


def _build_risk_profile(df: pd.DataFrame) -> Optional[dict]:
    val_col, owned = 'MY VALUE ₹', 'OWNED?'
    if val_col not in df.columns:
        return None
    if owned in df.columns:
        hold = df[df[owned].astype(str).str.upper().eq('YES')].copy()
    else:
        hold = df[df[val_col] > 0].copy()
    if hold.empty:
        return None
    w = pd.to_numeric(hold[val_col], errors='coerce').fillna(0)
    w_sum = float(w.sum())
    if w_sum <= 0:
        return None
    vol_col = 'VOLATILITY %' if 'VOLATILITY %' in hold.columns else None
    vol = pd.to_numeric(hold[vol_col], errors='coerce').fillna(30.0) if vol_col else pd.Series(30.0, index=hold.index)
    wv = float((vol * w).sum() / w_sum)
    daily = wv / (252 ** 0.5)
    var_95 = w_sum * (daily / 100.0) * 1.65
    worst_sym, worst_pnl = '', 0.0
    if 'P&L %' in hold.columns:
        pnl = pd.to_numeric(hold['P&L %'], errors='coerce')
        if pnl.notna().any():
            wi = pnl.idxmin()
            worst_sym = str(hold.loc[wi, 'symbol'])
            worst_pnl = float(pnl.min())
    return {
        'portfolioValue': int(w_sum),
        'volatilityPct': round(wv, 1),
        'var95': int(var_95),
        'worstSymbol': worst_sym,
        'worstPnlPct': round(worst_pnl, 1),
    }


def _build_risk_warnings(df: pd.DataFrame, regime: str) -> List[str]:
    warnings: List[str] = []
    regime_u = str(regime or '').upper()
    if regime_u in ('BEAR', 'BEARISH'):
        warnings.append('BEAR MARKET — all new positions carry elevated risk')
    buys = df[(df['MY VALUE ₹'] == 0) & (df['INVEST ₹'] > 0)] if 'INVEST ₹' in df.columns else pd.DataFrame()
    inc = df[df['ACTION'].astype(str).str.contains('INCREASE', na=False)] if 'ACTION' in df.columns else pd.DataFrame()
    combined = pd.concat([buys, inc], ignore_index=True) if len(buys) + len(inc) else pd.DataFrame()
    for _, r in combined.iterrows():
        sym = str(r.get('symbol', ''))
        vol = r.get('VOLATILITY %', 0)
        risk = str(r.get('RISK CAT', r.get('RISK', '')))
        if vol and float(vol) > 40:
            warnings.append(f'{sym}: HIGH volatility ({float(vol):.1f}%)')
        if 'HIGH' in risk.upper() or 'VERY' in risk.upper():
            warnings.append(f'{sym}: {risk} risk')
    return warnings[:12]


def _build_sector_concentration(df: pd.DataFrame) -> List[dict]:
    if 'sector' not in df.columns:
        return []
    try:
        from config import get_config
        cap = int(getattr(get_config(), 'SECTOR_CAP', 4))
    except Exception:
        cap = 4
    counts = df['sector'].fillna('Unknown').value_counts().to_dict()
    return [
        {'sector': s, 'count': c, 'overCap': c > cap}
        for s, c in sorted(counts.items(), key=lambda x: -x[1])
        if c > 1
    ]


def _build_partial_execution(df: pd.DataFrame) -> Optional[dict]:
    val, act = 'MY VALUE ₹', 'ACTION'
    if 'sector' not in df.columns or val not in df.columns:
        return None
    hold = df[df[val] > 0].copy()
    if hold.empty:
        return None
    sell_set = set(hold[hold[act].astype(str).str.upper().str.contains('SELL', na=False)]['symbol'].tolist())
    if not sell_set:
        return None
    total = len(hold)
    sect = hold['sector'].fillna('Unknown').value_counts()
    top = str(sect.index[0])
    top_n = int(sect.iloc[0])
    conc_pct = round(top_n / total * 100) if total else 0
    if conc_pct < 40:
        return None
    partial = hold[~(
        (hold['symbol'].isin(sell_set)) &
        (~hold['sector'].fillna('').astype(str).str.contains(top.split()[0], na=False, regex=False))
    )]
    ha_sect = partial['sector'].fillna('Unknown').value_counts()
    ha_top = str(ha_sect.index[0]) if len(ha_sect) else '-'
    ha_n = int(ha_sect.iloc[0]) if len(ha_sect) else 0
    ha_pct = round(ha_n / len(partial) * 100) if len(partial) else 0
    sells_in_top = sum(
        1 for s in sell_set
        if top.split()[0] in str(hold[hold['symbol'] == s]['sector'].iloc[0])
    )
    return {
        'topSector': top,
        'topCount': top_n,
        'totalHoldings': total,
        'concPct': conc_pct,
        'sellCount': len(sell_set),
        'sellsInTop': sells_in_top,
        'ifPartialOnly': f'{ha_top} would be {ha_n}/{len(partial)} ({ha_pct}%)',
        'worsens': ha_pct > conc_pct,
        'recommendation': f'Execute SELLs in overweight sector ({top}) FIRST',
    }


def _f(r: pd.Series, col: str, default: float = 0.0) -> float:
    try:
        v = pd.to_numeric(r.get(col, default), errors='coerce')
        return float(v) if pd.notna(v) else default
    except Exception:
        return default


def _s(r: pd.Series, col: str, maxlen: int = 0) -> str:
    v = str(r.get(col, '') or '').strip()
    if maxlen and len(v) > maxlen:
        return v[:maxlen]
    return v


def _enrich_priority_row(r: pd.Series, sym: str, detail: str, amount: str) -> dict:
    book = _f(r, 'BOOK %')
    book_pct = round(book * 100, 0) if 0 < book <= 1 else round(book, 0)
    return {
        'stock': _s(r, sym),
        'detail': detail,
        'amount': amount,
        'when': _s(r, 'WHEN', 24),
        'reason': _s(r, 'REASON', 160),
        'sector': _s(r, 'sector', 28),
        'score': round(_f(r, 'SCORE'), 1),
        'adjScore': round(_f(r, 'ADJ SCORE'), 1),
        'v2Score': round(_f(r, 'V2 RAW'), 1),
        'v1Score': round(_f(r, 'V1 RAW'), 1),
        'pnlPct': round(_f(r, 'P&L %'), 1),
        'ml': _s(r, 'ML', 12),
        'mlConf': round(_f(r, 'ML CONF %'), 0),
        'risk': _s(r, 'RISK CAT', 16),
        'stopLoss': round(_f(r, 'STOP LOSS'), 2),
        'stopTier': _s(r, 'STOP TIER', 20),
        'bookPct': book_pct,
        'price': round(_f(r, 'PRICE'), 2),
        'qty': int(_f(r, 'MY QTY')),
        'type': _s(r, 'TYPE', 16),
        'sleeve': _s(r, 'SLEEVE', 16),
    }


def _build_allocation_master(df: pd.DataFrame) -> List[dict]:
    rows = []
    for _, r in df.iterrows():
        book = _f(r, 'BOOK %')
        rows.append({
            'stock': _s(r, 'symbol'),
            'company': _s(r, 'company_name', 40),
            'action': _s(r, 'ACTION'),
            'when': _s(r, 'WHEN'),
            'score': round(_f(r, 'SCORE'), 1),
            'adjScore': round(_f(r, 'ADJ SCORE'), 1),
            'v1Score': round(_f(r, 'V1 RAW'), 1),
            'v2Score': round(_f(r, 'V2 RAW'), 1),
            'v2delta': round(_f(r, 'V2-V1 RAW Δ'), 1),
            'pnlPct': round(_f(r, 'P&L %'), 1),
            'value': int(_f(r, 'MY VALUE ₹')),
            'invest': int(_f(r, 'INVEST ₹')),
            'qty': int(_f(r, 'MY QTY')),
            'buyQty': int(_f(r, 'BUY QTY')),
            'avgCost': round(_f(r, 'avg_cost'), 2),
            'price': round(_f(r, 'PRICE'), 2),
            'bookPct': round(book * 100, 0) if 0 < book <= 1 else round(book, 0),
            'bookInr': int(_f(r, 'BOOK ₹')),
            'taxInr': int(_f(r, 'TAX ₹')),
            'netInr': int(_f(r, 'NET ₹')),
            'sector': _s(r, 'sector'),
            'ml': _s(r, 'ML'),
            'mlConf': round(_f(r, 'ML CONF %'), 0),
            'risk': _s(r, 'RISK CAT'),
            'owned': _s(r, 'OWNED?'),
            'reason': _s(r, 'REASON', 200),
            'detail': _s(r, 'DETAIL', 120),
            'quality': round(_f(r, 'QUALITY'), 1),
            'momentum': round(_f(r, 'MOMENTUM'), 1),
            'growth': round(_f(r, 'GROWTH'), 1),
            'valueScore': round(_f(r, 'VALUE'), 1),
            'vol': round(_f(r, 'VOL'), 1),
            'mtf': round(_f(r, 'MTF'), 1),
            'riskComp': round(_f(r, 'RISK'), 1),
            'underval': round(_f(r, 'UNDERVAL'), 1),
            'pe': round(_f(r, 'PE'), 1),
            'roe': round(_f(r, 'ROE %'), 1),
            'de': round(_f(r, 'D/E'), 2),
            'rsi': round(_f(r, 'RSI'), 1),
            'volatility': round(_f(r, 'VOLATILITY %'), 1),
            'chg20d': round(_f(r, '20D CHG %'), 1),
            'high52': round(_f(r, '52W HIGH'), 2),
            'low52': round(_f(r, '52W LOW'), 2),
            'support': round(_f(r, 'SUPPORT'), 2),
            'resist': round(_f(r, 'RESIST'), 2),
            'stopLoss': round(_f(r, 'STOP LOSS'), 2),
            'stopTier': _s(r, 'STOP TIER'),
            'rank': int(_f(r, 'RANK')),
            'weightPct': round(_f(r, 'WT %'), 2),
            'rotTarget': _s(r, 'ROT TARGET'),
            'rotPrice': round(_f(r, 'ROT PRICE'), 2),
            'cooldown': _s(r, 'cooldown_suppression_reason', 80),
            'type': _s(r, 'TYPE'),
            'sleeve': _s(r, 'SLEEVE'),
        })
    return rows


def _build_holdings_enriched(df: pd.DataFrame, holdings: List[dict]) -> List[dict]:
    by_sym = {str(r.get('symbol', '')): r for _, r in df.iterrows()} if 'symbol' in df.columns else {}
    out = []
    for h in holdings:
        sym = h['stock']
        r = by_sym.get(sym)
        row = dict(h)
        if r is not None:
            row.update({
                'action': _s(r, 'ACTION'),
                'when': _s(r, 'WHEN'),
                'score': round(_f(r, 'SCORE'), 1),
                'v2Score': round(_f(r, 'V2 RAW'), 1),
                'pnlPctAlloc': round(_f(r, 'P&L %'), 1),
                'sector': _s(r, 'sector'),
                'stopLoss': round(_f(r, 'STOP LOSS'), 2),
                'ml': _s(r, 'ML'),
                'reason': _s(r, 'REASON', 100),
            })
        out.append(row)
    return out


def _build_sector_chart(holdings_enriched: List[dict]) -> List[dict]:
    sect_val: Dict[str, float] = {}
    for h in holdings_enriched:
        s = h.get('sector') or 'Unknown'
        sect_val[s] = sect_val.get(s, 0) + h.get('value', 0)
    return [{'name': k, 'value': int(v)} for k, v in sorted(sect_val.items(), key=lambda x: -x[1])]


def _load_report_extras(report_path: Path) -> dict:
    extras: dict = {
        'topPicks': [], 'tradingLevels': [], 'undervalued': [],
        'sectorAnalysis': [], 'portfolioSummary': {}, 'weeklyChanges': [],
    }
    if not report_path.exists():
        return extras

    def _rows(frame: pd.DataFrame, mapping: dict, limit: int = 25) -> List[dict]:
        out = []
        for _, r in frame.head(limit).iterrows():
            out.append({k: (round(float(r[src]), 1) if isinstance(r.get(src), (int, float)) and k.endswith('Score')
                          else str(r.get(src, ''))[:60] if isinstance(r.get(src), str) else r.get(src, ''))
                        for k, src in mapping.items() if src in r.index or src in frame.columns})
        return out

    try:
        tp = pd.read_excel(report_path, sheet_name='Top Picks')
        for _, r in tp.head(20).iterrows():
            extras['topPicks'].append({
                'stock': str(r.get('symbol', '')),
                'company': str(r.get('company_name', ''))[:35],
                'sector': str(r.get('sector', '')),
                'score': round(float(r.get('final_blended_score', 0) or 0), 1),
                'underval': round(float(r.get('undervaluation_score', 0) or 0), 1),
                'risk': str(r.get('risk_category', '')),
                'rec': str(r.get('final_recommendation', '')),
                'price': round(float(r.get('current_price', 0) or 0), 2),
            })
    except Exception:
        pass

    try:
        tl = pd.read_excel(report_path, sheet_name='Trading Levels')
        for _, r in tl.head(25).iterrows():
            extras['tradingLevels'].append({
                'stock': str(r.get('symbol', '')),
                'signal': str(r.get('SIGNAL', '')),
                'price': round(float(r.get('PRICE', 0) or 0), 2),
                'entry': f"{round(float(r.get('ENTRY_LOW', 0) or 0), 0)}-{round(float(r.get('ENTRY_HIGH', 0) or 0), 0)}",
                'target1': round(float(r.get('TARGET_1', 0) or 0), 2),
                'target2': round(float(r.get('TARGET_2', 0) or 0), 2),
                'stop': round(float(r.get('STOP_LOSS', 0) or 0), 2),
                'rr': str(r.get('RISK_REWARD', '')),
                'strategy': str(r.get('STRATEGY', ''))[:40],
            })
    except Exception:
        pass

    try:
        uv = pd.read_excel(report_path, sheet_name='Undervalued')
        for _, r in uv.head(15).iterrows():
            extras['undervalued'].append({
                'stock': str(r.get('symbol', '')),
                'company': str(r.get('company_name', ''))[:35],
                'score': round(float(r.get('undervaluation_score', 0) or 0), 1),
                'pe': round(float(r.get('pe_ratio', 0) or 0), 1),
                'roe': round(float(r.get('roe', 0) or 0), 1),
                'rec': str(r.get('final_recommendation', '')),
                'price': round(float(r.get('current_price', 0) or 0), 2),
            })
    except Exception:
        pass

    try:
        sa = pd.read_excel(report_path, sheet_name='Sector Analysis')
        col0 = sa.columns[0]
        for _, r in sa.iterrows():
            name = str(r.get(col0, ''))
            if not name or name == 'nan':
                continue
            extras['sectorAnalysis'].append({
                'sector': name,
                'count': int(r.get('count', 0) or 0),
                'avgScore': round(float(r.get('avg_overall_score', 0) or 0), 1),
                'avgFund': round(float(r.get('avg_fundamental_score', 0) or 0), 1),
                'avgTech': round(float(r.get('avg_technical_score', 0) or 0), 1),
                'strongBuy': int(r.get('strong_buy_count', 0) or 0),
                'buyCount': int(r.get('buy_count', 0) or 0),
            })
    except Exception:
        pass

    try:
        ps = pd.read_excel(report_path, sheet_name='Portfolio Summary')
        if not ps.empty:
            r = ps.iloc[0]
            extras['portfolioSummary'] = {
                'totalStocks': int(r.get('total_stocks', 0) or 0),
                'holdings': int(r.get('current_holdings', 0) or 0),
                'toSell': int(r.get('positions_to_sell', 0) or 0),
                'toHold': int(r.get('positions_to_hold', 0) or 0),
                'newPositions': int(r.get('new_positions', 0) or 0),
                'saleProceeds': int(r.get('sale_proceeds', 0) or 0),
                'newCapital': int(r.get('new_capital', 0) or 0),
                'availableFunds': int(r.get('available_funds', 0) or 0),
                'portfolioValue': int(r.get('current_portfolio_value', 0) or 0),
                'targetValue': int(r.get('total_target_portfolio_value', 0) or 0),
                'marketRegime': str(r.get('market_regime', '')),
                'exposurePct': round(float(r.get('recommended_exposure', 0) or 0) * 100, 0),
                'cashReserve': int(r.get('cash_reserve', 0) or 0),
                'avgScore': round(float(r.get('avg_score', 0) or 0), 1),
                'sectorCount': int(r.get('sector_count', 0) or 0),
                'utilization': round(float(r.get('portfolio_utilization', 0) or 0), 1),
            }
    except Exception:
        pass

    try:
        wc = pd.read_excel(report_path, sheet_name='Weekly Changes')
        for _, r in wc.iterrows():
            sym = str(r.get('symbol', '')).strip()
            if not sym or sym == 'nan':
                continue
            chg = float(r.get('change', 0) or 0)
            extras['weeklyChanges'].append({
                'stock': sym,
                'current': round(float(r.get('current_score', 0) or 0), 1),
                'previous': round(float(r.get('previous_score', 0) or 0), 1),
                'change': round(chg, 1),
                'action': str(r.get('action', '')),
                'direction': str(r.get('direction', '')),
                'tone': 'success' if chg > 0 else 'danger' if chg < 0 else 'neutral',
            })
    except Exception:
        pass

    return extras


def _build_mtf_for_book(df: pd.DataFrame, report_path: Path) -> List[dict]:
    """MTF rows for holdings + new buys only (Turbo MTF cockpit)."""
    if 'symbol' not in df.columns:
        return []
    book_syms = set()
    for _, r in df.iterrows():
        sym = str(r.get('symbol', '')).strip()
        if not sym:
            continue
        owned = str(r.get('OWNED?', '')).upper() == 'YES'
        is_new = 'NEW POSITION' in str(r.get('ACTION', '')).upper()
        has_value = float(r.get('MY VALUE ₹', 0) or 0) > 0
        if owned or is_new or has_value:
            book_syms.add(sym.upper())

    if not book_syms or not report_path.exists():
        return []

    mtf_sheet = None
    try:
        xl = pd.ExcelFile(report_path)
        for name in xl.sheet_names:
            if 'Multi-Timeframe' in name or 'MTF' in name.upper():
                mtf_sheet = name
                break
    except Exception:
        return []

    if not mtf_sheet:
        return []

    try:
        mtf = pd.read_excel(report_path, sheet_name=mtf_sheet)
    except Exception:
        return []

    sym_col = 'Symbol' if 'Symbol' in mtf.columns else 'symbol'
    rows = []
    for _, r in mtf.iterrows():
        sym = str(r.get(sym_col, '')).strip().upper()
        if sym not in book_syms:
            continue
        agree = float(r.get('Agreement %', 0) or 0)
        rows.append({
            'stock': str(r.get(sym_col, '')),
            'daily': str(r.get('Daily Trend', '')),
            'weekly': str(r.get('Weekly Trend', '')),
            'monthly': str(r.get('Monthly Trend', '')),
            'signal': str(r.get('MTF Signal', '')),
            'agreement': round(agree, 0),
            'mtfScore': round(float(r.get('MTF Score', 0) or 0), 1),
            'quality': str(r.get('Signal Quality', '')),
            'rec': str(r.get('Recommendation', '')),
            'aligned': agree >= 66,
        })
    rows.sort(key=lambda x: (-x['mtfScore'], x['stock']))
    return rows


def _build_dual_strategy(allocation_df: pd.DataFrame) -> List[dict]:
    try:
        from config import get_config
        profiles = getattr(get_config(), 'DUAL_STRATEGY_PROFILES', {}) or {}
    except Exception:
        return []
    if not profiles or allocation_df.empty:
        return []
    sym_col = 'symbol'
    act_col = 'ACTION'
    keys = list(profiles.keys())
    if len(keys) < 2:
        return []
    turbo_w = profiles[keys[0]].get('weights', {})
    monthly_w = profiles[keys[1]].get('weights', {})
    turbo_scores = _rescore(allocation_df, turbo_w)
    monthly_scores = _rescore(allocation_df, monthly_w)
    rows = []
    for i, r in allocation_df.iterrows():
        ts, ms = float(turbo_scores.at[i]), float(monthly_scores.at[i])
        t_sig, m_sig = _signal_from_score(ts), _signal_from_score(ms)
        if t_sig == 'BUY' and m_sig == 'BUY':
            agree = 'BUY (both agree)'
        elif t_sig in ('SELL', 'WEAK SELL') and m_sig in ('SELL', 'WEAK SELL'):
            agree = 'SELL (both agree)'
        else:
            agree = 'SPLIT'
        rows.append({
            'stock': str(r.get(sym_col, '')),
            'primary': str(r.get(act_col, 'HOLD')),
            'turbo': round(ts, 1),
            'monthly': round(ms, 1),
            'turboSig': t_sig,
            'monthlySig': m_sig,
            'agree': agree,
            'owned': str(r.get('OWNED?', '')),
        })
    rows.sort(key=lambda x: (-x['turbo'], x['stock']))
    return rows


def _load_holdings(repo_root: Path) -> List[dict]:
    merged = sorted((repo_root / 'reports').glob('merged_portfolio_*.xlsx'))
    if not merged:
        return []
    df = pd.read_excel(merged[-1])
    if 'Qty.' not in df.columns:
        return []
    df = df[df['Qty.'] > 0].copy().sort_values('Cur. val', ascending=False)
    return [{
        'stock': str(r['Instrument']),
        'qty': int(r['Qty.']),
        'value': int(round(float(r['Cur. val']))),
        'pnl': int(round(float(r.get('P&L', 0) or 0))),
        'pnlPct': round(float(r.get('P&L %', 0) or 0), 1) if 'P&L %' in df.columns else 0,
    } for _, r in df.iterrows()]


def _load_trust_metrics(repo_root: Path, report_path: Optional[Path] = None) -> dict:
    win_rate, spread, trust = 47.8, 2.2, 'Partly reliable'
    rec_n, expectancy = 0, 0.0
    wf_verdict, wf_reason, promotion = '—', '', 'Unknown'

    if report_path and report_path.exists():
        try:
            rp = pd.read_excel(report_path, sheet_name='Rec Performance')
            row30 = rp[rp['Horizon'].astype(str).str.strip() == '30d']
            if not row30.empty:
                r = row30.iloc[0]
                wr = pd.to_numeric(r.get('Win Rate %'), errors='coerce')
                if pd.notna(wr):
                    win_rate = float(wr)
                rec_n = int(pd.to_numeric(r.get('Recommendations'), errors='coerce') or 0)
                exp = pd.to_numeric(r.get('Expectancy %'), errors='coerce')
                if pd.notna(exp):
                    expectancy = float(exp)
        except Exception:
            pass

    wf_path = repo_root / 'data' / 'walkforward_v2_validation_fixed_turbo.json'
    if wf_path.exists():
        try:
            wf = json.loads(wf_path.read_text())
            v2 = (wf.get('primary_80_20') or {}).get('v2') or {}
            ic = v2.get('ic_30d')
            spread = float(v2.get('spread_pp') or spread)
            verdict_obj = wf.get('verdict') or {}
            if isinstance(verdict_obj, dict):
                promotion = str(verdict_obj.get('verdict', 'HOLD_SHADOW'))
                wf_reason = str(verdict_obj.get('reason', ''))[:120]
            else:
                promotion = str(verdict_obj)
            wf_verdict = promotion
            if ic is not None and ic >= 0.05 and spread >= 3.0:
                trust = 'Ranking works (OOS test)'
            elif ic is not None and ic > 0:
                trust = 'Partly reliable — spread < 3pp'
            else:
                trust = 'Use with caution'
        except Exception:
            pass

    return {
        'winRate30d': round(win_rate, 1),
        'topBeatBottomPct': round(spread, 1),
        'trustLabel': trust,
        'recCount30d': rec_n,
        'expectancy30d': round(expectancy, 2),
        'promotion': promotion,
        'wfReason': wf_reason,
    }


def _hold_note(df: pd.DataFrame, holdings: List[dict]) -> str:
    held = {h['stock'] for h in holdings}
    new_buys = set(df.loc[df['ACTION'].astype(str).str.contains('NEW POSITION', na=False), 'symbol'].astype(str))
    overlap = sorted(held & new_buys)
    if overlap:
        return f'Do not buy {", ".join(overlap)} again — already in portfolio (hold only).'
    return ''


def _action_summary(df: pd.DataFrame) -> List[dict]:
    if 'ACTION' not in df.columns:
        return []
    counts = df['ACTION'].astype(str).value_counts()
    return [{'action': str(a), 'count': int(c)} for a, c in counts.items()]


def generate_canvas_tsx(
    report_file: str,
    allocation_df: pd.DataFrame,
    portfolio_amount: float = 0,
    regime: str = 'Sideways',
    repo_root: Path | None = None,
) -> str:
    root = repo_root or REPO_ROOT
    df = _prep_numeric(_normalize_allocation_df(allocation_df.copy()))
    run_date = datetime.now().strftime('%d %b %Y')
    report_name = Path(report_file).name

    report_path = Path(report_file)
    if not report_path.is_absolute():
        report_path = root / report_path

    sections, totals = _build_action_plan_sections(df)
    final_numbers = _build_final_numbers(totals, portfolio_amount)
    holdings = _load_holdings(root)
    holdings_enriched = _build_holdings_enriched(df, holdings)
    dual = _build_dual_strategy(df)
    trust = _load_trust_metrics(root, report_path)
    hold_note = _hold_note(df, holdings)
    extras = _load_report_extras(report_path)
    ps = extras.get('portfolioSummary') or {}
    mtf_book = _build_mtf_for_book(df, report_path)

    payload = {
        'runDate': run_date,
        'report': report_name,
        'regime': str(regime) or ps.get('marketRegime', 'Sideways'),
        'positions': len(holdings) or int((df['MY VALUE ₹'] > 0).sum()) if 'MY VALUE ₹' in df.columns else 0,
        'portfolioValue': sum(h['value'] for h in holdings) or int(df.loc[df['MY VALUE ₹'] > 0, 'MY VALUE ₹'].sum()) if 'MY VALUE ₹' in df.columns else 0,
        'trust': trust,
        'holdNote': hold_note,
        'sections': sections,
        'finalNumbers': final_numbers,
        'taxHarvest': _build_tax_harvest(df),
        'riskProfile': _build_risk_profile(df),
        'riskWarnings': _build_risk_warnings(df, regime),
        'sectorConcentration': _build_sector_concentration(df),
        'partialExecution': _build_partial_execution(df),
        'holdings': holdings_enriched,
        'sectorChart': _build_sector_chart(holdings_enriched),
        'allocationMaster': _build_allocation_master(df),
        'dualStrategy': dual,
        'actionSummary': _action_summary(df),
        'portfolioSummary': ps,
        'topPicks': extras.get('topPicks', []),
        'tradingLevels': extras.get('tradingLevels', []),
        'undervalued': extras.get('undervalued', []),
        'sectorAnalysis': extras.get('sectorAnalysis', []),
        'weeklyChanges': extras.get('weeklyChanges', []),
        'mtfBook': mtf_book,
    }

    data_js = _tsx_data(payload)

    return f'''import {{
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  CollapsibleSection,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  PieChart,
  Row,
  Stack,
  Stat,
  Table,
  Text,
}} from 'cursor/canvas';

const DATA = {data_js} as const;

function fmtLakh(n: number): string {{
  if (n >= 100000) return `₹${{(n / 100000).toFixed(2)}}L`;
  if (n >= 1000) return `₹${{(n / 1000).toFixed(1)}}k`;
  return `₹${{Math.round(n)}}`;
}}

function sectionTone(tone: string): 'danger' | 'warning' | 'success' | 'info' | undefined {{
  if (tone === 'danger') return 'danger';
  if (tone === 'warning') return 'warning';
  if (tone === 'success') return 'success';
  if (tone === 'info') return 'info';
  return undefined;
}}

function actionRowTone(action: string): 'danger' | 'warning' | 'success' | 'info' | undefined {{
  const a = action.toUpperCase();
  if (a === 'SELL' || a.includes('WEAK SELL')) return 'danger';
  if (a.includes('CONSIDER') || a.includes('REDUCE') || a.includes('BOOK')) return 'warning';
  if (a.includes('BUY') || a.includes('INCREASE') || a.includes('NEW')) return 'success';
  return undefined;
}}

function pnlTone(pnl: number): 'success' | 'danger' | undefined {{
  if (pnl > 0) return 'success';
  if (pnl < 0) return 'danger';
  return undefined;
}}

function PriorityBlock({{ section }}: {{ section: (typeof DATA.sections)[0] }}) {{
  const headers = ['Stock', 'When', 'Detail', 'Amount', 'Score', 'V2', 'P&L%', 'Sector', 'ML', 'Stop', 'Reason'];
  const rows = section.rows.map((r) => [
    r.stock,
    r.when || '—',
    r.detail,
    r.amount,
    String(r.score ?? '—'),
    String(r.v2Score ?? '—'),
    r.pnlPct !== undefined ? `${{r.pnlPct}}%` : '—',
    r.sector || '—',
    r.ml ? `${{r.ml}} (${{r.mlConf}}%)` : '—',
    r.stopLoss ? `₹${{r.stopLoss}}` : '—',
    r.reason || '—',
  ]);
  return (
    <Stack gap={{8}}>
      <Row gap={{8}} align="center">
        <H3>{{section.title}}</H3>
        {{section.totalValue ? <Pill tone={{sectionTone(section.tone)}}>{{section.totalValue}}</Pill> : null}}
      </Row>
      <Table headers={{headers}} rows={{rows}} rowTone={{section.rows.map(() => sectionTone(section.tone))}} />
    </Stack>
  );
}}

export default function StockAnalysisDashboard() {{
  const fn = DATA.finalNumbers;
  const ps = DATA.portfolioSummary;
  const budgetTone = fn.budgetStatus === 'surplus' || fn.budgetStatus === 'within' ? 'success' : 'warning';
  const owned = DATA.allocationMaster.filter((r) => r.owned === 'YES' || r.value > 0);

  return (
    <Stack gap={{28}}>
      <Stack gap={{6}}>
        <H1>Full analysis dashboard</H1>
        <Text tone="secondary" size="small">
          {{DATA.report}} · {{DATA.runDate}} · Regime: {{DATA.regime}} · Turbo MTF weekly
        </Text>
      </Stack>

      <Grid columns={{4}} gap={{12}}>
        <Stat value={{fmtLakh(DATA.portfolioValue)}} label="Portfolio value" />
        <Stat value={{String(DATA.positions)}} label="Holdings" />
        <Stat value={{fmtLakh(fn.buyOrders)}} label="Total buys" tone="success" />
        <Stat value={{fmtLakh(fn.sellProceeds)}} label="Total sells" tone="danger" />
      </Grid>

      <Card>
        <CardHeader title="Trust strip — should I follow this run?" />
        <CardBody>
          <Grid columns={{4}} gap={{12}}>
            <Stat value={{`${{DATA.trust.winRate30d}}%`}} label="Rec win rate (30d)" tone="warning" />
            <Stat value={{`+${{DATA.trust.topBeatBottomPct}}%`}} label="OOS top-bottom spread" tone="success" />
            <Stat value={{DATA.trust.promotion}} label="v2 promotion state" tone="info" />
            <Stat value={{DATA.trust.trustLabel}} label="Overall" />
          </Grid>
          <Text size="small" tone="secondary">
            {{DATA.trust.recCount30d}} recommendations tracked · expectancy {{DATA.trust.expectancy30d}}% (30d)
          </Text>
          {{DATA.trust.wfReason ? <Text size="small" tone="secondary">{{DATA.trust.wfReason}}</Text> : null}}
        </CardBody>
      </Card>

      {{DATA.weeklyChanges.length > 0 ? (
        <>
          <Divider />
          <H2>What changed since last run</H2>
          <Text tone="secondary" size="small">Weekly score moves — focus on IMPROVED/DETERIORATED in your book.</Text>
          <Table
            headers={{['Stock', 'Was', 'Now', 'Δ', 'Action', 'Direction']}}
            rows={{DATA.weeklyChanges.map((w) => [
              w.stock,
              String(w.previous),
              String(w.current),
              (w.change > 0 ? '+' : '') + String(w.change),
              w.action,
              w.direction,
            ])}}
            rowTone={{DATA.weeklyChanges.map((w) =>
              w.tone === 'success' ? 'success' : w.tone === 'danger' ? 'danger' : undefined,
            )}}
          />
        </>
      ) : null}}

      {{Object.keys(ps).length > 0 ? (
        <Card>
          <CardHeader title="Portfolio summary (Excel)" />
          <CardBody>
            <Grid columns={{4}} gap={{12}}>
              <Stat value={{String(ps.holdings)}} label="Current holdings" />
              <Stat value={{String(ps.toSell)}} label="To sell" tone="danger" />
              <Stat value={{String(ps.toHold)}} label="To hold" />
              <Stat value={{String(ps.newPositions)}} label="New positions" tone="success" />
              <Stat value={{fmtLakh(ps.newCapital)}} label="New capital needed" />
              <Stat value={{fmtLakh(ps.availableFunds)}} label="Available funds" />
              <Stat value={{String(ps.avgScore)}} label="Avg score" />
              <Stat value={{`${{ps.exposurePct}}%`}} label="Recommended exposure" />
              <Stat value={{`${{ps.utilization}}%`}} label="Portfolio utilization" />
              <Stat value={{String(ps.sectorCount)}} label="Sectors" />
            </Grid>
          </CardBody>
        </Card>
      ) : null}}

      <Card>
        <CardHeader title="Final numbers (MIN vs optional MAX)" />
        <CardBody>
          <Grid columns={{4}} gap={{12}}>
            <Stat value={{fmtLakh(fn.sellProceeds)}} label="Sell proceeds (required)" />
            <Stat value={{fmtLakh(fn.buyOrders)}} label="Buy orders" />
            <Stat value={{`₹${{fn.netMin.toLocaleString('en-IN')}}`}} label="Net MIN (P1–P5)" tone={{budgetTone}} />
            <Stat value={{`₹${{fn.netWithOptionalTrims.toLocaleString('en-IN')}}`}} label="Net if optional trims" tone="warning" />
          </Grid>
          <Text size="small" tone={{budgetTone}}>{{fn.budgetNote}}</Text>
          {{fn.optionalTrimNote ? <Text size="small" tone="warning">{{fn.optionalTrimNote}}</Text> : null}}
          {{fn.skipNote ? <Text size="small" tone="secondary">{{fn.skipNote}}</Text> : null}}
        </CardBody>
      </Card>

      {{DATA.holdNote ? <Callout tone="warning" title="Important"><Text size="small">{{DATA.holdNote}}</Text></Callout> : null}}

      {{DATA.mtfBook.length > 0 ? (
        <>
          <Divider />
          <H2>Turbo MTF — your book only</H2>
          <Text tone="secondary" size="small">Daily / weekly / monthly alignment for holdings + new buys.</Text>
          <Table
            headers={{['Stock', 'Daily', 'Weekly', 'Monthly', 'Signal', 'Agree%', 'MTF', 'Rec']}}
            rows={{DATA.mtfBook.map((m) => [
              m.stock,
              m.daily,
              m.weekly,
              m.monthly,
              m.signal,
              `${{m.agreement}}%`,
              String(m.mtfScore),
              m.rec,
            ])}}
            rowTone={{DATA.mtfBook.map((m) =>
              m.aligned ? 'success' : String(m.signal).toUpperCase().includes('BEAR') ? 'danger' : 'warning',
            )}}
          />
        </>
      ) : null}}

      <Divider />
      <H2>Action plan — full detail per priority</H2>
      {{DATA.sections.map((section) => (
        <CollapsibleSection key={{section.id}} title={{section.title}} count={{section.rows.length}}>
          <PriorityBlock section={{section}} />
        </CollapsibleSection>
      ))}}

      {{DATA.sectorConcentration.length > 0 ? (
        <>
          <Divider /><H2>Your portfolio sector concentration</H2>
          <Table
            headers={{['Sector', 'Stocks', 'Status']}}
            rows={{DATA.sectorConcentration.map((s) => [s.sector, String(s.count), s.overCap ? 'Over cap' : 'OK'])}}
            rowTone={{DATA.sectorConcentration.map((s) => (s.overCap ? 'warning' : undefined))}}
          />
        </>
      ) : null}}

      {{DATA.riskWarnings.length > 0 ? (
        <Callout tone="warning" title="Risk warnings">
          <Stack gap={{4}}>{{DATA.riskWarnings.map((w) => <Text key={{w}} size="small">• {{w}}</Text>)}}</Stack>
        </Callout>
      ) : null}}

      {{DATA.partialExecution ? (
        <Callout tone="warning" title="Partial-execution concentration">
          <Text size="small">{{DATA.partialExecution.topSector}}: {{DATA.partialExecution.topCount}}/{{DATA.partialExecution.totalHoldings}} ({{DATA.partialExecution.concPct}}%). {{DATA.partialExecution.recommendation}}</Text>
        </Callout>
      ) : null}}

      {{DATA.taxHarvest ? (
        <>
          <Divider /><H2>Tax-loss harvest</H2>
          <Grid columns={{4}} gap={{12}}>
            <Stat value={{fmtLakh(DATA.taxHarvest.losses)}} label="Losses" tone="success" />
            <Stat value={{fmtLakh(DATA.taxHarvest.gains)}} label="Gains" />
            <Stat value={{`₹${{DATA.taxHarvest.netPnl.toLocaleString('en-IN')}}`}} label="Net P&L" />
            <Stat value={{fmtLakh(DATA.taxHarvest.taxPayable)}} label="Est. tax" tone="warning" />
          </Grid>
        </>
      ) : null}}

      {{DATA.riskProfile ? (
        <>
          <Divider /><H2>Risk profile</H2>
          <Grid columns={{4}} gap={{12}}>
            <Stat value={{`${{DATA.riskProfile.volatilityPct}}%`}} label="Volatility" tone="warning" />
            <Stat value={{fmtLakh(DATA.riskProfile.var95)}} label="1d VaR 95%" tone="danger" />
            <Stat value={{DATA.riskProfile.worstSymbol}} label="Worst stock" />
            <Stat value={{`${{DATA.riskProfile.worstPnlPct}}%`}} label="Worst P&L" tone="danger" />
          </Grid>
        </>
      ) : null}}

      <Divider />
      <H2>Top picks (universe scan)</H2>
      <Table
        headers={{['#', 'Stock', 'Sector', 'Score', 'Underval', 'Risk', 'Rec', 'Price']}}
        rows={{DATA.topPicks.map((r, i) => [
          String(i + 1), r.stock, r.sector, String(r.score), String(r.underval), r.risk, r.rec, `₹${{r.price}}`,
        ])}}
      />

      <Divider />
      <H2>Trading levels (entry / target / stop)</H2>
      <Table
        headers={{['Stock', 'Signal', 'Price', 'Entry', 'T1', 'T2', 'Stop', 'R:R', 'Strategy']}}
        rows={{DATA.tradingLevels.map((r) => [
          r.stock, r.signal, `₹${{r.price}}`, r.entry, `₹${{r.target1}}`, `₹${{r.target2}}`, `₹${{r.stop}}`, r.rr, r.strategy,
        ])}}
      />

      <Divider />
      <H2>Top undervalued</H2>
      <Table
        headers={{['Stock', 'Score', 'PE', 'ROE', 'Rec', 'Price']}}
        rows={{DATA.undervalued.map((r) => [r.stock, String(r.score), String(r.pe), String(r.roe), r.rec, `₹${{r.price}}`])}}
      />

      <Divider />
      <H2>Sector analysis (universe)</H2>
      <Table
        headers={{['Sector', 'Count', 'Avg score', 'Fund', 'Tech', 'Strong buy', 'Buy']}}
        rows={{DATA.sectorAnalysis.map((s) => [
          s.sector, String(s.count), String(s.avgScore), String(s.avgFund), String(s.avgTech), String(s.strongBuy), String(s.buyCount),
        ])}}
      />

      <Divider />
      <H2>Your holdings + system view</H2>
      {{DATA.sectorChart.length > 0 ? (
        <PieChart data={{DATA.sectorChart.map((s) => ({{ label: s.name, value: s.value }}))}} donut size={{200}} />
      ) : null}}
      <BarChart
        categories={{DATA.holdings.slice(0, 12).map((h) => h.stock)}}
        series={{[{{ name: '₹k', data: DATA.holdings.slice(0, 12).map((h) => Math.round(h.value / 1000)), tone: 'info' }}]}}
        horizontal height={{280}} valueSuffix="k"
      />
      <Table
        headers={{['Stock', 'Qty', 'Value', 'P&L', 'Action', 'When', 'Score', 'V2', 'Sector', 'Stop', 'Reason']}}
        rows={{DATA.holdings.map((h) => [
          h.stock, String(h.qty), fmtLakh(h.value),
          (h.pnl >= 0 ? '+' : '') + fmtLakh(Math.abs(h.pnl)),
          h.action || '—', h.when || '—', String(h.score ?? '—'), String(h.v2Score ?? '—'),
          h.sector || '—', h.stopLoss ? `₹${{h.stopLoss}}` : '—', h.reason || '—',
        ])}}
        rowTone={{DATA.holdings.map((h) => pnlTone(h.pnl))}}
      />

      <Divider />
      <H2>Allocation — actions & scores</H2>
      <Table
        headers={{['Stock', 'Company', 'Action', 'When', 'Score', 'V1', 'V2', 'Δ', 'Adj', 'P&L%', 'Value', 'Invest', 'Qty']}}
        rows={{DATA.allocationMaster.map((r) => [
          r.stock, r.company, r.action, r.when, String(r.score), String(r.v1Score), String(r.v2Score), String(r.v2delta),
          String(r.adjScore), `${{r.pnlPct}}%`, r.value ? fmtLakh(r.value) : '—', r.invest ? fmtLakh(r.invest) : '—', String(r.qty),
        ])}}
        rowTone={{DATA.allocationMaster.map((r) => actionRowTone(r.action))}}
      />

      <CollapsibleSection title="Score components (Q/M/G/V/MTF/Risk)" count={{DATA.allocationMaster.length}}>
        <Table
          headers={{['Stock', 'Qual', 'Mom', 'Growth', 'Value', 'Vol', 'MTF', 'Risk', 'Underval', 'ML', 'ML%']}}
          rows={{DATA.allocationMaster.map((r) => [
            r.stock, String(r.quality), String(r.momentum), String(r.growth), String(r.valueScore),
            String(r.vol), String(r.mtf), String(r.riskComp), String(r.underval), r.ml, String(r.mlConf),
          ])}}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Technical levels & stops" count={{DATA.allocationMaster.length}}>
        <Table
          headers={{['Stock', 'Price', '52H', '52L', '20d%', 'RSI', 'Vol%', 'Support', 'Resist', 'Stop', 'Tier']}}
          rows={{DATA.allocationMaster.map((r) => [
            r.stock, `₹${{r.price}}`, `₹${{r.high52}}`, `₹${{r.low52}}`, `${{r.chg20d}}%`, String(r.rsi),
            `${{r.volatility}}%`, `₹${{r.support}}`, `₹${{r.resist}}`, `₹${{r.stopLoss}}`, r.stopTier,
          ])}}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Fundamentals & tax" count={{DATA.allocationMaster.length}}>
        <Table
          headers={{['Stock', 'PE', 'ROE%', 'D/E', 'Book%', 'Book₹', 'Tax₹', 'Net₹', 'Rank', 'Wt%']}}
          rows={{DATA.allocationMaster.map((r) => [
            r.stock, String(r.pe), String(r.roe), String(r.de), String(r.bookPct),
            r.bookInr ? fmtLakh(r.bookInr) : '—', r.taxInr ? fmtLakh(r.taxInr) : '—', r.netInr ? fmtLakh(r.netInr) : '—',
            String(r.rank), `${{r.weightPct}}%`,
          ])}}
        />
      </CollapsibleSection>

      <CollapsibleSection title="Reasons, rotation & cooldown" count={{DATA.allocationMaster.length}}>
        <Table
          headers={{['Stock', 'Action', 'Reason', 'Detail', 'Rot target', 'Rot ₹', 'Cooldown']}}
          rows={{DATA.allocationMaster.map((r) => [
            r.stock, r.action, r.reason || '—', r.detail || '—', r.rotTarget || '—',
            r.rotPrice ? `₹${{r.rotPrice}}` : '—', r.cooldown || '—',
          ])}}
        />
      </CollapsibleSection>

      <Divider />
      <H2>Dual strategy — all stocks</H2>
      <Table
        headers={{['Stock', 'Plan', 'Turbo', 'Sig', 'Monthly', 'Sig', 'Consensus', 'Owned']}}
        rows={{DATA.dualStrategy.map((r) => [
          r.stock, r.primary, r.turbo.toFixed(1), r.turboSig, r.monthly.toFixed(1), r.monthlySig, r.agree, r.owned,
        ])}}
        rowTone={{DATA.dualStrategy.map((r) => r.agree.includes('SPLIT') ? 'warning' : r.agree.includes('SELL') ? 'danger' : r.agree.includes('BUY') ? 'success' : undefined)}}
      />

      <Divider />
      <H2>Current holdings only ({{owned.length}})</H2>
      <Table
        headers={{['Stock', 'Action', 'Score', 'P&L%', 'Value', 'Stop', 'Sleeve', 'Type']}}
        rows={{owned.map((r) => [
          r.stock, r.action, String(r.score), `${{r.pnlPct}}%`, fmtLakh(r.value), `₹${{r.stopLoss}}`, r.sleeve, r.type,
        ])}}
        rowTone={{owned.map((r) => actionRowTone(r.action))}}
      />

    </Stack>
  );
}}
'''


def update_analysis_canvas(
    report_file: str,
    allocation_df: Optional[pd.DataFrame] = None,
    portfolio_amount: float = 0,
    regime: str = 'Sideways',
    repo_root: Path | None = None,
) -> Optional[Path]:
    root = repo_root or REPO_ROOT
    report_path = Path(report_file)
    if not report_path.is_absolute():
        report_path = root / report_path
    if not report_path.exists():
        print(f'[CANVAS] Skip — report not found: {report_path}')
        return None
    try:
        if allocation_df is None:
            allocation_df = pd.read_excel(report_path, sheet_name='Portfolio Allocation', header=1)
        allocation_df = _normalize_allocation_df(allocation_df)
        if allocation_df is None or allocation_df.empty:
            print('[CANVAS] Skip — empty Portfolio Allocation sheet')
            return None
        content = generate_canvas_tsx(
            str(report_path), allocation_df,
            portfolio_amount=portfolio_amount, regime=regime, repo_root=root,
        )
        out_path = resolve_canvas_dir(root) / CANVAS_NAME
        out_path.write_text(content, encoding='utf-8')
        print(f'[CANVAS] Dashboard updated: {out_path}')
        return out_path
    except Exception as exc:
        print(f'[CANVAS] Update failed: {exc}')
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Refresh analysis canvas from latest report')
    parser.add_argument('--report', type=str, default='')
    args = parser.parse_args()
    report = args.report
    if not report:
        files = sorted((REPO_ROOT / 'reports').glob('Enhanced_Stock_Report_*.xlsx'))
        if not files:
            raise SystemExit('No report found')
        report = str(files[-1])
    update_analysis_canvas(report)
