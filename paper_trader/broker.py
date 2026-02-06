from __future__ import annotations

from typing import Any

from paper_trader.models import TokenStatus


class GrowwPaperBroker:
    """Strict GrowwAPI adapter (paper-data only, no order methods)."""

    def __init__(self) -> None:
        from growwapi import GrowwAPI

        self._sdk = GrowwAPI

    def client(self, token: str) -> Any:
        return self._sdk(token)

    def validate_token(self, token_status: TokenStatus) -> tuple[bool, str]:
        """Classify token as usable / forbidden / expired-ish from SDK response."""
        try:
            groww = self.client(token_status.token)
            groww.get_ltp(groww.SEGMENT_CASH, ("NSE_NIFTY",))
            return True, "usable"
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if "forbidden" in msg or "403" in msg or "permission" in msg:
                return False, "forbidden_market_data"
            if "expired" in msg or "token" in msg or "unauthorized" in msg or "401" in msg:
                return False, "expired_or_invalid"
            return False, f"error:{str(exc)}"

    def get_ltp(self, token: str, segment: Any, symbols: tuple[str, ...]) -> Any:
        groww = self.client(token)
        return groww.get_ltp(segment, symbols)

    def get_quote(self, token: str, symbol: str) -> Any:
        groww = self.client(token)
        return groww.get_quote(symbol)

    def get_ohlc(self, token: str, symbol: str) -> Any:
        groww = self.client(token)
        return groww.get_ohlc(symbol)

    def get_greeks(self, token: str, symbol: str) -> Any:
        groww = self.client(token)
        return groww.get_greeks(symbol)

    def get_option_chain(self, token: str, exchange: Any, underlying: str, expiry_date: str) -> Any:
        groww = self.client(token)
        return groww.get_option_chain(exchange, underlying, expiry_date)

    def get_contracts(self, token: str, underlying: str, expiry_date: str) -> Any:
        groww = self.client(token)
        return groww.get_contracts(underlying, expiry_date)

    def get_instrument_by_groww_symbol(self, token: str, groww_symbol: str) -> Any:
        groww = self.client(token)
        return groww.get_instrument_by_groww_symbol(groww_symbol)

    def get_instrument_by_exchange_and_trading_symbol(self, token: str, exchange: str, trading_symbol: str) -> Any:
        groww = self.client(token)
        return groww.get_instrument_by_exchange_and_trading_symbol(exchange, trading_symbol)

    def get_instrument_by_exchange_token(self, token: str, exchange: str, exchange_token: str) -> Any:
        groww = self.client(token)
        return groww.get_instrument_by_exchange_token(exchange, exchange_token)

    def load_instruments(self, token: str) -> Any:
        groww = self.client(token)
        if hasattr(groww, "_load_instruments"):
            return groww._load_instruments()  # noqa: SLF001
        raise RuntimeError("Groww SDK does not expose _load_instruments in this runtime")

    def instrument_csv_url(self, token: str) -> str:
        groww = self.client(token)
        return str(groww.INSTRUMENT_CSV_URL)
