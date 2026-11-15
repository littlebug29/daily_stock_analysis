# -*- coding: utf-8 -*-
"""Rendering helpers for Vietnam-specific report blocks."""

from __future__ import annotations

from typing import Any, Dict, List

_LABELS = {
    "vi": {
        "heading": "Quy tắc giao dịch",
        "exchange": "Sàn",
        "reference": "Giá tham chiếu",
        "band": "Biên độ phiên kế tiếp",
        "unit": "nghìn đồng",
    },
    "en": {
        "heading": "Trading rules",
        "exchange": "Exchange",
        "reference": "Reference Price",
        "band": "Next-session Price Band",
        "unit": "thousand đồng",
    },
}


def format_trade_rules_lines(rules: Dict[str, Any], language: str = "vi") -> List[str]:
    """Markdown lines for the Price Band and Settlement Lag under the Trade Plan."""
    labels = _LABELS.get(language, _LABELS["en"])
    floor = rules.get("floor_price", "N/A")
    ceiling = rules.get("ceiling_price", "N/A")
    return [
        f"**⚖️ {labels['heading']}** ({labels['unit']})",
        f"- {labels['exchange']}: {rules.get('exchange', 'N/A')} | "
        f"{labels['reference']}: {rules.get('reference_price', 'N/A')} | "
        f"{labels['band']}: {floor} – {ceiling}",
        f"- {rules.get('settlement_note', '')}",
        "",
    ]
