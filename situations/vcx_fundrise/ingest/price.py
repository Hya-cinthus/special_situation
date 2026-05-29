"""
Daily VCX market price from the Yahoo Finance chart API (no key).

VCX is a NYSE-listed closed-end fund, so its market price is what you actually
pay — distinct from NAV (the value of the underlying holdings). The whole thesis
is the gap between the two. Price is `measured` / high confidence.
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import VcxFundrise as CFG  # noqa: E402

_RAW = os.path.join(_REPO_ROOT, "situations", "vcx_fundrise", "data", "raw")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "vcx_fundrise", "data", "processed")


def _epoch(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def fetch_price(ticker: str | None = None, start: str | None = None) -> list[dict]:
    ticker = ticker or CFG.PRICE_TICKER
    start = start or CFG.WINDOW_START
    p1 = _epoch(start)
    p2 = int(time.time()) + 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={p1}&period2={p2}&interval=1d")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=45).read()
    os.makedirs(_RAW, exist_ok=True)
    with open(os.path.join(_RAW, f"price_{ticker}.json"), "wb") as f:
        f.write(raw)
    res = json.loads(raw)["chart"]["result"][0]
    ts, q = res["timestamp"], res["indicators"]["quote"][0]["close"]
    out = []
    for i, t in enumerate(ts):
        if q[i] is None:
            continue
        out.append({"date": datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(),
                    "price": round(float(q[i]), 4)})
    out.sort(key=lambda r: r["date"])
    return out


def write_price_csv(rows: list[dict]) -> str:
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "price_daily.csv")
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "price"])
        w.writeheader()
        w.writerows(rows)
    return path


if __name__ == "__main__":
    rows = fetch_price()
    path = write_price_csv(rows)
    print(f"Wrote {len(rows)} VCX price rows ({rows[0]['date']}..{rows[-1]['date']}) -> {path}")
    print(f"latest price: ${rows[-1]['price']}")
