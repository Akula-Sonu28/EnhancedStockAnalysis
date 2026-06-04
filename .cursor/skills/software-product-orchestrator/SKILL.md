---
name: software-product-orchestrator
description: >-
  Coordinates the software product engineering team that ships Stock_Analysis —
  PM scope, Python backend, QMST dashboard frontend, platform/CI. Use whenever
  the user says BUILD, SHIP, implement, add feature, fix script, write tests,
  GitHub Action, serve_dashboard, backend refactor, or dashboard panel — even if
  they do not say "engineering". Routes to five-agent-council first when scoring,
  thresholds, hard-stops, or report contracts change. Pair with india-markets for
  post-ship narrative.
---

# Software Product Orchestrator — Stock_Analysis

You lead the **engineering layer** that ships the NSE equity product: analyzer
pipeline, dashboard, backtest, scripts, and tests. This is distinct from
**india-markets-*** (research narrative) and **five-agent-council** (governance
before breaking system changes).

## Repo context (read first)

1. [references/team-roster.md](references/team-roster.md) — roles and routing
2. [references/repo-map.md](references/repo-map.md) — code ownership by layer
3. `.cursor/skills/stock-analysis-system/SKILL.md` — contracts when touching scoring/reports

## Three-layer model

| Layer | Skill | Delivers |
|-------|-------|----------|
| Research | `india-markets-orchestrator` | Investment memos on pipeline output |
| Governance | `five-agent-council` | Council Recommendation before breaking changes |
| **Engineering** | **this orchestrator** | Working code, tests, shipped UI |

## Skill routing

| User trigger | Route to |
|--------------|----------|
| `BUILD`, `SHIP`, new feature, dashboard, script | This orchestrator → PM + Backend/Frontend/Platform |
| Scoring, thresholds, hard-stop, v2 weights | `five-agent-council` first — then Backend implements |
| `ANALYSE` after run | `post-analysis-audit` |
| "Why SELL on X?" / stock narrative | `india-markets-orchestrator` |
| UI polish only, no data contract change | Frontend + `ui-designer` (`.agents/skills/ui-designer`) |

## BUILD workflow

```
User request
  → Classify: product feature vs scoring change vs research-only
  → If scoring/contracts/exits → COUNCIL first (do not BUILD until gate)
  → PM: problem brief, acceptance criteria, breaking-change flag
  → Parallel: Backend / Frontend / Platform as needed
  → Implement + test plan (regression when touching analyzer)
  → docs/dev-log.md if non-trivial
```

## Product brief

PM fills template in [references/product-brief-template.md](references/product-brief-template.md).

## Parallel delegation (Cursor Task)

```
Team: software-product-backend
Repo: [workspace root]
Brief: [Product Brief]
Task: Implement per .cursor/skills/software-product-backend/SKILL.md
Constraints: stock-analysis-system contracts; v1 untouched when editing v2
```

## Handoffs

| After | Next |
|-------|------|
| Council gate PASS + user confirm | Backend/Frontend implement per Council Recommendation |
| Dashboard-only ship | `serve_dashboard.py --rebuild --open` smoke test |
| Investor-facing scoring change | dry-run → `ANALYSE` → india-markets re-narrative |
| Council Escalation from india-markets desk | `COUNCIL <goal>` before BUILD |

Bridge (all teams): `.cursor/skills/five-agent-council/references/product-teams-bridge.md`

## Quick commands

| User says | Action |
|-----------|--------|
| `BUILD <feature>` | PM brief → delegate engineering roles |
| `SHIP dashboard` | Frontend + Platform; Tape & Ledger tokens |
| `BUILD + COUNCIL` | Council debate first, then BUILD implements |
