from __future__ import annotations
from typing import List, Dict


class GrowwPaperBroker:
    """Groww API adapter – paper trading only"""

    def __init__(self) -> None:
        from growwapi import GrowwAPI
        self._GrowwAPI = GrowwAPI

    def client(self, token: str):
        return self._GrowwAPI(token)

    # -------------------------------
    # TOKEN VALIDATION
    # -------------------------------
    def validate_token(self, token: str) -> tuple[bool, str]:
        try:
            groww = self.client(token)

            # Correct Groww call
            groww.get_ltp(
                segment="CASH",
                symbols=["NSE_NIFTY"]
            )

            return True, "valid"

        except Exception as e:
            return False, str(e)

    # -------------------------------
    # MARKET DATA
    # -------------------------------
    def get_ltp(self, token: str, segment: str, symbols: List[str]) -> Dict:
        groww = self.client(token)
        return groww.get_ltp(segment=segment, symbols=symbols)
