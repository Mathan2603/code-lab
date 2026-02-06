from __future__ import annotations
from typing import Any


class GrowwPaperBroker:
    """
    Correct Groww API adapter (paper trading, data-only).
    """

    def __init__(self) -> None:
        from growwapi import Client
        self._Client = Client

    def client(self, token: str):
        return self._Client(token)

    # -------------------------------------------------
    # TOKEN VALIDATION (THIS WAS YOUR BUG)
    # -------------------------------------------------
    def validate_token(self, token: str) -> tuple[bool, str]:
        try:
            client = self.client(token)

            # ✅ Correct Groww call
            client.get_ltp(
                segment="CASH",
                symbols=["NSE_NIFTY"]
            )

            return True, "valid"

        except Exception as e:
            return False, str(e)

    # -------------------------------------------------
    # MARKET DATA
    # -------------------------------------------------
    def get_ltp(self, token: str, segment: str, symbols: list[str]) -> list[dict]:
        client = self.client(token)
        return client.get_ltp(segment=segment, symbols=symbols)

    def get_expiries(self, token: str, symbol: str) -> list[str]:
        client = self.client(token)
        return client.get_expiries(symbol)

    def get_contracts(self, token: str, symbol: str, expiry: str) -> list[dict]:
        client = self.client(token)
        return client.get_contracts(symbol, expiry)

    def get_ohlc(self, token: str, symbol: str):
        client = self.client(token)
        return client.get_ohlc(symbol)

    def load_instruments(self, token: str):
        client = self.client(token)

        if hasattr(client, "_load_instruments"):
            return client._load_instruments()

        raise RuntimeError("Groww SDK does not expose instrument loader")
