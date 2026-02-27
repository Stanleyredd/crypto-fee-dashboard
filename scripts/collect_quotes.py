import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from datetime import datetime
from db import connect
from collectors.bitvavo import fetch_bitvavo_top_of_book

def main():
    con = connect()
    cur = con.cursor()

    cur.execute("SELECT id FROM exchanges WHERE name = ?", ("Bitvavo",))
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Bitvavo not found. Run scripts/init_db.py first.")
    bitvavo_id = row[0]

    symbol = "BTC-EUR"
    bid, ask = fetch_bitvavo_top_of_book(symbol)
    ts = datetime.utcnow().isoformat()

    cur.execute(
        "INSERT INTO quotes(exchange_id, symbol, bid, ask, ts) VALUES (?, ?, ?, ?, ?)",
        (bitvavo_id, symbol, bid, ask, ts)
    )
    con.commit()
    con.close()
    print("Quote saved:", symbol, bid, ask, ts)

if __name__ == "__main__":
    main()
