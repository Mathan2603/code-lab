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
PAPER_CAPITAL_INITIAL = 50000.0
IST = pytz.timezone("Asia/Kolkata")

# =====================================================
# SAFE LTP EXTRACTOR (LOCKED)
# =====================================================
def extract_ltp(val):
    if isinstance(val, dict):
        return val.get("ltp") or val.get("last_price") or val.get("price")
    if isinstance(val, (int, float)):
        return float(val)
    return None

# =====================================================
# SESSION STATE
# =====================================================
ss = st.session_state

ss.setdefault("tokens", [""] * 5)
ss.setdefault("bot_running", False)
ss.setdefault("last_refresh", 0.0)
ss.setdefault("index_ltp", {})
ss.setdefault("options_ltp", {})
ss.setdefault("paper_balance", PAPER_CAPITAL_INITIAL)
ss.setdefault("trades", [])
ss.setdefault("errors", [])
ss.setdefault("price_memory", {})  # for indicators

# =====================================================
# SIDEBAR (LOCKED UI)
# =====================================================
st.sidebar.header("🔑 Groww Tokens")
for i in range(5):
    ss.tokens[i] = st.sidebar.text_input(f"Token {i+1}", type="password", value=ss.tokens[i])

c1, c2 = st.sidebar.columns(2)
if c1.button("▶ Start Bot"):
    ss.bot_running = True
if c2.button("⏹ Stop Bot"):
    ss.bot_running = False

st.sidebar.caption("Auto refresh every 5 seconds")

# =====================================================
# TOP-RIGHT TIME (IST)
# =====================================================
with st.container():
    colA, colB = st.columns([9, 1])
    with colB:
        st.markdown(
            f"<div style='font-size:12px; text-align:right;'>"
            f"{datetime.now(IST).strftime('%H:%M:%S IST')}</div>",
            unsafe_allow_html=True
        )

# =====================================================
# AUTO REFRESH (FIXED)
# =====================================================
now = time.time()
if ss.bot_running and (now - ss.last_refresh) >= REFRESH_INTERVAL:
    ss.last_refresh = now
    st.rerun()

# =====================================================
# INIT GROWW (TOKEN-1 ONLY)
# =====================================================
groww = None
if ss.bot_running and ss.tokens[0]:
    groww = GrowwAPI(ss.tokens[0])

# =====================================================
# TOKEN-1: INDEX LTP + BALANCE (LOCKED)
# =====================================================
groww_balance = None
if groww:
    try:
        resp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )
        for k, v in resp.items():
            ltp = extract_ltp(v)
            if ltp:
                ss.index_ltp[k.replace("NSE_", "")] = ltp

        bal = groww.get_available_margin_details()
        groww_balance = bal.get("clear_cash")

    except Exception as e:
        ss.errors.append(str(e))

# =====================================================
# MONTHLY & WEEKLY LTP (LOCKED)
# =====================================================
monthly_syms = [
    "NSE_NIFTY26FEB25500CE",
    "NSE_NIFTY26FEB25500PE",
]

weekly_sym = "NIFTY2621025500CE"

if groww:
    try:
        mresp = groww.get_ltp(
            segment=groww.SEGMENT_FNO,
            exchange_trading_symbols=tuple(monthly_syms)
        )
        for k, v in mresp.items():
            ltp = extract_ltp(v)
            if ltp:
                ss.options_ltp[k] = ltp

        q = groww.get_quote(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_FNO,
            weekly_sym
        )
        wltp = extract_ltp(q)
        if wltp:
            ss.options_ltp[weekly_sym] = wltp

    except Exception as e:
        ss.errors.append(str(e))

# =====================================================
# INDICATORS + PAPER TRADE LOGIC
# =====================================================
def should_enter_trade(symbol, ltp):
    prev = ss.price_memory.get(symbol)
    ss.price_memory[symbol] = ltp
    if not prev:
        return False
    move_pct = abs((ltp - prev) / prev) * 100
    return move_pct >= 0.3  # momentum filter

def update_trade(trade, ltp):
    if trade["status"] == "OPEN":
        if ltp <= trade["stop_loss"]:
            trade["status"] = "CLOSED"
            trade["sell_price"] = ltp

# =====================================================
# EXECUTION
# =====================================================
for sym, ltp in ss.options_ltp.items():
    open_trades = [t for t in ss.trades if t["symbol"] == sym and t["status"] == "OPEN"]
    if not open_trades and should_enter_trade(sym, ltp):
        lot = 50
        buy_value = lot * ltp
        if ss.paper_balance >= buy_value:
            sl = ltp * 0.70
            ss.paper_balance -= buy_value
            ss.trades.append({
                "symbol": sym,
                "buy_price": ltp,
                "lot": lot,
                "buy_value": buy_value,
                "stop_loss": sl,
                "status": "OPEN",
                "sell_price": None
            })

for t in ss.trades:
    if t["status"] == "OPEN" and t["symbol"] in ss.options_ltp:
        update_trade(t, ss.options_ltp[t["symbol"]])

# =====================================================
# TABLE-1
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

        **Groww Available Balance (LIVE):**  
        <span style="color:{'green' if (groww_balance or 0) >= 0 else 'red'};font-weight:bold;">
        ₹ {groww_balance if groww_balance is not None else '—'}
        </span>
        """,
        unsafe_allow_html=True
    )

# =====================================================
# TABLE-2
# =====================================================
st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(
    pd.DataFrame(
        [{"Symbol": k, "LTP": v} for k, v in ss.options_ltp.items()]
    ),
    use_container_width=True
)

# =====================================================
# TABLE-3 (FIXED)
# =====================================================
st.subheader("📜 Table 3: Trade History")

rows = []
for i, t in enumerate(ss.trades, 1):
    rows.append({
        "S.No": i,
        "Symbol": t["symbol"],
        "Buy Price": t["buy_price"],
        "Lot Size": t["lot"],
        "Buy Value": t["buy_value"],
        "Stop Loss": t["stop_loss"],
        "Live / Sold Price": ss.options_ltp.get(t["symbol"]) if t["status"] == "OPEN" else t["sell_price"],
        "Order Status": t["status"]
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
