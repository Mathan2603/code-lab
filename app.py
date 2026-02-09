import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI
import math

# =========================================================
# UI CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL = 50000.0
LOT_SIZE = 50

# =========================================================
# HELPERS
# =========================================================
def extract_ltp(v):
    if isinstance(v, dict):
        return v.get("ltp") or v.get("last_price") or v.get("price")
    if isinstance(v, (int, float)):
        return float(v)
    return None

def log_error(msg):
    st.session_state.errors.append(str(msg))

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
    st.session_state.last_refresh = 0

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

# =========================================================
# INIT GROWW CLIENTS (TOKEN SPLIT)
# =========================================================
gw_index = GrowwAPI(st.session_state.tokens[0])
gw_monthly = GrowwAPI(st.session_state.tokens[1])
gw_weekly = GrowwAPI(st.session_state.tokens[2])

# =========================================================
# 1️⃣ FETCH INDEX LTPs (TOKEN 1)
# =========================================================
try:
    resp = gw_index.get_ltp(
        segment=gw_index.SEGMENT_CASH,
        exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
    )
    st.session_state.index_ltp.clear()
    for sym, raw in resp.items():
        ltp = extract_ltp(raw)
        if ltp:
            st.session_state.index_ltp[sym.replace("NSE_", "")] = ltp
except Exception as e:
    log_error(e)

# =========================================================
# 2️⃣ AUTO EXPIRY DETECTION (MONTHLY ONLY)
# =========================================================
expiry_map = {}
try:
    for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
        expiries = gw_index.get_expiries(gw_index.EXCHANGE_NSE, idx)
        if expiries:
            expiry_map[idx] = expiries[0]  # nearest monthly
except Exception as e:
    log_error(e)

# =========================================================
# 3️⃣ NEAREST STRIKE CALCULATION
# =========================================================
STRIKE_STEP = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50
}

nearest_symbols = []
nearest_rows = []

for idx, ltp in st.session_state.index_ltp.items():
    if idx not in expiry_map:
        continue

    step = STRIKE_STEP[idx]
    atm = round(ltp / step) * step
    expiry = expiry_map[idx].replace("-", "")

    for i in range(-10, 11):
        strike = int(atm + i * step)
        for opt in ["CE", "PE"]:
            symbol = f"NSE_{idx}{expiry}{strike}{opt}"
            nearest_symbols.append(symbol)
            nearest_rows.append({
                "Index": idx,
                "Symbol": symbol,
                "Strike": strike,
                "Type": opt,
                "LTP": None
            })

# =========================================================
# 4️⃣ FETCH NEAREST STRIKE LTPs (TOKEN 2, BATCHED)
# =========================================================
try:
    for i in range(0, len(nearest_symbols), 50):
        batch = nearest_symbols[i:i+50]
        resp = gw_monthly.get_ltp(
            segment=gw_monthly.SEGMENT_FNO,
            exchange_trading_symbols=tuple(batch)
        )
        for sym, raw in resp.items():
            ltp = extract_ltp(raw)
            if ltp:
                st.session_state.monthly_ltp[sym] = ltp
except Exception as e:
    log_error(e)

# attach LTPs
for row in nearest_rows:
    row["LTP"] = st.session_state.monthly_ltp.get(row["Symbol"])

st.session_state.nearest_strikes = nearest_rows

# =========================================================
# UI TABLES (LOCKED STRUCTURE)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
    ),
    use_container_width=True
)

st.subheader("📌 Table 2A: Nearest Strikes (Auto)")
st.dataframe(
    pd.DataFrame(st.session_state.nearest_strikes),
    use_container_width=True
)

st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.trades), use_container_width=True)

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for e in st.session_state.errors[-5:]:
        st.error(e)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
