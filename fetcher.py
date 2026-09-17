import datetime as dt
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

from db import get_conn, init_db

load_dotenv()

API_KEY = os.environ.get("TWELVEDATA_API_KEY")
BASE_URL = "https://api.twelvedata.com/time_series"
MAX_BARS = 5000  # Twelve Data's per-request ceiling
RATE_LIMIT_WAIT = 61  # free tier allows 8 requests a minute


def fetch_range(symbol: str, start: str, end: str) -> list:
    """Daily bars for `symbol` between two YYYY-MM-DD dates, inclusive. Empty list if none."""
    if not API_KEY:
        raise RuntimeError("TWELVEDATA_API_KEY not set in environment (.env)")
    # Twelve Data reads a date-only end_date as midnight at the start of that day,
    # which drops the last bar. Ask for one day more and trim.
    end_exclusive = (dt.date.fromisoformat(end) + dt.timedelta(days=1)).isoformat()
    params = {
        "symbol": symbol,
        "interval": "1day",
        "start_date": start,
        "end_date": end_exclusive,
        "outputsize": MAX_BARS,
        "apikey": API_KEY,
        "format": "JSON",
    }
    for attempt in range(2):
        try:
            r = requests.get(BASE_URL, params=params, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"{symbol}: could not reach Twelve Data ({type(e).__name__})")
        if r.status_code == 404:
            raise RuntimeError(f"{symbol}: symbol not found")
        if r.status_code >= 400:
            # Never include r.url: it carries the API key.
            raise RuntimeError(f"{symbol}: Twelve Data returned HTTP {r.status_code}")
        data = r.json()
        if data.get("status") == "ok":
            return [v for v in data["values"] if start <= v["datetime"][:10] <= end]
        if data.get("code") == 429 and attempt == 0:
            print(f"  Rate limited, waiting {RATE_LIMIT_WAIT}s...")
            time.sleep(RATE_LIMIT_WAIT)
            continue
        if data.get("code") == 400 and "no data" in str(data.get("message", "")).lower():
            return []
        raise RuntimeError(f"{symbol}: Twelve Data error {data.get('code')}: {data.get('message', 'unknown')}")
    raise RuntimeError(f"{symbol}: still rate limited after retry")


def store_prices(symbol: str, values: list) -> None:
    rows = [
        (
            symbol,
            v["datetime"],
            float(v["open"]),
            float(v["high"]),
            float(v["low"]),
            float(v["close"]),
            int(float(v.get("volume", 0))),  # forex bars have no volume
        )
        for v in values
    ]
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def coverage(symbol: str) -> Optional[tuple[str, str]]:
    """The (start, end) calendar range already requested for `symbol`, or None if never fetched."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT start_date, end_date FROM coverage WHERE symbol = ?", (symbol,)
        ).fetchone()
    return (row["start_date"], row["end_date"]) if row else None


def _set_coverage(symbol: str, start: str, end: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO coverage (symbol, start_date, end_date) VALUES (?, ?, ?)",
            (symbol, start, end),
        )


def missing_ranges(symbol: str, start: str, end: str) -> list[tuple[str, str]]:
    """Sub-ranges of [start, end] not yet covered for `symbol`. Empty if fully cached."""
    have = coverage(symbol)
    if have is None:
        return [(start, end)]
    have_start, have_end = have
    gaps = []
    if start < have_start:
        gaps.append((start, have_start))
    if end > have_end:
        gaps.append((have_end, end))
    return gaps


def fetch_gap(symbol: str, gap_start: str, gap_end: str) -> int:
    """Fetch one missing range into the cache and extend the symbol's coverage. Returns bars stored."""
    values = fetch_range(symbol, gap_start, gap_end)
    store_prices(symbol, values)
    have = coverage(symbol)
    new_start = min(gap_start, have[0]) if have else gap_start
    new_end = max(gap_end, have[1]) if have else gap_end
    _set_coverage(symbol, new_start, new_end)
    return len(values)


def ensure_prices(symbols: list, start: str, end: str, throttle_sec: float = 0.5) -> None:
    """Make sure the cache holds every bar for each symbol in [start, end], fetching only the gaps."""
    init_db()
    requests_made = 0
    for symbol in symbols:
        for gap_start, gap_end in missing_ranges(symbol, start, end):
            if requests_made:
                time.sleep(throttle_sec)
            print(f"Fetching {symbol} {gap_start} -> {gap_end}...")
            n = fetch_gap(symbol, gap_start, gap_end)
            requests_made += 1
            print(f"  Stored {n} bars")
    if not requests_made:
        print(f"Cache: all symbols already cover {start} -> {end}, skipping fetch.")


def load_prices(symbol: str, start: Optional[str] = None, end: Optional[str] = None) -> list:
    """[(date, close), ...] oldest first, restricted to [start, end] when given."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT date, close FROM prices
            WHERE symbol = ? AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)
            ORDER BY date ASC
            """,
            (symbol, start, start, end, end),
        ).fetchall()
    return [(r["date"], r["close"]) for r in rows]
