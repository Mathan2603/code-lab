import threading
import time
from datetime import datetime
from growwapi import GrowwAPI


class TradingBot:
    def __init__(self, state):
        self.state = state
        self.thread = None
        self.stop_event = threading.Event()

    def update_tokens(self, tokens):
        self.state["tokens"] = tokens

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.state["running"] = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.state["running"] = False
        self.stop_event.set()

    def log_error(self, token, api, symbol, err):
        self.state["errors"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "token": token,
            "api": api,
            "symbol": symbol,
            "error": str(err)
        })

    def extract_ltp(self, raw):
        if isinstance(raw, dict):
            return raw.get("ltp") or raw.get("last_price")
        return None

    def select_expiries(self, expiries):
        if not expiries:
            return None, None
        expiries = sorted(expiries)
        monthly = expiries[-1]
        weekly = expiries[0] if len(expiries) > 1 else None
        return monthly, weekly

    def run(self):
        while not self.stop_event.is_set():
            start = time.time()
            tokens = self.state["tokens"]

            try:
                gw_index = GrowwAPI(tokens[0])
                gw_monthly = GrowwAPI(tokens[1])
                gw_weekly = GrowwAPI(tokens[2]) if tokens[2] else None

                # INDEX LTP
                resp = gw_index.get_ltp(
                    segment=gw_index.SEGMENT_CASH,
                    exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY")
                )
                self.state["index_ltp"] = {
                    k.replace("NSE_", ""): self.extract_ltp(v)
                    for k, v in resp.items()
                }

                # EXPIRIES
                monthly_expiry, weekly_expiry = {}, {}
                for idx in ["NIFTY", "BANKNIFTY"]:
                    exps = gw_index.get_expiries(gw_index.EXCHANGE_NSE, idx)
                    m, w = self.select_expiries(exps)
                    if m:
                        monthly_expiry[idx] = m
                    if w:
                        weekly_expiry[idx] = w

                # MONTHLY CONTRACTS
                symbols = []
                rows = []
                for idx, exp in monthly_expiry.items():
                    contracts = gw_index.get_contracts(gw_index.EXCHANGE_NSE, idx, exp)
                    ltp = self.state["index_ltp"].get(idx)
                    strikes = sorted({float(c["strike_price"]) for c in contracts if c.get("strike_price")})
                    if not strikes or not ltp:
                        continue
                    atm = min(strikes, key=lambda x: abs(x - ltp))
                    window = strikes[max(0, strikes.index(atm)-10): strikes.index(atm)+11]

                    for c in contracts:
                        if float(c["strike_price"]) in window:
                            symbols.append(c["trading_symbol"])
                            rows.append({
                                "index": idx,
                                "symbol": c["trading_symbol"],
                                "strike": c["strike_price"],
                                "type": c["option_type"],
                                "ltp": None
                            })

                # MONTHLY LTP
                ltp_map = {}
                for i in range(0, len(symbols), 50):
                    resp = gw_monthly.get_ltp(
                        segment=gw_monthly.SEGMENT_FNO,
                        exchange_trading_symbols=tuple(symbols[i:i+50])
                    )
                    for s, r in resp.items():
                        ltp_map[s] = self.extract_ltp(r)

                for r in rows:
                    r["ltp"] = ltp_map.get(r["symbol"])

                self.state["nearest_strikes"] = rows
                self.state["monthly_ltp"] = ltp_map

                # WEEKLY LTP (ONE SYMBOL)
                cycle = self.state["weekly_cycle"] % 2
                self.state["weekly_cycle"] += 1
                weekly_ltp = {}

                for idx, exp in weekly_expiry.items():
                    contracts = gw_index.get_contracts(gw_index.EXCHANGE_NSE, idx, exp)
                    atm = min(
                        [float(c["strike_price"]) for c in contracts if c.get("strike_price")],
                        key=lambda x: abs(x - self.state["index_ltp"][idx])
                    )
                    for c in contracts:
                        if float(c["strike_price"]) == atm:
                            if cycle == 0 and c["option_type"] == "CE":
                                sym = c["trading_symbol"]
                            elif cycle == 1 and c["option_type"] == "PE":
                                sym = c["trading_symbol"]
                            else:
                                continue
                            if gw_weekly:
                                q = gw_weekly.get_quote(
                                    gw_weekly.EXCHANGE_NSE,
                                    gw_weekly.SEGMENT_FNO,
                                    sym
                                )
                                weekly_ltp[sym] = self.extract_ltp(q)

                self.state["weekly_ltp"] = weekly_ltp
                self.state["last_cycle"] = datetime.now().strftime("%H:%M:%S")

            except Exception as e:
                self.log_error("SYS", "RUN", "-", e)

            sleep = max(0, 5 - (time.time() - start))
            if self.stop_event.wait(sleep):
                break
