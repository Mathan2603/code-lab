import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from growwapi import GrowwAPI

# =========================================================
# CONFIG (LOCKED)
# =========================================================
st.set_page_config(page_title="Groww Live Paper Trading Bot", layout="wide")
st.title("🚀 Groww Live Paper Trading Bot")

REFRESH_INTERVAL = 5
PAPER_CAPITAL_INITIAL = 50000.0
LOT_SIZE = 50
COOLDOWN_SECONDS = 60

IGNORED_ERRORS = (
    "Not able to recognize exchange",
    "Indicator data not ready yet"
)

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
# INDICATORS
# =========================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "tokens": ["", "", "", "", ""],
    "bot_running": False,
    "errors": [],
    "logged_errors": set(),
    "index_ltp": {},
    "options_ltp": {},
    "paper_balance": PAPER_CAPITAL_INITIAL,
    "trades": [],
    "last_trade_time": {},
    "indicator_df": None,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# SAFE ERROR LOGGER
# =========================================================
def log_error(msg):
    if any(x in msg for x in IGNORED_ERRORS):
        return
    if msg not in st.session_state.logged_errors:
        st.session_state.logged_errors.add(msg)
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
# AUTO REFRESH
# =========================================================
now = time.time()
if now - st.session_state.get("last_refresh", 0) >= REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    if st.session_state.bot_running:
        st.rerun()

# =========================================================
# INIT GROWW
# =========================================================
groww = None
if st.session_state.bot_running and st.session_state.tokens[0]:
    groww = GrowwAPI(st.session_state.tokens[0])

# =========================================================
# FETCH INDICATORS (ONCE, GUARDED)
# =========================================================
if groww and st.session_state.indicator_df is None:
    try:
        end = datetime.now()
        start = end - timedelta(days=60)

        candles = groww.get_historical_candles(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_CASH,
            "NSE-NIFTY",
            start.strftime("%Y-%m-%d %H:%M:%S"),
            end.strftime("%Y-%m-%d %H:%M:%S"),
            "15minute"
        )

        if candles and len(candles) >= 30:
            df = pd.DataFrame(
                candles,
                columns=["time", "open", "high", "low", "close", "volume"]
            )
            df["ema9"] = ema(df["close"], 9)
            df["ema21"] = ema(df["close"], 21)
            df["rsi"] = rsi(df["close"])
            st.session_state.indicator_df = df
        else:
            log_error("Indicator data not ready yet")

    except Exception as e:
        log_error(str(e))

# =========================================================
# INDEX LTP + BALANCE (LOCKED)
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

        groww_balance = groww.get_available_margin_details().get("clear_cash")

    except Exception as e:
        log_error(str(e))

# =========================================================
# OPTION LTP FETCHERS (LOCKED)
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
        log_error(str(e))

weekly_symbol = "NIFTY2621025500CE"

if groww:
    try:
        quote = groww.get_quote(
            groww.EXCHANGE_NSE,
            groww.SEGMENT_FNO,
            weekly_symbol
        )
        ltp = extract_ltp(quote)
        if ltp:
            st.session_state.options_ltp[weekly_symbol] = ltp
    except Exception as e:
        log_error(str(e))

# =========================================================
# SAFE TRADE LOGIC
# =========================================================
df = st.session_state.indicator_df
if df is not None and not df.empty:
    latest = df.iloc[-1]
    trend_ok = latest["ema9"] > latest["ema21"]
    rsi_ok = 35 < latest["rsi"] < 65

    for symbol, ltp in st.session_state.options_ltp.items():
        if time.time() - st.session_state.last_trade_time.get(symbol, 0) < COOLDOWN_SECONDS:
            continue

        cost = ltp * LOT_SIZE
        if trend_ok and rsi_ok and st.session_state.paper_balance >= cost:
            st.session_state.paper_balance -= cost
            st.session_state.trades.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": symbol,
                "price": ltp,
                "qty": LOT_SIZE,
                "sl": round(ltp * 0.85, 2)
            })
            st.session_state.last_trade_time[symbol] = time.time()
            break

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
# ERROR LOGS
# =========================================================
st.subheader("🛑 Error Logs")
if st.session_state.errors:
    for err in st.session_state.errors[-5:]:
        st.error(err)
else:
    st.success("No critical errors")

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
