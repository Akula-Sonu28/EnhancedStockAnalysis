# Repo Map — Software Product Ownership

Workspace root: Stock_Analysis NSE equity product.

## Backend (Python product core)

| Path | Owner concerns |
|------|----------------|
| `analyze_top200_stocks_enhanced.py` | Orchestrator phases, allocation, report emit |
| `hybrid_optimized_scoring.py` | v1 baseline — read-only for v2 work |
| `hybrid_scoring_v2.py` | v2 live engine |
| `config.py`, `config.json` | `get_config()` singleton — never local instantiate |
| `src/` | Analyzers, turbo, VMQ, universe, dashboard payload builders |
| `backtest/` | Engine, strategies, costs, pytest under `backtest/tests/` |
| `recommendation_history.py` | History schema, cooldown, actions |
| `market_regime_detector.py`, `adaptive_market_strategy.py` | Regime layer |

## Frontend (investor-facing product UI)

| Path | Owner concerns |
|------|----------------|
| `frontend/qmst-dashboard.html` | Live dashboard served on `:9876` |
| `frontend/dashboard/template.html`, `app.js`, `tape-dashboard.css` | Tape dashboard shell |
| `frontend/design-playbook.html` | `--tape-*` design tokens (source of truth) |
| `src/analysis_dashboard.py`, `src/dashboard_*.py` | Payload + action document builders |
| `scripts/build_analysis_dashboard.py` | Build from Excel report |
| `scripts/serve_dashboard.py` | Local dev server + auto-reload |

## Platform (ship & verify)

| Path | Owner concerns |
|------|----------------|
| `tests/test_v2_regression.py` | 222-suite gate |
| `tests/test_regression_fixes.py` | Broader regression |
| `.github/workflows/` | CI |
| `scripts/` | Operational scripts (audit, run_analysis, fetch, etc.) |
| `docs/dev-log.md` | Change log for non-trivial ships |

## Contracts (any role touching these → council or AUDIT review)

- Action enum + Excel sheet names + `recommendation_history.csv` columns
- Scoring weights / thresholds / hard-stop / exit logic
- v2 promotion state (`V2_SHADOW_MODE`, calibrated weight files)

## Local dev smoke

```bash
python3 scripts/serve_dashboard.py --rebuild --portfolio-amount 100000 --open
python3 tests/test_v2_regression.py
python3 -m pytest backtest/tests/ -v
```
