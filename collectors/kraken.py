import requests


class KrakenCollector:
    SYMBOL_MAP = {
        "BTC-EUR": "XXBTZEUR",
    }

    def fetch_top_of_book(self, symbol: str = "BTC-EUR"):
        mapped = self.SYMBOL_MAP.get(symbol)
        if not mapped:
            raise ValueError(f"Unsupported symbol for Kraken: {symbol}")

        url = f"https://api.kraken.com/0/public/Depth?pair={mapped}&count=1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        errors = data.get("error", [])
        if errors:
            raise ValueError(f"Kraken API error for {mapped}: {', '.join(errors)}")

        result = data.get("result", {})
        if not result:
            raise ValueError(f"No Kraken depth data for {mapped}")

        book = next(iter(result.values()))
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if not bids or not asks:
            raise ValueError(f"Incomplete Kraken orderbook for {mapped}")

        bid = float(bids[0][0])
        ask = float(asks[0][0])
        return bid, ask
