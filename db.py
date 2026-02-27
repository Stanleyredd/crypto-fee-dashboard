import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DB_PATH = Path("data/app.db")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    con = connect()
    try:
        cur = con.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                website TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fees (
                exchange_id INTEGER PRIMARY KEY,
                trading_fee_pct REAL NOT NULL DEFAULT 0,
                deposit_ideal_fee_eur REAL NOT NULL DEFAULT 0,
                withdraw_eur_fee_eur REAL NOT NULL DEFAULT 0,
                spread_estimate_pct REAL NOT NULL DEFAULT 0,
                source_url TEXT,
                updated_at TEXT,
                FOREIGN KEY(exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS quotes (
                exchange_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                bid REAL NOT NULL,
                ask REAL NOT NULL,
                ts TEXT NOT NULL,
                FOREIGN KEY(exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_quotes_exchange_symbol_ts
            ON quotes(exchange_id, symbol, ts DESC)
            """
        )

        if _needs_fk_cascade_migration(con):
            _migrate_fk_to_cascade(con)
            print("Migration applied")
        else:
            print("No migration needed")

        con.commit()
    finally:
        con.close()


def _needs_fk_cascade_migration(con: sqlite3.Connection) -> bool:
    cur = con.cursor()
    fees_fk = cur.execute("PRAGMA foreign_key_list('fees')").fetchall()
    quotes_fk = cur.execute("PRAGMA foreign_key_list('quotes')").fetchall()

    if not fees_fk or not quotes_fk:
        return False

    fees_on_delete = str(fees_fk[0][6]).upper()
    quotes_on_delete = str(quotes_fk[0][6]).upper()
    return fees_on_delete != "CASCADE" or quotes_on_delete != "CASCADE"


def _migrate_fk_to_cascade(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("BEGIN")

        cur.execute("ALTER TABLE fees RENAME TO fees_old")
        cur.execute("ALTER TABLE quotes RENAME TO quotes_old")

        cur.execute(
            """
            CREATE TABLE fees (
                exchange_id INTEGER PRIMARY KEY,
                trading_fee_pct REAL NOT NULL DEFAULT 0,
                deposit_ideal_fee_eur REAL NOT NULL DEFAULT 0,
                withdraw_eur_fee_eur REAL NOT NULL DEFAULT 0,
                spread_estimate_pct REAL NOT NULL DEFAULT 0,
                source_url TEXT,
                updated_at TEXT,
                FOREIGN KEY(exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE quotes (
                exchange_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                bid REAL NOT NULL,
                ask REAL NOT NULL,
                ts TEXT NOT NULL,
                FOREIGN KEY(exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute(
            """
            INSERT INTO fees(
                exchange_id, trading_fee_pct, deposit_ideal_fee_eur, withdraw_eur_fee_eur,
                spread_estimate_pct, source_url, updated_at
            )
            SELECT
                exchange_id, trading_fee_pct, deposit_ideal_fee_eur, withdraw_eur_fee_eur,
                spread_estimate_pct, source_url, updated_at
            FROM fees_old
            """
        )

        cur.execute(
            """
            INSERT INTO quotes(exchange_id, symbol, bid, ask, ts)
            SELECT exchange_id, symbol, bid, ask, ts
            FROM quotes_old
            """
        )

        cur.execute("DROP TABLE fees_old")
        cur.execute("DROP TABLE quotes_old")

        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys = ON")


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_exchange_by_name(con: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    cur = con.cursor()
    cur.execute("SELECT id, name, type, website FROM exchanges WHERE name = ?", (name,))
    return cur.fetchone()


def list_exchanges(con: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = con.cursor()
    cur.execute("SELECT id, name, type, website FROM exchanges ORDER BY name")
    return cur.fetchall()


def create_exchange(
    con: sqlite3.Connection,
    name: str,
    exchange_type: str,
    website: str,
) -> int:
    clean_name = (name or "").strip()
    clean_type = (exchange_type or "").strip()
    clean_website = (website or "").strip()

    if not clean_name:
        raise ValueError("Exchange name is required.")
    if clean_type not in {"exchange", "broker"}:
        raise ValueError("Exchange type must be 'exchange' or 'broker'.")

    cur = con.cursor()
    cur.execute(
        "INSERT INTO exchanges(name, type, website) VALUES (?, ?, ?)",
        (clean_name, clean_type, clean_website),
    )
    exchange_id = int(cur.lastrowid)
    ensure_fee_row(con, exchange_id)
    con.commit()
    return exchange_id


def update_exchange(
    con: sqlite3.Connection,
    exchange_id: int,
    name: str,
    exchange_type: str,
    website: str,
) -> bool:
    clean_name = (name or "").strip()
    clean_type = (exchange_type or "").strip()
    clean_website = (website or "").strip()

    if not clean_name:
        raise ValueError("Exchange name is required.")
    if clean_type not in {"exchange", "broker"}:
        raise ValueError("Exchange type must be 'exchange' or 'broker'.")

    cur = con.cursor()
    cur.execute(
        """
        UPDATE exchanges
        SET name = ?, type = ?, website = ?
        WHERE id = ?
        """,
        (clean_name, clean_type, clean_website, int(exchange_id)),
    )
    con.commit()
    return cur.rowcount > 0


def delete_exchange(con: sqlite3.Connection, exchange_id: int) -> bool:
    cur = con.cursor()
    cur.execute("DELETE FROM exchanges WHERE id = ?", (int(exchange_id),))
    con.commit()
    return cur.rowcount > 0


def delete_exchange_cascade(con: sqlite3.Connection, exchange_id: int) -> bool:
    ex_id = int(exchange_id)
    cur = con.cursor()
    try:
        con.execute("BEGIN")
        cur.execute("DELETE FROM quotes WHERE exchange_id = ?", (ex_id,))
        cur.execute("DELETE FROM fees WHERE exchange_id = ?", (ex_id,))
        cur.execute("DELETE FROM exchanges WHERE id = ?", (ex_id,))
        deleted = cur.rowcount > 0
        con.commit()
        return deleted
    except sqlite3.Error:
        con.rollback()
        raise


def ensure_fee_row(con: sqlite3.Connection, exchange_id: int) -> None:
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO fees(
            exchange_id, trading_fee_pct, deposit_ideal_fee_eur, withdraw_eur_fee_eur,
            spread_estimate_pct, source_url, updated_at
        )
        VALUES (?, 0, 0, 0, 0, '', ?)
        """,
        (int(exchange_id), _now_utc_iso()),
    )


def get_fee_row(con: sqlite3.Connection, exchange_id: int) -> sqlite3.Row | None:
    cur = con.cursor()
    cur.execute(
        """
        SELECT trading_fee_pct, deposit_ideal_fee_eur, withdraw_eur_fee_eur,
               spread_estimate_pct, source_url, updated_at
        FROM fees
        WHERE exchange_id = ?
        """,
        (int(exchange_id),),
    )
    return cur.fetchone()


def upsert_fee_row(
    con: sqlite3.Connection,
    exchange_id: int,
    trading_fee_pct: float,
    deposit_ideal_fee_eur: float,
    withdraw_eur_fee_eur: float,
    spread_estimate_pct: float,
    source_url: str,
    updated_at: str | None = None,
) -> None:
    ts = updated_at or _now_utc_iso()
    cur = con.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO fees(
            exchange_id, trading_fee_pct, deposit_ideal_fee_eur, withdraw_eur_fee_eur,
            spread_estimate_pct, source_url, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(exchange_id),
            float(trading_fee_pct),
            float(deposit_ideal_fee_eur),
            float(withdraw_eur_fee_eur),
            float(spread_estimate_pct),
            (source_url or "").strip(),
            ts,
        ),
    )
    con.commit()


def insert_quote(
    con: sqlite3.Connection,
    exchange_id: int,
    symbol: str,
    bid: float,
    ask: float,
    ts: str | None = None,
) -> None:
    quote_ts = ts or _now_utc_iso()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO quotes(exchange_id, symbol, bid, ask, ts) VALUES (?, ?, ?, ?, ?)",
        (int(exchange_id), symbol, float(bid), float(ask), quote_ts),
    )
    con.commit()


def get_latest_quote(
    con: sqlite3.Connection,
    exchange_id: int,
    symbol: str,
) -> sqlite3.Row | None:
    cur = con.cursor()
    cur.execute(
        """
        SELECT bid, ask, ts
        FROM quotes
        WHERE exchange_id = ? AND symbol = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (int(exchange_id), symbol),
    )
    return cur.fetchone()


def list_exchange_fee_rows(con: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = con.cursor()
    cur.execute(
        """
        SELECT e.id, e.name, e.type, e.website,
               f.trading_fee_pct, f.deposit_ideal_fee_eur, f.withdraw_eur_fee_eur,
               f.spread_estimate_pct, f.source_url, f.updated_at
        FROM exchanges e
        JOIN fees f ON f.exchange_id = e.id
        ORDER BY e.name
        """
    )
    return cur.fetchall()


def seed_exchanges_and_fees(
    con: sqlite3.Connection,
    exchanges: list[tuple[str, str, str]],
    fees_by_name: dict[str, dict[str, Any]],
) -> None:
    now = _now_utc_iso()
    cur = con.cursor()

    for name, exchange_type, website in exchanges:
        cur.execute(
            "INSERT OR IGNORE INTO exchanges(name, type, website) VALUES (?, ?, ?)",
            ((name or "").strip(), (exchange_type or "").strip(), (website or "").strip()),
        )

    cur.execute("SELECT id, name FROM exchanges")
    rows = cur.fetchall()

    for row in rows:
        ex_id = int(row["id"])
        name = str(row["name"])
        fee = fees_by_name.get(
            name,
            {
                "trading_fee_pct": 0.0,
                "deposit_ideal_fee_eur": 0.0,
                "withdraw_eur_fee_eur": 0.0,
                "spread_estimate_pct": 0.0,
                "source_url": "",
            },
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO fees(
                exchange_id, trading_fee_pct, deposit_ideal_fee_eur, withdraw_eur_fee_eur,
                spread_estimate_pct, source_url, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ex_id,
                float(fee["trading_fee_pct"]),
                float(fee["deposit_ideal_fee_eur"]),
                float(fee["withdraw_eur_fee_eur"]),
                float(fee["spread_estimate_pct"]),
                str(fee.get("source_url", "") or ""),
                now,
            ),
        )

    con.commit()


def ensure_seed_data(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    row = cur.execute("SELECT COUNT(*) AS cnt FROM exchanges").fetchone()
    if row and int(row["cnt"]) > 0:
        return

    exchanges = [
        ("Bitvavo", "exchange", "https://bitvavo.com"),
        ("Coinbase", "exchange", "https://coinbase.com"),
        ("Bybit", "exchange", "https://www.bybit.com"),
        ("Kraken", "exchange", "https://www.kraken.com"),
        ("Binance", "exchange", "https://www.binance.com"),
    ]

    fees_by_name = {
        "Bitvavo": {
            "trading_fee_pct": 0.25,
            "deposit_ideal_fee_eur": 0.0,
            "withdraw_eur_fee_eur": 0.0,
            "spread_estimate_pct": 0.10,
            "source_url": "",
        },
        "Coinbase": {
            "trading_fee_pct": 0.60,
            "deposit_ideal_fee_eur": 0.0,
            "withdraw_eur_fee_eur": 0.0,
            "spread_estimate_pct": 0.80,
            "source_url": "",
        },
        "Bybit": {
            "trading_fee_pct": 0.10,
            "deposit_ideal_fee_eur": 0.0,
            "withdraw_eur_fee_eur": 0.0,
            "spread_estimate_pct": 0.20,
            "source_url": "",
        },
        "Kraken": {
            "trading_fee_pct": 0.26,
            "deposit_ideal_fee_eur": 0.0,
            "withdraw_eur_fee_eur": 0.0,
            "spread_estimate_pct": 0.20,
            "source_url": "",
        },
        "Binance": {
            "trading_fee_pct": 0.10,
            "deposit_ideal_fee_eur": 0.0,
            "withdraw_eur_fee_eur": 0.0,
            "spread_estimate_pct": 0.15,
            "source_url": "",
        },
    }

    seed_exchanges_and_fees(con, exchanges=exchanges, fees_by_name=fees_by_name)
