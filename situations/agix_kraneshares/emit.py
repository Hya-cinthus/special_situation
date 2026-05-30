"""JSON emitter for agix_kraneshares -> dashboard/data/agix_kraneshares.json.

AGIX is an ETF (trades at NAV), so no premium-to-NAV play. The story is Anthropic
CONCENTRATION over time — and it has been DILUTED (4.2% -> 2.76%) as the fund grew
on inflows, a clean parallel to the Baron dilution case. All numbers SEC-verified."""

import csv, json, os, sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import AgixKraneshares as CFG, DASHBOARD_DATA_DIR
from situations.vcx_fundrise.engine import nav_markto as M

_SIT = os.path.join(_REPO_ROOT, "situations", "agix_kraneshares")
_PROCESSED = os.path.join(_SIT, "data", "processed")

DISCLAIMER = ("Analysis, not investment advice. AGIX is an ETF: its create/redeem mechanism keeps the "
              "market price at/near NAV, so there is NO premium-to-NAV play (unlike VCX/DXYZ/RVI). "
              "Anthropic is a DIRECT, SEC-named holding (NPORT title 'ANTHROPIC, PBC SERIES E-1 PREFERRED'), "
              "verified each quarter. All figures are from SEC NPORT-P (seriesId S000085506). No datapoint "
              "is fabricated.")


def _load_price():
    with open(os.path.join(_PROCESSED, "price_daily.csv"), encoding="utf-8") as f:
        return [{"date": r["date"], "price": float(r["price"])} for r in csv.DictReader(f)]


def _load_nport():
    p = os.path.join(_PROCESSED, "nport_anchors.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def build_payload():
    price = _load_price()
    nport = _load_nport()

    conc = [{
        "date": a["report_date"], "net_assets_usd": a["net_assets_usd"],
        "anthropic_value_usd": a["anthropic_value_usd"], "anthropic_pct": a["anthropic_pct"],
        "accession": a["accession"],
    } for a in nport if a.get("anthropic_pct") is not None]

    latest = next((a for a in reversed(nport) if a.get("anthropic_pct") is not None), (nport[-1] if nport else {}))
    latest_px = price[-1] if price else {}

    tl = CFG.valuation_timeline()
    base_date = latest.get("report_date", "2026-03-31")
    holding_marks = M.holding_marks(CFG.LOOKTHROUGH, tl, base_date, latest_px.get("date", base_date))
    anth_mark = next((h for h in holding_marks if h["name"] == "Anthropic"), None)

    implied_now_pct = None
    if latest.get("anthropic_pct") is not None and anth_mark and latest.get("net_assets_usd"):
        a0 = latest["anthropic_value_usd"]
        a1 = a0 * anth_mark["growth_mult"]
        other = latest["net_assets_usd"] - a0
        implied_now_pct = a1 / (a1 + other) * 100 if (a1 + other) else None

    cost_basis_mult = None
    if CFG.ANTHROPIC_COST_BASIS_VALUATION:
        cost_basis_mult = CFG.UNDERLYING_MARKS["Anthropic"]["current_valuation_usd"] / CFG.ANTHROPIC_COST_BASIS_VALUATION

    payload = {
        "meta": {"key": CFG.KEY, "title": CFG.TITLE,
                 "generated_at": datetime.now(timezone.utc).isoformat(), "disclaimer": DISCLAIMER,
                 "primary_ticker": CFG.PRIMARY_TICKER, "edgar_cik": CFG.EDGAR_CIK,
                 "edgar_series_id": CFG.EDGAR_SERIES_ID, "is_etf": True,
                 "expense_ratio": CFG.EXPENSE_RATIO,
                 "last_data_day": latest_px.get("date"), "headline_name": "Anthropic"},
        "kpis": {
            "as_of": latest_px.get("date"), "price": latest_px.get("price"),
            "expense_ratio": CFG.EXPENSE_RATIO, "net_assets_usd": latest.get("net_assets_usd"),
            "anthropic_pct_filed": latest.get("anthropic_pct"),
            "anthropic_value_usd": latest.get("anthropic_value_usd"),
            "anthropic_filed_date": latest.get("report_date"),
            "anthropic_pct_implied_now": implied_now_pct,
            "anthropic_sleeve_mult": (anth_mark["growth_mult"] if anth_mark else None),
            "anthropic_cost_basis_mult": cost_basis_mult,
        },
        "price_series": price, "concentration": conc, "holding_marks": holding_marks,
        "lookthrough": CFG.LOOKTHROUGH,
        "events": [{"date": d, "label": l, "kind": k} for d, l, k in CFG.EVENTS],
        "nport_latest": latest,
    }
    return payload


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, DASHBOARD_DATA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "%s.json" % CFG.KEY)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = write_json(); print("Wrote %s (%.0f KB)" % (p, os.path.getsize(p) / 1024))
