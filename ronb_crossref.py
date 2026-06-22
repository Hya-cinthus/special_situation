"""
RONB cross-reference -> dashboard/data/ronb_crossref.json

RONB = Baron First Principles ETF (launched 2025-12-15), Baron's actively-managed
ETF run alongside the Baron Partners Fund (BPTIX). It holds SpaceX DIRECTLY plus
largely the same public names, and -- being an ETF -- publishes FULL HOLDINGS DAILY
(BPTIX only files quarterly NPORT). So RONB is an extra, high-frequency data point on
what Baron is doing: fresh public weights, new-name detection, and an independent
read on the SpaceX weight.

CAVEATS (from the teammate + the data): they are NOT identical. Pre-IPO they diverged
(RONB took heavy subscriptions); RONB has no leverage (BPTIX is/was levered); and the
books differ (RONB holds IBKR/MORN/ABNB/LYV that BPTIX's tracked set doesn't; BPTIX
holds CoStar/CSGP -- a big position -- that RONB doesn't). So RONB is treated as a
"managed-similarly" proxy + watchlist, never as BPTIX's exact book.

What the backtest shows (price-based, computed here): post-IPO RONB<->BPTIX daily
returns correlate ~0.997 with BPTIX ~1.3x RONB (higher SpaceX weight + leverage),
vs ~0.73 pre-IPO. So since the IPO RONB is an excellent leading proxy -- it prints
its close the SAME day, before BPTIX's NAV posts.

Holdings are seeded from the 2026-06-17 daily CSV (Baron site) and updated as new
daily snapshots arrive (the teammate has daily visibility). Prices are cached so the
build is network-free; refresh with `py ronb_crossref.py --refresh`.
"""

import json
import os

import fund_snapshots as fs

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
_CACHE = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "ronb.json")
_OUT = os.path.join(_REPO_ROOT, "dashboard", "data", "ronb_crossref.json")
IPO_DATE = "2026-06-12"

# Seed RONB holdings snapshot (Baron First Principles ETF daily CSV, as-of 2026-06-17).
# weight = % of fund; held as a committed seed so the build runs network-free.
RONB_SEED = {
    "as_of": "2026-06-17",
    "holdings": [
        {"ticker": "SPCX", "name": "Space Exploration Technologies Cl A", "weight": 31.23, "private": True},
        {"ticker": "TSLA", "name": "Tesla", "weight": 11.89}, {"ticker": "MSCI", "name": "MSCI", "weight": 4.72},
        {"ticker": "H", "name": "Hyatt Hotels", "weight": 4.51}, {"ticker": "SCHW", "name": "Charles Schwab", "weight": 3.73},
        {"ticker": "IBKR", "name": "Interactive Brokers", "weight": 3.73}, {"ticker": "SHOP", "name": "Shopify", "weight": 3.02},
        {"ticker": "VRSK", "name": "Verisk Analytics", "weight": 2.96}, {"ticker": "RRR", "name": "Red Rock Resorts", "weight": 2.67},
        {"ticker": "FDS", "name": "FactSet", "weight": 2.66}, {"ticker": "BIRK", "name": "Birkenstock", "weight": 2.64},
        {"ticker": "SPOT", "name": "Spotify", "weight": 2.59}, {"ticker": "CHH", "name": "Choice Hotels", "weight": 2.31},
        {"ticker": "FIGS", "name": "FIGS Inc", "weight": 2.29}, {"ticker": "ONON", "name": "On Holding", "weight": 2.26},
        {"ticker": "MTN", "name": "Vail Resorts", "weight": 2.16}, {"ticker": "MORN", "name": "Morningstar", "weight": 2.14},
        {"ticker": "HEI-A", "name": "HEICO Cl A", "weight": 2.13}, {"ticker": "IDXX", "name": "IDEXX Labs", "weight": 1.83},
        {"ticker": "ABNB", "name": "Airbnb", "weight": 1.76}, {"ticker": "ACGL", "name": "Arch Capital", "weight": 1.71},
        {"ticker": "GWRE", "name": "Guidewire", "weight": 1.64}, {"ticker": "LYV", "name": "Live Nation", "weight": 1.36},
        {"ticker": "IT", "name": "Gartner", "weight": 0.78}, {"ticker": "KNSL", "name": "Kinsale Capital", "weight": 0.75},
        {"ticker": "CASH", "name": "Cash & FX", "weight": 0.58, "cash": True},
    ],
}


def _yahoo(tk, days=320):
    import time, urllib.request
    p2 = int(time.time()); p1 = p2 - days * 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
           f"?period1={p1}&period2={p2}&interval=1d")
    j = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
    r = j["chart"]["result"][0]; ts = r["timestamp"]; c = r["indicators"]["quote"][0]["close"]
    return {time.strftime("%Y-%m-%d", time.gmtime(t)): round(c[i], 4) for i, t in enumerate(ts) if c[i] is not None}


_PRODUCT_URL = "https://www.baroncapitalgroup.com/product-detail/baron-first-principles-etf-ronb"
_BROWSER_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "text/csv,text/html,*/*", "Accept-Language": "en-US,en;q=0.9",
                "Referer": _PRODUCT_URL}
# Ticker normalization to our convention (match BPTIX names).
_TK_FIX = {"HEI.A": "HEI-A"}


def fetch_holdings():
    """Scrape Baron's product page for the latest daily-holdings CSV link, download
    and parse it -> {as_of, holdings:[...]}. Returns RONB_SEED on any failure."""
    import csv as _csv
    import io
    import re
    import urllib.request
    try:
        html = urllib.request.urlopen(urllib.request.Request(_PRODUCT_URL, headers=_BROWSER_HDR), timeout=30).read().decode("utf-8", "replace")
        m = re.search(r'(/api/product/media/csv/RONB-HOLDINGS-\d{8}-0\.csv\?[^"\'\s\\]*)', html)
        if not m:
            return RONB_SEED
        csv_url = "https://www.baroncapitalgroup.com" + m.group(1).replace("&amp;", "&")
        raw = urllib.request.urlopen(urllib.request.Request(csv_url, headers=_BROWSER_HDR), timeout=30).read().decode("utf-8", "replace")
    except Exception:
        return RONB_SEED
    holdings, as_of = [], None
    for row in _csv.reader(io.StringIO(raw)):
        if not row or row[0] == "Holding":
            continue
        name = row[0].strip()
        if name.lower().startswith("as of"):
            as_of = row[1].strip() if len(row) > 1 else None
            continue
        if name.lower().startswith("other assets"):
            continue
        try:
            wt = round(float(row[2].replace("%", "").strip()), 4)
        except (ValueError, IndexError):
            continue
        tk = (row[1] or "").strip()
        tk = _TK_FIX.get(tk, tk)
        h = {"ticker": tk or "CASH", "name": " ".join(name.split()).title(), "weight": wt}
        if "space exploration" in name.lower():
            h["private"] = True
        elif name.lower().startswith("cash"):
            h["cash"] = True
        holdings.append(h)
    return {"as_of": as_of or RONB_SEED["as_of"], "holdings": holdings} if holdings else RONB_SEED


def refresh(verbose=True):
    """Fetch RONB daily holdings (Baron site) + RONB/BPTIX closes (Yahoo) -> cache."""
    cache = {"holdings": fetch_holdings(), "ronb_px": _yahoo("RONB"), "bptix_px": _yahoo("BPTIX")}
    with open(_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, separators=(",", ":"))
    if verbose:
        print("cached holdings as-of", cache["holdings"]["as_of"], "(%d names)" % len(cache["holdings"]["holdings"]),
              "| RONB px", len(cache["ronb_px"]), "BPTIX px", len(cache["bptix_px"]), "->", _CACHE)
    return _CACHE


def _load():
    if os.path.exists(_CACHE):
        return json.load(open(_CACHE, encoding="utf-8"))
    return {"holdings": RONB_SEED, "ronb_px": {}, "bptix_px": {}}


def _corr_beta(rd, bd, lo=None, hi=None):
    days = sorted(d for d in (set(rd) & set(bd)) if (lo is None or d >= lo) and (hi is None or d < hi))
    rr, br = [], []
    for i in range(1, len(days)):
        rr.append(rd[days[i]] / rd[days[i - 1]] - 1)
        br.append(bd[days[i]] / bd[days[i - 1]] - 1)
    n = len(rr)
    if n < 2:
        return {"n": n, "corr": None, "beta": None}
    mr, mb = sum(rr) / n, sum(br) / n
    cov = sum((rr[i] - mr) * (br[i] - mb) for i in range(n)) / n
    vr = sum((x - mr) ** 2 for x in rr) / n
    sb = (sum((x - mb) ** 2 for x in br) / n) ** 0.5
    sr = vr ** 0.5
    return {"n": n, "corr": round(cov / (sr * sb), 3) if sr and sb else None,
            "beta": round(cov / vr, 3) if vr else None,
            "vol_ronb_pct": round(sr * 100, 2), "vol_bptix_pct": round(sb * 100, 2)}


def build_payload():
    c = _load()
    H = c["holdings"]
    rd, bd = c.get("ronb_px", {}), c.get("bptix_px", {})

    # --- holdings comparison vs BPTIX's tracked public set (5/31 NPORT back-solve) ---
    bptix_pub = {k for k in fs.WEIGHTS_5_31 if k != "SPY"}
    ronb_pub = [h for h in H["holdings"] if not h.get("private") and not h.get("cash")]
    ronb_pub_tk = {h["ticker"] for h in ronb_pub}
    shared = sorted(ronb_pub_tk & bptix_pub)
    ronb_only = sorted(ronb_pub_tk - bptix_pub)         # candidate NEW names BPTIX may hold/add
    bptix_only = sorted(bptix_pub - ronb_pub_tk)        # BPTIX names RONB lacks (e.g. CoStar)
    spx = next((h for h in H["holdings"] if h.get("private")), None)

    # RONB public weights (ex SpaceX, ex cash), renormalized -> a fresh daily basket
    pub_sum = sum(h["weight"] for h in ronb_pub) or 1
    ronb_basket = {h["ticker"]: round(h["weight"] / pub_sum, 6) for h in ronb_pub}

    # --- correlation backtest: pre vs post IPO ---
    bt = {"pre_ipo": _corr_beta(rd, bd, hi=IPO_DATE),
          "post_ipo": _corr_beta(rd, bd, lo=IPO_DATE),
          "all": _corr_beta(rd, bd)}

    # --- latest RONB move -> implied BPTIX move (leading cross-check) ---
    rdays = sorted(rd)
    implied = None
    beta = bt["post_ipo"]["beta"] or bt["all"]["beta"]
    if len(rdays) >= 2 and beta:
        d1, d0 = rdays[-1], rdays[-2]
        ronb_ret = rd[d1] / rd[d0] - 1
        implied = {"date": d1, "ronb_ret_pct": round(ronb_ret * 100, 2),
                   "beta": beta, "implied_bptix_ret_pct": round(ronb_ret * beta * 100, 2),
                   "note": ("RONB prints its close the same day, before BPTIX's NAV posts. RONB's daily "
                            "return x the post-IPO beta (%.2f) is a leading estimate of BPTIX's move." % beta)}

    # SpaceX weight cross-check: RONB (ETF, unlevered) vs BPTIX back-solve (levered)
    spx_check = None
    if spx:
        spx_check = {"ronb_spacex_pct": spx["weight"],
                     "note": ("RONB carries SpaceX at %.1f%% of net (ETF, unlevered, direct shares). BPTIX's "
                              "back-solved SpaceX weight is ~37%% -- higher because BPTIX is/was levered and sized "
                              "SpaceX larger. The two move together; RONB is the independent floor/triangulation."
                              % spx["weight"])}

    return {
        "meta": {
            "title": "RONB cross-reference — Baron's daily-transparent ETF as a BPTIX proxy",
            "as_of": H["as_of"],
            "what": ("RONB (Baron First Principles ETF) is run alongside BPTIX, holds SpaceX directly + the same "
                     "public names, and publishes holdings DAILY -- so it's a high-frequency window on what Baron "
                     "is doing, where BPTIX only files quarterly."),
            "caveat": ("Managed similarly, NOT identical: RONB is unlevered; pre-IPO they diverged (RONB took heavy "
                       "subscriptions); RONB holds IBKR/MORN/ABNB/LYV that BPTIX's tracked set doesn't, and lacks "
                       "BPTIX's CoStar (CSGP, a large BPTIX position). Use as a proxy + watchlist, not a copy."),
            "ronb_inception": "2025-12-15",
        },
        "backtest": bt,
        "implied_bptix": implied,
        "spacex_check": spx_check,
        "holdings": H["holdings"],
        "compare": {
            "shared": shared, "ronb_only": ronb_only, "bptix_only": bptix_only,
            "ronb_only_note": "In RONB, not in BPTIX's tracked 5/31 set -> candidate new names BPTIX may already hold or add.",
            "bptix_only_note": "In BPTIX (5/31), not in RONB -> BPTIX-specific (notably CoStar/CSGP); RONB can't proxy these.",
        },
        "ronb_basket": ronb_basket,
    }


def write_json():
    payload = build_payload()
    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return _OUT


if __name__ == "__main__":
    import sys
    if "--refresh" in sys.argv:
        refresh()
    p = build_payload()
    m = p["meta"]; bt = p["backtest"]
    print(m["title"], "| holdings as of", m["as_of"])
    print("backtest: pre-IPO corr %s beta %s | POST-IPO corr %s beta %s"
          % (bt["pre_ipo"]["corr"], bt["pre_ipo"]["beta"], bt["post_ipo"]["corr"], bt["post_ipo"]["beta"]))
    if p["implied_bptix"]:
        ib = p["implied_bptix"]
        print("latest %s: RONB %+.2f%% -> implied BPTIX %+.2f%% (beta %.2f)" % (ib["date"], ib["ronb_ret_pct"], ib["implied_bptix_ret_pct"], ib["beta"]))
    print("SpaceX: RONB %.1f%% (unlevered) vs BPTIX ~37%% (levered)" % p["spacex_check"]["ronb_spacex_pct"])
    cmp = p["compare"]
    print("shared:", len(cmp["shared"]), "| RONB-only (new-name watch):", cmp["ronb_only"], "| BPTIX-only:", cmp["bptix_only"])
    print("wrote", write_json())
