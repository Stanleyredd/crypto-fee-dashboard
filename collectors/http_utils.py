from __future__ import annotations

from typing import Iterable

import requests

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KiralyAI/1.0; +https://kiraly.ai)",
    "Accept": "application/json",
}


def get_json_with_bases(
    bases: Iterable[str],
    path_with_query: str,
) -> dict:
    errors: list[str] = []
    for base in bases:
        url = f"{base}{path_with_query}"
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(3, 10))
            if response.status_code != 200:
                errors.append(f"{url} -> HTTP {response.status_code}")
                continue
            return response.json()
        except Exception as exc:
            errors.append(f"{url} -> {exc}")

    raise RuntimeError(
        f"All endpoints failed for {path_with_query}: " + " | ".join(errors)
    )


def get_usdt_eur_mid_coinbase() -> float:
    data = get_json_with_bases(
        ["https://api.coinbase.com"],
        "/v2/exchange-rates?currency=USDT",
    )

    rates = data.get("data", {}).get("rates", {})
    eur = rates.get("EUR")
    if eur is None:
        raise RuntimeError("Coinbase exchange-rates response missing EUR for USDT")

    rate = float(eur)
    if rate <= 0:
        raise RuntimeError(f"Invalid USDT->EUR rate from Coinbase: {rate}")

    return rate
