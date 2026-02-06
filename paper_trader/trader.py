from __future__ import annotations

import threading
import time
from datetime import time as dtime
from typing import Any

from paper_trader.broker import GrowwPaperBroker
from paper_trader.data_store import CsvStore
from paper_trader.models import EngineSnapshot, Position, TokenStatus
from paper_trader.risk import RiskManager
from paper_trader.strategy import DirectionalTrend
from paper_trader.token_pool import TokenPool
from paper_trader.utils import InMemoryLogger, now_ist, token_preview


class PaperTraderEngine:
    def __init__(
        self,
        broker: GrowwPaperBroker,
        token_pool: TokenPool,
        poll_seconds: int = 5,
        quantity: int = 1,
    ) -> None:
        self.broker = broker
        self.tokens = token_pool
        self.poll_seconds = max(5, poll_seconds)
        self.quantity = max(1, quantity)

        self.logger = InMemoryLogger(capacity=500)
        self.store = CsvStore()
        self.risk = RiskManager()

        self.trend = {
            "NSE_NIFTY": DirectionalTrend(),
            "NSE_BANKNIFTY": DirectionalTrend(),
        }

        self.positions: list[Position] = []
        self.realized_pnl = 0.0

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active_token: str = ""

        # 🔥 NEW: live LTP cache
        self.latest_ltps: dict[str, float] = {}

    # ---------------- TOKEN ----------------

    def validate_tokens(self) -> list[tuple[str, bool, str]]:
        rows = []
        for status in self.tokens.statuses():
            try:
                client = self.broker._client(status.token)
                client.get_ltp(
                    segment=client.SEGMENT_CASH,
                    exchange_trading_symbols=("NSE_NIFTY",),
                )
                rows.append((token_preview(status.token), True, "valid"))
                self.logger.info(f"token_validation {token_preview(status.token)} => valid")
            except Exception as exc:
                self.tokens.mark_failed(status.token, str(exc))
                rows.append((token_preview(status.token), False, str(exc)))
                self.logger.info(
                    f"token_validation {token_preview(status.token)} => {exc}"
                )
        return rows

    # ---------------- ENGINE CONTROL ----------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("engine started")

    def stop(self) -> None:
        self._stop.set()
        self.logger.info("engine stopped")

    # ---------------- SNAPSHOT ----------------

    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot(
            running=bool(self._thread and self._thread.is_alive()),
            active_token_preview=token_preview(self._active_token)
            if self._active_token
            else "-",
            realized_pnl=self.realized_pnl,
            unrealized_pnl=0.0,
            open_positions=list(self.positions),
            logs=self.logger.tail(50),
        )

    # 🔥 NEW: expose LTPs
    def get_latest_ltps(self) -> dict[str, float]:
        return dict(self.latest_ltps)

    # ---------------- LOOP ----------------

    def _next_token(self) -> TokenStatus:
        status = self.tokens.choose_next()
        self._active_token = status.token
        return status

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                now = now_ist().time()
                if now < dtime(9, 15):
                    time.sleep(self.poll_seconds)
                    continue

                self._poll_underlyings()

            except Exception as exc:
                self.logger.info(f"engine error: {exc}")

            time.sleep(self.poll_seconds)

    # ---------------- MARKET DATA ----------------

    def _poll_underlyings(self) -> None:
        token = self._next_token().token
        client = self.broker._client(token)

        resp = client.get_ltp(
            segment=client.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY"),
        )

        for symbol, payload in resp.items():
            ltp = float(payload["ltp"])
            self.latest_ltps[symbol] = ltp
            self.logger.info(f"LTP {symbol} = {ltp}")
