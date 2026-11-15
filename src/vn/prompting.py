# -*- coding: utf-8 -*-
"""Prompt text for Vietnamese Decision Reports."""

from __future__ import annotations

from src.vn.rules import PRICE_BAND_PCT, SETTLEMENT_LAG_TRADING_DAYS

_BANDS = ", ".join(f"±{int(pct * 100)}% {exchange.value}" for exchange, pct in PRICE_BAND_PCT.items())

MARKET_ROLE = {
    "en": "Vietnamese stock investment analysis (HOSE, HNX, UPCoM)",
    "zh": "越南股票投资分析（HOSE、HNX、UPCoM）",
}

MARKET_GUIDELINES = {
    "en": f"""- This is a Vietnamese Instrument listed on HOSE, HNX or UPCoM. All prices are in thousand đồng (e.g. 120.5 = 120,500 đ).
- Daily Price Band from the Reference Price: {_BANDS}. Buy zones (orders for the next session) must lie between its Floor and Ceiling Price.
- Prices must be multiples of the Exchange Tick Size (HOSE: 0.01 below 10, 0.05 from 10 to below 50, 0.1 from 50; HNX/UPCoM: 0.1).
- Settlement Lag is T+{SETTLEMENT_LAG_TRADING_DAYS}: shares bought today can only be sold {SETTLEMENT_LAG_TRADING_DAYS} Trading Days later, so a stop-loss cannot be executed before then.
- Sessions (ICT): ATO 9:00-9:15, continuous 9:15-11:30 and 13:00-14:30, ATC 14:30-14:45.""",
    "zh": f"""- 这是在 HOSE、HNX 或 UPCoM 上市的越南证券，价格单位为千越南盾（120.5 = 120,500 đ）。
- 涨跌幅限制：{_BANDS}（以参考价计算）。
- 价格须符合最小报价单位；结算为 T+{SETTLEMENT_LAG_TRADING_DAYS}，买入后 {SETTLEMENT_LAG_TRADING_DAYS} 个交易日内不能卖出。""",
}

VI_OUTPUT_DIRECTIVE = f"""

## Output Language (highest priority)

- Keep all JSON keys unchanged.
- `decision_type` must remain `buy|hold|sell`.
- All human-readable JSON values must be written in Vietnamese (tiếng Việt), using Vietnamese market terms (giá trần, giá sàn, giá tham chiếu, khối ngoại, tự doanh, thanh khoản).
- `operation_advice` must be exactly one of: "Mua", "Theo dõi", "Bán".
- Write every price in thousand đồng with a dot as the decimal separator (e.g. 118.5), never with "元" or "$".
- In the Trade Plan (`sniper_points`), buy zones are orders for the next session and must lie inside its Price Band; stop-loss and target may be further away. Remember the T+{SETTLEMENT_LAG_TRADING_DAYS} Settlement Lag: say when the stop-loss becomes executable.
- Use the listed company's Vietnamese name when confident; otherwise keep the code. Do not invent names.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, nested dashboard text, checklist items, and all narrative summaries.
"""
