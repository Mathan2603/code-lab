from __future__ import annotations
import threading
import time
from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.utils import now_ist, token_preview
from paper_trader.models import EngineSnapshot


def extract_ltp(payload, symbol: str) -> float:
    if isinstance(payload, (int, float)):
        return float(payload)

    if isinstance(payload, dict):
        val = payload.get(symbol)
        if isinstance(val, dict):
            return float(val.get("ltp"))
        return float(val)

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

        self._thread = None
        self._stop = threading.Event()

        self.active_token = ""
        self.logs: list[str] = []
        self.last_prices: dict[str, float] = {}

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
                ts = self.tokens.next()
                self.active_token = ts.token

                groww = self.broker.client(ts.token)
                resp = self.broker.get_ltp(
                    token=ts.token,
                    segment=groww.SEGMENT_CASH,
                    symbols=("NSE_NIFTY", "NSE_BANKNIFTY"),
                )

                self.last_prices = {
                    "NSE_NIFTY": extract_ltp(resp, "NSE_NIFTY"),
                    "NSE_BANKNIFTY": extract_ltp(resp, "NSE_BANKNIFTY"),
                }

                self.log(f"LTP fetched {self.last_prices}")

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
            last_prices=self.last_prices,
        )
