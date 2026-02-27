import requests


class BybitCollector:
    SYMBOL_MAP = {
        "BTC-EUR": "BTCEUR",
    }

    def fetch_top_of_book(self, symbol: str = "BTC-EUR"):
        mapped = self.SYMBOL_MAP.get(symbol)
        if not mapped:
            raise ValueError(f"Unsupported symbol for Bybit: {symbol}")

        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={mapped}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if str(data.get("retCode")) != "0":
            raise ValueError(f"Bybit API error for {mapped}: {data.get('retMsg', 'unknown error')}")

        rows = data.get("result", {}).get("list", [])
        if not rows:
            raise ValueError(f"No Bybit ticker data for {mapped}")

        top = rows[0]
        bid = float(top["bid1Price"])
        ask = float(top["ask1Price"])
        return bid, ask
