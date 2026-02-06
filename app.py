from __future__ import annotations

import streamlit as st

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine

st.set_page_config(page_title="Groww NSE Paper Trader", page_icon="📈", layout="wide")

st.title("📈 Groww NSE Paper Trading Dashboard")
st.caption("Paper trading only • polling mode • Streamlit mobile dashboard")


def _parse_uploaded_tokens(uploaded_file) -> list[str]:
    if uploaded_file is None:
        return []
    content = uploaded_file.read().decode("utf-8")
    tokens = [line.strip() for line in content.splitlines() if line.strip()]
    uniq: list[str] = []
    for token in tokens:
        if token not in uniq:
            uniq.append(token)
    return uniq[:5]


if "engine" not in st.session_state:
    st.session_state.engine = None
if "token_rows" not in st.session_state:
    st.session_state.token_rows = []

with st.sidebar:
    st.header("Setup")
    uploaded = st.file_uploader("Upload token .txt (1-5 lines)", type=["txt"])
    poll_seconds = st.number_input("Poll interval (seconds)", min_value=5, max_value=60, value=5, step=1)
    quantity = st.number_input("Lot quantity", min_value=1, max_value=500, value=1, step=1)

    if st.button("Initialize tokens", use_container_width=True):
        tokens = _parse_uploaded_tokens(uploaded)
        if not tokens:
            st.error("Please upload a token file first.")
        else:
            broker = GrowwPaperBroker()
            pool = TokenPool(tokens=tokens, min_gap_seconds=5)
            engine = PaperTraderEngine(broker=broker, token_pool=pool, poll_seconds=int(poll_seconds), quantity=int(quantity))
            st.session_state.token_rows = engine.validate_tokens()
            st.session_state.engine = engine
            st.success(f"Initialized {len(tokens)} token(s).")

    a, b = st.columns(2)
    with a:
        if st.button("▶️ Start", use_container_width=True):
            if st.session_state.engine is None:
                st.error("Initialize tokens first.")
            else:
                st.session_state.engine.start()
    with b:
        if st.button("⏹ Stop", use_container_width=True):
            if st.session_state.engine is not None:
                st.session_state.engine.stop()

st.subheader("Token validation status")
if st.session_state.token_rows:
    st.dataframe(
        {
            "token": [r[0] for r in st.session_state.token_rows],
            "usable": [r[1] for r in st.session_state.token_rows],
            "status": [r[2] for r in st.session_state.token_rows],
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No validation performed yet.")

engine: PaperTraderEngine | None = st.session_state.engine

m1, m2, m3, m4 = st.columns(4)
if engine is None:
    m1.metric("Bot", "Not initialized")
    m2.metric("Active token", "-")
    m3.metric("Realized P&L", "₹0.00")
    m4.metric("Unrealized P&L", "₹0.00")
else:
    snap = engine.snapshot()
    m1.metric("Bot", "Running" if snap.running else "Stopped")
    m2.metric("Active token", snap.active_token_preview)
    m3.metric("Realized P&L", f"₹{snap.realized_pnl:.2f}")
    m4.metric("Unrealized P&L", f"₹{snap.unrealized_pnl:.2f}")

st.subheader("Open paper positions")
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
            "opened_at": [p.opened_at.strftime("%H:%M:%S") for p in pos],
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No open positions")

st.subheader("Live logs (last 50 lines)")
if engine is None:
    st.code("Initialize engine to see logs", language="text")
else:
    st.code("\n".join(engine.snapshot().logs) or "No logs yet", language="text")

st.caption("No real orders are placed by this app. Paper trading only.")
