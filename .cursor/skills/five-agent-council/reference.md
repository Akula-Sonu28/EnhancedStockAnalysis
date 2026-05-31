# Five-Agent Council — Reference

## Round 1 Position Template

Each agent receives this instruction block (plus Problem Brief + persona):

```markdown
You are [AGENT_ID] on the Stock_Analysis Five-Agent Council.

Read first:
1. Your persona: .cursor/skills/five-agent-council/agents/[persona-file]
2. .cursor/skills/stock-analysis-system/SKILL.md

Return ONLY a Position Paper in this format:

# Position Paper — [AGENT_ID]

## Recommendation
[Your proposed approach — specific files, functions, config keys]

## Evidence
- [Repo facts: file paths, existing patterns, test suites that apply]

## Risks
- [What could go wrong in this codebase specifically]

## Non-negotiables
- [Hard requirements from your domain]

## Open questions
- [What you need from other agents in Round 2]
```

---

## Round 2 Debate Template

```markdown
You are [AGENT_ID] on the Stock_Analysis Five-Agent Council.

Read your persona and stock-analysis-system/SKILL.md.

Below are all five Round-1 Position Papers. Debate them.

Rules:
1. Name at least TWO other agents and challenge or support their claims
2. Cite repo evidence (files, tests, config keys) — no generic best practices
3. Revise your position if another agent convinced you
4. Propose at least one MERGE: "Take ARCH's module split + QUANT's weight formula"

Return ONLY:

# Debate Response — [AGENT_ID]

## Revised recommendation
[Updated approach after seeing others]

## Challenges
### vs [OTHER_AGENT]
- Claim: ...
- Counter: ... (with file/test evidence)

## Supports
### vs [OTHER_AGENT]
- Align on: ...

## Proposed merges
- [Concrete hybrid of two or more positions]

## Remaining objections
- [Blockers that must be resolved before ACK]
```

---

## Round 4 Acknowledgment Template

```markdown
You are [AGENT_ID] on the Stock_Analysis Five-Agent Council.

The orchestrator has synthesized a Council Recommendation (below).
You also have your Round-2 debate position for context.

Your job is PEER ACKNOWLEDGMENT — not re-debate from scratch.

Evaluate whether the recommendation:
1. Satisfies your domain non-negotiables
2. Adequately addresses objections you raised in Round 2
3. Is safe to deploy into this repo

Return ONLY:

# Peer Acknowledgment — [AGENT_ID]

## Verdict
ACK | ACK_WITH_CONDITIONS | BLOCK

## Conditions (if ACK_WITH_CONDITIONS)
- [ ] ...

## Blocking reason (if BLOCK)
...

## Residual concerns (non-blocking)
- ...

## Peer credit
- [Name another agent whose contribution improved the final solution]
```

---

## Council Scorecard Template

Orchestrator fills after Round 4:

| Agent | Verdict | Key note |
|-------|---------|----------|
| ARCH | | |
| QUANT | | |
| RISK | | |
| AUDIT | | |
| SKEPTIC | | |

**Gate:** [PASS / CONDITIONAL / BLOCKED]

---

## Subagent Spawn Prompt (orchestrator copy-paste)

```
Council member task — Stock_Analysis Five-Agent Council

Agent: [AGENT_ID]
Persona: .cursor/skills/five-agent-council/agents/[file].md
Domain skill: .cursor/skills/stock-analysis-system/SKILL.md
Round: [1 | 2 | 4]

[Problem Brief OR Position Papers OR Council Recommendation]

[Round template from this reference file]

Return structured markdown only. Readonly — do not edit files.
```

---

## Deadlock Resolution

When agents deadlock after max debate rounds:

1. List each unresolved objection with owning agent
2. Present **Option A** (majority merge) vs **Option B** (minority safe path)
3. Ask user to pick — council does not implement on deadlock without user decision
4. Document dissent in `docs/dev-log.md` if user overrides a BLOCK from AUDIT/RISK

---

## Breaking-Change Detector

Flag `Breaking-change flag: YES` when recommendation touches:

- `config.json` thresholds (`STRONG_BUY`, `BUY`, `HOLD`, `SELL`, hard-stop tiers)
- Scoring weights in `config.py` or hybrid engines
- Exit logic (`_evaluate_hard_stop`, rotation, exhaustion)
- Action enum or history schema columns
- Excel sheet names or report structure
- v2 promotion state or `V2_SHADOW_MODE`

These require explicit user confirmation per `core-interaction.mdc`.
