import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI
import math

# =========================================================
# CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL_INITIAL = 50000.0

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
# SESSION STATE
# =========================================================
defaults = {
    "tokens": ["", "", "", "", ""],
    "bot_running": False,
    "errors": [],
    "index_ltp": {},
    "options_ltp": {},              # existing working fetcher
    "nearest_option_ltp": {},       # NEW (nearest strikes)
    "paper_balance": PAPER_CAPITAL_INITIAL,
    "closed_trades": [],
    "last_refresh": 0,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# ERROR LOGGER (LOCKED)
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
# AUTO REFRESH (CORRECT)
# =========================================================
now = time.time()
if st.session_state.bot_running:
    if now - st.session_state.last_refresh >= REFRESH_INTERVAL:
        st.session_state.last_refresh = now
        st.rerun()

# =========================================================
# INIT GROWW
# =========================================================
groww = None
if st.session_state.bot_running and st.session_state.tokens[0]:
    groww = GrowwAPI(st.session_state.tokens[0])

# =========================================================
# INDEX LTP FETCHER (LOCKED & WORKING)
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
# EXISTING MONTHLY & WEEKLY OPTION FETCHERS (DO NOT TOUCH)
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
# ✅ NEW: NEAREST STRIKE FETCHER (MONTHLY ONLY, SAFE)
# =========================================================
STRIKE_RULES = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
}

if groww and st.session_state.index_ltp:
    try:
        symbols = []

        for index, step in STRIKE_RULES.items():
            index_ltp = st.session_state.index_ltp.get(index)
            if not index_ltp:
                continue

            atm = int(round(index_ltp / step) * step)

            for i in range(-10, 11):
                strike = atm + (i * step)
                symbols.append(f"NSE_{index}26FEB{strike}CE")
                symbols.append(f"NSE_{index}26FEB{strike}PE")

        # batch fetch (≤50 symbols)
        for i in range(0, len(symbols), 50):
            batch = symbols[i:i+50]
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
# UI TABLES (LOCKED)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
    ),
    use_container_width=True
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

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
