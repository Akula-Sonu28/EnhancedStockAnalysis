# Pine Script — Stock_Analysis Repo Integration

## Pine files in this repo

| File | Purpose |
|------|---------|
| `scripts/qlvm_indicator.pine` | QLVM overlay (v6) — vol filter, 12m momentum, SMA50, stop |
| `docs/dev-log.md` | Dated notes when Pine work ships |

New indicators/strategies: prefer `scripts/<descriptive-name>.pine` (lowercase, hyphens).

## Python mirrors (read before editing Pine)

| Module | What Pine mirrors |
|--------|-------------------|
| `src/quality_lowvol_momentum.py` | Quality-LVM composite (fundamentals + price) |
| `src/lowvol_momentum.py` | Price-only LVM |
| `config.py` | Default lookbacks, vol cap, stop % — align Pine `input.*` defaults |

Pine cannot run cross-sectional rank across NSE universe or Screener fundamentals — comments in `qlvm_indicator.pine` document that gap; keep fund/rank logic in Python analyzer.

## Upstream skill docs (optional)

Installed skills reference `/docs/pinescript-v6/…` and `/projects/blank.pine` from the upstream
[pinescript-agents](https://github.com/traderspost/pinescript-agents) repo. Those paths are **not**
in Stock_Analysis unless you clone that repo separately. For syntax rules, rely on
`pine-developer/SKILL.md` inline sections (ternary one-line, indentation).

## pine-visualizer caveat

Upstream `pine-visualizer` may call `python tools/video-analyzer.py` — **not present** in this repo.
For YouTube URLs, analyze transcript manually or skip video tooling.

## Verification

After Pine edits:

1. Paste into TradingView Pine Editor — confirm compile
2. If logic tied to Python strategy, spot-check against `backtest/lvm_strategy.py` or QLVM tests
3. Log non-trivial changes in `docs/dev-log.md`

## Related skills

- `@pinescript-agents` — entry router (this bundle)
- `@india-markets-technical` — chart context for NSE names
- `@product-teams-orchestrator` — if Pine + dashboard + council in one request
