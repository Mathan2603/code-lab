from __future__ import annotations

from datetime import timedelta
from threading import Lock
from typing import List

from paper_trader.models import TokenStatus
from paper_trader.utils import now_ist


class TokenPool:
    """
    TokenPool manages up to 5 Groww access tokens with:
    - cooldown enforcement
    - failure marking
    - round-robin selection
    """

    def __init__(self, tokens: List[str], min_gap_seconds: int = 5) -> None:
        if not tokens:
            raise ValueError("At least one access token is required")

        cleaned = [t.strip() for t in tokens if t.strip()]
        if not cleaned:
            raise ValueError("Token input has no usable tokens")

        if len(cleaned) > 5:
            raise ValueError("Maximum 5 access tokens are supported")

        self._statuses: List[TokenStatus] = [
            TokenStatus(token=t) for t in cleaned
        ]

        self._min_gap = timedelta(seconds=min_gap_seconds)
        self._cursor = 0
        self._lock = Lock()

    # ------------------------------------------------------------------
    # SAFE READ-ONLY SNAPSHOT (for UI)
    # ------------------------------------------------------------------
    def statuses(self) -> List[TokenStatus]:
        """
        Returns a COPY of token statuses.
        Never return internal references.
        """
        with self._lock:
            return [
                TokenStatus(**vars(s))
                for s in self._statuses
            ]

    # ------------------------------------------------------------------
    # FAILURE HANDLING
    # ------------------------------------------------------------------
    def mark_failed(self, token: str, error: str) -> None:
        """
        Mark a token inactive and store error as STRING ONLY.
        """
        with self._lock:
            for s in self._statuses:
                if s.token == token:
                    s.active = False
                    s.last_error = str(error)
                    return

    # ------------------------------------------------------------------
    # TOKEN ROTATION
    # ------------------------------------------------------------------
    def choose_next(self) -> TokenStatus:
        """
        Select next usable token respecting cooldown.
        Returns a COPY of TokenStatus.
        """
        with self._lock:
            active_tokens = [s for s in self._statuses if s.active]
            if not active_tokens:
                raise RuntimeError("All tokens are inactive")

            attempts = 0
            now = now_ist()

            while attempts < len(self._statuses):
                status = self._statuses[self._cursor]
                self._cursor = (self._cursor + 1) % len(self._statuses)
                attempts += 1

                if not status.active:
                    continue

                if status.last_used_at:
                    if now - status.last_used_at < self._min_gap:
                        continue

                # update internal state
                status.last_used_at = now
                status.calls_made += 1

                # RETURN COPY — NEVER INTERNAL OBJECT
                return TokenStatus(**vars(status))

            raise RuntimeError("All active tokens are in cooldown")
