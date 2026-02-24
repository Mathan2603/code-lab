"""
risk_module.py - Position sizing and risk limits.
Responsibility: Capital management, position sizing, daily limits.
No trade logic. No entry logic.
"""

import config


class RiskModule:
    def __init__(self):
        self.capital = config.INITIAL_CAPITAL
        self.start_of_day_capital = config.INITIAL_CAPITAL
        self.daily_trades = 0
        self.consecutive_losses = {}  # per index
        self.open_indices = set()     # indices with open trades

        for idx in config.INDEX_LIST:
            self.consecutive_losses[idx] = 0

    def reset_daily(self):
        """Reset daily counters at market open."""
        self.daily_trades = 0
        self.start_of_day_capital = self.capital
        for idx in config.INDEX_LIST:
            self.consecutive_losses[idx] = 0
        print("[Risk] Daily counters reset.")

    def can_trade(self, index_symbol: str) -> bool:
        """
        Check if a new trade is allowed for this index.
        Checks:
        - Max trades per day
        - Max consecutive losses per index
        - Daily drawdown limit
        - One open trade per index
        """
        # Max trades per day
        if self.daily_trades >= config.MAX_TRADES_PER_DAY:
            return False

        # Max consecutive losses per index
        if self.consecutive_losses.get(index_symbol, 0) >= config.MAX_CONSECUTIVE_LOSSES:
            return False

        # Daily drawdown limit
        drawdown = (self.start_of_day_capital - self.capital) / self.start_of_day_capital
        if drawdown >= config.MAX_DAILY_DRAWDOWN_PCT:
            print(f"[Risk] Daily drawdown limit reached: {drawdown:.2%}")
            return False

        # One open trade per index
        if index_symbol in self.open_indices:
            return False

        return True

    def calculate_position(self, entry_price: float, atr: float, structure_stop: float, lot_size: int):
        """
        Calculate position size based on 2% risk.
        Stop = max(1.5 * ATR, distance to structure stop)
        No averaging. No pyramiding.

        Returns dict with qty, stop, target, risk_per_unit or None if invalid.
        """
        if entry_price <= 0 or atr <= 0:
            return None

        # Calculate stop distance
        atr_stop_distance = config.ATR_STOP_MULTIPLIER * atr
        structure_stop_distance = abs(entry_price - structure_stop)
        stop_distance = max(atr_stop_distance, structure_stop_distance)

        if stop_distance <= 0:
            return None

        # Stop price
        stop_price = entry_price - stop_distance

        # Risk amount = 2% of capital
        risk_amount = self.capital * config.RISK_PER_TRADE_PCT

        # Quantity calculation (must be multiple of lot size)
        risk_per_unit = stop_distance
        raw_qty = risk_amount / risk_per_unit
        lots = max(1, int(raw_qty / lot_size))
        qty = lots * lot_size

        # Verify the actual risk doesn't exceed limit
        actual_risk = qty * risk_per_unit
        if actual_risk > risk_amount * 1.5:  # Allow small buffer
            lots = max(1, lots - 1)
            qty = lots * lot_size

        # Target at 3R
        target_price = entry_price + (stop_distance * config.TARGET_R)

        return {
            "qty": qty,
            "lots": lots,
            "stop": stop_price,
            "target": target_price,
            "risk_per_unit": risk_per_unit,
            "stop_distance": stop_distance,
        }

    def register_trade_opened(self, index_symbol: str):
        """Record that a trade was opened."""
        self.daily_trades += 1
        self.open_indices.add(index_symbol)

    def register_trade_closed(self, index_symbol: str, pnl: float):
        """Record trade result and update capital."""
        self.capital += pnl
        self.open_indices.discard(index_symbol)

        if pnl < 0:
            self.consecutive_losses[index_symbol] = self.consecutive_losses.get(index_symbol, 0) + 1
        else:
            self.consecutive_losses[index_symbol] = 0

    def get_daily_drawdown_pct(self) -> float:
        """Current daily drawdown percentage."""
        if self.start_of_day_capital <= 0:
            return 0.0
        return (self.start_of_day_capital - self.capital) / self.start_of_day_capital
