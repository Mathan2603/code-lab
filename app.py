import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI

# =========================================================
# CONFIG (LOCKED UI)
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
        return value.get("ltp") or value.get("last_price") or value.get("price")
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

if "cycle_counter" not in st.session_state:
    st.session_state.cycle_counter = 0

if "index_ltp" not in st.session_state:
    st.session_state.index_ltp = {}

if "options_ltp" not in st.session_state:
    st.session_state.options_ltp = {}

# =========================================================
# SIDEBAR (LOCKED)
# =========================================================
st.sidebar.header("🔑 Groww Tokens")

for i in range(5):
    st.session_state.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}", type="password", value=st.session_state.tokens[i]
    )

valid_tokens = [t for t in st.session_state.tokens if t.strip()]

c1, c2 = st.sidebar.columns(2)
if c1.button("▶ Start Bot"):
    st.session_state.bot_running = True
if c2.button("⏹ Stop Bot"):
    st.session_state.bot_running = False

st.sidebar.caption("Auto refresh every 5 seconds")

# =========================================================
# AUTO REFRESH (LOCKED)
# =========================================================
now = time.time()
last = st.session_state.get("last_refresh", 0)
if now - last >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    if st.session_state.bot_running:
        st.session_state.cycle_counter += 1
        st.rerun()

# =========================================================
# INIT GROWW (TOKEN-1 ONLY)
# =========================================================
groww = None
if st.session_state.bot_running and valid_tokens:
    groww = GrowwAPI(valid_tokens[0])

# =========================================================
# TOKEN-1 — INDEX LTP + BALANCE (LOCKED & WORKING)
# =========================================================
groww_balance = None

if groww:
    try:
        ltp_resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )

        for sym, raw in ltp_resp.items():
            ltp = extract_ltp(raw)
            if ltp is not None:
                st.session_state.index_ltp[sym.replace("NSE_", "")] = ltp

        bal = groww.get_available_margin_details()
        groww_balance = bal.get("clear_cash")

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# TOKEN-2 — MONTHLY FNO (FIXED, REAL)
# =========================================================
if groww and "NIFTY" in st.session_state.index_ltp:
    try:
        nifty_spot = st.session_state.index_ltp["NIFTY"]
        atm = round(nifty_spot / 50) * 50

        # ✅ CORRECT Groww API USAGE (NO segment param)
        expiries = groww.get_expiries(
            exchange=groww.EXCHANGE_NSE,
            trading_symbol="NIFTY"
        )
        monthly_expiry = expiries[0]

        contracts = groww.get_contracts(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_FNO,
            trading_symbol="NIFTY",
            expiry=monthly_expiry
        )

        symbols = []
        for c in contracts:
            if abs(c["strike_price"] - atm) <= 100:
                symbols.append(c["trading_symbol"])

        if symbols:
            resp = groww.get_ltp(
                segment=groww.SEGMENT_FNO,
                exchange_trading_symbols=tuple(symbols)
            )

            for sym, raw in resp.items():
                ltp = extract_ltp(raw)
                if ltp is not None:
                    st.session_state.options_ltp[sym] = ltp

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# UI TABLES (LOCKED)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
    ),
    use_container_width=True,
)

st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.options_ltp.items()]
    ),
    use_container_width=True,
)

st.subheader("📜 Table 3: Trade History")
st.info("Paper trades will appear here once execution logic is enabled")

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
