# Specialist Team Roster — Stock_Analysis

Each desk skill lives in `.cursor/skills/india-markets-*`. This repo **implements** fundamental, technical, macro/regime, and portfolio logic in Python; derivatives and IPO desks are research-only.

## Teams

| Desk | Skill folder | Repo implementation | Research-only? |
|------|--------------|---------------------|----------------|
| Orchestrator | `india-markets-orchestrator` | Routes + synthesizes | — |
| Fundamental | `india-markets-fundamental` | `src/enhanced_fundamental_analyzer.py`, v2 `fundamental_quality/growth/value` | No |
| Technical | `india-markets-technical` | `src/technical_analyzer.py`, `enhanced_technical_analyzer.py`, `pattern_recognition.py`, `early_breakout_detector.py` | No |
| Macro / regime | `india-markets-macro` | `market_regime_detector.py`, `adaptive_market_strategy.py`, `crisis_detector.py` | No |
| Portfolio / risk | `india-markets-portfolio` | Analyzer allocation, hard-stop, rotation, `recommendation_history.py` | No |
| Regulatory / tax | `india-markets-regulatory` | `backtest/costs.py`; general SEBI knowledge | Partial |
| Derivatives F&O | `india-markets-derivatives` | — | **Yes** |
| IPO / primary | `india-markets-ipo` | — | **Yes** |

## Repo-native skills (not india-markets desks)

| Skill | Role |
|-------|------|
| `stock-analysis-system` | Code, config contracts, v2 promotion |
| `post-analysis-audit` | ANALYSE after pipeline run |
| `turbo-mtf-weekly-trader` | Weekly Turbo MTF process |
| `five-agent-council` | Multi-agent **code** review (ARCH/QUANT/RISK/AUDIT/SKEPTIC) |

**Council vs india-markets:** Use **five-agent-council** for changing the system; use **india-markets-orchestrator** for interpreting output and investment narrative.

## Routing (Stock_Analysis context)

| User intent | Primary desk(s) | Repo action |
|-------------|-----------------|-------------|
| "ANALYSE latest run" | — | `post-analysis-audit` skill |
| "Weekly rebalance plan" | Portfolio + Macro | `turbo-mtf-weekly-trader` |
| "Why SELL on INFY?" | Fundamental + Technical + Portfolio | Read report + history |
| "Regime and sector tilt" | Macro | `data/last_known_regime.json` + Sector Analysis sheet |
| "Full view on RELIANCE" | All implemented desks | `main.py -s RELIANCE` then synthesize |
| "Bank Nifty straddle" | Derivatives only | Research memo (no pipeline) |
| "Apply for IPO?" | IPO + Fundamental | Research memo (no pipeline) |
| "Change scoring weights" | — | `five-agent-council` + `stock-analysis-system` |

## Handoff block

```
Symbol: RELIANCE
Question: ...
Horizon: Turbo MTF 15-30d / long-term
Repo artifacts: [report path, cache path, history row]
Pipeline action/score: ...
Open for this desk: ...
```

See [repo-integration.md](repo-integration.md) for paths and commands.
