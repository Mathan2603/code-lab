# app.py
import streamlit as st
import time
import pandas as pd
from growwapi import GrowwAPI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Groww Paper Trading Dashboard",
    layout="wide"
)

st.title("📊 Groww Paper Trading Dashboard")
st.caption("Index + Weekly + Monthly F&O • Auto-refresh")

# =========================
# SESSION STATE
# =========================
if "api" not in st.session_state:
    st.session_state.api = None

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0

if "error_logs" not in st.session_state:
    st.session_state.error_logs = []

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("🔑 Groww Token")
    token = st.text_area("Paste Groww Access Token", height=120)

    weekly_symbol = st.text_input(
        "Weekly Option Symbol",
        value="NIFTY2621026400CE"
    )

    monthly_symbols = st.text_area(
        "Monthly Option Symbols (comma separated)",
        value="NSE_NIFTY25JAN24500CE,NSE_NIFTY25JAN24500PE"
    )

    refresh_sec = st.number_input(
        "Refresh interval (seconds)",
        min_value=2,
        value=5
    )

    init = st.button("🚀 Initialize API")

# =========================
# INIT API
# =========================
if init and token.strip():
    try:
        st.session_state.api = GrowwAPI(token.strip())
        st.success("Groww API initialized successfully")
    except Exception as e:
        st.error(str(e))

api = st.session_state.api

# =========================
# AUTO REFRESH (SAFE)
# =========================
now = time.time()
if now - st.session_state.last_refresh >= refresh_sec:
    st.session_state.last_refresh = now
    st.rerun()

# =========================
# INDEX LTP
# =========================
st.subheader("📈 Index LTP")

if api:
    try:
        index_ltp = api.get_ltp(
            segment=api.SEGMENT_CASH,
            exchange_trading_symbols=(
                "NSE_NIFTY",
                "NSE_BANKNIFTY"
            )
        )

        df_index = pd.DataFrame([
            {"Symbol": k, "LTP": v}
            for k, v in index_ltp.items()
        ])
        st.dataframe(df_index, use_container_width=True)

    except Exception as e:
        st.error(str(e))
        st.session_state.error_logs.append(str(e))
else:
    st.info("Initialize API")

# =========================
# WEEKLY OPTION (QUOTE API)
# =========================
st.subheader("📄 Weekly Option LTP")

if api:
    try:
        quote = api.get_quote(
            exchange=api.EXCHANGE_NSE,
            segment=api.SEGMENT_FNO,
            trading_symbol=weekly_symbol.strip()
        )

        st.metric(
            label=weekly_symbol,
            value=quote.get("last_price")
        )

    except Exception as e:
        st.error(str(e))
        st.session_state.error_logs.append(str(e))

# =========================
# MONTHLY OPTIONS (MULTI LTP)
# =========================
st.subheader("📊 Monthly Options (Multi-LTP)")

if api:
    try:
        symbols = [
            s.strip()
            for s in monthly_symbols.split(",")
            if s.strip()
        ]

        if symbols:
            monthly_ltp = api.get_ltp(
                segment=api.SEGMENT_FNO,
                exchange_trading_symbols=tuple(symbols)
            )

            df_monthly = pd.DataFrame([
                {"Symbol": k, "LTP": v}
                for k, v in monthly_ltp.items()
            ])
            st.dataframe(df_monthly, use_container_width=True)
        else:
            st.info("Enter monthly symbols")

    except Exception as e:
        st.error(str(e))
        st.session_state.error_logs.append(str(e))

# =========================
# LOGS
# =========================
st.subheader("🧾 Error Logs")

if st.session_state.error_logs:
    st.dataframe(
        pd.DataFrame(
            st.session_state.error_logs[-20:],
            columns=["Error"]
        ),
        use_container_width=True
    )
else:
    st.write("No errors")
