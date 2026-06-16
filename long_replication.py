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

from config import SpacexBaron as CFG

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
        shares, mapped_val, other_val, cash_val, spx_val, spx_bal = {}, 0.0, 0.0, 0.0, 0.0, 0.0
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
                spx_bal += bal
                continue
            tk = _ticker_for(name)
            if tk:
                shares[tk] = shares.get(tk, 0.0) + bal
                mapped_val += val
            else:
                other_val += val   # private/delisted/foreign tail -> held flat
        pub_val = mapped_val + other_val
        # blended per-share SpaceX mark (USD); all in-window quarters are PRE the
        # 2026-05-04 5-for-1 split, so they are mutually comparable. /5 -> post-split.
        mark = (spx_val / spx_bal) if spx_bal else None
        qs[rd] = {"report_date": rd, "net_assets": net, "total_assets": tot,
                  "shares": shares, "mapped_value": mapped_val, "other_value": other_val,
                  "cash_value": cash_val, "spacex_value": spx_val, "spacex_balance": spx_bal,
                  "spacex_mark_presplit": mark, "public_value": pub_val,
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


# ------------------- SpaceX per-share mark (private) series ----------------
def _mark_steps(quarters, dates, navret):
    """SpaceX per-share mark series driving the PRIVATE leg. SIZE from the fund's
    OWN books (NPORT value/balance, the blended carrying mark; ratios only so the
    blend level cancels). Each quarter's mark step is PLACED on the day the NAV
    actually re-rated (the biggest up-move inside that quarter window) since the
    fund's exact internal mark date isn't disclosed; that aligns the replicated
    re-mark with the observed jump. IPO-era marks chain the config per-share RATIOS
    (135/105.32 = +28%, then 6/12 $160.95, 6/15 $192.50) onto the last NPORT level
    (NOT their absolute level -- different basis)."""
    qs = [q for q in quarters if q.get("spacex_mark_presplit")]
    steps = {}
    for i, q in enumerate(qs):
        if i == 0:
            steps[q["report_date"]] = (q["spacex_mark_presplit"], "base mark %s" % q["report_date"])
            continue
        prevd, qd = qs[i - 1]["report_date"], q["report_date"]
        win = [d for d in dates if prevd < d <= qd]
        place = max(win, key=lambda d: navret.get(d, -9)) if win else qd   # NAV re-rate day
        steps[place] = (q["spacex_mark_presplit"], "NPORT %s mark (NAV re-rated %s)" % (qd, place))
    if qs:
        m_last, d_last = qs[-1]["spacex_mark_presplit"], qs[-1]["report_date"]
        for rm in sorted(getattr(CFG, "SPACEX_REMARKS", []), key=lambda r: r["date"]):
            new, old = rm.get("per_share_new"), rm.get("per_share_old_split_adj")
            if new and old and rm["date"] > d_last:
                steps[rm["date"]] = (m_last * (new / old), "re-mark %s $%.2f/sh" % (rm["date"], new))
    return sorted((d, v, lab) for d, (v, lab) in steps.items())


def _holdings_diff(prevq, q):
    """What changed in the public book from prevq -> q (for the rebalance marker)."""
    added = sorted(tk for tk in q["shares"] if tk not in prevq["shares"])
    removed = sorted(tk for tk in prevq["shares"] if tk not in q["shares"])
    changed = []
    for tk in q["shares"]:
        a, b = prevq["shares"].get(tk), q["shares"][tk]
        if a and b and abs(b / a - 1) >= 0.15:
            changed.append({"ticker": tk, "chg_pct": round((b / a - 1) * 100, 0)})
    changed.sort(key=lambda c: -abs(c["chg_pct"]))
    return added, removed, changed[:6]


# ------------------------------ reconstruction -----------------------------
def build_payload():
    prices = _load_prices()
    if not prices:
        return None
    quarters = parse_quarters()
    nav = _load_nav()

    def gov_quarter(d):
        g = None
        for q in quarters:
            if q["report_date"] <= d:
                g = q
            else:
                break
        return g

    def book(q, d):
        tot = q["other_value"]
        for tk, sh in q["shares"].items():
            px = prices.get(tk, {}).get(d)
            if px is not None:
                tot += sh * px
        return tot

    dates = sorted(d for d in nav if d >= START and any(d in prices.get(tk, {}) for tk in prices))
    # actual NAV daily returns -> used to place each quarter's mark on the day the
    # fund actually re-rated (the biggest up-move in that quarter window).
    navret, pdc = {}, None
    for d in dates:
        if pdc and pdc in nav and d in nav:
            navret[d] = nav[d] / nav[pdc] - 1
        pdc = d

    steps = _mark_steps(quarters, dates, navret)
    step_dates = [s[0] for s in steps]

    def mark_of(d):
        import bisect
        i = bisect.bisect_right(step_dates, d) - 1
        return steps[i][1] if i >= 0 else None

    series = []
    cum_act = cum_repl = cum_pub = 100.0
    prev = None
    for d in dates:
        if prev is None or prev not in nav or d not in nav:
            prev = d if d in nav else prev
            continue
        q = gov_quarter(prev)                  # weights/shares in effect DURING prev->d
        if not q:
            prev = d
            continue
        pv_t, pv_p = book(q, d), book(q, prev)
        if pv_p <= 0:
            prev = d
            continue
        r_pub = pv_t / pv_p - 1
        mp, md = mark_of(prev), mark_of(d)
        r_priv = (md / mp - 1) if (mp and md) else 0.0     # SpaceX mark step (0 most days)
        wP = (q["wP_pct"] or 0) / 100.0
        wS = (q["wS_pct"] or 0) / 100.0
        c_pub, c_priv = wP * r_pub, wS * r_priv            # contributions to NAV return
        r_repl = c_pub + c_priv
        r_act = nav[d] / nav[prev] - 1
        resid = r_act - r_repl
        cum_act *= (1 + r_act)
        cum_repl *= (1 + r_repl)
        cum_pub *= (1 + c_pub)
        series.append({
            "date": d, "q": q["report_date"],
            "r_pub_pct": round(r_pub * 100, 3), "r_priv_pct": round(r_priv * 100, 3),
            "c_pub_pct": round(c_pub * 100, 3), "c_priv_pct": round(c_priv * 100, 3),
            "r_repl_pct": round(r_repl * 100, 3), "r_nav_pct": round(r_act * 100, 3),
            "resid_pct": round(resid * 100, 3),
            "cum_actual": round(cum_act, 3), "cum_repl": round(cum_repl, 3),
            "cum_public": round(cum_pub, 3),                 # public floor; private band = cum_repl - cum_public
            "wP_pct": q["wP_pct"], "wS_pct": q["wS_pct"], "mark": round(md, 2) if md else None})
        prev = d

    win = [series[0]["date"], series[-1]["date"]] if series else [START, START]

    # ---- events: re-marks (with step %) + quarterly rebalances (with diff) ----
    events = []
    last_m = None
    for d, m, lab in steps:
        if win[0] <= d <= win[1]:
            step_pct = round((m / last_m - 1) * 100, 1) if last_m else None
            events.append({"date": d, "type": "remark", "mark": round(m, 2),
                           "step_pct": step_pct, "label": lab})
        last_m = m
    for i in range(1, len(quarters)):
        q = quarters[i]
        if not (win[0] <= q["report_date"] <= win[1]):
            continue
        added, removed, changed = _holdings_diff(quarters[i - 1], q)
        events.append({"date": q["report_date"], "type": "rebalance",
                       "added": added, "removed": removed, "changed": changed,
                       "wS_pct": q["wS_pct"], "wP_pct": q["wP_pct"], "leverage": q["leverage"],
                       "coverage_pct": q["coverage_pct"]})
    events.sort(key=lambda e: (e["date"], e["type"]))

    # ---- where is the deviation? top |residual| days ----
    dev = sorted(series, key=lambda s: -abs(s["resid_pct"]))[:8]
    deviations = [{"date": s["date"], "resid_pct": s["resid_pct"], "r_nav_pct": s["r_nav_pct"],
                   "r_repl_pct": s["r_repl_pct"]} for s in dev]
    resids = [s["resid_pct"] for s in series]
    mean_r = sum(resids) / len(resids) if resids else 0.0
    sd_r = (sum((r - mean_r) ** 2 for r in resids) / (len(resids) - 1)) ** 0.5 if len(resids) > 1 else 0.0

    return {
        "meta": {
            "title": "Long-horizon replication — public book + SpaceX re-marks vs NAV",
            "window": win, "n_days": len(series), "n_quarters": len(quarters),
            "tickers": sorted({tk for q in quarters for tk in q["shares"]}),
            "method": ("Replicated NAV return = wP_q * public-book return + wS_q * SpaceX mark-step return. "
                       "Public book = sum(NPORT shares_q * adj close_t) with shares held constant within each "
                       "quarter; PRIVATE = SpaceX re-marked at each NPORT quarter mark (value/balance) and at "
                       "the recent exact-dated marks ($135 6/4, $160.95 6/12, $192.50 6/15). wP_q, wS_q are the "
                       "filed public / SpaceX weights of net assets (so they carry the fund's leverage). The "
                       "replicated line should now TRACK actual; the leftover residual = mark-timing (we step "
                       "marks at the quarter-end observation, the fund re-marked intra-quarter) + financing + "
                       "the held-flat 'other' tail."),
            "coverage_note": ("Public: ~35 liquid names ~95% of the book, small private/delisted/foreign tail "
                              "('other', incl. xAI ~1%) held flat. Private: SpaceX only (the material private mark)."),
            "price_basis": "Yahoo adjusted close (total-return) vs the fund's nav_adj (total-return NAV).",
            "disclaimer": "Estimate. Quarter-constant weights; marks stepped at quarter-end (not the exact tender date); financing not separately sourced.",
        },
        "quarters": [{k: q[k] for k in ("report_date", "net_assets", "total_assets", "leverage",
                                        "wP_pct", "wS_pct", "coverage_pct", "spacex_value")} for q in quarters],
        "events": events,
        "series": series,
        "stats": {
            "cum_actual_idx": series[-1]["cum_actual"] if series else None,
            "cum_repl_idx": series[-1]["cum_repl"] if series else None,
            "cum_public_idx": series[-1]["cum_public"] if series else None,
            "replication_gap_pct": round((series[-1]["cum_actual"] / series[-1]["cum_repl"] - 1) * 100, 1) if series else None,
            "private_share_of_repl_pct": round((1 - series[-1]["cum_public"] / series[-1]["cum_repl"]) * 100, 1) if series and series[-1]["cum_repl"] else None,
            "resid_sd_bps": round(sd_r * 100, 1), "resid_mean_bps": round(mean_r * 100, 2),
            "spacex_wt_start_pct": quarters[0]["wS_pct"] if quarters else None,
            "spacex_wt_end_pct": quarters[-1]["wS_pct"] if quarters else None,
            "top_deviations": deviations,
        },
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
    print("window", m["window"], "days", m["n_days"], "quarters", m["n_quarters"], "events", len(pl["events"]))
    print("SpaceX weight %.1f%% -> %.1f%% (net)" % (st["spacex_wt_start_pct"], st["spacex_wt_end_pct"]))
    print("cum: actual %.1f | replicated %.1f | public-only %.1f" % (st["cum_actual_idx"], st["cum_repl_idx"], st["cum_public_idx"]))
    print("replication gap (actual vs replicated): %.1f%%  | private = %.1f%% of replicated growth"
          % (st["replication_gap_pct"], st["private_share_of_repl_pct"]))
    print("residual sd %.1f bps/day  | biggest deviations:" % st["resid_sd_bps"])
    for dv in st["top_deviations"][:5]:
        print("   %s resid %+.2f%% (actual %+.2f vs repl %+.2f)" % (dv["date"], dv["resid_pct"], dv["r_nav_pct"], dv["r_repl_pct"]))
    print("wrote", write_json())
