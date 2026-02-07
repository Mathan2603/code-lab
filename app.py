import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI

# =========================================================
# CONFIG (UI + TOKEN-1 LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL = 50000.0

# =========================================================
# SAFE LTP EXTRACTOR (MANDATORY)
# =========================================================
def extract_ltp(value):
    if isinstance(value, dict):
        return (
            value.get("ltp")
            or value.get("last_price")
            or value.get("price")
        )
    if isinstance(value, (int, float)):
        return float(value)
    return None

# =========================================================
# SESSION STATE
# =========================================================
if "tokens" not in st.session_state:
    st.session_state.tokens = ["", "", "", "", ""]

if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

if "errors" not in st.session_state:
    st.session_state.errors = []

if "index_ltp" not in st.session_state:
    st.session_state.index_ltp = {}

# =========================================================
# SIDEBAR (LOCKED)
# =========================================================
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

c1, c2 = st.sidebar.columns(2)
if c1.button("▶ Start Bot"):
    st.session_state.bot_running = True

if c2.button("⏹ Stop Bot"):
    st.session_state.bot_running = False

st.sidebar.caption("Auto refresh every 5 seconds")

# =========================================================
# AUTO REFRESH (SAFE)
# =========================================================
now = time.time()
last = st.session_state.get("last_refresh", 0)
if now - last >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    if st.session_state.bot_running:
        st.rerun()

# =========================================================
# INIT GROWW (TOKEN-1 ONLY)
# =========================================================
groww = None
if st.session_state.bot_running and valid_tokens:
    try:
        groww = GrowwAPI(valid_tokens[0])
    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# TOKEN-1 — CASH LTP + BALANCE (LOCKED LOGIC)
# =========================================================
groww_balance = None

if groww:
    try:
        ltp_resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=(
                "NSE_NIFTY",
                "NSE_BANKNIFTY",
                "NSE_FINNIFTY",
            )
        )

        for symbol, raw_value in ltp_resp.items():
            ltp = extract_ltp(raw_value)
            if ltp is not None:
                st.session_state.index_ltp[symbol.replace("NSE_", "")] = ltp

        bal_resp = groww.get_available_margin_details()
        groww_balance = bal_resp.get("clear_cash")

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# UI TABLES (LOCKED)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")

index_df = pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
)

col_a, col_b = st.columns([2, 1])

with col_a:
    st.dataframe(index_df, width=True)

with col_b:
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

st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.info("Live option fetching will populate here (Token 2 / 3 / 4 cycles)")

st.subheader("📜 Table 3: Trade History")
st.info("Paper trades will appear here once execution logic is enabled")

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
