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
LOT_SIZE = 50

INITIAL_SL_PCT = 0.15
TRAIL_SL_PCT = 0.10
TARGET_PCT = 0.30

# =========================================================
# SAFE LTP EXTRACTOR (LOCKED)
# =========================================================
def extract_ltp(value):
    if isinstance(value, dict):
        return value.get("ltp") or value.get("last_price") or value.get("price")
    if isinstance(value, (int, float)):
        return float(value)
    return None

# =========================================================
# INDICATORS (LOCKED)
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
    "nearest_option_ltp": {},   # 🔥 NEW
    "paper_balance": PAPER_CAPITAL_INITIAL,
    "positions": [],
    "closed_trades": [],
    "indicator_df": None,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# SAFE ERROR LOGGER (LOCKED)
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
# AUTO REFRESH (HARD LOCKED)
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
# INDEX LTP FETCHER (LOCKED)
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
# OPTION LTP FETCHERS (LOCKED – EXISTING)
# =========================================================
monthly_symbols = [
    "NSE_NIFTY26FEB25500CE",
    "NSE_NIFTY26FEB25500PE"
]

if groww:
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_FNO,
            exchange_trading_symbols=tuple(monthly_symbols)
        )
        for sym, raw in resp.items():
            ltp = extract_ltp(raw)
            if ltp:
                st.session_state.options_ltp[sym] = ltp
    except Exception as e:
        log_error(str(e))

weekly_symbol = "NIFTY2621025500CE"

if groww:
    try:
        quote = groww.get_quote(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_FNO,
            weekly_symbol
        )
        ltp = extract_ltp(quote)
        if ltp:
            st.session_state.options_ltp[weekly_symbol] = ltp
    except Exception as e:
        log_error(str(e))

# =========================================================
# 🔥 NEW: NEAREST STRIKE AUTO FETCHER
# =========================================================
STRIKE_CONFIG = {
    "NIFTY": {"step": 50},
    "BANKNIFTY": {"step": 100},
    "FINNIFTY": {"step": 50},
}

if groww and st.session_state.index_ltp:
    try:
        symbols_to_fetch = []

        for index, cfg in STRIKE_CONFIG.items():
            ltp = st.session_state.index_ltp.get(index)
            if not ltp:
                continue

            step = cfg["step"]
            atm = int(round(ltp / step) * step)

            for i in range(-10, 11):
                strike = atm + (i * step)
                symbols_to_fetch.append(f"NSE_{index}26FEB{strike}CE")
                symbols_to_fetch.append(f"NSE_{index}26FEB{strike}PE")

        # Batch in chunks of 50 (Groww limit)
        for i in range(0, len(symbols_to_fetch), 50):
            batch = symbols_to_fetch[i:i+50]
            resp = groww.get_ltp(
                segment=groww.SEGMENT_FNO,
                exchange_trading_symbols=tuple(batch)
            )
            for sym, raw in resp.items():
                ltp = extract_ltp(raw)
                if ltp:
                    st.session_state.nearest_option_ltp[sym] = ltp

    except Exception as e:
        log_error(str(e))

# =========================================================
# UI TABLES (LOCKED – UNCHANGED)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
colA, colB = st.columns([2, 1])

with colA:
    st.dataframe(
        pd.DataFrame(
            [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
        ),
        use_container_width=True
    )

with colB:
    st.markdown(
        f"""
        **Paper Trade Capital:**  
        <span style="color:green;font-weight:bold;">₹ {round(st.session_state.paper_balance,2)}</span>
        """,
        unsafe_allow_html=True
    )

st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.options_ltp.items()]
    ),
    use_container_width=True
)

st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.closed_trades), use_container_width=True)

# =========================================================
# ERROR LOGS (LOCKED)
# =========================================================
st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
