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
    rows = []
    for tk, name, fsh, fval, px, ush, uval in legs:
        fw = fval / fund_total
        uw = uval / short_total
        target_sh = round(fsh * scale)                    # shares to match the fund weight exactly
        rows.append({
            "ticker": tk.replace("-", "/"), "name": name,
            "fund_shares": fsh, "fund_value": round(fval, 0), "fund_weight": round(fw, 4),
            "our_shares": ush, "our_value": round(uval, 0), "our_weight": round(uw, 4),
            "diff_pp": round((uw - fw) * 100, 2),
            "diff_usd": round((uw - fw) * short_total, 0),  # $ of this name over/under-hedged
            "target_shares": target_sh,
            "delta_shares": target_sh - ush,                 # +add / -trim to match
            "ratio_inv": round(fsh / ush) if ush else None,  # fund holds 1 per N of ours
        })
    rows.sort(key=lambda r: r["diff_pp"])                 # most UNDER-shorted first

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
    print("%-7s %8s %8s %7s %11s %9s" % ("ticker", "fundWt", "ourWt", "diff", "diff$", "addShares"))
    for r in pl["rows"]:
        print("%-7s %7.1f%% %7.1f%% %+6.1f %11s %+9d"
              % (r["ticker"], r["fund_weight"] * 100, r["our_weight"] * 100, r["diff_pp"],
                 "$%.0fk" % (r["diff_usd"] / 1e3), r["delta_shares"]))
    p = write_json()
    print("wrote", p)
