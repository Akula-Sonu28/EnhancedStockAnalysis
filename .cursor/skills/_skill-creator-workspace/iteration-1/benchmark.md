# Eval Results — product-teams-orchestrator (iteration 1)

**Date:** 2026-06-03  
**Method:** skill-creator loop — 4 prompts × with_skill vs without_skill (8 readonly subagent runs)

## Scorecard

| Eval | With skill | Without skill | Winner |
|------|------------|---------------|--------|
| call everyone → BEAR hard-stop + ship | **6/6 (100%)** | 2/6 (33%) | **With skill** |
| BUILD dashboard filter chip | **4/4 (100%)** | 4/4 (100%) | Tie |
| full view TCS | **4/4 (100%)** | 3/4 (75%) | **With skill** |
| COUNCIL DEBATE ONLY quality_lvm | **4/4 (100%)** | 3/4 (75%) | **With skill** |
| **Overall** | **18/18 (100%)** | **12/17 (71%)** | **With skill +29pp** |

*Eval 2 baseline tied because the agent read `AGENTS.md` and discovered `software-product-orchestrator` without the master router skill.*

## Verdict

**Yes — the skill is genuinely enhanced and measurably better** for:

1. **Multi-layer requests** (“call everyone”) — without skill → generic eng roles; with skill → Research → COUNCIL → BUILD → ANALYSE chain
2. **Master router entry** — with skill always classifies via `product-teams-orchestrator` first; without skill jumps to sub-orchestrator
3. **DEBATE ONLY boundaries** — with skill enforces stop at Round 3 + no BUILD; baseline similar but misses classify step

**Not differentiated on:** simple BUILD UI-only tasks when the agent already reads repo docs (`AGENTS.md`).

## What this proves vs what it doesn't

| Proven | Not proven (yet) |
|--------|------------------|
| Routing quality on 4 representative prompts | Trigger rate in live Cursor sessions |
| With skill wins on ambiguous multi-intent | Full council Round 1-4 execution |
| skill-creator eval methodology works for this skill | Description optimization (`run_loop.py`) |

## Artifacts

- Eval definitions: `.cursor/skills/product-teams-orchestrator/evals/evals.json`
- Benchmark: `.cursor/skills/_skill-creator-workspace/iteration-1/benchmark.json`
- v0 snapshot: `.cursor/skills/_skill-creator-workspace/v0-original/`
- Comparison doc: `.cursor/skills/_skill-creator-workspace/COMPARISON.md`

## Recommended next iteration

1. Add eval for `BUILD + COUNCIL` combined phrase
2. Run `run_loop.py` on description for trigger optimization
3. Dedupe remaining india-markets desk Council blocks → shared template
