"""
entry_module.py - 15M option entry signal detection.
Responsibility: Check all 4 entry conditions on 15M option candles.
All conditions must be true simultaneously. No scoring.
"""

import datetime
import config


class EntryModule:
    def __init__(self, groww):
        self.groww = groww

    def check_entry(self, contract: str, trend: str):
        """
        Check entry conditions on 15M option candles.
        All 4 conditions must be true:
        1. Breakout: Close > highest high of last 5 candles
        2. Volume expansion: Volume > 10 candle average
        3. ATR expansion: Current ATR > rolling ATR mean
        4. RSI: CE -> RSI > 55, PE -> RSI < 45

        Returns: (signal: bool, candle_data: dict or None)
        """
        try:
            candles = self._fetch_15m_candles(contract)
            if candles is None:
                return False, None

            min_candles = max(
                config.BREAKOUT_LOOKBACK + 1,
                config.VOLUME_AVG_PERIOD + 1,
                config.ATR_PERIOD + 1,
                config.RSI_PERIOD + 1,
            )

            if len(candles) < min_candles:
                print(f"  [Entry] Not enough 15M candles for {contract} (got {len(candles)})")
                return False, None

            # Parse candle data
            # Candle format: [timestamp, open, high, low, close, volume] or with OI
            parsed = self._parse_candles(candles)
            if parsed is None:
                return False, None

            closes = parsed["closes"]
            highs = parsed["highs"]
            lows = parsed["lows"]
            volumes = parsed["volumes"]

            # Current candle (last completed)
            current_close = closes[-1]
            current_high = highs[-1]
            current_low = lows[-1]
            current_volume = volumes[-1]

            # 1. Breakout check
            lookback_highs = highs[-(config.BREAKOUT_LOOKBACK + 1):-1]
            highest_high = max(lookback_highs)
            breakout = current_close > highest_high

            if not breakout:
                return False, None

            # 2. Volume expansion
            vol_avg = sum(volumes[-(config.VOLUME_AVG_PERIOD + 1):-1]) / config.VOLUME_AVG_PERIOD
            volume_ok = current_volume > vol_avg if vol_avg > 0 else False

            if not volume_ok:
                return False, None

            # 3. ATR expansion
            atr_values = self._calculate_atr_series(highs, lows, closes, config.ATR_PERIOD)
            if not atr_values or len(atr_values) < 2:
                return False, None

            current_atr = atr_values[-1]
            atr_mean = sum(atr_values) / len(atr_values)
            atr_ok = current_atr > atr_mean

            if not atr_ok:
                return False, None

            # 4. RSI check
            rsi = self._calculate_rsi(closes, config.RSI_PERIOD)
            if rsi is None:
                return False, None

            opt_type = "CE" if trend == "UP" else "PE"
            if opt_type == "CE":
                rsi_ok = rsi > config.RSI_CE_THRESHOLD
            else:
                rsi_ok = rsi < config.RSI_PE_THRESHOLD

            if not rsi_ok:
                return False, None

            # All conditions met
            candle_data = {
                "close": current_close,
                "high": current_high,
                "low": current_low,
                "volume": current_volume,
                "ATR": current_atr,
                "RSI": rsi,
            }

            print(f"  [Entry] ALL conditions met for {contract}")
            print(f"    Breakout: {current_close:.2f} > {highest_high:.2f}")
            print(f"    Volume: {current_volume} > avg {vol_avg:.0f}")
            print(f"    ATR: {current_atr:.2f} > mean {atr_mean:.2f}")
            print(f"    RSI: {rsi:.2f} ({'>' if opt_type == 'CE' else '<'} threshold)")

            return True, candle_data

        except Exception as e:
            print(f"  [Entry] Error for {contract}: {e}")
            return False, None

    def _fetch_15m_candles(self, contract: str):
        """
        Fetch 15M candles for option contract.
        Uses FNO segment.
        """
        now = datetime.datetime.now()
        # Go back enough to get sufficient candles
        start = now - datetime.timedelta(days=5)

        start_str = start.strftime("%Y-%m-%d %H:%M:%S")
        end_str = now.strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Convert contract format for LTP symbol
            # Contract: NSE-NIFTY-24Feb26-25600-CE
            # groww_symbol for historical candles: use contract as-is
            data = self.groww.get_historical_candles(
                exchange=self.groww.EXCHANGE_NSE,
                segment=self.groww.SEGMENT_FNO,
                groww_symbol=contract,
                start_time=start_str,
                end_time=end_str,
                candle_interval=self.groww.CANDLE_INTERVAL_MIN_15,
            )

            candles = data.get("candles", [])
            if not candles:
                return None
            return candles

        except Exception as e:
            print(f"  [Entry] Candle fetch error for {contract}: {e}")
            return None

    def _parse_candles(self, candles: list):
        """
        Parse candle data handling both 6-column and 7-column formats.
        Returns dict with opens, highs, lows, closes, volumes.
        """
        try:
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []

            for c in candles:
                # Handle both formats:
                # 6-col: [timestamp, open, high, low, close, volume]
                # 7-col: [timestamp, open, high, low, close, volume, oi]
                if len(c) >= 6:
                    opens.append(float(c[1]))
                    highs.append(float(c[2]))
                    lows.append(float(c[3]))
                    closes.append(float(c[4]))
                    # Volume can be None for some candles
                    vol = c[5]
                    volumes.append(float(vol) if vol is not None else 0.0)
                else:
                    return None

            return {
                "opens": opens,
                "highs": highs,
                "lows": lows,
                "closes": closes,
                "volumes": volumes,
            }
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _calculate_atr_series(highs: list, lows: list, closes: list, period: int) -> list:
        """
        Calculate ATR series using True Range.
        Returns list of ATR values.
        """
        if len(highs) < period + 1:
            return []

        true_ranges = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return []

        # First ATR = SMA of first `period` TRs
        atr = sum(true_ranges[:period]) / period
        atr_series = [atr]

        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period
            atr_series.append(atr)

        return atr_series

    @staticmethod
    def _calculate_rsi(closes: list, period: int):
        """
        Calculate RSI using standard Wilder's method.
        Returns latest RSI value or None.
        """
        if len(closes) < period + 1:
            return None

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        gains = [d if d > 0 else 0 for d in deltas[:period]]
        losses = [-d if d < 0 else 0 for d in deltas[:period]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        for d in deltas[period:]:
            gain = d if d > 0 else 0
            loss = -d if d < 0 else 0
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi
