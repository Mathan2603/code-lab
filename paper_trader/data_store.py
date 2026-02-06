from __future__ import annotations

import csv
from pathlib import Path

from paper_trader.models import Position, TradeRecord
from paper_trader.utils import IST


class CsvStore:
    def __init__(self, trade_log_dir: str = "paper_logs", portfolio_path: str = "data-paper_portfolio.csv") -> None:
        self.trade_log_dir = Path(trade_log_dir)
        self.trade_log_dir.mkdir(parents=True, exist_ok=True)
        self.portfolio_path = Path(portfolio_path)
        self.portfolio_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.portfolio_path.exists():
            self.write_positions([])

    def _trade_file(self, ts) -> Path:
        return self.trade_log_dir / f"paper_logs-paper_trades_{ts.strftime('%Y%m%d')}.csv"

    def append_trade(self, trade: TradeRecord) -> None:
        fpath = self._trade_file(trade.time)
        new_file = not fpath.exists()
        with fpath.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new_file:
                writer.writerow([
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
                ])
            writer.writerow([
                trade.sno,
                trade.time.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                trade.symbol,
                f"{trade.buy_price:.2f}",
                trade.quantity,
                f"{trade.entry_price:.2f}",
                f"{trade.stop_loss:.2f}",
                f"{trade.target:.2f}",
                f"{trade.sold_price:.2f}",
                f"{trade.pnl_after_trade:.2f}",
            ])

    def write_positions(self, positions: list[Position]) -> None:
        with self.portfolio_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["symbol", "quantity", "entry_price", "stop_loss", "target", "opened_at", "direction"])
            for p in positions:
                writer.writerow([
                    p.symbol,
                    p.quantity,
                    f"{p.entry_price:.2f}",
                    f"{p.stop_loss:.2f}",
                    f"{p.target:.2f}",
                    p.opened_at.astimezone(IST).isoformat(),
                    p.direction,
                ])
