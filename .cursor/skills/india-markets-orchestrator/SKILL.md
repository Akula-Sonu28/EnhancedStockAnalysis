---
name: india-markets-orchestrator
description: >-
  Coordinates the india-markets specialist desk for NSE equity research inside
  Stock_Analysis. Routes to fundamental, technical, macro/regime, portfolio, and
  research-only derivatives/IPO desks; reads pipeline output (Excel, cache,
  recommendation_history); integrates with stock-analysis-system,
  post-analysis-audit, and turbo-mtf-weekly-trader. Use for Indian stock questions,
  multi-angle views on Nifty 500 names, interpreting analyzer actions/scores, or
  weekly investment narrative on top of analyze_top200 output.
---

# India Markets Orchestrator — Stock_Analysis

You lead a **multi-desk research layer** on top of the Stock_Analysis NSE pipeline (`analyze_top200_stocks_enhanced.py`, hybrid v2 scoring, Zerodha-aware allocation).

## Repo context (read first)

1. [references/repo-integration.md](references/repo-integration.md) — commands, modules, contracts
2. [references/team-roster.md](references/team-roster.md) — which desk maps to which code
3. [references/data-sources.md](references/data-sources.md) — where to read scores/prices

Also load **`stock-analysis-system`** when the user touches config, scoring code, or report contracts.

## Skill routing (Stock_Analysis)

| User trigger | Skill to use (not india-markets) |
|--------------|----------------------------------|
| `ANALYSE` / audit latest run | `post-analysis-audit` |
| Weekly dry-run vs live, Turbo MTF | `turbo-mtf-weekly-trader` |
| Change scoring, thresholds, architecture | `five-agent-council` + `stock-analysis-system` |

## Mandatory disclaimer

End synthesized research with:

> **Disclaimer:** Educational research from pipeline output, not SEBI-registered investment advice. Verify with official sources before acting.

## Workflow

```
User question
  → Classify: pipeline-interpret vs pure research vs code change
  → If code change → hand off to five-agent-council
  → If ANALYSE → post-analysis-audit
  → Else: pick desks (team-roster)
  → Load latest repo artifacts OR run:
       python main.py -s SYMBOL --risk-profile aggressive
  → Delegate desk memos (parallel Task when independent)
  → Synthesize with pipeline action/score vs desk narrative
  → Disclaimer
```

## Repo-first data rule

Before narrative:

1. Newest `reports/Enhanced_Stock_Report_*.xlsx`
2. `data/cache/{SYMBOL}_comprehensive_*.json`
3. `data/recommendation_history.csv` row for symbol
4. `data/last_known_regime.json` for macro desk

Run analyzer only if missing/stale. Prefer `--dry-run --fast` for previews.

## Synthesis template

```markdown
# [SYMBOL] — Multi-Desk View (Stock_Analysis)

**As of:** [report timestamp] | **Regime:** [from cache] | **Pipeline:** score X → ACTION

## Executive summary
- Pipeline says: ...
- Desks agree/disagree on: ...

## Desk memos
### Fundamental — [fundamental_quality / growth / value from report]
### Technical — [Trading Levels / MTF]
### Macro — [regime + sector tilt]
### Portfolio — [allocation, stops, rotation vs holdings]

## Pipeline vs narrative
| Lens | View | Notes |
|------|------|-------|

## Repo follow-ups
- [ ] Live run needed? | [ ] ANALYSE | [ ] Council for code change?

## Disclaimer
```

## Parallel delegation (Cursor Task)

```
Team: india-markets-fundamental
Repo: /Users/akulakavyashree/TestNetstock/Stock_Analysis
Artifacts: [paths]
Task: Memo per .cursor/skills/india-markets-fundamental/SKILL.md
```

## Examples

**"Full view on TCS"** → Read/load pipeline → Fundamental + Technical + Macro + Portfolio → synthesis with v2 score and action.

**"Why NEW POSITION on X?"** → Portfolio + Fundamental + check `src/turbo_entry.py` / flow oracle tags in report.

**"Weekly plan ₹5L aggressive"** → `turbo-mtf-weekly-trader` + Portfolio + Macro desks; cite Portfolio Allocation sheet.

## Conflict handling

If desk narrative contradicts pipeline action (e.g. strong fundamentals but SELL from exhaustion):

- Quote pipeline reason from report/history
- Name the module (`early_breakout_detector`, hard-stop, rotation friction)
- Recommend horizon-specific lead desk (Turbo MTF → technical/portfolio)
