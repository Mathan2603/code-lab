from __future__ import annotations
from typing import Any


class GrowwPaperBroker:
    """
    Correct Groww API adapter (paper trading, data-only).
    Compatible with Streamlit Cloud.
    """

    def __init__(self) -> None:
        from growwapi import GrowwAPI
        self._GrowwAPI = GrowwAPI

    def client(self, token: str):
        return self._GrowwAPI(token)

    # --------------------------------------------------
    # TOKEN VALIDATION
    # --------------------------------------------------
    def validate_token(self, token: str) -> tuple[bool, str]:
        try:
            groww = self.client(token)

            # ✅ Correct Groww validation call
            groww.get_ltp(
                segment="CASH",
                symbols=["NSE_NIFTY"]
            )

            return True, "valid"

        except Exception as e:
            return False, str(e)

    # --------------------------------------------------
    # MARKET DATA
    # --------------------------------------------------
    def get_ltp(self, token: str, segment: str, symbols: list[str]) -> dict:
        groww = self.client(token)
        return groww.get_ltp(segment=segment, symbols=symbols)

    def get_expiries(self, token: str, symbol: str) -> list[str]:
        groww = self.client(token)
        return groww.get_expiries(symbol)

    def get_contracts(self, token: str, symbol: str, expiry: str) -> list[dict]:
        groww = self.client(token)
        return groww.get_contracts(symbol, expiry)

    def get_ohlc(self, token: str, symbol: str):
        groww = self.client(token)
        return groww.get_ohlc(symbol)

    def load_instruments(self, token: str):
        groww = self.client(token)

        if hasattr(groww, "_load_instruments"):
            return groww._load_instruments()

        raise RuntimeError("Groww SDK does not expose instrument loader")
