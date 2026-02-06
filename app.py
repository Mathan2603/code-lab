from __future__ import annotations

import time
import streamlit as st

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine
from paper_trader.utils import token_preview

# -----------------------------
# Streamlit Page Config
# -----------------------------
st.set_page_config(
    page_title="Groww NSE Paper Trader",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Groww NSE Paper Trading Dashboard")
st.caption("Paper trading only • Polling mode • Mobile-friendly Streamlit UI")

# -----------------------------
# Helpers
# -----------------------------
def parse_tokens_from_text(text: str) -> list[str]:
    """
    Parse tokens from textarea.
    - One token per line
    - Remove duplicates
    - Max 5 tokens
    """
    if not text:
        return []

    raw = [line.strip() for line in text.splitlines() if line.strip()]
    unique: list[str] = []
    for t in raw:
        if t not in unique:
            unique.append(t)
    return unique[:5]


# -----------------------------
# Session State
# -----------------------------
if "engine" not in st.session_state:
    st.session_state.engine = None

if "token_rows" not in st.session_state:
    st.session_state.token_rows = []


# -----------------------------
# Sidebar – Setup
# -----------------------------
with st.sidebar:
    st.header("Setup")

    token_text = st.text_area(
        "Paste Groww access token(s)\n(1–5 tokens, one per line)",
        height=160,
        placeholder="eyJr...\neyJx...\n...",
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

    # -------- Initialize --------
    if st.button("Initialize tokens", use_container_width=True):
        tokens = parse_tokens_from_text(token_text)

        if not tokens:
            st.error("Paste at least one valid access token.")
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

            st.success(f"Initialized {len(tokens)} token(s)")

    # -------- Controls --------
    col_start, col_stop = st.columns(2)

    with col_start:
        if st.button("▶️ Start", use_container_width=True):
            if st.session_state.engine is None:
                st.error("Initialize tokens first.")
            else:
                st.session_state.engine.start()

    with col_stop:
        if st.button("⏹ Stop", use_container_width=True):
            if st.session_state.engine is not None:
                st.session_state.engine.stop()


# -----------------------------
# Token Validation Table
# -----------------------------
st.subheader("Token validation status")

if st.session_state.token_rows:
    st.dataframe(
        {
            "token": [row[0] for row in st.session_state.token_rows],
            "usable": [row[1] for row in st.session_state.token_rows],
            "status": [row[2] for row in st.session_state.token_rows],
        },
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No validation performed yet.")


# -----------------------------
# Engine Snapshot
# -----------------------------
engine: PaperTraderEngine | None = st.session_state.engine

col1, col2, col3, col4 = st.columns(4)

if engine is not None:
    snap = engine.snapshot()

    col1.metric("Bot", "Running" if snap.running else "Stopped")
    col2.metric("Active token", snap.active_token_preview or "-")
    col3.metric("Realized P&L", f"₹{snap.realized_pnl:.2f}")
    col4.metric("Unrealized P&L", f"₹{snap.unrealized_pnl:.2f}")
else:
    col1.metric("Bot", "Not initialized")
    col2.metric("Active token", "-")
    col3.metric("Realized P&L", "₹0.00")
    col4.metric("Unrealized P&L", "₹0.00")


# -----------------------------
# Open Positions
# -----------------------------
st.subheader("Open paper positions")

if engine is not None and engine.snapshot().open_positions:
    positions = engine.snapshot().open_positions
    st.dataframe(
        {
            "Symbol": [p.symbol for p in positions],
            "Qty": [p.quantity for p in positions],
            "Entry": [p.entry_price for p in positions],
            "Stop Loss": [p.stop_loss for p in positions],
            "Target": [p.target for p in positions],
            "Direction": [p.direction for p in positions],
        },
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No open positions.")


# -----------------------------
# Logs
# -----------------------------
st.subheader("Live logs (last 50 lines)")

if engine is not None:
    logs = engine.snapshot().logs
    st.code("\n".join(logs) if logs else "No logs yet.", language="text")
else:
    st.code("Initialize engine to see logs.", language="text")


st.caption(
    "No real orders are placed. This app is strictly for paper trading. "
    "Tokens are rotated automatically with cooldown handling."
)

# Light refresh for dashboard feel
time.sleep(0.2)
