"""
JSON emitter for the spacex_baron situation.

Assembles the reconstructed series, anchors, residuals, events, marks, scenario
base + precomputed table, and the data-gaps memo into the single JSON file the
dashboard reads. The frontend does NO heavy computation — only the interactive
scenario re-rating, which it recomputes client-side from `scenario_base`.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from config import SpacexBaron as CFG, DASHBOARD_DATA_DIR
from situations.spacex_baron.engine import reconstruct as R
from situations.spacex_baron.engine import scenarios as Scn
from situations.spacex_baron.ingest import baron_site, morningstar_log

_SIT = os.path.join(_REPO_ROOT, "situations", "spacex_baron")
_PROCESSED = os.path.join(_SIT, "data", "processed")

DISCLAIMER = ("Analysis, not investment advice. Daily SpaceX weight is NOT directly "
              "observable; it is reconstructed between quarterly SEC filing anchors. "
              "Every point is labeled measured / interpolated / scenario with a "
              "confidence level. No datapoint is fabricated.")


def _load_anchors_csv():
    path = os.path.join(_PROCESSED, "anchors_quarterly.csv")
    out = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for k in ("net_assets_usd", "total_assets_usd", "spacex_value_usd",
                      "spacex_pct_of_net_assets", "spacex_balance_units"):
                r[k] = float(r[k]) if r[k] else None
            r["spacex_n_tranches"] = int(r["spacex_n_tranches"]) if r.get("spacex_n_tranches") else None
            out.append(r)
    return out


def _load_nav_csv():
    path = os.path.join(_PROCESSED, "nav_daily.csv")
    with open(path, encoding="utf-8") as f:
        return [{"date": r["date"], "nav": float(r["nav"]) if r["nav"] else None}
                for r in csv.DictReader(f)]


def _project_aum(recon: dict, cur_val: float, spacex_value: float) -> dict:
    """Extrapolate net AUM from the last measured point to the IPO date.

    Fits a log-linear trend (constant % daily growth) to the reconstruction's
    daily net-AUM series over the recent inflow window, then projects forward to
    CFG.IPO_FIRST_TRADE_DATE. SpaceX $ is held flat (private mark unchanged), so
    the projected SpaceX weight = spacex_value / projected_AUM. This is an
    EXTRAPOLATION (dashed, low confidence), not a forecast — flagged as such.
    """
    from datetime import date, timedelta
    import math

    series = [p for p in recon["series"] if p.get("total_nav_usd")]
    if len(series) < 5:
        return {"points": [], "method": "insufficient data"}

    last = series[-1]
    last_d = date.fromisoformat(last["date"])
    ipo_d = date.fromisoformat(CFG.IPO_FIRST_TRADE_DATE)
    if ipo_d <= last_d:
        return {"points": [], "method": "IPO date already passed"}

    # Fit log-linear growth over the recent inflow window (last ~45 calendar days),
    # which captures the post-filing surge rather than the whole flat history.
    window_start = last_d - timedelta(days=45)
    fit = [(date.fromisoformat(p["date"]), p["total_nav_usd"])
           for p in series if date.fromisoformat(p["date"]) >= window_start]
    if len(fit) < 5:
        fit = [(date.fromisoformat(p["date"]), p["total_nav_usd"]) for p in series[-30:]]

    x0 = fit[0][0]
    xs = [(d - x0).days for d, _ in fit]
    ys = [math.log(v) for _, v in fit]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / denom  # daily log-growth
    daily_growth = math.exp(slope) - 1.0

    # Anchor the projection at the last MEASURED AUM (continuity), grow by slope.
    pts = []
    cur = last_d
    base = last["total_nav_usd"]
    while cur <= ipo_d:
        days = (cur - last_d).days
        aum = base * math.exp(slope * days)
        wt = spacex_value / aum if aum else None
        pts.append({"date": cur.isoformat(),
                    "total_nav_usd": round(aum, 2),
                    "spacex_weight": round(wt, 6) if wt else None})
        cur += timedelta(days=1)

    return {
        "points": pts,
        "from_date": last["date"],
        "from_aum_usd": base,
        "to_date": CFG.IPO_FIRST_TRADE_DATE,
        "to_aum_usd": pts[-1]["total_nav_usd"] if pts else None,
        "to_spacex_weight": pts[-1]["spacex_weight"] if pts else None,
        "daily_growth_pct": daily_growth,
        "fit_window_days": (last_d - fit[0][0]).days,
        "method": "log-linear fit to recent net-AUM trend; SpaceX $ held flat",
        "confidence": "low",
    }


def _latest_bptix_nav():
    """Latest BPTIX NAV/share from hedge_book.json (Yahoo-sourced). (nav, date) | (None, None)."""
    p = os.path.join(_REPO_ROOT, DASHBOARD_DATA_DIR, "hedge_book.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
        for r in reversed(d["series"]):
            if r.get("nav_bptix") is not None:
                return float(r["nav_bptix"]), r["date"]
    except Exception:
        pass
    return None, None


def _lookthrough(recon: dict) -> dict | None:
    """Per-share SpaceX look-through at the latest reported AUM.

    How much SpaceX $ — and how many SpaceX shares — sit behind one fund share.
    SpaceX $ is carried at the latest private mark ($135 post 5-for-1 split); the
    fund's SpaceX share count = SpaceX $ ÷ that mark (carried flat from 3/31, since
    a private holding can't be added with daily cash). Per-class figures use each
    share class's own NAV: SpaceX shares / class-share = weight × class_NAV ÷ mark.
    """
    ov_list = recon.get("aum_overrides") or []
    series = [p for p in recon["series"] if p.get("total_nav_usd")]
    if ov_list:
        a = ov_list[-1]
        aum, spx, bptrx_nav, as_of = a["net_assets_usd"], a["spacex_value_usd"], a["nav_at_report"], a["report_date"]
    elif series:
        a = series[-1]
        aum, spx, bptrx_nav, as_of = a["total_nav_usd"], a["spacex_value_usd"], a["nav_per_share"], a["date"]
    else:
        return None
    remarks = sorted(getattr(CFG, "SPACEX_REMARKS", []), key=lambda r: r["date"])
    mark = remarks[-1].get("per_share_new") if remarks else None
    weight = (spx / aum) if aum else None
    if not (weight and mark):
        return None
    nav_date = series[-1]["date"] if series else None
    bptix_nav, bptix_date = _latest_bptix_nav()

    def _per(nav):
        return {"nav": round(nav, 2), "spacex_usd": round(weight * nav, 2),
                "spacex_shares": round(weight * nav / mark, 4)} if nav else None

    return {
        "as_of": as_of,
        "fund_aum_usd": aum,
        "spacex_value_usd": round(spx, 2),
        "spacex_weight": round(weight, 6),
        "spacex_mark_per_share": mark,
        "spacex_shares_held": round(spx / mark, 0),
        "per_share": {
            "BPTRX": {**(_per(bptrx_nav) or {}), "nav_as_of": nav_date} if bptrx_nav else None,
            "BPTIX": {**_per(bptix_nav), "nav_as_of": bptix_date} if bptix_nav else None,
        },
    }


def build_payload() -> dict:
    anchors = _load_anchors_csv()
    nav = _load_nav_csv()
    marks = baron_site.read_external_marks()

    recon = R.reconstruct_daily(anchors, nav, marks, CFG.DENSITY_ERAS,
                                CFG.WINDOW_START, CFG.ENTRY_DATE,
                                aum_overrides=morningstar_log.resolve_aum_datapoints())
    state = R.current_state(recon, CFG.ENTRY_DATE)

    spacex_value = state["spacex_value_usd"] or 0.0
    public_value = state["public_value_usd"] or 0.0
    cur_val = CFG.CURRENT_SPACEX_VALUATION_USD

    scenario_table = Scn.scenario_table(spacex_value, public_value, cur_val,
                                         CFG.IPO_VALUATION_SCENARIOS_USD)

    with open(os.path.join(_SIT, "data", "data_gaps.md"), encoding="utf-8") as f:
        gaps_md = f.read()

    # Trim anchor objects for transport (drop bulky internals we don't render).
    anchors_out = [{
        "report_date": a["report_date"], "filing_date": a["filing_date"],
        "accession": a["accession"], "net_assets_usd": a["net_assets_usd"],
        "total_assets_usd": a.get("total_assets_usd"),
        "spacex_value_usd": a["spacex_value_usd"],
        "spacex_pct_of_net_assets": a["spacex_pct_of_net_assets"],
        "spacex_balance_units": a["spacex_balance_units"],
        "spacex_n_tranches": a.get("spacex_n_tranches"),
        "spacex_weight_measured": a["spacex_weight_measured"],
        "nav_at_report": a["nav_at_report"],
        "shares_outstanding": round(a["shares_outstanding"], 2),
        "edgar_url": (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                      f"&CIK={CFG.EDGAR_CIK}&type=NPORT-P"),
        "source": a["source"], "confidence": a["confidence"],
    } for a in recon["anchors"]]

    aum_projection = _project_aum(recon, cur_val, spacex_value)
    lookthrough = _lookthrough(recon)

    payload = {
        "meta": {
            "key": CFG.KEY,
            "title": CFG.TITLE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": DISCLAIMER,
            "window_start": CFG.WINDOW_START,
            "last_data_day": recon["last_data_day"],
            "entry_date": CFG.ENTRY_DATE,
            "primary_ticker": CFG.PRIMARY_TICKER,
            "share_classes": CFG.SHARE_CLASSES,
            "edgar_cik": CFG.EDGAR_CIK,
            "ipo": {
                "ticker": CFG.IPO_TICKER, "exchange": CFG.IPO_EXCHANGE,
                "pricing_date": CFG.IPO_PRICING_DATE,
                "first_trade_date": CFG.IPO_FIRST_TRADE_DATE,
                "lockup_expiry": CFG.LOCKUP_EXPIRY_DATE,
            },
        },
        "kpis": {
            "as_of": state["as_of"],
            "spacex_weight": state["spacex_weight"],
            "spacex_value_usd": state["spacex_value_usd"],
            "total_nav_usd": state["total_nav_usd"],
            "last_private_mark_usd": cur_val,
            "entry_date": state["entry_date"],
            "entry_weight": state["entry_weight"],
            "entry_total_nav_usd": state["entry_total_nav_usd"],
        },
        "series": recon["series"],
        "anchors": anchors_out,
        "residuals": recon["residuals"],
        "aum_overrides": [{
            "date": o["report_date"], "net_assets_usd": o["net_assets_usd"],
            "reported_total_assets_usd": o.get("reported_total_assets_usd"),
            "leverage_ratio": CFG.LEVERAGE_RATIO,
            "spacex_value_usd": o["spacex_value_usd"],
            "spacex_weight": o["spacex_weight_measured"],
            "source": o.get("ov_source", ""), "source_url": o.get("ov_source_url", ""),
            "confidence": o["confidence"],
        } for o in recon.get("aum_overrides", [])],
        "aum_projection": aum_projection,
        "lookthrough": lookthrough,
        "events": [{"date": d, "label": l, "kind": k} for d, l, k in CFG.EVENTS],
        "density_eras": [{"start": s, "end": e, "label": l, "confidence": c}
                         for s, e, l, c in CFG.DENSITY_ERAS],
        "marks": marks,
        "scenario_base": {
            "spacex_value_usd": spacex_value,
            "public_value_usd": public_value,
            "total_nav_usd": state["total_nav_usd"],
            "current_valuation_usd": cur_val,
            "ipo_valuations_usd": CFG.IPO_VALUATION_SCENARIOS_USD,
            "default_net_flow_usd": CFG.DEFAULT_NET_FLOW_SHOCK_USD,
        },
        "scenario_table": scenario_table,
        "data_gaps_md": gaps_md,
    }
    return payload


def write_json() -> str:
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, DASHBOARD_DATA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{CFG.KEY}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = write_json()
    print(f"Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
