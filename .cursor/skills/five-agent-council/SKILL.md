---
name: five-agent-council
description: >-
  Five-expert multi-agent council (ARCH, QUANT, RISK, AUDIT, SKEPTIC) for
  Stock_Analysis — multi-round debate and peer ACK before system changes.
  Use whenever the user says COUNCIL, DEBATE, PEER REVIEW, multi-agent,
  expert review, or asks to change scoring weights, v2 promotion, hard-stops,
  exit logic, Excel/history contracts, or analyzer architecture — even for
  "small" threshold tweaks. Software-product team implements after gate.
  Skip for one-line fixes or pure dashboard CSS with no contract change.
---

# Five-Agent Council — Stock_Analysis

A structured **orchestrator-led** council where five domain experts independently
analyze a problem, debate across multiple rounds, synthesize the best solution,
and **peer-acknowledge** before anything ships to the codebase.

This skill runs from the **main session only**. Council members are Task subagents
with isolated context — they do not spawn other agents.

## When to Use

| Trigger | Example |
|---------|---------|
| User says `COUNCIL`, `DEBATE`, `PEER REVIEW`, `multi-agent` | "Run the council on adding a v3 toggle" |
| Architectural or cross-module change | New scoring module, refactor analyze_top200 |
| System-wide behavior change | Thresholds, weights, exit logic, report format |
| High-stakes decision under uncertainty | v2 promotion, hard-stop tier change |
| User wants best solution, not fastest | "What is the right way to add regime-aware sizing?" |

**Skip** for: one-line fixes, formatting, reading/summarizing code, or when the
user explicitly wants speed over deliberation.

## The Five Experts

| ID | Role | Focus | Persona file |
|----|------|-------|--------------|
| **ARCH** | Pipeline Architect | Module boundaries, v1/v2 isolation, orchestrator flow | [agents/architect.md](agents/architect.md) |
| **QUANT** | Quant Strategist | Scoring math, IC calibration, regime weights, factor design | [agents/quant-strategist.md](agents/quant-strategist.md) |
| **RISK** | Risk Guardian | Hard-stops, universe filter, allocation, investor safety | [agents/risk-guardian.md](agents/risk-guardian.md) |
| **AUDIT** | Contract Auditor | Regression suites, Excel/history schemas, test coverage | [agents/contract-auditor.md](agents/contract-auditor.md) |
| **SKEPTIC** | Devil's Advocate | Adversarial challenge, blind spots, failure modes | [agents/devils-advocate.md](agents/devils-advocate.md) |

Before Round 1, read:

1. `.cursor/skills/stock-analysis-system/SKILL.md` (mandatory)
2. [references/product-teams-bridge.md](references/product-teams-bridge.md) (mandatory)
3. Topic-matched **India Markets desk** and/or **software-product** skill(s) from the bridge tables

Each subagent reads its persona + stock-analysis-system + bridge doc + any desk
or engineering skills the orchestrator assigns (see bridge tables).

## Council Workflow

Copy and track this checklist:

```
Council session:
- [ ] Intake — problem brief written (≤10 lines)
- [ ] Round 1 — five independent positions (parallel spawn)
- [ ] Round 2 — cross-examination debate (parallel spawn)
- [ ] Round 3 — synthesis draft (orchestrator)
- [ ] Round 4 — peer acknowledgment (parallel spawn)
- [ ] Gate — deployment decision (consensus / trade-offs / blocked)
- [ ] Implement — only if gate passed and user confirmed
```

### Intake (orchestrator)

Write a **Problem Brief** before spawning anyone:

```markdown
## Problem Brief
**Goal:** [one sentence]
**Constraints:** [contracts, v1 untouched, config rules, etc.]
**Blast radius:** [files/modules affected]
**Non-goals:** [what we are NOT doing]
**Success criteria:** [how we know it worked]
```

If the brief is vague, ask the user 1–2 clarifying questions first.

### Round 1 — Independent Positions

Spawn **five Task subagents in parallel** (`subagent_type: generalPurpose`, `readonly: true`).

Each prompt must include:
1. The Problem Brief (include **India context** fields when investor-facing — see bridge)
2. The agent's persona file path (read it first)
3. `.cursor/skills/stock-analysis-system/SKILL.md` (read first)
4. `.cursor/skills/five-agent-council/references/product-teams-bridge.md` (read first)
5. Assigned India Markets desk and/or software-product skill path(s) for this agent
6. Round-1 instructions from [reference.md](reference.md#round-1-position-template)

Each agent returns a **Position Paper** (see reference). Do not share other agents'
outputs in Round 1.

### Round 2 — Cross-Examination Debate

Orchestrator posts all five Position Papers to each agent (parallel spawn again).

Round-2 instructions from [reference.md](reference.md#round-2-debate-template).

Each agent must:
- Challenge at least **two** other agents by name
- Defend or revise their own position with repo-specific evidence
- Propose **concrete merges** where two positions overlap

**Stop early** if Round 2 produces unanimous agreement on a single approach with
no unresolved blockers — skip to Round 3.

**Extend to Round 2b** (optional) when:
- Two or more agents hold hard blocks
- SKEPTIC surfaces a contract or safety violation no one addressed
- QUANT and RISK disagree on threshold/weight changes

Max **3 debate rounds** total (Round 2 + up to 2 extensions). Escalate to user
if still deadlocked.

### Round 3 — Synthesis (orchestrator, no subagents)

Merge the debate into a **Council Recommendation**:

```markdown
# Council Recommendation

## Recommended approach
[3–8 sentences — the best combined solution]

## Rationale
- Why this beats alternatives
- What each agent contributed

## Implementation plan
1. [ordered steps with file paths]
2. ...

## Test plan
- [ ] python3 tests/test_v2_regression.py
- [ ] [other suites if applicable]

## Dissent / trade-offs
| Agent | Concern | Resolution |
|-------|---------|------------|

## Breaking-change flag
YES / NO — if YES, user must confirm before implement
```

Apply these merge rules:
- **ARCH** wins on module boundaries and v1/v2 isolation
- **AUDIT** wins on contract/schema violations (blocking)
- **RISK** wins on investor-safety blockers (blocking)
- **QUANT** wins on scoring math when AUDIT/RISK do not block
- **SKEPTIC** cannot veto alone — must convince AUDIT or RISK to block

### Round 4 — Peer Acknowledgment

Spawn five agents **in parallel** with:
1. The Council Recommendation (full text)
2. Their Round-2 position + others' key challenges
3. Acknowledgment template from [reference.md](reference.md#round-4-acknowledgment-template)

Each agent returns **ACK**, **ACK_WITH_CONDITIONS**, or **BLOCK**:

| Verdict | Meaning |
|---------|---------|
| **ACK** | Solution is sound; ready to deploy |
| **ACK_WITH_CONDITIONS** | Deploy only if listed conditions are met |
| **BLOCK** | Must not deploy; blocking reason required |

### Deployment Gate

| Outcome | Action |
|---------|--------|
| 5× ACK | Proceed to implement (if user wants implementation) |
| ≥4 ACK + rest ACK_WITH_CONDITIONS (conditions satisfiable) | Implement including conditions |
| Any BLOCK from AUDIT or RISK | **Stop.** Revise recommendation or escalate to user |
| Any BLOCK from others | One revision round (Round 3b + 4b) or user override |
| 2+ BLOCK | **Stop.** Present deadlock to user |

**Never implement** scoring/threshold/exit/report changes without:
1. Passing the deployment gate, AND
2. Explicit user confirmation when `Breaking-change flag: YES`

After gate, route implementation to **software-product-orchestrator** (Backend/
Frontend/Platform per Product Brief) unless user asks orchestrator-only debate.

After implementation, run the test plan and append a dated entry to `docs/dev-log.md`.

## Orchestration Rules

1. **Parallel spawn** Round 1, Round 2, and Round 4 agents in a single turn when possible.
2. **Personas do not invoke personas** — only the orchestrator spawns council members.
3. **Pass artifacts, not reasoning** — debate rounds get Position Papers and the Brief,
   not the orchestrator's synthesis journey.
4. **Repo paths are real** — agents must cite actual files (`hybrid_scoring_v2.py`,
   `config.json`, `tests/test_v2_regression.py`), not generic advice.
5. **SKEPTIC is adversarial by default** — their job is to break consensus, not rubber-stamp.

## User-Facing Output

After the gate, present:

1. **Executive summary** — recommended approach in plain language
2. **Council scorecard** — table of five ACK/BLOCK verdicts
3. **Council Recommendation** — full synthesis
4. **Next step** — "Implement now?", "Revise?", or "Blocked because …"

## Quick Commands

| User says | Orchestrator does |
|-----------|-------------------|
| `COUNCIL <topic>` | Full workflow through deployment gate |
| `COUNCIL DEBATE ONLY <topic>` | Rounds 1–3, no implement |
| `COUNCIL RESUME` | Continue from last Council Recommendation in chat |
| `COUNCIL ACK` | Re-run Round 4 only on current recommendation |
| `BUILD <feature>` | Hand off to `software-product-orchestrator` (skip council if PM says non-breaking) |
| `BUILD + COUNCIL <topic>` | Full council gate, then software-product team implements |

## Related Skills

- **stock-analysis-system** — domain contracts (mandatory read)
- **software-product-orchestrator** + roles (`pm`, `backend`, `frontend`, `platform`) — ships code after council gate or for non-breaking BUILD
- **india-markets-orchestrator** + desk skills — NSE research narrative; escalates to council
- [references/product-teams-bridge.md](references/product-teams-bridge.md) — unified research · governance · engineering map
- **doubt-driven-development** — single-artifact adversarial review; SKEPTIC overlaps but council is multi-domain
- **code-review-and-quality** — post-implementation PR review, not pre-design debate

## Additional Resources

- Debate templates and output schemas: [reference.md](reference.md)
- Worked example: [examples.md](examples.md)
