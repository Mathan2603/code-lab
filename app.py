import streamlit as st
from streamlit_autorefresh import st_autorefresh
from growwapi import GrowwAPI
import pandas as pd
from datetime import datetime
import pytz

# ======================================================
# CONFIG (LOCKED)
# ======================================================
st.set_page_config(
    page_title="Groww Live Paper Trading Bot",
    layout="wide"
)

IST = pytz.timezone("Asia/Kolkata")
REFRESH_MS = 5000
PAPER_START_BALANCE = 50000.0

st.title("🚀 Groww Live Paper Trading Bot")
st_autorefresh(interval=REFRESH_MS, key="auto_refresh")

# ======================================================
# SESSION STATE INITIALIZATION (HARD SAFE)
# ======================================================
ss = st.session_state

if "initialized" not in ss:
    ss.initialized = True
    ss.tokens = [""] * 5
    ss.bot_running = False
    ss.paper_balance = PAPER_START_BALANCE
    ss.trades = []                # ALWAYS list of dicts
    ss.index_ltp = {}
    ss.options_ltp = {}
    ss.errors = []

# ======================================================
# SIDEBAR (LOCKED UI)
# ======================================================
st.sidebar.header("🔑 Groww Tokens")
for i in range(5):
    ss.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}",
        type="password",
        value=ss.tokens[i]
    )

st.sidebar.divider()

if st.sidebar.button("▶ Start Bot"):
    ss.bot_running = True

if st.sidebar.button("⏹ Stop Bot"):
    ss.bot_running = False

if st.sidebar.button("🔁 Reset Paper Trades"):
    ss.trades = []
    ss.paper_balance = PAPER_START_BALANCE

st.sidebar.caption("Auto refresh every 5 seconds")

# ======================================================
# TIME DISPLAY (TOP RIGHT)
# ======================================================
_, time_col = st.columns([9, 1])
with time_col:
    st.markdown(
        f"<div style='font-size:12px;text-align:right;'>"
        f"{datetime.now(IST).strftime('%H:%M:%S IST')}</div>",
        unsafe_allow_html=True
    )

# ======================================================
# GROWW INIT (TOKEN 1 ONLY — LOCKED)
# ======================================================
groww = None
if ss.bot_running and ss.tokens[0]:
    try:
        groww = GrowwAPI(ss.tokens[0])
    except Exception as e:
        ss.errors.append(str(e))

# ======================================================
# TOKEN 1 — INDEX LTP (LOCKED & STABLE)
# ======================================================
if groww:
    try:
        ltp_resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=(
                "NSE_NIFTY",
                "NSE_BANKNIFTY",
                "NSE_FINNIFTY"
            )
        )
        ss.index_ltp = {
            k.replace("NSE_", ""): float(v["ltp"])
            for k, v in ltp_resp.items()
        }
    except Exception as e:
        ss.errors.append(str(e))

# ======================================================
# OPTIONS LTP (MONTHLY + WEEKLY — SAFE)
# ======================================================
monthly_symbols = (
    "NSE_NIFTY26FEB25500CE",
    "NSE_NIFTY26FEB25500PE",
)
weekly_symbol = "NIFTY2621025500CE"

if groww:
    try:
        m_resp = groww.get_ltp(
            segment=groww.SEGMENT_FNO,
            exchange_trading_symbols=monthly_symbols
        )
        for s, d in m_resp.items():
            ss.options_ltp[s] = float(d["ltp"])

        w_resp = groww.get_quote(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_FNO,
            weekly_symbol
        )
        ss.options_ltp[weekly_symbol] = float(w_resp["ltp"])

    except Exception as e:
        ss.errors.append(str(e))

# ======================================================
# SANITIZE TRADES (CRITICAL FIX)
# ======================================================
clean_trades = []
for t in ss.trades:
    if isinstance(t, dict) and "buy_price" in t:
        clean_trades.append(t)
ss.trades = clean_trades

# ======================================================
# TABLE 1 — INDEX SUMMARY
# ======================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")

c1, c2 = st.columns([2, 1])
with c1:
    st.dataframe(
        pd.DataFrame(
            [{"Symbol": k, "LTP": v} for k, v in ss.index_ltp.items()]
        ),
        use_container_width=True
    )

with c2:
    st.markdown(
        f"""
        <b>Paper Trade Capital</b><br>
        <span style="color:green;font-size:20px;">
        ₹ {ss.paper_balance:.2f}
        </span>
        """,
        unsafe_allow_html=True
    )

# ======================================================
# TABLE 2 — OPTION LTPs
# ======================================================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in ss.options_ltp.items()]
    ),
    use_container_width=True
)

# ======================================================
# TABLE 3 — TRADE HISTORY (SAFE)
# ======================================================
st.subheader("📜 Table 3: Trade History")

rows = []
for i, t in enumerate(ss.trades, start=1):
    rows.append({
        "S.No": i,
        "Symbol": t["symbol"],
        "Buy Price": t["buy_price"],
        "Lot Size": t["lot"],
        "Buy Value": t["buy_price"] * t["lot"],
        "Stop Loss": t["stop_loss"],
        "Live / Sold Price": t.get("exit_price", t["buy_price"]),
        "Order Status": t["status"]
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ======================================================
# ERROR LOGS
# ======================================================
st.subheader("🛑 Error Logs")
if ss.errors:
    for e in ss.errors[-5:]:
        st.error(e)
else:
    st.success("No errors")

st.caption(
    f"Last updated: {datetime.now(IST).strftime('%H:%M:%S IST')}"
)
