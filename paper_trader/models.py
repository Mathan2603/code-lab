from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    strike: float
    option_type: str
    expiry: str


@dataclass
class Position:
    symbol: str
    entry_price: float
    quantity: int
    stop_loss: float
    target: float
    open_time: datetime
    side: str
    max_favorable_price: float


@dataclass
class TradeRecord:
    sno: int
    time: datetime
    symbol: str
    buy_price: float
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    sold_price: float
    pnl_after_trade: float
