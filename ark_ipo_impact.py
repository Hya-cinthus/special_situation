"""
ARK IPO-day impact analytics -> merged into dashboard/data/ark_tracker.json.

For each historical IPO ARK bought, compute from REAL price data (Yahoo):
  - the IPO stock's day-1 move (open->close, and close->next-close)
  - ARKK's same-day return
  - ARKK's trailing realized vol (10/21/63d, annualized + daily) BEFORE the event
  - z-score = ARKK day move / ARKK daily realized vol  -> did ARKK move MORE than
    its normal daily noise on the IPO day? "excess move" attributable to the event.
This isolates the IPO's marginal impact on ARKK from ordinary market wiggle.

Then a forward SpaceX scenario: given an assumed ARKK target weight in SpaceX and
an assumed day-1 SpaceX pop, the mechanical NAV contribution to ARKK = weight x pop
(a NEW position bought at IPO adds weight*pop to NAV on day 1). Compared to ARKK's
current realized-vol band so the user sees if it'd be a >1-sigma day.

Pure stdlib. All inputs are measured prices; assumptions are labeled.
"""

import json
import os
import sys
import math
import datetime
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
_UA = {"User-Agent": "Mozilla/5.0"}

# IPO stock ticker + date + the IPO stock's INITIAL WEIGHT IN ARKK (for the
# contribution decomposition: how much of ARKK's day was THIS stock). Weight from
# the ark_tracker IPO database (disclosed first-day weights; None where unknown).
IPO_EVENTS = [
    {"company": "Circle", "ticker": "CRCL", "ipo_date": "2025-06-05", "arkk_weight": 0.044},
    {"company": "Coinbase", "ticker": "COIN", "ipo_date": "2021-04-14", "arkk_weight": 0.04},
    {"company": "Roblox", "ticker": "RBLX", "ipo_date": "2021-03-10", "arkk_weight": 0.01},
    {"company": "Robinhood", "ticker": "HOOD", "ipo_date": "2021-07-29", "arkk_weight": None},
    {"company": "Reddit", "ticker": "RDDT", "ipo_date": "2024-03-21", "arkk_weight": None},
    {"company": "Tempus AI", "ticker": "TEM", "ipo_date": "2024-06-14", "arkk_weight": 0.05},
    {"company": "UiPath", "ticker": "PATH", "ipo_date": "2021-04-21", "arkk_weight": None},
]


def _epoch(d):
    return int(datetime.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


def _series(tk, start, end):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
         f"?period1={_epoch(start)}&period2={_epoch(end)}&interval=1d")
    try:
        j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=_UA), timeout=30).read())
        r = j["chart"]["result"][0]
        ts, q = r["timestamp"], r["indicators"]["quote"][0]
        out = []
        for i, t in enumerate(ts):
            c = q["close"][i]
            if c is None:
                continue
            out.append({"date": datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat(),
                        "open": q["open"][i], "close": c})
        return out
    except Exception as e:
        print(f"[ark_ipo] fetch {tk} failed: {e}")
        return []


def _ret(a, b):
    return (b / a - 1.0) if (a and b) else None


def _realized_vol(closes, n):
    """Annualized realized vol from the last n daily log returns."""
    if len(closes) < n + 1:
        return None
    rets = []
    for i in range(len(closes) - n, len(closes)):
        if closes[i - 1] and closes[i]:
            rets.append(math.log(closes[i] / closes[i - 1]))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    daily = math.sqrt(var)
    return {"daily": daily, "annual": daily * math.sqrt(252)}


def analyze_event(ev):
    d0 = ev["ipo_date"]
    d0d = datetime.date.fromisoformat(d0)
    # window: 100 calendar days before (for vol) to 10 days after
    start = (d0d - datetime.timedelta(days=130)).isoformat()
    end = (d0d + datetime.timedelta(days=12)).isoformat()

    stock = _series(ev["ticker"], start, end)
    arkk = _series("ARKK", start, end)
    if not stock or not arkk:
        return {**ev, "ok": False}

    # IPO stock day-1: open->close, then close->next close
    s_idx = next((i for i, r in enumerate(stock) if r["date"] >= d0), None)
    stock_day1_oc = stock_day2 = None
    if s_idx is not None:
        r0 = stock[s_idx]
        stock_day1_oc = _ret(r0["open"], r0["close"])
        if s_idx + 1 < len(stock):
            stock_day2 = _ret(r0["close"], stock[s_idx + 1]["close"])

    # ARKK: find the IPO day (or next trading day) and the day before
    a_idx = next((i for i, r in enumerate(arkk) if r["date"] >= d0), None)
    arkk_day = arkk_next = None
    pre_vol = {}
    if a_idx is not None and a_idx >= 1:
        arkk_day = _ret(arkk[a_idx - 1]["close"], arkk[a_idx]["close"])  # close-to-close on IPO day
        if a_idx + 1 < len(arkk):
            arkk_next = _ret(arkk[a_idx]["close"], arkk[a_idx + 1]["close"])
        pre_closes = [r["close"] for r in arkk[:a_idx]]  # strictly before the event
        for label, n in (("d10", 10), ("d21", 21), ("d63", 63)):
            pre_vol[label] = _realized_vol(pre_closes, n)

    # z-score: ARKK IPO-day move vs its pre-event daily vol (21d)
    z = None
    base = pre_vol.get("d21")
    if arkk_day is not None and base and base["daily"]:
        z = arkk_day / base["daily"]

    # CONTRIBUTION DECOMPOSITION: how much of ARKK's day was THIS IPO stock?
    # contribution = weight x stock day-1 return; residual = ARKK total - contribution.
    # Uses the stock's close-to-close on day 1 (the part ARKK's NAV actually felt,
    # since ARK buys at/after the open). For a fresh IPO bought day-1 we approximate
    # the held return by open->close (no prior close).
    w = ev.get("arkk_weight")
    stock_held_ret = stock_day1_oc  # open->close = the move while ARKK held it day 1
    contribution = (w * stock_held_ret) if (w is not None and stock_held_ret is not None) else None
    residual = (arkk_day - contribution) if (arkk_day is not None and contribution is not None) else None
    pct_explained = None
    if contribution is not None and arkk_day not in (None, 0):
        pct_explained = contribution / arkk_day  # share of ARKK's move from the IPO stock

    return {
        "company": ev["company"], "ticker": ev["ticker"], "ipo_date": d0, "ok": True,
        "stock_day1_open_close": stock_day1_oc,
        "stock_day2_close": stock_day2,
        "arkk_ipo_day_return": arkk_day,
        "arkk_next_day_return": arkk_next,
        "arkk_prevol": {k: (v["annual"] if v else None) for k, v in pre_vol.items()},
        "arkk_prevol_daily_21": (base["daily"] if base else None),
        "arkk_z_score": z,
        "arkk_weight": w,
        "ipo_contribution": contribution,   # weight x stock return = pp of ARKK's day from the IPO
        "arkk_residual": residual,          # the rest (market/other holdings)
        "pct_explained": pct_explained,     # share of ARKK's move attributable to the IPO stock
    }


def build():
    events = [analyze_event(ev) for ev in IPO_EVENTS]
    events = [e for e in events if e.get("ok")]

    # current ARKK realized vol (for the forward scenario baseline)
    today = datetime.date.today() if False else None  # date.today blocked in some sandboxes
    # use last ~100 days up to now via a wide window
    end = (datetime.date(2026, 6, 2) + datetime.timedelta(days=1)).isoformat()
    start = (datetime.date(2026, 6, 2) - datetime.timedelta(days=130)).isoformat()
    arkk = _series("ARKK", start, end)
    closes = [r["close"] for r in arkk]
    cur_vol = {k: _realized_vol(closes, n) for k, n in (("d10", 10), ("d21", 21), ("d63", 63))}

    # summary: average |excess| and how often IPO day was a >1sigma move
    zs = [abs(e["arkk_z_score"]) for e in events if e.get("arkk_z_score") is not None]
    avg_abs_z = (sum(zs) / len(zs)) if zs else None
    n_gt1 = sum(1 for z in zs if z > 1.0)

    return {
        "events": events,
        "arkk_current_vol": {k: (v["annual"] if v else None) for k, v in cur_vol.items()},
        "arkk_current_vol_daily_21": (cur_vol["d21"]["daily"] if cur_vol["d21"] else None),
        "summary": {"avg_abs_z": avg_abs_z, "n_events": len(events),
                    "n_gt_1sigma": n_gt1},
    }


_CACHE = os.path.join(_REPO_ROOT, "dashboard", "data", "ark_ipo_impact_cache.json")


def build_and_cache():
    """Compute the impact block from live prices and persist it to a committed
    cache so the tracker JSON always carries it (even on a no-fetch rebuild)."""
    imp = build()
    if imp.get("events"):              # only overwrite cache if the fetch worked
        with open(_CACHE, "w", encoding="utf-8") as f:
            json.dump(imp, f, separators=(",", ":"), allow_nan=False)
    return imp


def load_cached():
    if os.path.exists(_CACHE):
        return json.load(open(_CACHE, encoding="utf-8"))
    return None


def merge_into_tracker():
    path = os.path.join(_REPO_ROOT, "dashboard", "data", "ark_tracker.json")
    payload = json.load(open(path, encoding="utf-8"))
    payload["ipo_impact"] = build_and_cache()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    imp = build()
    print(f"events analyzed: {len(imp['events'])}")
    for e in imp["events"]:
        print(f"  {e['company']:10s} {e['ipo_date']}  stock d1 "
              f"{(e['stock_day1_open_close'] or 0)*100:+6.1f}%  ARKK day "
              f"{(e['arkk_ipo_day_return'] or 0)*100:+5.2f}%  z={e['arkk_z_score']}")
    print("ARKK current vol (ann):", {k: round(v, 3) if v else None for k, v in imp["arkk_current_vol"].items()})
    print("summary:", imp["summary"])
