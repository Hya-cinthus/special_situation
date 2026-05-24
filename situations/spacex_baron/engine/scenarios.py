"""
Scenario engine — IPO re-rating and flow shock.

Pure functions. The SAME math is mirrored client-side in app.js so the
dashboard sliders are instant; keeping a Python copy lets us unit-test it and
precompute a baseline scenario table into the JSON.

Channels (all bidirectional, per the user's hypothesis being tested):
  • IPO re-rate: SpaceX is marked from the standing private valuation to the
    public valuation. SpaceX $ value scales by (ipo_val / current_val); the
    public book is unchanged at the re-mark instant; weight and per-share NAV
    step up.
  • Flow shock: a private holding cannot be added with new cash, so net INFLOWS
    land in the public book → SpaceX weight is DILUTED. Net OUTFLOWS are met by
    selling LIQUID public holdings first → SpaceX weight passively RISES; only
    once the public book is exhausted is SpaceX itself sold.
"""


def ipo_rerate(spacex_value_usd: float,
               public_value_usd: float,
               current_valuation_usd: float,
               ipo_valuation_usd: float) -> dict:
    """Re-mark SpaceX from the standing private valuation to an IPO valuation."""
    scale = ipo_valuation_usd / current_valuation_usd
    new_spacex = spacex_value_usd * scale
    new_total = new_spacex + public_value_usd
    total_before = spacex_value_usd + public_value_usd
    return {
        "ipo_valuation_usd": ipo_valuation_usd,
        "scale": scale,
        "spacex_value_usd": new_spacex,
        "public_value_usd": public_value_usd,
        "total_nav_usd": new_total,
        "spacex_weight": new_spacex / new_total if new_total else None,
        "nav_stepup_pct": (new_total / total_before - 1.0) if total_before else None,
    }


def flow_shock(spacex_value_usd: float,
               public_value_usd: float,
               net_flow_usd: float) -> dict:
    """Apply a net flow. Inflows (+) dilute; outflows (−) concentrate.

    Outflows are absorbed by the public book first; if they exceed it, the
    remainder forces SpaceX sales (the structural floor on concentration).
    """
    new_public = public_value_usd + net_flow_usd
    spacex_forced_sale = 0.0
    if new_public < 0:                       # public book exhausted by redemptions
        spacex_forced_sale = -new_public
        new_public = 0.0
    new_spacex = max(0.0, spacex_value_usd - spacex_forced_sale)
    new_total = new_spacex + new_public
    return {
        "net_flow_usd": net_flow_usd,
        "spacex_value_usd": new_spacex,
        "public_value_usd": new_public,
        "spacex_forced_sale_usd": spacex_forced_sale,
        "total_nav_usd": new_total,
        "spacex_weight": new_spacex / new_total if new_total else None,
    }


def combined(spacex_value_usd: float,
             public_value_usd: float,
             current_valuation_usd: float,
             ipo_valuation_usd: float,
             net_flow_usd: float) -> dict:
    """Re-rate first (mark event), then apply the flow on the re-rated book."""
    r = ipo_rerate(spacex_value_usd, public_value_usd, current_valuation_usd, ipo_valuation_usd)
    f = flow_shock(r["spacex_value_usd"], r["public_value_usd"], net_flow_usd)
    return {
        "ipo_valuation_usd": ipo_valuation_usd,
        "net_flow_usd": net_flow_usd,
        "spacex_weight": f["spacex_weight"],
        "spacex_value_usd": f["spacex_value_usd"],
        "public_value_usd": f["public_value_usd"],
        "total_nav_usd": f["total_nav_usd"],
        "nav_stepup_pct": r["nav_stepup_pct"],
        "spacex_forced_sale_usd": f["spacex_forced_sale_usd"],
    }


def scenario_table(spacex_value_usd: float,
                   public_value_usd: float,
                   current_valuation_usd: float,
                   ipo_valuations_usd: list[float]) -> list[dict]:
    """Precompute the headline IPO scenarios (status-quo + each IPO valuation)."""
    rows = [{
        "label": "Status quo (private mark)",
        "ipo_valuation_usd": current_valuation_usd,
        **{k: v for k, v in ipo_rerate(spacex_value_usd, public_value_usd,
                                       current_valuation_usd, current_valuation_usd).items()},
    }]
    for v in ipo_valuations_usd:
        rows.append({
            "label": f"IPO @ ${v/1e12:.2f}T",
            **ipo_rerate(spacex_value_usd, public_value_usd, current_valuation_usd, v),
        })
    return rows
