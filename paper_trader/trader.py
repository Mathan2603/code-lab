from __future__ import annotations

import threading
import time
from typing import Dict

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.utils import now_ist, token_preview
from paper_trader.models import EngineSnapshot


def extract_ltp(payload, symbol: str) -> float:
    if isinstance(payload, (int, float)):
        return float(payload)

    if isinstance(payload, dict):
        value = payload.get(symbol)
        if isinstance(value, dict):
            return float(value.get("ltp"))
        return float(value)

    raise RuntimeError(f"Unable to extract LTP for {symbol}")


class PaperTraderEngine:
    def __init__(
        self,
        broker: GrowwPaperBroker,
        token_pool: TokenPool,
        poll_seconds: int,
        quantity: int,
    ) -> None:
        self.broker = broker
        self.tokens = token_pool
        self.poll_seconds = poll_seconds
        self.quantity = quantity

        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

        self.active_token: str = ""
        self.logs: list[str] = []

        self.cash_prices: Dict[str, float] = {}
        self.fno_prices: Dict[str, float] = {}

    def log(self, msg: str) -> None:
        self.logs.append(f"[{now_ist().strftime('%H:%M:%S')}] {msg}")
        self.logs = self.logs[-50:]

    def validate_tokens(self):
        rows = []
        for t in self.tokens.statuses():
            try:
                self.broker.validate_token(t.token)
                rows.append((token_preview(t.token), True, "valid"))
                self.log(f"token_validation {token_preview(t.token)} => valid")
            except Exception as e:
                self.tokens.mark_failed(t.token, str(e))
                rows.append((token_preview(t.token), False, str(e)))
                self.log(f"token_validation {token_preview(t.token)} => {e}")
        return rows

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.log("engine started")

    def stop(self):
        self._stop.set()
        self.log("engine stopped")

    def _run(self):
        while not self._stop.is_set():
            try:
                token_status = self.tokens.next()
                self.active_token = token_status.token

                groww = self.broker.client(token_status.token)

                # -------- CASH LTP --------
                cash_resp = self.broker.get_ltp(
                    token=token_status.token,
                    segment=groww.SEGMENT_CASH,
                    symbols=("NSE_NIFTY", "NSE_BANKNIFTY"),
                )

                nifty = extract_ltp(cash_resp, "NSE_NIFTY")
                banknifty = extract_ltp(cash_resp, "NSE_BANKNIFTY")

                self.cash_prices = {
                    "NSE_NIFTY": nifty,
                    "NSE_BANKNIFTY": banknifty,
                }

                # -------- F&O LTP (ATM OPTIONS) --------
                nifty_atm = round(nifty / 50) * 50
                bank_atm = round(banknifty / 100) * 100

                fno_symbols = (
                    f"NIFTY25FEB{int(nifty_atm)}CE",
                    f"BANKNIFTY25FEB{int(bank_atm)}CE",
                )

                fno_resp = self.broker.get_ltp(
                    token=token_status.token,
                    segment=groww.SEGMENT_FNO,
                    symbols=fno_symbols,
                )

                self.fno_prices = {
                    fno_symbols[0]: extract_ltp(fno_resp, fno_symbols[0]),
                    fno_symbols[1]: extract_ltp(fno_resp, fno_symbols[1]),
                }

                self.log(
                    f"LTP fetched CASH={self.cash_prices} FNO={self.fno_prices}"
                )

            except Exception as e:
                self.log(f"engine error: {e}")

            time.sleep(self.poll_seconds)

    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot(
            running=self._thread.is_alive() if self._thread else False,
            active_token_preview=token_preview(self.active_token),
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            open_positions=[],
            logs=self.logs,
            last_prices={
                **self.cash_prices,
                **self.fno_prices,
            },
        )
