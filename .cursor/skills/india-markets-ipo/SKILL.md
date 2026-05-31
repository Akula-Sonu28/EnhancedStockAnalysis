---
name: india-markets-ipo
description: >-
  Indian IPO primary-market research desk — NOT implemented in Stock_Analysis
  pipeline (universe is Nifty 500 CSV, no DRHP parser). Use for IPO apply/avoid
  analysis, DRHP review when user provides document, or post-listing name once in
  stock_list_template500.csv. For listed Nifty 500 names use india-markets-fundamental.
---

# IPO Desk — Research Only

**Stock_Analysis does not parse DRHP/RHP or track IPO calendar.** Listed names enter via `stock_list_template500.csv` after inclusion.

## When to use

- Pre-IPO: user provides DRHP/RHP link or PDF summary
- Post-listing: symbol in universe → switch to pipeline + fundamental desk

## Workflow

1. If symbol **in universe CSV** → run `python main.py -s SYMBOL` and use fundamental desk for listed analysis.
2. If **pre-IPO** → manual DRHP review (peers, risks, valuation band).
3. Never use pipeline score for unlisted IPO.

## Report template

```markdown
# IPO Research Memo

**Status:** Pre-IPO / Recently listed | **In Nifty 500 universe:** Y/N

## Issue structure
[From user-provided DRHP]

## Valuation vs peers
| Peer (listed) | PE | Source |

## Risks (from offer doc)

## Recommendation
Apply / Avoid / Neutral

**GMP is unofficial — do not rely on it.**

If listed and in universe: see pipeline report at [path].
```

## Repo link

- After listing + universe add → `india-markets-fundamental` + orchestrator
