import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww Paper Trading Dashboard",
    layout="wide",
)

st.title("🚀 Groww Paper Trading Bot – UI Wireframe")

# =========================
# AUTO REFRESH (5 seconds)
# =========================
st_autorefresh(interval=5000, key="auto_refresh")

# =========================
# SESSION STATE INIT
# =========================
if "tokens" not in st.session_state:
    st.session_state.tokens = ["", "", "", "", ""]

if "errors" not in st.session_state:
    st.session_state.errors = []

# =========================
# SIDEBAR – TOKEN INPUT
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

run_bot = st.sidebar.button("▶️ Initialize Bot")

# =========================
# TABS FOR EACH TOKEN
# =========================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Token 1", "Token 2", "Token 3", "Token 4", "Token 5"]
)

# =========================
# MOCK DATA (UI ONLY)
# =========================
index_data = pd.DataFrame({
    "Symbol": ["NIFTY", "BANKNIFTY", "FINNIFTY"],
    "LTP": [25436.25, 58456.80, 21540.10]
})

funds_data = {
    "Available Funds": 100000,
    "Overall P&L": -2450.75
}

options_ltp_data = pd.DataFrame({
    "Symbol": [
        "NIFTY26FEB26000CE",
        "NIFTY26FEB25900PE",
        "BANKNIFTY26FEB58500CE",
    ],
    "LTP": [152.5, 98.4, 210.3]
})

trade_history = pd.DataFrame({
    "S.No": [1, 2],
    "Symbol": ["NIFTY26FEB26000CE", "BANKNIFTY26FEB58500PE"],
    "Buy Price": [120.0, 180.0],
    "Buy Lot": [1, 1],
    "Dynamic SL": [90.0, 140.0],
    "Live / Sold Price": [152.5, 0.0],
    "Order Status": ["OPEN", "CLOSED"]
})

# =========================
# TABLE 1 – INDEX + FUNDS
# =========================
st.subheader("📊 Table 1: Index LTPs & Account Summary")

col1, col2 = st.columns([2, 1])

with col1:
    st.dataframe(
        index_data.style.set_properties(**{"color": "white"}),
        use_container_width=True
    )

with col2:
    pnl_color = "green" if funds_data["Overall P&L"] >= 0 else "red"
    st.markdown(f"""
    **Available Funds:** ₹ {funds_data['Available Funds']}  
    **Overall P&L:** <span style="color:{pnl_color}; font-weight:bold;">
    ₹ {funds_data['Overall P&L']}
    </span>
    """, unsafe_allow_html=True)

# =========================
# TABLE 2 – OPTIONS LTP
# =========================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")

st.dataframe(
    options_ltp_data.style.set_properties(**{"color": "white"}),
    use_container_width=True
)

# =========================
# TABLE 3 – TRADE HISTORY
# =========================
st.subheader("📜 Table 3: Trade History")

def color_status(val):
    if val == "OPEN":
        return "color: green"
    return "color: red"

st.dataframe(
    trade_history.style.applymap(color_status, subset=["Order Status"]),
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
