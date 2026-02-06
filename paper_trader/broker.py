from __future__ import annotations
from typing import Any, Tuple

from paper_trader.models import TokenStatus


class GrowwPaperBroker:
    def __init__(self) -> None:
        from growwapi import GrowwAPI
        self._client_cls = GrowwAPI

    def _client(self, token: str):
        return self._client_cls(token)

    def validate_token(self, status: TokenStatus) -> Tuple[bool, str]:
        """
        IMPORTANT:
        - NEVER return TokenStatus
        - ONLY return (bool, str)
        """
        try:
            client = self._client(status.token)

            # minimal safe validation call
            client.get_ltp(
                segment=client.SEGMENT_CASH,
                exchange_trading_symbols=("NSE_NIFTY",),
            )

            return True, "valid"

        except Exception as exc:
            return False, str(exc)
