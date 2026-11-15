# -*- coding: utf-8 -*-
"""Vietnamese (``vi``) report copy, merged into ``src.report_language`` tables.

Kept in its own module so upstream's language tables stay untouched apart from
the single install hook (ADR-0001: keep Vietnam logic in new modules).

Signals use the project's three-word vocabulary (CONTEXT.md "Signal"):
Mua (Buy), Theo dõi (Watch), Bán (Sell). Upstream's seven operation-advice
levels collapse onto those three in Vietnamese output.
"""

from __future__ import annotations

from typing import Any, Dict

LANGUAGE = "vi"

ALIASES = {
    "vietnamese": "vi",
    "vi-vn": "vi",
    "vi_vn": "vi",
    "vn": "vi",
    "tiếng_việt": "vi",
}

SIGNAL_BUY = "Mua"
SIGNAL_WATCH = "Theo dõi"
SIGNAL_SELL = "Bán"

OPERATION_ADVICE = {
    "strong_buy": SIGNAL_BUY,
    "buy": SIGNAL_BUY,
    "hold": SIGNAL_WATCH,
    "watch": SIGNAL_WATCH,
    "reduce": SIGNAL_SELL,
    "sell": SIGNAL_SELL,
    "strong_sell": SIGNAL_SELL,
}

# Vietnamese words the LLM may emit, mapped back to canonical keys.
OPERATION_ADVICE_CANONICAL = {
    "mua mạnh": "strong_buy",
    "mua": "buy",
    "tích lũy": "buy",
    "nắm giữ": "hold",
    "giữ": "hold",
    "theo dõi": "watch",
    "quan sát": "watch",
    "đứng ngoài": "watch",
    "giảm tỷ trọng": "reduce",
    "bán": "sell",
    "bán mạnh": "strong_sell",
}

TREND_PREDICTION = {
    "strong_bullish": "Tăng mạnh",
    "bullish": "Tăng",
    "sideways": "Đi ngang",
    "bearish": "Giảm",
    "strong_bearish": "Giảm mạnh",
}

TREND_PREDICTION_CANONICAL = {
    "tăng mạnh": "strong_bullish",
    "tăng": "bullish",
    "đi ngang": "sideways",
    "tích lũy đi ngang": "sideways",
    "giảm": "bearish",
    "giảm mạnh": "strong_bearish",
}

CONFIDENCE_LEVEL = {"high": "Cao", "medium": "Trung bình", "low": "Thấp"}
CONFIDENCE_LEVEL_CANONICAL = {"cao": "high", "trung bình": "medium", "thấp": "low"}

STRATEGY_SIGNAL = {
    "strong_buy": SIGNAL_BUY,
    "buy": SIGNAL_BUY,
    "hold": SIGNAL_WATCH,
    "sell": SIGNAL_SELL,
    "strong_sell": SIGNAL_SELL,
}

CONSENSUS_LEVEL = {
    "high": "Cao",
    "medium": "Trung bình",
    "low": "Thấp",
    "insufficient": "Chưa đủ bằng chứng",
}

CONFLICT_SEVERITY = {"none": "Không", "low": "Thấp", "medium": "Trung bình", "high": "Cao"}

STRATEGY_SKILL = {
    "bull_trend": "Xu hướng tăng",
    "hot_theme": "Chủ đề nóng",
    "volume_breakout": "Bùng nổ khối lượng",
    "ma_golden_cross": "Giao cắt vàng MA",
    "growth_quality": "Chất lượng tăng trưởng",
    "bottom_volume": "Khối lượng đáy",
    "box_oscillation": "Dao động hộp",
    "chan_theory": "Lý thuyết Chan",
    "dragon_head": "Cổ phiếu dẫn dắt",
    "emotion_cycle": "Chu kỳ tâm lý",
    "event_driven": "Theo sự kiện",
    "expectation_repricing": "Định giá lại kỳ vọng",
    "one_yang_three_yin": "Một tăng ba giảm",
    "shrink_pullback": "Điều chỉnh khối lượng thấp",
    "wave_theory": "Lý thuyết sóng",
}

CHIP_HEALTH = {"healthy": "Tốt", "average": "Trung bình", "caution": "Cần thận trọng"}
BIAS_STATUS = {"safe": "An toàn", "caution": "Cảnh giác", "danger": "Nguy hiểm"}

PLACEHOLDER = "Đang cập nhật"
UNKNOWN = "Không rõ"
NO_DATA = "Thiếu dữ liệu"
CHIP_UNAVAILABLE = "Phân bổ giá vốn chưa bật hoặc nguồn dữ liệu tạm thời không khả dụng; chưa dùng tín hiệu này."
GENERIC_STOCK_NAME = "Mã chưa xác định"

REPORT_LABELS: Dict[str, str] = {
    "dashboard_title": "Bảng quyết định",
    "brief_title": "Tóm tắt quyết định",
    "analyzed_prefix": "Đã phân tích",
    "stock_unit": "mã",
    "stock_unit_compact": "mã",
    "buy_label": SIGNAL_BUY,
    "watch_label": SIGNAL_WATCH,
    "sell_label": SIGNAL_SELL,
    "summary_heading": "Tổng quan",
    "info_heading": "Cập nhật chính",
    "sentiment_summary_label": "Tâm lý",
    "earnings_outlook_label": "Triển vọng lợi nhuận",
    "risk_alerts_label": "Rủi ro",
    "positive_catalysts_label": "Động lực tích cực",
    "latest_news_label": "Tin mới nhất",
    "core_conclusion_heading": "Kết luận chính",
    "one_sentence_label": "Quyết định một câu",
    "time_sensitivity_label": "Thời hạn",
    "default_time_sensitivity": "Tuần này",
    "position_status_label": "Vị thế",
    "action_advice_label": "Hành động",
    "no_position_label": "Chưa nắm giữ",
    "has_position_label": "Đang nắm giữ",
    "continue_holding": "Tiếp tục nắm giữ",
    "market_snapshot_heading": "Diễn biến giá",
    "close_label": "Đóng cửa",
    "prev_close_label": "Giá tham chiếu",
    "open_label": "Mở cửa",
    "high_label": "Cao nhất",
    "low_label": "Thấp nhất",
    "change_pct_label": "Thay đổi %",
    "change_amount_label": "Thay đổi",
    "amplitude_label": "Biên độ dao động",
    "volume_label": "Khối lượng",
    "amount_label": "Giá trị giao dịch",
    "current_price_label": "Giá",
    "volume_ratio_label": "Tỷ lệ khối lượng",
    "turnover_rate_label": "Tỷ lệ luân chuyển",
    "source_label": "Nguồn",
    "data_sources_label": "Nguồn dữ liệu",
    "data_perspective_heading": "Góc nhìn dữ liệu",
    "ma_alignment_label": "Sắp xếp MA",
    "bullish_alignment_label": "Sắp xếp tăng",
    "yes_label": "Có",
    "no_label": "Không",
    "none_label": "Không có",
    "trend_strength_label": "Sức mạnh xu hướng",
    "price_metrics_label": "Chỉ số giá",
    "ma5_label": "MA5",
    "ma10_label": "MA10",
    "ma20_label": "MA20",
    "bias_ma5_label": "Độ lệch (MA5)",
    "support_level_label": "Hỗ trợ",
    "resistance_level_label": "Kháng cự",
    "chip_label": "Phân bổ giá vốn",
    "phase_decision_heading": "Kiểm soát theo phiên",
    "action_window_label": "Thời điểm hành động",
    "immediate_action_label": "Hành động hiện tại",
    "watch_conditions_label": "Điều kiện theo dõi",
    "next_check_time_label": "Kiểm tra tiếp theo",
    "confidence_reason_label": "Lý do mức tin cậy",
    "data_limitations_label": "Giới hạn dữ liệu",
    "battle_plan_heading": "Kế hoạch giao dịch",
    "ideal_buy_label": "Vùng mua",
    "secondary_buy_label": "Vùng mua phụ",
    "stop_loss_label": "Cắt lỗ",
    "take_profit_label": "Mục tiêu",
    "suggested_position_label": "Tỷ trọng",
    "entry_plan_label": "Kế hoạch vào lệnh",
    "risk_control_label": "Quản trị rủi ro",
    "checklist_heading": "Danh sách kiểm tra",
    "failed_checks_heading": "Điều kiện chưa đạt",
    "history_compare_heading": "So sánh tín hiệu trước đây",
    "time_label": "Thời gian",
    "score_label": "Điểm",
    "advice_label": "Khuyến nghị",
    "trend_label": "Xu hướng",
    "generated_at_label": "Tạo lúc",
    "report_time_label": "Thời điểm",
    "no_results": "Không có kết quả phân tích",
    "report_title": "Báo cáo phân tích cổ phiếu",
    "avg_score_label": "Điểm trung bình",
    "action_points_heading": "Mức giá hành động",
    "position_advice_heading": "Khuyến nghị vị thế",
    "analysis_model_label": "Mô hình",
    "not_investment_advice": "Nội dung do AI tạo, chỉ để tham khảo, không phải khuyến nghị đầu tư.",
    "details_report_hint": "Xem báo cáo chi tiết:",
    "financial_summary_heading": "Tóm tắt tài chính",
    "report_date_label": "Kỳ báo cáo",
    "revenue_label": "Doanh thu",
    "net_profit_label": "Lợi nhuận sau thuế (công ty mẹ)",
    "operating_cash_flow_label": "Dòng tiền kinh doanh",
    "roe_label": "ROE",
    "revenue_yoy_label": "Doanh thu so với cùng kỳ",
    "net_profit_yoy_label": "Lợi nhuận so với cùng kỳ",
    "gross_margin_label": "Biên lợi nhuận gộp",
    "shareholder_return_heading": "Lợi ích cổ đông",
    "ttm_cash_dividend_label": "Cổ tức tiền mặt 12 tháng / cổ phiếu",
    "ttm_event_count_label": "Số lần trả cổ tức 12 tháng",
    "ttm_dividend_yield_label": "Tỷ suất cổ tức 12 tháng",
    "latest_ex_dividend_label": "Ngày giao dịch không hưởng quyền gần nhất",
    "institutional_flow_heading": "Dòng tiền tổ chức",
    "institutional_flow_note": "Dương = mua ròng, âm = bán ròng.",
    "inst_foreign_label": "Khối ngoại",
    "inst_trust_label": "Quỹ đầu tư",
    "inst_dealer_label": "Tự doanh",
    "inst_total_label": "Tổng",
    "related_boards_heading": "Ngành liên quan",
    "industry_boards_heading": "Ngành",
    "concept_boards_heading": "Chủ đề",
    "board_name_label": "Ngành",
    "board_type_label": "Loại",
    "board_status_label": "Trạng thái",
    "board_change_pct_label": "Thay đổi %",
    "leading_board_label": "Dẫn dắt",
    "lagging_board_label": "Kém nhất",
    "signal_attribution_heading": "Phân rã tín hiệu",
    "attribution_weights_label": "Trọng số",
    "technical_indicators_label": "Chỉ báo kỹ thuật",
    "news_sentiment_label": "Tâm lý tin tức",
    "fundamentals_label": "Cơ bản",
    "market_conditions_label": "Bối cảnh thị trường",
    "strongest_bullish_signal_label": "Tín hiệu tăng mạnh nhất",
    "strongest_bearish_signal_label": "Tín hiệu giảm mạnh nhất",
    "strategy_synthesis_heading": "Tổng hợp chiến lược",
    "strategy_final_signal_label": "Tín hiệu cuối",
    "strategy_consensus_level_label": "Mức đồng thuận",
    "strategy_conflict_label": "Mâu thuẫn",
    "strategy_confidence_label": "Mức tin cậy",
    "strategy_summary_label": "Tóm tắt",
    "strategy_supporting_skills_label": "Chiến lược ủng hộ",
    "strategy_opposing_skills_label": "Chiến lược phản đối",
    "strategy_invalid_opinions_label": "{count} chiến lược khác không tạo được tín hiệu hợp lệ",
}


def _merge_translations(table: Dict[str, Dict[str, str]], values: Dict[str, str]) -> None:
    for key, text in values.items():
        if key in table:
            table[key][LANGUAGE] = text


def install(module: Any) -> None:
    """Register ``vi`` copy in ``src.report_language``'s tables (idempotent)."""
    module._REPORT_LANGUAGE_ALIASES.update(ALIASES)
    module._OPERATION_ADVICE_CANONICAL_MAP.update(OPERATION_ADVICE_CANONICAL)
    module._TREND_PREDICTION_CANONICAL_MAP.update(TREND_PREDICTION_CANONICAL)
    module._CONFIDENCE_LEVEL_CANONICAL_MAP.update(CONFIDENCE_LEVEL_CANONICAL)
    _merge_translations(module._OPERATION_ADVICE_TRANSLATIONS, OPERATION_ADVICE)
    _merge_translations(module._TREND_PREDICTION_TRANSLATIONS, TREND_PREDICTION)
    _merge_translations(module._CONFIDENCE_LEVEL_TRANSLATIONS, CONFIDENCE_LEVEL)
    _merge_translations(module._STRATEGY_SIGNAL_TRANSLATIONS, STRATEGY_SIGNAL)
    _merge_translations(module._CONSENSUS_LEVEL_TRANSLATIONS, CONSENSUS_LEVEL)
    _merge_translations(module._CONFLICT_SEVERITY_TRANSLATIONS, CONFLICT_SEVERITY)
    _merge_translations(module._STRATEGY_SKILL_TRANSLATIONS, STRATEGY_SKILL)
    _merge_translations(module._CHIP_HEALTH_TRANSLATIONS, CHIP_HEALTH)
    _merge_translations(module._BIAS_STATUS_TRANSLATIONS, BIAS_STATUS)
    module._PLACEHOLDER_BY_LANGUAGE[LANGUAGE] = PLACEHOLDER
    module._UNKNOWN_BY_LANGUAGE[LANGUAGE] = UNKNOWN
    module._NO_DATA_BY_LANGUAGE[LANGUAGE] = NO_DATA
    module._CHIP_UNAVAILABLE_BY_LANGUAGE[LANGUAGE] = CHIP_UNAVAILABLE
    module._GENERIC_STOCK_NAME_BY_LANGUAGE[LANGUAGE] = GENERIC_STOCK_NAME
    labels = dict(module._REPORT_LABELS.get("en", {}))
    labels.update(REPORT_LABELS)
    module._REPORT_LABELS[LANGUAGE] = labels
