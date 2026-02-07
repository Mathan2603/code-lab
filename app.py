import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI
import matplotlib.pyplot as plt

# =========================================================
# CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL_INITIAL = 50000.0

# =========================================================
# SAFE LTP EXTRACTOR
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

if "index_ltp" not in st.session_state:
    st.session_state.index_ltp = {}

if "options_ltp" not in st.session_state:
    st.session_state.options_ltp = {}

if "paper_balance" not in st.session_state:
    st.session_state.paper_balance = PAPER_CAPITAL_INITIAL

if "trades" not in st.session_state:
    st.session_state.trades = []

# =========================================================
# SIDEBAR (LOCKED UI)
# =========================================================
st.sidebar.header("🔑 Groww Tokens")
for i in range(5):
    st.session_state.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}", type="password", value=st.session_state.tokens[i]
    )

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
        st.rerun()

# =========================================================
# INIT GROWW (TOKEN 1 ONLY)
# =========================================================
groww = None
if st.session_state.bot_running and st.session_state.tokens[0]:
    groww = GrowwAPI(st.session_state.tokens[0])

# =========================================================
# TOKEN 1 — INDEX LTP + BALANCE (LOCKED)
# =========================================================
groww_balance = None

if groww:
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )

        for sym, raw in resp.items():
            ltp = extract_ltp(raw)
            if ltp:
                st.session_state.index_ltp[sym.replace("NSE_", "")] = ltp

        bal = groww.get_available_margin_details()
        groww_balance = bal.get("clear_cash")

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# MONTHLY FNO LTP ENGINE (LIVE)
# =========================================================
monthly_symbols = [
    "NSE_NIFTY26FEB25500CE",
    "NSE_NIFTY26FEB25500PE"
]

if groww:
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_FNO,
            exchange_trading_symbols=tuple(monthly_symbols)
        )

        for sym, raw in resp.items():
            ltp = extract_ltp(raw)
            if ltp:
                st.session_state.options_ltp[sym] = ltp

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# WEEKLY FNO LTP ENGINE (LIVE)
# =========================================================
weekly_symbol = "NIFTY2621025500CE"

if groww:
    try:
        quote = groww.get_quote(
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_FNO,
            trading_symbol=weekly_symbol
        )

        ltp = extract_ltp(quote)
        if ltp:
            st.session_state.options_ltp[weekly_symbol] = ltp

    except Exception as e:
        st.session_state.errors.append(str(e))

# =========================================================
# PAPER TRADE EXECUTION (BASIC)
# =========================================================
if st.session_state.options_ltp:
    symbol, ltp = next(iter(st.session_state.options_ltp.items()))
    cost = ltp * 50  # example lot

    if st.session_state.paper_balance >= cost:
        st.session_state.paper_balance -= cost
        st.session_state.trades.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": symbol,
            "price": ltp,
            "qty": 50
        })

# =========================================================
# UI TABLES (LOCKED)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
colA, colB = st.columns([2, 1])

with colA:
    st.dataframe(
        pd.DataFrame(
            [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
        ),
        use_container_width=True
    )

with colB:
    st.markdown(
        f"""
        **Paper Trade Capital:**  
        <span style="color:green;font-weight:bold;">₹ {st.session_state.paper_balance}</span>

        **Groww Available Balance (LIVE):**  
        <span style="color:{'green' if (groww_balance or 0) >= 0 else 'red'};font-weight:bold;">
        ₹ {groww_balance if groww_balance is not None else '—'}
        </span>
        """,
        unsafe_allow_html=True
    )

st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in st.session_state.options_ltp.items()]
    ),
    use_container_width=True
)

st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.trades), use_container_width=True)

# =========================================================
# BACKTESTING CHART PAGE
# =========================================================
st.subheader("📊 Backtesting Chart (Example)")

if groww:
    candles = groww.get_historical_candles(
        exchange=groww.EXCHANGE_NSE,
        segment=groww.SEGMENT_CASH,
        groww_symbol="NSE-NIFTY",
        start_time="2024-01-01 09:15:00",
        end_time="2024-01-10 15:30:00",
        candle_interval="15minute"
    )

    df = pd.DataFrame(
        candles,
        columns=["time", "open", "high", "low", "close", "volume"]
    )

    fig, ax = plt.subplots()
    ax.plot(df["close"])
    ax.set_title("NIFTY Backtest Close Price")
    st.pyplot(fig)

# =========================================================
# ERROR LOGS
# =========================================================
st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
