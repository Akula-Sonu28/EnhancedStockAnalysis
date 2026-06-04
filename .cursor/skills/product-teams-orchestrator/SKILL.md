---
name: product-teams-orchestrator
description: >-
  Master router for Stock_Analysis — coordinates India Markets research desks,
  Five-Agent Council governance, and software product engineering (BUILD/SHIP).
  Use whenever the user wants the full team, multi-desk stock view, council
  debate, product feature work, dashboard changes, scoring changes, weekly plan,
  or says COUNCIL, BUILD, SHIP, ANALYSE, or "call everyone". Prefer this over
  guessing which sub-orchestrator to load when intent spans research + code.
---

# Product Teams Orchestrator

Single entry point for the **three layers** of Stock_Analysis skills.

When the user says `call everyone` without a goal, ask what they want done (one short question).

## Route in 10 seconds

| User intent | Command / skill |
|-------------|-----------------|
| Stock thesis, weekly plan, "why SELL?" | `india-markets-orchestrator` |
| Debate before scoring/exit/architecture change | `COUNCIL <topic>` → `five-agent-council` |
| Ship code, dashboard, script, CI | `BUILD <feature>` → `software-product-orchestrator` |
| Debate then ship | `BUILD + COUNCIL <topic>` |
| Audit latest analyzer run | `ANALYSE` → `post-analysis-audit` |

Full handoff map: [../five-agent-council/references/product-teams-bridge.md](../five-agent-council/references/product-teams-bridge.md)

## Classify first

```
Request
  → Research only?     → india-markets-orchestrator (+ desks)
  → Code/contracts?    → COUNCIL if breaking; else BUILD
  → Both?              → india-markets evidence → Council Escalation → COUNCIL → BUILD
  → Audit?             → ANALYSE
```

Breaking = scoring weights, thresholds, hard-stop, action enum, history/Excel schema.
Non-breaking = dashboard CSS, new read-only script, CI, docs.

## "Call everyone" pattern

When the user wants all layers engaged:

1. **Research** — relevant india-markets desks for NSE context (see bridge table)
2. **Governance** — `COUNCIL` with extended Problem Brief ([bridge](../five-agent-council/references/product-teams-bridge.md))
3. **Engineering** — after gate, `BUILD` via software-product PM → Backend/Frontend/Platform
4. **Verify** — regression test plan; optional dry-run + `ANALYSE`

Copy this checklist:

```
- [ ] Classify: research / council / build / all
- [ ] Load product-teams-bridge.md
- [ ] India desk memos (if investor-facing)
- [ ] COUNCIL rounds (if breaking)
- [ ] Product Brief + implement (if shipping)
- [ ] pytest + dev-log
```

## Escalation template

Desks and PM use the shared block — do not duplicate per skill:

[../five-agent-council/references/council-escalation-template.md](../five-agent-council/references/council-escalation-template.md)

## Sub-orchestrators

| Skill | Path |
|-------|------|
| Research | `.cursor/skills/india-markets-orchestrator/SKILL.md` |
| Council | `.cursor/skills/five-agent-council/SKILL.md` |
| Engineering | `.cursor/skills/software-product-orchestrator/SKILL.md` |
| Contracts | `.cursor/skills/stock-analysis-system/SKILL.md` |
