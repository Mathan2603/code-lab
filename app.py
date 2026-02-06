from __future__ import annotations

import time
import streamlit as st
from typing import Dict

from paper_trader.broker import GrowwPaperBroker

# ============================
# PAGE CONFIG
# ============================
st.set_page_config(
    page_title="Groww NSE Paper Trading Dashboard",
    layout="wide",
)

st.title("📈 Groww NSE Paper Trading Dashboard")

# ============================
# SESSION STATE
# ============================
if "broker" not in st.session_state:
    st.session_state.broker = None

if "running" not in st.session_state:
    st.session_state.running = False

if "logs" not in st.session_state:
    st.session_state.logs = []

if "ltp_data" not in st.session_state:
    st.session_state.ltp_data: Dict[str, float] = {}

if "last_poll" not in st.session_state:
    st.session_state.last_poll = 0.0

# ============================
# SIDEBAR
# ============================
with st.sidebar:
    st.header("Setup")

    token = st.text_area(
        "Paste Groww access token (1 only for now)",
        height=120,
    ).strip()

    poll_seconds = st.number_input(
        "Poll interval (seconds)",
        min_value=3,
        max_value=60,
        value=5,
    )

    if st.button("Initialize token"):
        if token:
            st.session_state.broker = GrowwPaperBroker(token)
            st.session_state.logs.append("token_validation => valid")
        else:
            st.error("Token required")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start"):
            st.session_state.running = True
            st.session_state.logs.append("engine started")

    with col2:
        if st.button("Stop"):
            st.session_state.running = False
            st.session_state.logs.append("engine stopped")

# ============================
# BOT STATUS
# ============================
st.subheader("Bot status")
st.markdown("🟢 Running" if st.session_state.running else "🔴 Stopped")

# ============================
# POLLING LOOP
# ============================
if st.session_state.running and st.session_state.broker:
    now = time.time()
    if now - st.session_state.last_poll >= poll_seconds:
        st.session_state.last_poll = now

        try:
            index_symbols = ["NSE_NIFTY", "NSE_BANKNIFTY"]
            ltp = st.session_state.broker.get_index_ltp(index_symbols)

            st.session_state.ltp_data = ltp
            st.session_state.logs.append(f"LTP fetched {ltp}")

        except Exception as e:
            st.session_state.logs.append(f"engine error: {e}")

# ============================
# LTP DISPLAY
# ============================
st.subheader("📊 Live Market Prices (LTP)")

if st.session_state.ltp_data:
    st.table(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_data.items()]
    )
else:
    st.info("Waiting for market data...")

# ============================
# LOGS
# ============================
st.subheader("Live logs (last 50)")
for line in st.session_state.logs[-50:]:
    st.code(line)
