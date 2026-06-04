---
name: india-markets-portfolio
description: >-
  Portfolio construction and risk desk for Stock_Analysis. Interprets Portfolio
  Allocation sheet, recommendation_history actions, hard-stop and rotation logic,
  sector caps, Zerodha holdings merge, and Turbo MTF weekly cadence. Use for
  allocation plans, explaining HOLD/SELL/NEW POSITION/INCREASE, position sizing
  from pipeline output, or weekly rebalance narrative with run_analysis.py.
---

# Portfolio Desk — Stock_Analysis

## Repo modules

| Module | Role |
|--------|------|
| `analyze_top200_stocks_enhanced.py` | Allocation builder, sector caps, cap-tier limits |
| `recommendation_history.py` | Action canonicalisation, cooldown, flip-flop guard |
| Hard-stop / rotation | `_evaluate_hard_stop`, `_should_rotate` in analyzer |
| `src/zerodha_holdings.py` | Kite holdings → merge with recommendations |
| `backtest/costs.py` | Zerodha delivery costs in backtests |

## Read data

1. Excel **Portfolio Allocation**, **Portfolio Summary**, **Risk Analysis**, **Risk Management**
2. `Portfolio_Allocation_Dashboard.html`
3. `data/recommendation_history.csv` — latest action per symbol
4. Holdings: `Holding/holdings*.csv` or Kite API (`KITE_USE_HOLDINGS`)

## Action contract (baseline seven)

`HOLD`, `SELL`, `INCREASE`, `NEW POSITION`, `WATCHLIST`, `EXIT NOW - Heavy exhaustion`, `HIGH MOMENTUM NEW POSITION`

Extended via `_normalize_action`: `STRONG BUY`, `BUY`, `REDUCE`, `SCALE_OUT_20`, `SWAP`, etc.

Verify live thresholds in `config.json` / `docs/config-contract.md` (STRONG BUY ≥70, BUY ≥60, …).

## Weekly process (integrate turbo-mtf-weekly-trader)

```bash
# Preview — no history mutation
python3 scripts/run_analysis.py --dry-run --fast

# Live weekly commit
python3 scripts/run_analysis.py

# Then user says ANALYSE → post-analysis-audit
```

Read `data/turbo_mtf_cadence_comparison.json` before changing weekly vs biweekly execution.

## Strategy lanes affecting picks

- `src/flow_quality_oracle.py` — anti-chase rank
- `src/vmq_strategy.py` — momentum-quality gates
- `src/path2_balanced.py` — soft rank-sells
- `src/breakout_radar.py` — fast-track NEW names

## Report template

```markdown
# Portfolio Memo — Stock_Analysis

**Capital:** | **Risk profile:** | **Holdings source:**

## Pipeline allocation (from latest report)
| Symbol | Action | Weight | Score | Sector |

## Risk controls active
- Hard stop / trailing / scale-out: [from report or config]
- Rotation friction: [ROTATION_FRICTION_POINTS from config-contract]
- Universe: tradeable per universe_filter

## Weekly actions
- NEW / INCREASE / SELL / HOLD with pipeline reasons

## vs holdings
[Overlap, trim candidates, deploy cash]

## Next step
[ ] dry-run [ ] live run [ ] ANALYSE
```

## Hand off

- Macro tilt → `india-markets-macro`
- Single-name thesis → Fundamental + Technical
- Code changes to stops/allocation → `five-agent-council`

## Five-Agent Council

**Research-only desk.** Weekly rebalance narrative stays here; stop/allocation **code** → council.

| Escalate when | Council agents most involved |
|---------------|------------------------------|
| hard-stop tiers, rotation, cooldown rules | RISK (binding), AUDIT |
| sector caps, allocation builder, action enum | RISK, AUDIT, ARCH |
| Zerodha holdings merge or Turbo MTF sizing | ARCH, RISK |

```markdown
## Council Escalation (from Portfolio desk)
**Goal:** [e.g. "Regime-aware hard-stop tier for BEAR"]
**India context:** live recommendations | investor-facing: YES
**Evidence:** [history rows, Risk Analysis sheet, stop trigger case]
**Proposed change:** [function/config]
**Council trigger:** COUNCIL <goal>
```

Bridge: `.cursor/skills/five-agent-council/references/product-teams-bridge.md`
