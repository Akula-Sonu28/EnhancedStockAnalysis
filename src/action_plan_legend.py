"""Action-plan category guide — printed before priority sections."""
from __future__ import annotations

from typing import Iterable, List

# (section_key, title, meaning, typical REASON / trigger)
ACTION_PLAN_CATEGORIES: List[tuple] = [
    (
        'VMQ',
        'VMQ STRATEGY',
        'Validated Momentum-Quality exits and entry gates (overrides rank when loss or gate fails).',
        'VMQ HARD STOP (-8%), VMQ SWING STOP (-5%), churn cap 3/3, turbo/value-trap block',
    ),
    (
        'PATH2',
        'PATH 2 — BALANCED',
        'Softer rank trims + Breakout Radar watchlist (vol/momentum coils, not full NEW yet).',
        'Rank SELL softened to CONSIDER; radar tiers B-IGNITE / A+-READY / A-COIL',
    ),
    (
        'RADAR',
        'PRIORITY 4: BREAKOUT RADAR',
        'Monday timing watch — needs vol≥2.5× avg AND +2.5% day (or break 20d high for coils).',
        'Per-row: tier + ignition/coil reason + monday_trigger column',
    ),
    (
        'SELL_CAT',
        'SELL CATEGORY BREAKDOWN',
        'Groups every SELL by SELL WHY code so you see the rule, not just the label.',
        'VMQ_HARD_STOP, VMQ_SWING_STOP, THESIS_BREAK, RANK_REBALANCE, …',
    ),
    (
        'P1',
        'PRIORITY 1: SWAP',
        'Sell a weak holding and rotate proceeds into a higher-scored name (rank upgrade).',
        'Upgrade to SYMBOL (Score +Δ); buy target uses ENTRY SCENARIOS — not market chase',
    ),
    (
        'P1_5',
        'PRIORITY 1.5: EXIT',
        'Momentum exhaustion — partial or full exit before full stop (overbought / tired trend).',
        'EXIT 75-80% / EXIT NOW — Heavy exhaustion',
    ),
    (
        'P2',
        'PRIORITY 2: SELL',
        'Hard exits — execute this week. VMQ stops and confirmed sell signals only.',
        'VMQ HARD/SWING STOP with P&L%; rank/thesis sells when not softened',
    ),
    (
        'P2_5',
        'PRIORITY 2.5: CONSIDER SELLING',
        'Soft trim — review before acting (often flat P&L or path2-softened rank exit).',
        'CONSIDER SELLING — sector cap or rank trim with friction',
    ),
    (
        'P3',
        'PRIORITY 3: BOOK PROFITS',
        'Partial profit booking on winners (keeps core exposure, locks gains).',
        'BOOK_PROFIT with booking % of position',
    ),
    (
        'P3_5',
        'PRIORITY 3.5: REDUCE',
        'Sector diversification trim — too many names in one sector vs cap.',
        'Sector overweight; score override may protect high scorers',
    ),
    (
        'P4_INC',
        'PRIORITY 4: INCREASE',
        'Add to an existing winner within budget and turbo/churn rules.',
        'HOLD STEADY rank + funded INCREASE; blocked → TURBO BLOCK (INCREASE)',
    ),
    (
        'P5',
        'PRIORITY 5: BUY NEW',
        'Rank-based NEW size = budget ceiling. Pick fill via ENTRY SCENARIOS (S1/S2/S3).',
        'High momentum / oracle pick; line shows (system max) shares @ last close',
    ),
    (
        'P5_5',
        'PRIORITY 5.5: WATCHLIST / CONFIRM WAIT',
        'Good name but entry blocked — wait for gate or budget slot.',
        'TURBO BLOCK: churn cap; Budget exhausted; CONFIRM_WAIT (price timing)',
    ),
    (
        'P6',
        'PRIORITY 6: HOLD / KEEP',
        'No trade — rank OK or policy override (oracle no rank-sell, cooldown).',
        'HOLD STEADY (Rank #n); ORACLE_NO_RANK_SELL; RECENT-BUY COOLDOWN',
    ),
    (
        'P7',
        'PRIORITY 7: WATCHLIST',
        'Monitor for a future entry when budget or gates open (duplicate count OK).',
        'Same as 5.5 unfunded NEW — monitor only',
    ),
    (
        'P8',
        'PRIORITY 8: OPTIONAL / SKIP',
        'Low-priority names deprioritized in top-20 NEW cap — no urgency.',
        'Skipped after top-N rank cut for new capital',
    ),
    (
        'DUAL',
        'DUAL STRATEGY VIEW',
        'Turbo MTF (timing) vs Monthly stable — HIGH CONVICTION = both say BUY.',
        'SPLIT = strategies disagree — use primary ACTION column first',
    ),
]

# Column guide (Portfolio Allocation sheet)
COLUMN_GUIDE: List[dict] = [
    {'column': 'ACTION', 'meaning': 'What to do this week (SELL, HOLD, NEW POSITION, WATCHLIST, …)'},
    {'column': 'REASON', 'meaning': 'Human-readable rule that triggered this action — read this first'},
    {'column': 'SELL WHY', 'meaning': 'Exit category code (SELL rows only) — groups the rule type'},
    {'column': 'INVEST ₹', 'meaning': 'Cash to deploy; ₹0 means no buy funded this week'},
    {'column': 'WHEN', 'meaning': 'Timing hint (TODAY vs MONITOR)'},
    {'column': 'MY VALUE ₹', 'meaning': 'Current holding value (₹0 = not owned)'},
]

# Reason text → plain English (matched as substring, first match wins)
REASON_PATTERNS: List[dict] = [
    {'pattern': 'VMQ HARD STOP', 'plain': 'Loss hit the −8% hard stop — exit this week.'},
    {'pattern': 'VMQ SWING STOP', 'plain': 'Loss hit the −5% swing stop — exit this week.'},
    {'pattern': 'VMQ TRAIL', 'plain': 'Price gave back 8% from peak profit — trailing exit.'},
    {'pattern': 'VMQ DAY-3', 'plain': 'Day-3 validation failed (regime-gated in your config).'},
    {'pattern': 'VMQ DAY-5', 'plain': 'Day-5 validation failed.'},
    {'pattern': 'TURBO BLOCK: churn cap', 'plain': 'Weekly NEW slot full (3/3) — no more entries this week.'},
    {'pattern': 'TURBO BLOCK (INCREASE)', 'plain': 'Wanted to add shares but churn cap blocked — stays HOLD.'},
    {'pattern': 'TURBO BLOCK', 'plain': 'Turbo/momentum/MTF gate failed — wait for timing.'},
    {'pattern': 'VMQ BLOCK: value_trap', 'plain': 'High quality but weak momentum — value trap block.'},
    {'pattern': 'Budget exhausted', 'plain': 'Ranked for NEW but ₹0 funded — monitor, not out of cash necessarily.'},
    {'pattern': 'CONFIRM WAIT', 'plain': 'Price/timing confirmation not ready — wait for trigger.'},
    {'pattern': 'ORACLE_NO_RANK_SELL', 'plain': 'Rank-based sell disabled for this name — policy HOLD.'},
    {'pattern': 'HOLD STEADY', 'plain': 'Rank still OK in your book — no trade needed.'},
    {'pattern': 'TOP SCORER but AT LOSS', 'plain': 'Strong rank but underwater — hold, rotate when green.'},
    {'pattern': 'RECENT-BUY COOLDOWN', 'plain': 'Bought recently — suppress flip-flop sells/buys.'},
    {'pattern': 'Upgrade to', 'plain': 'Rotation: sell weak name to fund higher-scored pick.'},
    {'pattern': 'High momentum score', 'plain': 'Turbo/momentum pick — size is budget ceiling, use entry scenarios.'},
    {'pattern': 'ORACLE+TURBO ELIGIBLE', 'plain': 'Passed fq_score + turbo gates — eligible NEW.'},
    {'pattern': 'EXIT NOW', 'plain': 'Momentum exhaustion — full or heavy exit.'},
    {'pattern': 'EXIT 75', 'plain': 'Momentum exhaustion — partial exit (75–80%).'},
    {'pattern': 'Sector overweight', 'plain': 'Too many names in one sector vs cap — trim for diversification.'},
    {'pattern': 'BOOK_PROFIT', 'plain': 'Partial profit booking on a winner.'},
    {'pattern': 'Pick rank:', 'plain': 'Holdings pick rank vs rest of book (negative = lower in book).'},
    {'pattern': 'Rank #', 'plain': 'Relative rank in your portfolio (lower number = stronger).'},
    {'pattern': 'SWAP_ROTATION', 'plain': 'Sold to fund a higher-scored rotation target.'},
]

DASHBOARD_SKIP_SECTIONS = frozenset({
    'intro', 'vmq', 'path2', 'dual', 'hold_note', 'hold', 'sell_breakdown',
})
_DASHBOARD_SKIP_SECTIONS = DASHBOARD_SKIP_SECTIONS

DASHBOARD_MONITOR_SECTIONS = frozenset({'radar', 'watch'})


def dashboard_policy() -> dict:
    """Single source of truth for HTML dashboard visibility rules."""
    return {
        'skipSections': sorted(DASHBOARD_SKIP_SECTIONS),
        'monitorSectionIds': sorted(DASHBOARD_MONITOR_SECTIONS),
    }

RADAR_TIERS: List[dict] = [
    {'tier': 'B-IGNITE', 'meaning': 'Ignition day — big up move (+2.5%+) with heavy volume (≥2.5× avg). Already moving; higher chase risk.'},
    {'tier': 'A+-READY', 'meaning': 'Coiled tight under 20-day high — best risk/reward if Monday breaks with volume.'},
    {'tier': 'A-COIL', 'meaning': 'Classic coil below highs — wait for volume surge and break above resistance.'},
    {'tier': 'C-MOM-POP', 'meaning': 'Quality + MTF strong but momentum still flat — needs a momentum pop before entry.'},
]

ENTRY_SCENARIOS: List[dict] = [
    {'code': 'S1', 'label': 'Hold / half-size', 'meaning': 'Open holds above the hold floor → buy half the rank size only (no chase).'},
    {'code': 'S2', 'label': 'Pullback', 'meaning': 'Price retests the pullback band → preferred full-size limit entry.'},
    {'code': 'S3', 'label': 'Break / skip', 'meaning': 'Daily close below breakdown level → skip NEW; thesis or support broken.'},
]

EXIT_SCENARIOS: List[dict] = [
    {'code': 'E1', 'label': 'Open / scale', 'meaning': 'Execute at market open — hard exit or scale-out partial.'},
    {'code': 'E2', 'label': 'Bounce / limit', 'meaning': 'Limit sell into resistance bounce for a better fill.'},
    {'code': 'E3', 'label': 'Defer / skip', 'meaning': 'Skip trim if support holds — review next run (soft exits only).'},
]

MONITOR_LEVELS: List[dict] = [
    {'code': 'M1', 'label': 'Hold', 'meaning': 'Close above support — keep position, no trade.'},
    {'code': 'M2', 'label': 'Review', 'meaning': 'Close below support — revisit on next run.'},
    {'code': 'M3', 'label': 'Alert', 'meaning': 'Close below breakdown — thesis broken; expect SELL path.'},
]

RADAR_FIELD_HINTS: List[dict] = [
    {'abbr': 'mtf', 'meaning': 'Multi-timeframe score — trend alignment across horizons (higher = stronger).'},
    {'abbr': 'vol', 'meaning': 'Volume vs 20-day average (2.5× = ignition threshold).'},
    {'abbr': 'ignition', 'meaning': 'Same-day surge: large up move plus volume spike.'},
    {'abbr': 'coil', 'meaning': 'Price compressed near resistance — breakout not confirmed yet.'},
    {'abbr': 'fund', 'meaning': 'Fundamental quality score from the hybrid model.'},
    {'abbr': 'mom', 'meaning': 'Momentum / technical score (not yet extended).'},
]

TRIGGER_HINTS: List[dict] = [
    {'pattern': 'vol>=2.5x', 'meaning': 'Volume at least 2.5× the 20-day average.'},
    {'pattern': '+2.5% day', 'meaning': 'Stock up at least 2.5% on the session.'},
    {'pattern': '20d high', 'meaning': 'Break above the 20-day high confirms a coil breakout.'},
    {'pattern': 'Active:', 'meaning': 'Trigger already firing today — act or wait for pullback (tier-dependent).'},
]

DUAL_CONSENSUS: List[dict] = [
    {'label': 'BUY (both agree)', 'meaning': 'HIGH CONVICTION — turbo timing and monthly stable both say buy.'},
    {'label': 'SPLIT', 'meaning': 'Strategies disagree — follow primary ACTION column first.'},
    {'label': 'SELL (both agree)', 'meaning': 'Both profiles say exit — act on primary SELL if present.'},
]

READING_RULE = (
    'Trust REASON + SELL WHY over the priority headline alone. '
    'INVEST ₹ = 0 means no buy funded even if rank is good.'
)

# Rich per-section tables for HTML dashboard (mirrors terminal action-plan guide).
SECTION_RICH: dict = {
    'INTRO': {
        'tables': [{
            'title': 'How to read any row',
            'subtitle': 'Every stock in Portfolio Allocation has:',
            'headers': ['Column', 'Meaning'],
            'rows': [[c['column'], c['meaning']] for c in COLUMN_GUIDE[:4]],
        }],
        'callouts': [READING_RULE],
    },
    'VMQ': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['VMQ HARD STOP: loss −X% ≤ −8%', 'Cut loser at −8%'],
                ['VMQ SWING STOP: loss −X% ≤ −5%', 'Cut at −5% swing line'],
                ['TURBO BLOCK: churn cap 3/3', 'Already 3 NEW in 7 days — no more entries'],
                ['TURBO BLOCK: turbo/mom/mtf …', 'Score/timing gate failed'],
                ['VMQ BLOCK: value_trap …', 'High quality, weak momentum trap'],
            ],
        }],
    },
    'PATH2': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['Rank SELL → CONSIDER', 'Would sell on rank alone, but P&L flat — you decide'],
                ['Breakout Radar sheet', 'Coil/ignition names for Monday triggers'],
            ],
        }],
    },
    'RADAR': {
        'tables': [{
            'title': 'Tier',
            'headers': ['Tier', 'Meaning'],
            'rows': [[t['tier'], t['meaning']] for t in RADAR_TIERS],
        }],
        'callouts': [
            'Trigger: vol ≥ 2.5× average and +2.5% day (or break 20d high for coils).',
        ],
    },
    'SELL_CAT': {
        'tables': [{
            'title': 'SELL WHY',
            'headers': ['SELL WHY', 'Meaning'],
            'rows': [
                ['VMQ_HARD_STOP', 'Loss beyond −8%'],
                ['VMQ_SWING_STOP', 'Loss beyond −5%'],
                ['VMQ_TRAIL_STOP', 'Gave back 8% from peak profit'],
                ['VMQ_DAY3/5_FAIL', 'Early validation fail (day-3/5 OFF in your config)'],
                ['THESIS_BREAK', 'Fundamentals broke'],
                ['EMERGENCY_EXIT', 'Deep loss + weak score'],
                ['RANK_REBALANCE', 'Bottom rank trim'],
                ['SWAP_ROTATION', 'Sold to fund stronger name'],
                ['RANK_DISABLED_HOLD', 'Rank sell turned off — should HOLD'],
                ['NOT_SELL', 'Listed in exit summary but action isn\'t SELL (e.g. watch)'],
            ],
        }],
    },
    'P1': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['Upgrade to SYMBOL (Score +Δ)', 'Rotation score gap large enough'],
            ],
        }],
        'callouts': [
            'Proceeds from the sold name ≠ “buy at market now”. Use ENTRY SCENARIOS (S1/S2/S3) on the target.',
        ],
    },
    'P1_5': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['EXIT 75–80% / EXIT NOW', 'Overbought / momentum exhaustion — partial or full exit'],
            ],
        }],
    },
    'P2': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['VMQ HARD/SWING STOP', 'Hard loss exit — execute this week'],
            ],
        }],
    },
    'P2_5': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['Sector cap / rank trim, flat P&L', 'Path2 softened — not mandatory'],
            ],
        }],
    },
    'P3': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['BOOK_PROFIT + booking %', 'Partial sell on winner — keep core exposure'],
            ],
        }],
    },
    'P3_5': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['Too many names in one sector vs SECTOR_CAP', 'High scorers (≥75) may be protected'],
            ],
        }],
    },
    'P4_INC': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['HOLD STEADY (Rank #n) + funded INCREASE', 'Rank OK, budget allocated'],
                ['TURBO BLOCK (INCREASE): churn cap 3/3', 'Blocked → stays HOLD, ₹0'],
            ],
        }],
    },
    'P5': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['High momentum score: 100/100', 'Turbo/momentum picked it'],
                ['ORACLE+TURBO ELIGIBLE', 'fq_score + turbo pass'],
            ],
        }],
        'callouts': [
            'Rank-based max size = budget ceiling, not “market order now”. Use ENTRY SCENARIOS: S1 half / S2 pullback / S3 skip.',
        ],
    },
    'P5_5': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['TURBO BLOCK: churn cap 3/3', 'Weekly NEW slots full'],
                ['Budget exhausted — monitor for future entry', 'Ranked NEW but ₹0 funded (not always out of cash)'],
                ['CONFIRM_WAIT / short confirm …', 'Timing not ready — wait for price'],
                ['RSI … hard block / chase 5d …', 'Extended move — wait'],
            ],
        }],
    },
    'P6': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['HOLD STEADY (Rank #n/19)', 'Still in upper book ranks'],
                ['ORACLE_NO_RANK_SELL', 'Policy: don\'t rank-sell core/oracle names'],
                ['TOP SCORER but AT LOSS', 'Good rank, underwater — don\'t panic sell'],
                ['TURBO BLOCK (INCREASE): churn cap', 'Wanted to add, blocked → hold'],
                ['RECENT-BUY COOLDOWN', 'Bought recently — suppress flip-flop'],
            ],
        }],
    },
    'P7': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['Same as 5.5 unfunded NEW', 'Monitor only — duplicate summary count OK'],
            ],
        }],
    },
    'P8': {
        'tables': [{
            'title': 'Typical REASON',
            'headers': ['Typical REASON', 'Meaning'],
            'rows': [
                ['Skipped after top-N rank cut', 'Deprioritized NEW — no urgency'],
            ],
        }],
    },
    'DUAL': {
        'tables': [{
            'title': 'Consensus',
            'headers': ['Consensus', 'Meaning'],
            'rows': [[d['label'], d['meaning']] for d in DUAL_CONSENSUS] + [
                ['Turbo BUY + Primary WATCHLIST', 'Timing likes it; gates/budget still block'],
            ],
        }],
    },
}


def enrich_section_guide(key: str, base: dict) -> dict:
    """Merge rich tables/callouts into a section guide dict for the dashboard."""
    rich = SECTION_RICH.get(key, {})
    out = dict(base)
    if rich.get('tables'):
        out['tables'] = rich['tables']
    if rich.get('callouts'):
        out['callouts'] = rich['callouts']
    if key == 'INTRO' and not out.get('columns'):
        out['columns'] = COLUMN_GUIDE[:4]
    return out


def decode_tier_plain(tier: str) -> str:
    t = str(tier or '').strip()
    for item in RADAR_TIERS:
        if item['tier'] == t:
            return item['meaning']
    return ''


def decode_sell_why_plain(code: str) -> str:
    c = str(code or '').strip()
    if not c or c == 'NOT_SELL':
        return ''
    try:
        from src.picking_metrics import SELL_CATEGORY_LABELS
        return str(SELL_CATEGORY_LABELS.get(c, '') or '')
    except ImportError:
        return ''


def decode_trigger_plain(trigger: str) -> str:
    text = str(trigger or '').strip()
    if not text:
        return ''
    parts: List[str] = []
    low = text.lower()
    for hint in TRIGGER_HINTS:
        if hint['pattern'].lower() in low:
            parts.append(hint['meaning'])
    if parts:
        return ' '.join(dict.fromkeys(parts))
    return text


def explain_radar_reason(reason: str) -> str:
    r = str(reason or '').strip()
    if not r:
        return ''
    if r.startswith('ignition'):
        return (
            'Breakout already started: strong up day with volume surge. '
            'Higher chase risk — prefer pullback entry unless tier policy allows fast-track.'
        )
    if r.startswith('coil ready'):
        return 'Tight coil near 20-day high — watch Monday for volume + break (best risk/reward).'
    if r.startswith('coil '):
        return 'Coiling below highs — needs volume and a break before entry.'
    if 'mom pop needed' in r:
        return 'Fundamentals and MTF are strong; momentum still needs to accelerate.'
    return r


def build_context_glossary(
    action_document: dict | None = None,
    holdings: List[dict] | None = None,
) -> List[dict]:
    """Glossary entries for codes that appear in this run (dashboard chip strip + help)."""
    seen: set = set()
    entries: List[dict] = []

    def add(code: str, meaning: str, kind: str, label: str = '') -> None:
        c = str(code or '').strip()
        m = str(meaning or '').strip()
        if not c or not m:
            return
        key = (kind, c.upper())
        if key in seen:
            return
        seen.add(key)
        entries.append({
            'code': c,
            'label': label or c,
            'meaning': m,
            'kind': kind,
        })

    sections = (action_document or {}).get('sections') or []
    for sec in sections:
        if sec.get('id') in DASHBOARD_SKIP_SECTIONS:
            continue
        items: List[dict] = list(sec.get('items') or [])
        for grp in sec.get('grouped') or []:
            items.extend(grp.get('stocks') or [])
        for it in items:
            tier = it.get('tier')
            if tier:
                add(str(tier), decode_tier_plain(str(tier)), 'tier')
            sw = it.get('sellWhy')
            if sw and str(sw) != 'NOT_SELL':
                add(str(sw), decode_sell_why_plain(str(sw)) or str(sw), 'sellWhy')
            reason = str(it.get('reason') or '')
            plain = str(it.get('reasonPlain') or '') or decode_reason_plain(reason)
            if plain:
                for pat in REASON_PATTERNS:
                    if pat['pattern'].upper() in reason.upper():
                        add(pat['pattern'], pat['plain'], 'reason')
            if it.get('entryScenarios'):
                for es in ENTRY_SCENARIOS:
                    add(es['code'], es['meaning'], 'entry', es['label'])
            trig = it.get('trigger')
            if trig:
                tp = decode_trigger_plain(str(trig))
                if tp and tp != str(trig):
                    add('Monday trigger', tp, 'trigger')

    for row in holdings or []:
        reason = str(row.get('reason') or '')
        plain = str(row.get('reasonPlain') or '') or decode_reason_plain(reason)
        if plain:
            for pat in REASON_PATTERNS:
                if pat['pattern'].upper() in reason.upper():
                    add(pat['pattern'], pat['plain'], 'reason')

    # Stable reference blocks when radar or entries appear in this brief
    kinds = {e['kind'] for e in entries}
    if 'tier' in kinds:
        for t in RADAR_TIERS:
            add(t['tier'], t['meaning'], 'tier')
    if 'entry' in kinds:
        for es in ENTRY_SCENARIOS:
            add(es['code'], es['meaning'], 'entry', es['label'])

    order = {'tier': 0, 'entry': 1, 'sellWhy': 2, 'reason': 3, 'trigger': 4}
    entries.sort(key=lambda e: (order.get(e['kind'], 9), e['code']))
    return entries


def build_dashboard_glossary() -> dict:
    """Structured glossary for HTML dashboard Guide tab."""
    try:
        from src.picking_metrics import SELL_CATEGORY_LABELS
        sell_why = [
            {'code': code, 'label': label}
            for code, label in sorted(SELL_CATEGORY_LABELS.items())
        ]
    except ImportError:
        sell_why = []

    categories = []
    for key, title, meaning, reasons in ACTION_PLAN_CATEGORIES:
        categories.append({
            'key': key,
            'title': title,
            'what': meaning,
            'typicalReason': reasons,
        })

    return {
        'readingRule': READING_RULE,
        'columns': COLUMN_GUIDE,
        'categories': categories,
        'reasonPatterns': REASON_PATTERNS,
        'sellWhyCodes': sell_why,
        'radarTiers': RADAR_TIERS,
        'entryScenarios': ENTRY_SCENARIOS,
        'exitScenarios': EXIT_SCENARIOS,
        'monitorLevels': MONITOR_LEVELS,
        'radarFieldHints': RADAR_FIELD_HINTS,
        'triggerHints': TRIGGER_HINTS,
        'dualConsensus': DUAL_CONSENSUS,
    }


def decode_reason_plain(
    reason: str,
    action: str | None = None,
    sell_why: str | None = None,
) -> str:
    """Return plain-English line for a REASON string."""
    act_u = str(action or '').upper()
    if 'SELL' in act_u:
        sw_plain = decode_sell_why_plain(str(sell_why or ''))
        if sw_plain:
            return sw_plain
        if 'LVM ROTATION' in act_u:
            return 'LVM rotation (not in active Top-N roster — rotate out)'
    text = str(reason or '').strip()
    if not text:
        return ''
    upper = text.upper()
    for item in REASON_PATTERNS:
        if item['pattern'].upper() in upper:
            return item['plain']
    return ''



def format_action_plan_legend(keys: Iterable[str] | None = None) -> List[str]:
    """Return legend lines; optional keys filter to sections present this run."""
    keyset = set(keys) if keys else None
    lines = [
        'ACTION PLAN GUIDE — categories and typical REASON text:',
        '(Execute priorities top-down; REASON column in Excel has per-stock detail)',
        '',
    ]
    for key, title, meaning, reasons in ACTION_PLAN_CATEGORIES:
        if keyset is not None and key not in keyset:
            continue
        lines.append(f'  • {title}')
        lines.append(f'      What: {meaning}')
        lines.append(f'      Typical REASON: {reasons}')
        lines.append('')
    return lines


def print_action_plan_legend(keys: Iterable[str] | None = None) -> None:
    for line in format_action_plan_legend(keys):
        print(line)


def row_reason_text(row, max_len: int = 90) -> str:
    """Best REASON string from a Portfolio Allocation row."""
    if hasattr(row, 'get'):
        data = row
    else:
        data = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
    for col in ('REASON', 'exit_reason', 'action_reason', 'vmq_reason', 'DETAIL'):
        val = data.get(col)
        if val is not None and str(val).strip() and str(val).lower() not in ('nan', 'none'):
            return str(val).strip()[:max_len]
    return ''


def format_holdings_action_lines(
    df,
    *,
    value_col: str = 'MY VALUE ₹',
    pnl_col: str = 'P&L %',
) -> List[str]:
    """Symbol + ACTION + REASON (+ optional P&L) for terminal listing.
    
    P&L is shown only when:
    - It is not NaN/None/'nan'/'none'
    - If near zero, avg_cost must exist (otherwise it's missing data, not breakeven)
    """
    lines: List[str] = []
    if df is None or df.empty:
        return lines
    for _, row in df.iterrows():
        sym = str(row.get('symbol', '?'))
        act = str(row.get('ACTION', 'HOLD')).strip()
        rsn = row_reason_text(row)
        pnl = row.get(pnl_col, row.get('Profit_Margin', ''))
        extra = ''
        if pnl != '' and pnl is not None and str(pnl).lower() not in ('nan', 'none'):
            try:
                pnl_f = float(pnl)
                # Check for misleading 0.0% from missing cost basis
                show_pnl = True
                if abs(pnl_f) < 0.05:
                    avg_cost = row.get('avg_cost', row.get('Avg. cost', 0))
                    try:
                        avg_cost_f = float(avg_cost) if avg_cost is not None else 0
                    except (TypeError, ValueError):
                        avg_cost_f = 0
                    if avg_cost_f <= 0:
                        show_pnl = False
                if show_pnl:
                    extra = f" · P&L {pnl_f:+.1f}%"
            except (TypeError, ValueError):
                pass
        val = row.get(value_col, row.get('current_value', 0))
        try:
            val_s = f" · ₹{float(val):,.0f}" if float(val) > 0 else ''
        except (TypeError, ValueError):
            val_s = ''
        line = f"  {sym}: {act}"
        if rsn:
            line += f" — {rsn}"
        line += f"{extra}{val_s}"
        lines.append(line)
    return lines
