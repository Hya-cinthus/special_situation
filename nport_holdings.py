"""
Baron Partners Fund — Portfolio of Investments, 2026-03-31 (UNAUDITED)
-> dashboard/data/nport_holdings.json

Verbatim from the fund's shareholder-report Portfolio of Investments (the two
images the user supplied). This is the authoritative holdings record: exact share
counts, cost, and market value per position. It anchors every SpaceX number on the
dashboard and the full valuation reconciliation (3/31 mark -> 6/4 IPO reprice ->
the $1.77T cap table).

Cross-checks that MUST hold (all verified in build_payload):
  - SpaceX (5 classes) value sums to $3,890,267,879  == footnote 3 "restricted
    securities ... 37.43% of net assets"
  - Total Investments value sums to $11,782,549,084  (113.35% of net)
  - Net Assets = Total Investments + (Liabilities less Cash & Other) = $10,394,470,144
Pure stdlib.
"""

import json
import os
import datetime

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

AS_OF = "2026-03-31"
NET_ASSETS = 10_394_470_144            # stated Net Assets
TOTAL_INVESTMENTS = 11_782_549_084     # Total Investments (113.35% of net)
LIAB_LESS_CASH = -1_388_078_940        # Liabilities Less Cash and Other Assets (-13.35%)

# IPO reprice facts (Baron S-1; 5-for-1 split of COMMON only, effective 2026-05-04)
SPLIT_RATIO = 5
IPO_COMMON_PX = 135.00                  # Class A IPO price
IPO_PREFERRED_PX = 6_750.00            # private preferred reprice (= 50 x common)
IPO_VALUATION_POST_MONEY = 1.77e12

# --- Full holdings (section, sub_industry, name, shares, cost, value) ----------
HOLDINGS = [
    # Common Stocks (75.93%)
    ("Common", "Communication Services", "Spotify Technology SA", 524_000, 187_026_515, 254_092_840),
    ("Common", "Consumer Discretionary", "Tesla, Inc.", 6_455_000, 95_897_630, 2_399_646_250),
    ("Common", "Consumer Discretionary", "Red Rock Resorts, Inc., Cl A", 3_140_000, 142_345_674, 167_550_400),
    ("Common", "Consumer Discretionary", "Birkenstock Holding PLC", 3_490_000, 148_751_040, 125_046_700),
    ("Common", "Consumer Discretionary", "On Holding AG, Cl A", 2_948_579, 112_584_294, 100_310_657),
    ("Common", "Consumer Discretionary", "Choice Hotels International, Inc.", 2_488_000, 248_875_789, 257_508_000),
    ("Common", "Consumer Discretionary", "Hyatt Hotels Corp., Cl A", 3_350_000, 120_944_360, 481_696_500),
    ("Common", "Consumer Discretionary", "Vail Resorts, Inc.", 1_800_000, 192_334_241, 230_976_000),
    ("Common", "Financials", "FactSet Research Systems, Inc.", 1_875_000, 411_222_334, 406_856_250),
    ("Common", "Financials", "MSCI, Inc.", 898_500, 450_508_188, 484_300_485),
    ("Common", "Financials", "The Charles Schwab Corp.", 4_865_500, 157_813_402, 457_259_690),
    ("Common", "Financials", "Arch Capital Group Ltd.", 6_175_000, 27_361_902, 592_738_250),
    ("Common", "Financials", "Kinsale Capital Group, Inc.", 368_401, 140_062_300, 125_867_886),
    ("Common", "Health Care", "IDEXX Laboratories, Inc.", 620_000, 27_074_536, 348_371_800),
    ("Common", "Industrials", "HEICO Corp.", 125_625, 9_632_520, 34_446_375),
    ("Common", "Industrials", "HEICO Corp., Cl A", 116_875, 7_586_429, 24_671_144),
    ("Common", "Industrials", "Verisk Analytics, Inc.", 746_000, 146_099_785, 141_553_500),
    ("Common", "Information Technology", "Figma, Inc., Cl A", 1_257_000, 36_904_178, 26_572_980),
    ("Common", "Information Technology", "Guidewire Software, Inc.", 1_694_550, 187_223_861, 253_436_898),
    ("Common", "Information Technology", "Shopify, Inc., Cl A", 1_960_000, 245_433_871, 232_495_200),
    ("Common", "Information Technology", "Gartner, Inc.", 2_372_500, 425_873_305, 375_661_650),
    ("Common", "Real Estate", "Gaming and Leisure Properties, Inc.", 1_775_000, 55_052_805, 78_756_750),
    ("Common", "Real Estate", "CoStar Group, Inc.", 7_250_000, 116_351_106, 292_465_000),
    # Private Common Stocks (12.76%) — SpaceX
    ("Private Common", "SpaceX (Aerospace & Defense)", "Space Exploration Technologies Corp., Cl A", 2_216_310, 29_920_185, 1_167_086_683),
    ("Private Common", "SpaceX (Aerospace & Defense)", "Space Exploration Technologies Corp., Cl C", 302_210, 4_079_835, 159_140_764),
    # Private Convertible Preferred (0.00%) — Northvolt (bankrupt, marked to 0)
    ("Private Convertible Preferred", "Unclassified", "Northvolt AB, Series E2 (Sweden)", 21_213_656, 7_843_621, 0),
    # Private Preferred Stocks (24.66%) — SpaceX
    ("Private Preferred", "SpaceX (Aerospace & Defense)", "Space Exploration Technologies Corp., Cl H", 311_111, 41_999_985, 1_638_279_415),
    ("Private Preferred", "SpaceX (Aerospace & Defense)", "Space Exploration Technologies Corp., Cl I", 131_657, 22_250_032, 693_292_596),
    ("Private Preferred", "SpaceX (Aerospace & Defense)", "Space Exploration Technologies Corp., Series N", 44_146, 11_919_420, 232_468_421),
]

_SPACEX = "Space Exploration Technologies Corp"


def _is_spacex(name):
    return name.startswith(_SPACEX)


def build_payload():
    rows = [{"section": s, "group": g, "name": n, "shares": sh, "cost": c, "value": v}
            for (s, g, n, sh, c, v) in HOLDINGS]

    # --- SpaceX detail (5 classes) -------------------------------------------
    spx = [r for r in rows if _is_spacex(r["name"])]
    for r in spx:
        r["kind"] = "common" if "Private Common" in r["section"] else "preferred"
        r["px_per_share"] = round(r["value"] / r["shares"], 2)
        # 6/4 IPO reprice: common splits 5:1 then -> $135; preferred -> $6,750.
        if r["kind"] == "common":
            r["shares_postsplit"] = r["shares"] * SPLIT_RATIO
            r["value_remark"] = round(r["shares_postsplit"] * IPO_COMMON_PX, 0)
        else:
            r["shares_postsplit"] = r["shares"]            # preferred does NOT split
            r["value_remark"] = round(r["shares"] * IPO_PREFERRED_PX, 0)
        r["remark_factor"] = round(r["value_remark"] / r["value"], 4)

    spx_value = sum(r["value"] for r in spx)
    spx_remark = sum(r["value_remark"] for r in spx)
    spx_common = sum(r["value"] for r in spx if r["kind"] == "common")
    spx_pref = sum(r["value"] for r in spx if r["kind"] == "preferred")

    total_value = sum(r["value"] for r in rows)
    public_value = total_value - spx_value

    # --- assertions (the cross-checks that must hold) -------------------------
    assert spx_value == 3_890_267_879, spx_value
    assert total_value == TOTAL_INVESTMENTS, total_value
    assert NET_ASSETS == TOTAL_INVESTMENTS + LIAB_LESS_CASH, NET_ASSETS

    leverage = TOTAL_INVESTMENTS / NET_ASSETS               # 1.1335 (= 113.35%)

    # --- $1.77T cap-table tie-out (S-1 pro forma, post-split) -----------------
    pf_classA = 6_824_581_339
    pf_classB = 5_695_729_430
    pf_common = pf_classA + pf_classB
    ipo_new = round(75e9 / IPO_COMMON_PX)                    # $75B raise / $135
    greenshoe = 83_330_000
    post_ipo_shares = pf_common + ipo_new + greenshoe
    post_ipo_val = post_ipo_shares * IPO_COMMON_PX

    # --- Share-count bridge: where the dilution comes from (S-1 exact figures) -
    # Actual common (3/31, post-split): Class A 44,444 + Class B 2,421,276,530.
    # xAI Merger (closed 2026-02-02): issued 321,681,643 Cl A + 121,683,400 Cl B.
    # The rest of the jump to pro-forma common = Preferred Conversion + Class C
    # Reclassification (SpaceX is preferred-heavy; exact split is BLANK in the
    # preliminary S-1, filled in the final 424B). Plus the IPO raise + greenshoe.
    actual_common = 44_444 + 2_421_276_530
    xai_classA, xai_classB = 321_681_643, 121_683_400
    xai_total = xai_classA + xai_classB
    pref_conv_reclass = pf_common - actual_common - xai_total   # residual (the bulk)
    dilution = {
        "actual_common": actual_common,
        "xai_merger": xai_total, "xai_classA": xai_classA, "xai_classB": xai_classB,
        "xai_date": "2026-02-02",
        "pref_conv_and_reclass": pref_conv_reclass,
        "pro_forma_common": pf_common,
        "ipo_new": ipo_new, "greenshoe": greenshoe,
        "post_ipo_common": post_ipo_shares,
        "musk_perf_classB": 200_000_000,        # granted 2026-01-13, milestone-vesting
        "musk_options_classB": 350_000_000,     # issuable on option exercise
    }
    assert actual_common + xai_total + pref_conv_reclass == pf_common

    # --- Single additive valuation bridge, ALL in post-split common shares -----
    # Start from the share count the $1.25T headline implies, add each step, end at
    # $1.77T. (preferred is folded in as converted common at 50:1.)
    OLD_PX = 526.59 / SPLIT_RATIO                              # $105.318 post-split common
    implied_125 = round(1.25e12 / OLD_PX)                      # ~11.869B
    bridge = [
        {"label": "$1.25T mark (Feb 2 headline)", "shares": implied_125, "delta": None,
         "price": round(OLD_PX, 2), "valuation": round(implied_125 * OLD_PX), "src_type": "derived",
         "source": ("DERIVED = $1.25T / $105.32. $1.25T = SpaceX+xAI merger headline (CNBC 2026-02-03). "
                    "$105.32 = $526.59 / 5 (split); $526.59 = the 3/31 NPORT mark (Baron's Cl A common "
                    "$1,167,086,683 / 2,216,310 sh). Not a directly-reported share count.")},
        {"label": "True-up to the precise 3/31 cap-table count", "shares": pf_common,
         "delta": pf_common - implied_125, "price": round(OLD_PX, 2),
         "valuation": round(pf_common * OLD_PX), "src_type": "residual",
         "source": ("RESIDUAL = exact S-1 pro-forma common (12,520,310,769) − the round-headline implied "
                    "count (11,868,816,347). No independent source: it is the gap between the round $1.25T "
                    "headline and the exact filing (at the same $105.32 the precise value is ~$1.32T — value "
                    "drifted up Feb→Mar and/or the $1.25T is rounded).")},
        {"label": "6/4 IPO price re-mark (+28.2%, NO new shares)", "shares": pf_common,
         "delta": 0, "price": IPO_COMMON_PX, "valuation": round(pf_common * IPO_COMMON_PX), "src_type": "reported",
         "source": ("REPORTED: Baron S-1 — SpaceX common reprices to $135.00 on 2026-06-04 (from $105.32). "
                    "This is the per-share gain Baron actually captures; adds no shares.")},
        {"label": "+ IPO primary raise ($75B new cash)", "shares": pf_common + ipo_new,
         "delta": ipo_new, "price": IPO_COMMON_PX, "valuation": round((pf_common + ipo_new) * IPO_COMMON_PX),
         "src_type": "derived",
         "source": ("DERIVED = $75B raise / $135 = 555.6M new Class A. $75B & $135 from CNBC IPO-priced "
                    "(2026-06-03). The preliminary S-1 leaves the offering size blank; filled in the 424B.")},
        {"label": "+ greenshoe (over-allotment)", "shares": post_ipo_shares,
         "delta": greenshoe, "price": IPO_COMMON_PX, "valuation": round(post_ipo_shares * IPO_COMMON_PX),
         "src_type": "derived",
         "source": ("DERIVED: 83.33M = 15% over-allotment (≈ $11.2B); CNBC IPO terms. Post-money = $1.77T ✓")},
    ]
    dilution["valuation_bridge"] = bridge
    dilution["implied_shares_at_125T"] = implied_125
    dilution["old_common_px_postsplit"] = round(OLD_PX, 2)

    # Source-tagged breakdown of the 12.52B pro-forma common (Table B), with a
    # RUNNING (cumulative) count so it reads like the bridge above.
    dilution["source_breakdown"] = [
        {"label": "Actual common on the books (3/31)", "delta": actual_common, "cumulative": actual_common,
         "src_type": "reported",
         "source": "S-1 cap table 'actual': Class A 44,444 + Class B 2,421,276,530."},
        {"label": "+ xAI Merger (2026-02-02)", "delta": xai_total, "cumulative": actual_common + xai_total,
         "src_type": "reported",
         "source": ("S-1: \"issued 321,681,643 shares of Class A common stock and 121,683,400 shares of "
                    "Class B common stock as partial consideration\" (common-control merger).")},
        {"label": "+ Preferred conversion + Class C reclassification", "delta": pref_conv_reclass,
         "cumulative": pf_common, "src_type": "reported-total / residual-split",
         "source": ("Residual = pro-forma common (S-1) − actual − xAI. S-1 confirms ALL preferred converts to "
                    "common and Class C reclassifies to Class A at the IPO; the exact per-line counts are "
                    "blank in the preliminary S-1 (filled in the 424B).")},
        {"label": "= Pro-forma common (3/31)", "delta": None, "cumulative": pf_common,
         "src_type": "reported",
         "source": "S-1 cap table 'pro forma': Class A 6,824,581,339 + Class B 5,695,729,430."},
    ]

    return {
        "meta": {
            "title": "Baron Partners Fund — holdings & SpaceX valuation reconciliation",
            "as_of": AS_OF,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": ("Fund shareholder-report Portfolio of Investments, 2026-03-31 (unaudited); "
                       "SpaceX 6/4 reprice + cap table from SpaceX Form S-1, SEC accession "
                       "0001628280-26-036936 (CIK 1181412)."),
            "net_assets": NET_ASSETS,
            "total_investments": TOTAL_INVESTMENTS,
            "liabilities_less_cash": LIAB_LESS_CASH,
            "leverage": round(leverage, 4),
            "spacex_value": spx_value,
            "spacex_pct_of_net": round(spx_value / NET_ASSETS, 4),     # 37.43%
            "public_value": public_value,
            "disclaimer": "Verbatim holdings (3/31/2026, unaudited). Re-mark/cap-table per Baron S-1. Not advice.",
        },
        "spacex": {
            "classes": spx,
            "value_3_31": spx_value,
            "value_common_3_31": spx_common,
            "value_preferred_3_31": spx_pref,
            "value_remark_6_4": round(spx_remark, 0),
            "remark_factor": round(spx_remark / spx_value, 4),         # ~1.282 (+28.2%)
            "total_shares_3_31": sum(r["shares"] for r in spx),
        },
        "captable": {
            "split_ratio": SPLIT_RATIO,
            "split_date": "2026-05-04",
            "pro_forma_classA": pf_classA, "pro_forma_classB": pf_classB,
            "pro_forma_common": pf_common,
            "ipo_new_shares": ipo_new, "greenshoe": greenshoe,
            "post_ipo_shares": post_ipo_shares,
            "post_ipo_valuation": round(post_ipo_val, 0),              # ~$1.77T
            "stated_valuation": IPO_VALUATION_POST_MONEY,
            "ipo_common_px": IPO_COMMON_PX, "ipo_preferred_px": IPO_PREFERRED_PX,
            "conversion_ratio": round(IPO_PREFERRED_PX / IPO_COMMON_PX),  # 50:1
            "dilution": dilution,
        },
        "holdings": rows,
        "totals": {"total_value": total_value, "public_value": public_value,
                   "spacex_value": spx_value, "net_assets": NET_ASSETS},
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "nport_holdings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = build_payload()
    m, sx, ct = p["meta"], p["spacex"], p["captable"]
    print("Net Assets $%.3fB | Total Investments $%.3fB | leverage %.4f"
          % (m["net_assets"] / 1e9, m["total_investments"] / 1e9, m["leverage"]))
    print("SpaceX 3/31 = $%.3fB (%.2f%% of net) [common $%.3fB + preferred $%.3fB]"
          % (sx["value_3_31"] / 1e9, m["spacex_pct_of_net"] * 100,
             sx["value_common_3_31"] / 1e9, sx["value_preferred_3_31"] / 1e9))
    for r in sx["classes"]:
        print("  %-12s %10s sh @ $%9.2f = $%.3fB  -> 6/4 $%.3fB (x%.3f)"
              % (r["name"].split(", ")[-1], format(r["shares"], ","), r["px_per_share"],
                 r["value"] / 1e9, r["value_remark"] / 1e9, r["remark_factor"]))
    print("SpaceX 6/4 re-mark total = $%.3fB (x%.4f, +%.1f%%)"
          % (sx["value_remark_6_4"] / 1e9, sx["remark_factor"], (sx["remark_factor"] - 1) * 100))
    print("Cap table: pro-forma common %.2fB + IPO %.0fM + green %.0fM = %.2fB x $135 = $%.3fT (stated $%.2fT)"
          % (ct["pro_forma_common"] / 1e9, ct["ipo_new_shares"] / 1e6, ct["greenshoe"] / 1e6,
             ct["post_ipo_shares"] / 1e9, ct["post_ipo_valuation"] / 1e12, ct["stated_valuation"] / 1e12))
    pth = write_json()
    print("wrote", pth)
