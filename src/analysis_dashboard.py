"""Tape & Ledger HTML dashboard for QMST analysis runs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / 'frontend' / 'dashboard'
TEMPLATE_PATH = DASHBOARD_DIR / 'template.html'
CSS_PATH = DASHBOARD_DIR / 'tape-dashboard.css'
JS_PATH = DASHBOARD_DIR / 'app.js'
DEFAULT_OUTPUT = REPO_ROOT / 'frontend' / 'qmst-dashboard.html'

_DASHBOARD_PAYLOAD_KEYS = (
    'runDate', 'report', 'reportPath', 'regime', 'activeStrategy', 'buildVersion',
    'positions', 'portfolioValue',
    'finalNumbers', 'holdings', 'actionPlanGuide', 'actionDocument', 'dashboardPolicy',
    'sectorChart', 'lvmTop10', 'rsiPullback',
    'taxHarvest', 'riskProfile', 'riskWarnings',
)

_LVM_DASHBOARD_KEEP_SECTIONS = frozenset({
    'sell', 'lvmrot', 'buynew', 'rsipullback', 'final_numbers', 'hold',
})

_LVM_POLICY_SKIP = (
    'swap', 'consider', 'book', 'reduce', 'increase', 'watch', 'radar',
    'intro', 'path2', 'dual',
)


def apply_dashboard_policy(payload: dict) -> dict:
    """Single source for HTML + Cursor canvas section visibility."""
    try:
        from src.action_plan_legend import dashboard_policy
        payload['dashboardPolicy'] = dashboard_policy()
    except ImportError:
        payload['dashboardPolicy'] = {'skipSections': [], 'monitorSectionIds': ['radar', 'watch']}
    if payload.get('activeStrategy') == 'LowVol→Mom':
        _skip = payload.setdefault('dashboardPolicy', {}).setdefault('skipSections', [])
        for _s in _LVM_POLICY_SKIP:
            if _s not in _skip:
                _skip.append(_s)
        payload['dashboardPolicy']['skipSections'] = [
            s for s in _skip if s not in _LVM_DASHBOARD_KEEP_SECTIONS
        ]
        payload['dashboardPolicy']['activeStrategy'] = 'LowVol→Mom'
    return payload


def stamp_dashboard_build_version(payload: dict, report_path: Path) -> dict:
    try:
        from src.dashboard_browser import dashboard_build_version
        payload['buildVersion'] = dashboard_build_version(payload, report_path)
    except ImportError:
        payload['buildVersion'] = f"{payload.get('runDate', '')}|{report_path.name}"
    return payload

_ITEM_KEYS = frozenset({
    'stock', 'company', 'targetSymbol', 'action', 'amount', 'value', 'detail', 'when',
    'pnlPct', 'reason', 'reasonPlain', 'sellWhy', 'sellWhyPlain',
    'stopLoss', 'gttStop', 'gttStopPct', 'stopTier', 'bookPct', 'sleeve', 'type',
    'score', 'adjScore', 'v1Score', 'v2Score',
    'sector', 'ml', 'mlConf', 'risk', 'price', 'qty',
    'tier', 'tierPlain', 'trigger', 'triggerPlain',
    'entryScenariosRef', 'categoryLabel',
})

_HOLDING_KEYS = frozenset({
    'stock', 'company', 'qty', 'action', 'value', 'price', 'pnl', 'pnlPct', 'pnlPctAlloc',
    'when', 'score', 'v2Score', 'sector', 'stopLoss', 'gttStop', 'gttStopPct', 'ml',
    'reason', 'reasonPlain', 'summaryLine', 'monitorScenarios',
})

_GUIDE_KEYS = frozenset({
    'readingRule', 'radarTiers', 'entryScenarios', 'exitScenarios',
    'monitorLevels', 'sellWhyCodes', 'reasonPatterns',
})

_SCENARIO_KEYS = frozenset({
    'symbol', 's1', 's2', 's3', 'e1', 'e2', 'e3', 'm1', 'm2', 'm3',
})


_SCENARIO_LINE_PATTERNS = (
    ('s1', re.compile(r'^\s*S1\b', re.I)),
    ('s2', re.compile(r'^\s*S2\b', re.I)),
    ('s3', re.compile(r'^\s*S3\b', re.I)),
    ('e1', re.compile(r'^\s*E1\b', re.I)),
    ('e2', re.compile(r'^\s*E2\b', re.I)),
    ('e3', re.compile(r'^\s*E3\b', re.I)),
    ('m1', re.compile(r'^\s*M1\b', re.I)),
    ('m2', re.compile(r'^\s*M2\b', re.I)),
    ('m3', re.compile(r'^\s*M3\b', re.I)),
)

_STRUCTURED_KEYS = frozenset({
    'symbol', 'price', 'invest', 'full_qty', 'half_qty', 'support',
    'hold_floor', 'pullback_lo', 'pullback_hi', 'breakdown',
})


def _parse_scenario_lines(lines: Any) -> dict:
    out: Dict[str, str] = {}
    for line in lines or []:
        text = str(line).strip()
        for key, pattern in _SCENARIO_LINE_PATTERNS:
            if key in out or not pattern.match(text):
                continue
            out[key] = re.sub(r'^\s*[SEM][123][^:]*:\s*', '', text, flags=re.I)
    return out


def _slim_scenario_block(block: Any) -> Optional[dict]:
    if not block or not isinstance(block, dict):
        return None
    out = {k: block[k] for k in _SCENARIO_KEYS if block.get(k)}
    if block.get('symbol'):
        out['symbol'] = block['symbol']
    parsed = _parse_scenario_lines(block.get('lines'))
    for key, val in parsed.items():
        out.setdefault(key, val)
    structured = block.get('structured')
    if isinstance(structured, dict):
        compact = {k: structured[k] for k in _STRUCTURED_KEYS if k in structured}
        if compact and not (out.get('m1') or out.get('s1') or out.get('e1')):
            out['structured'] = compact
    return out if len(out) > 1 or out.get('s1') or out.get('e1') or out.get('m1') else out or None


def _slim_action_item(item: dict) -> dict:
    """Keep major row fields; only trim bulky scenario line arrays."""
    out = {k: item[k] for k in _ITEM_KEYS if k in item}
    for key in ('entryScenarios', 'exitScenarios', 'monitorScenarios'):
        if key not in item:
            continue
        slim = _slim_scenario_block(item[key])
        if slim:
            out[key] = slim
    return out


def _section_has_rows(sec: dict) -> bool:
    if sec.get('kind') == 'footer':
        return True
    if sec.get('grouped'):
        return any((g.get('stocks') or []) for g in sec['grouped'])
    return bool(sec.get('items'))


def _slim_action_section(sec: dict) -> dict:
    out: Dict[str, Any] = {
        k: sec[k]
        for k in ('id', 'kind', 'headline', 'subhead', 'note', 'tone', 'totalLabel', 'totalValue')
        if k in sec
    }
    if sec.get('kind') == 'footer':
        if sec.get('finalNumbers'):
            out['finalNumbers'] = sec['finalNumbers']
        return out
    if sec.get('grouped'):
        out['grouped'] = []
        for cat in sec['grouped']:
            stocks = [_slim_action_item(s) for s in (cat.get('stocks') or [])]
            if stocks:
                out['grouped'].append({
                    'code': cat.get('code', ''),
                    'label': cat.get('label', ''),
                    'stocks': stocks,
                })
    else:
        out['items'] = [_slim_action_item(i) for i in (sec.get('items') or [])]
    return out


def _slim_action_document(doc: dict, skip_sections: frozenset) -> dict:
    sections: List[dict] = []
    for sec in (doc or {}).get('sections') or []:
        sid = sec.get('id', '')
        if sid in skip_sections:
            continue
        if not _section_has_rows(sec):
            continue
        sections.append(_slim_action_section(sec))
    return {'sections': sections}


def _slim_guide(guide: dict) -> dict:
    return {k: guide[k] for k in _GUIDE_KEYS if k in (guide or {})}


def _slim_holding_row(row: dict) -> dict:
    out = {k: row[k] for k in _HOLDING_KEYS if k in row and k != 'monitorScenarios'}
    if row.get('summaryLine'):
        out.pop('reason', None)
    if row.get('monitorScenarios'):
        slim = _slim_scenario_block(row['monitorScenarios'])
        if slim:
            slim.pop('structured', None)
            slim.pop('symbol', None)
            out['monitorScenarios'] = slim
    return out


def _slim_holdings(rows: List[dict]) -> List[dict]:
    return [_slim_holding_row(row) for row in (rows or [])]


def slim_dashboard_payload(payload: dict) -> dict:
    """HTML dashboard payload: visible sections only; major row fields kept."""
    try:
        from src.action_plan_legend import DASHBOARD_SKIP_SECTIONS
        default_skip = DASHBOARD_SKIP_SECTIONS
    except ImportError:
        default_skip = frozenset({
            'intro', 'vmq', 'path2', 'dual', 'hold_note', 'hold', 'sell_breakdown',
        })
    policy_skip = (payload.get('dashboardPolicy') or {}).get('skipSections')
    skip = frozenset(policy_skip) if policy_skip is not None else default_skip

    slim: Dict[str, Any] = {}
    for key in _DASHBOARD_PAYLOAD_KEYS:
        if key not in payload:
            continue
        if key == 'actionDocument':
            slim[key] = _slim_action_document(payload[key], skip)
        elif key == 'actionPlanGuide':
            slim[key] = _slim_guide(payload[key])
        elif key == 'holdings':
            slim[key] = _slim_holdings(payload[key])
        else:
            slim[key] = payload[key]
    return slim


def render_dashboard_html(payload: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding='utf-8')
    css = CSS_PATH.read_text(encoding='utf-8')
    js = JS_PATH.read_text(encoding='utf-8')
    data_script = (
        '<script id="dashboard-data">\n'
        f'window.DASHBOARD_DATA = {json.dumps(payload, ensure_ascii=False, separators=(",", ":"))};\n'
        '</script>'
    )
    if '<!--DASHBOARD_DATA-->' not in template:
        raise ValueError(f'Missing <!--DASHBOARD_DATA--> marker in {TEMPLATE_PATH}')
    html = template.replace('<!--INLINE_CSS-->', f'<style>\n{css}\n</style>', 1)
    html = html.replace('<!--INLINE_JS-->', f'<script>\n{js}\n</script>', 1)
    return html.replace('<!--DASHBOARD_DATA-->', data_script, 1)


def build_analysis_dashboard(
    report_file: str,
    allocation_df: Optional[pd.DataFrame] = None,
    portfolio_amount: float = 0,
    regime: str = 'Sideways',
    repo_root: Path | None = None,
    output_path: Path | None = None,
    open_browser: bool = False,
    sync_canvas: bool = True,
) -> Optional[Path]:
    """Build self-contained HTML dashboard from latest Excel report."""
    root = repo_root or REPO_ROOT
    report_path = Path(report_file)
    if not report_path.is_absolute():
        report_path = root / report_path
    if not report_path.exists():
        print(f'[DASH] Skip — report not found: {report_path}')
        return None

    try:
        from scripts.update_analysis_canvas import build_dashboard_payload
    except ImportError:
        print('[DASH] Skip — update_analysis_canvas unavailable')
        return None

    if allocation_df is None:
        allocation_df = pd.read_excel(report_path, sheet_name='Portfolio Allocation', header=1)
    if allocation_df is None or allocation_df.empty:
        print('[DASH] Skip — empty Portfolio Allocation sheet')
        return None

    payload = build_dashboard_payload(
        str(report_path),
        allocation_df,
        portfolio_amount=portfolio_amount,
        regime=regime,
        repo_root=root,
    )
    payload['reportPath'] = str(report_path.resolve())
    apply_dashboard_policy(payload)
    stamp_dashboard_build_version(payload, report_path)

    slim = slim_dashboard_payload(payload)
    slim['buildVersion'] = payload['buildVersion']
    html = render_dashboard_html(slim)
    out = output_path or DEFAULT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    json_kb = len(json.dumps(slim, ensure_ascii=False, separators=(',', ':'))) // 1024
    print(f'[DASH] Dashboard written: {out} ({len(html) // 1024} KB, data {json_kb} KB)')
    if sync_canvas:
        try:
            from scripts.update_analysis_canvas import update_analysis_canvas

            canvas_path = update_analysis_canvas(
                str(report_path),
                allocation_df=allocation_df,
                portfolio_amount=portfolio_amount,
                regime=regime,
                repo_root=root,
            )
            if canvas_path:
                print(f'[DASH] Cursor canvas synced: {canvas_path}')
        except Exception as canvas_err:
            print(f'[DASH] Canvas sync skipped: {canvas_err}')
    if open_browser:
        try:
            from src.dashboard_browser import open_analysis_dashboard

            open_analysis_dashboard()
        except Exception as browser_err:
            print(f'[DASH] Browser open failed: {browser_err}')
            if 'another checkout' in str(browser_err).lower():
                print('[DASH] Fix: kill $(lsof -ti :9876) then python3 scripts/serve_dashboard.py --open')
    return out
