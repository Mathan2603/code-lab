import time
import streamlit as st
from datetime import datetime

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine

# ---------------- CONFIG ----------------
st.set_page_config(layout="wide")
st.title("📈 Groww NSE Paper Trading Dashboard")

# ---------------- SESSION INIT ----------------
if "engine" not in st.session_state:
    st.session_state.engine = None

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# ---------------- SIDEBAR ----------------
tokens_text = st.sidebar.text_area(
    "Paste Groww access token(s) (1–5, one per line)"
)

poll_seconds = st.sidebar.number_input(
    "Poll interval (seconds)", min_value=5, max_value=60, value=5
)

lot_qty = st.sidebar.number_input(
    "Lot quantity", min_value=1, max_value=100, value=1
)

# ---------------- INIT TOKENS ----------------
if st.sidebar.button("Initialize tokens"):
    tokens = [t.strip() for t in tokens_text.splitlines() if t.strip()]
    broker = GrowwPaperBroker()
    pool = TokenPool(tokens)
    engine = PaperTraderEngine(
        broker=broker,
        token_pool=pool,
        poll_seconds=poll_seconds,
        quantity=lot_qty,
    )
    engine.validate_tokens()
    st.session_state.engine = engine
    st.success("Initialized tokens")

# ---------------- START / STOP ----------------
if st.sidebar.button("Start") and st.session_state.engine:
    st.session_state.engine.start()

if st.sidebar.button("Stop") and st.session_state.engine:
    st.session_state.engine.stop()

engine = st.session_state.engine

# ---------------- MAIN UI ----------------
if engine:
    snap = engine.snapshot()

    st.subheader("Bot status")
    st.write("🟢 Running" if snap.running else "🔴 Stopped")
    st.write("Active token:", snap.active_token_preview)

    # -------- LTP TABLE --------
    st.subheader("📊 Live Market Prices (LTP)")
    if snap.last_prices:
        st.dataframe(
            {
                "Symbol": list(snap.last_prices.keys()),
                "LTP": list(snap.last_prices.values()),
            },
            width="stretch",
        )
    else:
        st.info("Waiting for market data...")

    # -------- LOGS --------
    st.subheader("Live logs (last 50)")
    st.code("\n".join(snap.logs))

# ---------------- AUTO REFRESH (SAFE WAY) ----------------
now = time.time()
if now - st.session_state.last_refresh >= poll_seconds:
    st.session_state.last_refresh = now
    st.experimental_rerun()
