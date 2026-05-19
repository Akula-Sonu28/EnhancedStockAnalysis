"""Indian Equity Delivery cost model (Zerodha-equivalent).

Sources:
    https://zerodha.com/charges/  (Equity Delivery row, as of 2026 schedule)

All numbers are point-in-time defaults; pass an explicit `CostConfig` to
override (e.g. test against a Groww/Upstox invoice).

Formulas (per leg, BUY or SELL):
    brokerage         = 0 for delivery (Zerodha Equity Delivery is free)
    stt               = 0.001  * turnover  (BUY + SELL legs, delivery)
    exchange_txn      = 0.0000297 * turnover  (NSE; BSE differs)
    sebi              = 10 / 1e7 * turnover  ( = ₹10 per crore)
    stamp_duty_buy    = 0.00015 * turnover   (BUY leg only; max ₹1500/contract)
    gst               = 0.18 * (brokerage + exchange_txn + sebi)
    ipft              = 0.0000010 * turnover (NSE investor protection; tiny)

    total_cost_leg = brokerage + stt + exchange_txn + sebi + stamp_duty
                     + gst + ipft

Capital gains (settled on EXIT only, paid annually but accrued here):
    STCG (holding < 365 days):     20% on realized gain (Budget 2024, effective 2024-07-23)
    LTCG (holding >= 365 days):    10% on realized gain ABOVE ₹1L per FY
                                   (we apply 10% from rupee 1; the ₹1L
                                   exemption is consumed by the portfolio's
                                   own running total. See `apply_ltcg_fy`.)

The model is intentionally a closed-form function; no global state. The
portfolio module accumulates LTCG-eligible gains separately so the
₹1L/FY exemption can be applied at year-end (FY = Apr 1 - Mar 31).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# --- Default schedule (Zerodha Equity Delivery, NSE, 2026) ----------------

@dataclass(frozen=True)
class CostConfig:
    brokerage_per_leg: float = 0.0           # delivery is free at Zerodha
    stt_pct: float = 0.001                    # 0.1% buy + sell legs
    exchange_txn_pct: float = 0.0000297       # NSE
    sebi_per_crore: float = 10.0              # ₹10/crore
    stamp_duty_buy_pct: float = 0.00015       # buy leg only
    stamp_duty_cap_per_contract: float = 1500.0
    gst_rate: float = 0.18                    # 18% on (brokerage+exchange+SEBI)
    ipft_pct: float = 0.0000010               # tiny investor protection fund

    stcg_rate: float = 0.20                   # < 365 days (Budget 2024, effective 2024-07-23)
    ltcg_rate: float = 0.10                   # >= 365 days
    ltcg_exemption_per_fy: float = 100_000.0  # ₹1L/FY


DEFAULT_COST = CostConfig()


# --- Slippage --------------------------------------------------------------

@dataclass(frozen=True)
class SlippageConfig:
    """Slippage as % of fill price, applied unfavourably (buy paid more, sell received less).

    Defaults by cap tier (rupees crore):
        > 50,000     (large/mega):     10 bps
        10,000-50,000 (mid):           20 bps
        2,000-10,000  (small):         30 bps
        < 2,000       (micro):         50 bps

    A backtest run with `slippage_bps=0` produces the *gross* number; the
    default produces the *net* number you'd actually expect to realize.
    """
    bps_large: float = 10.0
    bps_mid: float = 20.0
    bps_small: float = 30.0
    bps_micro: float = 50.0

    def bps_for_market_cap(self, market_cap_crores: float | None) -> float:
        if market_cap_crores is None or market_cap_crores <= 0:
            return self.bps_mid
        if market_cap_crores >= 50_000:
            return self.bps_large
        if market_cap_crores >= 10_000:
            return self.bps_mid
        if market_cap_crores >= 2_000:
            return self.bps_small
        return self.bps_micro


DEFAULT_SLIPPAGE = SlippageConfig()


# --- Charges per leg -------------------------------------------------------

def charges_for_leg(turnover: float, side: str,
                    cfg: CostConfig = DEFAULT_COST) -> dict:
    """Compute total charges for a single BUY or SELL leg.

    Args:
        turnover: quantity * fill_price (rupees, positive)
        side: 'BUY' or 'SELL'
        cfg: CostConfig schedule

    Returns:
        dict with line items and 'total'. All values in rupees.
    """
    if turnover <= 0:
        return {'brokerage': 0.0, 'stt': 0.0, 'exchange': 0.0, 'sebi': 0.0,
                'stamp_duty': 0.0, 'gst': 0.0, 'ipft': 0.0, 'total': 0.0}

    side = side.upper()
    if side not in ('BUY', 'SELL'):
        raise ValueError(f'side must be BUY or SELL, got {side!r}')

    brokerage = cfg.brokerage_per_leg
    stt = cfg.stt_pct * turnover
    exchange = cfg.exchange_txn_pct * turnover
    sebi = cfg.sebi_per_crore / 1e7 * turnover
    if side == 'BUY':
        stamp_duty = min(cfg.stamp_duty_buy_pct * turnover,
                         cfg.stamp_duty_cap_per_contract)
    else:
        stamp_duty = 0.0
    gst = cfg.gst_rate * (brokerage + exchange + sebi)
    ipft = cfg.ipft_pct * turnover

    total = brokerage + stt + exchange + sebi + stamp_duty + gst + ipft

    return {
        'brokerage':  round(brokerage,  4),
        'stt':        round(stt,        4),
        'exchange':   round(exchange,   4),
        'sebi':       round(sebi,       4),
        'stamp_duty': round(stamp_duty, 4),
        'gst':        round(gst,        4),
        'ipft':       round(ipft,       4),
        'total':      round(total,      4),
    }


def apply_slippage(price: float, side: str, slippage_bps: float) -> float:
    """Return slippage-adjusted fill price. BUY pays higher, SELL receives lower."""
    if price <= 0:
        return price
    side = side.upper()
    bps_frac = slippage_bps / 10_000.0
    if side == 'BUY':
        return price * (1 + bps_frac)
    if side == 'SELL':
        return price * (1 - bps_frac)
    raise ValueError(f'side must be BUY or SELL, got {side!r}')


# --- Capital gains ---------------------------------------------------------

def is_long_term(entry_date: date, exit_date: date) -> bool:
    """Indian equity LTCG: >= 12 months (365 days) holding."""
    return (exit_date - entry_date).days >= 365


def realized_gain(entry_price: float, exit_price: float, qty: int) -> float:
    """Realized gain in rupees (positive = profit, negative = loss)."""
    return (exit_price - entry_price) * qty


def stcg_on(gain: float, cfg: CostConfig = DEFAULT_COST) -> float:
    """STCG: 20% on realized short-term gain; 0 on loss (post-Budget-2024)."""
    return cfg.stcg_rate * gain if gain > 0 else 0.0


def ltcg_on(gain: float, fy_running_ltcg: float,
            cfg: CostConfig = DEFAULT_COST) -> tuple[float, float]:
    """LTCG: 10% above ₹1L exemption per FY.

    Args:
        gain: this trade's realized long-term gain (₹). Loss → no tax.
        fy_running_ltcg: cumulative LTCG already realized this FY (₹).

    Returns:
        (tax_this_trade, new_fy_running_ltcg)
    """
    if gain <= 0:
        return 0.0, fy_running_ltcg
    new_total = fy_running_ltcg + gain
    taxable = max(0.0, new_total - cfg.ltcg_exemption_per_fy)
    prev_taxable = max(0.0, fy_running_ltcg - cfg.ltcg_exemption_per_fy)
    tax = cfg.ltcg_rate * (taxable - prev_taxable)
    return round(tax, 4), new_total


def indian_fy_of(d: date) -> tuple[date, date]:
    """Indian FY containing date `d`: Apr 1 - Mar 31."""
    if d.month >= 4:
        start = date(d.year, 4, 1)
        end = date(d.year + 1, 3, 31)
    else:
        start = date(d.year - 1, 4, 1)
        end = date(d.year, 3, 31)
    return start, end
