import streamlit as st
import time
from typing import Dict, List

from growwapi import GrowwAPI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww NSE Paper Trading Dashboard",
    layout="wide",
)

# =========================
# SESSION STATE
# =========================
if "groww" not in st.session_state:
    st.session_state.groww = None

if "running" not in st.session_state:
    st.session_state.running = False

if "logs" not in st.session_state:
    st.session_state.logs: List[str] = []

if "index_ltp" not in st.session_state:
    st.session_state.index_ltp: Dict[str, float] = {}

if "fno_ltp" not in st.session_state:
    st.session_state.fno_ltp: Dict[str, float] = {}

# =========================
# HELPERS
# =========================
def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{ts}] {msg}")
    st.session_state.logs = st.session_state.logs[-50:]


def init_groww(token: str):
    st.session_state.groww = GrowwAPI(token=token)
    log("token_validation => valid")


# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("Setup")

    token = st.text_area(
        "Paste Groww access token (1 only)",
        height=120
    )

    poll_interval = st.number_input(
        "Poll interval (seconds)",
        min_value=3,
        max_value=30,
        value=5
    )

    if st.button("Initialize token"):
        if token.strip():
            init_groww(token.strip())
        else:
            st.error("Token cannot be empty")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start"):
            st.session_state.running = True
            log("engine started")

    with col2:
        if st.button("Stop"):
            st.session_state.running = False
            log("engine stopped")

# =========================
# MAIN UI
# =========================
st.title("📊 Groww NSE Paper Trading Dashboard")

# Bot status
st.subheader("Bot status")
if st.session_state.running:
    st.success("🟢 Running")
else:
    st.warning("🟡 Stopped")

# =========================
# INDEX LTP
# =========================
st.subheader("📈 Live Market Prices (Index)")

index_placeholder = st.empty()

# =========================
# F&O LTP
# =========================
st.subheader("📉 Live Market Prices (F&O)")

fno_placeholder = st.empty()

# =========================
# LOGS
# =========================
st.subheader("Live logs (last 50)")
log_placeholder = st.empty()

# =========================
# ENGINE LOOP
# =========================
if st.session_state.running and st.session_state.groww:

    try:
        groww = st.session_state.groww

        # -------- INDEX LTP (MULTI SYMBOL, get_ltp) --------
        index_symbols = ["NSE_NIFTY", "NSE_BANKNIFTY"]

        index_resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=tuple(index_symbols)
        )

        # get_ltp returns dict for multi symbols
        if isinstance(index_resp, dict):
            st.session_state.index_ltp = index_resp
            log(f"INDEX LTP {index_resp}")

        # -------- F&O LTP (SINGLE SYMBOL, get_quote) --------
        # Example WEEKLY or MONTHLY option
        fno_symbol = "NIFTY26FEB24500CE"

        quote = groww.get_quote(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_FNO,
            fno_symbol
        )

        # get_quote returns dict
        if isinstance(quote, dict) and "ltp" in quote:
            st.session_state.fno_ltp = {fno_symbol: quote["ltp"]}
            log(f"FNO LTP {st.session_state.fno_ltp}")

    except Exception as e:
        log(f"engine error: {e}")

# =========================
# RENDER INDEX TABLE
# =========================
if st.session_state.index_ltp:
    index_placeholder.table([
        {"Symbol": k, "LTP": v}
        for k, v in st.session_state.index_ltp.items()
    ])
else:
    index_placeholder.info("Waiting for index data...")

# =========================
# RENDER F&O TABLE
# =========================
if st.session_state.fno_ltp:
    fno_placeholder.table([
        {"Symbol": k, "LTP": v}
        for k, v in st.session_state.fno_ltp.items()
    ])
else:
    fno_placeholder.info("Waiting for F&O data...")

# =========================
# RENDER LOGS
# =========================
log_placeholder.code("\n".join(st.session_state.logs))

# =========================
# AUTO REFRESH
# =========================
if st.session_state.running:
    time.sleep(poll_interval)
    st.rerun()
