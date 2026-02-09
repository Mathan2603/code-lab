import math
import os
import time
from datetime import datetime

import pandas as pd
import streamlit as st
from growwapi import GrowwAPI

# =========================================================
# UI CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL = 50000.0
LOT_SIZES = {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}

PORTFOLIO_FILE = "data-paper_portfolio.csv"
TRADE_LOG_FILE = f"paper_logs-paper_trades_{datetime.now().strftime('%Y%m%d')}.csv"

# =========================================================
# HELPERS
# =========================================================

def extract_ltp(value):
    if isinstance(value, dict):
        return value.get("ltp") or value.get("last_price") or value.get("price")
    if isinstance(value, (int, float)):
        return float(value)
    return None


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


def log_error(token_id, api_name, symbol, message):
    st.session_state.errors.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "token": token_id,
            "api": api_name,
            "symbol": symbol,
            "error": str(message),
        }
    )


def load_csv(path, columns=None):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns or [])


def append_csv(path, row, columns):
    df = pd.DataFrame([row], columns=columns)
    if os.path.exists(path):
        df.to_csv(path, mode="a", header=False, index=False)
    else:
        df.to_csv(path, mode="w", header=True, index=False)


def save_portfolio(portfolio):
    df = pd.DataFrame(portfolio)
    df.to_csv(PORTFOLIO_FILE, index=False)


# =========================================================
# SESSION STATE INIT
# =========================================================
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.tokens = ["", "", "", "", ""]
    st.session_state.bot_running = False
    st.session_state.errors = []
    st.session_state.index_ltp = {}
    st.session_state.monthly_ltp = {}
    st.session_state.weekly_ltp = {}
    st.session_state.nearest_strikes = []
    st.session_state.trades = []
    st.session_state.price_history = {}
    st.session_state.weekly_cycle = 0
    st.session_state.last_refresh = 0
    st.session_state.account_summary = {}
    st.session_state.position_ltp = {}
    st.session_state.weekly_position_queue = []
    st.session_state.weekly_position_index = 0

# =========================================================
# SIDEBAR (LOCKED)
# =========================================================
st.sidebar.header("🔑 Groww Tokens")
for i in range(5):
    st.session_state.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}", type="password", value=st.session_state.tokens[i]
    )

c1, c2 = st.sidebar.columns(2)
if c1.button("▶ Start Bot"):
    st.session_state.bot_running = True
if c2.button("⏹ Stop Bot"):
    st.session_state.bot_running = False

st.sidebar.caption("Auto refresh every 5 seconds")

# =========================================================
# STOP EARLY IF BOT NOT RUNNING
# =========================================================
if not st.session_state.bot_running:
    st.info("Bot stopped")
    st.stop()

active_tokens = [token for token in st.session_state.tokens if token.strip()]
if len(active_tokens) < 2:
    st.error("At least 2 tokens are required to run the bot.")
    st.stop()

# =========================================================
# INIT GROWW CLIENTS (TOKEN SPLIT)
# =========================================================
gw_index = GrowwAPI(st.session_state.tokens[0])
gw_monthly = GrowwAPI(st.session_state.tokens[1])
gw_weekly_nifty = GrowwAPI(st.session_state.tokens[2]) if st.session_state.tokens[2] else None
gw_weekly_banknifty = (
    GrowwAPI(st.session_state.tokens[3]) if st.session_state.tokens[3] else None
)
gw_positions = GrowwAPI(st.session_state.tokens[4]) if st.session_state.tokens[4] else None

cycle_start = time.time()

# =========================================================
# 1️⃣ FETCH INDEX LTPs + ACCOUNT (TOKEN 1)
# =========================================================
try:
    resp = gw_index.get_ltp(
        segment=gw_index.SEGMENT_CASH,
        exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY"),
    )
    st.session_state.index_ltp.clear()
    for sym, raw in resp.items():
        ltp = extract_ltp(raw)
        if ltp:
            st.session_state.index_ltp[sym.replace("NSE_", "")] = ltp
except Exception as exc:
    log_error("token1", "get_ltp", "NSE_INDEX", exc)

margin_info = st.session_state.account_summary.get("margin")
if isinstance(margin_info, dict):
    available_margin = margin_info.get("available", available_margin)
# =========================================================
# 2️⃣ EXPIRY DETECTION (MONTHLY + WEEKLY)
# =========================================================
expiry_map = {}
weekly_expiry_map = {}
for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
    try:
        expiries = gw_index.get_expiries(gw_index.EXCHANGE_NSE, idx)
        monthly, weekly = select_expiry_dates(expiries)
        if monthly:
            expiry_map[idx] = monthly
        if weekly:
            weekly_expiry_map[idx] = weekly
    except Exception as exc:
        log_error("token1", "get_expiries", idx, exc)

# =========================================================
# 3️⃣ CONTRACTS & NEAREST STRIKES (MONTHLY)
# =========================================================
monthly_contracts = {}
for idx, expiry in expiry_map.items():
    try:
        contracts = gw_index.get_contracts(gw_index.EXCHANGE_NSE, idx, expiry)
        monthly_contracts[idx] = contracts or []
    except Exception as exc:
        log_error("token1", "get_contracts", f"{idx}-{expiry}", exc)

nearest_rows = []
nearest_symbols = []
for idx, ltp in st.session_state.index_ltp.items():
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
        strike_contracts = [c for c in contracts if float(c.get("strike_price", -1)) == strike]
        for contract in strike_contracts:
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

# =========================================================
# 4️⃣ FETCH NEAREST STRIKE LTPs (TOKEN 2, BATCHED)
# =========================================================
if nearest_symbols:
    try:
        for i in range(0, len(nearest_symbols), 50):
            batch = nearest_symbols[i : i + 50]
            resp = gw_monthly.get_ltp(
                segment=gw_monthly.SEGMENT_FNO, exchange_trading_symbols=tuple(batch)
            )
            for sym, raw in resp.items():
                ltp = extract_ltp(raw)
                if ltp:
                    st.session_state.monthly_ltp[sym] = ltp
    except Exception as exc:
        log_error("token2", "get_ltp", "MONTHLY_BATCH", exc)

for row in nearest_rows:
    row["LTP"] = st.session_state.monthly_ltp.get(row["Symbol"])

st.session_state.nearest_strikes = nearest_rows

# =========================================================
# 5️⃣ WEEKLY CONTRACTS & LTP (TOKEN 3/4)
# =========================================================
weekly_contracts = {}
for idx, expiry in weekly_expiry_map.items():
    try:
        contracts = gw_index.get_contracts(gw_index.EXCHANGE_NSE, idx, expiry)
        weekly_contracts[idx] = contracts or []
    except Exception as exc:
        log_error("token1", "get_contracts", f"{idx}-{expiry}", exc)

weekly_symbols = {}
for idx, contracts in weekly_contracts.items():
    strikes = sorted(
        {float(contract.get("strike_price")) for contract in contracts if contract.get("strike_price")}
    )
    if not strikes or idx not in st.session_state.index_ltp:
        continue
    ltp = st.session_state.index_ltp[idx]
    atm = min(strikes, key=lambda strike: abs(strike - ltp))
    selected = {"CE": None, "PE": None}
    for contract in contracts:
        if float(contract.get("strike_price", -1)) != atm:
            continue
        option_type = contract.get("option_type") or contract.get("right")
        if option_type in selected:
            selected[option_type] = contract.get("trading_symbol")
    weekly_symbols[idx] = selected

cycle_mode = st.session_state.weekly_cycle % 2
st.session_state.weekly_cycle += 1

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
            st.session_state.weekly_ltp[nifty_symbol] = ltp
    except Exception as exc:
        log_error("token3", "get_quote", nifty_symbol, exc)

if banknifty_symbol and gw_weekly_banknifty:
    try:
        resp = gw_weekly_banknifty.get_quote(
            exchange=gw_weekly_banknifty.EXCHANGE_NSE,
            segment=gw_weekly_banknifty.SEGMENT_FNO,
            trading_symbol=banknifty_symbol,
        )
        ltp = extract_ltp(resp)
        if ltp:
            st.session_state.weekly_ltp[banknifty_symbol] = ltp
    except Exception as exc:
        log_error("token4", "get_quote", banknifty_symbol, exc)

# =========================================================
# 6️⃣ POSITION TRACKER (TOKEN 5)
# =========================================================
if gw_positions:
    try:
        portfolio_positions = gw_positions.get_positions()
        st.session_state.account_summary["paper_positions"] = portfolio_positions
        monthly_symbols = []
        weekly_symbols = []
        if isinstance(portfolio_positions, list):
            for position in portfolio_positions:
                symbol = position.get("trading_symbol") or position.get("symbol")
                if not symbol:
                    continue
                if symbol.startswith("NSE_"):
                    monthly_symbols.append(symbol)
                else:
                    weekly_symbols.append(symbol)

        if monthly_symbols:
            try:
                resp = gw_positions.get_ltp(
                    segment=gw_positions.SEGMENT_FNO,
                    exchange_trading_symbols=tuple(monthly_symbols),
                )
                for sym, raw in resp.items():
                    ltp = extract_ltp(raw)
                    if ltp:
                        st.session_state.position_ltp[sym] = ltp
            except Exception as exc:
                log_error("token5", "get_ltp", "MONTHLY_POSITIONS", exc)

        st.session_state.weekly_position_queue = weekly_symbols
    except Exception as exc:
        log_error("token5", "get_positions", "PAPER_POSITIONS", exc)

    if st.session_state.weekly_position_queue:
        idx = st.session_state.weekly_position_index % len(
            st.session_state.weekly_position_queue
        )
        weekly_symbol = st.session_state.weekly_position_queue[idx]
        st.session_state.weekly_position_index += 1
        try:
            resp = gw_positions.get_quote(
                exchange=gw_positions.EXCHANGE_NSE,
                segment=gw_positions.SEGMENT_FNO,
                trading_symbol=weekly_symbol,
            )
            ltp = extract_ltp(resp)
            if ltp:
                st.session_state.position_ltp[weekly_symbol] = ltp
        except Exception as exc:
            log_error("token5", "get_quote", weekly_symbol, exc)

# =========================================================
# 7️⃣ INDICATORS & PAPER TRADING
# =========================================================
price_sources = {**st.session_state.monthly_ltp, **st.session_state.weekly_ltp}
for symbol, price in price_sources.items():
    history = st.session_state.price_history.setdefault(symbol, [])
    history.append(price)
    if len(history) > 200:
        history.pop(0)

portfolio_df = load_csv(PORTFOLIO_FILE, columns=[
    "symbol",
    "qty",
    "entry_price",
    "stop_loss",
    "status",
    "index",
    "updated_at",
])

if st.session_state.trades:
    portfolio_df = pd.DataFrame(st.session_state.trades)

available_margin = PAPER_CAPITAL
margin_info = st.session_state.account_summary.get("margin")
if isinstance(margin_info, dict):
    available_margin = margin_info.get("available", available_margin)

open_positions = [p for p in st.session_state.trades if p.get("status") == "OPEN"]

for row in st.session_state.nearest_strikes:
    symbol = row["Symbol"]
    index = row["Index"]
    ltp = row["LTP"]
    if not ltp:
        continue
    history = st.session_state.price_history.get(symbol, [])
    ema_fast = ema(history, 20)
    ema_slow = ema(history, 50)
    rsi_val = rsi(history, 14)
    atr_val = atr(history, 14)

    if ema_fast is None or ema_slow is None or rsi_val is None or atr_val is None:
        continue

    already_open = any(pos.get("symbol") == symbol and pos.get("status") == "OPEN" for pos in open_positions)
    if already_open:
        continue

    if ema_fast > ema_slow and rsi_val > 55:
        lot_size = LOT_SIZES.get(index, 1)
        cost = ltp * lot_size
        if cost > available_margin:
            cheaper_options = [
                r for r in st.session_state.nearest_strikes
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
        st.session_state.trades.append(trade)
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

# Update stop losses
for trade in st.session_state.trades:
    if trade.get("status") != "OPEN":
        continue
    symbol = trade.get("symbol")
    current_price = price_sources.get(symbol)
    history = st.session_state.price_history.get(symbol, [])
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

save_portfolio(st.session_state.trades)

# =========================================================
# UI TABLES (LOCKED STRUCTURE)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
    ),
    use_container_width=True,
)

st.subheader("📌 Table 2A: Nearest Strikes (Auto)")
st.dataframe(pd.DataFrame(st.session_state.nearest_strikes), use_container_width=True)

st.subheader("📌 Table 2B: Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.weekly_ltp.items()]
    ),
    use_container_width=True,
)

st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.trades), use_container_width=True)

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    st.dataframe(pd.DataFrame(st.session_state.errors).tail(10), use_container_width=True)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

# =========================================================
# CYCLE SLEEP (AFTER BACKEND LOGIC)
# =========================================================
elapsed = time.time() - cycle_start
sleep_time = max(0, REFRESH_INTERVAL - elapsed)
if sleep_time:
    time.sleep(sleep_time)

st.experimental_rerun()
