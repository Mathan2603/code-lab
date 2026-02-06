from __future__ import annotations

from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class InMemoryLogger:
    def __init__(self, capacity: int = 200) -> None:
        self._buffer: deque[str] = deque(maxlen=capacity)

    def info(self, msg: str) -> None:
        ts = datetime.now(tz=IST).strftime("%Y-%m-%d %H:%M:%S")
        self._buffer.append(f"[{ts}] {msg}")

    def tail(self, n: int = 50) -> list[str]:
        return list(self._buffer)[-n:]


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def token_preview(token: str) -> str:
    if len(token) <= 8:
        return token
    return f"{token[:4]}...{token[-4:]}"
