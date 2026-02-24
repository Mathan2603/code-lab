"""
config.py - Constants only. No logic allowed.
Paper Trading Bot v1.0
"""

# Groww API Token (set at runtime)
API_TOKEN = ""

# Indices to monitor
INDEX_LIST = ["NSE_NIFTY", "NSE_BANKNIFTY", "NSE_FINNIFTY"]

# Underlying mapping (strip NSE_ prefix)
UNDERLYING_MAP = {
    "NSE_NIFTY": "NIFTY",
    "NSE_BANKNIFTY": "BANKNIFTY",
    "NSE_FINNIFTY": "FINNIFTY",
}

# Groww symbol format for get_historical_candles (dash format)
GROWW_SYMBOL_MAP = {
    "NSE_NIFTY": "NSE-NIFTY",
    "NSE_BANKNIFTY": "NSE-BANKNIFTY",
    "NSE_FINNIFTY": "NSE-FINNIFTY",
}

# Lot sizes per index
LOT_SIZE = {
    "NSE_NIFTY": 75,
    "NSE_BANKNIFTY": 30,
    "NSE_FINNIFTY": 40,
}

# ATM strike range (+/- from ATM)
ATM_STRIKE_RANGE = 2

# Timeframes
BIAS_INTERVAL = "1hour"       # 1H for trend bias
ENTRY_INTERVAL = "15minute"   # 15M for option entry

# EMA periods for trend
EMA_FAST = 21
EMA_SLOW = 50

# Entry conditions
BREAKOUT_LOOKBACK = 5         # Highest high of last N candles
VOLUME_AVG_PERIOD = 10        # Volume average period
RSI_PERIOD = 14               # RSI calculation period
ATR_PERIOD = 14               # ATR calculation period
RSI_CE_THRESHOLD = 55         # RSI > this for CE
RSI_PE_THRESHOLD = 45         # RSI < this for PE

# Risk management
RISK_PER_TRADE_PCT = 0.02     # 2% capital per trade
ATR_STOP_MULTIPLIER = 1.5     # Stop = max(1.5 * ATR, structure stop)
BREAKEVEN_R = 1.0             # Move stop to breakeven at 1R
TRAIL_R = 1.5                 # Start trailing after 1.5R
TARGET_R = 3.0                # Hard target at 3R
MAX_TRADES_PER_DAY = 5
MAX_CONSECUTIVE_LOSSES = 3    # Per index
MAX_DAILY_DRAWDOWN_PCT = 0.06 # 6% daily drawdown limit
MAX_OPEN_PER_INDEX = 1        # One open trade per index

# Initial capital
INITIAL_CAPITAL = 1000000

# Loop interval
LOOP_SLEEP_SECONDS = 5

# Historical candle lookback (hours for 1H, minutes for 15M)
BIAS_CANDLE_COUNT = 60        # Need at least 50 candles for EMA50
ENTRY_CANDLE_COUNT = 30       # Need enough for ATR/RSI/volume

# Market hours (IST -> UTC offset +5:30)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# Logging
LOG_FILE = "paper_trades_log.csv"
