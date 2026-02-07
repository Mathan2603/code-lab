import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI
import math

# =========================================================
# CONFIG (UI LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL = 50000.0

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

# Stores (NO DUPLICATES)
if "index_ltp" not in st.session_state:
    st.session_state.index_ltp = {}

if "options_ltp" not in st.session_state:
    st.session_state.options_ltp = {}

if "trade_history" not in st.session_state:
    st.session_state.trade_history = []

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
# AUTO REFRESH
# =========================================================
now = time.time()
last = st.session_state.get("last_refresh", 0)
if now - last >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    if st.session_state.bot_running:
        st.session_state.cycle_counter += 1
        st.rerun()

# =========================================================
# INIT GROWW APIS (ALL TOKENS)
# =========================================================
groww_clients = []
if st.session_state.bot_running:
    for t in valid_tokens:
        try:
            groww_clients.append(GrowwAPI(t))
        except Exception as e:
            st.session_state.errors.append(str(e))

# =========================================================
# TOKEN 1 — INDEX + BALANCE (LOCKED)
# =========================================================
groww_balance = None

if groww_clients:
    try:
        ltp_resp = groww_clients[0].get_ltp(
            segment=groww_clients[0].SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )

        for sym, data in ltp_resp.items():
            ltp = data["ltp"] if isinstance(data, dict) else data
            st.session_state.index_ltp[sym.replace("NSE_", "")] = float(ltp)

        bal = groww_clients[0].get_available_margin_details()
        groww_balance = bal.get("clear_cash")

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# TOKEN 2 — MONTHLY OPTIONS (FNO BULK)
# =========================================================
if len(groww_clients) > 1 and st.session_state.index_ltp:
    try:
        cycle = st.session_state.cycle_counter % 2
        underlying = "NIFTY" if cycle == 0 else "BANKNIFTY"
        ltp = st.session_state.index_ltp.get(underlying)

        if ltp:
            atm = round(ltp / 50) * 50
            strikes = [atm + i * 50 for i in range(-10, 11)]

            # NOTE: plug your expiry+contract resolver here
            symbols = []  # resolved monthly symbols (<=50)

            if symbols:
                ltp_resp = groww_clients[1].get_ltp(
                    segment=groww_clients[1].SEGMENT_FNO,
                    exchange_trading_symbols=tuple(symbols)
                )

                for sym, data in ltp_resp.items():
                    ltp_val = data["ltp"] if isinstance(data, dict) else data
                    st.session_state.options_ltp[sym] = float(ltp_val)

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# TOKEN 3 & 4 — WEEKLY OPTIONS (QUOTE)
# =========================================================
if len(groww_clients) > 3:
    try:
        # plug resolved weekly symbols here safely
        weekly_symbol = None

        if weekly_symbol:
            quote = groww_clients[2].get_quote(
                exchange=groww_clients[2].EXCHANGE_NSE,
                segment=groww_clients[2].SEGMENT_FNO,
                trading_symbol=weekly_symbol
            )
            st.session_state.options_ltp[weekly_symbol] = quote.get("ltp")

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# UI TABLES (LOCKED)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")

index_df = pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
)

cA, cB = st.columns([2, 1])
with cA:
    st.dataframe(index_df, use_container_width=True)

with cB:
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
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.options_ltp.items()]
    ),
    use_container_width=True,
)

st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
