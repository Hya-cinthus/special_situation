"""
Daily BPTIX NAV-estimate log -> dashboard/data/daily_nav_log.json

Each trading day the user pastes that day's public-holding closes + the SPCX close.
For every basket-weighting mechanism we've tried (actual hedge, fund 3/31, 4/30,
5/31, blend, optimal), we predict the day's BPTIX NAV and record it; when the real
NAV is known it goes in the last column and we score each basket's error. Append a
new dict to ENTRIES each day — that's the whole workflow.

Prediction (chained off the prior day's ACTUAL NAV where known):
    NAV_t = NAV_{t-1} x (1 + w_spx x spcx_return + (1 - w_spx) x basket_return)
SpaceX is marked to the live SPCX close (re-marks daily now it's public). w_spx is
carried from the reconstruction and updated each day (SpaceX value x SPCX move /
AUM grown by the NAV move; no-flows approx until the Morningstar AUM is supplied).
Public weights drop the SPY residual and renormalize over the 23 real names (per
the user's preference). Pure stdlib; the 6/12 base closes are read from hedge_book.
"""

import json
import os

import fund_snapshots as fs

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# Base = last fully-known day before the log starts (6/12 Fri close). spacex_value
# is the NO-BUY 6/12 mark (kept here so recalibrate.py's "prior" stays the no-buy
# baseline); the Friday-buy ASSUMPTION below is added on top for the prediction.
BASE = {"date": "2026-06-12", "nav": 289.98, "spcx": 160.95, "aum": 20.4e9, "spacex_value": 5.945106488e9}

# NEW ASSUMPTION (2026-06-16): 6/15's actual NAV cleared every no-buy basket AND the
# perfect-fit band, so 6/12 (Friday) DID add SpaceX. The recalibration back-solves
# ~$262M (band $259-344M). We fold that into the predicted SpaceX value here, which
# lifts the carried SpaceX weight from ~29.1% (no buy) to ~30.4% on 6/15 and ~35.9%
# carried into 6/16. Adjust this one number as the calibration tightens.
FRIDAY_SPACEX_BUY = 0.262e9

# START-OF-DAY leverage assumption = gross holdings / net assets entering the day
# (BEFORE that day's redemptions, which are forward-priced at the close and don't
# touch the day's return). Public sleeve weight of net = LEVERAGE - w_spx; the
# remainder (1 - LEVERAGE) is net cash earning ~0. 0.968 = the 5/31 disclosed level
# (slightly NET CASH). Adjust as fresher leverage is known. With LEVERAGE = 1.0 this
# reduces to the old (1 - w_spx) public weight.
LEVERAGE_ASSUMPTION = 0.968

# Append-only AS-OF (vintage) log: each day's estimate frozen as first reported, so
# revising an assumption (Friday buy, leverage, ...) never erases what we estimated
# that day. Seeded with 6/15 (no-buy) + 6/16 (pre-leverage); future days auto-freeze.
_VINTAGE_PATH = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "daily_nav_vintage.jsonl")

# Append one dict per trading day. closes = {ticker: close} for the 23 public names
# (Yahoo-style tickers, HEI/A -> HEI-A). spcx = SPCX close. actual_nav = BPTIX NAV
# (None until known). aum = Morningstar Total Assets (optional; improves w_spx).
# note = the day's "what's new" (information added / what changed in the assumptions).
ENTRIES = [
    {"date": "2026-06-15", "spcx": 192.50, "actual_nav": 307.55, "aum": 20.7e9,
     "closes": {"ACGL": 91.50, "BIRK": 47.93, "CHH": 112.00, "CSGP": 32.04, "FDS": 235.86,
                "FIG": 18.51, "GLPI": 46.74, "GWRE": 120.03, "H": 198.95, "HEI": 336.18,
                "HEI-A": 248.73, "IDXX": 570.00, "IT": 142.77, "KNSL": 311.83, "MSCI": 611.17,
                "MTN": 134.40, "ONON": 38.69, "RRR": 61.13, "SCHW": 90.95, "SHOP": 112.49,
                "SPOT": 479.85, "TSLA": 411.15, "VRSK": 180.46},
     "note": "Actual NAV 307.55 + AUM 20.7B in. NEW: it cleared every no-buy basket AND the perfect-fit band "
             "-> Friday DID buy SpaceX (~$262M); w_spx raised 29.1%->30.4%. Implied ~$0.9B Monday outflow."},
    {"date": "2026-06-16", "spcx": 201.80, "actual_nav": None, "aum": None,
     "closes": {"ACGL": 92.58, "BIRK": 48.97, "CHH": 116.07, "CSGP": 31.97, "FDS": 237.56,
                "FIG": 17.98, "GLPI": 46.73, "GWRE": 117.46, "H": 197.03, "HEI": 335.53,
                "HEI-A": 248.11, "IDXX": 573.00, "IT": 142.24, "KNSL": 312.69, "MSCI": 608.16,
                "MTN": 136.68, "ONON": 38.06, "RRR": 60.92, "SCHW": 93.67, "SHOP": 113.23,
                "SPOT": 469.81, "TSLA": 404.66, "VRSK": 179.61},
     "note": "Estimate only (BPTIX NAV + Morningstar AUM land tomorrow). SPCX 201.80 (+4.8%). Carries the "
             "post-Friday-buy SpaceX weight (~35.9%). Public basket ~flat (TSLA -1.6%, insurers up)."},
]

METHOD_LABELS = {"actual": "actual hedge", "fund_3_31": "fund 3/31", "fund_4_30": "fund 4/30",
                 "fund_5_31": "fund 5/31", "blend": "blend 4/30+5/31", "optimal": "optimal (min-var)"}


def _nospy(W):
    w = {k: v for k, v in W.items() if k != "SPY"}
    s = sum(w.values()) or 1
    return {k: v / s for k, v in w.items()}


def _weightings():
    H = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "hedge_book.json"), encoding="utf-8"))
    comps = {m: {r["ticker"].replace("/", "-"): r["weight"] for r in rows if r["ticker"] != "SPY"}
             for m, rows in H["meta"]["basket_compositions"].items()}

    def renorm(w):
        s = sum(w.values()) or 1
        return {k: v / s for k, v in w.items()}

    blend = {t: 0.5 * (fs.WEIGHTS_4_30.get(t, 0) + fs.WEIGHTS_5_31.get(t, 0))
             for t in set(fs.WEIGHTS_4_30) | set(fs.WEIGHTS_5_31)}
    return {
        "actual": renorm(comps.get("actual", {})),
        "fund_3_31": _nospy(fs.WEIGHTS_3_31), "fund_4_30": _nospy(fs.WEIGHTS_4_30),
        "fund_5_31": _nospy(fs.WEIGHTS_5_31), "blend": _nospy(blend),
        "optimal": renorm(comps.get("optimal", {})),
    }, H


def _base_closes(H):
    legs = {l["ticker"].replace("/", "-"): l for l in H["legs"] if l["side"] == "short"}
    spnl = {p["ticker"].replace("/", "-"): p for p in H["short_legs_pnl"]}
    sd = [r["date"] for r in H["series"]]
    li = sd.index(BASE["date"])
    return {t: legs[t]["entry_px"] + spnl[t]["pnl"][li] / legs[t]["shares"]
            for t in legs if legs[t].get("shares")}


def _ensemble():
    """Perfect-fit ensemble (normalized weights) from ipo_day_recon, for a NAV band."""
    try:
        e = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "ipo_day_recon.json"), encoding="utf-8"))["best_fit"]["ensemble"]
        return e["tickers"], e["fits"]
    except Exception:
        return [], []


def build_payload():
    WS, H = _weightings()
    methods = list(METHOD_LABELS)
    ens_tk, ens_fits = _ensemble()
    prev = {"nav": BASE["nav"], "spcx": BASE["spcx"], "aum": BASE["aum"],
            "spx_value": BASE["spacex_value"] + FRIDAY_SPACEX_BUY, "closes": _base_closes(H)}
    rows = []
    for e in ENTRIES:
        spx_ret = e["spcx"] / prev["spcx"] - 1
        w_spx = prev["spx_value"] / prev["aum"]
        preds = {}
        for m in methods:
            W = WS[m]
            num = den = 0.0
            for t, w in W.items():
                a, b = prev["closes"].get(t), e["closes"].get(t)
                if a and b and w:
                    num += w * (b / a - 1)
                    den += w
            br = num / den if den else 0.0
            navret = w_spx * spx_ret + (LEVERAGE_ASSUMPTION - w_spx) * br
            preds[m] = {"basket_ret_pct": round(br * 100, 3),
                        "nav_return_pct": round(navret * 100, 3),
                        "pred_nav": round(prev["nav"] * (1 + navret), 2)}
        # perfect-fit ensemble band: apply each fit's (normalized) weights -> NAV range
        ens_navs = []
        for fw in ens_fits:
            num = den = 0.0
            for ti, t in enumerate(ens_tk):
                a, b, w = prev["closes"].get(t), e["closes"].get(t), fw[ti]
                if a and b and w:
                    num += w * (b / a - 1)
                    den += w
            br = num / den if den else 0.0
            ens_navs.append(prev["nav"] * (1 + w_spx * spx_ret + (LEVERAGE_ASSUMPTION - w_spx) * br))
        pf_range = [round(min(ens_navs), 2), round(max(ens_navs), 2)] if ens_navs else None
        actual = e.get("actual_nav")
        errs = ({m: round(preds[m]["pred_nav"] - actual, 2) for m in methods} if actual else {})
        best = min(errs, key=lambda m: abs(errs[m])) if errs else None
        rows.append({"date": e["date"], "spcx": e["spcx"], "spcx_ret_pct": round(spx_ret * 100, 2),
                     "spacex_weight_pct": round(w_spx * 100, 2), "leverage": LEVERAGE_ASSUMPTION,
                     "prior_nav": prev["nav"], "preds": preds, "perfect_fit_range": pf_range,
                     "actual_nav": actual, "errors": errs, "best_method": best,
                     "note": e.get("note", "")})
        # chain to next day: base off ACTUAL nav if known, else the median prediction
        base_nav = actual if actual else sorted(preds[m]["pred_nav"] for m in methods)[len(methods) // 2]
        spx_value = prev["spx_value"] * (e["spcx"] / prev["spcx"])
        aum = float(e["aum"]) if e.get("aum") else prev["aum"] * (base_nav / prev["nav"])
        prev = {"nav": base_nav, "spcx": e["spcx"], "aum": aum, "spx_value": spx_value, "closes": e["closes"]}

    vintage_rows = _freeze_vintage(rows)
    return {
        "meta": {
            "title": "Daily BPTIX NAV estimate — per basket-weighting vs actual",
            "method_labels": METHOD_LABELS, "methods": methods, "base": BASE,
            "friday_spacex_buy_usd": FRIDAY_SPACEX_BUY, "leverage": LEVERAGE_ASSUMPTION,
            "note": ("Each day's predicted BPTIX NAV under every basket weighting we've tested, vs the actual. "
                     "NAV_t = NAV_{t-1} x (1 + w_spx x SPCX_return + (LEVERAGE - w_spx) x basket_return); SpaceX "
                     "marked to live SPCX; public weights drop SPY and renormalize over the 23 names. w_spx folds "
                     "in the assumed Friday SpaceX buy ($%.0fM); LEVERAGE is the start-of-day gross/net (%.3f, "
                     "pre-redemption). Chained off the prior ACTUAL NAV where known (else the median prediction)."
                     % (FRIDAY_SPACEX_BUY / 1e6, LEVERAGE_ASSUMPTION)),
            "two_views_note": ("AS-OF (vintage): each day's estimate FROZEN as first reported — what we thought "
                               "that day. REVISED: recomputed now with the current assumptions (Friday buy + "
                               "leverage). Toggle to compare; the gap is the assumption update."),
            "disclaimer": "Estimate, not the fund's record. Excludes fees, intraday timing, mid-day flows.",
        },
        "rows": rows,                 # REVISED (current assumptions)
        "vintage_rows": vintage_rows, # AS-OF (frozen as first reported)
    }


def _freeze_vintage(rows):
    """Append-only: freeze each day's estimate the first time it is built; never
    revise a frozen day. Returns the frozen rows in date order (idempotent)."""
    frozen, order = {}, []
    if os.path.exists(_VINTAGE_PATH):
        for line in open(_VINTAGE_PATH, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                frozen[r["date"]] = r
                order.append(r["date"])
    added = []
    for r in rows:
        if r["date"] not in frozen:
            frozen[r["date"]] = r
            order.append(r["date"])
            added.append(r)
    if added:
        with open(_VINTAGE_PATH, "a", encoding="utf-8") as f:
            for r in added:
                f.write(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n")
    return [frozen[d] for d in sorted(set(order))]


def write_json():
    payload = build_payload()
    out = os.path.join(_REPO_ROOT, "dashboard", "data", "daily_nav_log.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return out


if __name__ == "__main__":
    pl = build_payload()
    print(pl["meta"]["title"])
    for r in pl["rows"]:
        ps = " ".join("%s=%.2f" % (m, r["preds"][m]["pred_nav"]) for m in pl["meta"]["methods"])
        print(r["date"], "SPCX", r["spcx"], "w_spx %.1f%%" % r["spacex_weight_pct"], "| actual", r["actual_nav"])
        print("  ", ps)
    print("wrote", write_json())
