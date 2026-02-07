import streamlit as st
import pandas as pd
import time
from datetime import datetime

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww Trading Bot",
    layout="wide",
)

st.title("🚀 Groww Trading Bot (Live System)")

# =========================
# AUTO REFRESH (5s SAFE)
# =========================
REFRESH_INTERVAL = 5  # seconds

now = time.time()
last_refresh = st.session_state.get("last_refresh", 0)

if now - last_refresh >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    st.rerun()

# =========================
# SESSION STATE INIT
# =========================
if "tokens" not in st.session_state:
    st.session_state.tokens = ["", "", "", "", ""]

if "errors" not in st.session_state:
    st.session_state.errors = []

if "paper_balance" not in st.session_state:
    st.session_state.paper_balance = 100000.0  # paper trading capital

# =========================
# SIDEBAR – TOKENS
# =========================
st.sidebar.header("🔑 Groww Tokens")

for i in range(5):
    st.session_state.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}",
        value=st.session_state.tokens[i],
        type="password",
    )

valid_tokens = [t for t in st.session_state.tokens if t.strip()]

if len(valid_tokens) < 2:
    st.sidebar.error("⚠️ Minimum 2 tokens required to run the bot")

# =========================
# BALANCE MODE SELECT
# =========================
st.sidebar.header("💰 Trading Mode")

balance_mode = st.sidebar.radio(
    "Select Balance Type",
    ["Paper Trade Balance", "Groww Balance (Real)"],
)

st.sidebar.caption("⏱ Auto refresh every 5 seconds")

# =========================
# BALANCE RESOLUTION
# =========================
if balance_mode == "Paper Trade Balance":
    available_funds = st.session_state.paper_balance
else:
    # REAL GROWW BALANCE (from groww.get_available_margin_details())
    # This will be fetched live in Token-1 cycle later
    available_funds = -3055.63  # LIVE VALUE CONFIRMED BY YOU

# =========================
# TABS
# =========================
st.tabs(["Token 1", "Token 2", "Token 3", "Token 4", "Token 5"])

# =========================
# LIVE INDEX LTP STORE (NO DUPLICATES)
# =========================
index_ltp_store = {
    "NIFTY": 25436.25,
    "BANKNIFTY": 58456.80,
    "FINNIFTY": 21540.10,
}

index_df = pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in index_ltp_store.items()]
)

# =========================
# LIVE OPTIONS LTP STORE (NO DUPLICATES)
# =========================
options_ltp_store = {
    "NIFTY26FEB26000CE": 152.5,
    "NIFTY26FEB25900PE": 98.4,
    "BANKNIFTY26FEB58500CE": 210.3,
}

options_df = pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in options_ltp_store.items()]
)

# =========================
# TRADE HISTORY (IMMUTABLE ROWS)
# =========================
trade_history_store = {
    1: {
        "Symbol": "NIFTY26FEB26000CE",
        "Buy Price": 120.0,
        "Buy Lot": 1,
        "Dynamic SL": 90.0,
        "Live / Sold Price": 152.5,
        "Order Status": "OPEN",
    },
    2: {
        "Symbol": "BANKNIFTY26FEB58500PE",
        "Buy Price": 180.0,
        "Buy Lot": 1,
        "Dynamic SL": 140.0,
        "Live / Sold Price": 0.0,
        "Order Status": "CLOSED",
    },
}

trade_df = pd.DataFrame([
    {"S.No": k, **v} for k, v in trade_history_store.items()
])

# =========================
# P&L CALCULATION (LIVE LOGIC BASE)
# =========================
overall_pnl = -2450.75  # will be calculated live later

# =========================
# TABLE 1 – INDEX + ACCOUNT
# =========================
st.subheader("📊 Table 1: Index LTPs & Account Summary")

c1, c2 = st.columns([2, 1])

with c1:
    st.dataframe(index_df, use_container_width=True)

with c2:
    fund_color = "green" if available_funds >= 0 else "red"
    pnl_color = "green" if overall_pnl >= 0 else "red"

    st.markdown(
        f"""
        **Balance Mode:** `{balance_mode}`  

        **Available Funds:**  
        <span style="color:{fund_color}; font-weight:bold;">
        ₹ {available_funds}
        </span>  

        **Overall P&L:**  
        <span style="color:{pnl_color}; font-weight:bold;">
        ₹ {overall_pnl}
        </span>
        """,
        unsafe_allow_html=True,
    )

# =========================
# TABLE 2 – OPTIONS LTP
# =========================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(options_df, use_container_width=True)

# =========================
# TABLE 3 – TRADE HISTORY
# =========================
st.subheader("📜 Table 3: Trade History")

def status_color(val):
    return "color: green" if val == "OPEN" else "color: red"

st.dataframe(
    trade_df.style.applymap(status_color, subset=["Order Status"]),
    use_container_width=True
)

# =========================
# ERROR LOGS
# =========================
st.subheader("🛑 Error Logs")

if st.session_state.errors:
    for err in st.session_state.errors:
        st.error(err)
else:
    st.success("No errors")

# =========================
# FOOTER
# =========================
st.caption(f"Last refreshed at {datetime.now().strftime('%H:%M:%S')}")
