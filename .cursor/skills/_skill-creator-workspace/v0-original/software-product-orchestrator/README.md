# Software Product Team — Stock_Analysis

Engineering layer that **ships the product** (Python pipeline, dashboard, CI).

## Quick start

```
BUILD add filter panel to action plan dashboard     → software-product-orchestrator
BUILD new backtest runner flag                        → PM → Backend → Platform
COUNCIL change hard-stop tiers                        → council gate → Backend implements
SHIP dashboard                                        → Frontend + serve_dashboard smoke
```

## Role index

| Skill | Role |
|-------|------|
| `software-product-orchestrator` | Routes BUILD work |
| `software-product-pm` | Product brief, council flag |
| `software-product-backend` | Python pipeline, backtest |
| `software-product-frontend` | QMST dashboard, Tape & Ledger UI |
| `software-product-platform` | CI, scripts, pytest gates |

## Full org

| Layer | Orchestrator |
|-------|--------------|
| Research | `india-markets-orchestrator` |
| Governance | `five-agent-council` |
| Engineering | `software-product-orchestrator` |

Bridge: `.cursor/skills/five-agent-council/references/product-teams-bridge.md`

References: `software-product-orchestrator/references/repo-map.md`, `team-roster.md`
