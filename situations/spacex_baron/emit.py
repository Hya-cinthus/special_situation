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
from situations.spacex_baron.ingest import baron_site

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


def build_payload() -> dict:
    anchors = _load_anchors_csv()
    nav = _load_nav_csv()
    marks = baron_site.read_external_marks()

    recon = R.reconstruct_daily(anchors, nav, marks, CFG.DENSITY_ERAS,
                                CFG.WINDOW_START, CFG.ENTRY_DATE,
                                aum_overrides=getattr(CFG, "AUM_DATAPOINTS", None))
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
            "spacex_value_usd": o["spacex_value_usd"],
            "spacex_weight": o["spacex_weight_measured"],
            "source": o.get("ov_source", ""), "source_url": o.get("ov_source_url", ""),
            "confidence": o["confidence"],
        } for o in recon.get("aum_overrides", [])],
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
