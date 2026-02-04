from __future__ import annotations

import csv
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from paper_trader.models import Position, TradeRecord
from paper_trader.utils import IST


class TradeDataStore:
    def __init__(self, trade_log_dir: str, portfolio_path: str) -> None:
        self.trade_log_dir = Path(trade_log_dir)
        self.portfolio_path = Path(portfolio_path)
        self.trade_log_dir.mkdir(parents=True, exist_ok=True)
        if not self.portfolio_path.exists():
            self._init_portfolio()

    def trade_log_path(self, trade_date: datetime) -> Path:
        file_name = trade_date.strftime("paper_trades_%Y%m%d.csv")
        return self.trade_log_dir / f"paper_logs-{file_name}"

    def _init_trade_log(self, path: Path) -> None:
        if path.exists():
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "s.no",
                    "time (IST)",
                    "symbol",
                    "buy price",
                    "quantity",
                    "entry price",
                    "stop loss",
                    "target",
                    "sold price",
                    "P&L after trade",
                ]
            )

    def _init_portfolio(self) -> None:
        self.portfolio_path.parent.mkdir(parents=True, exist_ok=True)
        with self.portfolio_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "symbol",
                    "entry_price",
                    "quantity",
                    "stop_loss",
                    "target",
                    "open_time",
                    "side",
                ]
            )

    def append_trade(self, record: TradeRecord) -> None:
        path = self.trade_log_path(record.time)
        self._init_trade_log(path)
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    record.sno,
                    record.time.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                    record.symbol,
                    f"{record.buy_price:.2f}",
                    record.quantity,
                    f"{record.entry_price:.2f}",
                    f"{record.stop_loss:.2f}",
                    f"{record.target:.2f}",
                    f"{record.sold_price:.2f}",
                    f"{record.pnl_after_trade:.2f}",
                ]
            )

    def write_portfolio(self, positions: list[Position]) -> None:
        with self.portfolio_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "symbol",
                    "entry_price",
                    "quantity",
                    "stop_loss",
                    "target",
                    "open_time",
                    "side",
                ]
            )
            for position in positions:
                writer.writerow(
                    [
                        position.symbol,
                        f"{position.entry_price:.2f}",
                        position.quantity,
                        f"{position.stop_loss:.2f}",
                        f"{position.target:.2f}",
                        position.open_time.astimezone(IST).isoformat(),
                        position.side,
                    ]
                )

    def load_portfolio(self) -> list[Position]:
        if not self.portfolio_path.exists():
            return []
        positions: list[Position] = []
        with self.portfolio_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                positions.append(
                    Position(
                        symbol=row["symbol"],
                        entry_price=float(row["entry_price"]),
                        quantity=int(row["quantity"]),
                        stop_loss=float(row["stop_loss"]),
                        target=float(row["target"]),
                        open_time=datetime.fromisoformat(row["open_time"]),
                        side=row["side"],
                        max_favorable_price=float(row["entry_price"]),
                    )
                )
        return positions

    def snapshot(self, positions: list[Position]) -> list[dict[str, str]]:
        return [asdict(position) for position in positions]
