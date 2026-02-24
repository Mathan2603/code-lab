"""
position_module.py - Trade management (open positions tracking).
Responsibility: Track open trades, manage stops, breakeven, trailing, exits.
No entry logic. No risk calculation.
"""

import datetime
import config


class PositionModule:
    def __init__(self):
        self.open_positions = []

    def open_trade(self, contract: str, index_symbol: str, entry_price: float,
                   stop_price: float, target_price: float, qty: int,
                   lot_size: int, risk_per_unit: float):
        """
        Open a new paper trade.
        """
        trade = {
            "contract": contract,
            "index": index_symbol,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "target_price": target_price,
            "qty": qty,
            "lot_size": lot_size,
            "risk_per_unit": risk_per_unit,
            "entry_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "highest_since_entry": entry_price,
            "breakeven_moved": False,
            "trailing_active": False,
        }
        self.open_positions.append(trade)

    def manage_positions(self, groww, risk_module, logger):
        """
        Manage all open positions every cycle:
        - Fetch current LTP
        - Check stop hit
        - Check target hit
        - Move to breakeven at 1R
        - Trail after 1.5R
        """
        if not self.open_positions:
            return

        closed_trades = []

        for trade in self.open_positions:
            try:
                # Fetch current LTP for the option
                ltp = self._get_option_ltp(groww, trade)
                if ltp is None:
                    continue

                entry = trade["entry_price"]
                stop = trade["stop_price"]
                target = trade["target_price"]
                risk = trade["risk_per_unit"]
                qty = trade["qty"]

                # Update highest since entry
                if ltp > trade["highest_since_entry"]:
                    trade["highest_since_entry"] = ltp

                # Check stop hit
                if ltp <= stop:
                    pnl = (ltp - entry) * qty
                    self._close_trade(trade, ltp, pnl, "STOP HIT", risk_module, logger)
                    closed_trades.append(trade)
                    continue

                # Check target hit
                if ltp >= target:
                    pnl = (ltp - entry) * qty
                    self._close_trade(trade, ltp, pnl, "TARGET HIT", risk_module, logger)
                    closed_trades.append(trade)
                    continue

                # Move to breakeven at 1R
                move_from_entry = ltp - entry
                r_multiple = move_from_entry / risk if risk > 0 else 0

                if not trade["breakeven_moved"] and r_multiple >= config.BREAKEVEN_R:
                    trade["stop_price"] = entry
                    trade["breakeven_moved"] = True
                    print(f"  [Position] Breakeven moved: {trade['contract']} stop -> {entry:.2f}")

                # Trail after 1.5R
                if r_multiple >= config.TRAIL_R:
                    trade["trailing_active"] = True
                    # Trail stop = entry + (current_move - 1R)
                    trail_stop = entry + (move_from_entry - risk)
                    if trail_stop > trade["stop_price"]:
                        trade["stop_price"] = trail_stop
                        print(f"  [Position] Trail updated: {trade['contract']} stop -> {trail_stop:.2f}")

            except Exception as e:
                print(f"  [Position] Error managing {trade['contract']}: {e}")

        # Remove closed trades
        for trade in closed_trades:
            if trade in self.open_positions:
                self.open_positions.remove(trade)

    def _get_option_ltp(self, groww, trade: dict):
        """
        Fetch LTP for an option contract.
        Convert contract format to LTP symbol format.
        """
        try:
            contract = trade["contract"]
            # Contract: NSE-NIFTY-24Feb26-25600-CE
            # LTP symbol: NSE_NIFTY26FEB25600CE (monthly)
            # For weekly, must use get_quote or proper format

            ltp_symbol = self._contract_to_ltp_symbol(contract)
            if ltp_symbol is None:
                # Fallback: try get_quote
                return self._get_ltp_via_quote(groww, contract)

            ltp_data = groww.get_ltp(
                segment=groww.SEGMENT_FNO,
                exchange_trading_symbols=(ltp_symbol,),
            )

            ltp = ltp_data.get(ltp_symbol)
            if ltp is None:
                # Fallback to get_quote
                return self._get_ltp_via_quote(groww, contract)

            return float(ltp)

        except Exception as e:
            print(f"  [Position] LTP fetch error: {e}")
            # Fallback to get_quote
            return self._get_ltp_via_quote(groww, contract)

    def _contract_to_ltp_symbol(self, contract: str):
        """
        Convert contract format to LTP exchange_trading_symbol.
        Contract: NSE-NIFTY-24Feb26-25600-CE
        Monthly LTP: NSE_NIFTY26FEB25600CE

        WARNING: Weekly symbols should NOT be guessed.
        Returns None if format is uncertain.
        """
        try:
            parts = contract.split("-")
            if len(parts) != 5:
                return None

            exchange = parts[0]       # NSE
            underlying = parts[1]     # NIFTY
            date_str = parts[2]       # 24Feb26
            strike = parts[3]         # 25600
            opt_type = parts[4]       # CE

            # Parse the date to determine if monthly or weekly
            from datetime import datetime as dt
            exp_date = dt.strptime(date_str, "%d%b%y")

            # For monthly expiry, format: NSE_NIFTY26FEB25600CE
            # (YY + MON_UPPER + strike + type)
            year_2d = exp_date.strftime("%y")
            month_upper = exp_date.strftime("%b").upper()

            ltp_symbol = f"NSE_{underlying}{year_2d}{month_upper}{strike}{opt_type}"
            return ltp_symbol

        except Exception:
            return None

    def _get_ltp_via_quote(self, groww, contract: str):
        """
        Fallback: get LTP via get_quote for weekly contracts.
        trading_symbol = contract, exchange = NSE, segment = FNO
        """
        try:
            quote = groww.get_quote(
                trading_symbol=contract,
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_FNO,
            )
            ltp = quote.get("ltp")
            if ltp is not None:
                return float(ltp)
            return None
        except Exception as e:
            print(f"  [Position] Quote fallback error: {e}")
            return None

    def _close_trade(self, trade: dict, exit_price: float, pnl: float,
                     reason: str, risk_module, logger):
        """Close a trade and log it."""
        print(f"\nTrade Closed: {trade['contract']} | {reason} | PnL: {pnl:.2f}")

        risk_module.register_trade_closed(trade["index"], pnl)
        print(f"Capital: {risk_module.capital:.2f}")

        logger.log_trade(
            date=trade["entry_time"],
            contract=trade["contract"],
            index=trade["index"],
            entry=trade["entry_price"],
            exit_price=exit_price,
            qty=trade["qty"],
            lot=trade["lot_size"],
            pnl=pnl,
            capital_after=risk_module.capital,
        )

    def has_open_position(self, index_symbol: str) -> bool:
        """Check if there's an open position for this index."""
        return any(t["index"] == index_symbol for t in self.open_positions)
