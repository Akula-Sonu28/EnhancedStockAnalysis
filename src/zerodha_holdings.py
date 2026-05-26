"""Zerodha Kite Connect holdings fetcher (read-only).

Maps Kite ``holdings()`` to the same DataFrame shape as Kite CSV exports
(Instrument, Qty., Avg. cost, LTP, Invested, Cur. val, P&L, ...).

Auth via environment variables only:
    KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN
    KITE_USE_HOLDINGS=true  — enable API path in the analyzer

Never put credentials in config.json or commit them.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

KITE_CSV_COLUMNS = [
    "Instrument",
    "Qty.",
    "Avg. cost",
    "LTP",
    "Invested",
    "Cur. val",
    "P&L",
    "Net chg.",
    "Day chg.",
]

_BROKER_TO_NSE = {
    "GVTD": "GVT&D",
    "AREM": "ARE&M",
    "BAJAJAUTO": "BAJAJ-AUTO",
    "JKBANK": "J&KBANK",
    "MM": "M&M",
    "MMFIN": "M&MFIN",
    "NAMINDIA": "NAM-INDIA",
}


def zerodha_holdings_enabled() -> bool:
    return os.environ.get("KITE_USE_HOLDINGS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


@dataclass(frozen=True)
class ZerodhaConfig:
    api_key: str
    api_secret: str
    access_token: str

    @classmethod
    def from_env(cls) -> "ZerodhaConfig":
        api_key = os.environ.get("KITE_API_KEY", "").strip()
        api_secret = os.environ.get("KITE_API_SECRET", "").strip()
        access_token = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
        missing = [
            name
            for name, val in (
                ("KITE_API_KEY", api_key),
                ("KITE_API_SECRET", api_secret),
                ("KITE_ACCESS_TOKEN", access_token),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(
                f"Missing {', '.join(missing)}. "
                "Set them in .env and run: python3 scripts/kite_login.py"
            )
        return cls(api_key=api_key, api_secret=api_secret, access_token=access_token)


def _kite_client(cfg: ZerodhaConfig, *, auto_session: bool = False):
    try:
        from kiteconnect import KiteConnect
    except ImportError as exc:
        raise RuntimeError(
            "kiteconnect is not installed. Run: pip install kiteconnect"
        ) from exc
    token = cfg.access_token
    if auto_session or os.environ.get("KITE_AUTO_LOGIN", "").lower() in ("1", "true", "yes"):
        from src.kite_session import ensure_access_token
        token = ensure_access_token(auto_browser=auto_session)
    kite = KiteConnect(api_key=cfg.api_key)
    kite.set_access_token(token)
    return kite


def effective_quantity(row: dict[str, Any]) -> int:
    """Settled (quantity) plus T+1 buys. Do not use opening_quantity — it is start-of-day."""
    q = int(row.get("quantity") or 0)
    t1 = int(row.get("t1_quantity") or 0)
    return q + t1


def _parse_filled_qty(qty_field: str) -> int:
    """Kite orders CSV/API: '84/84' or '14/14' -> filled leg."""
    text = str(qty_field).strip()
    if "/" in text:
        return int(text.split("/")[0].strip() or 0)
    return int(float(text) if text else 0)


def apply_todays_order_adjustments(
    holdings_df: pd.DataFrame,
    orders_df: pd.DataFrame,
) -> pd.DataFrame:
    """Subtract today's COMPLETE SELLs (and add BUYs) so sold names drop out."""
    if holdings_df is None or holdings_df.empty or orders_df is None or orders_df.empty:
        return holdings_df

    sym_col = "Instrument" if "Instrument" in holdings_df.columns else "Symbol"
    if sym_col not in holdings_df.columns:
        return holdings_df

    type_col = next((c for c in ("Type", "transaction_type") if c in orders_df.columns), None)
    if not type_col:
        return holdings_df

    status_col = next((c for c in ("Status", "status") if c in orders_df.columns), None)
    orders = orders_df.copy()
    if status_col:
        orders = orders[orders[status_col].astype(str).str.upper() == "COMPLETE"]

    net_delta: dict[str, int] = {}
    for _, row in orders.iterrows():
        sym = str(row.get("Instrument", row.get("tradingsymbol", ""))).strip().upper()
        if not sym:
            continue
        sym = _BROKER_TO_NSE.get(sym, sym)
        filled = _parse_filled_qty(row.get("Qty.", row.get("quantity", 0)))
        txn = str(row.get(type_col, "")).strip().upper()
        if txn == "SELL":
            net_delta[sym] = net_delta.get(sym, 0) - filled
        elif txn == "BUY":
            net_delta[sym] = net_delta.get(sym, 0) + filled

    if not net_delta:
        return holdings_df

    out = holdings_df.copy()
    out[sym_col] = out[sym_col].astype(str).str.strip().str.upper().replace(_BROKER_TO_NSE)
    adjusted = []
    for sym, delta in net_delta.items():
        if sym not in out[sym_col].values:
            continue
        idx = out.index[out[sym_col] == sym]
        for i in idx:
            old_q = float(out.at[i, "Qty."])
            new_q = max(0.0, old_q + delta)
            out.at[i, "Qty."] = new_q
            if new_q <= 0:
                adjusted.append(sym)
            elif old_q > 0 and new_q < old_q:
                ratio = new_q / old_q
                for col in ("Invested", "Cur. val", "P&L"):
                    if col in out.columns:
                        out.at[i, col] = float(out.at[i, col]) * ratio

    out = out[out["Qty."] > 0].copy()
    if adjusted:
        logger.info("Adjusted holdings after today's orders: %s", ", ".join(sorted(set(adjusted))))
    return out


def holdings_raw(cfg: ZerodhaConfig | None = None, *, auto_session: bool = False) -> list[dict[str, Any]]:
    cfg = cfg or ZerodhaConfig.from_env()
    kite = _kite_client(cfg, auto_session=auto_session)
    rows = kite.holdings()
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected holdings response from Kite API")
    return [r for r in rows if effective_quantity(r) > 0]


def kite_row_to_record(row: dict[str, Any]) -> dict[str, float | str]:
    symbol = str(row.get("tradingsymbol", "")).strip().upper()
    qty = float(effective_quantity(row))
    avg = float(row.get("average_price") or 0)
    ltp = float(row.get("last_price") or 0)
    if ltp <= 0 and qty > 0:
        ltp = avg
    invested = avg * qty
    cur_val = ltp * qty
    pnl = float(row.get("pnl") if row.get("pnl") is not None else (cur_val - invested))
    net_chg = (pnl / invested * 100.0) if invested > 0 else 0.0
    day_chg = float(row.get("day_change_percentage") or row.get("day_change") or 0)
    return {
        "Instrument": symbol,
        "Qty.": qty,
        "Avg. cost": avg,
        "LTP": ltp,
        "Invested": invested,
        "Cur. val": cur_val,
        "P&L": pnl,
        "Net chg.": round(net_chg, 2),
        "Day chg.": round(day_chg, 2),
    }


def holdings_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=KITE_CSV_COLUMNS)
    records = [kite_row_to_record(r) for r in rows]
    df = pd.DataFrame(records)
    df["Instrument"] = df["Instrument"].astype(str).str.strip().replace(_BROKER_TO_NSE)
    for col in ("Qty.", "Avg. cost", "LTP", "Invested", "Cur. val", "P&L", "Net chg.", "Day chg."):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df[df["Qty."] > 0].copy()
    return df


def fetch_holdings_dataframe(
    cfg: ZerodhaConfig | None = None,
    *,
    auto_session: bool = False,
    apply_orders: bool = True,
) -> pd.DataFrame:
    """Live holdings from Kite API in Kite-CSV-compatible shape."""
    rows = holdings_raw(cfg, auto_session=auto_session)
    df = holdings_to_dataframe(rows)
    if apply_orders:
        try:
            odf = fetch_orders_dataframe(cfg, auto_session=False)
            df = apply_todays_order_adjustments(df, odf)
        except Exception as exc:
            logger.warning("Order adjustment skipped: %s", exc)
    return df


def orders_raw(cfg: ZerodhaConfig | None = None, *, auto_session: bool = False) -> list[dict[str, Any]]:
    """Today's orders from Kite (all statuses)."""
    cfg = cfg or ZerodhaConfig.from_env()
    kite = _kite_client(cfg, auto_session=auto_session)
    rows = kite.orders()
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected orders response from Kite API")
    return rows


def kite_order_to_record(row: dict[str, Any]) -> dict[str, str | float]:
    symbol = str(row.get("tradingsymbol", "")).strip().upper()
    symbol = _BROKER_TO_NSE.get(symbol, symbol)
    txn = str(row.get("transaction_type", "")).strip().upper()
    product = str(row.get("product", "")).strip().upper()
    qty = int(row.get("quantity") or 0)
    filled = int(row.get("filled_quantity") or qty)
    avg = float(row.get("average_price") or 0)
    status = str(row.get("status", "")).strip().upper()
    ts = row.get("order_timestamp") or row.get("exchange_timestamp") or ""
    if hasattr(ts, "strftime"):
        time_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    else:
        time_str = str(ts).replace("T", " ")[:19]
    return {
        "Time": time_str,
        "Type": txn,
        "Instrument": symbol,
        "Product": product,
        "Qty.": f"{filled}/{qty}",
        "Avg. price": avg,
        "Status": status,
    }


def orders_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    cols = ["Time", "Type", "Instrument", "Product", "Qty.", "Avg. price", "Status"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame([kite_order_to_record(r) for r in rows])
    return df.sort_values("Time", ascending=False).reset_index(drop=True)


def fetch_orders_dataframe(cfg: ZerodhaConfig | None = None, *, auto_session: bool = False) -> pd.DataFrame:
    return orders_to_dataframe(orders_raw(cfg, auto_session=auto_session))


def save_orders_snapshot(
    df: pd.DataFrame,
    directory: Path | str = "Holding",
    prefix: str = "orders_api",
) -> Path:
    from datetime import datetime

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{ts}.csv"
    out = df.copy()
    if "" not in out.columns:
        out[""] = ""
    out.to_csv(path, index=False)
    latest = directory / "orders_latest.csv"
    out.to_csv(latest, index=False)
    logger.info("Wrote orders snapshot: %s", path)
    return path


def save_holdings_snapshot(
    df: pd.DataFrame,
    directory: Path | str = "Holding",
    prefix: str = "holdings_api",
) -> Path:
    """Write a timestamped CSV under Holding/ for audit / offline reruns."""
    from datetime import datetime

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = directory / f"{prefix}_{ts}.csv"
    out = df.copy()
    if "" not in out.columns:
        out[""] = ""
    out.to_csv(path, index=False)
    latest = directory / "holdings_latest.csv"
    out.to_csv(latest, index=False)
    logger.info("Wrote holdings snapshot: %s", path)
    return path
