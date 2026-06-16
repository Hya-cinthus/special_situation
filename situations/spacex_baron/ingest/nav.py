"""
Daily NAV ingestion — BPTIX from the Yahoo Finance chart API.

Yahoo's chart endpoint needs no API key (Stooq now gates CSV downloads behind
one). For a mutual fund, the daily "close" IS the NAV per share. We pull the
full window from config and cache it to data/raw/.

Daily NAV/share is `measured` / `high` confidence. (Shares-outstanding and thus
total AUM are NOT free daily — that gap is handled in the engine; see
data_gaps.md item #2.)
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import SpacexBaron as CFG  # noqa: E402

_RAW_DIR = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "raw")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "processed")


def _epoch(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def fetch_nav(ticker: str | None = None, start: str | None = None) -> list[dict]:
    ticker = ticker or CFG.NAV_TICKER
    start = start or CFG.WINDOW_START
    p1 = _epoch(start)
    p2 = int(time.time()) + 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=45).read()

    os.makedirs(_RAW_DIR, exist_ok=True)
    with open(os.path.join(_RAW_DIR, f"nav_{ticker}.json"), "wb") as f:
        f.write(raw)

    j = json.loads(raw)
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    # Prefer adjusted close where present (handles distributions); fall back to close.
    adj = res.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose")
    out = []
    for i, t in enumerate(ts):
        c = closes[i]
        if c is None:
            continue
        out.append({
            "date": datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
            "nav": round(float(c), 4),
            "nav_adj": round(float(adj[i]), 4) if adj and adj[i] is not None else None,
        })
    out.sort(key=lambda r: r["date"])
    return out


def write_nav_csv(rows: list[dict]) -> str:
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "nav_daily.csv")
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "nav", "nav_adj"])
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":
    rows = fetch_nav()
    path = write_nav_csv(rows)
    print(f"Wrote {len(rows)} daily NAV rows ({rows[0]['date']} .. {rows[-1]['date']}) -> {path}")
    print(f"NAV on entry {CFG.ENTRY_DATE}: "
          f"{next((r['nav'] for r in rows if r['date'] == CFG.ENTRY_DATE), 'n/a')}")
