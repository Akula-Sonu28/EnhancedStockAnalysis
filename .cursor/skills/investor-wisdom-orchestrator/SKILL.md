---
name: investor-wisdom-orchestrator
description: >-
  Coordinates famous-investor philosophy skills — how Buffett, Lynch, Graham,
  Dalio, Marks, Jhunjhunwala, and others choose stocks, what trends they follow,
  and how they make money. Compare multiple investor lenses on the same company,
  sector, or market regime. Use when the user asks what would X investor do,
  famous investor stock selection, investing styles, value vs growth vs macro,
  or how legendary investors pick stocks — independent of pipeline v1/v2 scoring.
---

# Investor Wisdom Orchestrator

Teach and apply **how famous investors think** — not what your quant pipeline scores. Each investor is a separate skill under `.cursor/skills/investor-*`.

## Read first

- [references/investor-roster.md](references/investor-roster.md) — who covers what
- [references/how-they-make-money.md](references/how-they-make-money.md) — edges, sizing, trends

## Disclaimer (always include)

> These frameworks describe **historical investment philosophies** for education. They are not live buy/sell calls or SEBI-registered advice. Past investor success does not guarantee future results.

## Workflow

```
User question
  → Single investor named? → Load that investor skill only
  → Compare investors? → Load 2–4 relevant skills (roster table)
  → "How do legends invest?" → Summarize schools + offer to deep-dive one
  → Apply to Indian stock? → Named investor skill + India checks (promoter, liquidity)
  → Synthesize comparison memo
  → Disclaimer
```

## Comparison memo template

```markdown
# [Company / Theme] — Investor Lens Comparison

**Question:** | **Market:** NSE / global

## Quick verdict table
| Investor | Would likely | Key reason | Biggest concern |
|----------|--------------|------------|-----------------|

## Detailed memos
### Warren Buffett lens
...
### Peter Lynch lens
...

## Where they agree / disagree
**Consensus:** ...
**Divergence:** ...

## Practical takeaway (education only)
[What to research next — not a recommendation]

## Disclaimer
```

## Parallel delegation (Cursor Task)

Spawn one task per investor when comparing:

```
Load skill: .cursor/skills/investor-warren-buffett/SKILL.md
Analyze: [SYMBOL or theme] purely through this investor's framework.
Output: Use that skill's report template. No pipeline v1/v2 scores.
```

## School groupings (for overview answers)

| School | Investors | Core question |
|--------|-----------|---------------|
| Deep value | Graham, early Buffett, Greenblatt | What is it worth vs price? |
| Quality compounder | Buffett, Munger, Damani | Will this compound for 20 years? |
| GARP / growth | Lynch, Fisher, Kedia, Agrawal | Can earnings grow faster than PE? |
| Macro / reflexivity | Dalio, Soros, Druckenmiller | What is the regime and liquidity doing? |
| Cycle | Marks | Where are we in optimism/pain? |
| Disruption | Wood | Is adoption exponential? |
| India conviction | Jhunjhunwala | Is this India's next scalable winner? |

## Do not

- Cite Stock_Analysis v1/v2 scores unless user explicitly asks to compare pipeline vs philosophy
- Present any output as "Buffett would buy this" — use "Buffett framework would focus on…"
- Invent investor quotes — paraphrase documented principles

## Examples

- "How would Lynch and Buffett view Asian Paints?" → two skills + comparison template
- "How does Howard Marks think about market cycles in 2026?" → Marks skill + cycle framing
- "Indian midcap — Jhunjhunwala vs Kedia approach" → both Indian skills + compare
