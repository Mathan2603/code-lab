from __future__ import annotations

from datetime import timedelta
from threading import Lock

from paper_trader.models import TokenStatus
from paper_trader.utils import now_ist


class TokenPool:
    def __init__(self, tokens: list[str], min_gap_seconds: int = 5) -> None:
        if not tokens:
            raise ValueError("At least one access token is required")
        if len(tokens) > 5:
            raise ValueError("Maximum 5 access tokens are supported")
        self._statuses = [TokenStatus(token=t.strip()) for t in tokens if t.strip()]
        if not self._statuses:
            raise ValueError("Token file has no usable token")
        self._min_gap = timedelta(seconds=min_gap_seconds)
        self._cursor = 0
        self._lock = Lock()

    def statuses(self) -> list[TokenStatus]:
        with self._lock:
            return [TokenStatus(**vars(s)) for s in self._statuses]

    def mark_failed(self, token: str, error: str) -> None:
        with self._lock:
            for s in self._statuses:
                if s.token == token:
                    s.active = False
                    s.last_error = error
                    return

    def choose_next(self) -> TokenStatus:
        with self._lock:
            active = [s for s in self._statuses if s.active]
            if not active:
                raise RuntimeError("All tokens inactive")

            attempts = 0
            while attempts < len(self._statuses):
                status = self._statuses[self._cursor]
                self._cursor = (self._cursor + 1) % len(self._statuses)
                attempts += 1
                if not status.active:
                    continue
                now = now_ist()
                if status.last_used_at and now - status.last_used_at < self._min_gap:
                    continue
                status.last_used_at = now
                status.calls_made += 1
                return TokenStatus(**vars(status))

            raise RuntimeError("All active tokens are in cooldown")
