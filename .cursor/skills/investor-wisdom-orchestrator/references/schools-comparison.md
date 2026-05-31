# Investment Schools — Deep Comparison

Supplementary reference for `investor-wisdom-orchestrator`. Load when user asks "which style suits me" or broad education.

## Decision tree: pick your school

```
Do you want to predict economy first?
  YES → Macro school (Dalio, Druckenmiller, Soros)
  NO → Is price far below value?
         YES → Value school (Graham, Greenblatt)
         NO → Is earnings growth the main story?
                YES → Growth school (Lynch, Fisher, Kedia, Agrawal)
                NO → Is it a decades-long compounder?
                       YES → Quality school (Buffett, Munger, Damani)
```

## Holding period vs activity

| Style | Typical hold | Portfolio turnover |
|-------|--------------|-------------------|
| Graham net-net | Months–2Y | High among value names |
| Buffett/Munger/Damani | 10–30+ years | Very low |
| Lynch GARP | 1–5 years | Medium-high |
| Fisher | 5–20 years | Low |
| Greenblatt formula | ~1 year rebalance | Systematic high |
| Marks cycle | Full cycle | Medium |
| Druckenmiller/Soros macro | Days–months | Very high |
| Wood thematic | 5–10 years | Medium (volatile) |
| Jhunjhunwala/Kedia | 5–15 years | Low–medium |

## How each school makes money (mechanism)

| School | Primary alpha source | Main risk |
|--------|---------------------|-----------|
| Deep value | Mean reversion, corporate events | Value traps, fraud |
| Quality compounder | Reinvestment at high ROIC | Overpaying, moat death |
| GARP | Earnings surprise + rerating | Growth deceleration |
| Scuttlebutt growth | Early quality identification | Illiquidity, wrong management read |
| Magic formula | Systematic mispricing | Multi-year lag vs momentum |
| Macro | Regime/liquidity inflection | Wrong thesis sized large |
| Reflexivity | Trend overshoot + reversal | Early vs late in trend |
| Disruption | S-curve adoption | Duration, hype |
| India SMILE/QGLP | Small→large cap migration | Governance, liquidity |

## Additional famous investors (brief — no dedicated skill yet)

| Investor | One-line framework |
|----------|-------------------|
| **John Templeton** | Buy maximum pessimism globally; contrarian value |
| **David Tepper** | Distressed credit/equity at cycle lows; aggressive when odds favor |
| **Seth Klarman** | Baupost margin of safety; risk-averse value + special sits |
| **Bill Ackman** | Concentrated activist; catalyst-driven |
| **Mohnish Pabrai** | Dhandho — low risk, high uncertainty bets; clone great investors |
| **Porinju Veliyath** | Indian turnaround/value in ignored smallcaps (high risk) |
| **Raamdeo Agrawal** | Same as Ramdeo — QGLP co-founder MOFSL |
| **Nassim Taleb** | Antifragile barbell — not stock-picker; tail risk framing |

Request a dedicated skill if you use one of these repeatedly.

## Indian market cross-cutting rules (all schools)

1. **Promoter governance** — non-negotiable for long-only India
2. **Liquidity** — SMILE/smallcap styles need size discipline
3. **Policy** — banks, infra, pharma hit by RBI/ministry cycles
4. **Tax** — STCG/LTCG/STT affects turnover styles differently
5. **Accounting** — Ind AS, related-party, auditor changes

## Combining schools (orchestrator pattern)

| Question type | Combine |
|---------------|---------|
| Large-cap consumer | Buffett + Damani + Agrawal QGLP |
| Midcap multibagger | Kedia + Lynch + Fisher scuttlebutt |
| Market crash entry | Marks + Graham + Templeton lens |
| Rate cycle | Dalio + Druckenmiller + Marks |
| IT/tech disruption | Fisher + Wood (with skeptic) + Lynch category |

**Independent of Stock_Analysis v1/v2 pipeline scoring.**
