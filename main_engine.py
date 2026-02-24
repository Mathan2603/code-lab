"""
main_engine.py - Orchestration only.
Responsibility: Initialize modules, run main loop, coordinate between modules.
No strategy logic. No risk calculation. No logging logic.
"""

import time
import datetime
import sys
from growwapi import GrowwAPI

import config
from trend_module import TrendModule
from entry_module import EntryModule
from risk_module import RiskModule
from position_module import PositionModule
from logger_module import LoggerModule


def get_api_token():
    """Get API token from config or prompt user."""
    if config.API_TOKEN:
        return config.API_TOKEN

    token = input("Enter your Groww API token: ").strip()
    if not token:
        print("ERROR: API token is required.")
        sys.exit(1)
    return token


def is_market_hours() -> bool:
    """Check if current time is within market hours (IST)."""
    now_ist = get_ist_now()

    current_time = now_ist.hour * 60 + now_ist.minute
    market_open = config.MARKET_OPEN_HOUR * 60 + config.MARKET_OPEN_MINUTE
    market_close = config.MARKET_CLOSE_HOUR * 60 + config.MARKET_CLOSE_MINUTE

    # Also check weekday (0=Monday, 6=Sunday)
    if now_ist.weekday() >= 5:  # Saturday or Sunday
        return False

    return market_open <= current_time <= market_close


def get_ist_now():
    """Get current time in IST."""
    try:
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        return datetime.datetime.now(ist)
    except ImportError:
        return datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)


def is_daily_reset_time() -> bool:
    """Check if it's time for daily reset (9:15 IST)."""
    now_ist = get_ist_now()
    return now_ist.hour == config.MARKET_OPEN_HOUR and now_ist.minute == config.MARKET_OPEN_MINUTE


def is_expiry_day_past_cutoff(expiry_date_str: str) -> bool:
    """
    Check if expiry is today AND current IST time is past the cutoff (12:30 PM IST).
    If expiry is today and past cutoff -> True (skip this expiry, it's dead).
    If expiry is today but before cutoff -> False (still tradeable).
    If expiry is NOT today -> False (not relevant).
    """
    now_ist = get_ist_now()
    today_str = now_ist.strftime("%Y-%m-%d")

    if expiry_date_str != today_str:
        return False  # Not expiry day, no cutoff applies

    # Expiry is today - check if past cutoff
    cutoff_minutes = config.EXPIRY_DAY_CUTOFF_HOUR * 60 + config.EXPIRY_DAY_CUTOFF_MINUTE
    current_minutes = now_ist.hour * 60 + now_ist.minute

    if current_minutes >= cutoff_minutes:
        return True  # Past 12:30 PM IST on expiry day = dead expiry

    return False  # Before 12:30 PM on expiry day = still tradeable


def main():
    print("=====================================")
    print("Paper Bot v1.0 - Hybrid MTF Engine")
    print("=====================================")

    # Get API token
    token = get_api_token()

    # Initialize Groww
    groww = GrowwAPI(token)

    # Initialize Modules
    trend_module = TrendModule(groww)
    entry_module = EntryModule(groww)
    risk_module = RiskModule()
    position_module = PositionModule()
    logger = LoggerModule()

    print("Initial Capital:", risk_module.capital)
    print("Monitoring indices:", config.INDEX_LIST)
    print("-------------------------------------\n")

    daily_reset_done = False

    while True:
        try:
            # Check market hours
            if not is_market_hours():
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Outside market hours. Waiting...")
                time.sleep(60)
                daily_reset_done = False
                continue

            # Daily reset logic (once at market open)
            if is_daily_reset_time() and not daily_reset_done:
                risk_module.reset_daily()
                daily_reset_done = True

            # Manage open trades every cycle
            position_module.manage_positions(groww, risk_module, logger)

            # Scan for entries
            for index_symbol in config.INDEX_LIST:

                # Check if we can trade this index
                if not risk_module.can_trade(index_symbol):
                    continue

                # Get 1H trend bias
                trend = trend_module.detect_trend(index_symbol)

                if trend is None:
                    print(f"{index_symbol} -> No clear trend")
                    continue

                print(f"{index_symbol} -> Trend: {trend}")

                # Fetch index LTP
                try:
                    ltp_data = groww.get_ltp(
                        segment=groww.SEGMENT_CASH,
                        exchange_trading_symbols=(index_symbol,),
                    )
                    index_ltp = ltp_data.get(index_symbol)
                    if index_ltp is None:
                        print(f"  Could not get LTP for {index_symbol}")
                        continue
                    index_ltp = float(index_ltp)
                except Exception as e:
                    print(f"  LTP error for {index_symbol}: {e}")
                    continue

                underlying = config.UNDERLYING_MAP[index_symbol]

                # Get nearest expiry with suitable contracts
                try:
                    exp_data = groww.get_expiries(groww.EXCHANGE_NSE, underlying)
                    expiries = exp_data.get("expiries", [])
                    if not expiries:
                        print(f"  No expiries found for {underlying}")
                        continue

                    # Filter out expired dates
                    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    valid_expiries = [e for e in expiries if e >= today_str]
                    if not valid_expiries:
                        print(f"  No valid expiries for {underlying}")
                        continue

                except Exception as e:
                    print(f"  Expiry error for {underlying}: {e}")
                    continue

                # Try expiries in order until we find one with ATM contracts
                contracts = []
                expiry = None
                selected_strikes = []

                for candidate_expiry in valid_expiries[:3]:  # Try up to 3 expiries
                    try:
                        # Skip dead expiry: if expiry is today and past 12:30 PM IST
                        if is_expiry_day_past_cutoff(candidate_expiry):
                            print(f"  Expiry {candidate_expiry}: SKIPPED (expiry day past {config.EXPIRY_DAY_CUTOFF_HOUR}:{config.EXPIRY_DAY_CUTOFF_MINUTE:02d} IST cutoff)")
                            continue

                        contracts_data = groww.get_contracts(
                            groww.EXCHANGE_NSE,
                            underlying,
                            candidate_expiry,
                        )
                        candidate_contracts = contracts_data.get("contracts", [])
                        if not candidate_contracts:
                            continue

                        # Extract strikes
                        candidate_strikes = sorted(list(set(
                            int(c.split("-")[3]) for c in candidate_contracts
                            if len(c.split("-")) >= 5
                        )))

                        if not candidate_strikes:
                            continue

                        # Check if ATM strike is reasonably close to index LTP
                        atm = min(candidate_strikes, key=lambda x: abs(x - index_ltp))
                        atm_distance_pct = abs(atm - index_ltp) / index_ltp

                        if atm_distance_pct > 0.05:  # ATM > 5% away = skip
                            print(f"  Expiry {candidate_expiry}: ATM {atm} too far from LTP {index_ltp:.0f} ({atm_distance_pct:.1%}), trying next")
                            continue

                        # Good expiry found
                        expiry = candidate_expiry
                        contracts = candidate_contracts
                        atm_index = candidate_strikes.index(atm)
                        selected_strikes = candidate_strikes[
                            max(0, atm_index - config.ATM_STRIKE_RANGE):
                            atm_index + config.ATM_STRIKE_RANGE + 1
                        ]
                        break

                    except Exception as e:
                        print(f"  Contracts error for {candidate_expiry}: {e}")
                        continue

                if not expiry or not contracts or not selected_strikes:
                    print(f"  No suitable expiry/contracts for {underlying}")
                    continue

                print(f"  Expiry: {expiry} | Selected Strikes: {selected_strikes}")

                # Check each selected strike for entry
                for strike in selected_strikes:
                    opt = "CE" if trend == "UP" else "PE"

                    # Build contract name from expiry date
                    try:
                        exp_dt = datetime.datetime.strptime(expiry, "%Y-%m-%d")
                        exp_formatted = exp_dt.strftime("%d%b%y")
                        # Capitalize first letter of month: 24Feb26
                        contract = f"NSE-{underlying}-{exp_formatted}-{strike}-{opt}"
                    except Exception:
                        continue

                    # Validate contract exists in fetched contracts list
                    if contract not in contracts:
                        continue

                    # Check entry conditions on 15M candles
                    signal, candle = entry_module.check_entry(contract, trend)

                    if not signal:
                        continue

                    print(f"\nENTRY SIGNAL: {contract}")

                    entry_price = candle["close"]
                    atr = candle["ATR"]
                    structure_stop = candle["low"]

                    # Calculate position size
                    position_data = risk_module.calculate_position(
                        entry_price,
                        atr,
                        structure_stop,
                        config.LOT_SIZE[index_symbol],
                    )

                    if position_data is None:
                        print("  Position sizing failed - skipping")
                        continue

                    # Open the trade
                    position_module.open_trade(
                        contract,
                        index_symbol,
                        entry_price,
                        position_data["stop"],
                        position_data["target"],
                        position_data["qty"],
                        config.LOT_SIZE[index_symbol],
                        position_data["risk_per_unit"],
                    )

                    # Register with risk module
                    risk_module.register_trade_opened(index_symbol)

                    print(f"TRADE OPENED: {contract}")
                    print(f"  Entry: {entry_price:.2f}")
                    print(f"  Stop: {position_data['stop']:.2f}")
                    print(f"  Target: {position_data['target']:.2f}")
                    print(f"  Qty: {position_data['qty']} ({position_data['lots']} lots)")

                    # Only one trade per index per cycle
                    break

            # Status update
            print(f"\nCapital: {risk_module.capital:.2f}")
            print(f"Open Positions: {len(position_module.open_positions)}")
            print(f"Daily Trades: {risk_module.daily_trades}")
            print(f"Daily Drawdown: {risk_module.get_daily_drawdown_pct():.2%}")
            print("-------------------------------------\n")

        except KeyboardInterrupt:
            print("\n\nBot stopped by user.")
            print(f"Final Capital: {risk_module.capital:.2f}")
            print(f"Total Logged Trades: {logger.get_trade_count()}")
            break

        except Exception as e:
            print(f"\n[Engine] Unexpected error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(config.LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
