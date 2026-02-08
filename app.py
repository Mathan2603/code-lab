import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from datetime import datetime
import pytz
from growwapi import GrowwAPI

# =====================================================
# CONFIG (LOCKED)
# =====================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

IST = pytz.timezone("Asia/Kolkata")
REFRESH_MS = 5000
PAPER_CAPITAL = 50000.0

st_autorefresh(interval=REFRESH_MS, key="auto_refresh")

# =====================================================
# SESSION STATE — HARD RESET (CRITICAL FIX)
# =====================================================
ss = st.session_state

ss.setdefault("tokens", [""] * 5)
ss.setdefault("bot_running", False)

# 🚨 FORCE CLEAN RESET (kills old broken trades)
if "trades" not in ss or st.sidebar.button("🔁 Reset Paper Trades"):
    ss.trades = []
    ss.paper_balance = PAPER_CAPITAL

ss.setdefault("index_ltp", {})
ss.setdefault("options_ltp", {})
ss.setdefault("errors", [])

# =====================================================
# SIDEBAR (LOCKED UI)
# =====================================================
st.sidebar.header("🔑 Groww Tokens")
for i in range(5):
    ss.tokens[i] = st.sidebar.text_input(
        f"Token {i+1}", type="password", value=ss.tokens[i]
    )

c1, c2 = st.sidebar.columns(2)
if c1.button("▶ Start Bot"):
    ss.bot_running = True
if c2.button("⏹ Stop Bot"):
    ss.bot_running = False

st.sidebar.caption("Auto refresh every 5 seconds")

# =====================================================
# TIME (IST)
# =====================================================
_, time_col = st.columns([9, 1])
with time_col:
    st.markdown(
        f"<div style='font-size:12px;text-align:right;'>"
        f"{datetime.now(IST).strftime('%H:%M:%S IST')}</div>",
        unsafe_allow_html=True
    )

# =====================================================
# GROWW INIT (TOKEN 1 ONLY)
# =====================================================
groww = None
if ss.bot_running and ss.tokens[0]:
    groww = GrowwAPI(ss.tokens[0])

# =====================================================
# TOKEN 1 — INDEX LTP (LOCKED)
# =====================================================
if groww:
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )
        for sym, data in resp.items():
            ss.index_ltp[sym.replace("NSE_", "")] = float(data["ltp"])
    except Exception as e:
        ss.errors.append(str(e))

# =====================================================
# OPTIONS LTP (MONTHLY + WEEKLY)
# =====================================================
monthly_symbols = [
    "NSE_NIFTY26FEB25500CE",
    "NSE_NIFTY26FEB25500PE",
]
weekly_symbol = "NIFTY2621025500CE"

if groww:
    try:
        monthly = groww.get_ltp(
            segment=groww.SEGMENT_FNO,
            exchange_trading_symbols=tuple(monthly_symbols)
        )
        for sym, data in monthly.items():
            ss.options_ltp[sym] = float(data["ltp"])

        weekly = groww.get_quote(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_FNO,
            weekly_symbol
        )
        ss.options_ltp[weekly_symbol] = float(weekly["ltp"])

    except Exception as e:
        ss.errors.append(str(e))

# =====================================================
# TABLE 1 — INDEX
# =====================================================
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
        f"<b>Paper Trade Capital:</b><br>"
        f"<span style='color:green;font-size:18px;'>₹ {ss.paper_balance:.2f}</span>",
        unsafe_allow_html=True
    )

# =====================================================
# TABLE 2 — OPTIONS LTP
# =====================================================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in ss.options_ltp.items()]
    ),
    use_container_width=True
)

# =====================================================
# TABLE 3 — TRADE HISTORY (SAFE RENDER)
# =====================================================
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
        "Status": t["status"]
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True)

# =====================================================
# ERRORS
# =====================================================
st.subheader("🛑 Error Logs")
if ss.errors:
    for e in ss.errors[-5:]:
        st.error(e)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now(IST).strftime('%H:%M:%S IST')}")
