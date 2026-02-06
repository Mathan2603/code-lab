import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from paper_trader.broker import GrowwPaperBroker
from paper_trader.token_pool import TokenPool
from paper_trader.trader import PaperTraderEngine

# 🔁 AUTO REFRESH EVERY 5 SECONDS
st.autorefresh(interval=5000, key="refresh")

st.set_page_config(layout="wide")
st.title("📈 Groww NSE Paper Trading Dashboard")

tokens_text = st.sidebar.text_area(
    "Paste Groww access token(s) (1–5, one per line)"
)

poll = st.sidebar.number_input("Poll interval (seconds)", 5, 60, 5)
qty = st.sidebar.number_input("Lot quantity", 1, 100, 1)

if "engine" not in st.session_state:
    st.session_state.engine = None

if st.sidebar.button("Initialize tokens"):
    tokens = [t.strip() for t in tokens_text.splitlines() if t.strip()]
    broker = GrowwPaperBroker()
    pool = TokenPool(tokens)
    engine = PaperTraderEngine(broker, pool, poll, qty)
    engine.validate_tokens()
    st.session_state.engine = engine

if st.sidebar.button("Start") and st.session_state.engine:
    st.session_state.engine.start()

if st.sidebar.button("Stop") and st.session_state.engine:
    st.session_state.engine.stop()

engine = st.session_state.engine

if engine:
    snap = engine.snapshot()

    st.subheader("Bot status")
    st.write("Running" if snap.running else "Stopped")
    st.write("Active token:", snap.active_token_preview)

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

    st.subheader("Live logs")
    st.code("\n".join(snap.logs))
