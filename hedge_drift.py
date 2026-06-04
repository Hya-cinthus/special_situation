"""
Hedge-drift analysis -> dashboard/data/hedge_drift.json

The 5/20 short is a FIXED share count. But BPTRX/BPTIX is taking inflows, and
under the stated assumption — every Total-Assets change is allocated pro-rata to
the publicly-tradable holdings while the private (SpaceX) stake stays fixed — the
public book GROWS, so a fixed-share short progressively UNDER-hedges it.

This quantifies that drift, day by day, from the BPTRX reported Total Assets
(gross) series we already maintain:

    public_book_t   = gross_total_assets_t  -  SpaceX_value (fixed)
    target_short_t  = public_book_t   (what a perfectly-sized short would be)
    actual_short    = public_book(entry)   (fixed at 5/20)
    deviation_t     = target_short_t / actual_short - 1     (how under-hedged)
    implied_scale_t = the factor each short position "should" be multiplied by

So if Total Assets rises X% (all into public names), every public short is X%
too small, and you're left with an unintended LONG public-beta tilt of that size.

Reads dashboard/data/spacex_baron.json (the maintained override series). Pure stdlib.
"""

import json
import os
import sys
import datetime

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
ENTRY = "2026-05-20"


def _interp_entry(pts):
    """Interpolate gross Total Assets at the 5/20 entry from the override points."""
    def dt(s): return datetime.date.fromisoformat(s)
    before = [p for p in pts if p["date"] <= ENTRY]
    after = [p for p in pts if p["date"] >= ENTRY]
    if any(p["date"] == ENTRY for p in pts):
        return next(p["gross"] for p in pts if p["date"] == ENTRY)
    if not before or not after:
        # extrapolate flat from nearest
        return (before or after)[0 if before else 0]["gross"] if (before or after) else None
    a, b = before[-1], after[0]
    span = (dt(b["date"]) - dt(a["date"])).days or 1
    frac = (dt(ENTRY) - dt(a["date"])).days / span
    return a["gross"] + (b["gross"] - a["gross"]) * frac


def build_payload():
    base = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "spacex_baron.json"), encoding="utf-8"))
    ov = base["aum_overrides"]
    spacex_fixed = ov[-1]["spacex_value_usd"]   # fixed private stake (NPORT gross LMV)

    pts = [{"date": o["date"], "gross": o["reported_total_assets_usd"]}
           for o in ov if o.get("reported_total_assets_usd")]
    pts.sort(key=lambda p: p["date"])

    gross_entry = _interp_entry(pts)
    public_entry = gross_entry - spacex_fixed

    rows = []
    for p in pts:
        public = p["gross"] - spacex_fixed
        scale = public / public_entry if public_entry else None
        rows.append({
            "date": p["date"],
            "gross_total_assets": round(p["gross"], 0),
            "public_book": round(public, 0),
            "spacex_pct_of_gross": round(spacex_fixed / p["gross"], 4),
            "implied_scale": round(scale, 4),               # what each short SHOULD be x
            "hedge_deviation": round(scale - 1, 4),         # under-hedge fraction
        })

    last = rows[-1] if rows else {}
    return {
        "meta": {
            "title": "Hedge drift — fixed short vs growing public book (pro-rata inflow assumption)",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_date": ENTRY,
            "assumption": ("Every change in the fund's Total Assets is allocated PRO-RATA across the "
                           "publicly-tradable holdings; the private (SpaceX) stake stays fixed. So the public "
                           "book = Total Assets − fixed SpaceX, and a fixed-share short under-hedges it as "
                           "the fund grows on inflows."),
            "disclaimer": ("Analysis, not investment advice. Built from the maintained BPTRX reported "
                           "Total Assets (gross) series; SpaceX held fixed at its last NPORT gross LMV "
                           "(~$%.2fB). 5/20 entry public book is interpolated. Assumes pro-rata public "
                           "allocation of inflows — a simplification (the manager may not rebalance exactly "
                           "pro-rata). Model, not a statement of record." % (spacex_fixed / 1e9)),
            "spacex_fixed_usd": round(spacex_fixed, 0),
            "gross_entry_usd": round(gross_entry, 0),
            "public_entry_usd": round(public_entry, 0),
            "last_data_day": last.get("date"),
        },
        "kpis": {
            "as_of": last.get("date"),
            "hedge_deviation": last.get("hedge_deviation"),
            "implied_scale": last.get("implied_scale"),
            "public_book_now": last.get("public_book"),
            "public_book_growth_usd": round((last.get("public_book", 0) - public_entry), 0),
        },
        "series": rows,
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "hedge_drift.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    m = pl["meta"]
    print(f"SpaceX fixed ${m['spacex_fixed_usd']/1e9:.2f}B | entry public ${m['public_entry_usd']/1e9:.2f}B")
    print(f"{'date':12s} {'grossTA':>9s} {'public':>9s} {'scale':>7s} {'deviation':>10s}")
    for r in pl["series"]:
        print(f"{r['date']:12s} ${r['gross_total_assets']/1e9:>7.1f}B ${r['public_book']/1e9:>7.2f}B "
              f"{r['implied_scale']:>7.3f} {r['hedge_deviation']*100:>+9.1f}%")
    p = write_json()
    print("wrote", p)
