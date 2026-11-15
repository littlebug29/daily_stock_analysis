# -*- coding: utf-8 -*-
"""Report disclosure text for when the news search was not executed or returned zero hits.

Single source of truth: the string-concatenation renderer (src/notification.py) and the template
rendering chain (src/services/report_renderer.py + templates/*.j2) share this module, so that
the same analysis result is never disclosed on some channels and silent on others.

The disclosure asserts "whether this conclusion used any news evidence", so the primary basis is
whether the news evidence the analysis actually received (news_context) is non-empty, not how many
search hits there were. news_context may come from realtime search, social sentiment or the locally
stored news pool; the latter two also go into the model input but produce no search hits, so looking
only at the count would misreport such analyses as "news evidence not included" (review OR-COR-2e4b9d61).

news_result_count is therefore secondary and only explains why there is truly no evidence:
    None  search not executed (no search channel configured)
    0     search executed but zero hits (rate limiting, all failed, etc.)
    > 0   realtime search had hits (evidence necessarily exists in this case)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from src.report_language import SUPPORTED_REPORT_LANGUAGES

_ZH_NOT_CONFIGURED = "⚠️ 未配置搜索渠道，本次分析未纳入新闻面证据。"
_EN_NOT_CONFIGURED = (
    "⚠️ No news search channel is configured; "
    "this analysis does not incorporate news-based evidence."
)
_ZH_ZERO_RESULTS = "⚠️ 本次未获取到可用的新闻面数据，以下结论未纳入新闻维度证据。"
_EN_ZERO_RESULTS = (
    "⚠️ No news data could be retrieved for this run; "
    "the conclusions below do not incorporate news-based evidence."
)
_KO_NOT_CONFIGURED = (
    "⚠️ 뉴스 검색 채널이 설정되지 않아 이번 분석에는 "
    "뉴스 근거를 반영하지 않았습니다."
)
_KO_ZERO_RESULTS = (
    "⚠️ 이번 분석에서 사용 가능한 뉴스 데이터를 가져오지 못해 "
    "아래 결론에는 뉴스 근거를 반영하지 않았습니다."
)

_DISCLOSURES = {
    "zh": (_ZH_NOT_CONFIGURED, _ZH_ZERO_RESULTS),
    "en": (_EN_NOT_CONFIGURED, _EN_ZERO_RESULTS),
    "ko": (_KO_NOT_CONFIGURED, _KO_ZERO_RESULTS),
    "vi": (
        "⚠️ Chưa cấu hình nguồn tin tức; phân tích này chưa dùng bằng chứng từ tin tức.",
        "⚠️ Lần này không lấy được dữ liệu tin tức; các kết luận dưới đây chưa dùng bằng chứng từ tin tức.",
    ),
}

if set(_DISCLOSURES) != set(SUPPORTED_REPORT_LANGUAGES):
    raise RuntimeError(
        "Empty-news disclosures must cover every SUPPORTED_REPORT_LANGUAGES value"
    )


def persisted_news_result_state(
    raw_result: Any,
    context_snapshot: Any = None,
) -> Tuple[Optional[int], bool]:
    """Restore the count and its reliability from the persisted payload.

    New records store the tri-state value explicitly in raw_result; old records may leave a
    0 / >0 count in context_snapshot. When neither place has the field, it can only be classified
    as legacy unknown; a missing field must not be treated as an explicit None.
    """
    if isinstance(raw_result, Mapping):
        if raw_result.get("news_result_count_known") is False:
            return None, False
        if "news_result_count" in raw_result:
            return raw_result.get("news_result_count"), True

    if isinstance(context_snapshot, Mapping) and "news_result_count" in context_snapshot:
        return context_snapshot.get("news_result_count"), True

    return None, False


def news_evidence_present(*sources: Any) -> bool:
    """Whether this analysis actually received news evidence. True if any source is true.

    Each source is either a real item count (int) or a content string with **placeholder text
    already excluded**. Realtime search, social sentiment and the local news pool each count as
    one source; both pipeline paths use this function, so do not write a separate check elsewhere.

    **Do not pass in the whole news_context assembled by the pipeline.**
    `format_intel_report()` in `src/search_service.py` still outputs the
    `【XX 情报搜索结果】` heading and a 「未找到相关信息」 ("no relevant information found")
    placeholder for every dimension on zero hits, so the whole block is never empty; judging by it would turn
    "searched but got nothing" into "has evidence", swallowing exactly the disclosure this module
    adds (review OR-COR-8f4c2d1b). The check must register each source individually, not sniff the string.
    """
    for source in sources:
        if source is None or isinstance(source, bool):
            if source:
                return True
            continue
        if isinstance(source, (int, float)):
            if source > 0:
                return True
            continue
        if str(source).strip():
            return True
    return False


def _disclosure_for_state(
    news_result_count: Optional[int],
    *,
    known: bool,
    evidence_present: bool,
    language: str,
) -> Optional[str]:
    try:
        not_configured, zero_results = _DISCLOSURES[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported report language for empty-news disclosure: {language}") from exc

    if not known:
        return None
    # If evidence exists, show no notice, whichever source it came from; the count only explains why
    # there is no evidence.
    if evidence_present:
        return None
    if news_result_count is None:
        return not_configured
    if news_result_count == 0:
        return zero_results
    return None


def empty_news_disclosure(result: Any, language: str = "zh") -> Optional[str]:
    """Return the matching notice when search was not executed or had zero hits; return None on normal hits.

    The decision must be independent of whether the model produced news text: the analyzer's
    output schema still requires market_sentiment / hot_topics even without news, and deciding by
    whether those fields are empty would produce the worst combination: "showing the model-generated
    sentiment judgement while hiding that there was no news evidence".
    """
    if isinstance(result, Mapping):
        news_result_count, known = persisted_news_result_state(result)
        evidence_present = persisted_news_evidence_present(result, news_result_count)
    else:
        news_result_count = getattr(result, "news_result_count", None)
        known = getattr(result, "news_result_count_known", True)
        evidence_present = bool(getattr(result, "news_evidence_present", False))
    return _disclosure_for_state(
        news_result_count,
        known=known,
        evidence_present=evidence_present,
        language=language,
    )


def empty_news_disclosure_from_stored(
    raw_result: Any,
    context_snapshot: Any,
    language: str = "zh",
) -> Optional[str]:
    """Generate the disclosure from the persisted payload for history/API entry points.

    Stays silent when old records lack the fields.
    """
    news_result_count, known = persisted_news_result_state(raw_result, context_snapshot)
    return _disclosure_for_state(
        news_result_count,
        known=known,
        evidence_present=persisted_news_evidence_present(raw_result, news_result_count),
        language=language,
    )


def persisted_news_evidence_present(raw_result: Any, news_result_count: Optional[int]) -> bool:
    """Restore "whether this analysis used news evidence" from the persisted payload.

    Records written before this PR lack the field, so fall back to inferring from the count: >0 means
    evidence did exist, and anything else is treated as no evidence. This matches how the report
    looked at the time and never retroactively changes old reports.
    """
    if isinstance(raw_result, Mapping) and "news_evidence_present" in raw_result:
        return bool(raw_result.get("news_evidence_present"))
    return bool(news_result_count)
