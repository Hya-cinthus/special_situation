"""Daily RVI market price from Yahoo (no key). Closed-end fund; price != NAV."""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import RviRobinhood as CFG  # noqa: E402

_RAW = os.path.join(_REPO_ROOT, "situations", "rvi_robinhood", "data", "raw")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "rvi_robinhood", "data", "processed")


def _epoch(d): return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def fetch_price(ticker=None, start=None):
    ticker = ticker or CFG.PRICE_TICKER
    start = start or CFG.WINDOW_START
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d"
           % (ticker, _epoch(start), int(time.time()) + 86400))
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=45).read()
    os.makedirs(_RAW, exist_ok=True)
    open(os.path.join(_RAW, "price_%s.json" % ticker), "wb").write(raw)
    res = json.loads(raw)["chart"]["result"][0]
    ts, q = res["timestamp"], res["indicators"]["quote"][0]["close"]
    out = [{"date": datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(), "price": round(float(q[i]), 4)}
           for i, t in enumerate(ts) if q[i] is not None]
    out.sort(key=lambda r: r["date"])
    return out


def write_price_csv(rows):
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "price_daily.csv")
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "price"]); w.writeheader(); w.writerows(rows)
    return path


if __name__ == "__main__":
    rows = fetch_price(); print("wrote", write_price_csv(rows), "|", len(rows), "rows, latest $%.2f" % rows[-1]["price"])
