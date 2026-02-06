from __future__ import annotations

import time
import streamlit as st
from growwapi import GrowwAPI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww Paper Trader",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Groww Paper Trading Dashboard")
st.caption("Index + Weekly F&O LTP • Auto refresh every 5 seconds")

# =========================
# SESSION STATE INIT
# =========================
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0.0

if "groww" not in st.session_state:
    st.session_state.groww = None

# =========================
# SIDEBAR – TOKEN INPUT
# =========================
with st.sidebar:
    st.header("🔑 Groww Token")
    token_input = st.text_area(
        "Paste Groww Access Token",
        height=150,
        placeholder="eyJraWQiOiJ...",
    )

    weekly_symbol = st.text_input(
        "Weekly Option Symbol",
        value="NIFTY2621026400CE",
        help="Example: NIFTY2621026400CE (NO NSE_ prefix)",
    )

    poll_seconds = st.number_input(
        "Refresh interval (seconds)",
        min_value=5,
        max_value=30,
        value=5,
        step=1,
    )

    if st.button("🚀 Initialize", width="stretch"):
        if not token_input.strip():
            st.error("Please paste a valid Groww token")
        else:
            st.session_state.groww = GrowwAPI(token_input.strip())
            st.success("Groww API initialized successfully")

# =========================
# STOP IF NOT INITIALIZED
# =========================
if st.session_state.groww is None:
    st.info("👈 Paste token and click Initialize")
    st.stop()

groww = st.session_state.groww

# =========================
# AUTO REFRESH (SAFE)
# =========================
now = time.time()
if now - st.session_state.last_refresh >= poll_seconds:
    st.session_state.last_refresh = now
    st.rerun()

# =========================
# FETCH INDEX LTP (CASH)
# =========================
index_error = None
index_ltp = {}

try:
    index_ltp = groww.get_ltp(
        segment=groww.SEGMENT_CASH,
        exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY"),
    )
except Exception as e:
    index_error = str(e)

# =========================
# FETCH WEEKLY OPTION LTP (F&O)
# =========================
weekly_error = None
weekly_ltp = None

try:
    quote = groww.get_quote(
        exchange=groww.EXCHANGE_NSE,
        segment=groww.SEGMENT_FNO,
        trading_symbol=weekly_symbol.strip(),
    )
    weekly_ltp = quote.get("last_price")
except Exception as e:
    weekly_error = str(e)

# =========================
# UI DISPLAY
# =========================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Index LTP")
    if index_error:
        st.error(index_error)
    else:
        st.table(
            [
                {"Symbol": k, "LTP": v}
                for k, v in index_ltp.items()
            ]
        )

with col2:
    st.subheader("🧾 Weekly Option LTP")
    if weekly_error:
        st.error(weekly_error)
    else:
        st.table(
            [
                {
                    "Symbol": weekly_symbol,
                    "LTP": weekly_ltp,
                }
            ]
        )

st.caption(f"⏱ Auto-refreshing every {poll_seconds} seconds")
