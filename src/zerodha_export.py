"""Fetch all read-only Zerodha Kite account data and save under data/zerodha/."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from src.zerodha_holdings import (
    ZerodhaConfig,
    _kite_client,
    fetch_holdings_dataframe,
    fetch_orders_dataframe,
    holdings_to_dataframe,
    orders_to_dataframe,
    save_holdings_snapshot,
    save_orders_snapshot,
)

logger = logging.getLogger(__name__)

_EXPORT_ROOT = Path("data/zerodha")


class _JsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


def _json_dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, cls=_JsonEncoder, indent=2), encoding="utf-8")


def _safe(name: str, fn: Callable[[], Any]) -> tuple[str, Any | None, str | None]:
    try:
        return name, fn(), None
    except Exception as exc:
        logger.warning("%s failed: %s", name, exc)
        return name, None, str(exc)


def _records_to_csv(rows: list | dict | None, path: Path) -> bool:
    if not rows:
        return False
    if isinstance(rows, dict):
        for key, val in rows.items():
            if isinstance(val, list) and val:
                sub = path.parent / f"{path.stem}_{key}{path.suffix}"
                pd.DataFrame(val).to_csv(sub, index=False)
        return True
    if isinstance(rows, list) and rows:
        pd.DataFrame(rows).to_csv(path, index=False)
        return True
    return False


def _ltp_for_symbols(kite, symbols: set[str]) -> dict[str, Any]:
    if not symbols:
        return {}
    keys = [f"NSE:{s}" for s in sorted(symbols)]
    out: dict[str, Any] = {}
    batch = 200
    for i in range(0, len(keys), batch):
        chunk = keys[i : i + batch]
        try:
            out.update(kite.ltp(chunk) or {})
        except Exception as exc:
            logger.warning("ltp batch failed: %s", exc)
    return out


def fetch_all(cfg: ZerodhaConfig | None = None, *, auto_session: bool = False) -> dict[str, Any]:
    import os
    from src.kite_session import ensure_access_token

    auto = auto_session or os.environ.get("KITE_AUTO_LOGIN", "").lower() in ("1", "true", "yes")
    ensure_access_token(auto_browser=auto)
    cfg = cfg or ZerodhaConfig.from_env()
    kite = _kite_client(cfg)
    bundle: dict[str, Any] = {"fetched_at": datetime.now().isoformat(), "errors": {}}

    endpoints = [
        ("profile", kite.profile),
        ("margins", kite.margins),
        ("margins_equity", lambda: kite.margins(segment="equity")),
        ("margins_commodity", lambda: kite.margins(segment="commodity")),
        ("holdings_raw", kite.holdings),
        ("positions", kite.positions),
        ("orders_raw", kite.orders),
        ("trades", kite.trades),
        ("mf_holdings", kite.mf_holdings),
        ("mf_orders", kite.mf_orders),
        ("mf_sips", kite.mf_sips),
        ("gtts", kite.get_gtts),
        ("auction_instruments", kite.get_auction_instruments),
    ]

    for name, fn in endpoints:
        key, data, err = _safe(name, fn)
        if err:
            bundle["errors"][key] = err
        else:
            bundle[key] = data

    orders_raw = bundle.get("orders_raw") or []
    histories = {}
    if isinstance(orders_raw, list):
        for o in orders_raw:
            oid = o.get("order_id")
            if not oid:
                continue
            _, hist, err = _safe(f"order_history_{oid}", lambda oid=oid: kite.order_history(oid))
            if err:
                bundle["errors"][f"order_history_{oid}"] = err
            else:
                histories[str(oid)] = hist
    bundle["order_history"] = histories

    symbols: set[str] = set()
    for row in bundle.get("holdings_raw") or []:
        if row.get("tradingsymbol"):
            symbols.add(str(row["tradingsymbol"]).upper())
    pos = bundle.get("positions") or {}
    for leg in ("day", "net"):
        for row in pos.get(leg) or []:
            if row.get("tradingsymbol"):
                symbols.add(str(row["tradingsymbol"]).upper())
    bundle["quotes_ltp"] = _ltp_for_symbols(kite, symbols)

    bundle["holdings_csv"] = fetch_holdings_dataframe(cfg)
    bundle["orders_csv"] = fetch_orders_dataframe(cfg)
    return bundle


def save_export(bundle: dict[str, Any], root: Path | None = None) -> Path:
    root = root or _EXPORT_ROOT
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap = root / "snapshots" / ts
    latest = root / "latest"
    snap.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)

    manifest = {
        "fetched_at": bundle.get("fetched_at"),
        "errors": bundle.get("errors", {}),
        "counts": {
            "holdings": len(bundle.get("holdings_raw") or []),
            "orders": len(bundle.get("orders_raw") or []),
            "trades": len(bundle.get("trades") or []),
            "order_history": len(bundle.get("order_history") or {}),
            "gtts": len(bundle.get("gtts") or []) if isinstance(bundle.get("gtts"), list) else 0,
            "mf_holdings": len(bundle.get("mf_holdings") or []) if isinstance(bundle.get("mf_holdings"), list) else 0,
        },
    }

    json_keys = (
        "profile",
        "margins",
        "margins_equity",
        "margins_commodity",
        "holdings_raw",
        "positions",
        "orders_raw",
        "trades",
        "order_history",
        "mf_holdings",
        "mf_orders",
        "mf_sips",
        "gtts",
        "auction_instruments",
        "quotes_ltp",
        "errors",
    )

    for folder in (snap, latest):
        _json_dump(folder / "manifest.json", manifest)
        for key in json_keys:
            if key in bundle and bundle[key] is not None:
                _json_dump(folder / f"{key}.json", bundle[key])

        pos = bundle.get("positions")
        if pos:
            _records_to_csv(pos, folder / "positions.csv")

        for key in ("trades", "orders_raw", "holdings_raw", "mf_holdings", "mf_orders", "mf_sips", "gtts"):
            if isinstance(bundle.get(key), list):
                _records_to_csv(bundle[key], folder / f"{key}.csv")

        hdf = bundle.get("holdings_csv")
        odf = bundle.get("orders_csv")
        if isinstance(hdf, pd.DataFrame):
            hdf.to_csv(folder / "holdings_kite_format.csv", index=False)
        if isinstance(odf, pd.DataFrame):
            odf.to_csv(folder / "orders_kite_format.csv", index=False)

    save_holdings_snapshot(bundle["holdings_csv"], directory="Holding", prefix="holdings_api")
    save_orders_snapshot(bundle["orders_csv"], directory="Holding", prefix="orders_api")

    _write_summary_excel(snap, bundle)
    return snap


def _write_summary_excel(folder: Path, bundle: dict[str, Any]) -> None:
    path = folder / "zerodha_full_export.xlsx"
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, key in (
                ("Profile", None),
                ("Holdings", "holdings_csv"),
                ("Orders", "orders_csv"),
                ("Trades", "trades"),
                ("MF Holdings", "mf_holdings"),
                ("MF Orders", "mf_orders"),
                ("GTTS", "gtts"),
            ):
                if key is None:
                    prof = bundle.get("profile")
                    if prof:
                        pd.DataFrame([prof]).to_excel(writer, sheet_name=name[:31], index=False)
                    continue
                data = bundle.get(key)
                if isinstance(data, pd.DataFrame) and not data.empty:
                    data.to_excel(writer, sheet_name=name[:31], index=False)
                elif isinstance(data, list) and data:
                    pd.DataFrame(data).to_excel(writer, sheet_name=name[:31], index=False)

            pos = bundle.get("positions") or {}
            for leg in ("day", "net"):
                rows = pos.get(leg)
                if rows:
                    pd.DataFrame(rows).to_excel(writer, sheet_name=f"Pos_{leg}"[:31], index=False)

            margins = bundle.get("margins_equity") or bundle.get("margins")
            if isinstance(margins, dict):
                flat = {k: v for k, v in margins.items() if not isinstance(v, dict)}
                if flat:
                    pd.DataFrame([flat]).to_excel(writer, sheet_name="Margins", index=False)
    except Exception as exc:
        logger.warning("Excel export skipped: %s", exc)
