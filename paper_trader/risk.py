from __future__ import annotations


class RiskManager:
    def __init__(
        self,
        max_loss_per_trade: float = 500.0,
        max_daily_loss: float = 1500.0,
        max_consecutive_losses: int = 3,
        target_rr: float = 2.0,
        initial_sl_pct: float = 0.25,
        trail_sl_pct: float = 0.2,
    ) -> None:
        self.max_loss_per_trade = max_loss_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_consecutive_losses = max_consecutive_losses
        self.target_rr = target_rr
        self.initial_sl_pct = initial_sl_pct
        self.trail_sl_pct = trail_sl_pct
        self.daily_pnl = 0.0
        self.consecutive_losses = 0

    def can_trade(self) -> tuple[bool, str]:
        if self.daily_pnl <= -abs(self.max_daily_loss):
            return False, "Daily max loss reached"
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, "Consecutive loss limit reached"
        return True, "OK"

    def stop_target(self, entry_price: float, quantity: int) -> tuple[float, float]:
        hard_sl = entry_price - (self.max_loss_per_trade / max(quantity, 1))
        pct_sl = entry_price * (1.0 - self.initial_sl_pct)
        stop_loss = max(hard_sl, pct_sl)
        target = entry_price + (entry_price - stop_loss) * self.target_rr
        return stop_loss, target

    def trail(self, current_stop: float, latest_price: float) -> float:
        trailed = latest_price * (1.0 - self.trail_sl_pct)
        return max(current_stop, trailed)

    def register_trade(self, pnl: float) -> None:
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
