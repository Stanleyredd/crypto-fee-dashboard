import requests


class CoinbaseCollector:
    def fetch_top_of_book(self, symbol: str):
        product_id = symbol
        url = f"https://api.exchange.coinbase.com/products/{product_id}/ticker"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        bid = float(data["bid"])
        ask = float(data["ask"])
        return bid, ask
