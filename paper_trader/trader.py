from __future__ import annotations

import threading
import time
from typing import List, Tuple

from paper_trader.broker import GrowwPaperBroker
from paper_trader.models import EngineSnapshot, TokenStatus
from paper_trader.token_pool import TokenPool
from paper_trader.utils import InMemoryLogger, token_preview


class PaperTraderEngine:
    def __init__(
        self,
        broker: GrowwPaperBroker,
        token_pool: TokenPool,
        poll_seconds: int,
        quantity: int,
    ) -> None:
        self._broker = broker
        self._token_pool = token_pool
        self._poll_seconds = poll_seconds
        self._quantity = quantity

        self._logger = InMemoryLogger()
        self._running = False
        self._thread: threading.Thread | None = None

        self._realized_pnl = 0.0
        self._unrealized_pnl = 0.0
        self._active_token_preview: str | None = None

    # --------------------------------------------------
    # ✅ TOKEN VALIDATION (FIXED)
    # --------------------------------------------------
    def validate_tokens(self) -> List[Tuple[str, bool, str]]:
        """
        Returns rows for UI:
        (token_preview, usable, status_message)
        """
        rows: List[Tuple[str, bool, str]] = []

        for status in self._token_pool.statuses():
            preview = token_preview(status.token)

            try:
                ok, msg = self._broker.validate_token(status)

                if ok:
                    rows.append((preview, True, "valid"))
                    self._logger.info(f"token_validation {preview} => valid")
                else:
                    rows.append((preview, False, msg))
                    self._logger.info(f"token_validation {preview} => {msg}")

            except Exception as exc:
                err = str(exc)
                rows.append((preview, False, err))
                self._logger.info(f"token_validation {preview} => {err}")

        return rows

    # --------------------------------------------------
    # ENGINE CONTROL
    # --------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._logger.info("engine started")

    def stop(self) -> None:
        self._running = False
        self._logger.info("engine stopped")

    # --------------------------------------------------
    # MAIN LOOP (PAPER ONLY)
    # --------------------------------------------------
    def _run_loop(self) -> None:
        while self._running:
            try:
                token_status = self._token_pool.choose_next()
                self._active_token_preview = token_preview(token_status.token)

                # 🚧 PAPER TRADING PLACEHOLDER
                # Strategy logic will go here later

            except Exception as exc:
                self._logger.info(f"engine_error {exc}")

            time.sleep(self._poll_seconds)

    # --------------------------------------------------
    # SNAPSHOT FOR UI
    # --------------------------------------------------
    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot(
            running=self._running,
            active_token_preview=self._active_token_preview or "",
            realized_pnl=self._realized_pnl,
            unrealized_pnl=self._unrealized_pnl,
            open_positions=[],
            logs=self._logger.tail(50),
        )
