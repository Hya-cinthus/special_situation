"""
Mark-to-market NAV reconstruction for VCX. PURE PYTHON, unit-testable.

The problem: VCX's sponsor-published NAV is stale and sticky (it barely moved
12/31->3/31 even as Anthropic ~doubled). Comparing today's market price to that
stale NAV overstates the premium. Fix: re-mark each major holding by how much its
whole-company valuation has moved since a base date, using observable funding
rounds (config.VALUATION_TIMELINE), and rebuild an *estimated* NAV per share.

Method (transparent, conservative):
  base_date NAV = NAV0 (e.g. 2025-12-31, $18.26)
  for each disclosed holding i with weight w_i:
     base_val_i  = whole-company valuation at base_date (step lookup)
     val_i(t)    = whole-company valuation at date t (step lookup)
     contribution_i(t) = w_i * val_i(t) / base_val_i
  other (undisclosed + cash) weight = 1 - sum(w_i), held FLAT (×1)  [conservative]
  NAV_mtm(t) = NAV0 * ( sum_i contribution_i(t) + other_weight )

Everything is labeled estimate / med-low confidence: weights are sponsor-
disclosed (not SEC-verifiable) and the base-date marks assume last-round fair
value. The point is an apples-to-apples premium = price(t) / NAV_mtm(t).
"""

from datetime import date


def _d(s): return date.fromisoformat(s)


def valuation_at(timeline: list, on_date: str):
    """Step-function lookup: last observable whole-company valuation on/before date."""
    val = None
    for entry in timeline:           # (date, valuation, label, url)
        if entry[0] <= on_date:
            val = entry[1]
        else:
            break
    return val


def round_on_or_before(timeline: list, on_date: str):
    out = None
    for entry in timeline:
        if entry[0] <= on_date:
            out = entry
        else:
            break
    return out  # (date, val, label, url) or None


def holding_marks(lookthrough, timeline_map, base_date, as_of_date):
    """Per-holding table: base vs current valuation + growth multiple."""
    rows = []
    for h in lookthrough:
        tl = timeline_map.get(h["name"])
        if not tl:
            continue
        b = round_on_or_before(tl, base_date)
        c = round_on_or_before(tl, as_of_date)
        if not b or not c:
            continue
        mult = c[1] / b[1] if b[1] else None
        rows.append({
            "name": h["name"], "weight": h["weight"], "confidence": h.get("confidence", "med"),
            "base_valuation_usd": b[1], "base_round": b[2], "base_round_date": b[0],
            "cur_valuation_usd": c[1], "cur_round": c[2], "cur_round_date": c[0],
            "growth_mult": round(mult, 4) if mult else None,
            "contribution_to_nav_mult": round(h["weight"] * mult, 6) if mult else None,
        })
    return rows


def nav_mtm_at(lookthrough, timeline_map, base_date, base_nav, as_of_date,
              other_flat=True):
    """Estimated mark-to-market NAV per share at as_of_date."""
    mult_sum = 0.0
    disclosed_w = 0.0
    for h in lookthrough:
        tl = timeline_map.get(h["name"])
        if not tl:
            continue
        bv = valuation_at(tl, base_date)
        cv = valuation_at(tl, as_of_date)
        if not bv or not cv:
            continue
        disclosed_w += h["weight"]
        mult_sum += h["weight"] * (cv / bv)
    other_w = max(0.0, 1.0 - disclosed_w)
    other_contrib = other_w * (1.0 if other_flat else 1.0)
    return base_nav * (mult_sum + other_contrib)


def build_mtm_series(price_daily, lookthrough, timeline_map, base_date, base_nav,
                     other_flat=True):
    """Daily estimated NAV + true (MTM) premium aligned to the price series."""
    out = []
    for row in sorted(price_daily, key=lambda r: r["date"]):
        d = row["date"]
        nav = nav_mtm_at(lookthrough, timeline_map, base_date, base_nav, d, other_flat)
        prem = row["price"] / nav - 1.0 if nav else None
        out.append({
            "date": d, "price": round(row["price"], 4),
            "nav_mtm": round(nav, 4),
            "premium_mtm": round(prem, 6) if prem is not None else None,
            "source": "estimate", "confidence": "low",
        })
    return out
