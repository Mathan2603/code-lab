from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LtpResponse:
    symbol: str
    price: float


class GrowwBroker:
    def __init__(self, token: str, client: Any | None = None) -> None:
        self._token = token
        self._client = client or self._create_client(token)

    @staticmethod
    def _create_client(token: str) -> Any:
        from groww import GrowwClient

        return GrowwClient(token)

    def get_expiries(self, symbol: str) -> list[str]:
        return self._client.get_expiries(symbol)

    def get_contracts(self, symbol: str, expiry: str) -> list[dict[str, Any]]:
        return self._client.get_contracts(symbol, expiry)

    def get_ltp(self, segment: str, symbols: list[str]) -> dict[str, float]:
        response = self._client.get_ltp(segment=segment, symbols=symbols)
        prices: dict[str, float] = {}
        for item in response:
            prices[item["symbol"]] = float(item["ltp"])
        return prices

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client.place_order(payload)
