from typing import Dict, List
from growwapi import GrowwAPI


class GrowwPaperBroker:
    def __init__(self, token: str):
        # Correct Groww SDK usage
        self.client = GrowwAPI(token)

    # ============================
    # INDEX LTP (CASH SEGMENT)
    # ============================
    def get_index_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Always returns Dict[symbol, ltp]
        """
        response = self.client.get_ltp(
            segment=self.client.SEGMENT_CASH,
            exchange_trading_symbols=tuple(symbols),
        )

        # Groww returns float for single symbol
        if isinstance(response, float):
            return {symbols[0]: response}

        if isinstance(response, dict):
            return response

        raise TypeError(f"Unexpected LTP response type: {type(response)}")

    # ============================
    # F&O MONTHLY OPTIONS (MULTI – UP TO 50)
    # ============================
    def get_fno_monthly_ltp(self, symbols: List[str]) -> Dict[str, float]:
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
    # F&O WEEKLY OPTIONS (SINGLE ONLY)
    # ============================
    def get_fno_weekly_ltp(self, symbol: str) -> Dict[str, float]:
        quote = self.client.get_quote(
            segment=self.client.SEGMENT_FNO,
            exchange_trading_symbol=symbol,
        )

        if not isinstance(quote, dict) or "last_price" not in quote:
            raise ValueError("Invalid weekly quote response")

        return {symbol: float(quote["last_price"])}
