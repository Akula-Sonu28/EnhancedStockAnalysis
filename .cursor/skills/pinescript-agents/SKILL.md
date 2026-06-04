---
name: pinescript-agents
description: >-
  Master router for Pine Script v6 / TradingView work in Stock_Analysis.
  Coordinates pine-visualizer, pine-developer, pine-debugger, pine-backtester,
  pine-optimizer, pine-publisher, and pine-manager. Use for indicators,
  strategies, QLVM overlay, compile errors, backtest metrics, UX polish, or
  publishing. Triggers on Pine Script, TradingView, .pine files, QLVM indicator,
  or PINE command.
---

# Pine Script Agents — Stock_Analysis

Single entry point for the **seven-skill Pine Script desk** (from
[traderspost/pinescript-agents](https://github.com/traderspost/pinescript-agents)).

All skills live under this folder — load sub-skills by relative path when delegating.

## Route in 10 seconds

| User intent | Sub-skill | Path |
|-------------|-----------|------|
| Plan / decompose idea, YouTube strategy | `pine-visualizer` | [pine-visualizer/SKILL.md](pine-visualizer/SKILL.md) |
| Write / implement indicator or strategy | `pine-developer` | [pine-developer/SKILL.md](pine-developer/SKILL.md) |
| Fix errors, wrong values, repainting | `pine-debugger` | [pine-debugger/SKILL.md](pine-debugger/SKILL.md) |
| Win rate, drawdown, performance metrics | `pine-backtester` | [pine-backtester/SKILL.md](pine-backtester/SKILL.md) |
| Speed, inputs, colors, UX polish | `pine-optimizer` | [pine-optimizer/SKILL.md](pine-optimizer/SKILL.md) |
| Publish to TradingView library | `pine-publisher` | [pine-publisher/SKILL.md](pine-publisher/SKILL.md) |
| Full system, multi-phase project | `pine-manager` | [pine-manager/SKILL.md](pine-manager/SKILL.md) |

Roster detail: [references/team-roster.md](references/team-roster.md)  
Repo paths: [references/repo-integration.md](references/repo-integration.md)

## Classify first

```
Request
  → Concept / "how would I build"?     → pine-visualizer
  → New or edit .pine code?             → pine-developer (+ debugger if errors)
  → Broken / unexpected on chart?       → pine-debugger → developer
  → Strategy metrics?                   → pine-backtester
  → Slow or ugly UI?                    → pine-optimizer
  → Release to community?               → pine-publisher
  → Multi-feature trading system?       → pine-manager (orchestrates all)
```

## Stock_Analysis defaults

- **Primary Pine file:** `scripts/qlvm_indicator.pine` (QLVM overlay, v6)
- **Python source of truth:** `src/quality_lowvol_momentum.py`, `config.py` — mirror logic in Pine; cross-sectional rank and fundamentals stay in Python analyzer
- **Do not** change scoring thresholds in Pine without `COUNCIL` if tied to live pipeline behavior

## Workflow templates

### Edit existing indicator (QLVM)

```
1. Read scripts/qlvm_indicator.pine + repo-integration.md
2. pine-developer — implement change
3. pine-debugger — verify signals, no repainting
4. pine-optimizer — inputs / tooltips if UX touched
```

### New indicator from scratch

```
1. pine-visualizer — breakdown
2. pine-developer — implement in scripts/<name>.pine
3. pine-debugger — debug tools
4. pine-optimizer — polish
5. (optional) pine-publisher
```

### Strategy with backtest

```
pine-visualizer → pine-developer → pine-backtester → pine-debugger → pine-optimizer
```

## Commands

| Command | Action |
|---------|--------|
| `PINE <task>` | Route via table above |
| `PINE DEBUG <file>` | Load pine-debugger on file |
| `PINE BUILD <idea>` | pine-manager full workflow |

## Upstream package

Install or refresh all seven skills:

```bash
npx skills add https://github.com/traderspost/pinescript-agents
```

Then copy updated `SKILL.md` files into `.cursor/skills/pinescript-agents/<skill>/`.
