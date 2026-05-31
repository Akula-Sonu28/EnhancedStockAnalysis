# India Markets Multi-Desk — Stock_Analysis

Specialist research layer on top of the NSE equity pipeline. Tuned for this repo's modules, Excel contracts, and existing Cursor skills.

## Quick start

```
Use india-markets-orchestrator — full view on TCS from latest run
ANALYSE                                          → post-analysis-audit (not orchestrator)
Weekly rebalance dry-run                         → turbo-mtf-weekly-trader + orchestrator
Change hard-stop logic                           → five-agent-council
```

## Desk index

| Skill | Repo-backed? | Primary artifacts |
|-------|--------------|-------------------|
| `india-markets-orchestrator` | Yes | Routes all desks |
| `india-markets-fundamental` | Yes | cache JSON, Complete Data sheet |
| `india-markets-technical` | Yes | Trading Levels, MTF, Breakout Radar |
| `india-markets-macro` | Yes | last_known_regime.json, Sector Analysis |
| `india-markets-portfolio` | Yes | Portfolio Allocation, history CSV |
| `india-markets-regulatory` | Partial | backtest/costs.py, universe_filter |
| `india-markets-derivatives` | No | Research memos only |
| `india-markets-ipo` | No | Research memos only |

## Related repo skills

- `stock-analysis-system` — code, config, v2 promotion
- `post-analysis-audit` — after `analyze_top200` / ANALYSE
- `turbo-mtf-weekly-trader` — weekly process discipline
- `five-agent-council` — code/architecture decisions

## References

Orchestrator `references/`:

- `repo-integration.md` — commands and module map
- `data-sources.md` — where to read data
- `team-roster.md` — routing table
- `market-basics.md` — NSE context for this project

Eval prompts: `india-markets-orchestrator/evals/evals.json`
