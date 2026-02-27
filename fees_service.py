import sqlite3
from typing import Any

import pandas as pd

from collectors import get_collector
from db import (
    create_exchange,
    delete_exchange_cascade as db_delete_exchange_cascade,
    get_exchange_by_name,
    get_latest_quote,
    list_exchange_fee_rows,
    upsert_fee_row,
    insert_quote,
)


class ServiceError(Exception):
    pass


def compute_total_cost(spread_pct: float, fee_pct: float, amount_eur: float) -> tuple[float, float]:
    total_pct = float(spread_pct) + float(fee_pct)
    total_eur = float(amount_eur) * total_pct / 100.0
    return total_pct, total_eur


def add_exchange_with_defaults(
    con: sqlite3.Connection,
    name: str,
    exchange_type: str,
    website: str,
) -> int:
    try:
        return create_exchange(con, name=name, exchange_type=exchange_type, website=website)
    except sqlite3.IntegrityError as exc:
        raise ServiceError(f"Exchange already exists: {name}") from exc
    except (sqlite3.Error, ValueError) as exc:
        raise ServiceError(f"Could not add exchange: {exc}") from exc


def save_exchange_fees(
    con: sqlite3.Connection,
    exchange_id: int,
    trading_fee_pct: float,
    deposit_ideal_fee_eur: float,
    withdraw_eur_fee_eur: float,
    spread_estimate_pct: float,
    source_url: str,
) -> None:
    try:
        upsert_fee_row(
            con,
            exchange_id=exchange_id,
            trading_fee_pct=trading_fee_pct,
            deposit_ideal_fee_eur=deposit_ideal_fee_eur,
            withdraw_eur_fee_eur=withdraw_eur_fee_eur,
            spread_estimate_pct=spread_estimate_pct,
            source_url=source_url,
        )
    except (sqlite3.Error, ValueError) as exc:
        raise ServiceError(f"Could not save fees: {exc}") from exc


def delete_exchange_cascade(con: sqlite3.Connection, exchange_id: int) -> None:
    try:
        deleted = db_delete_exchange_cascade(con, exchange_id)
    except sqlite3.Error as exc:
        raise ServiceError(f"Could not delete exchange: {exc}") from exc

    if not deleted:
        raise ServiceError("Exchange not found.")


def fetch_and_store_bitvavo_quote(
    con: sqlite3.Connection,
    symbol: str = "BTC-EUR",
    collector: Any | None = None,
    exchange_name: str = "Bitvavo",
) -> None:
    row = get_exchange_by_name(con, exchange_name)
    if not row:
        raise ServiceError(f"{exchange_name} staat niet in exchanges. Run scripts/init_db.py")

    try:
        active_collector = collector or get_collector(exchange_name)
        bid, ask = active_collector.fetch_top_of_book(symbol)
        insert_quote(con, exchange_id=int(row["id"]), symbol=symbol, bid=bid, ask=ask)
    except Exception as exc:
        raise ServiceError(f"Could not fetch/store {exchange_name} quote: {exc}") from exc


def build_comparison_dataframe(
    con: sqlite3.Connection,
    symbol: str,
    amount: float,
) -> pd.DataFrame:
    rows = list_exchange_fee_rows(con)
    data: list[dict[str, object]] = []

    for row in rows:
        ex_id = int(row["id"])
        q = get_latest_quote(con, exchange_id=ex_id, symbol=symbol)

        if q:
            bid = float(q["bid"])
            ask = float(q["ask"])
            mid = (bid + ask) / 2.0
            spread_pct = ((ask - bid) / mid) * 100.0 if mid else 0.0
            spread_source = f"live ({q['ts']})"
        else:
            spread_pct = float(row["spread_estimate_pct"])
            spread_source = "estimate"

        total_pct, total_eur = compute_total_cost(
            spread_pct=spread_pct,
            fee_pct=float(row["trading_fee_pct"]),
            amount_eur=amount,
        )

        data.append(
            {
                "Exchange": row["name"],
                "Type": row["type"],
                "Fee %": round(float(row["trading_fee_pct"]), 6),
                "Spread %": round(float(spread_pct), 6),
                "Total %": round(float(total_pct), 6),
                f"Total € (op €{amount})": round(float(total_eur), 2),
                "iDEAL fee €": float(row["deposit_ideal_fee_eur"]),
                "EUR opname €": float(row["withdraw_eur_fee_eur"]),
                "Spread source": spread_source,
                "Fees updated": row["updated_at"],
                "Website": row["website"],
                "Source": row["source_url"] or "",
            }
        )

    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by=f"Total € (op €{amount})", ascending=True)
    return df
