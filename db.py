import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "stock.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                symbol TEXT NOT NULL,
                date   TEXT NOT NULL,
                open   REAL NOT NULL,
                high   REAL NOT NULL,
                low    REAL NOT NULL,
                close  REAL NOT NULL,
                volume INTEGER NOT NULL,
                PRIMARY KEY (symbol, date)
            )
        """)
        # The calendar range we have *asked the API for* per symbol. This is what
        # decides whether a fetch is needed; it can't be inferred from the bars
        # themselves because weekends and holidays have no bar.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coverage (
                symbol     TEXT PRIMARY KEY,
                start_date TEXT NOT NULL,
                end_date   TEXT NOT NULL
            )
        """)
