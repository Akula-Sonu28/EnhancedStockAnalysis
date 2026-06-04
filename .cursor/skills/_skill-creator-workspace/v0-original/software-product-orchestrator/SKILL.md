---
name: software-product-orchestrator
description: >-
  Coordinates the software product engineering team building Stock_Analysis —
  product scope, Python backend, frontend/dashboard, platform/CI. Routes BUILD
  work, integrates with five-agent-council for governance and india-markets for
  domain context. Use for new features, dashboard UX, scripts, tests, CI, or
  when the user says BUILD, SHIP, or product engineering.
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

## Product brief template (PM owns)

```markdown
# Product Brief — [feature name]

**User goal:** [one sentence]
**Persona:** [investor using dashboard | operator running analyzer | developer]
**Acceptance criteria:**
- [ ] ...
**Out of scope:**
**Breaking-change:** YES / NO
**Council required:** YES / NO
**Modules:** [paths from repo-map]
**Test plan:** [pytest targets]
```

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
