import csv
import os
import threading
import time
from datetime import datetime

from growwapi import GrowwAPI

PAPER_CAPITAL = 50000.0
LOT_SIZES = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}
PORTFOLIO_FILE = "data-paper_portfolio.csv"
TRADE_LOG_FILE = f"paper_logs-paper_trades_{datetime.now().strftime('%Y%m%d')}.csv"

INDEX_SYMBOLS = ("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")


def extract_ltp(value):
    if isinstance(value, dict):
        return value.get("ltp") or value.get("last_price") or value.get("price")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def ema(values, period):
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period
    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for idx in range(1, period + 1):
        delta = values[idx] - values[idx - 1]
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for idx in range(period + 1, len(values)):
        delta = values[idx] - values[idx - 1]
        gain = max(delta, 0)
        loss = abs(min(delta, 0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(values, period=14):
    if len(values) <= period:
        return None
    trs = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def parse_expiry_dates(expiries):
    parsed = []
    for expiry in expiries or []:
        try:
            parsed.append((expiry, datetime.strptime(expiry, "%Y-%m-%d")))
        except ValueError:
            continue
    return parsed


def select_expiry_dates(expiries):
    parsed = parse_expiry_dates(expiries)
    if not parsed:
        return None, None
    sorted_dates = sorted(parsed, key=lambda item: item[1])
    weekly = sorted_dates[0][0]
    monthly = sorted_dates[-1][0]
    return monthly, weekly


def append_csv(path, row, columns):
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def save_portfolio(positions):
    columns = ["symbol", "qty", "entry_price", "stop_loss", "status", "index", "updated_at"]
    with open(PORTFOLIO_FILE, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for position in positions:
            writer.writerow(position)


class TradingBot:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._tokens = ["", "", "", "", ""]
        self.errors = []
        self.trades = []
        self.index_ltp = {}
        self.nearest_strikes = []
        self.monthly_ltp = {}
        self.weekly_ltp = {}
        self.price_history = {}
        self.weekly_cycle = 0
        self.last_cycle_time = None

    def set_tokens(self, tokens):
        with self._lock:
            self._tokens = tokens

    def start(self):
        with self._lock:
            if self._running:
                return
            if len([t for t in self._tokens if t.strip()]) < 2:
                self._log_error("system", "start", "TOKENS", "At least 2 tokens required")
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False

    def status(self):
        with self._lock:
            return {
                "running": self._running,
                "last_cycle_time": self.last_cycle_time,
                "index_ltp": self.index_ltp,
            }

    def get_trades(self):
        with self._lock:
            return list(self.trades)

    def get_errors(self):
        with self._lock:
            return list(self.errors)

    def _log_error(self, token_id, api_name, symbol, message):
        with self._lock:
            self.errors.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "token": token_id,
                    "api": api_name,
                    "symbol": symbol,
                    "error": str(message),
                }
            )
            self.errors = self.errors[-200:]

    def _run_loop(self):
        while True:
            with self._lock:
                running = self._running
                tokens = list(self._tokens)
            if not running:
                break
            cycle_start = time.time()
            self._run_cycle(tokens)
            self.last_cycle_time = datetime.now().strftime("%H:%M:%S")
            elapsed = time.time() - cycle_start
            sleep_time = max(0, 5 - elapsed)
            time.sleep(sleep_time)

    def _run_cycle(self, tokens):
        token1, token2, token3, token4, _token5 = tokens
        gw_index = GrowwAPI(token1) if token1 else None
        gw_monthly = GrowwAPI(token2) if token2 else None
        gw_weekly_nifty = GrowwAPI(token3) if token3 else None
        gw_weekly_banknifty = GrowwAPI(token4) if token4 else None

        index_ltp = {}
        monthly_ltp = dict(self.monthly_ltp)
        weekly_ltp = dict(self.weekly_ltp)

        if gw_index:
            try:
                resp = gw_index.get_ltp(
                    segment=gw_index.SEGMENT_CASH,
                    exchange_trading_symbols=INDEX_SYMBOLS,
                )
                for sym, raw in resp.items():
                    ltp = extract_ltp(raw)
                    if ltp:
                        index_ltp[sym.replace("NSE_", "")] = ltp
            except Exception as exc:
                self._log_error("token1", "get_ltp", "NSE_INDEX", exc)

        expiry_map = {}
        weekly_expiry_map = {}
        for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            if not gw_index:
                continue
            try:
                expiries = gw_index.get_expiries(gw_index.EXCHANGE_NSE, idx)
                monthly, weekly = select_expiry_dates(expiries)
                if monthly:
                    expiry_map[idx] = monthly
                if weekly:
                    weekly_expiry_map[idx] = weekly
            except Exception as exc:
                self._log_error("token1", "get_expiries", idx, exc)

        monthly_contracts = {}
        for idx, expiry in expiry_map.items():
            if not gw_index:
                continue
            try:
                contracts = gw_index.get_contracts(gw_index.EXCHANGE_NSE, idx, expiry)
                monthly_contracts[idx] = contracts or []
            except Exception as exc:
                self._log_error("token1", "get_contracts", f"{idx}-{expiry}", exc)

        nearest_rows = []
        nearest_symbols = []
        for idx, ltp in index_ltp.items():
            contracts = monthly_contracts.get(idx, [])
            if not contracts:
                continue
            strikes = sorted(
                {
                    float(contract.get("strike_price"))
                    for contract in contracts
                    if contract.get("strike_price") is not None
                }
            )
            if not strikes:
                continue
            atm = min(strikes, key=lambda strike: abs(strike - ltp))
            atm_index = strikes.index(atm)
            start = max(atm_index - 10, 0)
            end = min(atm_index + 10, len(strikes) - 1)
            strike_window = strikes[start : end + 1]

            for strike in strike_window:
                for contract in contracts:
                    if float(contract.get("strike_price", -1)) != strike:
                        continue
                    option_type = contract.get("option_type") or contract.get("right")
                    symbol = contract.get("trading_symbol")
                    if not symbol or option_type not in {"CE", "PE"}:
                        continue
                    nearest_symbols.append(symbol)
                    nearest_rows.append(
                        {
                            "Index": idx,
                            "Symbol": symbol,
                            "Strike": strike,
                            "Type": option_type,
                            "LTP": None,
                        }
                    )

        if gw_monthly and nearest_symbols:
            try:
                for i in range(0, len(nearest_symbols), 50):
                    batch = nearest_symbols[i : i + 50]
                    resp = gw_monthly.get_ltp(
                        segment=gw_monthly.SEGMENT_FNO,
                        exchange_trading_symbols=tuple(batch),
                    )
                    for sym, raw in resp.items():
                        ltp = extract_ltp(raw)
                        if ltp:
                            monthly_ltp[sym] = ltp
            except Exception as exc:
                self._log_error("token2", "get_ltp", "MONTHLY_BATCH", exc)

        for row in nearest_rows:
            row["LTP"] = monthly_ltp.get(row["Symbol"])

        weekly_contracts = {}
        for idx, expiry in weekly_expiry_map.items():
            if not gw_index:
                continue
            try:
                contracts = gw_index.get_contracts(gw_index.EXCHANGE_NSE, idx, expiry)
                weekly_contracts[idx] = contracts or []
            except Exception as exc:
                self._log_error("token1", "get_contracts", f"{idx}-{expiry}", exc)

        weekly_symbols = {}
        for idx, contracts in weekly_contracts.items():
            strikes = sorted(
                {
                    float(contract.get("strike_price"))
                    for contract in contracts
                    if contract.get("strike_price") is not None
                }
            )
            if not strikes or idx not in index_ltp:
                continue
            ltp = index_ltp[idx]
            atm = min(strikes, key=lambda strike: abs(strike - ltp))
            selected = {"CE": None, "PE": None}
            for contract in contracts:
                if float(contract.get("strike_price", -1)) != atm:
                    continue
                option_type = contract.get("option_type") or contract.get("right")
                if option_type in selected:
                    selected[option_type] = contract.get("trading_symbol")
            weekly_symbols[idx] = selected

        cycle_mode = self.weekly_cycle % 2
        self.weekly_cycle += 1
        if cycle_mode == 0:
            nifty_symbol = weekly_symbols.get("NIFTY", {}).get("CE")
            banknifty_symbol = weekly_symbols.get("BANKNIFTY", {}).get("CE")
        else:
            nifty_symbol = weekly_symbols.get("NIFTY", {}).get("PE")
            banknifty_symbol = weekly_symbols.get("BANKNIFTY", {}).get("PE")

        if nifty_symbol and gw_weekly_nifty:
            try:
                resp = gw_weekly_nifty.get_quote(
                    exchange=gw_weekly_nifty.EXCHANGE_NSE,
                    segment=gw_weekly_nifty.SEGMENT_FNO,
                    trading_symbol=nifty_symbol,
                )
                ltp = extract_ltp(resp)
                if ltp:
                    weekly_ltp[nifty_symbol] = ltp
            except Exception as exc:
                self._log_error("token3", "get_quote", nifty_symbol, exc)

        if banknifty_symbol and gw_weekly_banknifty:
            try:
                resp = gw_weekly_banknifty.get_quote(
                    exchange=gw_weekly_banknifty.EXCHANGE_NSE,
                    segment=gw_weekly_banknifty.SEGMENT_FNO,
                    trading_symbol=banknifty_symbol,
                )
                ltp = extract_ltp(resp)
                if ltp:
                    weekly_ltp[banknifty_symbol] = ltp
            except Exception as exc:
                self._log_error("token4", "get_quote", banknifty_symbol, exc)

        with self._lock:
            self.index_ltp = index_ltp
            self.monthly_ltp = monthly_ltp
            self.weekly_ltp = weekly_ltp
            self.nearest_strikes = nearest_rows
            self._update_history()
            self._evaluate_trades()

    def _update_history(self):
        price_sources = {**self.monthly_ltp, **self.weekly_ltp}
        for symbol, price in price_sources.items():
            history = self.price_history.setdefault(symbol, [])
            history.append(price)
            if len(history) > 200:
                history.pop(0)

    def _evaluate_trades(self):
        available_margin = self._calculate_available_margin()
        open_positions = [p for p in self.trades if p.get("status") == "OPEN"]

        for row in self.nearest_strikes:
            symbol = row["Symbol"]
            index = row["Index"]
            ltp = row["LTP"]
            if not ltp:
                continue
            history = self.price_history.get(symbol, [])
            ema_fast = ema(history, 20)
            ema_slow = ema(history, 50)
            rsi_val = rsi(history, 14)
            atr_val = atr(history, 14)

            if ema_fast is None or ema_slow is None or rsi_val is None or atr_val is None:
                continue

            already_open = any(
                pos.get("symbol") == symbol and pos.get("status") == "OPEN"
                for pos in open_positions
            )
            if already_open:
                continue

            if ema_fast > ema_slow and rsi_val > 55:
                lot_size = LOT_SIZES.get(index, 1)
                cost = ltp * lot_size
                if cost > available_margin:
                    cheaper_options = [
                        r
                        for r in self.nearest_strikes
                        if r["Index"] == index and r["LTP"] and r["LTP"] * lot_size <= available_margin
                    ]
                    if cheaper_options:
                        row = min(cheaper_options, key=lambda r: r["LTP"])
                        symbol = row["Symbol"]
                        ltp = row["LTP"]
                    else:
                        continue

                trade = {
                    "symbol": symbol,
                    "qty": lot_size,
                    "entry_price": ltp,
                    "stop_loss": max(ltp - atr_val, 0),
                    "status": "OPEN",
                    "index": index,
                    "updated_at": datetime.now().strftime("%H:%M:%S"),
                }
                self.trades.append(trade)
                append_csv(
                    TRADE_LOG_FILE,
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "BUY",
                        "symbol": symbol,
                        "qty": lot_size,
                        "price": ltp,
                    },
                    ["time", "action", "symbol", "qty", "price"],
                )
                available_margin -= ltp * lot_size

        for trade in self.trades:
            if trade.get("status") != "OPEN":
                continue
            symbol = trade.get("symbol")
            current_price = self.monthly_ltp.get(symbol) or self.weekly_ltp.get(symbol)
            history = self.price_history.get(symbol, [])
            atr_val = atr(history, 14)
            if not current_price or atr_val is None:
                continue
            new_sl = max(trade.get("stop_loss", 0), current_price - atr_val)
            trade["stop_loss"] = new_sl
            trade["updated_at"] = datetime.now().strftime("%H:%M:%S")
            if current_price <= trade["stop_loss"]:
                trade["status"] = "CLOSED"
                append_csv(
                    TRADE_LOG_FILE,
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "SELL",
                        "symbol": symbol,
                        "qty": trade.get("qty"),
                        "price": current_price,
                    },
                    ["time", "action", "symbol", "qty", "price"],
                )

        save_portfolio(self.trades)

    def _calculate_available_margin(self):
        used = sum(
            (trade.get("entry_price", 0) * trade.get("qty", 0))
            for trade in self.trades
            if trade.get("status") == "OPEN"
        )
        return max(PAPER_CAPITAL - used, 0)
