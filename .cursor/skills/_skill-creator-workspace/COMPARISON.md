# Skill comparison — v0 (manual) vs v1 (skill-creator enhanced)

Review date: 2026-06-03  
Method: Anthropic `skill-creator` installed via `npx skills add anthropics/skills --skill skill-creator`  
Snapshots: `_skill-creator-workspace/v0-original/`

## Verdict (short)

| Dimension | v0 (manual build) | v1 (skill-creator pass) | Winner |
|-----------|-------------------|-------------------------|--------|
| **Domain depth (Stock_Analysis)** | Deep — repo paths, council agents, NSE desks | Same depth retained | **Tie** |
| **Triggering / discovery** | Easy to miss skills (undertrigger) | Pushy descriptions + `product-teams-orchestrator` | **v1** |
| **Token efficiency** | Duplicated escalation blocks × 6 skills | Shared `council-escalation-template.md` | **v1** |
| **Progressive disclosure** | Partial (some refs) | Templates moved to `references/` | **v1** |
| **Testability** | evals only on india-markets | evals on council, software-product, master orchestrator | **v1** |
| **"Call everyone" UX** | User must know 3 orchestrators | Single `product-teams-orchestrator` | **v1** |
| **Council workflow detail** | Very complete (236 lines) | Unchanged body; better description | **v0 slight edge** on debate steps |
| **Ship readiness** | No packaged `.skill` file | Same (can `package_skill` later) | **Tie** |

**Overall: v1 is better for day-to-day use** (routing, triggering, maintenance). **v0 content remains the source of truth** for council debate mechanics — v1 did not remove those steps.

---

## What v0 did well (keep)

1. **Three-layer architecture** — Research / Governance / Engineering was correct and repo-specific.
2. **Council personas** — ARCH/QUANT/RISK/AUDIT/SKEPTIC with India Markets alignment blocks are high-value; skill-creator did not replace these.
3. **`product-teams-bridge.md`** — Concrete agent↔desk↔engineering map; rare in generic skills.
4. **Per-desk escalation tables** — "When to escalate" rows per desk are useful; v1 keeps them, only dedupes the markdown template.

## What skill-creator fixed

1. **Master router** — New `product-teams-orchestrator` answers "call everyone" and ambiguous multi-intent prompts.
2. **Descriptions** — Added trigger phrases skill-creator recommends ("even if they don't say BUILD", "small threshold tweaks") to combat undertrigger.
3. **evals.json** — Added for `five-agent-council`, `software-product-orchestrator`, `product-teams-orchestrator` (skill-creator loop enabler).
4. **DRY templates** — `council-escalation-template.md`, `product-brief-template.md` moved out of SKILL.md bodies.
5. **Leaner orchestrator SKILL** — software-product-orchestrator 97 → ~85 lines.

## What skill-creator would still recommend (not done yet)

| Item | Effort | Value |
|------|--------|-------|
| Full eval loop with subagents + `generate_review.py` | High | Proves trigger accuracy |
| Description optimization (`run_loop.py`) | Medium | Measurable trigger rate |
| Dedupe all 5 india-markets desk Council sections → link only | Low | Token savings |
| Fix stale paths (`TestNetstock/Stock_Analysis` → workspace root) | Low | Correctness |
| Remove eval #5 derivatives desk (deleted skill) in india-markets evals | Low | Accuracy |
| `package_skill` export for sharing | Low | Portability |

---

## Side-by-side: description (triggering)

### software-product-orchestrator

**v0:** "Use for new features, dashboard UX, scripts, tests, CI, or when the user says BUILD, SHIP..."

**v1:** "...Use whenever the user says BUILD, SHIP, implement, add feature... **even if they do not say engineering**..."

**Why v1 wins:** skill-creator docs say models undertrigger; explicit casual synonyms help.

### five-agent-council

**v0:** Lists COUNCIL/DEBATE/PEER REVIEW.

**v1:** Adds "even for small threshold tweaks" + "Skip for one-line fixes or pure dashboard CSS".

**Why v1 wins:** Negative triggers reduce false council runs on CSS typos.

---

## Side-by-side: structure

**v0:** Monolithic SKILL.md with embedded templates.

**v1:**
```
product-teams-orchestrator/SKILL.md     ← entry (new)
five-agent-council/
  references/product-teams-bridge.md
  references/council-escalation-template.md
software-product-orchestrator/
  references/product-brief-template.md
  evals/evals.json
```

Matches skill-creator **progressive disclosure** (metadata → SKILL.md → references).

---

## Recommendation

**Use v1 as the active set.** Keep v0 snapshots for diff only.

**Default entry when unsure:**
```
@product-teams-orchestrator
```
or natural language: *"call everyone to review and ship BEAR hard-stop change"*

**When you want full skill-creator benchmark loop next:**
```bash
# From repo root, after defining evals
python .agents/skills/skill-creator/eval-viewer/generate_review.py \
  .cursor/skills/_skill-creator-workspace/iteration-1 \
  --skill-name product-teams-orchestrator --static /tmp/review.html
```

---

## Files changed in v1 pass

| File | Change |
|------|--------|
| `product-teams-orchestrator/SKILL.md` | **New** master router |
| `product-teams-orchestrator/evals/evals.json` | **New** |
| `five-agent-council/evals/evals.json` | **New** |
| `software-product-orchestrator/evals/evals.json` | **New** |
| `five-agent-council/references/council-escalation-template.md` | **New** shared template |
| `software-product-orchestrator/references/product-brief-template.md` | **New** |
| `software-product-orchestrator/SKILL.md` | Pushy description + lean body |
| `five-agent-council/SKILL.md` | Pushy description + skip rules |
| `.agents/skills/skill-creator/` | Installed via npx |
