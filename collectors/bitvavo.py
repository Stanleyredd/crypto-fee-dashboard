import requests


class BitvavoCollector:
    def fetch_top_of_book(self, symbol: str = "BTC-EUR"):
        url = f"https://api.bitvavo.com/v2/ticker/book?market={symbol}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        bid = float(data["bid"])
        ask = float(data["ask"])
        return bid, ask


# Backward-compatible helper for existing call sites.
def fetch_bitvavo_top_of_book(symbol: str = "BTC-EUR"):
    return BitvavoCollector().fetch_top_of_book(symbol)
