from __future__ import annotations

from collections import deque


class DirectionalTrend:
    def __init__(self, short_window: int = 5, long_window: int = 20) -> None:
        self._short = short_window
        self._long = long_window
        self._prices: deque[float] = deque(maxlen=long_window)

    def update(self, price: float) -> str:
        self._prices.append(float(price))
        if len(self._prices) < self._long:
            return "flat"
        short_avg = sum(list(self._prices)[-self._short :]) / self._short
        long_avg = sum(self._prices) / self._long
        if short_avg > long_avg:
            return "up"
        if short_avg < long_avg:
            return "down"
        return "flat"
