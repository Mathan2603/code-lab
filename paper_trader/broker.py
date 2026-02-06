from __future__ import annotations

from typing import Any

from paper_trader.models import TokenStatus


class GrowwPaperBroker:
    """Thin adapter over GrowwAPI for paper-trading data calls only."""

    def __init__(self) -> None:
        from growwapi import GrowwAPI  # strict requirement

        self._sdk = GrowwAPI

    def _client(self, token: str) -> Any:
        return self._sdk(token)

    def validate_token(self, token_status: TokenStatus) -> tuple[bool, str]:
        try:
            client = self._client(token_status.token)
            client.get_ltp(
                segment=client.SEGMENT_CASH,
                exchange_trading_symbols=("NSE_NIFTY",),
            )
            return True, "valid"
        except Exception as exc:  # noqa: BLE001 - pass SDK message to UI
            return False, str(exc)

    def get_ltp(
        self,
        token: str,
        segment: Any,
        exchange_trading_symbols: tuple[str, ...],
    ) -> Any:
        client = self._client(token)
        return client.get_ltp(segment=segment, exchange_trading_symbols=exchange_trading_symbols)

    def get_quote(self, token: str, exchange_trading_symbol: str) -> Any:
        client = self._client(token)
        return client.get_quote(exchange_trading_symbol=exchange_trading_symbol)

    def get_ohlc(self, token: str, exchange_trading_symbol: str) -> Any:
        client = self._client(token)
        return client.get_ohlc(exchange_trading_symbol=exchange_trading_symbol)

    def get_option_chain(self, token: str, exchange_trading_symbol: str, expiry: str) -> Any:
        client = self._client(token)
        return client.get_option_chain(exchange_trading_symbol=exchange_trading_symbol, expiry=expiry)

    def get_greeks(self, token: str, exchange_trading_symbol: str) -> Any:
        client = self._client(token)
        return client.get_greeks(exchange_trading_symbol=exchange_trading_symbol)

    def get_contracts(self, token: str, exchange_trading_symbol: str, expiry: str) -> Any:
        client = self._client(token)
        return client.get_contracts(exchange_trading_symbol=exchange_trading_symbol, expiry=expiry)

    def get_instrument_by_groww_symbol(self, token: str, groww_symbol: str) -> Any:
        client = self._client(token)
        return client.get_instrument_by_groww_symbol(groww_symbol)

    def get_instrument_by_exchange_and_trading_symbol(
        self,
        token: str,
        exchange: str,
        trading_symbol: str,
    ) -> Any:
        client = self._client(token)
        return client.get_instrument_by_exchange_and_trading_symbol(exchange, trading_symbol)

    def get_instrument_by_exchange_token(self, token: str, exchange: str, exchange_token: str) -> Any:
        client = self._client(token)
        return client.get_instrument_by_exchange_token(exchange, exchange_token)

    def load_instruments_csv(self, token: str) -> Any:
        client = self._client(token)
        if hasattr(client, "_load_instruments"):
            return client._load_instruments()  # noqa: SLF001 - explicitly requested fallback
        raise RuntimeError("GrowwAPI._load_instruments() is unavailable in this SDK version.")

    def instrument_csv_url(self, token: str) -> str:
        client = self._client(token)
        return str(client.INSTRUMENT_CSV_URL)
