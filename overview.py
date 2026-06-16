"""
Cross-vehicle overview builder -> dashboard/data/overview.json.

Aggregates the already-emitted, already-verified per-vehicle JSONs plus the
PRIVATE_COMPANIES + VEHICLE_META registries (config.py) into one normalized
research-memo dataset: comparison rows, bear/base/bull scenarios, look-through
exposure by private company, data-confidence, and computed verdicts.

DESIGN RULES (anti-hallucination):
  - Reuse only values the per-vehicle pipelines already produced (SEC/Yahoo).
  - bear/base/bull are CURATED scenario inputs from the registry, each carrying a
    source + confidence; the page labels them ESTIMATE.
  - Never invent a premium for an at-NAV vehicle; never treat sponsor weights as
    SEC-verified. Confidence travels with every vehicle.
  - Scenario math is transparent: scenario_NAV = current_NAV x (1 + sum_i
    weight_i*(scenario_val_i/current_val_i - 1)); unknown holdings held flat.
"""

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import (DASHBOARD_DATA_DIR, SITUATIONS, PRIVATE_COMPANIES,  # noqa: E402
                    VEHICLE_META)

_CONF_SCORE = {"high": 0.9, "med": 0.6, "medium": 0.6, "low-med": 0.45, "low": 0.3}


def _load(key):
    p = os.path.join(_REPO_ROOT, DASHBOARD_DATA_DIR, f"{key}.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _lookthrough(key, d):
    """Return [{name, weight(of NAV)}] for the vehicle, normalized across shapes."""
    k = d.get("kpis", {})
    if key == "spacex_baron":
        w = k.get("spacex_weight")
        return [{"name": "SpaceX", "weight": w}] if w else []
    if key == "agix_kraneshares":
        p = k.get("anthropic_pct_filed")
        return [{"name": "Anthropic", "weight": p / 100.0}] if p else []
    # CEFs: vcx/dxyz/rvi
    return [{"name": h["name"], "weight": h["weight"]} for h in k.get("lookthrough", [])]


def _scenario_nav_mult(lookthrough, case):
    """Multiplier on current (MTM) NAV if each known holding moves current->case."""
    mult = 1.0
    contrib = []
    for h in lookthrough:
        pc = PRIVATE_COMPANIES.get(h["name"])
        if not pc or not h.get("weight"):
            continue
        cur = pc["current"]
        scen = pc[case]
        delta = h["weight"] * (scen / cur - 1.0)
        mult += delta
        contrib.append({"name": h["name"], "weight": h["weight"],
                        "delta_nav": round(delta, 4)})
    return mult, contrib


def _vehicle_record(key):
    d = _load(key)
    meta = VEHICLE_META.get(key, {})
    if not d:
        return {"key": key, "ticker": meta.get("ticker", key), "missing": True}
    k = d.get("kpis", {})
    is_etf = bool(d["meta"].get("is_etf"))
    # at-NAV vehicles: mutual fund (BPTIX), ETF (AGIX), interval fund (ARKVX)
    at_nav = is_etf or key == "spacex_baron" or bool(d["meta"].get("at_nav"))

    price = k.get("price")
    if key == "spacex_baron":
        price = None  # mutual fund: you transact at NAV, no separate market price
    nav_stale = k.get("nav")
    nav_mtm = k.get("nav_mtm")
    if key == "spacex_baron":
        nav_mtm = k.get("total_nav_usd")          # already marked; fund-level $
    if key in ("agix_kraneshares", "arkvx_arkventure"):
        nav_stale = price                          # at NAV
        nav_mtm = price

    premium_stale = k.get("premium")
    premium_mtm = k.get("premium_mtm")
    if at_nav:
        premium_stale = premium_mtm = 0.0

    lt = _lookthrough(key, d)

    # scenario fair NAV (per share for CEF/ETF; fund-level for BPTIX — only the
    # RATIO matters for returns) and the implied price under a premium assumption
    base_ref = nav_mtm if nav_mtm else (price or nav_stale)
    scen = {}
    contribs = {}
    for case in ("bear", "base", "bull"):
        mult, contrib = _scenario_nav_mult(lt, case)
        scen_nav = base_ref * mult if base_ref else None
        contribs[case] = contrib
        if at_nav:
            # no premium: you own NAV; return vs current = NAV ratio - 1
            ret = (mult - 1.0) if base_ref else None
            scen[case] = {"nav": scen_nav, "implied_price": scen_nav,
                          "premium_assumed": 0.0, "return_from_price": ret}
        else:
            # CEF: premium assumption per case (bear: ->0, base: ->half, bull: hold)
            prem = premium_mtm or 0.0
            prem_assumed = {"bear": 0.0, "base": prem / 2.0, "bull": prem}[case]
            implied_price = scen_nav * (1 + prem_assumed) if scen_nav else None
            ret = (implied_price / price - 1.0) if (implied_price and price) else None
            scen[case] = {"nav": scen_nav, "implied_price": implied_price,
                          "premium_assumed": prem_assumed, "return_from_price": ret}

    # verdict category (data-driven from premium + confidence)
    conf = meta.get("data_confidence", "med")
    conf_score = _CONF_SCORE.get(conf, 0.6)
    pm = premium_mtm or 0.0
    total_priv = sum((h.get("weight") or 0) for h in lt)
    if key == "spacex_baron":
        category, verdict = "opportunity", "Cleanest SpaceX at NAV; stale-mark re-rate optionality"
    elif at_nav and total_priv >= 0.12:
        category, verdict = "clean", "At-NAV multi-name private basket; gated liquidity is the catch"
    elif at_nav:
        category, verdict = "clean", "At-NAV, low-fee, verifiable — but low concentration"
    elif pm > 0.8:
        category, verdict = "avoid", "Overheated — premium dwarfs underlying upside"
    elif pm > 0.30:
        category, verdict = "rich", "Rich premium — needs the underlying to keep compounding"
    else:
        category, verdict = "fair", "Reasonable premium for the exposure"

    return {
        "key": key, "ticker": meta.get("ticker", key), "name": meta.get("name", key),
        "type": meta.get("type", ""), "headline": d["meta"].get("headline_name") or meta.get("headline"),
        "buyable": meta.get("buyable", ""), "fee": meta.get("fee", ""),
        "liquidity": meta.get("liquidity", ""),
        "at_nav": at_nav, "is_etf": is_etf,
        "price": price, "nav_stale": nav_stale, "nav_mtm": nav_mtm,
        "premium_stale": premium_stale, "premium_mtm": premium_mtm,
        "lookthrough": lt,
        "scenarios": scen, "scenario_contrib": contribs,
        "data_confidence": conf, "data_confidence_score": conf_score,
        "confidence_reasons": meta.get("confidence_reasons", ""),
        "structure_note": meta.get("structure_note", ""),
        "key_risk": meta.get("key_risk", ""),
        "reason_buy": meta.get("reason_buy", ""), "reason_avoid": meta.get("reason_avoid", ""),
        "category": category, "verdict": verdict,
        "as_of": k.get("as_of"), "page": f"{ 'index' if key=='spacex_baron' else {'vcx_fundrise':'vcx','dxyz_destiny':'dxyz','rvi_robinhood':'rvi','agix_kraneshares':'agix','arkvx_arkventure':'arkvx'}.get(key,key) }.html",
    }


def _company_section(vehicles):
    """For each private company: registry data + which vehicles expose it + the
    cleanest / most-overpriced way in (lowest vs highest premium-per-unit)."""
    out = []
    for name, pc in PRIVATE_COMPANIES.items():
        exposed = []
        for v in vehicles:
            if v.get("missing"):
                continue
            w = next((h["weight"] for h in v["lookthrough"] if h["name"] == name), None)
            if not w:
                continue
            # "cost" of the exposure = premium you pay for the wrapper (0 at NAV)
            exposed.append({"ticker": v["ticker"], "key": v["key"], "weight": w,
                            "premium_mtm": v["premium_mtm"], "at_nav": v["at_nav"],
                            "confidence": v["data_confidence"]})
        exposed.sort(key=lambda e: e["weight"], reverse=True)
        cleanest = min(exposed, key=lambda e: (e["premium_mtm"] or 0)) if exposed else None
        priciest = max(exposed, key=lambda e: (e["premium_mtm"] or 0)) if exposed else None
        out.append({
            "name": name, "sector": pc["sector"],
            "current": pc["current"], "bear": pc["bear"], "base": pc["base"], "bull": pc["bull"],
            "last_confirmed": pc["last_confirmed"], "rumored_range": pc["rumored_range"],
            "source_url": pc["source_url"], "notes": pc["notes"],
            "exposed_via": exposed,
            "cleanest_ticker": cleanest["ticker"] if cleanest else None,
            "priciest_ticker": priciest["ticker"] if priciest else None,
        })
    return out


def build_payload():
    vehicles = [_vehicle_record(k) for k in SITUATIONS]
    live = [v for v in vehicles if not v.get("missing")]

    # data-driven summary buckets
    cef = [v for v in live if not v["at_nav"]]
    best = min(live, key=lambda v: (v["premium_mtm"] or 0) - 0.3 * v["data_confidence_score"])
    # "Most overheated" = biggest gap vs PUBLISHED (stale) NAV — the headline a
    # naive buyer overpays; VCX's ~+1,000% dominates. Falls back to MTM premium.
    overheated = max(cef, key=lambda v: (v["premium_stale"] or v["premium_mtm"] or 0)) if cef else None
    uncertain = min(live, key=lambda v: v["data_confidence_score"])
    cleanest_exp = max(live, key=lambda v: v["data_confidence_score"] - (v["premium_mtm"] or 0))
    # most bull upside from price
    def bull_ret(v):
        s = v["scenarios"].get("bull", {})
        return s.get("return_from_price") if s.get("return_from_price") is not None else -9
    top_upside = max(live, key=bull_ret)

    summary = {
        "best_opportunity": {"ticker": best["ticker"], "key": best["key"], "why": best["verdict"]},
        "most_overheated": ({"ticker": overheated["ticker"], "key": overheated["key"],
                             "premium_mtm": overheated["premium_mtm"],
                             "why": overheated["key_risk"]} if overheated else None),
        "most_uncertain": {"ticker": uncertain["ticker"], "key": uncertain["key"],
                           "why": uncertain["confidence_reasons"]},
        "cleanest_exposure": {"ticker": cleanest_exp["ticker"], "key": cleanest_exp["key"],
                              "why": cleanest_exp["reason_buy"]},
        "top_bull_upside": {"ticker": top_upside["ticker"], "key": top_upside["key"],
                            "ret": bull_ret(top_upside)},
    }

    import datetime
    payload = {
        "meta": {"title": "AI / Space Private-Exposure Vehicles — Research Memo",
                 "generated_at": _now_iso(),
                 "disclaimer": ("Analysis, not investment advice. Vehicle prices/NAVs are from each "
                                "vehicle's verified pipeline (SEC NPORT-P + Yahoo). bear/base/bull are "
                                "CURATED scenario assumptions on the underlying private companies — each "
                                "carries a source + confidence and is an ESTIMATE, not a forecast. "
                                "Premiums apply only to closed-end funds. Sponsor-disclosed (SPV) weights "
                                "are flagged low-confidence. No datapoint is fabricated."),
                 "n_vehicles": len(live)},
        "summary": summary,
        "vehicles": vehicles,
        "companies": _company_section(vehicles),
    }
    return payload


def _now_iso():
    # Date.now() unavailable in workflow sandboxes; use os time via datetime here is fine in build.
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, DASHBOARD_DATA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "overview.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = write_json()
    print(f"Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
