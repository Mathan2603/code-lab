from __future__ import annotations
from typing import Dict, List

from growwapi import GrowwAPI


class GrowwPaperBroker:
    """
    Thin wrapper over GrowwAPI
    Paper-trading only (NO order placement)
    """

    def __init__(self, token: str) -> None:
        self.client = GrowwAPI(token)

    # =========================
    # INDEX LTP (CASH)
    # =========================
    def get_index_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Example symbols:
        NSE_NIFTY
        NSE_BANKNIFTY
        """
        resp = self.client.get_ltp(
            segment=self.client.SEGMENT_CASH,
            exchange_trading_symbols=tuple(symbols),
        )

        return {
            sym: float(data["ltp"])
            for sym, data in resp.items()
            if "ltp" in data
        }

    # =========================
    # MONTHLY OPTIONS (FNO, BATCH)
    # =========================
    def get_monthly_option_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Supports up to 50 symbols per request
        Example:
        NSE_NIFTY26FEB24500CE
        """
        resp = self.client.get_ltp(
            segment=self.client.SEGMENT_FNO,
            exchange_trading_symbols=tuple(symbols),
        )

        return {
            sym: float(data["ltp"])
            for sym, data in resp.items()
            if "ltp" in data
        }

    # =========================
    # WEEKLY OPTIONS (SINGLE ONLY)
    # =========================
    def get_weekly_option_ltp(self, symbol: str) -> float:
        """
        Weekly options DO NOT work with get_ltp()
        Must use get_quote() or get_ohlc()
        Example:
        NIFTY2621020400CE
        """
        resp = self.client.get_quote(
            exchange_trading_symbol=symbol
        )

        return float(resp["ltp"])
