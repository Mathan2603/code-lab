import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL = 50000.0

# =========================
# SESSION STATE
# =========================
if "tokens" not in st.session_state:
    st.session_state.tokens = ["", "", "", "", ""]

if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

if "errors" not in st.session_state:
    st.session_state.errors = []

# =========================
# SIDEBAR
# =========================
st.sidebar.header("🔑 Groww Tokens")

for i in range(5):
    st.session_state.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}",
        type="password",
        value=st.session_state.tokens[i],
    )

valid_tokens = [t for t in st.session_state.tokens if t.strip()]

if len(valid_tokens) < 2:
    st.sidebar.error("Minimum 2 tokens required")

col_a, col_b = st.sidebar.columns(2)
if col_a.button("▶ Start Bot"):
    st.session_state.bot_running = True

if col_b.button("⏹ Stop Bot"):
    st.session_state.bot_running = False

st.sidebar.caption("Auto refresh every 5 seconds")

# =========================
# AUTO REFRESH
# =========================
now = time.time()
last = st.session_state.get("last_refresh", 0)
if now - last >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    if st.session_state.bot_running:
        st.rerun()

# =========================
# INIT GROWW (TOKEN 1)
# =========================
groww = None
if st.session_state.bot_running and valid_tokens:
    try:
        groww = GrowwAPI(valid_tokens[0])
    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================
# TOKEN 1 – LIVE FETCH
# =========================
index_data = {}
portfolio_data = []
groww_balance = None

if groww:
    try:
        # Index LTPs
        ltp_data = groww.get_ltp(
            exchange="NSE",
            segment="CASH",
            symbols=["NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY"]
        )
        for k, v in ltp_data.items():
            index_data[k.replace("NSE_", "")] = v["ltp"]

        # Portfolio
        portfolio_data = groww.get_portfolio()

        # Balance
        bal = groww.get_available_margin_details()
        groww_balance = bal.get("clear_cash")

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================
# TABLE 1 – INDEX + BALANCE
# =========================
st.subheader("📊 Table 1: Index LTPs & Account Summary")

df_index = pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in index_data.items()]
)

c1, c2 = st.columns([2, 1])
with c1:
    st.dataframe(df_index, use_container_width=True)

with c2:
    st.markdown(
        f"""
        **Paper Trade Capital:**  
        <span style="color:green;font-weight:bold;">₹ {PAPER_CAPITAL}</span>

        **Groww Available Balance (LIVE):**  
        <span style="color:{'green' if (groww_balance or 0) >= 0 else 'red'};font-weight:bold;">
        ₹ {groww_balance if groww_balance is not None else '—'}
        </span>
        """,
        unsafe_allow_html=True,
    )

# =========================
# TABLE 2 – OPTIONS (LIVE FEED PLACEHOLDER)
# =========================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.info("Live option fetching will populate here (Token 2 / 3 / 4 cycles)")

# =========================
# TABLE 3 – TRADE HISTORY
# =========================
st.subheader("📜 Table 3: Trade History")
st.info("Paper trades will appear here once execution logic is enabled")

# =========================
# ERROR LOGS
# =========================
st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for e in st.session_state.errors[-5:]:
        st.error(e)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
