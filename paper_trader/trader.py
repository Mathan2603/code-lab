from __future__ import annotations

import time as time_module
from dataclasses import dataclass
from datetime import date

from paper_trader.broker import GrowwBroker
from paper_trader.config import StorageConfig, TradeConfig
from paper_trader.data_store import TradeDataStore
from paper_trader.execution import PaperExecutionEngine
from paper_trader.models import OptionContract, Position
from paper_trader.risk import RiskManager
from paper_trader.strategy import SimpleTrendStrategy
from paper_trader.utils import IST, now_ist, time_in_range


@dataclass
class UnderlyingState:
    symbol: str
    trend: SimpleTrendStrategy
    expiry: str | None = None
    contracts: list[OptionContract] | None = None
    last_refresh: date | None = None


class OptionPaperTrader:
    def __init__(
        self,
        broker: GrowwBroker,
        trade_config: TradeConfig,
        storage_config: StorageConfig,
    ) -> None:
        self._broker = broker
        self._config = trade_config
        self._storage = TradeDataStore(
            trade_log_dir=storage_config.trade_log_dir,
            portfolio_path=storage_config.portfolio_path,
        )
        self._risk = RiskManager(
            max_loss_per_trade=trade_config.max_loss_per_trade,
            max_daily_loss=trade_config.max_daily_loss,
            max_consecutive_losses=trade_config.max_consecutive_losses,
        )
        self._execution = PaperExecutionEngine(self._risk)
        self._positions: list[Position] = []
        self._underlyings = {
            symbol: UnderlyingState(symbol=symbol, trend=SimpleTrendStrategy())
            for symbol in trade_config.underlying_symbols
        }
        if trade_config.allow_sensex:
            self._underlyings["NSE_SENSEX"] = UnderlyingState(
                symbol="NSE_SENSEX",
                trend=SimpleTrendStrategy(),
            )

    def _refresh_contracts(self, state: UnderlyingState) -> None:
        expiries = self._broker.get_expiries(state.symbol)
        if not expiries:
            raise ValueError(f"No expiries returned for {state.symbol}.")
        expiry = sorted(expiries)[0]
        contracts_raw = self._broker.get_contracts(state.symbol, expiry)
        contracts = self._parse_contracts(contracts_raw, expiry)
        if not contracts:
            raise ValueError(f"No contracts returned for {state.symbol} {expiry}.")
        state.expiry = expiry
        state.contracts = contracts
        state.last_refresh = now_ist().date()

    def _parse_contracts(
        self, contracts_raw: list[dict[str, object]], expiry: str
    ) -> list[OptionContract]:
        contracts: list[OptionContract] = []
        for item in contracts_raw:
            symbol = item.get("symbol") or item.get("trading_symbol")
            strike = item.get("strike") or item.get("strike_price")
            option_type = item.get("option_type") or item.get("instrument_type")
            if symbol is None or strike is None or option_type is None:
                raise ValueError(
                    "Invalid contract data returned from Groww. "
                    "Expected symbol, strike, and option_type."
                )
            option_type = str(option_type).upper()
            if option_type not in {"CE", "PE"}:
                continue
            contracts.append(
                OptionContract(
                    symbol=str(symbol),
                    strike=float(strike),
                    option_type=option_type,
                    expiry=expiry,
                )
            )
        return contracts

    def _select_option(
        self, state: UnderlyingState, underlying_price: float, direction: str
    ) -> OptionContract:
        if state.contracts is None:
            raise ValueError("Contracts not loaded.")
        sorted_contracts = sorted(
            state.contracts,
            key=lambda c: abs(c.strike - underlying_price),
        )
        nearest = sorted_contracts[:20]
        for contract in nearest:
            if direction == "up" and contract.option_type == "CE":
                return contract
            if direction == "down" and contract.option_type == "PE":
                return contract
        raise ValueError(
            f"No matching option contracts found for {state.symbol} direction={direction}."
        )

    def _update_trailing_stop(self, position: Position, ltp: float) -> None:
        step_move = position.entry_price * self._config.trail_step_pct
        if ltp < position.max_favorable_price + step_move:
            return
        position.max_favorable_price = ltp
        trail_sl = ltp * (1 - self._config.trail_sl_pct)
        if trail_sl > position.stop_loss:
            position.stop_loss = trail_sl

    def _calculate_stop_and_target(self, entry_price: float) -> tuple[float, float]:
        max_loss_per_unit = self._config.max_loss_per_trade / max(
            self._config.position_size, 1
        )
        initial_sl = entry_price * (1 - self._config.initial_sl_pct)
        max_loss_sl = entry_price - max_loss_per_unit
        stop_loss = max(initial_sl, max_loss_sl)
        target = entry_price + (entry_price - stop_loss) * self._config.target_rr
        return stop_loss, target

    def _can_enter(self, current_time) -> bool:
        return current_time >= self._config.entry_after

    def _time_exit(self, current_time) -> bool:
        return current_time >= self._config.exit_before

    def _close_position(self, position: Position, exit_price: float) -> None:
        trade_record = self._execution.exit_position(position, exit_price)
        self._storage.append_trade(trade_record)

    def _poll_underlyings(self) -> dict[str, float]:
        symbols = list(self._underlyings.keys())
        return self._broker.get_ltp(segment="CASH", symbols=symbols)

    def _poll_options(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        return self._broker.get_ltp(segment="FNO", symbols=symbols)

    def run(self) -> None:
        while True:
            now = now_ist()
            current_time = now.time()
            if not time_in_range(
                current_time, self._config.entry_after, self._config.exit_before
            ):
                if current_time >= self._config.exit_before:
                    self._exit_all_positions()
                time_module.sleep(self._config.poll_interval_s)
                continue

            if not self._risk.can_take_trade():
                time_module.sleep(self._config.poll_interval_s)
                continue

            underlying_prices = self._poll_underlyings()

            for symbol, price in underlying_prices.items():
                state = self._underlyings[symbol]
                trend = state.trend.update(price)
                if state.last_refresh != now.date():
                    self._refresh_contracts(state)
                if self._positions:
                    continue
                if trend.direction in {"up", "down"} and self._can_enter(current_time):
                    contract = self._select_option(state, price, trend.direction)
                    option_prices = self._poll_options([contract.symbol])
                    option_price = option_prices.get(contract.symbol)
                    if option_price is None:
                        raise ValueError(
                            f"LTP missing for {contract.symbol}. "
                            "Symbol format must be fetched from get_contracts."
                        )
                    stop_loss, target = self._calculate_stop_and_target(option_price)
                    execution = self._execution.enter_position(
                        symbol=contract.symbol,
                        entry_price=option_price,
                        quantity=self._config.position_size,
                        stop_loss=stop_loss,
                        target=target,
                    )
                    self._positions.append(execution.position)
                    self._storage.write_portfolio(self._positions)

            self._manage_positions()
            time_module.sleep(self._config.poll_interval_s)

    def _manage_positions(self) -> None:
        if not self._positions:
            return
        symbols = [position.symbol for position in self._positions]
        prices = self._poll_options(symbols)
        for position in list(self._positions):
            ltp = prices.get(position.symbol)
            if ltp is None:
                continue
            self._update_trailing_stop(position, ltp)
            if ltp <= position.stop_loss or ltp >= position.target:
                self._close_position(position, ltp)
                self._positions.remove(position)
            elif self._time_exit(now_ist().time()):
                self._close_position(position, ltp)
                self._positions.remove(position)
        self._storage.write_portfolio(self._positions)

    def _exit_all_positions(self) -> None:
        if not self._positions:
            return
        symbols = [position.symbol for position in self._positions]
        prices = self._poll_options(symbols)
        for position in list(self._positions):
            ltp = prices.get(position.symbol)
            if ltp is None:
                continue
            self._close_position(position, ltp)
            self._positions.remove(position)
        self._storage.write_portfolio(self._positions)
