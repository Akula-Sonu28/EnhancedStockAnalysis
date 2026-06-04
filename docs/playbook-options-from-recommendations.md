# Options + Recommendations — Beginner Playbook

**Read this first:** Your system is built to make money on **cash equity** (15–30 day Turbo MTF).
Options are an **add-on** for hedging or small directional bets — not a replacement for following
NEW POSITION / SELL on the Excel sheet.

**No system guarantees profit.** This playbook reduces beginner mistakes.

---

## Two tracks every week

| Track | What | Where money is made first |
|-------|------|---------------------------|
| **A — Equity (primary)** | Buy/sell shares per Portfolio Allocation | `analyze_top200` → Excel |
| **B — Options (overlay)** | Hedge or tiny directional bets | Manual on broker; rules below |

Run Track A every week. Run Track B only when the rules say so.

---

## Weekly process (same as Turbo MTF)

### Sunday / Monday — preview

```bash
python3 scripts/run_analysis.py --dry-run --fast
```

Type **ANALYSE** in Cursor. Fix any FAIL before live.

### Once — live commit

```bash
python3 scripts/run_analysis.py
```

Then **ANALYSE** again.

### Options context (2 minutes)

```bash
python3 scripts/options_weekly_playbook.py
```

Read the printed **regime → options mode** before opening the broker F&O tab.

---

## Map pipeline actions → what you do

### Track A — Equity (do this for every row you act on)

| Action | You do | Options? |
|--------|--------|----------|
| **SELL** / **EXIT NOW** | Sell shares (urgent) | No new options on that symbol |
| **NEW POSITION** | Buy shares (turbo PASS) | Optional: skip options until holding 1+ week |
| **INCREASE** | Add shares | Same |
| **HOLD** | Keep | See hedge rules below |
| **WATCHLIST** | No trade | No options |
| **CONSIDER SELLING** | Review; often trim | Rarely buy puts unless large position |

**Rule:** If you have not executed the **equity** trade, do not open an option on that idea “for more leverage.”

---

## Track B — Options (beginner allowed strategies only)

### Strategy 1 — Portfolio hedge (learn this first)

**When:** Regime **BEAR** or **SIDEWAYS** + VIX ≥ 20, and you hold ≥ ₹5L in stocks.

**What:** Buy **1 lot Nifty put** (monthly expiry), strike slightly OTM (e.g. ~2–3% below spot).

**Why:** If market falls, put gains partly offset stock losses.

**Size:** Hedge ~30–50% of portfolio beta, not 100% on day one.

**Do not:** Buy puts every week in calm markets (VIX &lt; 18) — premium bleeds.

### Strategy 2 — Stock hedge (one name you already own)

**When:** Large holding (e.g. &gt; ₹1L) and action is **HOLD** but regime weak.

**What:** Buy **stock put** on that symbol (if in F&O list) — 1 lot only.

**Max loss:** Premium paid (if you only buy, never sell naked).

### Strategy 3 — Directional index (only after 4+ paper weeks)

**When:** Regime **BULL**, turbo many **NEW POSITION**, VIX &lt; 18.

**What:** Small **call** or **futures long** on Nifty — **not** on every stock pick.

**Skip when:** `trading_recommendation` = `WAIT_AND_WATCH` (your regime file).

### Forbidden for first 6 months

- Selling naked calls/puts
- Stock options on every NEW POSITION name
- “Double leverage” (full equity + aggressive calls same day)
- Trading options on expiry day as a beginner

---

## Regime → options mode (quick table)

| Regime | VIX | Equity aggression | Options mode |
|--------|-----|-------------------|--------------|
| BULL | &lt; 18 | Normal NEW/INCREASE | **OFF** or tiny index call (advanced) |
| BULL | ≥ 18 | Normal | Light put hedge optional |
| SIDEWAYS | &lt; 20 | Smaller NEW sizes | **OFF** or 1 protective put if large book |
| SIDEWAYS | ≥ 20 | Cautious | **LIGHT hedge** (1 Nifty put) |
| BEAR | any | SELL first; few NEW | **HEDGE** (puts); no new call lottery |
| WAIT_AND_WATCH | any | Equity only top picks | **NO new options** |

Current file: `data/regime_verification.json` — refresh by re-running analysis.

---

## Example week (fake numbers)

- Regime: SIDEWAYS, VIX 16, WAIT_AND_WATCH  
- Excel: 2× NEW POSITION, 1× SELL  

**Do:**

1. Execute **SELL** in equity.  
2. Execute **NEW** with smaller size (half deploy cash if cautious).  
3. Options: **none** this week (VIX low, wait-and-watch).

---

## Paper trading gate (before real option premium)

Log 8 weeks in a notebook or CSV:

| Week | Regime | Option trade? | Premium ₹ | Result ₹ | Rule followed? |
|------|--------|---------------|-----------|----------|----------------|

Go live with options only after **8 paper weeks** and **Track A** running cleanly.

---

## Broker setup (Zerodha-style)

1. Enable **F&O segment** (separate activation + income proof).  
2. Use **Basket** or single order — 1 lot only.  
3. Set **GTT** for equity; options managed manually at first.  
4. Read margin block before submit — if margin &gt; 20% of capital, skip.

---

## How this repo will grow (later)

| Phase | Deliverable |
|-------|-------------|
| Now | This playbook + `scripts/options_weekly_playbook.py` |
| Next | `data/fno_overlay_latest.json` from regime + holdings |
| Later | Separate F&O sheet in Excel (not mixed into action enum) |

---

## One-sentence discipline

**Make money on equity recommendations first; use options only to protect or express index view when regime and VIX say risk is elevated.**
