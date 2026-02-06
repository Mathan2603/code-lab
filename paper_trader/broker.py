from typing import Dict, List, Union
from growwapi import Client


class GrowwPaperBroker:
    def __init__(self, token: str):
        self.client = Client(token)

    # ============================
    # INDEX LTP (SAFE)
    # ============================
    def get_index_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Always returns Dict[symbol, ltp]
        """
        response = self.client.get_ltp(
            segment=self.client.SEGMENT_CASH,
            exchange_trading_symbols=tuple(symbols),
        )

        # Groww quirk handling
        if isinstance(response, float):
            return {symbols[0]: response}

        if isinstance(response, dict):
            return response

        raise TypeError(f"Unexpected LTP response type: {type(response)}")

    # ============================
    # F&O MONTHLY LTP (SAFE)
    # ============================
    def get_fno_monthly_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Supports up to 50 symbols
        """
        response = self.client.get_ltp(
            segment=self.client.SEGMENT_FNO,
            exchange_trading_symbols=tuple(symbols),
        )

        if isinstance(response, float):
            return {symbols[0]: response}

        if isinstance(response, dict):
            return response

        raise TypeError(f"Unexpected FNO LTP response type: {type(response)}")

    # ============================
    # F&O WEEKLY LTP (SAFE – SINGLE ONLY)
    # ============================
    def get_fno_weekly_ltp(self, symbol: str) -> Dict[str, float]:
        """
        Weekly options do NOT work with get_ltp
        Uses get_quote (single symbol only)
        """
        quote = self.client.get_quote(
            segment=self.client.SEGMENT_FNO,
            exchange_trading_symbol=symbol,
        )

        if not quote or "last_price" not in quote:
            raise ValueError("Invalid weekly quote response")

        return {symbol: float(quote["last_price"])}
