# External Skills (Minimal — Turbo MTF / NSE)

Methodology playbooks only — **do not replace** in-repo pipeline skills.

## Absolute core (tracked in repo)

| Skill | Role |
|-------|------|
| `stock-analysis-system` | v1/v2 scoring, config, history, regression contracts |
| `post-analysis-audit` | `ANALYSE` after each analyzer run |
| `turbo-mtf-weekly-trader` | Weekly rebalance / dry-run vs live |
| `five-agent-council` | `COUNCIL` / `DEBATE`; `product-teams-bridge.md` |
| `product-teams-orchestrator` | **Master router** — research + council + BUILD |
| `software-product-orchestrator` | `BUILD` / `SHIP` engineering team |

## India desks (tracked — pipeline-aligned)

| Skill | Role |
|-------|------|
| `india-markets-orchestrator` | Routes specialist desks |
| `india-markets-fundamental` | Fundamentals + v2 FQ components |
| `india-markets-technical` | MTF / breakout / trading levels |
| `india-markets-macro` | BULL/BEAR/SIDEWAYS regime framing |
| `india-markets-portfolio` | Allocation / HOLD-SELL / rotation narrative |
| `india-markets-regulatory` | Zerodha costs in backtests |

Removed: `india-markets-derivatives`, `india-markets-ipo` (research-only, not in pipeline).

## Software product team (tracked — ships code)

| Skill | Role |
|-------|------|
| `software-product-orchestrator` | Routes BUILD / SHIP |
| `software-product-pm` | Product brief, council flag |
| `software-product-backend` | Python pipeline, backtest |
| `software-product-frontend` | QMST dashboard, Tape & Ledger UI |
| `software-product-platform` | CI, scripts, pytest gates |

Unified handoff: `five-agent-council/references/product-teams-bridge.md`

## Optional methodology (gitignored copies — not committed)

| Skill | Role |
|-------|------|
| `backtesting-frameworks` | Look-ahead / survivorship / cost bias |
| `python-testing-patterns` | pytest when touching analyzer or v2 |
| `xlsx-official` | Parse `Enhanced_Stock_Report_*.xlsx` |
| `debugging-strategies` | Dry-run vs live drift |
| `walk-forward-validation` | v2 promotion / HOLD_SHADOW |
| `alpha-evaluate` | IC / ICIR / quintile language |

## CLI workflow (`.agents/skills/` — gitignored)

| Skill | Role |
|-------|------|
| `debugging-and-error-recovery` | Systematic pipeline debug |
| `find-skills` | Discover skills via `npx skills` |
| `ui-designer` | UI/UX for HTML dashboards (`frontend/qmst-dashboard.html`) |

## Removed (2026-05-31 prune)

- All `investor-*` philosophy skills (17)
- Duplicate trading packs: `regime-detection`, `risk-management`, `position-sizing`, `portfolio-analytics`, `trade-journal`, `alpha-backtest`, `alpha-monitor`, `data-scientist`, `ab-test-setup`
- `intraday-top-movers` (separate intraday product; not weekly QMST)
- `.agents` bloat: pdf, docx, ci-cd, TDD duplicates, webapp-testing, etc.

## Invoke

```
@stock-analysis-system
@post-analysis-audit   → then type ANALYSE
@turbo-mtf-weekly-trader
@ui-designer            → QMST dashboard / HTML UI/UX
@backtesting-frameworks review scripts/backtest_monthly_rebalance.py
```
