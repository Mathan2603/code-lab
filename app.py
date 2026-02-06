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
# SESSION STATE INIT
# ============================
if "broker" not in st.session_state:
    st.session_state.broker = None

if "running" not in st.session_state:
    st.session_state.running = False

if "logs" not in st.session_state:
    st.session_state.logs = []

if "last_fetch_ts" not in st.session_state:
    st.session_state.last_fetch_ts = 0.0

if "ltp_index" not in st.session_state:
    st.session_state.ltp_index: Dict[str, float] = {}

if "ltp_fno" not in st.session_state:
    st.session_state.ltp_fno: Dict[str, float] = {}

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
        max_value=30,
        value=5,
    )

    if st.button("Initialize token"):
        if not token:
            st.error("Token required")
        else:
            st.session_state.broker = GrowwPaperBroker(token)
            st.session_state.logs.append("token_validation => valid")

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
# FETCH LOGIC (CORRECT WAY)
# ============================
now = time.time()

if (
    st.session_state.running
    and st.session_state.broker
    and now - st.session_state.last_fetch_ts >= poll_seconds
):
    try:
        broker = st.session_state.broker

        # ----------------------------
        # INDEX LTP (CASH)
        # ----------------------------
        index_symbols = ["NSE_NIFTY", "NSE_BANKNIFTY"]
        index_ltp = broker.get_index_ltp(index_symbols)

        if not isinstance(index_ltp, dict):
            raise ValueError("Index LTP must be dict")

        st.session_state.ltp_index = index_ltp

        # ----------------------------
        # F&O MONTHLY (MULTI)
        # ----------------------------
        monthly_symbols = [
            "NSE_NIFTY26FEB24500CE",
            "NSE_NIFTY26FEB24600CE",
        ]
        monthly_ltp = broker.get_fno_monthly_ltp(monthly_symbols)

        if not isinstance(monthly_ltp, dict):
            raise ValueError("Monthly FNO LTP must be dict")

        # ----------------------------
        # F&O WEEKLY (SINGLE)
        # ----------------------------
        weekly_symbol = "NIFTY2621020400CE"
        weekly_ltp = broker.get_fno_weekly_ltp(weekly_symbol)

        if not isinstance(weekly_ltp, dict):
            raise ValueError("Weekly FNO LTP must be dict")

        fno_ltp = {}
        fno_ltp.update(monthly_ltp)
        fno_ltp.update(weekly_ltp)

        st.session_state.ltp_fno = fno_ltp

        st.session_state.logs.append(
            f"LTP fetched | INDEX={index_ltp} | FNO={fno_ltp}"
        )

        st.session_state.last_fetch_ts = now

    except Exception as e:
        st.session_state.logs.append(f"engine error: {e}")

# ============================
# DISPLAY INDEX LTP
# ============================
st.subheader("📊 Live Market Prices (Index)")

if st.session_state.ltp_index:
    st.table(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_index.items()]
    )
else:
    st.info("Waiting for index data...")

# ============================
# DISPLAY F&O LTP
# ============================
st.subheader("📈 Live Market Prices (F&O)")

if st.session_state.ltp_fno:
    st.table(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_fno.items()]
    )
else:
    st.info("Waiting for F&O data...")

# ============================
# LOGS
# ============================
st.subheader("Live logs (last 50)")
for line in st.session_state.logs[-50:]:
    st.code(line)
