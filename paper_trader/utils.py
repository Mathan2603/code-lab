from __future__ import annotations

from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> datetime:
    """Return current IST datetime"""
    return datetime.now(IST)


def log(message: str) -> str:
    """
    Standard log formatter used across app + engine
    Returns formatted string (does NOT print)
    """
    ts = now_ist().strftime("%H:%M:%S")
    return f"[{ts}] {message}"
