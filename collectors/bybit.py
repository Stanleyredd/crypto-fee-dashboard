import requests

from collectors.http_utils import DEFAULT_HEADERS, get_usdt_eur_mid_coinbase


class BybitCollector:
    BASE_URLS = ["https://api.bybit.com"]

    def __init__(self):
        self.last_quote_mode = "direct"

    def _fetch_btcusdt(self) -> tuple[float, float]:
        endpoints = [
            "/v5/market/orderbook?category=spot&symbol=BTCUSDT&limit=1",
            "/v5/market/tickers?category=spot&symbol=BTCUSDT",
        ]

        errors: list[str] = []
        last_status: int | None = None
        last_url: str | None = None

        for base in self.BASE_URLS:
            for path in endpoints:
                url = f"{base}{path}"
                last_url = url
                try:
                    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(3, 10))
                    last_status = response.status_code
                    if response.status_code != 200:
                        errors.append(f"{url} -> HTTP {response.status_code}")
                        continue

                    data = response.json()
                    if str(data.get("retCode")) != "0":
                        errors.append(f"{url} -> API {data.get('retMsg', 'unknown error')}")
                        continue

                    if "orderbook" in path:
                        result = data.get("result", {})
                        bids = result.get("b", [])
                        asks = result.get("a", [])
                        if not bids or not asks:
                            errors.append(f"{url} -> missing bids/asks")
                            continue
                        bid = float(bids[0][0])
                        ask = float(asks[0][0])
                        return bid, ask

                    rows = data.get("result", {}).get("list", [])
                    if not rows:
                        errors.append(f"{url} -> empty ticker list")
                        continue
                    top = rows[0]
                    bid = float(top["bid1Price"])
                    ask = float(top["ask1Price"])
                    return bid, ask
                except Exception as exc:
                    errors.append(f"{url} -> {exc}")

        raise RuntimeError(
            "Bybit BTCUSDT fetch failed"
            f" (last_status={last_status}, last_url={last_url}): "
            + " | ".join(errors)
        )

    def fetch_top_of_book(self, symbol: str = "BTC-EUR"):
        if symbol != "BTC-EUR":
            raise ValueError(f"Unsupported symbol for Bybit: {symbol}")

        bid_usdt, ask_usdt = self._fetch_btcusdt()
        usdt_eur = get_usdt_eur_mid_coinbase()

        bid_eur = float(bid_usdt) * float(usdt_eur)
        ask_eur = float(ask_usdt) * float(usdt_eur)
        self.last_quote_mode = "fallback_btcusdt_usdteur"
        return bid_eur, ask_eur
