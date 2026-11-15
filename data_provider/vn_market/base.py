# -*- coding: utf-8 -*-
"""Contract every Vietnamese market-data provider adapter implements.

An adapter wraps one source (Yahoo Finance today; broker Open APIs such as TCBS,
SSI or DNSE later) and returns data in this project's units: prices in thousand
đồng (Index levels in points), volumes in shares, Traded Value in đồng.

To add a provider: implement this protocol in a new module, register its class
in ``fetcher.PROVIDERS`` under a short name, and list that name in
``VN_DATA_PROVIDERS``. Providers are tried in that order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional, Protocol

import pandas as pd

from src.vn.instruments import CodeKind, Exchange

# Columns of ``daily_bars``; ``amount`` is Traded Value in đồng (NaN when the source omits it).
BAR_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]


@dataclass(frozen=True)
class VnQuote:
    """Latest session figures for one Instrument, in thousand đồng."""

    code: str
    exchange: Optional[Exchange]
    price: Optional[float] = None
    reference: Optional[float] = None  # Reference Price of the latest Trading Day
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    traded_value: Optional[float] = None  # đồng
    name: str = ""
    trading_day: Optional[date] = None


class VnMarketDataProvider(Protocol):
    name: str

    def __init__(self, config: Any) -> None:
        """Adapters are built from the app Config (credentials, options)."""

    def daily_bars(self, code: str, kind: CodeKind, start: date, end: date) -> pd.DataFrame:
        """Daily bars in ``BAR_COLUMNS``, oldest first, for ``start``..``end`` inclusive.

        Raise when the source has no data for the code, so the next provider is tried.
        """

    def quote(self, code: str, kind: CodeKind) -> Optional[VnQuote]:
        """Latest session figures (including the Exchange), or None when the source has none."""
