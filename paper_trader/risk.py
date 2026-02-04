from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskState:
    daily_pnl: float = 0.0
    consecutive_losses: int = 0


class RiskManager:
    def __init__(
        self,
        max_loss_per_trade: float,
        max_daily_loss: float,
        max_consecutive_losses: int,
    ) -> None:
        self._max_loss_per_trade = max_loss_per_trade
        self._max_daily_loss = max_daily_loss
        self._max_consecutive_losses = max_consecutive_losses
        self._state = RiskState()

    @property
    def state(self) -> RiskState:
        return self._state

    def can_take_trade(self) -> bool:
        if self._state.daily_pnl <= -abs(self._max_daily_loss):
            return False
        if self._state.consecutive_losses >= self._max_consecutive_losses:
            return False
        return True

    def register_trade_result(self, pnl: float) -> None:
        self._state.daily_pnl += pnl
        if pnl < 0:
            self._state.consecutive_losses += 1
        else:
            self._state.consecutive_losses = 0

    def trade_loss_exceeded(self, pnl: float) -> bool:
        return pnl <= -abs(self._max_loss_per_trade)
