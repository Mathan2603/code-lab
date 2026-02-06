from __future__ import annotations

import threading
import time
from datetime import time as dtime
from typing import Any

from paper_trader.broker import GrowwPaperBroker
from paper_trader.data_store import CsvStore
from paper_trader.models import EngineSnapshot, OptionContract, Position, TokenStatus, TradeRecord
from paper_trader.risk import RiskManager
from paper_trader.strategy import DirectionalTrend
from paper_trader.token_pool import TokenPool
from paper_trader.utils import InMemoryLogger, now_ist, token_preview


class PaperTraderEngine:
    def __init__(
        self,
        broker: GrowwPaperBroker,
        token_pool: TokenPool,
        poll_seconds: int = 5,
        quantity: int = 1,
    ) -> None:
        self.broker = broker
        self.tokens = token_pool
        self.poll_seconds = max(5, poll_seconds)
        self.quantity = max(1, quantity)
        self.logger = InMemoryLogger(capacity=500)
        self.store = CsvStore()
        self.risk = RiskManager()
        self.trend = {
            "NSE_NIFTY": DirectionalTrend(),
            "NSE_BANKNIFTY": DirectionalTrend(),
        }
        self.positions: list[Position] = []
        self.realized_pnl = 0.0
        self.trade_seq = 0
        self._active_token = ""
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def validate_tokens(self) -> list[tuple[str, bool, str]]:
        rows: list[tuple[str, bool, str]] = []
        for status in self.tokens.statuses():
            ok, msg = self.broker.validate_token(status)
            if not ok:
                self.tokens.mark_failed(status.token, msg)
            rows.append((token_preview(status.token), ok, msg))
            self.logger.info(f"Token validation {token_preview(status.token)}: {'OK' if ok else 'FAILED'}")
        return rows

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("Paper trader started")

    def stop(self) -> None:
        self._stop.set()
        self.logger.info("Stop signal sent")

    def snapshot(self) -> EngineSnapshot:
        unrealized = 0.0
        return EngineSnapshot(
            running=bool(self._thread and self._thread.is_alive()),
            active_token_preview=token_preview(self._active_token) if self._active_token else "-",
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized,
            open_positions=list(self.positions),
            logs=self.logger.tail(50),
        )

    def _next_token(self) -> TokenStatus:
        t = self.tokens.choose_next()
        self._active_token = t.token
        self.logger.info(f"Token rotation -> {token_preview(t.token)}")
        return t

    def _sdk_segment_cash(self, token: str) -> Any:
        client = self.broker._client(token)  # noqa: SLF001 - local constant access
        return client.SEGMENT_CASH

    def _sdk_segment_fno(self, token: str) -> Any:
        client = self.broker._client(token)  # noqa: SLF001
        return client.SEGMENT_FNO

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                allowed, reason = self.risk.can_trade()
                if not allowed:
                    self.logger.info(f"Risk block: {reason}")
                    time.sleep(self.poll_seconds)
                    continue

                now = now_ist().time()
                if now < dtime(10, 15):
                    time.sleep(self.poll_seconds)
                    continue

                self._evaluate_new_entries()
                self._manage_positions()
            except Exception as exc:  # noqa: BLE001
                self.logger.info(f"Engine error: {exc}")
            time.sleep(self.poll_seconds)

    def _evaluate_new_entries(self) -> None:
        if self.positions:
            return

        for underlying in ("NSE_NIFTY", "NSE_BANKNIFTY"):
            token = self._next_token().token
            try:
                ltp_resp = self.broker.get_ltp(
                    token=token,
                    segment=self._sdk_segment_cash(token),
                    exchange_trading_symbols=(underlying,),
                )
                u_price = self._extract_ltp(ltp_resp, underlying)
                direction = self.trend[underlying].update(u_price)
                if direction not in {"up", "down"}:
                    continue
                contract = self._pick_contract(token, underlying, direction)
                option_ltp_resp = self.broker.get_ltp(
                    token=token,
                    segment=self._sdk_segment_fno(token),
                    exchange_trading_symbols=(contract.symbol,),
                )
                option_price = self._extract_ltp(option_ltp_resp, contract.symbol)
                stop, target = self.risk.stop_target(option_price, self.quantity)
                self.positions.append(
                    Position(
                        symbol=contract.symbol,
                        quantity=self.quantity,
                        entry_price=option_price,
                        stop_loss=stop,
                        target=target,
                        opened_at=now_ist(),
                        direction=direction,
                        max_price_seen=option_price,
                    )
                )
                self.store.write_positions(self.positions)
                self.logger.info(
                    f"ENTRY {contract.symbol} @ {option_price:.2f}, SL {stop:.2f}, TGT {target:.2f}"
                )
                break
            except Exception as exc:  # noqa: BLE001
                self.tokens.mark_failed(token, str(exc))
                self.logger.info(f"Token/API failure {token_preview(token)}: {exc}")

    def _pick_contract(self, token: str, underlying: str, direction: str) -> OptionContract:
        chain = self.broker.get_option_chain(
            token=token,
            exchange_trading_symbol=underlying,
            expiry="nearest",
        )
        contracts = self._flatten_option_chain(chain)
        if not contracts:
            contracts_raw = self.broker.get_contracts(token=token, exchange_trading_symbol=underlying, expiry="nearest")
            contracts = self._parse_contracts(contracts_raw)
        if not contracts:
            raise RuntimeError(f"No contracts available for {underlying}")

        desired = "CE" if direction == "up" else "PE"
        filtered = [c for c in contracts if c.option_type == desired]
        if not filtered:
            raise RuntimeError(f"No {desired} contracts for {underlying}")
        return filtered[:20][0]

    def _flatten_option_chain(self, chain: Any) -> list[OptionContract]:
        contracts: list[OptionContract] = []
        if isinstance(chain, dict):
            rows = chain.get("data") or chain.get("option_chain") or []
        else:
            rows = chain
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            symbol = row.get("exchange_trading_symbol") or row.get("symbol")
            strike = row.get("strike_price") or row.get("strike")
            opt = row.get("option_type")
            expiry = row.get("expiry") or ""
            if symbol and strike and opt in {"CE", "PE"}:
                contracts.append(OptionContract(symbol=str(symbol), strike=float(strike), option_type=str(opt), expiry=str(expiry)))
        return contracts

    def _parse_contracts(self, contracts_raw: Any) -> list[OptionContract]:
        rows = contracts_raw if isinstance(contracts_raw, list) else contracts_raw.get("data", [])
        contracts: list[OptionContract] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = row.get("exchange_trading_symbol") or row.get("symbol")
            strike = row.get("strike_price") or row.get("strike")
            option_type = row.get("option_type")
            expiry = row.get("expiry") or ""
            if symbol and strike and option_type in {"CE", "PE"}:
                contracts.append(OptionContract(symbol=symbol, strike=float(strike), option_type=option_type, expiry=expiry))
        return contracts

    def _manage_positions(self) -> None:
        if not self.positions:
            return

        token = self._next_token().token
        symbols = tuple(p.symbol for p in self.positions)
        try:
            resp = self.broker.get_ltp(
                token=token,
                segment=self._sdk_segment_fno(token),
                exchange_trading_symbols=symbols,
            )
        except Exception as exc:  # noqa: BLE001
            self.tokens.mark_failed(token, str(exc))
            self.logger.info(f"Position polling failed {token_preview(token)}: {exc}")
            return

        for p in list(self.positions):
            ltp = self._extract_ltp(resp, p.symbol)
            p.max_price_seen = max(p.max_price_seen, ltp)
            p.stop_loss = self.risk.trail(p.stop_loss, p.max_price_seen)

            now = now_ist().time()
            should_exit = ltp <= p.stop_loss or ltp >= p.target or now >= dtime(15, 20)
            if not should_exit:
                continue

            pnl = (ltp - p.entry_price) * p.quantity
            self.realized_pnl += pnl
            self.risk.register_trade(pnl)
            self.trade_seq += 1
            trade = TradeRecord(
                sno=self.trade_seq,
                time=now_ist(),
                symbol=p.symbol,
                buy_price=p.entry_price,
                quantity=p.quantity,
                entry_price=p.entry_price,
                stop_loss=p.stop_loss,
                target=p.target,
                sold_price=ltp,
                pnl_after_trade=pnl,
            )
            self.store.append_trade(trade)
            self.positions.remove(p)
            self.logger.info(f"EXIT {p.symbol} @ {ltp:.2f}, PnL {pnl:.2f}")

        self.store.write_positions(self.positions)

    def _extract_ltp(self, payload: Any, symbol: str) -> float:
        if isinstance(payload, dict):
            if symbol in payload:
                value = payload[symbol]
                if isinstance(value, dict):
                    return float(value.get("ltp"))
                return float(value)
            data = payload.get("data")
            if isinstance(data, dict) and symbol in data:
                val = data[symbol]
                return float(val.get("ltp", val)) if isinstance(val, dict) else float(val)
        if isinstance(payload, list):
            for row in payload:
                if not isinstance(row, dict):
                    continue
                key = row.get("exchange_trading_symbol") or row.get("symbol")
                if key == symbol:
                    return float(row.get("ltp") or row.get("last_price"))
        raise RuntimeError(f"Unable to parse LTP for {symbol}")
