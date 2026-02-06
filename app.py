from __future__ import annotations

import time
import streamlit as st
from typing import List, Dict

from paper_trader.broker import GrowwPaperBroker
from paper_trader.utils import log

# ============================
# PAGE CONFIG
# ============================
st.set_page_config(
    page_title="Groww NSE Paper Trading Dashboard",
    layout="wide",
)

st.title("📈 Groww NSE Paper Trading Dashboard")

# ============================
# SESSION STATE INIT
# ============================
if "engine_running" not in st.session_state:
    st.session_state.engine_running = False

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if "active_token" not in st.session_state:
    st.session_state.active_token = None

if "ltp_index" not in st.session_state:
    st.session_state.ltp_index = {}

if "ltp_monthly" not in st.session_state:
    st.session_state.ltp_monthly = {}

if "ltp_weekly" not in st.session_state:
    st.session_state.ltp_weekly = {}

if "logs" not in st.session_state:
    st.session_state.logs = []

# ============================
# SIDEBAR – SETUP
# ============================
st.sidebar.header("Setup")

tokens_text = st.sidebar.text_area(
    "Paste Groww access token(s) (1–5, one per line)",
    height=120,
)

poll_seconds = st.sidebar.number_input(
    "Poll interval (seconds)",
    min_value=3,
    max_value=30,
    value=5,
)

lot_qty = st.sidebar.number_input(
    "Lot quantity",
    min_value=1,
    value=1,
)

init_btn = st.sidebar.button("Initialize tokens")
start_btn = st.sidebar.button("Start")
stop_btn = st.sidebar.button("Stop")

# ============================
# TOKEN INITIALIZATION
# ============================
if init_btn:
    tokens = [t.strip() for t in tokens_text.splitlines() if t.strip()]

    if not tokens:
        st.sidebar.error("Please paste at least one token")
    else:
        st.session_state.active_token = tokens[0]
        st.session_state.broker = GrowwPaperBroker(tokens[0])
        st.sidebar.success(f"Initialized {len(tokens)} token(s)")
        st.session_state.logs.append("token_validation => valid")

# ============================
# START / STOP
# ============================
if start_btn and st.session_state.active_token:
    st.session_state.engine_running = True
    st.session_state.logs.append("engine started")

if stop_btn:
    st.session_state.engine_running = False
    st.session_state.logs.append("engine stopped")

# ============================
# BOT STATUS
# ============================
st.subheader("Bot status")

if st.session_state.engine_running:
    st.markdown("🟢 **Running**")
else:
    st.markdown("🔴 **Stopped**")

if st.session_state.active_token:
    st.write(f"Active token: `{st.session_state.active_token[:6]}...`")

# ============================
# FETCH MARKET DATA
# ============================
if st.session_state.engine_running:
    try:
        broker: GrowwPaperBroker = st.session_state.broker

        # -------- INDEX LTP --------
        st.session_state.ltp_index = broker.get_index_ltp(
            ["NSE_NIFTY", "NSE_BANKNIFTY"]
        )

        # -------- MONTHLY OPTIONS (BATCH OK) --------
        monthly_symbols = [
            "NSE_NIFTY26FEB24500CE",
            "NSE_NIFTY26FEB24600CE",
        ]
        st.session_state.ltp_monthly = broker.get_monthly_option_ltp(
            monthly_symbols
        )

        # -------- WEEKLY OPTIONS (SINGLE ONLY) --------
        weekly_symbol = "NIFTY2621020400CE"
        st.session_state.ltp_weekly = {
            weekly_symbol: broker.get_weekly_option_ltp(weekly_symbol)
        }

        st.session_state.logs.append(
            f"LTP fetched {st.session_state.ltp_index}"
        )

    except Exception as e:
        st.session_state.logs.append(f"engine error: {e}")

# ============================
# DISPLAY LTP TABLES
# ============================
st.subheader("📊 Live Market Prices (LTP)")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### Index")
    if st.session_state.ltp_index:
        st.table(
            [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_index.items()]
        )
    else:
        st.info("Waiting for index data...")

with col2:
    st.markdown("### Monthly Options")
    if st.session_state.ltp_monthly:
        st.table(
            [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_monthly.items()]
        )
    else:
        st.info("Waiting for monthly option data...")

with col3:
    st.markdown("### Weekly Options")
    if st.session_state.ltp_weekly:
        st.table(
            [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_weekly.items()]
        )
    else:
        st.info("Waiting for weekly option data...")

# ============================
# LOGS
# ============================
st.subheader("🧾 Live logs (last 50)")

for line in st.session_state.logs[-50:]:
    st.code(line)

# ============================
# AUTO REFRESH (SAFE METHOD)
# ============================
now = time.time()
if now - st.session_state.last_refresh >= poll_seconds:
    st.session_state.last_refresh = now
    st.rerun()
