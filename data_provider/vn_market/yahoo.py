# -*- coding: utf-8 -*-
"""Yahoo Finance (yfinance) adapter for Vietnamese market data.

Coverage observed on 2026-11-14: HOSE stocks and ETFs as ``<CODE>.VN`` and
VN-Index as ``^VNINDEX.VN``; no HNX or UPCoM securities and no VN30/HNX indices.
Prices come in đồng (Index levels in points), and the day's close is available
shortly after the 14:45 ICT close. No key or login is needed, but this is
Yahoo's unofficial endpoint, meant for personal use.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from data_provider.base import DataFetchError
from src.vn import calendar as vn_calendar
from src.vn.instruments import CodeKind, Exchange

from .base import BAR_COLUMNS, VnQuote

logger = logging.getLogger(__name__)

_INDEX_SYMBOLS = {"VNINDEX": "^VNINDEX.VN"}


def yahoo_symbol(code: str, kind: CodeKind) -> Optional[str]:
    """Yahoo symbol for a Vietnamese code, or None if Yahoo doesn't carry that Index."""
    if kind is CodeKind.INDEX:
        return _INDEX_SYMBOLS.get(code)
    return f"{code}.VN"


def _unit(kind: CodeKind) -> int:
    """Yahoo quotes securities in đồng (-> divide by 1000) and Index levels in points."""
    return 1 if kind is CodeKind.INDEX else 1000


class YahooProvider:
    name = "yfinance"

    def __init__(self, config: Any = None) -> None:
        """Yahoo needs no credentials or options."""

    def _history(self, code: str, kind: CodeKind, **kwargs: Any) -> tuple[pd.DataFrame, dict]:
        symbol = yahoo_symbol(code, kind)
        if symbol is None:
            raise DataFetchError(f"{code}: no data on Yahoo Finance (index not carried)")
        ticker = yf.Ticker(symbol)
        frame = ticker.history(interval="1d", auto_adjust=False, **kwargs)
        if frame is None or frame.empty:
            # yfinance returns an empty frame both for symbols Yahoo doesn't carry and when
            # Yahoo is unreachable or rate-limiting, so the reason names both.
            raise DataFetchError(
                f"{code}: no data from Yahoo Finance ({symbol}); Yahoo only carries HOSE codes and VN-Index, "
                "or Yahoo is unreachable / rate-limiting"
            )
        return frame, dict(getattr(ticker, "history_metadata", None) or {})

    def daily_bars(self, code: str, kind: CodeKind, start: date, end: date) -> pd.DataFrame:
        # Yahoo's ``end`` is exclusive.
        frame, _ = self._history(code, kind, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
        unit = _unit(kind)
        index = pd.DatetimeIndex(frame.index)
        if index.tz is not None:
            index = index.tz_convert(vn_calendar.TZ).tz_localize(None)
        bars = pd.DataFrame(
            {
                "date": index.normalize(),
                "open": frame["Open"].to_numpy() / unit,
                "high": frame["High"].to_numpy() / unit,
                "low": frame["Low"].to_numpy() / unit,
                "close": frame["Close"].to_numpy() / unit,
                "volume": frame["Volume"].to_numpy(),
                "amount": float("nan"),  # Yahoo has no Traded Value
            },
            columns=BAR_COLUMNS,
        )
        bars = bars[(bars["date"].dt.date >= start) & (bars["date"].dt.date <= end)]
        if bars.empty:
            raise DataFetchError(f"{code}: no Yahoo Finance bars between {start} and {end}")
        return bars.sort_values("date").reset_index(drop=True)

    def quote(self, code: str, kind: CodeKind) -> Optional[VnQuote]:
        """Latest session from the last daily bars (Yahoo's own quote fields lag for HOSE)."""
        frame, meta = self._history(code, kind, period="5d")
        unit = _unit(kind)
        last = frame.iloc[-1]
        previous = frame.iloc[-2] if len(frame) > 1 else None
        last_day = pd.Timestamp(frame.index[-1])
        if last_day.tzinfo is not None:
            last_day = last_day.tz_convert(vn_calendar.TZ)
        return VnQuote(
            code=code,
            # Yahoo only carries HOSE listings, so an unparseable exchange name still means HOSE.
            exchange=Exchange.parse(meta.get("fullExchangeName")) or Exchange.HOSE,
            price=float(last["Close"]) / unit,
            reference=float(previous["Close"]) / unit if previous is not None else None,
            open=float(last["Open"]) / unit,
            high=float(last["High"]) / unit,
            low=float(last["Low"]) / unit,
            volume=int(last["Volume"]) if pd.notna(last["Volume"]) else None,
            name=str(meta.get("longName") or meta.get("shortName") or ""),
            trading_day=last_day.date(),
        )
