"""
VCX premium-to-NAV engine. PURE PYTHON, NO I/O — unit-testable.

The core of this situation: a closed-end fund whose market price can detach
wildly from the value of what it holds. For each trading day we have a measured
market price; NAV per share is published only periodically, so we carry the last
published NAV forward (step function — NAV does not move daily) and compute:

    premium_t = price_t / nav_t - 1

Every point carries source (measured | nav_carried) and confidence. Days on a
published-NAV date are tagged measured/high; days carrying a stale NAV forward
are nav_carried with the NAV's own confidence (and get staler over time).
"""

from datetime import date


def _d(s): return date.fromisoformat(s)


def build_premium_series(price_daily: list[dict], nav_anchors: list[dict]) -> list[dict]:
    """price_daily: [{date, price}]; nav_anchors: [{date, nav_per_share, confidence}].
    Returns daily [{date, price, nav, premium, nav_age_days, source, confidence}].
    """
    navs = sorted(nav_anchors, key=lambda a: a["date"])
    if not navs:
        raise ValueError("no NAV anchors")
    out = []
    for row in sorted(price_daily, key=lambda r: r["date"]):
        d = row["date"]
        # last NAV anchor on or before this date
        cur = None
        for a in navs:
            if a["date"] <= d:
                cur = a
            else:
                break
        if cur is None:
            continue  # price before first NAV — skip
        nav = cur["nav_per_share"]
        prem = row["price"] / nav - 1.0 if nav else None
        is_anchor = (d == cur["date"])
        age = (_d(d) - _d(cur["date"])).days
        out.append({
            "date": d,
            "price": round(row["price"], 4),
            "nav": round(nav, 4),
            "premium": round(prem, 6) if prem is not None else None,
            "nav_age_days": age,
            "source": "measured" if is_anchor else "nav_carried",
            "confidence": "high" if is_anchor else cur.get("confidence", "med"),
        })
    return out


def current_state(premium_series: list[dict], lookthrough: list[dict]) -> dict:
    """Snapshot for KPIs. 'effective $ paid per $1 of <name> NAV' = price multiple
    on NAV applied to that name's NAV weight."""
    if not premium_series:
        return {}
    last = premium_series[-1]
    price_mult = last["price"] / last["nav"] if last["nav"] else None  # = 1 + premium
    lt = []
    for h in lookthrough:
        nav_per_share_of_name = last["nav"] * h["weight"]            # NAV $ of this name per VCX share
        price_paid_for_name = last["price"] * h["weight"]            # but you pay price, so...
        lt.append({
            "name": h["name"], "weight": h["weight"],
            "nav_value_per_share": round(nav_per_share_of_name, 4),
            "price_paid_per_share": round(price_paid_for_name, 4),
            "confidence": h.get("confidence", "med"),
        })
    return {
        "as_of": last["date"],
        "price": last["price"],
        "nav": last["nav"],
        "premium": last["premium"],
        "price_multiple": round(price_mult, 4) if price_mult else None,
        "nav_age_days": last["nav_age_days"],
        "lookthrough": lt,
    }


def premium_stats(premium_series: list[dict]) -> dict:
    prem = [p["premium"] for p in premium_series if p["premium"] is not None]
    if not prem:
        return {}
    return {
        "min": round(min(prem), 6), "max": round(max(prem), 6),
        "first": prem[0], "last": prem[-1],
        "mean": round(sum(prem) / len(prem), 6),
    }
