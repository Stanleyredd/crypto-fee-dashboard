from collectors.bitvavo import BitvavoCollector
from collectors.binance import BinanceCollector
from collectors.bybit import BybitCollector
from collectors.coinbase import CoinbaseCollector
from collectors.kraken import KrakenCollector

COLLECTOR_REGISTRY = {
    "Bitvavo": BitvavoCollector,
    "Coinbase": CoinbaseCollector,
    "Bybit": BybitCollector,
    "Kraken": KrakenCollector,
    "Binance": BinanceCollector,
}


def get_collector(name: str):
    collector_cls = COLLECTOR_REGISTRY.get(name)
    if collector_cls is None:
        raise ValueError(f"No collector registered for exchange: {name}")
    return collector_cls()


def get_supported_exchange_names() -> list[str]:
    return list(COLLECTOR_REGISTRY.keys())
