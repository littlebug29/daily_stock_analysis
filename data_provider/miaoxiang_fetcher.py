"""
MiaoXiang financial data source - wrapper for East Money MiaoXiang Skills MX_API

Role:
    Fills vertical data blocks (per-stock capital flow / chip distribution) when the public quote APIs are unstable;
    it does not take part in the daily K-line main chain (its supported market set in `_DAILY_MARKET_FETCHER_SUPPORT` is empty).

Data source:
    MiaoXiang quant API (MX_API); natural-language queries return structured tables:
    POST https://mkapi2.dfcfs.com/finskillshub/api/claw/query
    Header: apikey: <MX_APIKEY>
    Body:   {"toolQuery": "<natural-language query>"}

Enabled when:
    MX_APIKEY is configured; DataFetcherManager then instantiates it automatically.
"""

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from .base import (
    BaseFetcher,
    DataFetchError,
    _is_etf_code,
    _is_non_cn_request,
    normalize_stock_code,
)
from .realtime_types import ChipDistribution

logger = logging.getLogger(__name__)

# MiaoXiang API base URL (direct connection within mainland China)
MX_API_BASE_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"

# Query result cache TTL (seconds): reuse capital flow / chip data for the same stock briefly to save quota
MX_CACHE_TTL_SECONDS = 300.0
# Minimum interval between consecutive requests (seconds): stay polite to the natural-language API
MX_MIN_REQUEST_INTERVAL_SECONDS = 0.3





def _parse_number(text: Any) -> Optional[float]:
    """Extract a number from text such as '13.91' / '13.91' with a yuan (CNY) suffix / '-1.5'."""
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def _parse_money_yuan(text: Any) -> Optional[float]:
    """Parse values with Chinese 10k (wan) / 100M (yi) units, e.g. '-93.64 wan yuan' / '1.2 yi' / '-493.5 wan', into a float in CNY."""
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if "%" in s or "％" in s:
        return None
    val = _parse_number(s)
    if val is None:
        return None
    if "亿" in s:
        val *= 1e8
    elif "万" in s:
        val *= 1e4
    return val


def _parse_ratio(text: Any) -> Optional[float]:
    """Parse '83.24%' as 0.8324; '0.83' is treated as already a fraction."""
    val = _parse_number(text)
    if val is None:
        return None
    if "%" in str(text or ""):
        val = val / 100.0
    if val > 1.0:
        # Fallback: some queries may return 83.24 without the % sign
        val = val / 100.0
    return val


class MiaoxiangFetcher(BaseFetcher):
    """MiaoXiang financial data source (supplementary source for capital flow / chip distribution)"""

    name = "MiaoxiangFetcher"
    # Declare which capital-flow markets this supplementary source can serve; probing and budget allocation rely on it,
    # so a same-named method implemented only for other markets (e.g. FutuFetcher, HK only) isn't mistaken for a supplement here
    capital_flow_markets = {"cn"}
    # Admission is shared by chip/flow queries and by fresh manager instances.
    # Never queue another quota-consuming request behind an abandoned worker.
    _request_lock = threading.Lock()

    def __init__(
        self,
        api_key: str = "",
        priority: int = 6,
        timeout: int = 10,
        base_url: str = MX_API_BASE_URL,
        cache_ttl: float = MX_CACHE_TTL_SECONDS,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.priority = int(priority)
        self.timeout = int(timeout)
        self.base_url = base_url.rstrip("/")
        self._cache_ttl = float(cache_ttl)
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()
        self._last_request_ts = 0.0

    def is_available_for_request(self, capability: str = "") -> bool:
        """Keep this supplement-only provider out of every daily-data route."""
        return capability != "daily_data"

    # ------------------------------------------------------------------
    # MX_API client
    # ------------------------------------------------------------------

    def _query_tables(self, cache_key: str, tool_query: str) -> List[Dict[str, Any]]:
        """Run one natural-language query and return dataTableDTOList (with TTL cache)."""
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and (time.time() - cached[0]) < self._cache_ttl:
                return cached[1]

        if not self._request_lock.acquire(blocking=False):
            raise DataFetchError("妙想 API 请求仍在执行，跳过本次补充查询")
        try:
            wait = MX_MIN_REQUEST_INTERVAL_SECONDS - (time.time() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            try:
                response = requests.post(
                    self.base_url,
                    headers={"apikey": self.api_key, "Content-Type": "application/json"},
                    json={"toolQuery": tool_query},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                raise DataFetchError(f"妙想 API 请求失败: {exc}") from exc
            finally:
                self._last_request_ts = time.time()
        finally:
            self._request_lock.release()

        if payload.get("status") != 0:
            message = str(payload.get("message", ""))[:120]
            raise DataFetchError(f"妙想 API 返回错误: status={payload.get('status')} {message}")

        # Supports two official response shapes (a limited set of explicit candidate paths, no recursive fallback):
        #   A. Observed shape:  data.data.searchDataResultDTO.dataTableDTOList
        #   B. Public docs:     data.dataTableDTOList
        tables: list = []
        data_node = payload.get("data")
        if isinstance(data_node, dict):
            candidate_a = (
                data_node.get("data", {})
                if isinstance(data_node.get("data"), dict) else {}
            ).get("searchDataResultDTO", {})
            candidate_a = candidate_a.get("dataTableDTOList") if isinstance(candidate_a, dict) else None
            candidate_b = data_node.get("dataTableDTOList")
            for candidate in (candidate_a, candidate_b):
                if isinstance(candidate, list) and candidate:
                    tables = [t for t in candidate if isinstance(t, dict)]
                    break
        if not tables:
            raise DataFetchError("妙想 API 未返回数据表格")

        with self._cache_lock:
            self._cache[cache_key] = (time.time(), tables)
        return tables

    @staticmethod
    def _table_name_map(table_dto: Dict[str, Any]) -> Dict[str, Any]:
        """Use the same numeric-key/list mapping for selection and row parsing."""
        name_map = table_dto.get("nameMap") or {}
        if isinstance(name_map, list):
            name_map = {str(i): v for i, v in enumerate(name_map)}
        return name_map

    @staticmethod
    def _table_rows(table_dto: Dict[str, Any]) -> List[Dict[str, str]]:
        """Convert an MX table (headName as the row axis + indicator column arrays) into a [{label: value}] row list."""
        table = table_dto.get("table") or {}
        name_map = MiaoxiangFetcher._table_name_map(table_dto)
        heads = table.get("headName") or []
        rows: List[Dict[str, str]] = []
        for key, values in table.items():
            if key == "headName" or not isinstance(values, list):
                continue
            label = str(name_map.get(key, name_map.get(str(key), key)))
            for idx, value in enumerate(values):
                while len(rows) <= idx:
                    rows.append({})
                rows[idx][label] = "" if value is None else str(value)
        # Keep each row's date (headName) so capital flow can be aggregated by day
        for idx, head in enumerate(heads):
            while len(rows) <= idx:
                rows.append({})
            rows[idx]["_date"] = str(head)
        return rows

    def _table_labels(self, table_dto: Dict[str, Any]) -> List[str]:
        """Return all indicator names in the table (mapped via nameMap)."""
        table = table_dto.get("table") or {}
        name_map = self._table_name_map(table_dto)
        labels: List[str] = []
        for key in table:
            if key == "headName":
                continue
            labels.append(str(name_map.get(key, name_map.get(str(key), key))))
        return labels

    def _find_table_by_label(self, tables: List[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
        """Return the table containing the given indicator; if several match, prefer the one with the most rows (time series over current snapshot)."""
        best: Optional[Dict[str, Any]] = None
        best_rows = -1
        for table_dto in tables:
            if not any(keyword in label for label in self._table_labels(table_dto)):
                continue
            rows = len((table_dto.get("table") or {}).get("headName") or [])
            if rows > best_rows:
                best = table_dto
                best_rows = rows
        return best

    def _find_table_by_label_score(
        self,
        tables: List[Dict[str, Any]],
        required_keyword: str,
        wanted_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Natural-language table combinations are unstable: score tables by "target fields hit" and prefer fewer rows (snapshot over series)."""
        best: Optional[Dict[str, Any]] = None
        best_key = (-1, 10**9)
        for table_dto in tables:
            labels = self._table_labels(table_dto)
            if not any(required_keyword in label for label in labels):
                continue
            score = sum(1 for kw in wanted_keywords if any(kw in label for label in labels))
            rows = len((table_dto.get("table") or {}).get("headName") or [])
            if (score, -rows) > best_key:
                best = table_dto
                best_key = (score, -rows)
        return best

    # ------------------------------------------------------------------
    # Chip distribution
    # ------------------------------------------------------------------

    def get_chip_distribution(self, stock_code: str) -> Optional[ChipDistribution]:
        """
        Fetch core chip-distribution metrics via the MiaoXiang API:
        profit ratio / average cost / 90% concentration / 70% concentration.

        Returns:
            ChipDistribution (source=miaoxiang); raises DataFetchError on failure.
        """
        stock_code = normalize_stock_code(stock_code)
        if _is_non_cn_request(stock_code) or _is_etf_code(stock_code):
            logger.debug(f"[API跳过] {stock_code} 非A股个股，无筹码分布数据")
            return None

        tables = self._query_tables(
            f"chip:{stock_code}",
            f"{stock_code} 获利比例 平均成本 90%筹码集中度 70%筹码集中度",
        )
        target = self._find_table_by_label_score(
            tables,
            required_keyword="平均成本",
            wanted_keywords=["获利比例", "90%筹码集中度", "70%筹码集中度"],
        )
        if target is None:
            target = self._find_table_by_label(tables, "筹码")
        if target is None:
            raise DataFetchError("妙想 API 筹码分布返回缺少可用表格")

        rows = self._table_rows(target)
        if not rows:
            raise DataFetchError("妙想 API 筹码分布表格为空")
        row = rows[0]

        avg_cost = _parse_number(row.get("平均成本"))
        profit_ratio = _parse_ratio(row.get("获利比例"))
        concentration_90 = _parse_ratio(row.get("90%筹码集中度"))
        concentration_70 = _parse_ratio(row.get("70%筹码集中度"))

        if avg_cost is None or avg_cost <= 0:
            raise DataFetchError(f"妙想 API 筹码分布平均成本无效: {row}")

        chip = ChipDistribution(
            code=stock_code,
            date=str(row.get("_date", "")).split(" ")[0],
            source="miaoxiang",
        )
        chip.avg_cost = float(avg_cost)
        if profit_ratio is not None:
            chip.profit_ratio = float(profit_ratio)
        if concentration_90 is not None:
            chip.concentration_90 = float(concentration_90)
        if concentration_70 is not None:
            chip.concentration_70 = float(concentration_70)
        return chip

    # ------------------------------------------------------------------
    # Per-stock capital flow
    # ------------------------------------------------------------------

    def get_capital_flow(self, stock_code: str, top_n: int = 5) -> Dict[str, Any]:
        """
        Fetch per-stock main-force capital flow via the MiaoXiang API:
        today's main-force net inflow + 5-day / 10-day main-force net inflow totals.

        Returns:
            Payload with the same shape as AkshareFundamentalAdapter.get_capital_flow.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "stock_flow": {},
            "sector_rankings": {"top": [], "bottom": []},
            "source_chain": [],
            "errors": [],
        }
        stock_code = normalize_stock_code(stock_code)
        if _is_non_cn_request(stock_code) or _is_etf_code(stock_code):
            return result

        try:
            tables = self._query_tables(
                f"flow:{stock_code}",
                f"{stock_code} 近10日每日主力净流入资金",
            )
        except DataFetchError as exc:
            result["errors"].append(f"miaoxiang: {exc}")
            return result
        # Natural-language responses may include prices or ratios before the amount.
        # Only explicit monetary metrics may feed currency-valued stock_flow fields.
        amount_labels = {"主力净流入", "主力净流入资金", "主力净流入金额"}
        amount_tables = [
            table for table in tables
            if any(label in amount_labels for label in self._table_labels(table))
        ]
        target = self._find_table_by_label(amount_tables, "主力净流入")
        if target is None:
            result["errors"].append("miaoxiang: no capital flow table")
            return result

        rows = self._table_rows(target)
        series: List[Tuple[str, Optional[float]]] = []
        for row in rows:
            label = next((k for k in row if k in amount_labels), None)
            value = _parse_money_yuan(row.get(label)) if label is not None else None
            # Keep missing observations in their original trading window; dropping
            # them would backfill today's value or compress a 5/10-day aggregate.
            series.append((str(row.get("_date", "")), value))

        if not series or all(value is None for _, value in series):
            result["errors"].append("miaoxiang: empty capital flow series")
            return result

        # headName is usually in descending date order (latest first); sort by date explicitly here so aggregation is correct
        series.sort(key=lambda item: item[0], reverse=True)
        latest = series[0][1]
        # Window fields are only emitted once full trading-day data is available, to avoid labelling a partial historical total
        # as a 5-day/10-day net inflow (sparse history for recent IPOs would inject a wrong mid-term signal)
        def window_sum(size: int) -> Optional[float]:
            values = [value for _, value in series[:size]]
            if len(values) < size or any(value is None for value in values):
                return None
            return sum(values)

        inflow_5d = window_sum(5)
        inflow_10d = window_sum(10)

        result["stock_flow"] = {
            "main_net_inflow": latest,
            "inflow_5d": inflow_5d,
            "inflow_10d": inflow_10d,
        }
        result["status"] = "partial"
        result["source_chain"].append("miaoxiang:capital_flow")
        return result

    # ------------------------------------------------------------------
    # Daily K-line main chain: explicitly unsupported (fail fast so it doesn't eat fallback-chain time)
    # ------------------------------------------------------------------

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise DataFetchError("MiaoxiangFetcher 不提供日线行情数据（专用补充数据源）")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        raise DataFetchError("MiaoxiangFetcher 不提供日线行情数据（专用补充数据源）")
