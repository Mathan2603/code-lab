from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from paper_trader.models import Position, TradeRecord
from paper_trader.risk import RiskManager
from paper_trader.utils import IST


@dataclass
class ExecutionResult:
    position: Position
    order_id: str


class PaperExecutionEngine:
    def __init__(self, risk: RiskManager) -> None:
        self._risk = risk
        self._order_seq = 0
        self._trade_seq = 0

    def _next_order_id(self) -> str:
        self._order_seq += 1
        return f"PAPER-{self._order_seq:05d}"

    def _next_trade_id(self) -> int:
        self._trade_seq += 1
        return self._trade_seq

    def enter_position(
        self,
        symbol: str,
        entry_price: float,
        quantity: int,
        stop_loss: float,
        target: float,
    ) -> ExecutionResult:
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            target=target,
            open_time=datetime.now(tz=IST),
            side="BUY",
            max_favorable_price=entry_price,
        )
        order_id = self._next_order_id()
        return ExecutionResult(position=position, order_id=order_id)

    def exit_position(
        self,
        position: Position,
        exit_price: float,
    ) -> TradeRecord:
        pnl = (exit_price - position.entry_price) * position.quantity
        self._risk.register_trade_result(pnl)
        trade_record = TradeRecord(
            sno=self._next_trade_id(),
            time=datetime.now(tz=IST),
            symbol=position.symbol,
            buy_price=position.entry_price,
            quantity=position.quantity,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            target=position.target,
            sold_price=exit_price,
            pnl_after_trade=pnl,
        )
        return trade_record
