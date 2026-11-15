# -*- coding: utf-8 -*-
"""Vietnamese market data for the fetcher manager, over pluggable provider adapters.

``VN_DATA_PROVIDERS`` lists provider names in priority order (default ``yfinance``);
each request falls back to the next provider when one fails or has no data.
New providers register their adapter class in ``PROVIDERS`` (see ``base.py``).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from data_provider.base import BaseFetcher, DataFetchError
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote
from src.vn.instruments import CodeKind, Instrument, MARKET, classify, exchange_rejection

from .base import VnMarketDataProvider, VnQuote
from .yahoo import YahooProvider

logger = logging.getLogger(__name__)

# Provider name (as written in VN_DATA_PROVIDERS) -> adapter class.
PROVIDERS: Dict[str, Callable[[Any], VnMarketDataProvider]] = {
    YahooProvider.name: YahooProvider,
}
DEFAULT_PROVIDERS = [YahooProvider.name]


def build_providers(config: Any) -> List[VnMarketDataProvider]:
    """Instantiate the configured providers in order; unknown names are logged and skipped."""
    providers: List[VnMarketDataProvider] = []
    for name in getattr(config, "vn_data_providers", None) or DEFAULT_PROVIDERS:
        factory = PROVIDERS.get(name)
        if factory is None:
            logger.warning("[VN] unknown VN_DATA_PROVIDERS entry %r (supported: %s)", name, ", ".join(PROVIDERS))
            continue
        providers.append(factory(config))
    return providers


class VnMarketFetcher(BaseFetcher):
    """Daily bars, latest session and Exchange lookup for HOSE/HNX/UPCoM codes."""

    name = "VnMarketFetcher"
    # Only serves Vietnamese codes, through the manager's VN route; never part of other markets' chains.
    priority = 90
    market = MARKET

    def __init__(self, providers: List[VnMarketDataProvider]) -> None:
        self.providers = list(providers)
        self._instrument_cache: Dict[str, Instrument] = {}

    def _first(self, call: str, *args: Any) -> Any:
        """First non-empty answer to ``call``; a provider that raises or has nothing passes to the next."""
        errors = []
        for provider in self.providers:
            try:
                answer = getattr(provider, call)(*args)
            except Exception as exc:  # fall back to the next provider
                errors.append(f"{provider.name}: {exc}")
                logger.info("[VN] %s %s failed, trying next provider: %s", provider.name, call, exc)
                continue
            if answer is None or (isinstance(answer, pd.DataFrame) and answer.empty):
                errors.append(f"{provider.name}: no data")
                continue
            return answer
        reasons = "; ".join(errors) or "no Vietnamese data provider configured"
        raise DataFetchError(f"{reasons} (this phase supports HOSE Instruments only)")

    @staticmethod
    def _supported(stock_code: str):
        parsed = classify(stock_code)
        if parsed is None or not parsed.supported:
            reason = parsed.rejection_reason if parsed else "not a Vietnamese Instrument"
            raise DataFetchError(f"{stock_code}: {reason}")
        return parsed

    # ------------------------------------------------------------- daily bars
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        parsed = self._supported(stock_code)
        if parsed.kind is not CodeKind.INDEX:
            instrument = self.get_instrument(parsed.code)
            rejection = exchange_rejection(instrument.exchange if instrument else None)
            if rejection:
                raise DataFetchError(f"{parsed.code}: {rejection}")
        return self._first(
            "daily_bars", parsed.code, parsed.kind, date.fromisoformat(start_date), date.fromisoformat(end_date)
        )

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        out = df.sort_values("date").reset_index(drop=True)
        out["pct_chg"] = out["close"].pct_change() * 100
        return out

    # ------------------------------------------------------------ instruments
    def _quote(self, code: str, kind: CodeKind) -> Optional[VnQuote]:
        try:
            return self._first("quote", code, kind)
        except DataFetchError as exc:
            logger.warning("[VN] quote %s unavailable: %s", code, exc)
            return None

    def get_instrument(self, stock_code: str) -> Optional[Instrument]:
        """Resolve the Exchange of a Vietnamese code; cached per process once resolved."""
        parsed = classify(stock_code)
        if parsed is None or not parsed.supported:
            return None
        cached = self._instrument_cache.get(parsed.code)
        if cached is not None:
            return cached
        if parsed.kind is CodeKind.INDEX:
            instrument = Instrument(parsed.code, parsed.kind, parsed.index_exchange, parsed.code)
        else:
            quote = self._quote(parsed.code, parsed.kind)
            exchange = quote.exchange if quote else None
            instrument = Instrument(parsed.code, parsed.kind, exchange, (quote.name if quote else "") or parsed.code)
            if exchange is None:
                logger.warning("[VN] %s: Exchange unknown; Price Band rules will be skipped", parsed.code)
                return instrument  # don't cache an unresolved lookup
        self._instrument_cache[parsed.code] = instrument
        return instrument

    # --------------------------------------------------------------- realtime
    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        parsed = classify(stock_code)
        if parsed is None or not parsed.supported:
            return None
        quote = self._quote(parsed.code, parsed.kind)
        if quote is None:
            return None
        change_amount = change_pct = None
        if quote.price is not None and quote.reference:
            change_amount = quote.price - quote.reference
            change_pct = change_amount / quote.reference * 100
        return UnifiedRealtimeQuote(
            code=parsed.code,
            name=quote.name or parsed.code,
            source=RealtimeSource.VN_MARKET,
            market=MARKET,
            currency="VND",
            price=quote.price,
            change_pct=change_pct,
            change_amount=change_amount,
            volume=quote.volume,
            amount=quote.traded_value,
            open_price=quote.open,
            high=quote.high,
            low=quote.low,
            pre_close=quote.reference,
            quote_date=quote.trading_day.isoformat() if quote.trading_day else None,
            fetched_at=datetime.now().isoformat(timespec="seconds"),
        )
