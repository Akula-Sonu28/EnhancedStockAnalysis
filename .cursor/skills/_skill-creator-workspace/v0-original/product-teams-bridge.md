# Product Teams Bridge — Research · Governance · Engineering

Stock_Analysis is built by **three coordinated layers**. This document is the
single handoff map for all of them.

## Three layers

| Layer | Orchestrator | Delivers | Does NOT |
|-------|--------------|----------|----------|
| **Research** | `india-markets-orchestrator` | NSE investment memos | Implement code |
| **Governance** | `five-agent-council` | Council Recommendation, gate | Buy/sell advice |
| **Engineering** | `software-product-orchestrator` | Shipped code, UI, CI | Change scoring without council |

Supporting contracts: `stock-analysis-system` (always for pipeline work).

---

## Engineering team ↔ council

| Council | Software role | Focus in debate / BUILD |
|---------|---------------|-------------------------|
| **ARCH** | Backend + Platform | Module boundaries, repo-map ownership, v1/v2 isolation |
| **QUANT** | Backend | Scoring engines, backtest strategies, calibration scripts |
| **RISK** | Backend + PM | Hard-stop, universe, investor-facing product flag |
| **AUDIT** | Platform + Backend | pytest suites, CI, history/Excel contracts |
| **SKEPTIC** | All engineering roles | Dry-run vs live, partial deploy, dashboard stale payload |

### BUILD vs COUNCIL

| Change type | Path |
|-------------|------|
| Dashboard CSS/layout on existing fields | `BUILD` → Frontend |
| New script reading existing Excel | `BUILD` → Backend + Platform |
| Scoring weights, thresholds, exits | `COUNCIL` → gate → Backend implements |
| New dashboard column from new score semantics | `COUNCIL` → gate → Backend + Frontend |
| CI/test-only | `BUILD` → Platform |

---

## Engineering topic → skills to load

| BUILD brief signals | Read |
|---------------------|------|
| Scope, acceptance criteria | `software-product-pm/SKILL.md` |
| Python pipeline, src/, backtest | `software-product-backend/SKILL.md` |
| frontend/, dashboard, canvas | `software-product-frontend/SKILL.md` + `ui-designer` |
| CI, scripts/, pytest infra | `software-product-platform/SKILL.md` |
| Code ownership question | `software-product-orchestrator/references/repo-map.md` |

---

## India Markets ↔ council (research layer)

| Council | Primary India Markets desk(s) | NSE focus |
|---------|--------------------------------|-----------|
| **ARCH** | orchestrator `repo-integration.md` | NSE data paths (Upstox/yfinance `.NS`, cache) |
| **QUANT** | fundamental, technical, macro | v2 factors, regime weights, IC |
| **RISK** | portfolio, regulatory | Hard-stops, ASM/universe, Zerodha costs |
| **AUDIT** | orchestrator `data-sources.md` | Excel/history contracts |
| **SKEPTIC** | regulatory, macro | Regime mislabel, stale cache, disclosure |

### Topic → india-markets desk skills (Round 1)

| Problem Brief signals | Read before Round 1 |
|-----------------------|---------------------|
| fundamental_quality/growth/value, PE/ROE | `india-markets-fundamental/SKILL.md` |
| turbo_entry, breakout, RSI exhaustion | `india-markets-technical/SKILL.md` |
| BULL/BEAR/SIDEWAYS, sector rotation | `india-markets-macro/SKILL.md` |
| hard-stop, allocation, Turbo MTF | `india-markets-portfolio/SKILL.md` |
| STT/LTCG, universe_filter, ASM | `india-markets-regulatory/SKILL.md` |

Cap at three desk skills per council agent.

---

## Extended Problem Brief fields

```markdown
**Product surface:** [analyzer | dashboard | backtest | scripts | CI]
**India context:** [NSE universe | backtest-only | regulatory | none]
**Investor-facing:** YES / NO
**Council required:** YES / NO
**BUILD assign:** [PM | Backend | Frontend | Platform]
**Desk input needed:** [fundamental | technical | macro | portfolio | regulatory | none]
```

---

## Handoff flows

### Research → council → engineering

```
india-markets desk memo
  → Council Escalation block
  → COUNCIL (gate)
  → user confirm
  → software-product-backend / frontend implements
  → pytest gate
  → optional ANALYSE + india-markets re-narrative
```

### Product feature (no scoring change)

```
BUILD request
  → software-product-pm (brief)
  → parallel Backend / Frontend / Platform
  → test plan
  → ship
```

### Council-only (debate, no implement)

```
COUNCIL DEBATE ONLY <topic>
  → rounds 1–3
  → user decides BUILD later
```

---

## Quick commands

| Command | Layer |
|---------|-------|
| `COUNCIL <topic>` | Governance |
| `BUILD <feature>` | Engineering |
| `BUILD + COUNCIL <topic>` | Governance then engineering |
| Full view on SYMBOL | Research (`india-markets-orchestrator`) |
| `ANALYSE` | `post-analysis-audit` |
