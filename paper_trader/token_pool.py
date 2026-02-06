from __future__ import annotations
from datetime import timedelta
from threading import Lock
from paper_trader.models import TokenStatus
from paper_trader.utils import now_ist


class TokenPool:
    def __init__(self, tokens: list[str], min_gap_seconds: int = 5) -> None:
        if not tokens:
            raise ValueError("At least one access token required")
        if len(tokens) > 5:
            raise ValueError("Maximum 5 tokens allowed")

        self._tokens = [TokenStatus(token=t.strip()) for t in tokens if t.strip()]
        self._gap = timedelta(seconds=min_gap_seconds)
        self._cursor = 0
        self._lock = Lock()

    def statuses(self) -> list[TokenStatus]:
        with self._lock:
            return [TokenStatus(**vars(t)) for t in self._tokens]

    def mark_failed(self, token: str, error: str) -> None:
        with self._lock:
            for t in self._tokens:
                if t.token == token:
                    t.active = False
                    t.last_error = error
                    return

    def next(self) -> TokenStatus:
        with self._lock:
            for _ in range(len(self._tokens)):
                t = self._tokens[self._cursor]
                self._cursor = (self._cursor + 1) % len(self._tokens)

                if not t.active:
                    continue

                now = now_ist()
                if t.last_used_at and now - t.last_used_at < self._gap:
                    continue

                t.last_used_at = now
                t.calls_made += 1
                return TokenStatus(**vars(t))

            raise RuntimeError("All tokens inactive or cooling down")
