from __future__ import annotations
from typing import Any
from growwapi import GrowwAPI


class GrowwPaperBroker:
    """
    Thin wrapper over GrowwAPI.
    IMPORTANT:
    - Always pass symbols as tuple
    - get_ltp may return float or dict → handled upstream
    """

    def __init__(self) -> None:
        self._sdk = GrowwAPI

    def client(self, token: str) -> GrowwAPI:
        return self._sdk(token)

    def validate_token(self, token: str) -> None:
        groww = self.client(token)
        groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY",),
        )

    def get_ltp(
        self,
        token: str,
        segment: Any,
        symbols: tuple[str, ...],
    ) -> Any:
        groww = self.client(token)
        return groww.get_ltp(
            segment=segment,
            exchange_trading_symbols=symbols,
        )
