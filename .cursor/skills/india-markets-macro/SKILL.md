---
name: india-markets-macro
description: >-
  Macro and market-regime desk for Stock_Analysis. Uses market_regime_detector,
  adaptive_market_strategy, crisis_detector (cross-asset), Nifty/Bank Nifty/VIX
  proxies, and regime-conditional v2 weights. Use for BULL/BEAR/SIDEWAYS context,
  sector rotation, RBI/budget impact on Nifty 500 portfolio, or explaining regime
  column in recommendation_history.
---

# Macro Desk — Stock_Analysis

## Repo modules

| Module | Role |
|--------|------|
| `market_regime_detector.py` | BULL / BEAR / SIDEWAYS |
| `adaptive_market_strategy.py` | Regime-adaptive weights + exposure caps |
| `crisis_detector.py` | Nifty, VIX, INR, crude, SPX — **default OFF** (`ENABLE_CRISIS_DETECTOR=False`) |
| `hybrid_scoring_v2.py` | Per-regime weights in `data/calibrated_weights_v2_{BULL,BEAR,SIDEWAYS}.json` |

## Read data

1. `data/last_known_regime.json`
2. Excel **Dashboard**, **Sector Analysis**, **Benchmark Comparison**
3. History column `regime` in `data/recommendation_history.csv`

## Cross-asset proxies (in code)

| Instrument | Symbol |
|------------|--------|
| Nifty 50 | `^NSEI` |
| Bank Nifty | `^NSEBANK` |
| India VIX | `^INDIAVIX` |
| USD/INR | `USDINR=X` |

## Workflow

1. State current **pipeline regime** and exposure posture (BULL/BEAR/SIDEWAYS weights).
2. Map user theme (RBI cut, budget, crude) → Nifty 500 **sectors** using Sector Analysis sheet.
3. Distinguish **pipeline regime logic** from general macro research (RBI dates, CPI).
4. Note if crisis detector is OFF — do not assume crisis gate is active unless config changed.

## Report template

```markdown
# Macro Memo — Stock_Analysis

**Pipeline regime:** [BULL/BEAR/SIDEWAYS] | **As of:** [last_known_regime.json date]

## Regime implications
- v2 weight shift: ...
- Exposure: BULL/SIDEWAYS/BEAR caps from adaptive_market_strategy

## Theme → sectors
| Sector | Tilt | Names in report |

## External macro (cite dated sources)
[RBI, budget, flows — supplement only]

## Portfolio implication
[Overweight/underweight vs current Portfolio Allocation sheet]
```

## Hand off

- Stock picks → Fundamental / Portfolio
- Technical entry → Technical
- Config/regime code changes → `five-agent-council`

## Five-Agent Council

**Research-only desk.** Regime **interpretation** stays here; regime **code** goes to council.

| Escalate when | Council agents most involved |
|---------------|------------------------------|
| Regime detector thresholds or BULL/BEAR/SIDEWAYS logic | QUANT, ARCH |
| Per-regime v2 weight files or promotion | QUANT, AUDIT |
| crisis_detector enable/default or cross-asset inputs | QUANT, RISK, SKEPTIC |

```markdown
## Council Escalation (from Macro desk)
**Goal:** [e.g. "Add BEAR override for sector exposure caps"]
**India context:** Nifty 500 regime | investor-facing: YES/NO
**Evidence:** [last_known_regime.json, Sector Analysis sheet]
**Proposed change:** [module/config keys]
**Council trigger:** COUNCIL <goal>
```

Bridge: `.cursor/skills/five-agent-council/references/product-teams-bridge.md`
