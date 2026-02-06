from __future__ import annotations
from typing import Dict, List

from growwapi import Client


class GrowwPaperBroker:
    def __init__(self, token: str):
        self.client = Client(token)

    # ===============================
    # CASH / INDEX LTP
    # ===============================
    def get_index_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Example symbols:
        NSE_NIFTY
        NSE_BANKNIFTY
        """
        response = self.client.get_ltp(
            segment=self.client.SEGMENT_CASH,
            exchange_trading_symbols=tuple(symbols),
        )

        return {item["symbol"]: float(item["ltp"]) for item in response}

    # ===============================
    # F&O MONTHLY OPTIONS (BATCH)
    # ===============================
    def get_monthly_option_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Example:
        NSE_NIFTY26FEB24500CE
        Supports up to 50 symbols
        """
        response = self.client.get_ltp(
            segment=self.client.SEGMENT_FNO,
            exchange_trading_symbols=tuple(symbols),
        )

        return {item["symbol"]: float(item["ltp"]) for item in response}

    # ===============================
    # F&O WEEKLY OPTIONS (SINGLE)
    # ===============================
    def get_weekly_option_ltp(self, symbol: str) -> float:
        """
        Example:
        NIFTY2621020400CE

        Groww restriction:
        - Only ONE weekly symbol per request
        - Must use get_quote or get_ohlc
        """
        quote = self.client.get_quote(
            segment=self.client.SEGMENT_FNO,
            exchange_trading_symbol=symbol,
        )
        return float(quote["ltp"])
