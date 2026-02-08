import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pytz
from growwapi import GrowwAPI

# =====================================================
# CONFIG (LOCKED)
# =====================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL = 50000.0
IST = pytz.timezone("Asia/Kolkata")

# =====================================================
# SESSION STATE (SAFE INIT)
# =====================================================
ss = st.session_state
ss.setdefault("tokens", [""] * 5)
ss.setdefault("bot_running", False)
ss.setdefault("paper_balance", PAPER_CAPITAL)
ss.setdefault("trades", [])
ss.setdefault("index_ltp", {})
ss.setdefault("options_ltp", {})
ss.setdefault("errors", [])
ss.setdefault("last_refresh", 0.0)
ss.setdefault("price_memory", {})

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
# TOP RIGHT TIME (IST)
# =====================================================
_, time_col = st.columns([9, 1])
with time_col:
    st.markdown(
        f"<div style='font-size:12px;text-align:right;'>"
        f"{datetime.now(IST).strftime('%H:%M:%S IST')}</div>",
        unsafe_allow_html=True
    )

# =====================================================
# AUTO REFRESH
# =====================================================
now = time.time()
if ss.bot_running and (now - ss.last_refresh) >= REFRESH_INTERVAL:
    ss.last_refresh = now
    st.rerun()

# =====================================================
# INIT GROWW (TOKEN 1 ONLY)
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
        for k, v in resp.items():
            ss.index_ltp[k.replace("NSE_", "")] = v["ltp"]
    except Exception as e:
        ss.errors.append(str(e))

# =====================================================
# MONTHLY + WEEKLY FNO LTP (FIXED)
# =====================================================
monthly_symbols = [
    "NSE_NIFTY26FEB25500CE",
    "NSE_NIFTY26FEB25500PE"
]

weekly_symbol = "NIFTY2621025500CE"

if groww:
    try:
        # Monthly → get_ltp (batch)
        m = groww.get_ltp(
            segment=groww.SEGMENT_FNO,
            exchange_trading_symbols=tuple(monthly_symbols)
        )
        for k, v in m.items():
            ss.options_ltp[k] = v["ltp"]

        # ✅ Weekly → get_quote (FIXED EXCHANGE)
        q = groww.get_quote(
            groww.EXCHANGE_NSE,     # ✅ FIX
            groww.SEGMENT_FNO,
            weekly_symbol
        )
        ss.options_ltp[weekly_symbol] = q["ltp"]

    except Exception as e:
        ss.errors.append(str(e))

# =====================================================
# TABLE 1
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
        f"""
        **Paper Trade Capital:**  
        <span style="color:green;font-weight:bold;">₹ {ss.paper_balance:.2f}</span>
        """,
        unsafe_allow_html=True
    )

# =====================================================
# TABLE 2
# =====================================================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in ss.options_ltp.items()]
    ),
    use_container_width=True
)

# =====================================================
# TABLE 3 (EMPTY FOR NOW – SAFE)
# =====================================================
st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame([]), use_container_width=True)

# =====================================================
# ERROR LOGS
# =====================================================
st.subheader("🛑 Error Logs")
if ss.errors:
    for e in ss.errors[-5:]:
        st.error(e)
else:
    st.success("No errors")

st.caption(f"Last updated: {datetime.now(IST).strftime('%H:%M:%S IST')}")
