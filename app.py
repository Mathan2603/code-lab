import streamlit as st
import time
from growwapi import GrowwAPI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="Groww NSE Paper Trading Dashboard", layout="wide")
st.title("📊 Groww NSE Paper Trading Dashboard")

# =========================
# SESSION STATE
# =========================
for k, v in {
    "client": None,
    "running": False,
    "last_refresh": 0.0,
    "index_ltp": {},
    "fno_ltp": {},
    "logs": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================
# LOG
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

    token = st.text_area("Paste Groww access token (1 only)", height=120)

    poll_seconds = st.number_input("Poll interval (seconds)", 3, 60, 5)

    if st.button("Initialize token"):
        try:
            st.session_state.client = GrowwAPI(token.strip())
            log("token_validation => valid")
        except Exception as e:
            log(f"token_validation => failed: {e}")

    if st.button("Start"):
        st.session_state.running = True
        log("engine started")

    if st.button("Stop"):
        st.session_state.running = False
        log("engine stopped")

# =========================
# STATUS
# =========================
st.subheader("Bot status")
st.success("🟢 Running") if st.session_state.running else st.warning("🔴 Stopped")

# =========================
# AUTO REFRESH (SAFE)
# =========================
now = time.time()
if now - st.session_state.last_refresh >= poll_seconds:
    st.session_state.last_refresh = now
    st.rerun()

# =========================
# NORMALIZE PRICE
# =========================
def extract_price(obj):
    if isinstance(obj, dict):
        return float(obj.get("last_price", 0))
    if isinstance(obj, (int, float)):
        return float(obj)
    return 0.0

# =========================
# FETCH INDEX
# =========================
def fetch_index(client):
    data = client.get_ltp(
        segment="CASH",
        exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY")
    )
    return {k: extract_price(v) for k, v in data.items()}

# =========================
# FETCH F&O
# =========================
def fetch_fno(client):
    result = {}

    # Monthly (multi allowed)
    monthly = client.get_ltp(
        segment="FNO",
        exchange_trading_symbols=("NSE_NIFTY26FEB24500CE",)
    )
    for k, v in monthly.items():
        result[k] = extract_price(v)

    # Weekly (ONLY SINGLE)
    weekly = client.get_quote(trading_symbol="NIFTY2621020400CE")
    result["NIFTY2621020400CE"] = extract_price(weekly)

    return result

# =========================
# ENGINE
# =========================
if st.session_state.running and st.session_state.client:
    try:
        st.session_state.index_ltp = fetch_index(st.session_state.client)
        log(f"INDEX LTP {st.session_state.index_ltp}")

        st.session_state.fno_ltp = fetch_fno(st.session_state.client)
        log(f"F&O LTP {st.session_state.fno_ltp}")

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
