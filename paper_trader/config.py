from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from getpass import getpass

from paper_trader.utils import MarketTimes, default_market_times


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    return float(value) if value is not None else default


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    return int(value) if value is not None else default


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class TradeConfig:
    poll_interval_s: int
    max_loss_per_trade: float
    max_daily_loss: float
    max_consecutive_losses: int
    position_size: int
    target_rr: float
    initial_sl_pct: float
    trail_sl_pct: float
    trail_step_pct: float
    entry_after: time
    exit_before: time
    underlying_symbols: tuple[str, ...]
    allow_sensex: bool
    paper_trading: bool

    @staticmethod
    def from_env() -> "TradeConfig":
        market_times = default_market_times()
        return TradeConfig(
            poll_interval_s=_env_int("POLL_INTERVAL_S", 5),
            max_loss_per_trade=_env_float("MAX_LOSS_PER_TRADE", 500.0),
            max_daily_loss=_env_float("MAX_DAILY_LOSS", 1500.0),
            max_consecutive_losses=_env_int("MAX_CONSECUTIVE_LOSSES", 3),
            position_size=_env_int("POSITION_SIZE", 1),
            target_rr=_env_float("TARGET_RR", 2.0),
            initial_sl_pct=_env_float("INITIAL_SL_PCT", 0.25),
            trail_sl_pct=_env_float("TRAIL_SL_PCT", 0.2),
            trail_step_pct=_env_float("TRAIL_STEP_PCT", 0.1),
            entry_after=market_times.entry_after,
            exit_before=market_times.exit_before,
            underlying_symbols=(
                "NSE_NIFTY",
                "NSE_BANKNIFTY",
            ),
            allow_sensex=_env_bool("ALLOW_SENSEX", False),
            paper_trading=_env_bool("PAPER_TRADING", True),
        )


@dataclass(frozen=True)
class AuthConfig:
    token: str

    @staticmethod
    def from_env() -> "AuthConfig":
        token = os.getenv("GROWW_TOKEN")
        if not token:
            token = getpass("Enter GROWW API token: ").strip()
        return AuthConfig(token=token)


@dataclass(frozen=True)
class StorageConfig:
    trade_log_dir: str
    portfolio_path: str

    @staticmethod
    def default() -> "StorageConfig":
        return StorageConfig(
            trade_log_dir="paper_logs",
            portfolio_path="data-paper_portfolio.csv",
        )
