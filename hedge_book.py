"""
Hedged SpaceX-isolation book -> dashboard/data/hedge_book.json

A delta-1 portfolio entered 2026-05-20 (EOD): LONG BPTIX, SHORT its public
holdings (Arch, CoStar, Tesla, Hyatt, Schwab, ...) at fixed share counts, to
strip out the public book and isolate the SpaceX (+ other private) exposure
inside the fund. Two accounts; we report the TOTAL only.

P&L_t per position = shares * (close_t - close_entry).  (shares<0 for shorts)
Three daily lines: Long (BPTIX leg), Short (sum of short legs), Total.
Prices: Yahoo daily closes from entry to latest. Pure stdlib.
"""

import json
import os
import sys
import datetime
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
_UA = {"User-Agent": "Mozilla/5.0"}
ENTRY = "2026-05-20"

# Total shares (account1 + account2) from the book. Yahoo tickers (HEI/A -> HEI-A).
# Long BPTIX; everything else short (negative).
POSITIONS = {
    "BPTIX": 130000,
    "ACGL": -16369, "BIRK": -13423, "CHH": -9569, "CSGP": -27884, "FDS": -4982,
    "FIG": -4835, "GLPI": -6827, "GWRE": -6517, "H": -9022, "HEI": -483,
    "HEI-A": -450, "IDXX": -1654, "IT": -7405, "KNSL": -1417, "MSCI": -2507,
    "MTN": -6923, "ONON": -11341, "RRR": -12077, "SCHW": -15428, "SHOP": -7092,
    "SPOT": -2015, "TSLA": -16836, "VRSK": -2869,
}


# Manual NAV/price points for days Yahoo hasn't posted yet (mutual-fund NAV lags
# ~1 day). Provenance must be a real reported figure, not an estimate. Only used
# where Yahoo doesn't already have the day (setdefault). Currently empty: Yahoo has
# caught up through 6/5 (the earlier BPTIX 6/4=$279.60 manual mark now matches the
# published Yahoo close, so it's no longer needed).
MANUAL_PX = {}


def _epoch(d):
    return int(datetime.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


def _series(tk, start, end):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
         f"?period1={_epoch(start)}&period2={_epoch(end)}&interval=1d")
    j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=_UA), timeout=30).read())
    r = j["chart"]["result"][0]
    ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
    out = {}
    for t, c in zip(ts, cl):
        if c is None:
            continue
        out[datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat()] = float(c)
    return out


def build_payload():
    end = (datetime.date(2026, 6, 5) + datetime.timedelta(days=1)).isoformat()
    px = {tk: _series(tk, ENTRY, end) for tk in POSITIONS}
    # merge manual points (only where Yahoo doesn't already have the day)
    for tk, days in MANUAL_PX.items():
        for d, v in days.items():
            px.setdefault(tk, {}).setdefault(d, v)

    # trading-day calendar = dates where BPTIX has a price (the long anchor)
    dates = sorted(d for d in px["BPTIX"] if d >= ENTRY)
    entry_px = {tk: px[tk].get(ENTRY) for tk in POSITIONS}

    series = []
    last = {tk: entry_px[tk] for tk in POSITIONS}   # carry-forward for any missing day
    short_pnl_by_tk = {tk: [] for tk in POSITIONS if POSITIONS[tk] < 0}
    for d in dates:
        longp = shortp = 0.0
        for tk, sh in POSITIONS.items():
            p = px[tk].get(d, last[tk])
            last[tk] = p
            pnl = sh * (p - entry_px[tk])
            if sh > 0:
                longp += pnl
            else:
                shortp += pnl
                short_pnl_by_tk[tk].append(round(pnl, 2))
        series.append({"date": d, "long_pnl": round(longp, 2),
                       "short_pnl": round(shortp, 2), "total_pnl": round(longp + shortp, 2)})

    # per-ticker daily P&L for the SHORT legs, sorted alphabetically by display ticker
    short_legs_pnl = sorted(
        ({"ticker": tk.replace("-", "/"), "shares": POSITIONS[tk], "pnl": short_pnl_by_tk[tk]}
         for tk in short_pnl_by_tk),
        key=lambda r: r["ticker"])

    # gross notional at entry (for context / return scaling)
    long_notional = sum(sh * entry_px[tk] for tk, sh in POSITIONS.items() if sh > 0)
    short_notional = sum(-sh * entry_px[tk] for tk, sh in POSITIONS.items() if sh < 0)

    # per-name entry detail (for a small reference table)
    legs = sorted(({"ticker": tk.replace("-", "/"), "shares": sh,
                    "entry_px": round(entry_px[tk], 2),
                    "notional": round(sh * entry_px[tk], 0),
                    "side": "long" if sh > 0 else "short"}
                   for tk, sh in POSITIONS.items()),
                  key=lambda x: x["notional"])

    last_row = series[-1] if series else {}
    return {
        "meta": {
            "title": "Hedged SpaceX-isolation book — long BPTIX vs short public holdings",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_date": ENTRY,
            "disclaimer": ("Analysis, not investment advice. Delta-1 book entered " + ENTRY + " EOD: long "
                           "130,000 BPTIX, short the fund's public holdings at fixed share counts (combined "
                           "across 2 accounts) to isolate the private (SpaceX) exposure. P&L = shares × "
                           "(close − entry close), Yahoo daily closes. Two accounts shown as TOTAL only. "
                           "Excludes financing/borrow, dividends, and BPTIX's leverage/fees. Model, not a "
                           "statement of record."),
            "long_notional": round(long_notional, 0),
            "short_notional": round(short_notional, 0),
            "n_shorts": sum(1 for s in POSITIONS.values() if s < 0),
            "last_data_day": last_row.get("date"),
            "manual_marks": [{"ticker": tk, "date": d, "value": v,
                              "source": "user-provided (Baron/brokerage), pending Yahoo"}
                             for tk, days in MANUAL_PX.items() for d, v in days.items()],
        },
        "kpis": {
            "as_of": last_row.get("date"),
            "long_pnl": last_row.get("long_pnl"),
            "short_pnl": last_row.get("short_pnl"),
            "total_pnl": last_row.get("total_pnl"),
        },
        "series": series,
        "legs": legs,
        "short_legs_pnl": short_legs_pnl,
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "hedge_book.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    print(f"entry {pl['meta']['entry_date']} | long notional ${pl['meta']['long_notional']/1e6:.1f}M "
          f"| short notional ${pl['meta']['short_notional']/1e6:.1f}M | {pl['meta']['n_shorts']} shorts")
    print(f"{'date':12s} {'long':>12s} {'short':>12s} {'total':>12s}")
    for r in pl["series"]:
        print(f"{r['date']:12s} {r['long_pnl']:>12,.0f} {r['short_pnl']:>12,.0f} {r['total_pnl']:>12,.0f}")
    p = write_json()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
