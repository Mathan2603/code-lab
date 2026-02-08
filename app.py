import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from growwapi import GrowwAPI
import math

# =========================================================
# CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL_INITIAL = 50000.0
LOT_SIZES = {
    "NIFTY": 65,
    "BANKNIFTY": 30,
    "FINNIFTY": 60,
}
STRIKE_STEP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
}

INITIAL_SL_PCT = 0.15
TRAIL_SL_PCT = 0.10
TARGET_PCT = 0.30

# =========================================================
# SAFE LTP EXTRACTOR
# =========================================================
def extract_ltp(value):
    if isinstance(value, dict):
        return value.get("ltp") or value.get("last_price") or value.get("price")
    if isinstance(value, (int, float)):
        return float(value)
    return None

# =========================================================
# INDICATORS
# =========================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "tokens": ["", "", "", "", ""],
    "bot_running": False,
    "errors": [],
    "index_ltp": {},
    "options_ltp": {},
    "paper_balance": PAPER_CAPITAL_INITIAL,
    "positions": [],
    "closed_trades": [],
    "indicator_df": None,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# SAFE ERROR LOGGER
# =========================================================
def log_error(msg):
    if "Not able to recognize exchange" in msg:
        return
    st.session_state.errors.append(msg)

# =========================================================
# SIDEBAR (LOCKED UI)
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
# AUTO REFRESH
# =========================================================
now = time.time()
if now - st.session_state.get("last_refresh", 0) >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    if st.session_state.bot_running:
        st.rerun()

# =========================================================
# INIT GROWW
# =========================================================
groww = None
if st.session_state.bot_running and st.session_state.tokens[0]:
    groww = GrowwAPI(st.session_state.tokens[0])

# =========================================================
# FETCH INDICATORS (ONCE)
# =========================================================
if groww and st.session_state.indicator_df is None:
    try:
        end = datetime.now()
        start = end - timedelta(days=60)

        candles = groww.get_historical_candles(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_CASH,
            "NSE-NIFTY",
            start.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
            "15minute"
        )

        if candles and len(candles) >= 30:
            df = pd.DataFrame(
                candles,
                columns=["time", "open", "high", "low", "close", "volume"]
            )
            df["ema9"] = ema(df["close"], 9)
            df["ema21"] = ema(df["close"], 21)
            df["rsi"] = rsi(df["close"])
            st.session_state.indicator_df = df

    except Exception as e:
        log_error(str(e))

# =========================================================
# INDEX LTP (LOCKED)
# =========================================================
if groww:
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )
        for sym, raw in resp.items():
            ltp = extract_ltp(raw)
            if ltp:
                st.session_state.index_ltp[sym.replace("NSE_", "")] = ltp
    except Exception as e:
        log_error(str(e))

# =========================================================
# 🔥 STEP 5 — DYNAMIC STRIKE SELECTION
# =========================================================
def select_dynamic_symbol():
    df = st.session_state.indicator_df
    if df is None or df.empty:
        return None, None, None

    latest = df.iloc[-1]
    trend = "BULLISH" if latest["ema9"] > latest["ema21"] else "BEARISH"

    index_name = "NIFTY"
    index_price = st.session_state.index_ltp.get(index_name)
    if not index_price:
        return None, None, None

    step = STRIKE_STEP[index_name]
    lot = LOT_SIZES[index_name]

    atm = int(round(index_price / step) * step)

    strikes = []
    for i in range(0, 10):
        strike = atm + (i * step if trend == "BULLISH" else -i * step)
        strikes.append(strike)

    for strike in strikes:
        opt_type = "CE" if trend == "BULLISH" else "PE"
        symbol = f"NSE_{index_name}26FEB{strike}{opt_type}"

        ltp = st.session_state.options_ltp.get(symbol)
        if ltp is None:
            continue

        cost = ltp * lot
        if cost <= st.session_state.paper_balance:
            return symbol, ltp, lot

    return None, None, None

# =========================================================
# ENTRY USING DYNAMIC STRIKE
# =========================================================
symbol, ltp, lot = select_dynamic_symbol()
if symbol and ltp:
    already_open = any(
        p["symbol"] == symbol and p["status"] == "OPEN"
        for p in st.session_state.positions
    )

    if not already_open:
        st.session_state.paper_balance -= ltp * lot
        st.session_state.positions.append({
            "symbol": symbol,
            "entry_price": ltp,
            "qty": lot,
            "sl": round(ltp * (1 - INITIAL_SL_PCT), 2),
            "target": round(ltp * (1 + TARGET_PCT), 2),
            "entry_time": datetime.now().strftime("%H:%M:%S"),
            "status": "OPEN"
        })

# =========================================================
# POSITION MANAGEMENT (UNCHANGED)
# =========================================================
for pos in list(st.session_state.positions):
    ltp = st.session_state.options_ltp.get(pos["symbol"])
    if ltp is None:
        continue

    trail_sl = round(ltp * (1 - TRAIL_SL_PCT), 2)
    if trail_sl > pos["sl"]:
        pos["sl"] = trail_sl

    exit_reason = None
    if ltp <= pos["sl"]:
        exit_reason = "SL"
    elif ltp >= pos["target"]:
        exit_reason = "TARGET"

    if exit_reason:
        pnl = (ltp - pos["entry_price"]) * pos["qty"]
        st.session_state.paper_balance += ltp * pos["qty"]

        pos.update({
            "exit_price": ltp,
            "exit_time": datetime.now().strftime("%H:%M:%S"),
            "pnl": round(pnl, 2),
            "exit_reason": exit_reason,
            "status": "CLOSED"
        })
        st.session_state.closed_trades.append(pos)
        st.session_state.positions.remove(pos)

# =========================================================
# UI TABLES (LOCKED)
# =========================================================
st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.closed_trades), use_container_width=True)

# =========================================================
# ERROR LOGS
# =========================================================
st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
