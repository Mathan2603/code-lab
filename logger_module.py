"""
logger_module.py - Trade logging to CSV.
Responsibility: Persistent CSV logging of all trades.
No trade logic. No risk logic.
"""

import os
import csv
import config


class LoggerModule:
    def __init__(self):
        self.log_file = config.LOG_FILE
        self._ensure_csv_header()

    def _ensure_csv_header(self):
        """Create CSV file with header if it doesn't exist."""
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Date", "Contract", "Index", "Entry", "Exit",
                    "Qty", "Lot", "PnL", "Capital_After"
                ])
            print(f"[Logger] Created trade log: {self.log_file}")

    def log_trade(self, date: str, contract: str, index: str,
                  entry: float, exit_price: float, qty: int,
                  lot: int, pnl: float, capital_after: float = None):
        """
        Append a trade record to the CSV log.
        """
        try:
            with open(self.log_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    date,
                    contract,
                    index,
                    f"{entry:.2f}",
                    f"{exit_price:.2f}",
                    qty,
                    lot,
                    f"{pnl:.2f}",
                    f"{capital_after:.2f}" if capital_after else "",
                ])
            print(f"[Logger] Trade logged: {contract} PnL={pnl:.2f}")
        except Exception as e:
            print(f"[Logger] ERROR writing log: {e}")

    def get_trade_count(self) -> int:
        """Return total number of logged trades."""
        try:
            if not os.path.exists(self.log_file):
                return 0
            with open(self.log_file, "r") as f:
                reader = csv.reader(f)
                next(reader)  # skip header
                return sum(1 for _ in reader)
        except Exception:
            return 0
