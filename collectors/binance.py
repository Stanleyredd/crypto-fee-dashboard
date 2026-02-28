import requests

from collectors.http_utils import DEFAULT_HEADERS, get_usdt_eur_mid_coinbase


class BinanceCollector:
    BASE_URLS = [
        "https://api.binance.com",
        "https://data-api.binance.vision",
        "https://www.binance.com",
    ]

    def __init__(self):
        self.last_quote_mode = "direct"

    def _fetch_btcusdt_book(self) -> tuple[float, float]:
        path = "/api/v3/ticker/bookTicker?symbol=BTCUSDT"
        errors: list[str] = []
        last_status: int | None = None
        last_url: str | None = None

        for base in self.BASE_URLS:
            url = f"{base}{path}"
            last_url = url
            try:
                response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(3, 10))
                last_status = response.status_code
                if response.status_code != 200:
                    errors.append(f"{url} -> HTTP {response.status_code}")
                    continue

                data = response.json()
                bid = float(data["bidPrice"])
                ask = float(data["askPrice"])
                return bid, ask
            except Exception as exc:
                errors.append(f"{url} -> {exc}")

        raise RuntimeError(
            "Binance BTCUSDT fetch failed"
            f" (last_status={last_status}, last_url={last_url}): "
            + " | ".join(errors)
        )

    def fetch_top_of_book(self, symbol: str = "BTC-EUR"):
        if symbol != "BTC-EUR":
            raise ValueError(f"Unsupported symbol for Binance: {symbol}")

        bid_usdt, ask_usdt = self._fetch_btcusdt_book()
        usdt_eur = get_usdt_eur_mid_coinbase()

        bid_eur = float(bid_usdt) * float(usdt_eur)
        ask_eur = float(ask_usdt) * float(usdt_eur)
        self.last_quote_mode = "fallback_btcusdt_usdteur"
        return bid_eur, ask_eur
