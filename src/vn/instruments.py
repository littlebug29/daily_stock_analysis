# -*- coding: utf-8 -*-
"""Vietnamese Instrument and Index codes (CONTEXT.md: Instrument, Index, Exchange).

Only common stocks, ETFs and the main Indices are in scope. Covered warrants and
futures are recognised so they can be rejected with a clear reason instead of
being mistaken for another market's code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

MARKET = "vn"


class Exchange(str, Enum):
    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"

    @classmethod
    def parse(cls, value: object) -> Optional["Exchange"]:
        text = str(value or "").strip().upper().replace("-", "").replace(" ", "")
        aliases = {"HOSE": cls.HOSE, "HSX": cls.HOSE, "HCM": cls.HOSE, "HNX": cls.HNX,
                   "HASTC": cls.HNX, "UPCOM": cls.UPCOM, "UPCOMINDEX": cls.UPCOM}
        return aliases.get(text)


class CodeKind(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    COVERED_WARRANT = "covered_warrant"
    FUTURES = "futures"


# Canonical index code -> (exchange it belongs to, accepted aliases)
_INDICES = {
    "VNINDEX": (Exchange.HOSE, ("VNINDEX", "VN-INDEX", "VNI")),
    "VN30": (Exchange.HOSE, ("VN30", "VN30INDEX", "VN30-INDEX")),
    "VN100": (Exchange.HOSE, ("VN100",)),
    "HNXINDEX": (Exchange.HNX, ("HNXINDEX", "HNX-INDEX", "HNX")),
    "HNX30": (Exchange.HNX, ("HNX30",)),
    "UPCOMINDEX": (Exchange.UPCOM, ("UPCOMINDEX", "UPCOM-INDEX", "UPCOM")),
}
_INDEX_ALIASES = {alias: code for code, (_, aliases) in _INDICES.items() for alias in aliases}

_STOCK_RE = re.compile(r"^(?=[A-Z0-9]*[A-Z])[A-Z0-9]{3}$")
_ETF_RE = re.compile(r"^(E1V|FUE)[A-Z0-9]{5}$")
_COVERED_WARRANT_RE = re.compile(r"^C(?!SI)[A-Z][A-Z0-9]{2}\d{4}$")  # CSI... is a China index family
_FUTURES_RE = re.compile(r"^(VN30F(\d{4}|[12][MQ])|VN100F\d{4}|41I1[A-Z0-9]{2,6}|GB(05|10)F\d{4})$")

# Exchanges served in the current phase; HNX and UPCoM come in later phases.
SUPPORTED_EXCHANGES = frozenset({Exchange.HOSE})


def exchange_rejection(exchange: Optional[Exchange]) -> Optional[str]:
    """Why an Instrument on ``exchange`` can't be analysed yet, or None if it can (or is unknown)."""
    if exchange is None or exchange in SUPPORTED_EXCHANGES:
        return None
    return f"{exchange.value} chưa được hỗ trợ; giai đoạn này chỉ hỗ trợ HOSE."


_REJECTION_REASONS = {
    CodeKind.COVERED_WARRANT: "Chứng quyền có bảo đảm chưa được hỗ trợ (chỉ hỗ trợ cổ phiếu, ETF và chỉ số).",
    CodeKind.FUTURES: "Hợp đồng tương lai chưa được hỗ trợ (chỉ hỗ trợ cổ phiếu, ETF và chỉ số).",
}


@dataclass(frozen=True)
class VnCode:
    """A recognised Vietnamese code before listing lookup."""

    code: str
    kind: CodeKind
    index_exchange: Optional[Exchange] = None

    @property
    def supported(self) -> bool:
        return self.rejection_reason is None

    @property
    def rejection_reason(self) -> Optional[str]:
        return _REJECTION_REASONS.get(self.kind) or exchange_rejection(self.index_exchange)


def _clean(code: object) -> str:
    text = str(code or "").strip().upper()
    for suffix in (".VN", ".HM", ".HN"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def classify(code: object) -> Optional[VnCode]:
    """Return the Vietnamese code kind, or ``None`` if it isn't Vietnamese."""
    text = _clean(code)
    if not text:
        return None
    if text in _INDEX_ALIASES:
        canonical = _INDEX_ALIASES[text]
        return VnCode(canonical, CodeKind.INDEX, _INDICES[canonical][0])
    if _FUTURES_RE.match(text):
        return VnCode(text, CodeKind.FUTURES)
    if _COVERED_WARRANT_RE.match(text):
        return VnCode(text, CodeKind.COVERED_WARRANT)
    if _ETF_RE.match(text):
        return VnCode(text, CodeKind.ETF)
    if _STOCK_RE.match(text):
        return VnCode(text, CodeKind.STOCK)
    return None


def is_vn_code(code: object) -> bool:
    """True for any recognised Vietnamese code, supported or not."""
    return classify(code) is not None


def canonical_code(code: object) -> str:
    parsed = classify(code)
    return parsed.code if parsed else _clean(code)


@dataclass(frozen=True)
class Instrument:
    """A listed Vietnamese Instrument or Index with its Exchange, once resolved."""

    code: str
    kind: CodeKind
    exchange: Optional[Exchange]
    name: str = ""
