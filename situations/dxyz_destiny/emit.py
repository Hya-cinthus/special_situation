"""JSON emitter for dxyz_destiny -> dashboard/data/dxyz_destiny.json.
Reuses the VCX engine modules (premium, scenarios, nav_markto) — they are pure
and situation-agnostic."""

import csv, json, os, sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import DxyzDestiny as CFG, DASHBOARD_DATA_DIR
from situations.vcx_fundrise.engine import premium as P
from situations.vcx_fundrise.engine import scenarios as S
from situations.vcx_fundrise.engine import nav_markto as M
from situations.dxyz_destiny.ingest import nav_log

_SIT = os.path.join(_REPO_ROOT, "situations", "dxyz_destiny")
_PROCESSED = os.path.join(_SIT, "data", "processed")

DISCLAIMER = ("Analysis, not investment advice. DXYZ is a closed-end fund: market price can detach from "
              "NAV. NAV is sponsor-published (~quarterly) and carried forward; SpaceX/OpenAI/Anthropic are "
              "held via SPVs and their weights are SPONSOR-DISCLOSED, not SEC-verifiable. Every figure is "
              "labeled with a confidence level. No datapoint is fabricated.")


def _load_price():
    with open(os.path.join(_PROCESSED, "price_daily.csv"), encoding="utf-8") as f:
        return [{"date": r["date"], "price": float(r["price"])} for r in csv.DictReader(f)]


def _load_nport():
    p = os.path.join(_PROCESSED, "nport_anchors.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def build_payload():
    price = _load_price()
    nav_anchors = nav_log.resolve_nav_anchors()
    series = P.build_premium_series(price, nav_anchors)
    state = P.current_state(series, CFG.LOOKTHROUGH)
    stats = P.premium_stats(series)
    nport = _load_nport()

    tl = CFG.valuation_timeline()
    mtm_series = M.build_mtm_series(price, CFG.LOOKTHROUGH, tl, CFG.NAV_MTM_BASE_DATE,
                                    CFG.NAV_MTM_BASE_NAV, other_flat=CFG.NAV_MTM_OTHER_WEIGHT_FLAT)
    as_of = price[-1]["date"] if price else CFG.NAV_MTM_BASE_DATE
    holding_marks = M.holding_marks(CFG.LOOKTHROUGH, tl, CFG.NAV_MTM_BASE_DATE, as_of)
    mtm_last = mtm_series[-1] if mtm_series else {}
    disclosed_w = sum(h["weight"] for h in CFG.LOOKTHROUGH if h["name"] in tl)

    hn = CFG.HEADLINE_NAME
    hw = next((l["weight"] for l in CFG.LOOKTHROUGH if l["name"] == hn), 0.0)
    um = CFG.UNDERLYING_MARKS.get(hn, {})
    cur_px, cur_nav = state.get("price"), state.get("nav")
    grid = S.scenario_grid(cur_px or 0, cur_nav or 1, [-0.2, 0.0, 0.2, 0.4], CFG.PREMIUM_SCENARIOS)

    payload = {
        "meta": {"key": CFG.KEY, "title": CFG.TITLE,
                 "generated_at": datetime.now(timezone.utc).isoformat(), "disclaimer": DISCLAIMER,
                 "primary_ticker": CFG.PRIMARY_TICKER, "edgar_cik": CFG.EDGAR_CIK,
                 "listing_date": CFG.LISTING_DATE, "lockup_expiry": CFG.LOCKUP_EXPIRY_DATE,
                 "last_data_day": price[-1]["date"] if price else None, "headline_name": hn},
        "kpis": {"as_of": state.get("as_of"), "price": state.get("price"), "nav": state.get("nav"),
                 "premium": state.get("premium"), "price_multiple": state.get("price_multiple"),
                 "nav_age_days": state.get("nav_age_days"), "lookthrough": state.get("lookthrough", []),
                 "nav_mtm": mtm_last.get("nav_mtm"), "premium_mtm": mtm_last.get("premium_mtm"),
                 "mtm_base_date": CFG.NAV_MTM_BASE_DATE, "mtm_base_nav": CFG.NAV_MTM_BASE_NAV,
                 "mtm_disclosed_weight": round(disclosed_w, 4)},
        "series": series, "mtm_series": mtm_series, "holding_marks": holding_marks,
        "premium_stats": stats, "nav_anchors": nav_anchors, "lookthrough": CFG.LOOKTHROUGH,
        "events": [{"date": d, "label": l, "kind": k} for d, l, k in CFG.EVENTS],
        "nport_latest": (nport[-1] if nport else None),
        "scenario_base": {"price": cur_px, "nav": cur_nav, "headline_name": hn, "headline_weight": hw,
                          "premium_scenarios": CFG.PREMIUM_SCENARIOS},
        "scenario_grid": grid,
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
