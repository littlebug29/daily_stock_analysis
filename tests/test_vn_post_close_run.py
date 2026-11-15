# -*- coding: utf-8 -*-
"""Analysis Run seam: Owner-only Post-close Decision Report for a Vietnamese Instrument (#2).

Boundaries faked: Yahoo Finance (``yfinance.Ticker``, returning frames in the shape
observed live on 2026-11-14: ``FPT.VN`` on HOSE, prices in đồng, no data for HNX or
UPCoM codes, ``^VNINDEX.VN`` in points), the LLM (``litellm.completion``) and
Telegram (``requests.post``). Everything between them, including config and the
provider adapters, is real.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data_provider.base import DataFetcherManager
from src.vn import calendar as vn_calendar
from src.vn.instruments import CodeKind, Exchange
from src.vn.rules import tick_size

RUN_DAY = date(2026, 11, 13)


@dataclass(frozen=True)
class Listing:
    code: str
    exchange: str
    name: str
    close: float
    average: Optional[float] = None  # session VWAP in thousand đồng (UPCoM Reference Price)
    kind: CodeKind = CodeKind.STOCK


LISTINGS = {
    "FPT": Listing("FPT", "HOSE", "FPT Corporation", 120.0),
    "E1VFVN30": Listing("E1VFVN30", "HOSE", "DCVFMVN30 ETF", 25.55, kind=CodeKind.ETF),
    "VNINDEX": Listing("VNINDEX", "HOSE", "VN-Index", 1734.93, kind=CodeKind.INDEX),
}
_YAHOO_SYMBOLS = {"FPT.VN": "FPT", "E1VFVN30.VN": "E1VFVN30", "^VNINDEX.VN": "VNINDEX"}
_YAHOO_TYPES = {CodeKind.STOCK: "EQUITY", CodeKind.ETF: "ETF", CodeKind.INDEX: "INDEX"}
VOLUME = 1_500_000


# --------------------------------------------------------------------- fakes
class FakeYahooTicker:
    """``yfinance.Ticker`` for Vietnamese symbols, as Yahoo served them on 2026-11-14."""

    requested: list = []

    def __init__(self, symbol: str, *_, **__) -> None:
        self.symbol = symbol
        self.listing = LISTINGS.get(_YAHOO_SYMBOLS.get(symbol, ""))
        self.history_metadata: dict = {}

    def history(self, start=None, end=None, period=None, interval="1d", auto_adjust=True, **_):
        FakeYahooTicker.requested.append(self.symbol)
        if self.listing is None:  # e.g. SHS.VN (HNX), VEA.VN (UPCoM): Yahoo has no data
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        days = vn_calendar.trading_days_between(RUN_DAY - timedelta(days=200), RUN_DAY)
        if start is not None:
            days = [d for d in days if d >= pd.Timestamp(start).date()]
        if end is not None:
            days = [d for d in days if d < pd.Timestamp(end).date()]  # Yahoo's end is exclusive
        index_points = self.listing.kind is CodeKind.INDEX
        unit = 1 if index_points else 1000  # stocks and ETFs in đồng
        start_close = self.listing.close * 0.85
        closes = [start_close + i * (self.listing.close - start_close) / max(len(days) - 1, 1) for i in range(len(days))]
        frame = pd.DataFrame(
            {
                "Open": [c * 0.995 * unit for c in closes],
                "High": [c * 1.01 * unit for c in closes],
                "Low": [c * 0.99 * unit for c in closes],
                "Close": [c * unit for c in closes],
                "Volume": [0 if index_points else VOLUME] * len(days),
                "Dividends": 0.0,
                "Stock Splits": 0.0,
            },
            index=pd.DatetimeIndex([pd.Timestamp(d, tz="Asia/Ho_Chi_Minh") for d in days], name="Date"),
        )
        self.history_metadata = {
            "symbol": self.symbol, "currency": "VND", "exchangeName": "VSE", "fullExchangeName": "HOSE",
            "instrumentType": _YAHOO_TYPES[self.listing.kind], "longName": self.listing.name,
            "regularMarketPrice": closes[-1] * unit if closes else None,
        }
        return frame


def _llm_reply(close: float) -> str:
    """A Decision Report whose Trade Plan prices are off-tick and partly outside the band."""
    payload = {
        "stock_name": "Mã thử",
        "sentiment_score": 72,
        "trend_prediction": "Tăng",
        "operation_advice": "Mua",
        "decision_type": "buy",
        "action": "buy",
        "confidence_level": "Cao",
        "dashboard": {
            "core_conclusion": {
                "one_sentence": "Giữ xu hướng tăng, có thể mua quanh MA5.",
                "signal_type": "🟢Tín hiệu mua",
                "time_sensitivity": "Tuần này",
                "position_advice": {"no_position": "Mua thăm dò", "has_position": "Tiếp tục nắm giữ"},
            },
            "intelligence": {
                "latest_news": "Không có tin quan trọng",
                "risk_alerts": ["Thanh khoản giảm"],
                "positive_catalysts": ["Kết quả kinh doanh tích cực"],
                "earnings_outlook": "Ổn định",
                "sentiment_summary": "Tích cực",
            },
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": f"Vùng mua: {close * 0.9863:.3f} (gần MA5)",
                    # Written in đồng with a thousands separator, next to an indicator with a space.
                    "secondary_buy": f"Vùng mua phụ: {round(close * 970):,} đồng (gần MA 10)",
                    # Exit levels beyond the next Price Band: rounded, not clamped, flagged.
                    "stop_loss": f"Cắt lỗ: {close * 0.7807:.3f} (thủng MA20, -22%)",
                    "take_profit": f"Mục tiêu: {close * 1.2202:.3f} (đỉnh cũ)",
                },
                "position_strategy": {"suggested_position": "3/10", "entry_plan": "Hai lần", "risk_control": "MA20"},
                "action_checklist": ["✅ MA5 > MA10 > MA20", "⚠️ Khối lượng trung bình"],
            },
        },
        "analysis_summary": "Xu hướng tăng ổn định.",
        "key_points": "xu hướng tăng",
        "risk_warning": "Thị trường chung biến động",
        "buy_reason": "Xu hướng tăng",
        "search_performed": False,
        "data_sources": "yfinance",
    }
    return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


def _completion_for(listing: Listing):
    def completion(*_args, **_kwargs):
        message = SimpleNamespace(content=_llm_reply(listing.average or listing.close), tool_calls=None, reasoning_content=None)
        choice = SimpleNamespace(message=message, finish_reason="stop", index=0)
        usage = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
        return SimpleNamespace(choices=[choice], usage=usage, model="openai/test-model", id="test")

    return completion


# ------------------------------------------------------------------- fixtures
@pytest.fixture
def owner_env(tmp_path, monkeypatch):
    from src.config import Config
    from src.storage import DatabaseManager

    env = {
        "STOCK_LIST": "FPT",
        "REPORT_LANGUAGE": "vi",
        "REPORT_TYPE": "full",
        "GENERATION_BACKEND": "litellm",
        "LITELLM_MODEL": "openai/test-model",
        "OPENAI_API_KEY": "sk-test-not-real",
        "TELEGRAM_BOT_TOKEN": "123:test",
        "TELEGRAM_CHAT_ID": "42",
        "DATABASE_PATH": str(tmp_path / "vn.db"),
        "VN_DATA_PROVIDERS": "yfinance",
        "ENABLE_REALTIME_QUOTE": "true",
        "ENABLE_CHIP_DISTRIBUTION": "false",
        "DAILY_MARKET_CONTEXT_ENABLED": "false",
        "MARKET_REVIEW_ENABLED": "false",
        "AGENT_MODE": "false",
        "MAX_WORKERS": "1",
        "ENV_FILE": str(tmp_path / "missing.env"),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    for key in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "TAVILY_API_KEYS",
                "SERPAPI_API_KEYS", "LLM_CHANNELS", "LITELLM_CONFIG", "LITELLM_FALLBACK_MODELS",
                "GENERATION_FALLBACK_BACKEND", "AGENT_GENERATION_BACKEND"):
        monkeypatch.delenv(key, raising=False)
    Config.reset_instance()
    DatabaseManager.reset_instance()
    FakeYahooTicker.requested = []
    with patch("data_provider.vn_market.yahoo.yf.Ticker", FakeYahooTicker):
        yield
    Config.reset_instance()
    DatabaseManager.reset_instance()


def _run_post_close(code: str = "FPT"):
    import src.analyzer as analyzer_module
    from src.core.pipeline import StockAnalysisPipeline

    telegram = MagicMock()
    telegram.return_value = MagicMock(status_code=200, json=lambda: {"ok": True}, text="{}")
    with patch.object(analyzer_module.litellm, "completion", side_effect=_completion_for(LISTINGS[code])), \
         patch("src.notification_sender.telegram_sender.requests.post", telegram):
        results = StockAnalysisPipeline().run(
            stock_codes=[code], send_notification=True, current_time=datetime(2026, 11, 13, 16, 0)
        )
    messages = [call.kwargs.get("json", {}).get("text", "") for call in telegram.call_args_list]
    return results, messages


def _prices(text: str) -> list[Decimal]:
    """Prices in a Trade Plan line (numbers not glued to an indicator or a % sign)."""
    return [Decimal(n) for n in re.findall(r"(?<![A-Za-z0-9+.,])\d+(?:\.\d+)?(?![\d%])", text)
            if not re.search(r"MA\s*$", text[: text.index(n)])]


# ---------------------------------------------------------------------- tests
def test_post_close_run_delivers_vietnamese_decision_report_to_telegram(owner_env):
    results, messages = _run_post_close("FPT")

    assert len(results) == 1 and results[0].success, results
    assert "FPT.VN" in FakeYahooTicker.requested
    assert messages, "Decision Report was not pushed to Telegram"
    report = "\n".join(messages)
    stock_line = next(line for line in report.splitlines() if "(FPT" in line and "Điểm" in line)
    assert re.search(r": (Mua|Theo dõi|Bán) \|", stock_line), stock_line  # Signal vocabulary
    assert "Kế hoạch giao dịch" in report and "Cắt lỗ" in report  # Vietnamese Trade Plan labels
    assert "Biên độ phiên kế tiếp: 111.6 – 128.4" in report  # next-session Price Band shown
    assert "T+2" in report  # Settlement Lag noted
    assert "đồng" not in report.split("Vùng mua phụ")[1].split("\n")[0]  # đồng price rewritten in thousands
    assert "万股" not in report and "元" not in report  # no Chinese units


@pytest.mark.parametrize(
    "code, exchange, reference, floor, ceiling",
    [
        ("FPT", Exchange.HOSE, "120", "111.6", "128.4"),  # Yahoo's 120,000 đồng read as 120 thousand
        ("E1VFVN30", Exchange.HOSE, "25.55", "23.77", "27.33"),  # ETF tick 0.01
    ],
)
def test_trade_plan_follows_exchange_rules(owner_env, code, exchange, reference, floor, ceiling):
    results, _ = _run_post_close(code)
    assert results and results[0].success, results
    battle_plan = results[0].dashboard["battle_plan"]
    rules = battle_plan["vn_trade_rules"]
    assert (rules["exchange"], rules["reference_price"], rules["floor_price"], rules["ceiling_price"]) == (
        exchange.value, reference, floor, ceiling,
    )
    kind = LISTINGS[code].kind
    lo, hi = Decimal(floor), Decimal(ceiling)
    sniper = battle_plan["sniper_points"]

    for field in ("ideal_buy", "secondary_buy"):  # next-session orders: on tick, inside the band
        prices = _prices(sniper[field])
        assert prices, (field, sniper[field])
        for price in prices:
            assert lo <= price <= hi, (field, price)
            assert price % tick_size(exchange, price, kind) == 0, (field, price)
    assert "MA 10" in sniper["secondary_buy"]  # indicator number left alone

    for field in ("stop_loss", "take_profit"):  # exits: on tick, not clamped, flagged
        price = _prices(sniper[field])[0]
        assert not lo <= price <= hi, (field, price)
        assert price % tick_size(exchange, price, kind) == 0, (field, price)
        assert "ngoài biên độ phiên kế tiếp" in sniper[field]
    assert "T+2" in rules["settlement_note"]


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 1, 2), []),   # Tết Dương lịch (swapped day)
        (date(2026, 2, 17), []),  # Tết Nguyên đán
        (date(2026, 4, 27), []),  # Giỗ Tổ Hùng Vương (observed)
        (date(2026, 4, 30), []),
        (date(2026, 5, 1), []),
        (date(2026, 9, 2), []),   # Quốc khánh
        (date(2026, 11, 14), []),  # Saturday
        (date(2026, 11, 13), ["FPT"]),
    ],
)
def test_trading_day_check_skips_vietnamese_holidays(owner_env, today, expected):
    import main

    args = SimpleNamespace(force_run=False, no_market_review=True)
    config = SimpleNamespace(trading_day_check_enabled=True, market_review_enabled=False)
    with patch("src.vn.calendar.today", return_value=today):
        codes, _, skip_all = main._compute_trading_day_filter(config, args, ["FPT"])
    assert codes == expected
    assert skip_all == (expected == [])


def test_force_run_ignores_trading_day_check(owner_env):
    import main

    args = SimpleNamespace(force_run=True)
    config = SimpleNamespace(trading_day_check_enabled=True, market_review_enabled=False)
    with patch("src.vn.calendar.today", return_value=date(2026, 2, 17)):
        codes, _, _ = main._compute_trading_day_filter(config, args, ["FPT"])
    assert codes == ["FPT"]


@pytest.mark.parametrize("code", ["CFPT2501", "VN30F2412", "VN30F1M"])
def test_covered_warrants_and_futures_are_rejected_with_a_reason(code):
    from src.services.stock_list_parser import ParseStatus, parse_analysis_target

    target = parse_analysis_target(code)
    assert target.asset_type == ParseStatus.UNSUPPORTED
    assert target.market == "vn"
    assert "chưa được hỗ trợ" in target.unsupported_reason


def test_yfinance_is_the_default_provider(owner_env, monkeypatch):
    from src.config import Config

    monkeypatch.delenv("VN_DATA_PROVIDERS")
    Config.reset_instance()
    df, source = DataFetcherManager().get_daily_data("FPT", days=30)
    assert source == "VnMarketFetcher" and not df.empty
    assert df["close"].iloc[-1] == pytest.approx(120.0)  # thousand đồng


def test_index_levels_stay_in_points(owner_env):
    df, _ = DataFetcherManager().get_daily_data("VNINDEX", days=30)
    assert "^VNINDEX.VN" in FakeYahooTicker.requested
    assert df["close"].iloc[-1] == pytest.approx(1734.93)


@pytest.mark.parametrize("code", ["SHS", "VEA"])  # HNX, UPCoM: Yahoo has no data for them
def test_codes_no_provider_covers_fail_with_a_clear_reason(owner_env, code):
    from data_provider.base import DataFetchError

    with pytest.raises(DataFetchError, match=r"yfinance: .*no data.*HOSE"):
        DataFetcherManager().get_daily_data(code, days=30)


@pytest.mark.parametrize("code", ["HNXINDEX", "HNX30", "UPCOMINDEX"])
def test_hnx_and_upcom_indices_are_rejected_in_this_phase(code):
    from src.services.stock_list_parser import ParseStatus, parse_analysis_target

    target = parse_analysis_target(code)
    assert target.asset_type == ParseStatus.UNSUPPORTED
    assert "HOSE" in target.unsupported_reason


class _StubProvider:
    """A provider adapter returning fixed answers, to exercise the adapter contract."""

    name = "stub"
    bars: Optional[pd.DataFrame] = None
    quote_value = None

    def __init__(self, config):
        pass

    def daily_bars(self, code, kind, start, end):
        return type(self).bars

    def quote(self, code, kind):
        return type(self).quote_value


def _use_stub(monkeypatch, order: str, bars=None, quote=None):
    from data_provider.vn_market.fetcher import PROVIDERS
    from src.config import Config

    stub = type("Stub", (_StubProvider,), {"bars": bars, "quote_value": quote})
    monkeypatch.setitem(PROVIDERS, "stub", stub)
    monkeypatch.setenv("VN_DATA_PROVIDERS", order)
    Config.reset_instance()


def test_empty_answers_fall_through_to_the_next_provider(owner_env, monkeypatch):
    _use_stub(monkeypatch, "stub,yfinance", bars=pd.DataFrame(columns=["date", "close"]), quote=None)
    manager = DataFetcherManager()

    df, _ = manager.get_daily_data("FPT", days=30)
    assert not df.empty and "FPT.VN" in FakeYahooTicker.requested
    assert manager.get_vn_instrument("FPT").exchange is Exchange.HOSE  # stub's None quote fell through


def test_instruments_outside_hose_are_rejected_in_this_phase(owner_env, monkeypatch):
    from data_provider.base import DataFetchError
    from data_provider.vn_market.base import VnQuote

    bars = pd.DataFrame({"date": pd.to_datetime(["2026-11-13"]), "open": [25.0], "high": [25.5],
                         "low": [24.8], "close": [25.3], "volume": [1000], "amount": [float("nan")]})
    _use_stub(monkeypatch, "stub", bars=bars, quote=VnQuote(code="SHS", exchange=Exchange.HNX, price=25.3))

    with pytest.raises(DataFetchError, match=r"HNX.*HOSE"):
        DataFetcherManager().get_daily_data("SHS", days=30)


@pytest.mark.parametrize("code", ["IBM", "AMD"])
def test_three_character_us_symbols_are_looked_up_as_vietnamese(owner_env, code):
    # ADR-0001: a 3-character code is a Vietnamese Instrument, never routed to US sources.
    from data_provider.base import DataFetchError

    with pytest.raises(DataFetchError, match=r"HOSE"):
        DataFetcherManager().get_daily_data(code, days=30)
    assert f"{code}.VN" in FakeYahooTicker.requested
    assert code not in FakeYahooTicker.requested


def test_yahoo_listing_without_exchange_name_is_hose(owner_env, monkeypatch):
    original = FakeYahooTicker.history

    def history_without_exchange(self, *args, **kwargs):
        frame = original(self, *args, **kwargs)
        self.history_metadata.pop("fullExchangeName", None)
        return frame

    monkeypatch.setattr(FakeYahooTicker, "history", history_without_exchange)
    assert DataFetcherManager().get_vn_instrument("FPT").exchange is Exchange.HOSE  # Yahoo only carries HOSE


def test_report_says_when_trade_plan_rules_could_not_be_applied(owner_env, monkeypatch):
    from data_provider.vn_market.base import VnQuote

    bars = FakeYahooTicker("FPT.VN").history()
    frame = pd.DataFrame({"date": bars.index.tz_localize(None), "open": bars["Open"] / 1000,
                          "high": bars["High"] / 1000, "low": bars["Low"] / 1000, "close": bars["Close"] / 1000,
                          "volume": bars["Volume"], "amount": float("nan")}).reset_index(drop=True)
    _use_stub(monkeypatch, "stub", bars=frame, quote=VnQuote(code="FPT", exchange=None, price=120.0))

    results, messages = _run_post_close("FPT")
    assert results and results[0].success
    assert "vn_trade_rules" not in results[0].dashboard["battle_plan"]
    assert "chưa áp dụng quy tắc biên độ" in "\n".join(messages).lower()  # the skip is visible in the report


def test_upcom_reference_ignores_missing_traded_value():
    from src.vn.rules import next_reference_price

    assert next_reference_price(Exchange.UPCOM, 21.0, float("nan"), VOLUME) == Decimal("21.0")


def test_trade_plan_leaves_non_price_numbers_alone():
    from src.vn import trade_plan
    from src.vn.instruments import Instrument

    result = SimpleNamespace(dashboard={"battle_plan": {"sniper_points": {
        "ideal_buy": "Vùng mua: 118.33 sau 200 phiên tích lũy, ngày 13/11",
        "stop_loss": "Cắt lỗ: 100 trong 100 ngày",
    }}})
    trade_plan.apply(result, Instrument("FPT", CodeKind.STOCK, Exchange.HOSE), 120, language="vi")
    sniper = result.dashboard["battle_plan"]["sniper_points"]
    assert sniper["ideal_buy"].startswith("Vùng mua: 118.3 sau 200 phiên") and "13/11" in sniper["ideal_buy"]
    assert "100 ngày" in sniper["stop_loss"]


def test_providers_are_tried_in_configured_order(owner_env, monkeypatch):
    from data_provider.vn_market.fetcher import PROVIDERS
    from src.config import Config

    class OfflineProvider:
        name = "offline"

        def __init__(self, config):
            pass

        def daily_bars(self, code, kind, start, end):
            raise ConnectionError("offline")

        def quote(self, code, kind):
            raise ConnectionError("offline")

    monkeypatch.setitem(PROVIDERS, "offline", OfflineProvider)
    monkeypatch.setenv("VN_DATA_PROVIDERS", "offline,unknown,yfinance")
    Config.reset_instance()

    df, _ = DataFetcherManager().get_daily_data("FPT", days=30)
    assert not df.empty  # fell back past the failing and the unknown provider to yfinance
