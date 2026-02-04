from __future__ import annotations

from paper_trader.broker import GrowwBroker
from paper_trader.config import AuthConfig, StorageConfig, TradeConfig
from paper_trader.trader import OptionPaperTrader


def main() -> None:
    auth = AuthConfig.from_env()
    trade_config = TradeConfig.from_env()
    storage_config = StorageConfig.default()
    broker = GrowwBroker(token=auth.token)
    trader = OptionPaperTrader(
        broker=broker,
        trade_config=trade_config,
        storage_config=storage_config,
    )
    trader.run()


if __name__ == "__main__":
    main()
