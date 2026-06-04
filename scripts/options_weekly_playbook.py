#!/usr/bin/env python3
"""
Weekly options overlay guidance from regime + latest Portfolio Allocation Excel.

Does NOT place trades. Equity actions remain primary (Turbo MTF / QMST).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGIME_PATH = ROOT / "data" / "regime_verification.json"
REPORTS_DIR = ROOT / "reports"

EQUITY_ACTIONS = frozenset(
    {
        "SELL",
        "EXIT NOW - Heavy exhaustion",
        "NEW POSITION",
        "INCREASE POSITION",
        "INCREASE",
        "HOLD",
        "WATCHLIST",
        "CONSIDER SELLING",
        "REDUCE (SECTOR OVERWEIGHT)",
    }
)


def _load_regime() -> dict:
    if not REGIME_PATH.exists():
        return {}
    with open(REGIME_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("regime") or data


def _options_mode(regime: str, vix: float, trading_rec: str) -> tuple[str, str]:
    regime_u = (regime or "UNKNOWN").upper()
    rec_u = (trading_rec or "").upper()

    if "WAIT" in rec_u or "WATCH" in rec_u:
        return "OFF", "Regime says wait — no new option premium this week."

    if regime_u == "BEAR":
        return "HEDGE", "Bear regime — consider 1 Nifty put; no new call bets."

    if regime_u == "SIDEWAYS":
        if vix >= 20:
            return "LIGHT_HEDGE", "Choppy + elevated VIX — optional 1 Nifty put if book ≥ ₹5L."
        return "OFF", "Sideways, calm VIX — focus equity only."

    if regime_u == "BULL":
        if vix >= 18:
            return "LIGHT_HEDGE", "Bull but nervous vol — optional light hedge only."
        return "OFF", "Bull, low VIX — equity NEW/INCREASE; skip option lottery."

    return "OFF", "Unknown regime — equity only."


def _latest_report() -> Path | None:
    if not REPORTS_DIR.exists():
        return None
    candidates = sorted(
        REPORTS_DIR.glob("Enhanced_Stock_Report*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _summarize_allocation(xlsx_path: Path) -> dict[str, list[str]]:
    try:
        import pandas as pd
    except ImportError:
        return {}

    try:
        df = pd.read_excel(xlsx_path, sheet_name="Portfolio Allocation", header=1)
    except Exception:
        return {}

    col = "action_recommendation"
    if col not in df.columns:
        for alt in ("ACTION", "Action", "action"):
            if alt in df.columns:
                col = alt
                break
        else:
            return {}

    sym_col = "symbol" if "symbol" in df.columns else "Symbol"
    if sym_col not in df.columns:
        return {}

    out: dict[str, list[str]] = {}
    for action, group in df.groupby(col):
        key = str(action).strip().upper()
        if not key:
            continue
        symbols = group[sym_col].astype(str).head(8).tolist()
        out[key] = symbols
    return out


def main() -> int:
    regime_data = _load_regime()
    regime = regime_data.get("regime", "UNKNOWN")
    vix = float(regime_data.get("vix_level") or 0)
    trading_rec = regime_data.get("trading_recommendation", "")
    mode, rationale = _options_mode(regime, vix, trading_rec)

    print("=" * 60)
    print("OPTIONS WEEKLY PLAYBOOK (overlay only — equity is primary)")
    print("=" * 60)
    print(f"Regime file : {REGIME_PATH}")
    print(f"Regime      : {regime}  |  VIX: {vix:.1f}  |  Rec: {trading_rec}")
    print(f"Options mode: {mode}")
    print(f"Guidance    : {rationale}")
    print()

    report = _latest_report()
    if report:
        print(f"Latest report: {report.name}")
        summary = _summarize_allocation(report)
        if summary:
            print("\nEquity actions to execute FIRST (from Portfolio Allocation):")
            priority = [
                "EXIT NOW - HEAVY EXHAUSTION",
                "SELL",
                "NEW POSITION",
                "INCREASE POSITION",
                "INCREASE",
                "HOLD",
            ]
            seen = set()
            for key in priority:
                for k, syms in summary.items():
                    if key in k.upper() and k not in seen:
                        seen.add(k)
                        print(f"  {k}: {', '.join(syms)}")
            for k, syms in summary.items():
                if k not in seen:
                    print(f"  {k}: {', '.join(syms)}")
        else:
            print("(Could not read Portfolio Allocation sheet — open Excel manually.)")
    else:
        print("No Enhanced_Stock_Report*.xlsx in reports/ — run analysis first.")

    print()
    print("Track A (money path): execute SELL → then NEW/INCREASE per Excel.")
    print("Track B (options):    follow mode above; see docs/playbook-options-from-recommendations.md")
    print("Paper trade options 8 weeks before risking real premium.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
