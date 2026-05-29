"""
VCX scenario engine — the two-way bet. PURE PYTHON.

Your return from here owns TWO independent moving parts:
  1. NAV change — the underlying privates re-rate (e.g. Anthropic IPOs). Modeled
     as a multiplier on NAV per share via the headline name's valuation change.
  2. Premium change — the wrapper premium can compress (esp. at the 9/19 lockup)
     toward some target premium.

    new_nav   = nav * (1 + nav_change_from_rerate)
    new_price = new_nav * (1 + target_premium)
    total_return = new_price / price - 1

This makes explicit that you can be RIGHT on the AI re-rate and still LOSE if the
premium collapses — the opposite of the Baron/SpaceX setup.
"""


def headline_nav_change(lookthrough_weight: float,
                        current_valuation_usd: float,
                        new_valuation_usd: float) -> float:
    """Approx NAV % change driven by re-rating ONE headline holding, holding the
    rest of the book flat. = weight * (new/cur - 1)."""
    if not current_valuation_usd:
        return 0.0
    return lookthrough_weight * (new_valuation_usd / current_valuation_usd - 1.0)


def scenario_return(price: float, nav: float,
                    nav_change: float, target_premium: float) -> dict:
    new_nav = nav * (1.0 + nav_change)
    new_price = new_nav * (1.0 + target_premium)
    cur_premium = price / nav - 1.0 if nav else None
    return {
        "nav_change": nav_change,
        "target_premium": target_premium,
        "current_premium": cur_premium,
        "new_nav": new_nav,
        "new_price": new_price,
        "total_return": new_price / price - 1.0 if price else None,
    }


def scenario_grid(price: float, nav: float,
                  nav_changes: list[float], target_premiums: list[float]) -> list[dict]:
    """Matrix of (NAV re-rate × premium normalization) -> total return."""
    rows = []
    for nc in nav_changes:
        for tp in target_premiums:
            r = scenario_return(price, nav, nc, tp)
            rows.append({"nav_change": nc, "target_premium": tp,
                         "total_return": r["total_return"],
                         "new_price": r["new_price"]})
    return rows
