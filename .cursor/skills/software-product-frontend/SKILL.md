---
name: software-product-frontend
description: >-
  Frontend engineer for Stock_Analysis — QMST dashboard, Tape & Ledger UI,
  frontend/dashboard/, build_analysis_dashboard, canvas sync. Use for BUILD
  requests on HTML/CSS/JS, dashboard panels, and investor-facing presentation
  (presentation-only — data contracts stay in backend).
---

# Frontend — Stock_Analysis

## Repo ownership

| Path | Notes |
|------|-------|
| `frontend/qmst-dashboard.html` | Served at `http://127.0.0.1:9876/` |
| `frontend/dashboard/` | template.html, app.js, tape-dashboard.css |
| `frontend/design-playbook.html` | **Tape & Ledger** `--tape-*` tokens |
| `src/analysis_dashboard.py`, `dashboard_*.py` | Payload → HTML |
| `scripts/build_analysis_dashboard.py` | Build from Excel |
| `scripts/serve_dashboard.py` | Dev server |

## Design system

Load `.agents/skills/ui-designer/SKILL.md` for visual craft. For QMST surfaces,
**reuse Tape & Ledger tokens** from `design-playbook.html` — do not invent a
parallel palette unless user explicitly requests rebrand.

## Non-negotiables

1. **Do not** bookmark `file://` — use `serve_dashboard.py` on port 9876
2. Presentation-only changes skip council unless Excel/history **data contract** changes
3. Payload fields come from backend — coordinate with `analysis_dashboard.py` if adding columns
4. `buildVersion` bump triggers browser reload via serve script

## Workflow

1. Read Product Brief — confirm presentation-only vs new data fields.
2. If new data fields → coordinate Backend first (may need council if action/score semantics change).
3. Implement UI; match existing dashboard patterns.
4. Smoke test:
   ```bash
   python3 scripts/serve_dashboard.py --rebuild --portfolio-amount 100000 --open
   ```
5. Run `tests/test_analysis_dashboard.py` if payload builders touched.

## Hand off

- New payload fields / Excel coupling → `software-product-backend`
- CI for dashboard build → `software-product-platform`
- Investor narrative on new UI → `india-markets-portfolio` (optional, post-ship)

## Five-Agent Council

Escalate when UI exposes **new** action semantics or edits history/report contracts.
Pure layout/CSS/filter-on-existing-fields → BUILD without council.

Bridge: `.cursor/skills/five-agent-council/references/product-teams-bridge.md`
