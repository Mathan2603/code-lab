from __future__ import annotations

import time
import streamlit as st
from typing import Dict, List

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

if "ltp_cash" not in st.session_state:
    st.session_state.ltp_cash: Dict[str, float] = {}

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
# MAIN LOOP (SAFE STREAMLIT WAY)
# ============================
if st.session_state.running and st.session_state.broker:

    try:
        # ----------------------------
        # CASH / INDEX LTP
        # ----------------------------
        cash_symbols = ["NSE_NIFTY", "NSE_BANKNIFTY"]
        cash_ltp = st.session_state.broker.get_index_ltp(cash_symbols)
        st.session_state.ltp_cash = cash_ltp

        # ----------------------------
        # F&O MONTHLY (MULTI)
        # ----------------------------
        monthly_fno_symbols = [
            "NSE_NIFTY26FEB24500CE",
            "NSE_NIFTY26FEB24600CE",
        ]

        monthly_ltp = st.session_state.broker.get_fno_monthly_ltp(
            monthly_fno_symbols
        )

        # ----------------------------
        # F&O WEEKLY (SINGLE ONLY)
        # ----------------------------
        weekly_symbol = "NIFTY2621020400CE"
        weekly_ltp = st.session_state.broker.get_fno_weekly_ltp(
            weekly_symbol
        )

        # MERGE FNO DATA
        fno_ltp = {}
        fno_ltp.update(monthly_ltp)
        fno_ltp.update(weekly_ltp)

        st.session_state.ltp_fno = fno_ltp

        st.session_state.logs.append(
            f"LTP fetched CASH={cash_ltp} FNO={fno_ltp}"
        )

    except Exception as e:
        st.session_state.logs.append(f"engine error: {e}")

    # ⏱️ THIS IS THE REFRESH MECHANISM
    time.sleep(poll_seconds)
    st.rerun()

# ============================
# DISPLAY CASH LTP
# ============================
st.subheader("📊 Live Market Prices (Index)")

if st.session_state.ltp_cash:
    st.table(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.ltp_cash.items()]
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
