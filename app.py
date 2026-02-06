from __future__ import annotations

import time
import streamlit as st

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine

st.set_page_config(
    page_title="Groww NSE Paper Trading Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Groww NSE Paper Trading Dashboard")
st.caption("Paper trading only • Polling mode • Mobile-friendly Streamlit UI")

# ---------------- SESSION ----------------

if "engine" not in st.session_state:
    st.session_state.engine = None
if "token_rows" not in st.session_state:
    st.session_state.token_rows = []

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.header("Setup")

    token_text = st.text_area(
        "Paste Groww access token(s) (1–5 tokens, one per line)",
        height=160,
    )

    poll_seconds = st.number_input(
        "Poll interval (seconds)", min_value=5, max_value=60, value=5
    )

    quantity = st.number_input("Lot quantity", min_value=1, value=1)

    if st.button("Initialize tokens", use_container_width=True):
        tokens = [t.strip() for t in token_text.splitlines() if t.strip()]
        broker = GrowwPaperBroker()
        pool = TokenPool(tokens=tokens, min_gap_seconds=5)
        engine = PaperTraderEngine(
            broker=broker,
            token_pool=pool,
            poll_seconds=int(poll_seconds),
            quantity=int(quantity),
        )
        st.session_state.token_rows = engine.validate_tokens()
        st.session_state.engine = engine
        st.success(f"Initialized {len(tokens)} token(s)")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶ Start", use_container_width=True):
            if st.session_state.engine:
                st.session_state.engine.start()
    with c2:
        if st.button("⏹ Stop", use_container_width=True):
            if st.session_state.engine:
                st.session_state.engine.stop()

# ---------------- TOKEN STATUS ----------------

st.subheader("Token validation status")

if st.session_state.token_rows:
    st.dataframe(
        {
            "token": [r[0] for r in st.session_state.token_rows],
            "usable": [r[1] for r in st.session_state.token_rows],
            "status": [r[2] for r in st.session_state.token_rows],
        },
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No validation performed yet.")

engine: PaperTraderEngine | None = st.session_state.engine

# ---------------- METRICS ----------------

c1, c2, c3, c4 = st.columns(4)

if engine:
    snap = engine.snapshot()
    c1.metric("Bot", "Running" if snap.running else "Stopped")
    c2.metric("Active token", snap.active_token_preview)
    c3.metric("Realized P&L", f"₹{snap.realized_pnl:.2f}")
    c4.metric("Unrealized P&L", f"₹{snap.unrealized_pnl:.2f}")
else:
    c1.metric("Bot", "Not initialized")
    c2.metric("Active token", "-")
    c3.metric("Realized P&L", "₹0.00")
    c4.metric("Unrealized P&L", "₹0.00")

# ---------------- 🔥 LIVE LTP TABLE ----------------

st.subheader("Live Market Prices (LTP)")

if engine and engine.get_latest_ltps():
    st.dataframe(
        {
            "symbol": list(engine.get_latest_ltps().keys()),
            "ltp": list(engine.get_latest_ltps().values()),
            "time (IST)": [time.strftime("%H:%M:%S")] * len(engine.get_latest_ltps()),
        },
        width="stretch",
        hide_index=True,
    )
else:
    st.info("Waiting for market data...")

# ---------------- LOGS ----------------

st.subheader("Live logs (last 50 lines)")
if engine:
    st.code("\n".join(engine.snapshot().logs) or "No logs yet.")
else:
    st.code("Initialize and start the engine.")

time.sleep(0.2)
