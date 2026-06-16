"""
SpaceX 6/4 re-mark — multi-scenario reconciliation -> dashboard/data/spacex_remark.json

On 2026-06-04 the fund's reported figures jumped (BPTIX NAV/share 262.23 -> 279.60,
+6.6%; Morningstar Total Assets 17.2B -> 18.7B) while its PUBLIC holdings barely
moved (+0.07% value-weighted basket return). That gap is a SpaceX re-mark. But
THREE things are genuinely uncertain, so instead of picking one we solve all three:
  - is the leverage ratio (1.1358) actually right?
  - is the reported "Total Assets" gross (after leverage) or net (real AUM)?
  - what is the exact new SpaceX valuation?

Identity used (the per-share NAV return is FLOW-NEUTRAL, so inflows don't distort it):
    nav_return = (SpaceX_prev * r_spx + public_prev * r_pub) / net_prev
    gross = net * L  ;  gross = SpaceX + public_gross

  S1  L trusted (1.1358), TA = GROSS   -> solve the SpaceX mark
  S2  SpaceX = full $1.77T IPO certain  -> solve the leverage it would require
  S3  L trusted (1.1358), TA = NET AUM  -> solve the SpaceX mark

All inputs are documented point-in-time facts (see INPUTS). Pure stdlib.
"""

import json
import os
import datetime

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# ---- Documented inputs (point-in-time facts, with provenance) -----------------
BPTIX_NAV_3 = 262.23          # Yahoo close 2026-06-03 (BPTIX)
BPTIX_NAV_4 = 279.60          # Yahoo close 2026-06-04 (BPTIX, +6.62%)
R_PUB = 0.000741              # value-weighted return of the 23-name public basket on
                              # 6/4 (Yahoo closes, weighted at 6/3 prices) — proxy for
                              # the fund's public book
SPX_3_USD = 3.89026788e9      # SpaceX holding value, 2026-03-31 NPORT-P gross LMV,
                              # carried unchanged through 6/3 (mark = $1.25T)
VAL_BASE = 1.25e12            # standing SpaceX valuation: 2026-02-02 SpaceX+xAI merger
                              # ($526.59/sh), confirmed by the 3/31 NPORT $ value
IPO_VAL = 1.77e12             # 2026-06-03 IPO priced: $135/sh, $1.77T
TA_3 = 17.2e9                 # Morningstar Total Assets 6/3 (gross convention)
TA_4 = 18.7e9                 # Morningstar Total Assets 6/4 (user-provided 6/5 AM)
L0 = 1.135836786284202        # leverage = gross/net from the 3/31 NPORT-P
NAV_RET = BPTIX_NAV_4 / BPTIX_NAV_3 - 1


def _val_to_usd(valuation):
    """Baron's SpaceX $ value at a given whole-company valuation (linear in valuation,
    anchored on the 3/31 NPORT: $3.89B @ $1.25T)."""
    return SPX_3_USD * valuation / VAL_BASE


def build_payload():
    scenarios = []

    # --- S1: L trusted, reported TA = GROSS -> solve SpaceX mark ---------------
    net3 = TA_3 / L0
    pub3 = TA_3 - SPX_3_USD
    r_spx1 = (NAV_RET * net3 - pub3 * R_PUB) / SPX_3_USD
    spx4_1 = SPX_3_USD * (1 + r_spx1)
    val4_1 = VAL_BASE * (1 + r_spx1)
    scenarios.append({
        "key": "S1", "name": "Leverage accurate + Total Assets = gross",
        "fixed": "L = 1.1358 (3/31 NPORT); treat 18.7B as gross (after leverage)",
        "solved_for": "SpaceX mark",
        "leverage": round(L0, 4),
        "net_aum_usd": round(TA_4 / L0, 0),
        "gross_ta_usd": round(TA_4, 0),
        "spacex_value_usd": round(spx4_1, 0),
        "spacex_valuation_usd": round(val4_1, 0),
        "spacex_return": round(r_spx1, 4),
        "public_gross_usd": round(TA_4 - spx4_1, 0),
        "verdict": "consistent",
        "note": "Internally-consistent default: SpaceX backs out to ~$1.57T, a partial re-mark.",
    })

    # --- S2: SpaceX = full $1.77T -> solve required leverage -------------------
    r_spx_full = IPO_VAL / VAL_BASE - 1
    net3_implied = (SPX_3_USD * r_spx_full + pub3 * R_PUB) / NAV_RET
    L_implied = TA_3 / net3_implied
    scenarios.append({
        "key": "S2", "name": "SpaceX = full $1.77T (certain)",
        "fixed": "SpaceX 6/4 = $1.77T ($5.51B); treat 18.7B as gross",
        "solved_for": "leverage",
        "spacex_value_usd": round(_val_to_usd(IPO_VAL), 0),
        "spacex_valuation_usd": IPO_VAL,
        "spacex_return": round(r_spx_full, 4),
        "implied_leverage": round(L_implied, 4),
        "implied_net_usd": round(net3_implied, 0),
        "verdict": "impossible",
        "note": ("For a full $1.77T mark to produce only +6.6%% NAV, leverage would have to be %.2fx "
                 "(<1 = net cash), impossible for a levered fund -> proves 6/4 is not a full mark." % L_implied),
    })

    # --- S3: reported TA = NET AUM, L trusted -> solve SpaceX mark -------------
    net3b = TA_3
    gross3b = TA_3 * L0
    pub3b = gross3b - SPX_3_USD
    r_spx3 = (NAV_RET * net3b - pub3b * R_PUB) / SPX_3_USD
    spx4_3 = SPX_3_USD * (1 + r_spx3)
    val4_3 = VAL_BASE * (1 + r_spx3)
    scenarios.append({
        "key": "S3", "name": "Total Assets = net (true AUM)",
        "fixed": "L = 1.1358; treat 18.7B as net AUM (not post-leverage)",
        "solved_for": "SpaceX mark",
        "leverage": round(L0, 4),
        "net_aum_usd": round(TA_4, 0),
        "gross_ta_usd": round(TA_4 * L0, 0),
        "spacex_value_usd": round(spx4_3, 0),
        "spacex_valuation_usd": round(val4_3, 0),
        "spacex_return": round(r_spx3, 4),
        "public_gross_usd": round(TA_4 * L0 - spx4_3, 0),
        "verdict": "consistent",
        "note": "If 18.7B is net, SpaceX backs out to ~$1.61T, still a partial re-mark.",
    })

    lo = min(s["spacex_valuation_usd"] for s in scenarios if s["verdict"] == "consistent")
    hi = max(s["spacex_valuation_usd"] for s in scenarios if s["verdict"] == "consistent")

    return {
        "meta": {
            "title": "SpaceX 6/4 re-mark — multi-scenario reconciliation",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "as_of": "2026-06-04",
            "base_valuation_usd": VAL_BASE,
            "ipo_valuation_usd": IPO_VAL,
            "observables": {
                "bptix_nav_prev": BPTIX_NAV_3, "bptix_nav_now": BPTIX_NAV_4,
                "nav_return": round(NAV_RET, 4), "public_basket_return": round(R_PUB, 5),
                "total_assets_prev_usd": TA_3, "total_assets_now_usd": TA_4,
                "spacex_prev_usd": round(SPX_3_USD, 0), "leverage_prior": round(L0, 4),
            },
            "confirmed": {
                "spacex_value_usd": round(SPX_3_USD * 135.0 / 105.32, 0),   # ~$4.99B
                "per_share_old_split_adj": 105.32, "per_share_new": 135.0,
                "per_share_remark_pct": round(135.0 / 105.32 - 1, 4),        # +28.2%
                "valuation_post_money_usd": IPO_VAL,
                "basis": ("Baron S-1: SpaceX common repriced $135.00 (preferred $6,750) on 2026-06-04. "
                          "Holding re-marks by per-share $105.32->$135 (+28.2%) to ~$4.99B -- NOT by "
                          "$1.77T/$1.25T (+41.6%, which double-counts IPO dilution). Explains the +6.6% NAV."),
            },
            "conclusion": ("Confirmed by Baron S-1: 6/4 SpaceX common repriced to $135/share (+28.2%% vs "
                           "$105.32), holding $3.89B -> ~$4.99B. $1.77T is the post-money whole-company "
                           "valuation, not to be applied to the holding. (The earlier S1/S3 back-outs of "
                           "$%.2f-$%.2fT agree; net basis confirmed by the 5/31 disclosure of SpaceX 23.2%%.)"
                           % (lo / 1e12, hi / 1e12)),
            "disclaimer": ("SpaceX $-to-price mapping linear off the 3/31 NPORT anchor ($3.89B @ $105.32 "
                           "split-adj). 6/4 reprice per Baron S-1. Next NPORT (period 6/30, ~late Aug) is the "
                           "next hard confirmation. Not investment advice."),
        },
        "scenarios": scenarios,
        "consistent_range_usd": [lo, hi],
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "spacex_remark.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    o = pl["meta"]["observables"]
    print("OBSERVABLES nav %.2f->%.2f (%.2f%%) | public basket %.3f%% | TA %.1f->%.1fB"
          % (o["bptrx_nav_prev"], o["bptrx_nav_now"], o["nav_return"] * 100,
             o["public_basket_return"] * 100, o["total_assets_prev_usd"] / 1e9,
             o["total_assets_now_usd"] / 1e9))
    for s in pl["scenarios"]:
        if s["solved_for"] == "SpaceX mark":
            print("[%s] solve SpaceX -> $%.2fB (%.1f%%) = $%.3fT  [%s]" % (
                s["key"], s["spacex_value_usd"] / 1e9, s["spacex_return"] * 100,
                s["spacex_valuation_usd"] / 1e12, s["verdict"]))
        else:
            print("[%s] solve leverage -> %.3fx  [%s]" % (
                s["key"], s["implied_leverage"], s["verdict"]))
    r = pl["consistent_range_usd"]
    print("consistent SpaceX range: $%.3fT - $%.3fT" % (r[0] / 1e12, r[1] / 1e12))
    p = write_json()
    print("wrote", p)
