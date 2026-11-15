# -*- coding: utf-8 -*-
"""
===================================
Data source strategy layer - package initialization
===================================

This package uses the strategy pattern to manage multiple data sources, providing:
1. A unified data-fetching interface
2. Automatic failover
3. Anti-ban rate-limiting strategy

Data source priority (adjusted dynamically):
[When TUSHARE_TOKEN is configured]
1. TushareFetcher (Priority 0) - 🔥 highest priority (dynamically promoted)
2. EfinanceFetcher (Priority 0) - same priority
3. AkshareFetcher (Priority 1) - from the akshare library
4. PytdxFetcher (Priority 2) - from the pytdx library (TDX / Tongdaxin)
5. BaostockFetcher (Priority 3) - from the baostock library
6. YfinanceFetcher (Priority 4) - from the yfinance library
7. TencentFetcher (Priority 5) - direct Tencent daily K-line, final fallback

[When TUSHARE_TOKEN is not configured]
1. EfinanceFetcher (Priority 0) - highest priority, from the efinance library
2. AkshareFetcher (Priority 1) - from the akshare library
3. PytdxFetcher (Priority 2) - from the pytdx library (TDX / Tongdaxin)
4. TushareFetcher (Priority 2) - from the tushare library (unavailable)
5. BaostockFetcher (Priority 3) - from the baostock library
6. YfinanceFetcher (Priority 4) - from the yfinance library
7. TencentFetcher (Priority 5) - direct Tencent daily K-line, final fallback
8. LongbridgeFetcher (Priority 5) - Longbridge OpenAPI (US/HK fallback; markets do not overlap with Tencent)

Note: a smaller priority number means higher priority; equal priorities keep initialization order
"""

from .base import BaseFetcher, DataFetcherManager
from .efinance_fetcher import EfinanceFetcher
from .tencent_fetcher import TencentFetcher
from .akshare_fetcher import AkshareFetcher, is_hk_stock_code
from .tushare_fetcher import TushareFetcher
from .pytdx_fetcher import PytdxFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher
from .longbridge_fetcher import LongbridgeFetcher
from .finnhub_fetcher import FinnhubFetcher
from .alphavantage_fetcher import AlphaVantageFetcher
from .us_index_mapping import is_us_index_code, is_us_stock_code, get_us_index_yf_symbol, US_INDEX_MAPPING

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'EfinanceFetcher',
    'TencentFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'PytdxFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
    'LongbridgeFetcher',
    'FinnhubFetcher',
    'AlphaVantageFetcher',
    'is_us_index_code',
    'is_us_stock_code',
    'is_hk_stock_code',
    'get_us_index_yf_symbol',
    'US_INDEX_MAPPING',
]
