---
name: india-markets-regulatory
description: >-
  Regulatory and Indian market-cost desk for Stock_Analysis. Uses backtest/costs.py
  Zerodha STT stamp GST STCG LTCG model, universe_filter surveillance exclusions,
  and general SEBI/ASM knowledge. Use for tax on equity gains, transaction costs in
  backtests, ETF exclusion rules, or compliance framing — not for changing scoring code.
---

# Regulatory Desk — Stock_Analysis

## Implemented in repo

| Area | Location |
|------|----------|
| Broker costs | `backtest/costs.py` — STT, stamp duty, GST, STCG/LTCG assumptions |
| Instrument exclusion | `src/universe_filter.py` — ETFs, InvITs, REITs, illiquid ADV |
| Investor safety rules | `.cursor/rules/stock-analysis-system.mdc`, core-interaction |

## Research-only (no pipeline module)

- SEBI ASM/GSM, F&O ban MWPL, insider trading, RA/IA registration
- Personal tax filing — always recommend CA for individual cases

## Workflow

1. Separate **backtest cost assumptions** (code) from **live tax law** (verify Finance Act / CBDT).
2. When user asks about report actions, clarify pipeline is **not** SEBI-registered advice.
3. For backtest P&L interpretation, cite `backtest/costs.py` parameters.

## Report template

```markdown
# Regulatory Memo

**Topic:** | **Repo touchpoint:**

## Rule / cost model
[From costs.py or SEBI — cite]

## Impact on Stock_Analysis user
[Backtest realism | universe exclusion | disclosure]

## Not covered by pipeline
[Gap — manual verification needed]

**Consult CA/lawyer for personal tax/legal matters.**
```

## Hand off

- Surveillance stock quality → Fundamental
- F&O rules → `india-markets-derivatives` (research-only)
