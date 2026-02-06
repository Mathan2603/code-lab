from typing import Dict, List
from growwapi import GrowwAPI


class GrowwPaperBroker:
    def __init__(self, access_token: str):
        self.client = GrowwAPI(access_token)

    # ============================
    # INDEX LTP (CASH)
    # ============================
    def get_index_ltp(self, symbols: List[str]) -> Dict[str, float]:
        response = self.client.get_ltp(
            segment="CASH",
            exchange_trading_symbols=tuple(symbols),
        )

        # Normalize response
        return {
            sym: float(data["last_price"])
            for sym, data in response.items()
        }

    # ============================
    # F&O MONTHLY (MULTI SYMBOL)
    # ============================
    def get_fno_monthly_ltp(self, symbols: List[str]) -> Dict[str, float]:
        response = self.client.get_ltp(
            segment="FNO",
            exchange_trading_symbols=tuple(symbols),
        )

        return {
            sym: float(data["last_price"])
            for sym, data in response.items()
        }

    # ============================
    # F&O WEEKLY (SINGLE SYMBOL ONLY)
    # ============================
    def get_fno_weekly_ltp(self, symbol: str) -> Dict[str, float]:
        quote = self.client.get_quote(
            trading_symbol=symbol  # ✅ CORRECT PARAM NAME
        )

        return {
            symbol: float(quote["last_price"])
        }
