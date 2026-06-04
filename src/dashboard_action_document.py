"""Build terminal-order action plan document for HTML dashboard."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from src.action_plan_legend import (
    ACTION_PLAN_CATEGORIES,
    COLUMN_GUIDE,
    READING_RULE,
    build_dashboard_glossary,
    decode_reason_plain,
    decode_sell_why_plain,
    decode_tier_plain,
    decode_trigger_plain,
    enrich_section_guide,
    explain_radar_reason,
)

SECTION_LEGEND_KEY = {
    'vmq': 'VMQ',
    'path2': 'PATH2',
    'radar': 'RADAR',
    'sell_breakdown': 'SELL_CAT',
    'swap': 'P1',
    'exit': 'P1_5',
    'sell': 'P2',
    'lvmrot': 'P2',
    'consider': 'P2_5',
    'book': 'P3',
    'reduce': 'P3_5',
    'increase': 'P4_INC',
    'buynew': 'P5',
    'watch': 'P5_5',
    'hold': 'P6',
    'skip': 'P8',
    'dual': 'DUAL',
}

PRIORITY_SECTION_ORDER = [
    'swap', 'exit', 'sell', 'lvmrot', 'consider', 'book', 'reduce', 'increase', 'buynew', 'watch', 'hold', 'skip',
]


def _legend_entry(key: str) -> dict:
    for k, title, what, typical in ACTION_PLAN_CATEGORIES:
        if k == key:
            return {'key': k, 'title': title, 'what': what, 'typicalReason': typical}
    return {'key': key, 'title': key, 'what': '', 'typicalReason': ''}


def _guide_block(key: str, extra_columns: Optional[List[str]] = None) -> dict:
    leg = _legend_entry(key)
    cols = COLUMN_GUIDE if key in ('VMQ', 'SELL_CAT', 'P2', 'P5', 'P5_5', 'P6') else COLUMN_GUIDE[:4]
    if extra_columns:
        cols = [c for c in COLUMN_GUIDE if c['column'] in extra_columns] or cols
    base = {
        'readingRule': READING_RULE if key in ('VMQ', 'INTRO') else '',
        'title': leg['title'],
        'what': leg['what'],
        'typicalReason': leg['typicalReason'],
        'columns': cols,
    }
    return enrich_section_guide(key, base)


def _company_lookup(df: pd.DataFrame) -> dict:
    sym_col = next((c for c in ('symbol', 'Symbol') if c in df.columns), None)
    co_col = next((c for c in ('company_name', 'Company Name', 'Company') if c in df.columns), None)
    if not sym_col or not co_col:
        return {}
    out: dict = {}
    for _, row in df.iterrows():
        sym = str(row.get(sym_col, '') or '').strip()
        if not sym:
            continue
        out[sym] = str(row.get(co_col, '') or '').strip()[:40]
    return out


def _row_item(r: dict) -> dict:
    reason = str(r.get('reason') or '')
    action = str(r.get('action') or r.get('ACTION') or '')
    sell_why = str(r.get('sellWhy') or r.get('SELL WHY') or '')
    out = {
        **r,
        'reasonPlain': r.get('reasonPlain') or decode_reason_plain(
            reason, action=action, sell_why=sell_why,
        ),
    }
    sw = r.get('sellWhy')
    if sw and str(sw) != 'NOT_SELL':
        out['sellWhyPlain'] = decode_sell_why_plain(str(sw))
    return out


def _load_breakout_radar(report_path) -> List[dict]:
    if not report_path or not report_path.exists():
        return []
    try:
        xl = pd.ExcelFile(report_path)
        sheet = next((n for n in xl.sheet_names if 'breakout radar' in n.lower()), None)
        if not sheet:
            return []
        df = pd.read_excel(report_path, sheet_name=sheet)
    except Exception:
        return []
    sym = 'symbol' if 'symbol' in df.columns else df.columns[0]
    rows = []
    for _, r in df.head(12).iterrows():
        tier = str(r.get('breakout_tier', r.get('tier', '')))
        reason = str(r.get('breakout_radar_reason', ''))[:120]
        trigger = str(r.get('monday_trigger', ''))
        rows.append({
            'stock': str(r.get(sym, '')),
            'tier': tier,
            'tierPlain': decode_tier_plain(tier),
            'reason': reason,
            'reasonPlain': explain_radar_reason(reason),
            'trigger': trigger,
            'triggerPlain': decode_trigger_plain(trigger),
            'score': round(float(r.get('breakout_radar_score', 0) or 0), 1),
            'price': round(float(r.get('current_price', r.get('PRICE', 0)) or 0), 2),
        })
    return rows


def _build_vmq_section(df: pd.DataFrame) -> Optional[dict]:
    reason_col = next((c for c in ('REASON', 'vmq_reason', 'exit_reason') if c in df.columns), None)
    if not reason_col:
        return None
    vmq_mask = df[reason_col].astype(str).str.contains('VMQ', na=False)
    sells = df[vmq_mask & df['ACTION'].astype(str).str.upper().str.contains('SELL', na=False)]
    blocked = df[df['ACTION'].astype(str).str.contains('WATCHLIST|TURBO BLOCK', na=False, regex=True)]
    if sells.empty and blocked.empty:
        return None
    items = []
    for _, r in sells.iterrows():
        items.append({
            'stock': str(r.get('symbol', '')),
            'reason': str(r.get(reason_col, ''))[:120],
            'reasonPlain': decode_reason_plain(str(r.get(reason_col, ''))),
            'pnlPct': round(float(r.get('P&L %', 0) or 0), 1),
            'action': 'SELL',
        })
    stats = []
    if len(sells):
        stats.append({'label': 'Forced SELL', 'value': str(len(sells)), 'tone': 'danger'})
    if len(blocked):
        stats.append({'label': 'Entry blocked → WATCHLIST', 'value': str(len(blocked)), 'tone': 'warn'})
    return {
        'id': 'vmq',
        'kind': 'pre',
        'headline': 'VMQ STRATEGY (Validated Momentum-Quality)',
        'guide': _guide_block('VMQ'),
        'stats': stats,
        'items': items,
    }


def _build_path2_section(df: pd.DataFrame, radar_count: int) -> Optional[dict]:
    considers = df[df['ACTION'].astype(str).str.contains('CONSIDER', na=False)] if 'ACTION' in df.columns else pd.DataFrame()
    if radar_count <= 0 and considers.empty:
        return None
    stats = []
    if len(considers):
        stats.append({'label': 'Rank SELL softened → CONSIDER', 'value': str(len(considers))})
    if radar_count:
        stats.append({'label': 'Breakout Radar candidates', 'value': str(radar_count)})
    return {
        'id': 'path2',
        'kind': 'pre',
        'headline': 'PATH 2 — BALANCED',
        'guide': _guide_block('PATH2'),
        'stats': stats,
        'items': [],
    }


def _entry_payload(df: pd.DataFrame, symbol: str, cfg=None) -> Optional[dict]:
    from src.new_entry_scenarios import build_entry_scenarios, format_entry_scenario_lines

    sym = str(symbol or '').strip().upper()
    if not sym or 'symbol' not in df.columns:
        return None
    mask = df['symbol'].astype(str).str.upper() == sym
    if not mask.any():
        return None
    row = df.loc[mask].iloc[0].to_dict()
    sc = build_entry_scenarios(row, cfg)
    lines = format_entry_scenario_lines(sc)
    return {
        'symbol': sym,
        'lines': lines,
        's1': lines[1] if len(lines) > 1 else '',
        's2': lines[2] if len(lines) > 2 else '',
        's3': lines[3] if len(lines) > 3 else '',
        'structured': sc,
    }


def _attach_scenarios_to_items(
    items: List[dict],
    df: pd.DataFrame,
    section_id: str,
    defer_to_buynew: Optional[set] = None,
) -> List[dict]:
    try:
        from config import get_config
        cfg = get_config()
    except Exception:
        cfg = None
    from src.action_scenarios import scenario_payload_for_section

    defer = defer_to_buynew or set()
    out = []
    for it in items:
        row = dict(it)
        sym = str(row.get('stock', row.get('symbol', ''))).strip().upper()
        alloc_row = df.loc[df['symbol'].astype(str).str.upper() == sym].iloc[0].to_dict() if sym and 'symbol' in df.columns and (df['symbol'].astype(str).str.upper() == sym).any() else row
        swap_target = str(row.get('targetSymbol', '')).strip().upper()
        payload = scenario_payload_for_section(
            alloc_row,
            section_id if section_id != 'swap' else 'swap',
            cfg,
            new_buy_syms=defer,
            swap_target=swap_target,
            allocation_df=df,
        )
        if payload.get('entryScenariosRef'):
            row['entryScenariosRef'] = payload['entryScenariosRef']
        if payload.get('entryScenarios'):
            row['entryScenarios'] = payload['entryScenarios']
        if payload.get('exitScenarios'):
            row['exitScenarios'] = payload['exitScenarios']
        if payload.get('monitorScenarios'):
            row['monitorScenarios'] = payload['monitorScenarios']
        out.append(row)
    return out


def build_action_document(
    df: pd.DataFrame,
    report_path,
    priority_sections: List[dict],
    sell_breakdown: List[dict],
    final_numbers: dict,
    tax_harvest: Optional[dict],
    risk_profile: Optional[dict],
    dual_strategy: List[dict],
    hold_note: str = '',
) -> dict:
    """Terminal-order document: guide + live data per section."""
    radar_rows = _load_breakout_radar(report_path)
    sections: List[dict] = []

    intro = {
        'id': 'intro',
        'kind': 'intro',
        'headline': 'How to read this plan',
        'guide': enrich_section_guide('INTRO', {
            'readingRule': READING_RULE,
            'title': 'How to read any row',
            'what': 'Execute sections top-down. Each block explains the category, then lists this run\'s stocks.',
            'typicalReason': '',
            'columns': COLUMN_GUIDE[:4],
        }),
        'stats': [],
        'items': [],
    }
    sections.append(intro)

    vmq = _build_vmq_section(df)
    if vmq:
        sections.append(vmq)

    path2 = _build_path2_section(df, len(radar_rows))
    if path2:
        sections.append(path2)

    if radar_rows:
        co_map = _company_lookup(df)
        for row in radar_rows:
            sym = str(row.get('stock', '') or '').strip()
            if sym and not row.get('company'):
                row['company'] = co_map.get(sym, '')
        sections.append({
            'id': 'radar',
            'kind': 'pre',
            'headline': 'PRIORITY 4: BREAKOUT RADAR',
            'subhead': 'Monday watch — vol≥2.5× avg AND +2.5% day',
            'guide': _guide_block('RADAR'),
            'stats': [{'label': 'Candidates', 'value': str(len(radar_rows))}],
            'items': radar_rows,
        })

    if sell_breakdown:
        sb_items = []
        for cat in sell_breakdown:
            for s in cat.get('stocks', []):
                sb_items.append({**s, 'sellWhy': cat.get('code'), 'categoryLabel': cat.get('label')})
        sections.append({
            'id': 'sell_breakdown',
            'kind': 'pre',
            'headline': 'SELL CATEGORY BREAKDOWN',
            'guide': _guide_block('SELL_CAT'),
            'stats': [{'label': 'Categories', 'value': str(len(sell_breakdown))}],
            'items': sb_items,
            'grouped': sell_breakdown,
        })

    from src.new_entry_scenarios import new_buy_symbols_from_df

    _vcol = next((c for c in ('MY VALUE ₹', 'MY VALUE', 'value') if c in df.columns), 'MY VALUE ₹')
    _icol = next((c for c in ('INVEST ₹', 'INVEST', 'invest') if c in df.columns), 'INVEST ₹')
    new_buy_syms = new_buy_symbols_from_df(df, _vcol, _icol)

    by_id = {s['id']: s for s in priority_sections}
    for sid in PRIORITY_SECTION_ORDER:
        sec = by_id.get(sid)
        if not sec or not sec.get('rows'):
            continue
        key = SECTION_LEGEND_KEY.get(sid, sid)
        items = [_row_item(r) for r in sec['rows']]
        if sid == 'swap':
            for it in items:
                detail = str(it.get('detail', ''))
                if 'buy ' in detail.lower():
                    parts = detail.lower().split('buy ')
                    if len(parts) > 1:
                        it['targetSymbol'] = parts[1].strip().split()[0].upper()
                if not it.get('targetSymbol') and 'rotate' in detail.lower():
                    _tok = detail.upper().split('INTO')
                    if len(_tok) > 1:
                        it['targetSymbol'] = _tok[1].strip().split()[0].upper()
        if sid in ('swap', 'exit', 'sell', 'lvmrot', 'consider', 'book', 'reduce', 'increase', 'buynew', 'watch', 'hold'):
            items = _attach_scenarios_to_items(items, df, sid, defer_to_buynew=new_buy_syms)
        if sid == 'radar':
            try:
                from config import get_config
                cfg = get_config()
            except Exception:
                cfg = None
            from src.action_scenarios import scenario_payload_for_section
            for it in items:
                payload = scenario_payload_for_section(it, 'radar', cfg, allocation_df=df)
                if payload.get('entryScenarios'):
                    it['entryScenarios'] = payload['entryScenarios']
        doc_sec = {
            'id': sid,
            'kind': 'priority',
            'headline': sec['title'],
            'guide': _guide_block(key),
            'stats': [],
            'tone': sec.get('tone', 'neutral'),
            'totalLabel': sec.get('totalLabel'),
            'totalValue': sec.get('totalValue'),
            'items': items,
        }
        if sid == 'swap':
            doc_sec['note'] = 'Exit source on schedule; buy target per ENTRY SCENARIOS — not blind market chase'
        if sid == 'buynew':
            doc_sec['note'] = 'Rank-based size = budget ceiling. Use ENTRY SCENARIOS for timing/price.'
        sections.append(doc_sec)

    if hold_note:
        sections.append({
            'id': 'hold_note',
            'kind': 'callout',
            'headline': 'Important',
            'guide': {'what': hold_note, 'typicalReason': '', 'columns': []},
            'items': [],
        })

    sections.append({
        'id': 'final_numbers',
        'kind': 'footer',
        'headline': 'Final numbers',
        'guide': _guide_block('P5'),
        'finalNumbers': final_numbers,
        'taxHarvest': tax_harvest,
        'riskProfile': risk_profile,
        'items': [],
    })

    if dual_strategy:
        high = [r for r in dual_strategy if 'BUY (both agree)' in str(r.get('agree', ''))]
        sections.append({
            'id': 'dual',
            'kind': 'appendix',
            'headline': 'Dual strategy view',
            'guide': _guide_block('DUAL'),
            'stats': [{'label': 'HIGH CONVICTION (both BUY)', 'value': str(len(high))}],
            'items': dual_strategy[:40],
        })

    return {
        'sections': sections,
        'glossary': build_dashboard_glossary(),
    }
