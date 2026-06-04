# Software Product Team Roster — Stock_Analysis

Engineering roles live in `.cursor/skills/software-product-*`. They **ship code**;
india-markets desks **interpret output**; council **governs breaking changes**.

## Teams

| Role | Skill folder | Owns |
|------|--------------|------|
| Orchestrator | `software-product-orchestrator` | Routes BUILD, merges PR-sized work |
| Product | `software-product-pm` | Brief, acceptance criteria, scope, breaking-change flag |
| Backend | `software-product-backend` | Python pipeline, `src/`, `backtest/`, scoring modules |
| Frontend | `software-product-frontend` | `frontend/`, dashboard, canvas, HTML contracts |
| Platform | `software-product-platform` | CI, `scripts/`, test infra, `serve_dashboard.py` |

## Routing

| User intent | Primary role(s) | Gate |
|-------------|-----------------|------|
| New dashboard panel | PM → Frontend → Platform | NO council if presentation-only |
| New analyzer script | PM → Backend → Platform | Council if touches scoring/history |
| Backtest strategy module | PM → Backend | Council if live weights/thresholds |
| GitHub Action / CI | Platform | NO council unless deploy affects live config |
| Refactor orchestrator | PM → Backend → ARCH (council) | **COUNCIL required** |
| Fix regression test | Backend or Platform | NO council |
| QMST dashboard UX | Frontend + `ui-designer` | Tape & Ledger tokens from design-playbook |

## Council ↔ engineering map

| Council agent | Software team counterpart |
|---------------|----------------------------|
| ARCH | Backend (module boundaries) + Platform (repo layout) |
| QUANT | Backend (scoring engines) |
| RISK | Backend (stops, universe) + PM (investor-facing flag) |
| AUDIT | Platform (pytest, CI) + Backend (contract tests) |
| SKEPTIC | All roles — failure scenarios in BUILD review |

## Full product org

| Layer | Orchestrator |
|-------|--------------|
| Research | `india-markets-orchestrator` |
| Governance | `five-agent-council` |
| Engineering | `software-product-orchestrator` |

See `product-teams-bridge.md` for cross-layer handoffs.
