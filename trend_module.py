"""
trend_module.py - 1H index trend bias detection.
Responsibility: Determine UP/DOWN/None trend using EMA21 vs EMA50 on 1H index candles.
"""

import datetime
import config


class TrendModule:
    def __init__(self, groww):
        self.groww = groww

    def detect_trend(self, index_symbol: str):
        """
        Detect trend on 1H index candles using EMA21 vs EMA50.
        Returns: "UP", "DOWN", or None
        """
        try:
            candles = self._fetch_1h_candles(index_symbol)
            if candles is None or len(candles) < config.EMA_SLOW:
                print(f"  [Trend] Not enough 1H candles for {index_symbol} (got {len(candles) if candles else 0})")
                return None

            closes = [float(c[4]) for c in candles]  # close price

            ema_fast = self._ema(closes, config.EMA_FAST)
            ema_slow = self._ema(closes, config.EMA_SLOW)

            if ema_fast > ema_slow:
                return "UP"
            elif ema_fast < ema_slow:
                return "DOWN"
            else:
                return None

        except Exception as e:
            print(f"  [Trend] Error for {index_symbol}: {e}")
            return None

    def _fetch_1h_candles(self, index_symbol: str):
        """
        Fetch 1H candles for index from Groww API.
        Uses get_historical_candles with proper time format.
        """
        now = datetime.datetime.now()
        # Go back enough days to get sufficient candles (weekends, holidays)
        start = now - datetime.timedelta(days=15)

        # Weekend-safe: adjust start to avoid starting on weekend
        start_str = start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = now.strftime("%Y-%m-%d %H:%M:%S")

        # groww_symbol requires dash format: NSE-NIFTY, not NSE_NIFTY
        groww_symbol = config.GROWW_SYMBOL_MAP[index_symbol]

        # For index candles, use CASH segment
        data = self.groww.get_historical_candles(
            exchange=self.groww.EXCHANGE_NSE,
            segment=self.groww.SEGMENT_CASH,
            groww_symbol=groww_symbol,
            start_time=start_str,
            end_time=end_str,
            candle_interval=self.groww.CANDLE_INTERVAL_HOUR_1,
        )

        candles = data.get("candles", [])
        return candles if candles else None

    @staticmethod
    def _ema(data: list, period: int) -> float:
        """
        Calculate EMA for given data and period.
        Returns the last EMA value.
        """
        if len(data) < period:
            return 0.0

        multiplier = 2.0 / (period + 1)
        ema = sum(data[:period]) / period  # SMA seed

        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema
