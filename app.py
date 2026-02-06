import time
import streamlit as st
from growwapi import GrowwAPI

# ===============================
# PAGE CONFIG
# ===============================
st.set_page_config(
    page_title="Groww NSE Paper Trading Dashboard",
    layout="wide"
)

st.title("📊 Groww NSE Paper Trading Dashboard")

# ===============================
# SESSION STATE
# ===============================
if "groww" not in st.session_state:
    st.session_state.groww = None

if "logs" not in st.session_state:
    st.session_state.logs = []

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0

# ===============================
# SIDEBAR
# ===============================
st.sidebar.header("Setup")

token = st.sidebar.text_area(
    "Paste Groww access token (1 only)",
    height=120
)

poll_seconds = st.sidebar.number_input(
    "Poll interval (seconds)",
    min_value=3,
    max_value=30,
    value=5
)

if st.sidebar.button("Initialize token"):
    try:
        st.session_state.groww = GrowwAPI(token.strip())
        st.session_state.logs.append("token_validation => valid")
    except Exception as e:
        st.session_state.logs.append(f"token_validation => failed: {e}")

# ===============================
# BOT STATUS
# ===============================
if st.session_state.groww:
    st.success("🟢 Running")
else:
    st.warning("🔴 Not Initialized")

# ===============================
# AUTO REFRESH (LOCKED & SAFE)
# ===============================
now = time.time()
if now - st.session_state.last_refresh >= poll_seconds:
    st.session_state.last_refresh = now
    st.rerun()

# ===============================
# INDEX LTP (CASH)
# ===============================
st.subheader("📈 Live Market Prices (Index)")

if st.session_state.groww:
    try:
        index_ltp = st.session_state.groww.get_ltp(
            segment=st.session_state.groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY")
        )

        st.table([
            {"Symbol": sym, "LTP": ltp}
            for sym, ltp in index_ltp.items()
        ])

        st.session_state.logs.append(f"INDEX LTP {index_ltp}")

    except Exception as e:
        st.error("Index fetch failed")
        st.session_state.logs.append(f"index_error: {e}")

# ===============================
# F&O LTP (CORRECT LOGIC)
# ===============================
st.subheader("📉 Live Market Prices (F&O)")

if st.session_state.groww:
    try:
        # 🔹 Monthly Option → get_ltp (supports multiple)
        monthly_symbol = "NSE_NIFTY26FEB24500CE"

        monthly_ltp = st.session_state.groww.get_ltp(
            segment=st.session_state.groww.SEGMENT_FNO,
            exchange_trading_symbols=monthly_symbol
        )

        # 🔹 Weekly Option → get_quote (ONLY ONE SYMBOL)
        weekly_symbol = "NIFTY2621020400CE"

        weekly_quote = st.session_state.groww.get_quote(
            st.session_state.groww.EXCHANGE_NSE,
            st.session_state.groww.SEGMENT_FNO,
            weekly_symbol
        )

        fno_rows = [
            {
                "Symbol": monthly_symbol,
                "LTP": monthly_ltp.get(monthly_symbol)
            },
            {
                "Symbol": weekly_symbol,
                "LTP": weekly_quote.get("ltp")
            }
        ]

        st.table(fno_rows)

        st.session_state.logs.append(
            f"FNO LTP monthly={monthly_ltp} weekly={weekly_quote.get('ltp')}"
        )

    except Exception as e:
        st.error("F&O fetch failed")
        st.session_state.logs.append(f"fno_error: {e}")

# ===============================
# LOGS
# ===============================
st.subheader("🧾 Live logs (last 50)")
for log in st.session_state.logs[-50:]:
    st.code(log)
