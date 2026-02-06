from __future__ import annotations

import time

import streamlit as st

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine
from paper_trader.utils import token_preview

st.set_page_config(page_title="Groww NSE Paper Trader", page_icon="📈", layout="wide")

st.title("📈 Groww NSE Paper Trading Dashboard")
st.caption("Paper trading only • Polling mode • Mobile-friendly Streamlit UI")


def _parse_uploaded_tokens(uploaded_file) -> list[str]:
    if uploaded_file is None:
        return []
    content = uploaded_file.read().decode("utf-8")
    tokens = [line.strip() for line in content.splitlines() if line.strip()]
    unique: list[str] = []
    for t in tokens:
        if t not in unique:
            unique.append(t)
    return unique[:5]


if "engine" not in st.session_state:
    st.session_state.engine = None
if "token_rows" not in st.session_state:
    st.session_state.token_rows = []

with st.sidebar:
    st.header("Setup")
    st.write("Upload a .txt file with 1-5 access tokens (one token per line).")
    uploaded = st.file_uploader("Token file", type=["txt"]) 
    poll_seconds = st.number_input("Poll frequency (seconds)", min_value=5, max_value=60, value=5, step=1)
    quantity = st.number_input("Order quantity", min_value=1, max_value=500, value=1, step=1)

    if st.button("Initialize Tokens", use_container_width=True):
        tokens = _parse_uploaded_tokens(uploaded)
        if not tokens:
            st.error("Upload a valid token file first.")
        else:
            broker = GrowwPaperBroker()
            pool = TokenPool(tokens=tokens, min_gap_seconds=5)
            engine = PaperTraderEngine(broker=broker, token_pool=pool, poll_seconds=int(poll_seconds), quantity=int(quantity))
            rows = engine.validate_tokens()
            st.session_state.engine = engine
            st.session_state.token_rows = rows
            st.success(f"Initialized with {len(tokens)} token(s)")

    start_col, stop_col = st.columns(2)
    with start_col:
        if st.button("▶️ Start", use_container_width=True):
            if st.session_state.engine is None:
                st.error("Initialize tokens before starting.")
            else:
                st.session_state.engine.start()
    with stop_col:
        if st.button("⏹ Stop", use_container_width=True):
            if st.session_state.engine is not None:
                st.session_state.engine.stop()

st.subheader("Token Validation")
if st.session_state.token_rows:
    st.dataframe(
        {
            "token": [r[0] for r in st.session_state.token_rows],
            "is_valid": [r[1] for r in st.session_state.token_rows],
            "message": [r[2] for r in st.session_state.token_rows],
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No tokens validated yet.")

engine: PaperTraderEngine | None = st.session_state.engine

col1, col2, col3 = st.columns(3)
if engine is not None:
    snap = engine.snapshot()
    col1.metric("Bot Status", "Running" if snap.running else "Stopped")
    col2.metric("Realized P&L", f"₹{snap.realized_pnl:.2f}")
    col3.metric("Current Token", snap.active_token_preview)
else:
    col1.metric("Bot Status", "Not initialized")
    col2.metric("Realized P&L", "₹0.00")
    col3.metric("Current Token", "-")

st.subheader("Open Paper Positions")
if engine is not None and engine.snapshot().open_positions:
    pos = engine.snapshot().open_positions
    st.dataframe(
        {
            "symbol": [p.symbol for p in pos],
            "qty": [p.quantity for p in pos],
            "entry": [p.entry_price for p in pos],
            "stop_loss": [p.stop_loss for p in pos],
            "target": [p.target for p in pos],
            "direction": [p.direction for p in pos],
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No open positions.")

st.subheader("Live Logs (last 50 lines)")
if engine is not None:
    st.code("\n".join(engine.snapshot().logs) or "No logs yet.", language="text")
else:
    st.code("Initialize and start the engine to view logs.", language="text")

st.caption(
    "Token rotation uses round-robin with cooldown. Failed tokens are marked inactive and skipped automatically. "
    "No real orders are sent by this app."
)

# Lightweight auto-refresh for mobile dashboard feel.
time.sleep(0.2)
