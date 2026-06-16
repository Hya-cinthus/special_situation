"""
Long-horizon replication of Baron Partners Fund -> dashboard/data/long_replication.json

The daily recalibration has only ~16 daily observations -> too few to pin the
public weights. This study fixes that by going back ~3 years (2023-01 -> now) and
using the fact that EVERY quarter's NPORT-P tells us the EXACT share count of each
public holding. So between filings we don't guess weights at all -- we hold shares
constant and let real daily prices move the book:

    public_book_t = sum_i  shares_i,q * price_i,t          (q = governing quarter)
    r_public,t    = public_book_t / public_book_{t-1} - 1

The fund's per-share NAV total return (nav_adj) then decomposes as

    r_NAV,t  =  wP_q * r_public,t  +  (SpaceX contribution)  -  financing

with wP_q = public book value / net assets straight from the filing (so it already
carries the fund's leverage). We predict the PUBLIC-ONLY part and read the residual:

  * between SpaceX mark events the residual is small & slowly-drifting (= financing
    + the tiny held-flat 'other' bucket) -> this VALIDATES the whole approach;
  * at SpaceX mark events (tenders, the IPO) the residual spikes -> that spike IS
    the SpaceX re-mark, measured independently of any model;
  * the widening gap between cumulative actual NAV and cumulative public-only NAV is
    SpaceX's cumulative contribution over the 3 years.

With ~750 daily observations and KNOWN quarterly shares the degrees-of-freedom
problem dissolves. Coverage: the ~20 liquid names below cover ~95% of the public
book; the small private / delisted / foreign tail (xAI, StubHub, Northvolt, Velo3D)
is bucketed as 'other' and held flat (labelled, conservative).

Prices are fetched ONCE by refresh_prices() and cached to data/raw (committed), so
build_payload() is network-free (the CI auto-rebuild never fetches). Pure stdlib.
"""

import csv
import glob
import json
import os
import re
import time
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
_RAW_EDGAR = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "raw", "edgar")
_NAV_CSV = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "processed", "nav_daily.csv")
# NOTE: lives in data/ (tracked), NOT data/raw/ (gitignored) -> the cache commits so
# the CI rebuild stays network-free instead of shipping a blank card.
_PRICE_CACHE = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "replication_prices.json")
_OUT = os.path.join(_REPO_ROOT, "dashboard", "data", "long_replication.json")

START = "2023-01-01"          # study window start
QUARTER_FLOOR = "2022-12-31"  # first NPORT that governs Jan-2023

SERIES_ID = "S000000588"

# name substring (lower) -> Yahoo ticker. Covers ~95% of the public book.
NAME_TICKER = [
    ("tesla", "TSLA"), ("costar", "CSGP"), ("arch capital", "ACGL"), ("hyatt", "H"),
    ("charles schwab", "SCHW"), ("idexx", "IDXX"), ("factset", "FDS"), ("gartner", "IT"),
    ("vail resorts", "MTN"), ("msci", "MSCI"), ("iridium", "IRDM"), ("guidewire", "GWRE"),
    ("choice hotels", "CHH"), ("spotify", "SPOT"), ("shopify", "SHOP"),
    ("gaming and leisure", "GLPI"), ("marriott vacations", "VAC"), ("red rock resorts", "RRR"),
    ("adyen", "ADYEY"), ("birkenstock", "BIRK"), ("verisk", "VRSK"), ("kinsale", "KNSL"),
    ("figs", "FIGS"), ("on holding", "ONON"), ("steers", "CNS"), ("moderna", "MRNA"),
    ("brookfield corp", "BN"), ("brookfield asset management", "BAM"), ("heico", "HEI"),
    ("nvidia", "NVDA"), ("douglas emmett", "DEI"), ("krispy kreme", "DNUT"), ("figma", "FIG"),
    ("illumina", "ILMN"), ("airbnb", "ABNB"),
]
SPACEX_NEEDLE = "space exploration"
CASH_NEEDLES = ("fixed income clearing", "fixed inc clearing")

# Known SpaceX whole-company mark steps in-window (for event lines on the chart).
SPACEX_EVENTS = [
    ("2024-12-10", "Tender ~$350B"), ("2025-07-01", "Secondary ~$400B"),
    ("2025-12-13", "Secondary ~$800B"), ("2026-02-02", "SpaceX+xAI $1.25T"),
    ("2026-06-04", "IPO repriced $135"), ("2026-06-12", "First trade SPCX $160.95"),
]


def _tag(x, n):
    m = re.search(rf"<{n}>(.*?)</{n}>", x, re.S)
    return m.group(1).strip() if m else None


def _ticker_for(name):
    n = name.lower()
    for needle, tk in NAME_TICKER:
        if needle in n:
            return tk
    return None


def parse_quarters():
    """Full public holdings per quarter (>= 2022-12-31) from cached NPORT XMLs."""
    qs = {}
    for p in glob.glob(os.path.join(_RAW_EDGAR, "*.xml")):
        x = open(p, encoding="utf-8", errors="replace").read()
        if _tag(x, "seriesId") != SERIES_ID:
            continue
        rd = _tag(x, "repPdDate")
        if not rd or rd < QUARTER_FLOOR:
            continue
        net = float(_tag(x, "netAssets") or 0)
        tot = float(_tag(x, "totAssets") or 0)
        shares, mapped_val, other_val, cash_val, spx_val = {}, 0.0, 0.0, 0.0, 0.0
        for blk in re.findall(r"<invstOrSec>.*?</invstOrSec>", x, re.S):
            name = (_tag(blk, "name") or "")
            low = name.lower()
            val = float(_tag(blk, "valUSD") or 0)
            bal = float(_tag(blk, "balance") or 0)
            if any(c in low for c in CASH_NEEDLES):
                cash_val += val
                continue
            if SPACEX_NEEDLE in low:
                spx_val += val
                continue
            tk = _ticker_for(name)
            if tk:
                shares[tk] = shares.get(tk, 0.0) + bal
                mapped_val += val
            else:
                other_val += val   # private/delisted/foreign tail -> held flat
        pub_val = mapped_val + other_val
        qs[rd] = {"report_date": rd, "net_assets": net, "total_assets": tot,
                  "shares": shares, "mapped_value": mapped_val, "other_value": other_val,
                  "cash_value": cash_val, "spacex_value": spx_val, "public_value": pub_val,
                  "coverage_pct": round(mapped_val / pub_val * 100, 1) if pub_val else 0.0,
                  "leverage": round(tot / net, 4) if net else None,
                  "wP_pct": round(pub_val / net * 100, 2) if net else None,
                  "wS_pct": round(spx_val / net * 100, 2) if net else None}
    return [qs[k] for k in sorted(qs)]


# --------------------------- price fetch (run once) ------------------------
def _yahoo(ticker, p1, p2):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        j = json.loads(r.read())
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]["close"]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", q)
    out = {}
    for i, t in enumerate(ts):
        v = adj[i] if adj and adj[i] is not None else q[i]
        if v is not None:
            out[time.strftime("%Y-%m-%d", time.gmtime(t))] = round(float(v), 4)
    return out


def refresh_prices(verbose=True):
    """Fetch adjusted daily closes for the whole holdings universe -> cache JSON.
    Run manually (network); build_payload() then reads the cache offline."""
    tickers = sorted({tk for q in parse_quarters() for tk in q["shares"]})
    p1 = int(time.mktime(time.strptime("2022-12-01", "%Y-%m-%d")))
    p2 = int(time.time())
    prices = {}
    for tk in tickers:
        try:
            prices[tk] = _yahoo(tk, p1, p2)
            if verbose:
                print(f"  {tk}: {len(prices[tk])} days")
        except Exception as e:
            if verbose:
                print(f"  ! {tk} FAILED: {e}")
            prices[tk] = {}
        time.sleep(0.3)
    os.makedirs(os.path.dirname(_PRICE_CACHE), exist_ok=True)
    with open(_PRICE_CACHE, "w", encoding="utf-8") as f:
        json.dump({"as_of": time.strftime("%Y-%m-%d"), "tickers": tickers, "prices": prices},
                  f, separators=(",", ":"))
    return _PRICE_CACHE


def _load_prices():
    if not os.path.exists(_PRICE_CACHE):
        return None
    return json.load(open(_PRICE_CACHE, encoding="utf-8"))["prices"]


def _load_nav():
    nav = {}
    with open(_NAV_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            v = row.get("nav_adj") or row.get("nav")
            if v:
                nav[row["date"]] = float(v)
    return nav


# ------------------------------ reconstruction -----------------------------
def build_payload():
    prices = _load_prices()
    if not prices:
        return None
    quarters = parse_quarters()
    nav = _load_nav()
    qdates = [q["report_date"] for q in quarters]

    def gov_quarter(d):
        g = None
        for q in quarters:
            if q["report_date"] <= d:
                g = q
            else:
                break
        return g

    # public book value on a given day for a given quarter's shares (+ flat other)
    def book(q, d):
        tot = q["other_value"]
        used = 0
        for tk, sh in q["shares"].items():
            px = prices.get(tk, {}).get(d)
            if px is not None:
                tot += sh * px
                used += 1
        return tot, used

    dates = sorted(d for d in nav if d >= START and any(d in prices.get(tk, {}) for tk in prices))
    series = []
    cum_act = cum_pub = 100.0
    prev = None
    for d in dates:
        q = gov_quarter(d)
        if not q or d not in nav:
            continue
        if prev is None or prev not in nav:
            prev = d
            continue
        # both legs priced off the SAME quarter's shares
        pv_t, _ = book(q, d)
        pv_p, _ = book(q, prev)
        if pv_p <= 0:
            prev = d
            continue
        r_pub = pv_t / pv_p - 1
        wP = (q["wP_pct"] or 0) / 100.0
        pred_pub = wP * r_pub
        r_act = nav[d] / nav[prev] - 1
        resid = r_act - pred_pub
        cum_act *= (1 + r_act)
        cum_pub *= (1 + pred_pub)
        series.append({"date": d, "r_pub_pct": round(r_pub * 100, 3),
                       "r_nav_pct": round(r_act * 100, 3), "pred_pub_pct": round(pred_pub * 100, 3),
                       "resid_pct": round(resid * 100, 3), "cum_actual": round(cum_act, 3),
                       "cum_public": round(cum_pub, 3), "wP_pct": q["wP_pct"], "q": q["report_date"]})
        prev = d

    # stats: residual = SpaceX contribution + financing. Split by whether a SpaceX
    # mark event fell in the (prev, d] window.
    evset = {e[0] for e in SPACEX_EVENTS}
    quiet = [s["resid_pct"] for s in series if s["date"] not in evset]
    mean_q = sum(quiet) / len(quiet) if quiet else 0.0
    sd_q = (sum((r - mean_q) ** 2 for r in quiet) / (len(quiet) - 1)) ** 0.5 if len(quiet) > 1 else 0.0
    cum_resid_pct = round((series[-1]["cum_actual"] / series[-1]["cum_public"] - 1) * 100, 1) if series else 0.0

    return {
        "meta": {
            "title": "Long-horizon replication — public book (known NPORT shares) vs NAV",
            "window": [series[0]["date"] if series else START, series[-1]["date"] if series else START],
            "n_days": len(series), "n_quarters": len(quarters),
            "tickers": sorted({tk for q in quarters for tk in q["shares"]}),
            "method": ("Public book = sum(NPORT shares_q * adj close_t), shares held constant within each "
                       "quarter (Baron rarely trades); predicted NAV return = wP_q * public return, wP_q = "
                       "public value / net assets from the filing (carries leverage). Residual = actual NAV "
                       "return - public-only prediction = SpaceX contribution + financing + flat 'other'."),
            "coverage_note": ("~20 liquid names cover ~95% of the public book; the small private/delisted/"
                              "foreign tail is bucketed as 'other' and held flat (conservative, labelled)."),
            "price_basis": "Yahoo adjusted close (total-return) vs the fund's nav_adj (total-return NAV).",
            "disclaimer": "Estimate. Quarter-constant weights; 'other' held flat; financing not separately sourced.",
        },
        "quarters": [{k: q[k] for k in ("report_date", "net_assets", "total_assets", "leverage",
                                        "wP_pct", "wS_pct", "coverage_pct", "spacex_value")} for q in quarters],
        "events": [{"date": d, "label": l} for d, l in SPACEX_EVENTS if (not series) or series[0]["date"] <= d <= series[-1]["date"]],
        "series": series,
        "stats": {"cum_actual_idx": series[-1]["cum_actual"] if series else None,
                  "cum_public_idx": series[-1]["cum_public"] if series else None,
                  "cum_spacex_plus_fin_pct": cum_resid_pct,
                  "quiet_resid_mean_bps": round(mean_q * 100, 2),
                  "quiet_resid_sd_bps": round(sd_q * 100, 2),
                  "spacex_wt_start_pct": quarters[0]["wS_pct"] if quarters else None,
                  "spacex_wt_end_pct": quarters[-1]["wS_pct"] if quarters else None},
    }


def write_json():
    payload = build_payload()
    if payload is None:
        raise RuntimeError("no price cache; run `py long_replication.py --refresh` first")
    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return _OUT


if __name__ == "__main__":
    import sys
    if "--refresh" in sys.argv:
        print("Fetching prices...")
        print("cached ->", refresh_prices())
    pl = build_payload()
    if pl is None:
        print("No price cache yet. Run: py long_replication.py --refresh")
        raise SystemExit(0)
    m, st = pl["meta"], pl["stats"]
    print(m["title"])
    print("window", m["window"], "days", m["n_days"], "quarters", m["n_quarters"])
    print("tickers (%d):" % len(m["tickers"]), " ".join(m["tickers"]))
    print("SpaceX weight %.1f%% -> %.1f%% (net)" % (st["spacex_wt_start_pct"], st["spacex_wt_end_pct"]))
    print("cum NAV idx %.1f vs public-only %.1f -> SpaceX+fin gap %.1f%%"
          % (st["cum_actual_idx"], st["cum_public_idx"], st["cum_spacex_plus_fin_pct"]))
    print("quiet-day residual mean %.2f bps/day sd %.2f bps" % (st["quiet_resid_mean_bps"], st["quiet_resid_sd_bps"]))
    print("wrote", write_json())
