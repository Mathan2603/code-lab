from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque


@dataclass
class TrendState:
    direction: str
    strength: float


class SimpleTrendStrategy:
    def __init__(self, short_window: int = 5, long_window: int = 20) -> None:
        self._short_window = short_window
        self._long_window = long_window
        self._prices: Deque[float] = deque(maxlen=long_window)

    def update(self, price: float) -> TrendState:
        self._prices.append(price)
        if len(self._prices) < self._long_window:
            return TrendState(direction="flat", strength=0.0)
        short_avg = sum(list(self._prices)[-self._short_window :]) / self._short_window
        long_avg = sum(self._prices) / self._long_window
        if short_avg > long_avg:
            return TrendState(direction="up", strength=short_avg - long_avg)
        if short_avg < long_avg:
            return TrendState(direction="down", strength=long_avg - short_avg)
        return TrendState(direction="flat", strength=0.0)
