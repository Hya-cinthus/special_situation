"""
Hedge basket vs fund holdings — composition mismatch -> dashboard/data/basket_mismatch.json

Answers, with strict provenance: for each public name, what SHOULD its weight in the
short basket be (= the fund's own weight), what is OUR short actually, and what is the
gap (in pp, in $, and in shares-to-add).

SOURCES (labeled on the card):
  - TARGET weights  = each public holding's market value / total public common, from
    the Baron Partners Fund **Portfolio of Investments, 2026-03-31 (unaudited)** —
    the latest filed holdings (next filing 6/30). Encoded in nport_holdings.py.
  - OUR short       = the hedge book's FIXED short positions, entered **2026-05-20**.
  Both weights are computed at the SAME 3/31 NPORT prices, so the difference is purely
  the share-proportion choice (not price drift between 3/31 and 5/20).

Pure stdlib.
"""

import json
import os
import datetime

import nport_holdings
import hedge_book

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# our short ticker -> fund holding name (3/31 Portfolio of Investments)
TICKER_TO_NAME = {
    "ACGL": "Arch Capital Group Ltd.", "BIRK": "Birkenstock Holding PLC",
    "CHH": "Choice Hotels International, Inc.", "CSGP": "CoStar Group, Inc.",
    "FDS": "FactSet Research Systems, Inc.", "FIG": "Figma, Inc., Cl A",
    "GLPI": "Gaming and Leisure Properties, Inc.", "GWRE": "Guidewire Software, Inc.",
    "H": "Hyatt Hotels Corp., Cl A", "HEI": "HEICO Corp.", "HEI-A": "HEICO Corp., Cl A",
    "IDXX": "IDEXX Laboratories, Inc.", "IT": "Gartner, Inc.",
    "KNSL": "Kinsale Capital Group, Inc.", "MSCI": "MSCI, Inc.", "MTN": "Vail Resorts, Inc.",
    "ONON": "On Holding AG, Cl A", "RRR": "Red Rock Resorts, Inc., Cl A",
    "SCHW": "The Charles Schwab Corp.", "SHOP": "Shopify, Inc., Cl A",
    "SPOT": "Spotify Technology SA", "TSLA": "Tesla, Inc.", "VRSK": "Verisk Analytics, Inc.",
}


def _load(name):
    with open(os.path.join(_REPO_ROOT, "dashboard", "data", name), encoding="utf-8") as f:
        return json.load(f)


def build_payload():
    fund = {}
    for sec, grp, name, sh, cost, val in nport_holdings.HOLDINGS:
        if sec == "Common":
            fund[name] = (sh, val)
    fund_total = sum(v for _, v in fund.values())

    legs = []
    short_total = 0.0
    for tk, name in TICKER_TO_NAME.items():
        fsh, fval = fund[name]
        px = fval / fsh                                   # 3/31 NPORT price
        ush = abs(hedge_book.POSITIONS[tk])
        uval = ush * px
        short_total += uval
        legs.append((tk, name, fsh, fval, px, ush, uval))

    scale = short_total / fund_total                      # our basket = this fraction of the fund

    # --- SCALE leg: your BPTIX position's GROSS public exposure (what a FULL hedge
    # must cover) = long_notional × (leverage − SpaceX weight). The fixed short was
    # sized to ~the NET (unlevered) public book, so it misses the leverage slice.
    try:
        hb, sb = _load("hedge_book.json"), _load("spacex_baron.json")
        long_notional = hb["meta"]["long_notional"]
        w_spx = {r["date"]: r["spacex_weight"] for r in sb["series"]}["2026-05-20"]
        lev = sb["aum_overrides"][0]["leverage_ratio"]
        gross_pub_exp = long_notional * (lev - w_spx)
        net_pub_exp = long_notional * (1.0 - w_spx)
        lev_factor = gross_pub_exp / net_pub_exp
    except Exception:
        long_notional = w_spx = lev = gross_pub_exp = net_pub_exp = lev_factor = None

    rows = []
    for tk, name, fsh, fval, px, ush, uval in legs:
        fw = fval / fund_total
        uw = uval / short_total
        # Step 1 — WEIGHT fix: bring this name to the fund weight at your CURRENT
        # (net-sized) short total. target = fund_weight × short_total ÷ price.
        target_sh = round(fsh * scale)
        # Step 2 — LEVERAGE scale: multiply the whole basket up by lev_factor so it
        # covers the GROSS (levered) public book, not just the net. So:
        #   perfect_full = target_sh × lev_factor   (=> delta_full = Δweight + Δlev)
        perfect_full = round(target_sh * lev_factor) if lev_factor else None
        rows.append({
            "ticker": tk.replace("-", "/"), "name": name,
            "fund_shares": fsh, "fund_value": round(fval, 0), "fund_weight": round(fw, 4),
            "our_shares": ush, "our_value": round(uval, 0), "our_weight": round(uw, 4),
            "diff_pp": round((uw - fw) * 100, 2),
            "diff_usd": round((uw - fw) * short_total, 0),  # $ of this name over/under-weighted
            "target_shares": target_sh,                      # after WEIGHT fix (net scale)
            "delta_weight": target_sh - ush,                 # Δ from the weight fix
            "perfect_full_shares": perfect_full,             # after weight + leverage
            "delta_leverage": (perfect_full - target_sh) if perfect_full is not None else None,
            "delta_full_shares": (perfect_full - ush) if perfect_full is not None else None,
            "ratio_inv": round(fsh / ush) if ush else None,
        })
    rows.sort(key=lambda r: r["diff_pp"])                 # most UNDER-weighted first

    unders = [r for r in rows if r["diff_pp"] < -0.2]
    return {
        "meta": {
            "title": "Hedge basket vs fund holdings — composition mismatch",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "target_source": ("Baron Partners Fund Portfolio of Investments, 2026-03-31 (unaudited) — latest "
                              "filed holdings. Target weight = name's market value / total public common "
                              "($%.2fB). The fund may have rebalanced since; next filing is period 6/30." % (fund_total / 1e9)),
            "short_source": "Hedge book FIXED short positions, entered 2026-05-20 (held constant since).",
            "pricing_note": ("Both weights use the SAME 3/31 NPORT prices, so the gap is purely the "
                             "share-proportion choice, not price drift. SpaceX/private is not shortable, so "
                             "this compares only the public book."),
            "fund_public_total": round(fund_total, 0),
            "short_total": round(short_total, 0),
            "scale": round(scale, 6), "scale_inv": round(1 / scale),
            "n_under": len(unders),
            "biggest_under": rows[0]["ticker"] if rows else None,
            # scale leg (leverage)
            "long_notional": round(long_notional, 0) if long_notional else None,
            "spacex_weight_entry": round(w_spx, 4) if w_spx else None,
            "leverage": round(lev, 4) if lev else None,
            "gross_public_exposure": round(gross_pub_exp, 0) if gross_pub_exp else None,
            "net_public_exposure": round(net_pub_exp, 0) if net_pub_exp else None,
            "leverage_factor": round(lev_factor, 4) if lev_factor else None,
            # table-consistent (3/31-price) totals so the per-name math ties exactly
            "full_hedge_total": round(short_total * lev_factor, 0) if lev_factor else None,
            "leverage_slice_usd": round(short_total * (lev_factor - 1), 0) if lev_factor else None,
            "scale_note": ("Your fixed short ($24.8M) ≈ the NET (unlevered) public book; a FULL hedge needs "
                           "the GROSS public exposure = long_notional × (leverage − SpaceX wt). The gap is "
                           "the leverage slice."),
        },
        "rows": rows,
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "basket_mismatch.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    m = pl["meta"]
    print("fund public $%.2fB | our short $%.1fM = %.4f%% (1 / %d)"
          % (m["fund_public_total"] / 1e9, m["short_total"] / 1e6, m["scale"] * 100, m["scale_inv"]))
    print("lev_factor %.4f | full hedge total $%.1fM | leverage slice $%.1fM"
          % (m["leverage_factor"], m["full_hedge_total"] / 1e6, m["leverage_slice_usd"] / 1e6))
    print("%-7s %8s %8s %7s %9s %9s %9s" % ("ticker", "fundWt", "ourWt", "diff", "dWeight", "dLev", "dFull"))
    for r in pl["rows"]:
        print("%-7s %7.1f%% %7.1f%% %+6.1f %+9d %+9d %+9d"
              % (r["ticker"], r["fund_weight"] * 100, r["our_weight"] * 100, r["diff_pp"],
                 r["delta_weight"], r["delta_leverage"], r["delta_full_shares"]))
    p = write_json()
    print("wrote", p)
