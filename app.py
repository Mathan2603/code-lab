from __future__ import annotations
import time
import uuid
import streamlit as st
from datetime import datetime
from growwapi import GrowwAPI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww Paper Trader",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Groww Paper Trading Dashboard")
st.caption("Index + Weekly + Monthly F&O • Paper Trading • Multi-Token")

# =========================
# SESSION STATE INIT
# =========================
def init_state():
    defaults = {
        "tokens": {},
        "last_refresh": 0.0,
        "trade_log": [],
        "error_log": [],
        "positions": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# =========================
# SIDEBAR – TOKENS
# =========================
with st.sidebar:
    st.header("🔑 Groww Tokens (Max 5)")

    temp_tokens = {}

    for i in range(5):
        token = st.text_area(
            f"Token {i+1}",
            key=f"token_input_{i}",
            height=80,
        )
        if token.strip():
            temp_tokens[i] = token.strip()

    st.session_state.tokens = temp_tokens

    refresh_interval = st.number_input(
        "Refresh Interval (seconds)",
        min_value=5,
        max_value=30,
        value=5,
        step=1,
    )

# =========================
# AUTO REFRESH (SAFE)
# =========================
now = time.time()
if now - st.session_state.last_refresh >= refresh_interval:
    st.session_state.last_refresh = now
    st.rerun()

# =========================
# NO TOKEN GUARD (IMPORTANT)
# =========================
if not st.session_state.tokens:
    st.info("👈 Paste at least one Groww token to start")
    st.stop()

# =========================
# TOKEN TABS
# =========================
tab_labels = [f"Token {i+1}" for i in st.session_state.tokens.keys()]
tabs = st.tabs(tab_labels)

for tab_idx, token_key in enumerate(st.session_state.tokens):
    with tabs[tab_idx]:
        token = st.session_state.tokens[token_key]

        try:
            groww = GrowwAPI(token)
            st.success("Groww API initialized")
        except Exception as e:
            st.error("Invalid token")
            st.session_state.error_log.append(str(e))
            continue

        # =========================
        # INDEX LTP
        # =========================
        st.subheader("📊 Index LTP")
        try:
            index_ltp = groww.get_ltp(
                segment=groww.SEGMENT_CASH,
                exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY"),
            )
            st.table(
                [{"Symbol": k, "LTP": v} for k, v in index_ltp.items()]
            )
        except Exception as e:
            st.error(e)
            st.session_state.error_log.append(str(e))

        # =========================
        # WEEKLY OPTION LTP (CONFIRMED LOGIC)
        # =========================
        st.subheader("🧾 Weekly Option LTP")
        weekly_symbol = st.text_input(
            "Weekly Option Symbol",
            value="NIFTY2621026400CE",
            key=f"weekly_{tab_idx}",
        )

        try:
            quote = groww.get_quote(
                groww.EXCHANGE_NSE,
                groww.SEGMENT_FNO,
                weekly_symbol,
            )
            st.table(
                [{"Symbol": weekly_symbol, "LTP": quote.get("last_price")}]
            )
        except Exception as e:
            st.error(e)
            st.session_state.error_log.append(str(e))

        # =========================
        # MONTHLY OPTIONS MULTI-LTP
        # =========================
        st.subheader("📈 Monthly Options (Multi-LTP)")
        monthly_symbols = st.text_area(
            "Monthly Symbols (comma separated)",
            value="NSE_NIFTY25JAN24500CE,NSE_NIFTY25JAN24500PE",
            key=f"monthly_{tab_idx}",
        )

        try:
            symbols = tuple(s.strip() for s in monthly_symbols.split(",") if s.strip())
            if symbols:
                monthly_ltp = groww.get_ltp(
                    segment=groww.SEGMENT_FNO,
                    exchange_trading_symbols=symbols,
                )
                st.table(
                    [{"Symbol": k, "LTP": v} for k, v in monthly_ltp.items()]
                )
        except Exception as e:
            st.error(e)
            st.session_state.error_log.append(str(e))

        # =========================
        # PAPER TRADE
        # =========================
        st.subheader("🧠 Paper Trade")
        with st.form(f"trade_form_{tab_idx}"):
            symbol = st.text_input("Symbol")
            qty = st.number_input("Quantity", min_value=1, value=1)
            price = st.number_input("Price", min_value=0.0)
            side = st.selectbox("Side", ["BUY", "SELL"])
            submit = st.form_submit_button("Execute")

            if submit:
                trade = {
                    "id": str(uuid.uuid4())[:8],
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "symbol": symbol,
                    "qty": qty,
                    "price": price,
                    "side": side,
                }
                st.session_state.trade_log.append(trade)
                st.session_state.positions.append(trade)
                st.success("Paper trade executed")

# =========================
# LOGS
# =========================
st.divider()
st.subheader("🧾 Trade Logs")
st.table(st.session_state.trade_log)

st.subheader("🚨 Error Logs")
st.table([{"Error": e} for e in st.session_state.error_log[-50:]])

# =========================
# PNL
# =========================
st.subheader("📊 PnL Summary")
pnl = 0.0
for t in st.session_state.positions:
    pnl += t["price"] * t["qty"] * (1 if t["side"] == "SELL" else -1)

st.metric("Net PnL", round(pnl, 2))
