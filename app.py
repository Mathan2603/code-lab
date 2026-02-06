from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine
from paper_trader.utils import token_preview

# -------------------------------------------------
# Streamlit config
# -------------------------------------------------
st.set_page_config(
    page_title="Groww NSE Paper Trader",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Groww NSE Paper Trading Dashboard")
st.caption("Paper trading only • Polling mode • Mobile-friendly Streamlit UI")

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def parse_tokens_from_text(text: str) -> list[str]:
    tokens = [t.strip() for t in text.splitlines() if t.strip()]
    unique = []
    for t in tokens:
        if t not in unique:
            unique.append(t)
    return unique[:5]


def sample_positions():
    """UI-only demo data"""
    return [
        {
            "symbol": "NSE-NIFTY-25FEB-24000-CE",
            "qty": 1,
            "entry": 125.40,
            "stop_loss": 95.20,
            "target": 185.00,
            "direction": "up",
        },
        {
            "symbol": "NSE-BANKNIFTY-25FEB-51000-PE",
            "qty": 1,
            "entry": 210.10,
            "stop_loss": 245.00,
            "target": 150.00,
            "direction": "down",
        },
    ]


# -------------------------------------------------
# Session state
# -------------------------------------------------
if "engine" not in st.session_state:
    st.session_state.engine = None

if "token_rows" not in st.session_state:
    st.session_state.token_rows = []

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
with st.sidebar:
    st.header("Setup")

    token_text = st.text_area(
        "Paste Groww access token(s) (1–5 tokens, one per line)",
        height=140,
    )

    poll_seconds = st.number_input(
        "Poll interval (seconds)",
        min_value=5,
        max_value=60,
        value=5,
        step=1,
    )

    quantity = st.number_input(
        "Lot quantity",
        min_value=1,
        max_value=500,
        value=1,
        step=1,
    )

    if st.button("Initialize tokens", use_container_width=True):
        tokens = parse_tokens_from_text(token_text)
        if not tokens:
            st.error("Please paste at least one valid token.")
        else:
            broker = GrowwPaperBroker()
            pool = TokenPool(tokens=tokens, min_gap_seconds=5)
            engine = PaperTraderEngine(
                broker=broker,
                token_pool=pool,
                poll_seconds=int(poll_seconds),
                quantity=int(quantity),
            )
            rows = engine.validate_tokens()
            st.session_state.engine = engine
            st.session_state.token_rows = rows
            st.success(f"Initialized {len(tokens)} token(s).")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ Start", use_container_width=True):
            if st.session_state.engine:
                st.session_state.engine.start()
    with col2:
        if st.button("⏹ Stop", use_container_width=True):
            if st.session_state.engine:
                st.session_state.engine.stop()

# -------------------------------------------------
# Token validation table
# -------------------------------------------------
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

# -------------------------------------------------
# Metrics
# -------------------------------------------------
engine: PaperTraderEngine | None = st.session_state.engine

m1, m2, m3, m4 = st.columns(4)

if engine:
    snap = engine.snapshot()
    m1.metric("Bot", "Running" if snap.running else "Stopped")
    m2.metric("Active token", snap.active_token_preview)
    m3.metric("Realized P&L", f"₹{snap.realized_pnl:.2f}")
    m4.metric("Unrealized P&L", f"₹{snap.unrealized_pnl:.2f}")
else:
    m1.metric("Bot", "Not initialized")
    m2.metric("Active token", "-")
    m3.metric("Realized P&L", "₹0.00")
    m4.metric("Unrealized P&L", "₹0.00")

# -------------------------------------------------
# Positions table (REAL or SAMPLE)
# -------------------------------------------------
st.subheader("Open paper positions")

if engine and engine.snapshot().open_positions:
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
        width="stretch",
        hide_index=True,
    )
else:
    st.caption("Showing sample data (no real positions yet)")
    demo = sample_positions()
    st.dataframe(
        {
            "symbol": [d["symbol"] for d in demo],
            "qty": [d["qty"] for d in demo],
            "entry": [d["entry"] for d in demo],
            "stop_loss": [d["stop_loss"] for d in demo],
            "target": [d["target"] for d in demo],
            "direction": [d["direction"] for d in demo],
        },
        width="stretch",
        hide_index=True,
    )

# -------------------------------------------------
# Logs
# -------------------------------------------------
st.subheader("Live logs (last 50 lines)")

if engine:
    st.code("\n".join(engine.snapshot().logs) or "No logs yet.", language="text")
else:
    st.code("Initialize engine to see logs.", language="text")

st.caption("No real orders are placed. This app is strictly for paper trading.")

time.sleep(0.2)
