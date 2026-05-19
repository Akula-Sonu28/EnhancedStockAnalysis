"""Order execution model.

Defaults:
    - Decision at day D close → fill at day D+1 open (T+1 fill).
    - Slippage applied unfavourably (BUY pays higher, SELL receives lower).
    - No partial fills (assume ₹1L portfolio is below capacity threshold).
    - No corporate-action handling beyond yfinance auto-adjustment.

The `Executor` is intentionally tiny: it converts (symbol, side, qty, ref_date)
plus a price lookup into a `Fill` record. Cost and slippage logic come from
`costs.py`; the executor only orchestrates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from .costs import (
    CostConfig, SlippageConfig, DEFAULT_COST, DEFAULT_SLIPPAGE,
    charges_for_leg, apply_slippage,
)


@dataclass
class Fill:
    """Single executed leg."""
    symbol: str
    side: str               # 'BUY' or 'SELL'
    decision_date: date     # When the strategy decided
    fill_date: date         # When the trade actually filled (T+1)
    raw_price: float        # Reference price BEFORE slippage
    fill_price: float       # Slippage-adjusted price
    qty: int
    turnover: float         # qty * fill_price
    charges: dict           # from charges_for_leg
    cash_delta: float       # net cash impact (negative for BUY, positive for SELL)
    slippage_bps: float     # bps actually applied
    reason: str = ''        # human-readable why


class ExecutionError(Exception):
    pass


# Type aliases
PriceLookup = Callable[[str, date], Optional[float]]
"""Function (symbol, date) -> next-day open price, or None if unavailable."""

MarketCapLookup = Callable[[str], Optional[float]]
"""Function (symbol) -> current market cap in INR crores."""


class Executor:
    """Stateless order executor."""

    def __init__(self,
                 next_day_open: PriceLookup,
                 market_cap_crores: MarketCapLookup,
                 cost_cfg: CostConfig = DEFAULT_COST,
                 slippage_cfg: SlippageConfig = DEFAULT_SLIPPAGE):
        self.next_day_open = next_day_open
        self.market_cap = market_cap_crores
        self.cost = cost_cfg
        self.slip = slippage_cfg

    def submit(self, *, symbol: str, side: str, qty: int,
               decision_date: date, fill_date: date,
               reason: str = '') -> Fill:
        """Submit a single-leg order. Raises ExecutionError if price unavailable.

        Convention: cash_delta is signed from the portfolio's perspective.
            BUY:  cash_delta = -(turnover + charges)
            SELL: cash_delta = +(turnover - charges)
        """
        if qty <= 0:
            raise ExecutionError(f'qty must be positive, got {qty}')
        side = side.upper()
        if side not in ('BUY', 'SELL'):
            raise ExecutionError(f'side must be BUY/SELL, got {side!r}')

        raw_price = self.next_day_open(symbol, decision_date)
        if raw_price is None or raw_price <= 0:
            raise ExecutionError(
                f'no next-day open price for {symbol} after {decision_date}'
            )

        mc = self.market_cap(symbol)
        bps = self.slip.bps_for_market_cap(mc)
        fill_price = apply_slippage(raw_price, side, bps)
        turnover = fill_price * qty
        ch = charges_for_leg(turnover, side, self.cost)
        if side == 'BUY':
            cash_delta = -(turnover + ch['total'])
        else:
            cash_delta = +(turnover - ch['total'])

        return Fill(
            symbol=symbol,
            side=side,
            decision_date=decision_date,
            fill_date=fill_date,
            raw_price=raw_price,
            fill_price=round(fill_price, 4),
            qty=qty,
            turnover=round(turnover, 4),
            charges=ch,
            cash_delta=round(cash_delta, 4),
            slippage_bps=bps,
            reason=reason,
        )
