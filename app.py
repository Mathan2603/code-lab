import streamlit as st
import time
from growwapi import GrowwAPI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww NSE Paper Trading Dashboard",
    layout="wide"
)

st.title("📊 Groww NSE Paper Trading Dashboard")

# =========================
# SESSION STATE INIT
# =========================
if "client" not in st.session_state:
    st.session_state.client = None

if "running" not in st.session_state:
    st.session_state.running = False

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0.0

if "index_ltp" not in st.session_state:
    st.session_state.index_ltp = {}

if "fno_ltp" not in st.session_state:
    st.session_state.fno_ltp = {}

if "logs" not in st.session_state:
    st.session_state.logs = []

# =========================
# LOG HELPER
# =========================
def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{ts}] {msg}")
    st.session_state.logs = st.session_state.logs[-50:]

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("Setup")

    token = st.text_area(
        "Paste Groww access token (1 only)",
        height=120
    )

    poll_seconds = st.number_input(
        "Poll interval (seconds)",
        min_value=3,
        max_value=60,
        value=5
    )

    if st.button("Initialize token"):
        try:
            st.session_state.client = GrowwAPI(token.strip())
            log("token_validation => valid")
        except Exception as e:
            log(f"token_validation => failed: {e}")

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
# BOT STATUS
# =========================
st.subheader("Bot status")
if st.session_state.running:
    st.success("🟢 Running")
else:
    st.warning("🔴 Stopped")

# =========================
# AUTO REFRESH (SAFE)
# =========================
now = time.time()
if now - st.session_state.last_refresh >= poll_seconds:
    st.session_state.last_refresh = now
    st.rerun()

# =========================
# FETCH INDEX LTP
# =========================
def fetch_index_ltp(client):
    resp = client.get_ltp(
        segment="CASH",
        exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY")
    )
    return {
        k: float(v["last_price"])
        for k, v in resp.items()
    }

# =========================
# FETCH F&O MONTHLY
# =========================
def fetch_fno_monthly(client):
    resp = client.get_ltp(
        segment="FNO",
        exchange_trading_symbols=("NSE_NIFTY26FEB24500CE",)
    )
    return {
        k: float(v["last_price"])
        for k, v in resp.items()
    }

# =========================
# FETCH F&O WEEKLY
# =========================
def fetch_fno_weekly(client):
    q = client.get_quote(trading_symbol="NIFTY2621020400CE")
    return {"NIFTY2621020400CE": float(q["last_price"])}

# =========================
# ENGINE LOOP (SAFE)
# =========================
if st.session_state.running and st.session_state.client:
    try:
        st.session_state.index_ltp = fetch_index_ltp(st.session_state.client)
        log(f"INDEX LTP fetched {st.session_state.index_ltp}")

        fno = {}
        fno.update(fetch_fno_monthly(st.session_state.client))
        fno.update(fetch_fno_weekly(st.session_state.client))
        st.session_state.fno_ltp = fno

        log(f"F&O LTP fetched {st.session_state.fno_ltp}")

    except Exception as e:
        log(f"engine error: {e}")

# =========================
# UI TABLES
# =========================
st.subheader("📈 Live Market Prices (Index)")
if st.session_state.index_ltp:
    st.dataframe(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()],
        width="stretch"
    )
else:
    st.info("Waiting for index data...")

st.subheader("📉 Live Market Prices (F&O)")
if st.session_state.fno_ltp:
    st.dataframe(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.fno_ltp.items()],
        width="stretch"
    )
else:
    st.info("Waiting for F&O data...")

# =========================
# LOGS
# =========================
st.subheader("Live logs (last 50)")
for l in st.session_state.logs:
    st.text(l)
