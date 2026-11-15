# -*- coding: utf-8 -*-
"""Vietnamese market rules (CONTEXT.md: Price Band, Ceiling/Floor Price, Tick Size, Settlement Lag).

Prices are in thousands of đồng, the unit Vietnamese price boards display
(providers convert to it) (e.g. 120.5 = 120,500 đ).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Optional

from src.vn.instruments import CodeKind, Exchange

PRICE_BAND_PCT = {
    Exchange.HOSE: Decimal("0.07"),
    Exchange.HNX: Decimal("0.10"),
    Exchange.UPCOM: Decimal("0.15"),
}

# Shares bought on Trading Day T become sellable on T+2 (afternoon session).
SETTLEMENT_LAG_TRADING_DAYS = 2


def _d(value: float | Decimal | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def tick_size(exchange: Exchange, price: float | Decimal, kind: CodeKind = CodeKind.STOCK) -> Decimal:
    """Smallest price step, in thousand đồng, at ``price``."""
    p = _d(price)
    if exchange is Exchange.HOSE:
        if kind is CodeKind.ETF:
            return Decimal("0.01")
        if p < 10:
            return Decimal("0.01")
        if p < 50:
            return Decimal("0.05")
        return Decimal("0.1")
    if kind is CodeKind.ETF:
        return Decimal("0.001")
    return Decimal("0.1")


def _to_tick(exchange: Exchange, price: Decimal, kind: CodeKind, rounding: str) -> Decimal:
    step = tick_size(exchange, price, kind)
    rounded = (price / step).quantize(Decimal("1"), rounding=rounding) * step
    # A HOSE price can cross a tick boundary when rounded; re-check with the new level.
    step_after = tick_size(exchange, rounded, kind)
    if step_after != step:
        rounded = (price / step_after).quantize(Decimal("1"), rounding=rounding) * step_after
    return rounded.normalize() if rounded != 0 else Decimal("0")


def round_to_tick(exchange: Exchange, price: float | Decimal, kind: CodeKind = CodeKind.STOCK) -> Decimal:
    return _to_tick(exchange, _d(price), kind, ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceBand:
    reference: Decimal
    floor: Decimal
    ceiling: Decimal

    def clamp(self, price: Decimal) -> Decimal:
        return min(max(price, self.floor), self.ceiling)


def price_band(exchange: Exchange, reference: float | Decimal, kind: CodeKind = CodeKind.STOCK) -> PriceBand:
    """Floor and Ceiling for a session whose Reference Price is ``reference``."""
    ref = _d(reference)
    pct = PRICE_BAND_PCT[exchange]
    ceiling = _to_tick(exchange, ref * (1 + pct), kind, ROUND_FLOOR)
    floor = _to_tick(exchange, ref * (1 - pct), kind, ROUND_CEILING)
    return PriceBand(reference=ref, floor=floor, ceiling=ceiling)


def _present(value: object) -> bool:
    """A usable number: not None, not NaN, not zero."""
    try:
        number = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return False
    return number.is_finite() and number != 0


def next_reference_price(
    exchange: Exchange,
    close: float | Decimal | None,
    traded_value_dong: float | Decimal | None = None,
    volume: float | Decimal | None = None,
    kind: CodeKind = CodeKind.STOCK,
) -> Optional[Decimal]:
    """Reference Price of the next session from today's final data.

    HOSE/HNX use today's close. UPCoM uses today's volume-weighted average price
    (Traded Value / volume), falling back to the close when either is missing.
    """
    if exchange is Exchange.UPCOM and _present(traded_value_dong) and _present(volume):
        average = _d(traded_value_dong) / _d(volume) / 1000  # đồng -> thousand đồng
        if average > 0:
            return round_to_tick(exchange, average, kind)
    if close is None:
        return None
    reference = _d(close)
    return reference if reference > 0 else None
