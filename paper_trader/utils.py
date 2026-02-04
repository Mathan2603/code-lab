from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def time_in_range(current: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


@dataclass(frozen=True)
class MarketTimes:
    entry_after: time
    exit_before: time
    market_open: time
    market_close: time


def default_market_times() -> MarketTimes:
    return MarketTimes(
        entry_after=time(10, 15),
        exit_before=time(15, 20),
        market_open=time(9, 15),
        market_close=time(15, 30),
    )
