from __future__ import annotations
import time
from typing import Dict, List

from paper_trader.broker import GrowwPaperBroker
from paper_trader.utils import log


class PaperTraderEngine:
    def __init__(self, broker: GrowwPaperBroker, poll_seconds: int):
        self.broker = broker
        self.poll_seconds = poll_seconds
        self.running = False

    def start(self):
        self.running = True
        log("engine started")

        while self.running:
            try:
                # -----------------------
                # INDEX LTP
                # -----------------------
                index_ltp = self.broker.get_index_ltp(
                    ["NSE_NIFTY", "NSE_BANKNIFTY"]
                )
                log(f"LTP fetched {index_ltp}")

                # -----------------------
                # MONTHLY OPTIONS (batch)
                # -----------------------
                monthly_symbols = [
                    "NSE_NIFTY26FEB24500CE",
                    "NSE_NIFTY26FEB24600CE",
                ]
                monthly_ltp = self.broker.get_monthly_option_ltp(monthly_symbols)
                log(f"Monthly option LTP {monthly_ltp}")

                # -----------------------
                # WEEKLY OPTIONS (single)
                # -----------------------
                weekly_symbol = "NIFTY2621020400CE"
                weekly_ltp = self.broker.get_weekly_option_ltp(weekly_symbol)
                log(f"Weekly option LTP {{'{weekly_symbol}': {weekly_ltp}}}")

            except Exception as e:
                log(f"engine error: {e}")

            time.sleep(self.poll_seconds)

    def stop(self):
        self.running = False
        log("engine stopped")
