# Indian Market Basics — Stock_Analysis Context

## This repo's scope

- **Universe:** Nifty 500 (`stock_list_template500.csv`), NSE symbols bare ticker
- **Fetch:** yfinance `.NS`, optional Upstox, Zerodha holdings overlay
- **Not in pipeline:** F&O chains, IPO calendar, BSE-primary, Screener.in scrape

## Exchanges and indices

| Index | yfinance | Used in |
|-------|----------|---------|
| Nifty 50 | `^NSEI` | Regime, benchmark |
| Bank Nifty | `^NSEBANK` | Regime |
| India VIX | `^INDIAVIX` | Regime, crisis |
| Nifty 500 | Constituents via CSV | Universe |

## Session (IST)

Pre-open 9:00–9:08 | Regular 9:15–15:30

## Pipeline outputs (authoritative for this project)

| Artifact | Path |
|----------|------|
| Excel report | `reports/Enhanced_Stock_Report_*.xlsx` |
| HTML dashboard | `Portfolio_Allocation_Dashboard.html` |
| History | `data/recommendation_history.csv` |
| Cache | `data/cache/{SYMBOL}_comprehensive_*.json` |
| Regime | `data/last_known_regime.json` |

## Surveillance (research + filter)

- `src/universe_filter.py` excludes ETFs/InvITs/REITs and low ADV names
- ASM/GSM/F&O ban — regulatory desk; not auto-fetched by pipeline

See [repo-integration.md](repo-integration.md) for commands.
