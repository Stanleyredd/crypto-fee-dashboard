import requests


class BinanceCollector:
    SYMBOL_MAP = {
        "BTC-EUR": "BTCEUR",
    }

    def fetch_top_of_book(self, symbol: str = "BTC-EUR"):
        mapped = self.SYMBOL_MAP.get(symbol)
        if not mapped:
            raise ValueError(f"Unsupported symbol for Binance: {symbol}")

        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={mapped}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        bid = float(data["bidPrice"])
        ask = float(data["askPrice"])
        return bid, ask
