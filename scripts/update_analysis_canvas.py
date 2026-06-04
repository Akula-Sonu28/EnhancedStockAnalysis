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

    try:
        from config import get_config as _ap_cfg
        from src.lowvol_momentum import lvm_top_label as _lvm_rot_label
        _rot_lbl = _lvm_rot_label(_ap_cfg())
    except Exception:
        _rot_lbl = 'LVM Top 20'
    lvm_rots = df[df[act].str.contains('LVM ROTATION', na=False)].sort_values(val, ascending=False)
    lvm_rot_rows, lvm_rot_total = [], 0.0
    for _, r in lvm_rots.iterrows():
        lvm_rot_rows.append(_enrich_priority_row(
            r, sym, f"Sell ALL {int(r[qty])} shares (not in {_rot_lbl})", _fmt_inr(r[val]),
        ))
        lvm_rot_total += r[val]
    s = _priority_section(
        'lvmrot', 'Priority 2.1: SELL (LVM rotation)', lvm_rot_rows,
        'LVM rotation proceeds', lvm_rot_total, 'danger',
    )
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

    new_buys = df[
        (df[inv] > 0) &
        (df[val] == 0) &
        df[act].str.contains('NEW POSITION', na=False)
    ].sort_values(inv, ascending=False)
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
        'lvmRotTotal': lvm_rot_total,
        'exitTotal': exit_total,
        'bookTotal': book_total,
        'buyTotal': buy_total,
        'increaseTotal': inc_total,
        'skipTotal': skip_total,
        'considerTotal': consider_total,
    }


def _allocation_action_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop Excel spacer/footer rows from action-plan aggregates."""
    if df is None or df.empty:
        return df
    work = df.copy()
    if 'symbol' not in work.columns:
        return work
    sym = work['symbol']
    sym_ok = sym.notna()
    sym_s = sym.astype(str).str.strip()
    sym_ok = sym_ok & ~sym_s.str.lower().isin(('', 'nan', 'none'))
    sym_ok = sym_ok & (sym_s.str.len() <= 32)
    has_econ = pd.Series(False, index=work.index)
    if 'MY VALUE ₹' in work.columns:
        has_econ = has_econ | (pd.to_numeric(work['MY VALUE ₹'], errors='coerce').fillna(0) > 0)
    if 'INVEST ₹' in work.columns:
        has_econ = has_econ | (pd.to_numeric(work['INVEST ₹'], errors='coerce').fillna(0) > 0)
    if 'ACTION' in work.columns:
        act = work['ACTION'].astype(str).str.strip()
        has_econ = has_econ | (act.ne('') & act.str.lower().ne('nan'))
    return work.loc[sym_ok & has_econ]


def _build_final_numbers(
    totals: dict,
    portfolio_amount: float,
    lvm_buy_total: float | None = None,
    lvm_active: bool = False,
) -> dict:
    if lvm_active:
        sell_proceeds = (
            float(totals.get('sellTotal', 0) or 0)
            + float(totals.get('exitTotal', 0) or 0)
            + float(totals.get('lvmRotTotal', 0) or 0)
        )
        buy_orders = float(lvm_buy_total or 0)
        basis_note = (
            'LVM Priority 5: sells = SELL + EXIT + LVM rotation; '
            'buys = funded rebalance only (not screen NEW POSITION rows)'
        )
    else:
        sell_proceeds = (
            totals['swapTotal'] + totals['sellTotal'] + totals['exitTotal']
            + totals['bookTotal'] + float(totals.get('lvmRotTotal', 0) or 0)
        )
        if lvm_buy_total is not None and lvm_buy_total > 0:
            buy_orders = float(lvm_buy_total)
        else:
            buy_orders = totals['buyTotal'] + totals['increaseTotal']
        basis_note = 'QMST: all sell categories + book proceeds vs buy/increase totals'
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
        'basisNote': basis_note,
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
    from src.lvm_action_plan import actionable_sell_mask, compute_tax_harvest_totals
    sells = df.loc[actionable_sell_mask(df['ACTION'])].copy()
    if sells.empty:
        return None
    totals = compute_tax_harvest_totals(sells)
    if not totals:
        return None
    losses = totals['losses']
    return {
        'losses': int(abs(losses)),
        'gains': int(totals['gains']),
        'netPnl': int(totals['net_pnl']),
        'taxPayable': int(totals['tax']),
        'note': 'Losses can offset other STCG/LTCG (8-year carry-forward)' if losses < 0 else '',
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


def _build_risk_warnings(
    df: pd.DataFrame,
    regime: str,
    *,
    sector_concentration: List[dict] | None = None,
    partial_execution: dict | None = None,
    tax_harvest: dict | None = None,
    lvm_data_degraded: bool = False,
) -> List[str]:
    warnings: List[str] = []
    if lvm_data_degraded:
        warnings.append('LVM momentum data incomplete — do not trade LVM picks from this report')
    regime_u = str(regime or '').upper()
    if regime_u in ('BEAR', 'BEARISH'):
        warnings.append('BEAR MARKET — all new positions carry elevated risk')
    for sec in sector_concentration or []:
        if sec.get('overCap'):
            warnings.append(
                f"Sector cap: {sec.get('sector')} has {sec.get('count')} names (limit exceeded)"
            )
    if partial_execution:
        conc = float(partial_execution.get('concPct', 0) or 0)
        if conc >= 40:
            warnings.append(
                f"Concentration: {partial_execution.get('topSector')} "
                f"is {conc:.0f}% of holdings — {partial_execution.get('recommendation', '')}"
            )
        if partial_execution.get('worsens'):
            warnings.append(
                f"Partial execution risk: {partial_execution.get('ifPartialOnly', '')}"
            )
    if tax_harvest:
        tax_pay = float(tax_harvest.get('taxPayable', 0) or 0)
        losses = float(tax_harvest.get('losses', 0) or 0)
        if tax_pay > losses and tax_pay > 0:
            warnings.append(
                f"Tax on sells (est. ₹{tax_pay:,.0f}) exceeds harvestable losses "
                f"(₹{losses:,.0f}) on actionable SELL rows"
            )
    if 'ACTION' in df.columns and 'MY VALUE ₹' in df.columns:
        rot_n = int(
            df['ACTION'].astype(str).str.contains('LVM ROTATION', na=False).sum()
        )
        if rot_n >= 4:
            warnings.append(f'LVM rotation cluster: {rot_n} full exits this month')
    work = _allocation_action_rows(df)
    buys = work[(work['MY VALUE ₹'] == 0) & (work['INVEST ₹'] > 0)] if 'INVEST ₹' in work.columns else pd.DataFrame()
    inc = work[work['ACTION'].astype(str).str.contains('INCREASE', na=False)] if 'ACTION' in work.columns else pd.DataFrame()
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
    from src.action_plan_legend import decode_reason_plain, decode_sell_why_plain

    book = _f(r, 'BOOK %')
    book_pct = round(book * 100, 0) if 0 < book <= 1 else round(book, 0)
    action = _s(r, 'ACTION')
    sell_why = _s(r, 'SELL WHY', 24) or _s(r, 'sell_category', 24)
    reason_plain = decode_reason_plain(
        _s(r, 'REASON', 200), action=action, sell_why=sell_why,
    )
    row = {
        'stock': _s(r, sym),
        'company': _s(r, 'company_name', 40),
        'detail': detail,
        'amount': amount,
        'when': _s(r, 'WHEN', 24),
        'reason': _s(r, 'REASON', 160),
        'reasonPlain': reason_plain,
        'sellWhy': sell_why,
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
    if 'SELL' in action.upper() and sell_why:
        row['sellWhyPlain'] = decode_sell_why_plain(sell_why) or reason_plain
    return row


def _build_allocation_master(df: pd.DataFrame) -> List[dict]:
    from src.action_plan_legend import decode_reason_plain

    rows = []
    for _, r in df.iterrows():
        book = _f(r, 'BOOK %')
        action = _s(r, 'ACTION')
        sell_why = _s(r, 'SELL WHY', 24) or _s(r, 'sell_category', 24)
        rows.append({
            'stock': _s(r, 'symbol'),
            'company': _s(r, 'company_name', 40),
            'action': action,
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
            'reasonPlain': decode_reason_plain(
                _s(r, 'REASON', 300), action=action, sell_why=sell_why,
            ),
            'sellWhy': sell_why,
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


def _is_lvm_pick_mode(cfg=None) -> bool:
    try:
        from config import get_config
        cfg = cfg or get_config()
        metric = str(getattr(cfg, 'ORACLE_PICK_METRIC', '')).lower()
        return metric in ('lowvol_mom', 'low_vol_momentum', 'quality_lvm')
    except Exception:
        return False


def _lvm_gtt_stop(price: float, cfg=None) -> tuple:
    """Return (gtt_stop_price, abs_stop_pct) for LVM GTT display."""
    if price <= 0:
        return 0.0, 10.0
    try:
        from config import get_config
        cfg = cfg or get_config()
        pct = float(getattr(cfg, 'LVM_STOP_PCT', -10.0))
    except Exception:
        pct = -10.0
    return round(price * (1 + pct / 100), 2), abs(pct)


def _build_holdings_enriched(df: pd.DataFrame, holdings: List[dict], cfg=None) -> List[dict]:
    from src.action_scenarios import scenario_payload_for_section

    try:
        from config import get_config
        cfg = cfg or get_config()
    except ImportError:
        cfg = None

    lvm_mode = _is_lvm_pick_mode(cfg)
    by_sym = {str(r.get('symbol', '')): r for _, r in df.iterrows()} if 'symbol' in df.columns else {}
    out = []
    for h in holdings:
        sym = h['stock']
        r = by_sym.get(sym)
        row = dict(h)
        if r is not None:
            pnl_pct = round(_f(r, 'P&L %'), 1)
            reason = _s(r, 'REASON', 100)
            action = _s(r, 'ACTION')
            sell_why = _s(r, 'SELL WHY', 24) or _s(r, 'sell_category', 24)
            try:
                from src.action_plan_legend import decode_reason_plain, format_holdings_action_lines
                reason_plain = decode_reason_plain(
                    reason,
                    action=action,
                    sell_why=sell_why,
                )
            except ImportError:
                reason_plain = ''
                format_holdings_action_lines = None  # type: ignore
            row.update({
                'action': action,
                'company': _s(r, 'company_name', 40),
                'when': _s(r, 'WHEN'),
                'score': round(_f(r, 'SCORE'), 1),
                'v2Score': round(_f(r, 'V2 RAW'), 1),
                'pnlPct': pnl_pct,
                'pnlPctAlloc': pnl_pct,
                'sector': _s(r, 'sector'),
                'stopLoss': round(_f(r, 'STOP LOSS'), 2),
                'ml': _s(r, 'ML'),
                'price': round(_f(r, 'PRICE'), 2),
                'reason': reason,
                'reasonPlain': reason_plain or '',
            })

            act_upper = str(action).upper()
            if ('HOLD' in act_upper or 'KEEP' in act_upper) and 'SELL' not in act_upper:
                alloc_row = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
                alloc_row.setdefault('symbol', sym)
                payload = scenario_payload_for_section(
                    alloc_row, 'hold', cfg, allocation_df=df,
                )
                if payload.get('monitorScenarios'):
                    row['monitorScenarios'] = payload['monitorScenarios']
                if format_holdings_action_lines:
                    summary = format_holdings_action_lines(
                        pd.DataFrame([{
                            'symbol': sym,
                            'ACTION': action or 'HOLD',
                            'REASON': reason,
                            'P&L %': pnl_pct,
                            'MY VALUE ₹': h.get('value', 0),
                        }]),
                    )
                    if summary:
                        row['summaryLine'] = summary[0].strip()
                if lvm_mode:
                    px = float(row.get('price') or _f(r, 'PRICE') or 0)
                    if px > 0:
                        gtt, gtt_pct = _lvm_gtt_stop(px, cfg)
                        row['gttStop'] = gtt
                        row['gttStopPct'] = gtt_pct
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
    work = _allocation_action_rows(df)
    counts = work['ACTION'].astype(str).str.strip().value_counts()
    out = []
    for a, c in counts.items():
        label = str(a).strip()
        if not label or label.lower() == 'nan':
            continue
        out.append({'action': label, 'count': int(c)})
    return out


def _build_sell_category_breakdown(df: pd.DataFrame) -> List[dict]:
    """SELL rows grouped by SELL WHY / sell_category."""
    from src.action_plan_legend import decode_reason_plain

    try:
        from src.picking_metrics import SELL_CATEGORY_LABELS, populate_sell_categories
        work = populate_sell_categories(df.copy())
    except ImportError:
        return []
    if 'ACTION' not in work.columns:
        return []
    from src.lvm_action_plan import actionable_sell_mask
    sells = work.loc[actionable_sell_mask(work['ACTION'])]
    if sells.empty:
        return []
    cat_col = 'SELL WHY' if 'SELL WHY' in sells.columns else 'sell_category'
    if cat_col not in sells.columns:
        return []
    out = []
    for cat in sorted(sells[cat_col].dropna().unique()):
        cat_s = str(cat)
        rows = sells[sells[cat_col] == cat]
        stocks = []
        for _, r in rows.iterrows():
            stocks.append({
                'stock': _s(r, 'symbol'),
                'reason': _s(r, 'REASON', 120),
                'reasonPlain': decode_reason_plain(_s(r, 'REASON', 200)),
                'pnlPct': round(_f(r, 'P&L %'), 1),
                'value': int(_f(r, 'MY VALUE ₹')),
            })
        out.append({
            'code': cat_s,
            'label': SELL_CATEGORY_LABELS.get(cat_s, cat_s),
            'count': len(stocks),
            'stocks': stocks,
        })
    return out


def _load_lvm_top10(report_path: Path, cfg=None) -> List[dict]:
    """Load LVM family Top-N picks from Excel (sheet name follows LVM_TOP_N)."""
    picks: List[dict] = []
    if not report_path.exists():
        return picks
    try:
        from src.lowvol_momentum import (
            active_lvm_score_col,
            is_quality_lvm_strategy,
            lvm_sheet_name,
            lvm_top_n,
        )
        _sheet = lvm_sheet_name(cfg) if cfg else 'LowVol-Mom Top 20'
        _scol = active_lvm_score_col(cfg) if cfg else 'lowvol_mom_score'
        _lvm_df = None
        _try_sheets = [_sheet]
        if cfg:
            _base = 'Quality-LVM' if is_quality_lvm_strategy(cfg) else 'LowVol-Mom'
            _try_sheets.extend(f'{_base} Top {n}' for n in (10, 15, 20))
        for _sh in dict.fromkeys(_try_sheets):
            try:
                _lvm_df = pd.read_excel(report_path, sheet_name=_sh, header=1)
                break
            except Exception:
                continue
        if _lvm_df is None:
            raise FileNotFoundError(f'No LVM sheet in {report_path}')
        for _, r in _lvm_df.iterrows():
            sym = str(r.get('symbol', '')).strip()
            if not sym:
                continue
            _score = r.get(_scol, r.get('quality_lvm_score', r.get('lowvol_mom_score', 0)))
            picks.append({
                'stock': sym,
                'company': str(r.get('company_name', '')),
                'sector': str(r.get('sector', '')),
                'price': float(r.get('current_price', 0)) if pd.notna(r.get('current_price')) else 0,
                'return12m': float(r.get('price_change_1y', 0)) if pd.notna(r.get('price_change_1y')) else 0,
                'volatility': float(
                    r.get('volatility_6m', r.get('volatility', 0))
                ) if pd.notna(r.get('volatility_6m', r.get('volatility'))) else 0,
                'lvmScore': float(_score) if pd.notna(_score) else 0,
            })
        _want = lvm_top_n(cfg) if cfg else 20
        if cfg is not None and len(picks) < _want:
            picks = []
            raise FileNotFoundError('stale LVM sheet — recompute from Complete Data')
    except Exception:
        if cfg is not None:
            try:
                from datetime import date as _lvm_d
                from src.lowvol_momentum import (
                    active_lvm_eligible_col,
                    active_lvm_score_col,
                    compute_active_lvm_score,
                )
                _cd = pd.read_excel(report_path, sheet_name='Complete Data')
                _cd = compute_active_lvm_score(_cd, cfg, as_of=_lvm_d.today())
                _ecol = active_lvm_eligible_col(cfg)
                _scol = active_lvm_score_col(cfg)
                _elig = _cd[_cd[_ecol].fillna(False).astype(bool)]
                for _, r in _elig.iterrows():
                    sym = str(r.get('symbol', '')).strip()
                    if not sym:
                        continue
                    picks.append({
                        'stock': sym,
                        'company': str(r.get('company_name', '')),
                        'sector': str(r.get('sector', '')),
                        'price': float(r.get('current_price', 0)) if pd.notna(r.get('current_price')) else 0,
                        'return12m': float(r.get('price_change_1y', 0)) if pd.notna(r.get('price_change_1y')) else 0,
                        'volatility': float(
                            r.get('volatility_6m', r.get('volatility', 0))
                        ) if pd.notna(r.get('volatility_6m', r.get('volatility'))) else 0,
                        'lvmScore': float(r.get(_scol, 0)) if pd.notna(r.get(_scol)) else 0,
                    })
            except Exception:
                pass
    if picks:
        try:
            from src.lowvol_momentum import (
                active_lvm_eligible_col,
                active_lvm_score_col,
                compute_active_lvm_score,
            )
            import numpy as _np
            from collections import Counter as _Counter

            _cd = pd.read_excel(report_path, sheet_name='Complete Data')
            _scol_x = active_lvm_score_col(cfg)
            from datetime import date as _stab_date
            _np.random.seed(42)
            _n_trials = 50
            counts: _Counter = _Counter()
            for _ in range(_n_trials):
                p = _cd.copy()
                noise = _np.random.uniform(0.98, 1.02, len(p))
                p['current_price'] = pd.to_numeric(p['current_price'], errors='coerce') * noise
                _ecol_s = active_lvm_eligible_col(cfg)
                trial = compute_active_lvm_score(p, cfg, as_of=_stab_date.today())
                for s in trial.loc[trial[_ecol_s].fillna(False).astype(bool), 'symbol']:
                    counts[s] += 1

            for pick in picks:
                sym = pick['stock']
                stab = counts.get(sym, 0)
                if stab >= _n_trials:
                    tier = 'ROCK SOLID'
                elif stab >= _n_trials * 0.9:
                    tier = 'VERY STABLE'
                elif stab >= _n_trials * 0.7:
                    tier = 'STABLE'
                elif stab >= _n_trials * 0.4:
                    tier = 'BORDERLINE'
                else:
                    tier = 'FRAGILE'
                pick['stability'] = stab
                pick['stabilityMax'] = _n_trials
                pick['tier'] = tier

            all_candidates = sorted(counts.keys(), key=lambda s: -counts[s])
            lvm_syms = {p['stock'] for p in picks}
            extras = []
            _max_extras = 0 if cfg and int(getattr(cfg, 'LVM_TOP_N', 20)) >= 20 else 5
            for sym in all_candidates:
                if sym in lvm_syms or len(extras) >= _max_extras:
                    continue
                stab = counts[sym]
                if stab < 5:
                    continue
                row = _cd[_cd['symbol'] == sym]
                if row.empty:
                    continue
                r = row.iloc[0]
                s_tier = 'STABLE' if stab >= _n_trials * 0.7 else ('BORDERLINE' if stab >= _n_trials * 0.4 else 'FRAGILE')
                extras.append({
                    'stock': sym,
                    'company': str(r.get('company_name', '')),
                    'sector': str(r.get('sector', '')),
                    'price': float(r.get('current_price', 0)) if pd.notna(r.get('current_price')) else 0,
                    'return12m': float(r.get('price_change_1y', 0)) if pd.notna(r.get('price_change_1y')) else 0,
                    'volatility': float(r.get('volatility_6m', r.get('volatility', 0)) or 0),
                    'lvmScore': float(r.get(_scol_x, r.get('lowvol_mom_score', 0)))
                    if pd.notna(r.get(_scol_x)) else 0,
                    'stability': stab,
                    'stabilityMax': _n_trials,
                    'tier': s_tier,
                    'isAlternate': True,
                })
            picks.extend(extras)
        except Exception:
            pass

    try:
        from src.lvm_action_plan import resolve_lvm_universe
        from datetime import date as _fund_date
        try:
            _fund_cd = pd.read_excel(report_path, sheet_name='Complete Data')
        except Exception:
            _fund_cd = pd.DataFrame()
        _screen_syms, _fund_syms, _, _fund_deg = resolve_lvm_universe(
            _fund_cd, cfg, as_of=_fund_date.today(),
        )
        if _fund_syms and not _fund_deg:
            _fund_set = {s.upper() for s in _fund_syms}
        else:
            from src.lowvol_momentum import lvm_fund_n
            _primary = [p for p in picks if not p.get('isAlternate')]
            _ranked = sorted(_primary, key=lambda x: -float(x.get('lvmScore', 0) or 0))
            _fund_set = {p['stock'] for p in _ranked[:lvm_fund_n(cfg)]}
        for p in picks:
            if p.get('isAlternate'):
                continue
            p['fundSlot'] = str(p.get('stock', '')).upper() in _fund_set
    except Exception:
        pass

    return picks


def _patch_lvm_action_document(
    action_document: dict,
    df: pd.DataFrame,
    lvm_top10: List[dict],
    totals: dict,
    portfolio_amount: float,
    complete_df: pd.DataFrame | None = None,
) -> dict:
    """Build LVM PRIORITY 5 section with INCREASE / BUY NEW / AT WEIGHT logic."""
    if not lvm_top10:
        return action_document, 0.0

    try:
        from src.lowvol_momentum import is_lvm_momentum_degraded
        from src.lvm_action_plan import LVM_DEGRADED_MSG
        _deg_df = complete_df if complete_df is not None and not complete_df.empty else df
        if is_lvm_momentum_degraded(_deg_df):
            degraded_sec = {
                'id': 'buynew',
                'kind': 'priority',
                'headline': 'Priority 5: LVM REBALANCE — SKIPPED (data incomplete)',
                'note': LVM_DEGRADED_MSG,
                'tone': 'warning',
                'totalLabel': 'Action',
                'totalValue': 'Do not trade LVM picks from this report',
                'items': [],
                'guide': {'title': 'LVM data incomplete', 'what': LVM_DEGRADED_MSG},
            }
            sections = [s for s in (action_document.get('sections') or []) if s.get('id') != 'buynew']
            insert_at = len(sections)
            for i, sec in enumerate(sections):
                if sec.get('id') in ('lvmrot', 'sell', 'exit'):
                    insert_at = i + 1
            sections.insert(insert_at, degraded_sec)
            action_document['sections'] = sections
            action_document['lvmDataDegraded'] = True
            return action_document, 0.0
    except Exception:
        pass

    try:
        from config import get_config
        from src.lowvol_momentum import lvm_fund_label, lvm_fund_n, lvm_top_label, lvm_top_n
        cfg = get_config()
        _lvm_label = lvm_top_label(cfg)
        _lvm_fund_label = lvm_fund_label(cfg)
        _lvm_screen_n = lvm_top_n(cfg)
        _lvm_fund_n = lvm_fund_n(cfg)
    except ImportError:
        cfg = None
        _lvm_label = 'LVM Top 20'
        _lvm_fund_label = 'LVM Fund Top 12'
        _lvm_screen_n = 20
        _lvm_fund_n = 12

    primary = [p for p in lvm_top10 if not p.get('isAlternate')]
    if any(p.get('fundSlot') for p in primary):
        funded_picks = [p for p in primary if p.get('fundSlot')]
    else:
        funded_picks = sorted(
            primary, key=lambda x: -float(x.get('lvmScore', 0) or 0),
        )[:_lvm_fund_n]

    val_col = 'MY VALUE ₹'
    act_col = 'ACTION'
    lvm_syms = {str(p.get('stock', '')).upper() for p in funded_picks}

    from src.lvm_action_plan import compute_lvm_p5_actions, lvm_p5_capital_and_buys

    sell_proceeds, _, total_available = lvm_p5_capital_and_buys(
        totals,
        portfolio_amount,
        lvm_syms,
        df,
        complete_df,
        val_col=val_col,
        price_by_sym=None,
    )

    _price_map = {
        str(p.get('stock', '')).upper(): float(p.get('price', 0) or 0)
        for p in funded_picks
        if p.get('price')
    }
    p5_actions, target_per, held_value, _held_syms, new_syms = compute_lvm_p5_actions(
        lvm_syms,
        total_available,
        df,
        None,
        min_invest=5000.0,
        val_col=val_col,
        price_by_sym=_price_map,
    )
    pick_by_sym = {str(p.get('stock', '')).upper(): p for p in funded_picks}

    buy_items: List[dict] = []
    buy_total = 0.0
    at_weight_syms: List[str] = []

    for act in p5_actions:
        sym = act['sym']
        act_label = act['action']
        if act_label == 'AT WEIGHT':
            at_weight_syms.append(sym)
            continue
        if act_label not in ('BUY NEW', 'INCREASE'):
            continue
        pick = pick_by_sym.get(sym, {})
        price = float(act.get('price') or pick.get('price', 0) or 0)
        cur_val = float(act.get('cur_val', 0) or 0)
        qty = int(act.get('shares', 0) or 0)
        inv = float(act.get('invest', 0) or 0)
        buy_amt = target_per if act_label == 'BUY NEW' else max(0.0, target_per - cur_val)
        buy_total += inv
        entry_lo = price * 0.97 if price else 0
        entry_hi = price * 1.01 if price else 0
        gtt_stop, gtt_pct = _lvm_gtt_stop(price, cfg) if price else (0.0, 10.0)
        buy_items.append({
            'stock': sym,
            'company': str(pick.get('company', ''))[:40],
            'sector': str(pick.get('sector', '')),
            'detail': (
                f'{act_label}: {qty} shares @ ₹{price:,.2f}'
                if qty else f'{act_label} ~₹{buy_amt:,.0f}'
            ),
            'amount': _fmt_inr(inv) if inv else f'~{_fmt_inr(buy_amt)} target',
            'price': round(price, 2),
            'qty': qty,
            'heldValue': round(cur_val, 0),
            'targetValue': round(target_per, 0),
            'stopLoss': round(price * 0.90, 2) if price else 0,
            'gttStop': gtt_stop,
            'gttStopPct': gtt_pct,
            'reason': f'{_lvm_fund_label} — entry band ₹{entry_lo:,.0f}–₹{entry_hi:,.0f}, stop -10%',
            'reasonPlain': f'{act_label}. Limit buy in entry band; GTT stop at -10%.',
            'action': act_label,
            'lvmScore': round(float(pick.get('lvmScore', 0) or 0), 0),
        })

    try:
        from src.dashboard_action_document import _guide_block
        guide = _guide_block('P5')
    except Exception:
        guide = {'title': 'Priority 5: LVM Rebalance', 'what': 'LVM rebalance', 'typicalReason': '', 'columns': []}

    if buy_items:
        headline = f'Priority 5: LVM REBALANCE — {_lvm_fund_label} (screen {_lvm_label})'
        note = (
            f'Monthly book: fund top {_lvm_fund_n} of {_lvm_screen_n} screen names (equal weight). '
            f'Capital: sells ₹{sell_proceeds:,.0f} + cash ₹{portfolio_amount:,.0f} = ₹{total_available:,.0f}. '
            f'Held funded LVM: ₹{held_value:,.0f}. Target: ₹{target_per:,.0f}/stock.'
        )
        if at_weight_syms:
            note += f' Already at weight: {", ".join(at_weight_syms)}.'
    else:
        headline = f'Priority 5: {_lvm_fund_label} — ALL AT TARGET WEIGHT'
        if new_syms:
            note = (
                f'Held {len(_held_syms)} funded names at ~₹{target_per:,.0f} each. '
                f'Still need {len(new_syms)} new funded names: {", ".join(sorted(new_syms))}. '
                f'Excess cash: ₹{total_available:,.0f}.'
            )
        else:
            note = (
                f'All {len(at_weight_syms)} funded LVM picks already held at ~₹{target_per:,.0f} each. '
                f'No new buys needed. Excess cash: ₹{total_available:,.0f}.'
            )

    buy_sec = {
        'id': 'buynew',
        'kind': 'priority',
        'headline': headline,
        'note': note,
        'tone': 'success' if buy_items else 'neutral',
        'totalLabel': 'Rebalance total' if buy_items else 'Excess cash',
        'totalValue': _fmt_inr(buy_total) if buy_items else _fmt_inr(total_available),
        'items': buy_items,
        'guide': guide,
    }

    sections = [s for s in (action_document.get('sections') or []) if s.get('id') != 'buynew']
    insert_at = len(sections)
    for i, sec in enumerate(sections):
        if sec.get('id') in ('lvmrot', 'sell', 'exit'):
            insert_at = i + 1
    sections.insert(insert_at, buy_sec)
    action_document['sections'] = sections
    action_document['lvmDataDegraded'] = False
    return action_document, buy_total


def build_dashboard_payload(
    report_file: str,
    allocation_df: pd.DataFrame,
    portfolio_amount: float = 0,
    regime: str = 'Sideways',
    repo_root: Path | None = None,
) -> dict:
    """Structured dashboard data shared by HTML dashboard and Cursor canvas."""
    root = repo_root or REPO_ROOT
    df = _prep_numeric(_normalize_allocation_df(allocation_df.copy()))
    df = _allocation_action_rows(df)
    run_date = datetime.now().strftime('%d %b %Y')
    report_name = Path(report_file).name

    report_path = Path(report_file)
    if not report_path.is_absolute():
        report_path = root / report_path

    complete_df: pd.DataFrame | None = None
    try:
        complete_df = pd.read_excel(report_path, sheet_name='Complete Data')
    except Exception:
        complete_df = None

    _lvm_active = False
    _lvm_cfg = None
    try:
        from config import get_config as _gc_lvm
        _lvm_cfg = _gc_lvm()
        from src.lowvol_momentum import is_lvm_strategy
        _lvm_active = is_lvm_strategy(_lvm_cfg)
    except Exception:
        pass

    lvm_top10 = _load_lvm_top10(report_path, _lvm_cfg) if _lvm_active else []

    if lvm_top10 and not df.empty and 'P&L %' in df.columns:
        _val_col = 'MY VALUE ₹'
        for pick in lvm_top10:
            sym = pick.get('stock', '')
            row = df[df['symbol'].astype(str).str.upper() == sym.upper()]
            if not row.empty:
                r = row.iloc[0]
                pnl = r.get('P&L %')
                val = r.get(_val_col, 0)
                pick['holdingPnl'] = round(float(pnl), 2) if pd.notna(pnl) else None
                pick['holdingValue'] = round(float(val), 0) if pd.notna(val) and float(val) > 0 else None

    if _lvm_active and lvm_top10:
        from src.lowvol_momentum import lvm_top_label as _lvm_lbl_fn
        from src.lvm_action_plan import apply_lvm_rotation_display_fields, resolve_lvm_universe
        from datetime import date as _rot_date
        _lvm_lbl = _lvm_lbl_fn(_lvm_cfg) if _lvm_cfg else 'LVM Top 20'
        try:
            _rot_cd = pd.read_excel(report_path, sheet_name='Complete Data')
        except Exception:
            _rot_cd = df
        _lvm_screen_syms, _, _, _lvm_rot_deg = resolve_lvm_universe(
            _rot_cd, _lvm_cfg, as_of=_rot_date.today(),
        )
        _val_col = 'MY VALUE ₹'
        _act_col = 'ACTION'
        if _val_col in df.columns and _act_col in df.columns and _lvm_screen_syms and not _lvm_rot_deg:
            for idx, row in df.iterrows():
                sym = str(row.get('symbol', '')).upper()
                act = str(row.get(_act_col, '')).upper()
                has_val = float(row.get(_val_col, 0) or 0) > 0
                is_hold = 'HOLD' in act or 'KEEP' in act or 'INCREASE' in act
                if has_val and is_hold and sym not in _lvm_screen_syms:
                    apply_lvm_rotation_display_fields(df, idx, row, _lvm_lbl, value_col=_val_col)

    sections, totals = _build_action_plan_sections(df)
    final_numbers = _build_final_numbers(totals, portfolio_amount, lvm_active=_lvm_active)
    holdings = _load_holdings(root)
    holdings_enriched = _build_holdings_enriched(df, holdings)
    dual = _build_dual_strategy(df)
    trust = _load_trust_metrics(root, report_path)
    hold_note = _hold_note(df, holdings)
    extras = _load_report_extras(report_path)
    ps = extras.get('portfolioSummary') or {}
    mtf_book = _build_mtf_for_book(df, report_path)

    try:
        from src.action_plan_legend import build_dashboard_glossary
        from src.dashboard_action_document import build_action_document
        action_guide = build_dashboard_glossary()
    except ImportError:
        action_guide = {}
        build_action_document = None

    sell_breakdown = _build_sell_category_breakdown(df)

    action_document = {'sections': [], 'glossary': action_guide}
    if build_action_document is not None:
        action_document = build_action_document(
            df, report_path, sections, sell_breakdown,
            final_numbers, _build_tax_harvest(df), _build_risk_profile(df),
            dual, hold_note,
        )

    lvm_data_degraded = False
    if _lvm_active and lvm_top10:
        _lvm_picks_only = [p for p in lvm_top10 if not p.get('isAlternate')]
        action_document, lvm_buy_total = _patch_lvm_action_document(
            action_document,
            df,
            _lvm_picks_only,
            totals,
            portfolio_amount,
            complete_df=complete_df,
        )
        lvm_data_degraded = bool(action_document.get('lvmDataDegraded'))
        final_numbers = _build_final_numbers(
            totals,
            portfolio_amount,
            lvm_buy_total=lvm_buy_total,
            lvm_active=True,
        )
        for sec in action_document.get('sections') or []:
            if sec.get('id') == 'final_numbers':
                sec['finalNumbers'] = final_numbers
                if tax_h := _build_tax_harvest(df):
                    sec['taxHarvest'] = tax_h
                if risk_p := _build_risk_profile(df):
                    sec['riskProfile'] = risk_p
                break

    # RSI Pullback candidates (scan Complete Data — allocation sheet lacks RSI/SMA cols)
    rsi_pullback = []
    try:
        if _lvm_active:
            from src.rsi_pullback_scanner import scan_rsi_pullback
            _rsi_df = None
            try:
                _rsi_df = pd.read_excel(report_path, sheet_name='Complete Data')
            except Exception:
                pass
            if _rsi_df is not None and not _rsi_df.empty:
                rsi_pullback_df = scan_rsi_pullback(_rsi_df, _lvm_cfg)
                _rsi_sym_to_company = {}
                if 'company_name' in _rsi_df.columns:
                    for _, _cr in _rsi_df[['symbol', 'company_name']].dropna().iterrows():
                        _rsi_sym_to_company[str(_cr['symbol']).upper()] = str(_cr['company_name'])
                for _, r in rsi_pullback_df.head(5).iterrows():
                    _rsym = str(r.get('symbol', ''))
                    rsi_pullback.append({
                        'stock': _rsym,
                        'company': _rsi_sym_to_company.get(_rsym.upper(), ''),
                        'price': float(r.get('current_price', 0)),
                        'rsi': float(r.get('rsi', 0)),
                        'distTo40': float(r.get('distance_to_40', 0)),
                        'aboveSma50Pct': float(r.get('above_sma50_pct', 0)),
                    })
            if rsi_pullback:
                rsi_items = []
                from src.lvm_action_plan import portfolio_value_for_rsi_sizing
                _pv_rsi = sum(h.get('value', 0) for h in holdings) if holdings else 0
                if _pv_rsi <= 0 and 'MY VALUE ₹' in df.columns:
                    _pv_rsi = float(df.loc[df['MY VALUE ₹'] > 0, 'MY VALUE ₹'].sum())
                _rsi_budget = portfolio_value_for_rsi_sizing(
                    df,
                    fallback_inr=float(_pv_rsi or 1_150_000),
                )
                from datetime import datetime as _dt_rsi, timedelta as _td_rsi
                _today = _dt_rsi.now()
                _wd = _today.weekday()
                _entry_offset = 1 if _wd < 4 else (7 - _wd)
                _entry_date = _today + _td_rsi(days=_entry_offset)
                _exit_date = _entry_date + _td_rsi(days=7)
                while _exit_date.weekday() >= 5:
                    _exit_date += _td_rsi(days=1)
                _entry_str = _entry_date.strftime('%a %d %b')
                _exit_str = _exit_date.strftime('%a %d %b')
                for p in rsi_pullback:
                    px = float(p.get('price', 0))
                    stop = round(px * 0.97, 1)
                    entry_lo = round(px * 0.99, 1)
                    entry_hi = round(px * 1.005, 1)
                    qty = int(_rsi_budget / px) if px > 0 else 0
                    invest = round(qty * px, 0)
                    max_loss = round(qty * (px - stop), 0)
                    rsi_items.append({
                        'stock': p['stock'],
                        'company': p.get('company', ''),
                        'detail': f"RSI {p['rsi']:.1f} | +{p['aboveSma50Pct']:.1f}% above SMA50",
                        'amount': _fmt_inr(invest),
                        'price': round(px, 2),
                        'qty': qty,
                        'invest': invest,
                        'maxLoss': max_loss,
                        'rsi': round(p['rsi'], 1),
                        'distTo40': round(p['distTo40'], 1),
                        'aboveSma50Pct': round(p['aboveSma50Pct'], 1),
                        'stopLoss': stop,
                        'action': 'RSI PULLBACK',
                        'when': f'Buy {_entry_str} at open',
                        'exitWhen': f'Exit {_exit_str} or stop ₹{stop:,.1f} (-3%)',
                        'reason': f'RSI {p["rsi"]:.1f} | {qty} shares @ ₹{px:,.0f} = ₹{invest:,.0f} | Stop ₹{stop:,.0f} (loss ₹{max_loss:,.0f})',
                        'reasonPlain': f'Buy {qty} shares {_entry_str}. Exit {_exit_str} or stop ₹{stop:,.0f}.',
                    })
                rsi_sec = {
                    'id': 'rsipullback',
                    'kind': 'priority',
                    'headline': f'Priority 5.5: RSI PULLBACK — Weekly Trades ({len(rsi_items)})',
                    'note': 'Buy closest to RSI 40, hold 5 days, -3% stop. 60% WR proven (443 trades).',
                    'tone': 'info',
                    'totalLabel': 'RSI candidates',
                    'totalValue': str(len(rsi_items)),
                    'items': rsi_items,
                }
                ad_sections = action_document.get('sections') or []
                insert_after = len(ad_sections)
                for i, sec in enumerate(ad_sections):
                    if sec.get('id') == 'buynew':
                        insert_after = i + 1
                        break
                ad_sections.insert(insert_after, rsi_sec)
                action_document['sections'] = ad_sections
    except Exception:
        pass

    tax_harvest = _build_tax_harvest(df)
    risk_profile = _build_risk_profile(df)
    sector_concentration = _build_sector_concentration(df)
    partial_execution = _build_partial_execution(df)

    return {
        'runDate': run_date,
        'report': report_name,
        'regime': str(regime) or ps.get('marketRegime', 'Sideways'),
        'activeStrategy': 'LowVol→Mom' if _lvm_active else 'QMST',
        'positions': len(holdings) or int((df['MY VALUE ₹'] > 0).sum()) if 'MY VALUE ₹' in df.columns else 0,
        'portfolioValue': sum(h['value'] for h in holdings) or int(df.loc[df['MY VALUE ₹'] > 0, 'MY VALUE ₹'].sum()) if 'MY VALUE ₹' in df.columns else 0,
        'trust': trust,
        'holdNote': hold_note,
        'sections': action_document.get('sections', sections),
        'finalNumbers': final_numbers,
        'taxHarvest': tax_harvest,
        'riskProfile': risk_profile,
        'riskWarnings': _build_risk_warnings(
            df,
            regime,
            sector_concentration=sector_concentration,
            partial_execution=partial_execution,
            tax_harvest=tax_harvest,
            lvm_data_degraded=lvm_data_degraded,
        ),
        'sectorConcentration': sector_concentration,
        'partialExecution': partial_execution,
        'holdings': holdings_enriched,
        'sectorChart': _build_sector_chart(holdings_enriched),
        'allocationMaster': _build_allocation_master(df),
        'dualStrategy': dual if not _lvm_active else {},
        'actionSummary': _action_summary(df),
        'portfolioSummary': ps,
        'topPicks': extras.get('topPicks', []),
        'tradingLevels': extras.get('tradingLevels', []),
        'undervalued': extras.get('undervalued', []),
        'sectorAnalysis': extras.get('sectorAnalysis', []),
        'weeklyChanges': extras.get('weeklyChanges', []),
        'mtfBook': mtf_book,
        'actionPlanGuide': action_guide,
        'sellCategoryBreakdown': sell_breakdown,
        'actionDocument': action_document,
        'lvmTop10': lvm_top10,
        'lvmScreenN': int(getattr(_lvm_cfg, 'LVM_TOP_N', 20)) if _lvm_cfg else 20,
        'lvmFundN': int(getattr(_lvm_cfg, 'LVM_FUND_N', 12)) if _lvm_cfg else 12,
        'lvmDataDegraded': bool(action_document.get('lvmDataDegraded')),
        'rsiPullback': rsi_pullback,
    }


def generate_canvas_tsx(
    report_file: str,
    allocation_df: pd.DataFrame,
    portfolio_amount: float = 0,
    regime: str = 'Sideways',
    repo_root: Path | None = None,
) -> str:
    root = repo_root or REPO_ROOT
    payload = build_dashboard_payload(
        report_file, allocation_df,
        portfolio_amount=portfolio_amount, regime=regime, repo_root=root,
    )
    from src.analysis_dashboard import apply_dashboard_policy, stamp_dashboard_build_version

    report_path = Path(report_file)
    if not report_path.is_absolute():
        report_path = root / report_path
    apply_dashboard_policy(payload)
    stamp_dashboard_build_version(payload, report_path)
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
        <H1>{{DATA.activeStrategy || 'QMST'}} analysis dashboard</H1>
        <Text tone="secondary" size="small">
          {{DATA.report}} · {{DATA.runDate}} · Regime: {{DATA.regime}}
          {{DATA.buildVersion ? ' · ' + DATA.buildVersion : ''}}
        </Text>
      </Stack>

      <Grid columns={{4}} gap={{12}}>
        <Stat value={{fmtLakh(DATA.portfolioValue)}} label="Portfolio value" />
        <Stat value={{String(DATA.positions)}} label="Holdings" />
        <Stat value={{fmtLakh(fn.buyOrders)}} label="Total buys" tone="success" />
        <Stat value={{fmtLakh(fn.sellProceeds)}} label="Total sells" tone="danger" />
      </Grid>

      {{DATA.activeStrategy !== 'LowVol→Mom' && DATA.trust && DATA.trust.trustLabel ? (
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
      ) : null}}

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
