import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from collectors import get_collector, get_supported_exchange_names
from db import connect


def main() -> None:
    con = connect()
    cur = con.cursor()

    try:
        supported_names = get_supported_exchange_names()
        if not supported_names:
            print("No supported collectors configured.")
            return

        placeholders = ",".join(["?"] * len(supported_names))
        cur.execute(
            f"SELECT id, name FROM exchanges WHERE name IN ({placeholders}) ORDER BY name",
            supported_names,
        )
        exchanges = cur.fetchall()

        for row in exchanges:
            exchange_id = int(row["id"])
            exchange_name = str(row["name"])

            try:
                collector = get_collector(exchange_name)
            except ValueError:
                print(f"SKIP {exchange_name} (no collector)")
                continue

            try:
                bid, ask = collector.fetch_top_of_book("BTC-EUR")
                ts = datetime.now(UTC).isoformat()
                cur.execute(
                    "INSERT INTO quotes(exchange_id, symbol, bid, ask, ts) VALUES (?, ?, ?, ?, ?)",
                    (exchange_id, "BTC-EUR", float(bid), float(ask), ts),
                )
                print(f"OK {exchange_name} bid={float(bid)} ask={float(ask)} ts={ts}")
            except ValueError as exc:
                print(f"SKIP {exchange_name} ({exc})")
            except Exception as exc:
                print(f"ERR {exchange_name} {exc}")

        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    main()
