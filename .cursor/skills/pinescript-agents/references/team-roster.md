# Pine Script Agents — Team Roster

All paths relative to `.cursor/skills/pinescript-agents/`.

| Skill | Role | Triggers |
|-------|------|----------|
| **pinescript-agents** | Master router | Pine Script, TradingView, `.pine`, QLVM, `PINE` |
| **pine-manager** | Project orchestration, scoping, multi-phase plans | "complete system", "trading system", complex multi-feature |
| **pine-visualizer** | Decompose ideas, plan components, YouTube URLs | "how would I build", concept breakdown |
| **pine-developer** | Production Pine Script v6 implementation | create, write, implement, code |
| **pine-debugger** | Errors, repainting, na propagation, opaque TV behavior | debug, fix, error, not working |
| **pine-backtester** | Metrics, equity curve, win rate, drawdown | backtest, performance, metrics |
| **pine-optimizer** | Performance, inputs, visuals, alerts | optimize, faster, UX, clean up |
| **pine-publisher** | TradingView House Rules, docs, release prep | publish, release, documentation |

## Coordination matrix (from pine-manager)

| User request | Primary | Supporting |
|--------------|---------|------------|
| Create indicator | visualizer → developer | debugger, optimizer |
| Build strategy | visualizer → developer → backtester | debugger, optimizer |
| Script has errors | debugger | developer |
| Optimize script | optimizer | backtester |
| Test performance | backtester | debugger |
| Prepare publishing | publisher | optimizer |
| Complex multi-part | manager | all as needed |

## Stock_Analysis cross-links

| Pine work touches… | Also load |
|--------------------|-----------|
| QLVM / LVM logic | `src/lowvol_momentum.py`, `src/quality_lowvol_momentum.py` |
| Dashboard / HTML | `software-product-frontend`, `ui-designer` |
| Scoring / pipeline thresholds | `five-agent-council`, `stock-analysis-system` |
