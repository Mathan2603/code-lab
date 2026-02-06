from dataclasses import dataclass, field


@dataclass
class TokenStatus:
    token: str
    active: bool = True
    last_used_at: object | None = None
    last_error: str = ""
    calls_made: int = 0


@dataclass
class EngineSnapshot:
    running: bool
    active_token_preview: str
    realized_pnl: float
    unrealized_pnl: float
    open_positions: list
    logs: list[str]
    last_prices: dict[str, float] = field(default_factory=dict)
