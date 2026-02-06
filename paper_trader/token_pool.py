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

        self._statuses: list[TokenStatus] = [
            TokenStatus(token=t.strip()) for t in tokens if t.strip()
        ]

        if not self._statuses:
            raise ValueError("Token file has no usable token")

        self._min_gap = timedelta(seconds=min_gap_seconds)
        self._cursor = 0
        self._lock = Lock()

    # ----------------------------
    # READ-ONLY SNAPSHOT (UI SAFE)
    # ----------------------------
    def statuses(self) -> list[TokenStatus]:
        with self._lock:
            return [
                TokenStatus(
                    token=s.token,
                    active=s.active,
                    last_used_at=s.last_used_at,
                    last_error=s.last_error,
                    calls_made=s.calls_made,
                )
                for s in self._statuses
            ]

    # ----------------------------
    # MARK TOKEN AS FAILED
    # ----------------------------
    def mark_failed(self, token: str, error: str) -> None:
        with self._lock:
            for s in self._statuses:
                if s.token == token:
                    s.active = False
                    s.last_error = error
                    return

    # ----------------------------
    # ROTATING TOKEN PICKER
    # ----------------------------
    def choose_next(self) -> TokenStatus:
        with self._lock:
            if not any(s.active for s in self._statuses):
                raise RuntimeError("All tokens are inactive")

            attempts = 0
            total = len(self._statuses)

            while attempts < total:
                status = self._statuses[self._cursor]
                self._cursor = (self._cursor + 1) % total
                attempts += 1

                if not status.active:
                    continue

                now = now_ist()
                if status.last_used_at and now - status.last_used_at < self._min_gap:
                    continue

                status.last_used_at = now
                status.calls_made += 1
                return status

            # fallback: pick first active token even if cooldown not met
            for status in self._statuses:
                if status.active:
                    status.last_used_at = now_ist()
                    status.calls_made += 1
                    return status

            raise RuntimeError("No usable token found")
