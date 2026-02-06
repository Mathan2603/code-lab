from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TokenStatus:
    token: str
    active: bool = True
    last_used_at: datetime | None = None
    last_error: str = ""
    calls_made: int = 0


@dataclass
class OptionContract:
    symbol: str
    strike: float
    option_type: str
    expiry: str


@dataclass
class Position:
    symbol: str
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    opened_at: datetime
    direction: str
    max_price_seen: float


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


@dataclass
class EngineSnapshot:
    running: bool
    active_token_preview: str
    realized_pnl: float
    unrealized_pnl: float
    open_positions: list[Position] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
