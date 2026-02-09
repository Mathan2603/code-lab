import streamlit as st
import pandas as pd
import time
from datetime import datetime
from growwapi import GrowwAPI
import math

# =========================================================
# CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL_INITIAL = 50000.0
LOT_SIZE = 50

# =========================================================
# SAFE LTP EXTRACTOR
# =========================================================
def extract_ltp(v):
    if isinstance(v, dict):
        return v.get("ltp") or v.get("last_price") or v.get("price")
    if isinstance(v, (int, float)):
        return float(v)
    return None

# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "tokens": ["", "", "", "", ""],
    "bot_running": False,
    "errors": [],
    "index_ltp": {},
    "options_ltp": {},
    "nearest_option_ltp": {},
    "nearest_table": [],
    "paper_balance": PAPER_CAPITAL_INITIAL,
    "positions": [],
    "closed_trades": [],
    "expiry_map": {},
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# ERROR LOGGER (LOCKED)
# =========================================================
def log_error(msg):
    if "Not able to recognize exchange" in msg:
        return
    st.session_state.errors.append(msg)

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
# INIT TOKENS
# =========================================================
gw_index = GrowwAPI(st.session_state.tokens[0]) if st.session_state.tokens[0] else None
gw_monthly = GrowwAPI(st.session_state.tokens[1]) if st.session_state.tokens[1] else None
gw_weekly = GrowwAPI(st.session_state.tokens[2]) if st.session_state.tokens[2] else None

# =========================================================
# INDEX LTP (TOKEN 1)
# =========================================================
if gw_index:
    try:
        resp = gw_index.get_ltp(
            segment=gw_index.SEGMENT_CASH,
            exchange_trading_symbols=("NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY")
        )
        for sym, raw in resp.items():
            ltp = extract_ltp(raw)
            if ltp:
                st.session_state.index_ltp[sym.replace("NSE_", "")] = ltp
    except Exception as e:
        log_error(str(e))

# =========================================================
# AUTO EXPIRY DETECTION (TOKEN 1)
# =========================================================
if gw_index:
    try:
        for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            exps = gw_index.get_expiries(gw_index.EXCHANGE_NSE, idx)
            if exps:
                st.session_state.expiry_map[idx] = exps[0]  # nearest
    except Exception as e:
        log_error(str(e))

# =========================================================
# NEAREST STRIKE FETCHER (TOKEN 2)
# =========================================================
STRIKE_RULES = {"NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50}

if gw_monthly and st.session_state.index_ltp and st.session_state.expiry_map:
    try:
        symbols = []
        table_rows = []

        for idx, step in STRIKE_RULES.items():
            ltp = st.session_state.index_ltp.get(idx)
            expiry = st.session_state.expiry_map.get(idx)
            if not ltp or not expiry:
                continue

            atm = int(round(ltp / step) * step)

            for i in range(-10, 11):
                strike = atm + (i * step)
                for opt in ["CE", "PE"]:
                    sym = f"NSE_{idx}{expiry.replace('-','')}{strike}{opt}"
                    symbols.append(sym)
                    table_rows.append({
                        "Index": idx,
                        "Symbol": sym,
                        "Strike": strike,
                        "Type": opt,
                        "LTP": None
                    })

        for i in range(0, len(symbols), 50):
            batch = symbols[i:i+50]
            resp = gw_monthly.get_ltp(
                segment=gw_monthly.SEGMENT_FNO,
                exchange_trading_symbols=tuple(batch)
            )
            for sym, raw in resp.items():
                ltp = extract_ltp(raw)
                if ltp:
                    st.session_state.nearest_option_ltp[sym] = ltp

        for row in table_rows:
            row["LTP"] = st.session_state.nearest_option_ltp.get(row["Symbol"])

        st.session_state.nearest_table = table_rows

    except Exception as e:
        log_error(str(e))

# =========================================================
# STRATEGY USING NEAREST STRIKES
# =========================================================
for row in st.session_state.nearest_table:
    if row["LTP"] is None:
        continue

    already = any(p["symbol"] == row["Symbol"] for p in st.session_state.positions)
    if already:
        continue

    if st.session_state.paper_balance < row["LTP"] * LOT_SIZE:
        continue

    # SIMPLE FILTER: trade only ATM ±1
    idx_ltp = st.session_state.index_ltp.get(row["Index"])
    if not idx_ltp:
        continue

    if abs(row["Strike"] - idx_ltp) > STRIKE_RULES[row["Index"]]:
        continue

    st.session_state.paper_balance -= row["LTP"] * LOT_SIZE
    st.session_state.positions.append({
        "symbol": row["Symbol"],
        "entry_price": row["LTP"],
        "qty": LOT_SIZE,
        "time": datetime.now().strftime("%H:%M:%S")
    })
    break

# =========================================================
# UI TABLES (LOCKED + ONE NEW TABLE)
# =========================================================
st.subheader("📊 Table 1: Index LTPs & Account Summary")
st.dataframe(pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in st.session_state.index_ltp.items()]
), use_container_width=True)

st.subheader("📈 Table 2: Monthly & Weekly Option LTPs")
st.dataframe(pd.DataFrame(
    [{"Symbol": k, "LTP": v} for k, v in st.session_state.options_ltp.items()]
), use_container_width=True)

st.subheader("📌 Table 2A: Nearest Strikes (Auto)")
st.dataframe(pd.DataFrame(st.session_state.nearest_table), use_container_width=True)

st.subheader("📜 Table 3: Trade History")
st.dataframe(pd.DataFrame(st.session_state.closed_trades), use_container_width=True)

st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for e in st.session_state.errors[-5:]:
        st.error(e)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
