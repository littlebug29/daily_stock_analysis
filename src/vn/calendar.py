# -*- coding: utf-8 -*-
"""Vietnamese trading calendar (CONTEXT.md: Trading Day, Market Phase).

exchange-calendars has no Vietnamese calendar, so closures come from the
repo-maintained ``data/holidays.json``. A year missing from that file falls back
to weekday-only checks and logs a warning, matching upstream's fail-open stance.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Ho_Chi_Minh"
TZ = ZoneInfo(TIMEZONE)

_HOLIDAYS_PATH = Path(__file__).with_name("data") / "holidays.json"


@lru_cache(maxsize=1)
def _load() -> Dict[int, Dict[date, str]]:
    raw = json.loads(_HOLIDAYS_PATH.read_text(encoding="utf-8"))
    years: Dict[int, Dict[date, str]] = {}
    for year, block in (raw.get("years") or {}).items():
        years[int(year)] = {
            date.fromisoformat(item["date"]): item.get("name", "")
            for item in block.get("closures", [])
        }
    return years


def is_trading_day(day: date) -> bool:
    """Weekday that is not an announced closure."""
    if day.weekday() >= 5:
        return False
    closures = _load().get(day.year)
    if closures is None:
        logger.warning(
            "VN holiday list has no entry for %s; treating weekdays as Trading Days. "
            "Update src/vn/data/holidays.json.",
            day.year,
        )
        return True
    return day not in closures


def is_year_covered(day: date) -> bool:
    return day.year in _load()


def next_trading_day(day: date) -> date:
    cursor = day + timedelta(days=1)
    while not is_trading_day(cursor):
        cursor += timedelta(days=1)
    return cursor


def trading_days_between(start: date, end: date) -> List[date]:
    """Inclusive list of Trading Days in ``[start, end]``."""
    days: List[date] = []
    cursor = start
    while cursor <= end:
        if is_trading_day(cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def today() -> date:
    return datetime.now(TZ).date()
