from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime
from typing import Any

from paper_trader.broker import GrowwPaperBroker
from paper_trader.data_store import CsvStore
from paper_trader.models import EngineSnapshot, OptionContract, Position, TokenStatus, TradeRecord
from paper_trader.risk import RiskManager
from paper_trader.strategy import DirectionalTrend
from paper_trader.token_pool import TokenPool
from paper_trader.utils import InMemoryLogger, IST, now_ist, token_preview


@dataclass
class InstrumentBook:
    rows: list[dict[str, Any]]


class PaperTraderEngine:
    def __init__(self, broker: GrowwPaperBroker, token_pool: TokenPool, poll_seconds: int = 5, quantity: int = 1) -> None:
        self.broker = broker
        self.tokens = token_pool
        self.poll_seconds = max(5, poll_seconds)
        self.quantity = max(1, quantity)
        self.logger = InMemoryLogger(capacity=500)
        self.store = CsvStore()
        self.risk = RiskManager()
        self.trend = {"NSE_NIFTY": DirectionalTrend(), "NSE_BANKNIFTY": DirectionalTrend()}
        self.positions: list[Position] = []
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.trade_seq = 0
        self._active_token = ""
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._book: InstrumentBook | None = None

    def validate_tokens(self) -> list[tuple[str, bool, str]]:
        rows: list[tuple[str, bool, str]] = []
        for status in self.tokens.statuses():
            ok, msg = self.broker.validate_token(status)
            if not ok:
                self.tokens.mark_failed(status.token, msg)
            rows.append((token_preview(status.token), ok, msg))
            self.logger.info(f"token_validation {token_preview(status.token)} => {msg}")
        return rows

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._load_instruments_once()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("paper_trader_started")

    def stop(self) -> None:
        self._stop.set()
        self.logger.info("paper_trader_stop_signal")

    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot(
            running=bool(self._thread and self._thread.is_alive()),
            active_token_preview=token_preview(self._active_token) if self._active_token else "-",
            realized_pnl=self.realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            open_positions=list(self.positions),
            logs=self.logger.tail(50),
        )

    def _next_token(self) -> TokenStatus:
        st = self.tokens.choose_next()
        self._active_token = st.token
        self.logger.info(f"token_rotation {token_preview(st.token)}")
        return st

    def _load_instruments_once(self) -> None:
        if self._book is not None:
            return
        token = self._next_token().token
        try:
            rows = self.broker.load_instruments(token)
            parsed = rows if isinstance(rows, list) else []
            if not parsed:
                raise RuntimeError("instrument load returned empty/non-list")
            self._book = InstrumentBook(rows=parsed)
            self.logger.info(f"instrument_book_loaded rows={len(parsed)}")
        except Exception as exc:  # noqa: BLE001
            self.tokens.mark_failed(token, str(exc))
            raise RuntimeError(f"Unable to load instrument book: {exc}") from exc

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                ok, reason = self.risk.can_trade()
                if not ok:
                    self.logger.info(f"risk_block {reason}")
                    time.sleep(self.poll_seconds)
                    continue

                t = now_ist().time()
                if t < dtime(10, 15):
                    time.sleep(self.poll_seconds)
                    continue

                if t >= dtime(15, 20):
                    self._exit_all("time_exit")
                    time.sleep(self.poll_seconds)
                    continue

                self._evaluate_entry()
                self._manage_position()
            except Exception as exc:  # noqa: BLE001
                self.logger.info(f"engine_error {exc}")
            time.sleep(self.poll_seconds)

    def _evaluate_entry(self) -> None:
        if self.positions:
            return

        for underlying_symbol in ("NSE_NIFTY", "NSE_BANKNIFTY"):
            token = self._next_token().token
            try:
                groww = self.broker.client(token)
                payload = self.broker.get_ltp(token, groww.SEGMENT_CASH, (underlying_symbol,))
                underlying_ltp = self._parse_ltp(payload, underlying_symbol)
                direction = self.trend[underlying_symbol].update(underlying_ltp)
                if direction not in {"up", "down"}:
                    continue

                option = self._select_option_from_instruments(underlying_symbol, underlying_ltp, direction)
                opt_payload = self.broker.get_ltp(token, groww.SEGMENT_FNO, (option.symbol,))
                entry_price = self._parse_ltp(opt_payload, option.symbol)
                stop, target = self.risk.stop_target(entry_price, self.quantity)
                self.positions = [
                    Position(
                        symbol=option.symbol,
                        quantity=self.quantity,
                        entry_price=entry_price,
                        stop_loss=stop,
                        target=target,
                        opened_at=now_ist(),
                        direction=direction,
                        max_price_seen=entry_price,
                    )
                ]
                self.store.write_positions(self.positions)
                self.logger.info(f"entry {option.symbol} @ {entry_price:.2f} sl={stop:.2f} tgt={target:.2f}")
                return
            except Exception as exc:  # noqa: BLE001
                self.tokens.mark_failed(token, str(exc))
                self.logger.info(f"entry_error {token_preview(token)} {exc}")

    def _manage_position(self) -> None:
        if not self.positions:
            self.unrealized_pnl = 0.0
            return

        token = self._next_token().token
        position = self.positions[0]
        try:
            groww = self.broker.client(token)
            payload = self.broker.get_ltp(token, groww.SEGMENT_FNO, (position.symbol,))
            ltp = self._parse_ltp(payload, position.symbol)
            position.max_price_seen = max(position.max_price_seen, ltp)
            position.stop_loss = self.risk.trail(position.stop_loss, position.max_price_seen)
            self.unrealized_pnl = (ltp - position.entry_price) * position.quantity

            if ltp <= position.stop_loss or ltp >= position.target or now_ist().time() >= dtime(15, 20):
                self._close_position(ltp, "sl_tgt_or_time")
            else:
                self.store.write_positions(self.positions)
        except Exception as exc:  # noqa: BLE001
            self.tokens.mark_failed(token, str(exc))
            self.logger.info(f"manage_error {token_preview(token)} {exc}")

    def _close_position(self, exit_price: float, reason: str) -> None:
        if not self.positions:
            return
        p = self.positions[0]
        pnl = (exit_price - p.entry_price) * p.quantity
        self.realized_pnl += pnl
        self.unrealized_pnl = 0.0
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
            sold_price=exit_price,
            pnl_after_trade=pnl,
        )
        self.store.append_trade(trade)
        self.positions = []
        self.store.write_positions([])
        self.logger.info(f"exit {p.symbol} @ {exit_price:.2f} pnl={pnl:.2f} reason={reason}")

    def _exit_all(self, reason: str) -> None:
        if not self.positions:
            return
        token = self._next_token().token
        p = self.positions[0]
        try:
            groww = self.broker.client(token)
            payload = self.broker.get_ltp(token, groww.SEGMENT_FNO, (p.symbol,))
            ltp = self._parse_ltp(payload, p.symbol)
            self._close_position(ltp, reason)
        except Exception as exc:  # noqa: BLE001
            self.tokens.mark_failed(token, str(exc))
            self.logger.info(f"forced_exit_error {token_preview(token)} {exc}")

    def _parse_ltp(self, payload: Any, symbol: str) -> float:
        """Single accepted structure: list of rows with symbol + ltp fields."""
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected LTP payload type; expected list")
        for row in payload:
            if not isinstance(row, dict):
                continue
            sym = row.get("exchange_trading_symbol") or row.get("symbol")
            if sym == symbol and row.get("ltp") is not None:
                return float(row["ltp"])
        raise RuntimeError(f"LTP not found for {symbol}")

    def _select_option_from_instruments(self, underlying_symbol: str, underlying_ltp: float, direction: str) -> OptionContract:
        if self._book is None:
            raise RuntimeError("Instrument book unavailable")

        underlying_plain = "NIFTY" if underlying_symbol == "NSE_NIFTY" else "BANKNIFTY"
        desired_opt = "CE" if direction == "up" else "PE"
        expiry = self._resolve_expiry(underlying_plain)
        rows = self._filter_option_rows(underlying_plain, expiry, desired_opt)
        if not rows:
            raise RuntimeError(f"No {desired_opt} options found for {underlying_plain} {expiry}")

        rows.sort(key=lambda r: abs(float(r["strike"]) - underlying_ltp))
        selected = rows[:20][0]
        return OptionContract(
            symbol=str(selected["symbol"]),
            strike=float(selected["strike"]),
            option_type=desired_opt,
            expiry=expiry,
        )

    def _resolve_expiry(self, underlying_plain: str) -> str:
        if self._book is None:
            raise RuntimeError("Instrument book unavailable")

        today = now_ist().date()
        expiries: list[date] = []
        for row in self._book.rows:
            if (row.get("underlying") or "").upper() != underlying_plain:
                continue
            expiry_txt = str(row.get("expiry") or row.get("expiry_date") or "")
            dt = self._parse_date(expiry_txt)
            if dt and dt >= today:
                expiries.append(dt)

        if not expiries:
            raise RuntimeError(f"No future expiries found for {underlying_plain}")

        uniq = sorted(set(expiries))
        if underlying_plain == "BANKNIFTY":
            monthly = self._monthly_expiries(uniq)
            if not monthly:
                raise RuntimeError("BANKNIFTY monthly expiry not found")
            return monthly[0].isoformat()
        return uniq[0].isoformat()

    def _monthly_expiries(self, expiries: list[date]) -> list[date]:
        by_month: dict[tuple[int, int], date] = {}
        for ex in expiries:
            key = (ex.year, ex.month)
            by_month[key] = max(ex, by_month.get(key, ex))
        return sorted(by_month.values())

    def _filter_option_rows(self, underlying_plain: str, expiry: str, option_type: str) -> list[dict[str, Any]]:
        assert self._book is not None
        out: list[dict[str, Any]] = []
        for row in self._book.rows:
            row_under = (row.get("underlying") or "").upper()
            row_exp = str(row.get("expiry") or row.get("expiry_date") or "")
            row_type = str(row.get("option_type") or row.get("instrument_type") or "").upper()
            symbol = row.get("exchange_trading_symbol") or row.get("symbol")
            strike = row.get("strike") or row.get("strike_price")
            if row_under != underlying_plain:
                continue
            if not symbol or strike is None:
                continue
            if self._normalize_date(row_exp) != expiry:
                continue
            if row_type != option_type:
                continue
            out.append({"symbol": symbol, "strike": float(strike)})
        return out

    def _normalize_date(self, value: str) -> str:
        dt = self._parse_date(value)
        if dt is None:
            return ""
        return dt.isoformat()

    def _parse_date(self, value: str) -> date | None:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d%b%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except Exception:  # noqa: BLE001
                continue
        return None
