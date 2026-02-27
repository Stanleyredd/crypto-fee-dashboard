import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from db import connect, init_db, seed_exchanges_and_fees

EXCHANGES = [
    ("Bitvavo", "exchange", "https://bitvavo.com"),
    ("Binance", "exchange", "https://www.binance.com"),
    ("Bybit", "exchange", "https://www.bybit.com"),
    ("Kraken", "exchange", "https://www.kraken.com"),
    ("Finst", "broker", "https://finst.com"),
    ("Coinbase", "exchange", "https://coinbase.com"),
    ("Coinmerce", "broker", "https://coinmerce.io"),
    ("BLOX", "broker", "https://weareblox.com"),
    ("eToro", "broker", "https://etoro.com"),
    ("Amdax", "broker", "https://amdax.com"),
]

FEES = {
    "Bitvavo": {
        "trading_fee_pct": 0.25,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 0.10,
        "source_url": "",
    },
    "Finst": {
        "trading_fee_pct": 0.0,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 0.50,
        "source_url": "",
    },
    "Binance": {
        "trading_fee_pct": 0.1,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 0.15,
        "source_url": "",
    },
    "Bybit": {
        "trading_fee_pct": 0.1,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 0.2,
        "source_url": "",
    },
    "Kraken": {
        "trading_fee_pct": 0.26,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 0.2,
        "source_url": "",
    },
    "Coinbase": {
        "trading_fee_pct": 0.60,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 0.80,
        "source_url": "",
    },
    "Coinmerce": {
        "trading_fee_pct": 0.0,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 1.00,
        "source_url": "",
    },
    "BLOX": {
        "trading_fee_pct": 0.0,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 1.00,
        "source_url": "",
    },
    "eToro": {
        "trading_fee_pct": 0.0,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 1.50,
        "source_url": "",
    },
    "Amdax": {
        "trading_fee_pct": 0.0,
        "deposit_ideal_fee_eur": 0.0,
        "withdraw_eur_fee_eur": 0.0,
        "spread_estimate_pct": 1.00,
        "source_url": "",
    },
}


def main() -> None:
    init_db()
    con = connect()
    try:
        seed_exchanges_and_fees(con, exchanges=EXCHANGES, fees_by_name=FEES)
    finally:
        con.close()
    print("DB initialized.")


if __name__ == "__main__":
    main()
