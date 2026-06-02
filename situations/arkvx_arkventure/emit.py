"""JSON emitter for arkvx_arkventure -> dashboard/data/arkvx_arkventure.json.

ARKVX is an at-NAV INTERVAL FUND (no wrapper premium). The story:
  1. multi-company SEC-named look-through (SpaceX/OpenAI/Anthropic + xAI/Neuralink/...)
  2. mark-to-market of the (ARK-marked) NAV by each tracked name's valuation move
  3. the SpaceX-IPO scenario upside, and the LIQUIDITY/GATING risk (not premium)
All look-through figures are SEC-verified from NPORT (directly named)."""

import csv, json, os, sys
from datetime import datetime, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import ArkvxArkVenture as CFG, DASHBOARD_DATA_DIR, PRIVATE_COMPANIES
from situations.vcx_fundrise.engine import nav_markto as M

_SIT = os.path.join(_REPO_ROOT, "situations", "arkvx_arkventure")
_PROCESSED = os.path.join(_SIT, "data", "processed")

DISCLAIMER = ("Analysis, not investment advice. ARKVX is an actively-managed INTERVAL FUND: it transacts "
              "at NAV (no wrapper premium like the CEFs), but redemptions are GATED to ~quarterly tenders "
              "capped near 5% — so the risk is a LIQUIDITY DISCOUNT, not a premium. Private holdings "
              "(SpaceX/OpenAI/Anthropic) are DIRECTLY SEC-NAMED in NPORT (high confidence). Underlying "
              "valuation marks are press-sourced estimates. No datapoint is fabricated.")


def _load_price():
    with open(os.path.join(_PROCESSED, "price_daily.csv"), encoding="utf-8") as f:
        return [{"date": r["date"], "price": float(r["price"])} for r in csv.DictReader(f)]


def _load_nport():
    p = os.path.join(_PROCESSED, "nport_anchors.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def build_payload():
    price = _load_price()
    nport = _load_nport()
    latest = nport[-1] if nport else {}
    latest_px = price[-1] if price else {}
    base_date = latest.get("report_date", CFG.NAV_MTM_BASE_DATE)

    # look-through (SEC-named) — use CFG weights (verified) but also expose the
    # filing-derived concentration history for the chart.
    lt = CFG.LOOKTHROUGH
    holding_marks = M.holding_marks(lt, CFG.valuation_timeline(), base_date,
                                    latest_px.get("date", base_date))

    # concentration history per tracked company (SEC-verified, from NPORT)
    conc = [{"date": a["report_date"], "net_assets_usd": a["net_assets_usd"],
             "tracked_pct": a.get("tracked_pct", {})} for a in nport if a.get("tracked_pct")]

    # mark-to-market NAV multiplier: re-rate each tracked name current->scenario.
    # at-NAV, so "return" = NAV multiplier - 1 (no premium leg).
    def nav_mult(case):
        mult, contrib = 1.0, []
        for h in lt:
            pc = PRIVATE_COMPANIES.get(h["name"])
            if not pc or not h.get("weight"):
                continue
            d = h["weight"] * (pc[case] / pc["current"] - 1.0)
            mult += d
            contrib.append({"name": h["name"], "weight": h["weight"], "delta_nav": round(d, 4)})
        return mult, contrib

    scenarios = {}
    for case in ("bear", "base", "bull"):
        m, contrib = nav_mult(case)
        scenarios[case] = {"nav_mult": m, "return": round(m - 1.0, 4), "contrib": contrib}

    # total private vs cash/public split (from NPORT top holdings, rough)
    total_tracked_pct = sum(h["weight"] for h in lt) * 100

    payload = {
        "meta": {"key": CFG.KEY, "title": CFG.TITLE,
                 "generated_at": datetime.now(timezone.utc).isoformat(), "disclaimer": DISCLAIMER,
                 "primary_ticker": CFG.PRIMARY_TICKER, "edgar_cik": CFG.EDGAR_CIK,
                 "is_etf": False, "is_interval": True, "at_nav": True,
                 "redemption_note": CFG.REDEMPTION_NOTE, "expense_ratio": CFG.EXPENSE_RATIO,
                 "last_data_day": latest_px.get("date"), "headline_name": CFG.HEADLINE_NAME},
        "kpis": {
            "as_of": latest_px.get("date"), "price": latest_px.get("price"),
            "nav": latest_px.get("price"),  # at NAV
            "expense_ratio": CFG.EXPENSE_RATIO,
            "net_assets_usd": latest.get("net_assets_usd"),
            "filed_date": latest.get("report_date"),
            "lookthrough": [{"name": h["name"], "weight": h["weight"],
                             "confidence": h["confidence"]} for h in lt],
            "total_tracked_pct": round(total_tracked_pct, 2),
            "bull_return": scenarios["bull"]["return"],
            "bear_return": scenarios["bear"]["return"],
        },
        "price_series": price,
        "concentration": conc,
        "scenarios": scenarios,
        "holding_marks": holding_marks,
        "lookthrough": lt,
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
