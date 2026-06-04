---
name: india-markets-fundamental
description: >-
  Fundamental equity analysis for NSE names in Stock_Analysis. Uses
  enhanced_fundamental_analyzer, yfinance/Upstox cache, v2 components
  (fundamental_quality, growth, value), and Complete Data / Undervalued Excel
  sheets. Use for business quality, PE/ROE/D/E, peer comps, or explaining
  fundamental scores in analyze_top200 reports.
---

# Fundamental Desk — Stock_Analysis

## Repo modules

| Module | Role |
|--------|------|
| `src/enhanced_fundamental_analyzer.py` | `get_comprehensive_stock_data` — PE, ROE, D/E, growth |
| `hybrid_scoring_v2.py` | Components: `fundamental_quality`, `growth`, `value` |
| `StockDataBundle` in `analyze_top200_stocks_enhanced.py` | Single 5Y yfinance pull per symbol |

## Read data (in order)

1. `data/cache/{SYMBOL}_comprehensive_*.json` (newest)
2. Excel **Complete Data**, **Undervalued**, **Valuation Analysis** sheets
3. Run if missing:

```bash
cd /Users/akulakavyashree/TestNetstock/Stock_Analysis
python main.py -s SYMBOL --risk-profile aggressive
```

Symbols in universe CSV are bare tickers (`RELIANCE`); yfinance uses `.NS` internally.

## Workflow

1. Pull pipeline fundamental components and raw ratios from cache/report.
2. Compare to sector peers in same report (Sector Analysis sheet).
3. Separate **pipeline score** from **your qualitative bull/bear** narrative.
4. Flag data gaps (yfinance `.info` missing fields — common on smallcaps).

## Report template

```markdown
# [SYMBOL] — Fundamental Memo

**Pipeline:** fundamental_quality=X growth=Y value=Z | **Score:** 

## From cache/report
| Metric | Value | 3Y trend | vs sector |
|--------|-------|----------|-----------|

## Qualitative
- Bull / Bear / Base

## Pipeline alignment
[Agrees / diverges from v2 action — why]

## Repo note
[Cache path | sheet row | re-run needed?]
```

## India checks

- Consolidated vs standalone in yfinance (prefer consolidated)
- ETF/InvIT exclusion already handled by `src/universe_filter.py`
- ML tag suppressed in recommendations until accuracy > 60% — do not overweight ML in narrative

## Hand off

- Entry timing → `india-markets-technical`, `src/turbo_entry.py`
- Regime tilt → `india-markets-macro`
- Allocation / action enum → `india-markets-portfolio`

## Five-Agent Council

**This desk is research-only.** Do not edit scoring code from a fundamental memo.

Escalate via shared template: `.cursor/skills/five-agent-council/references/council-escalation-template.md`

| Escalate when | Council agents most involved |
|---------------|------------------------------|
| v2 fundamental_quality/growth/value weights or thresholds | QUANT, AUDIT |
| yfinance/Upstox data pipeline or cache schema | ARCH, AUDIT |
| Universe exclusion affecting fundamental coverage | RISK, QUANT |

Bridge: `.cursor/skills/five-agent-council/references/product-teams-bridge.md`
