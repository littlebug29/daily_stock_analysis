# -*- coding: utf-8 -*-
"""Make a Decision Report's Trade Plan placeable on a Vietnamese Exchange.

The LLM writes the Trade Plan (upstream ``dashboard.battle_plan.sniper_points``)
as free text with prices in it. After generation:

- every price is rounded to the Exchange Tick Size;
- entry prices (buy zones), which are orders for the next session, are kept
  inside the next session's Price Band;
- exit levels (stop-loss, target) can be reached over several sessions, so they
  are only rounded, and flagged when they lie outside the next Price Band;
- the Settlement Lag is noted, so a stop-loss isn't read as executable on the buy day.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from src.vn.instruments import CodeKind, Exchange, Instrument
from src.vn.rules import SETTLEMENT_LAG_TRADING_DAYS, PriceBand, price_band, round_to_tick

ENTRY_FIELDS = ("ideal_buy", "secondary_buy")
EXIT_FIELDS = ("stop_loss", "take_profit")

# A number that is not part of an indicator name (MA20, RSI14, T+2), a date (13/11) or a
# percentage, and not a count of time (120 phiên, 100 ngày); optionally followed by a đồng
# unit word that must be dropped once written in thousands.
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9+.,/])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?![\d%/])(?!\s*%)"
    r"(?!\s*(?:phiên|ngày|tuần|tháng|năm|sessions?|days?|weeks?|months?|years?)\b)"
    r"(\s*(?:nghìn đồng|ngàn đồng|đồng|vnđ|vnd|đ)\b)?",
    re.IGNORECASE,
)
# "MA 10", "RSI 14", "EMA 20", "T+ 2": the number belongs to the indicator, not a price.
_INDICATOR_BEFORE_RE = re.compile(r"(?:\b(?:MA|EMA|SMA|RSI|MACD|KDJ|BOLL)|T\+)\s*$", re.IGNORECASE)
# How far from the Reference Price a number may be and still be read as a price.
_PRICE_RATIO_MIN = Decimal("0.25")
_PRICE_RATIO_MAX = Decimal("4")

_TEXT = {
    "vi": {
        "settlement": f"Lưu ý: cổ phiếu mua hôm nay chỉ bán được sau T+{SETTLEMENT_LAG_TRADING_DAYS}; "
                      "cắt lỗ chỉ thực hiện được từ ngày đó.",
        "outside_band": "ngoài biên độ phiên kế tiếp",
        "not_applied": "Chưa áp dụng quy tắc biên độ và bước giá cho kế hoạch giao dịch "
                       "(không xác định được sàn hoặc giá tham chiếu); kiểm tra lại giá trước khi đặt lệnh.",
    },
    "en": {
        "settlement": f"Note: shares bought today can only be sold after T+{SETTLEMENT_LAG_TRADING_DAYS}; "
                      "the stop-loss can only be executed from then.",
        "outside_band": "outside the next session's Price Band",
        "not_applied": "Price Band and Tick Size rules were not applied to this Trade Plan "
                       "(Exchange or Reference Price unknown); check prices before placing orders.",
    },
}


def _text(language: str) -> Dict[str, str]:
    return _TEXT.get(language, _TEXT["en"])


def _parse_number(raw: str) -> Optional[Decimal]:
    text = raw
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", text):
        text = re.sub(r"[.,]", "", text)  # thousands separators: 120.500 / 120,500 đồng
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _as_thousand_dong(value: Decimal, reference: Decimal) -> Optional[Decimal]:
    """Read ``value`` as a price near ``reference``, written in thousand đồng or in đồng."""
    for candidate in (value, value / 1000):
        if _PRICE_RATIO_MIN <= candidate / reference <= _PRICE_RATIO_MAX:
            return candidate
    return None


def _format(price: Decimal) -> str:
    return format(price.normalize(), "f")


def _rewrite(text: str, instrument: Instrument, band: PriceBand, clamp: bool, language: str) -> str:
    outside = False

    def replace(match: re.Match[str]) -> str:
        nonlocal outside
        if _INDICATOR_BEFORE_RE.search(match.string[: match.start()]):
            return match.group(0)
        value = _parse_number(match.group(1))
        price = _as_thousand_dong(value, band.reference) if value is not None else None
        if price is None:
            return match.group(0)
        rounded = round_to_tick(instrument.exchange, price, instrument.kind)
        if clamp:
            rounded = band.clamp(rounded)
        elif not band.floor <= rounded <= band.ceiling:
            outside = True
        unit = match.group(2) or ""
        keep_unit = "nghìn" in unit.lower() or "ngàn" in unit.lower()
        return _format(rounded) + (unit if keep_unit else "")

    rewritten = _NUMBER_RE.sub(replace, text)
    if outside:
        rewritten = f"{rewritten} ({_text(language)['outside_band']})"
    return rewritten


def apply(result: Any, instrument: Instrument, reference_price: Any, language: str = "vi") -> bool:
    """Normalise ``result``'s Trade Plan in place; return whether anything was applied."""
    if instrument.kind is CodeKind.INDEX or instrument.exchange is None:
        return False
    try:
        reference = Decimal(str(reference_price))
    except (InvalidOperation, TypeError):
        return False
    if reference <= 0:
        return False

    dashboard = getattr(result, "dashboard", None)
    battle_plan = dashboard.get("battle_plan") if isinstance(dashboard, dict) else None
    sniper_points = battle_plan.get("sniper_points") if isinstance(battle_plan, dict) else None
    if not isinstance(sniper_points, dict):
        return False

    band = price_band(instrument.exchange, reference, instrument.kind)
    for field in ENTRY_FIELDS + EXIT_FIELDS:
        value = sniper_points.get(field)
        if isinstance(value, (int, float)):
            value = str(value)
        if isinstance(value, str) and value.strip():
            sniper_points[field] = _rewrite(value, instrument, band, field in ENTRY_FIELDS, language)

    battle_plan["vn_trade_rules"] = trade_rules_summary(instrument.exchange, band, language)
    return True


def trade_rules_summary(exchange: Exchange, band: PriceBand, language: str = "vi") -> Dict[str, str]:
    return {
        "exchange": exchange.value,
        "reference_price": _format(band.reference),
        "floor_price": _format(band.floor),
        "ceiling_price": _format(band.ceiling),
        "settlement_note": _text(language)["settlement"],
    }


def note_rules_not_applied(result: Any, language: str = "vi") -> None:
    """Say in the report that the Trade Plan was left as the LLM wrote it."""
    dashboard = getattr(result, "dashboard", None)
    battle_plan = dashboard.get("battle_plan") if isinstance(dashboard, dict) else None
    if isinstance(battle_plan, dict):
        battle_plan["vn_trade_rules_not_applied"] = _text(language)["not_applied"]
