"""
SpaceX position breakdown -> dashboard/data/spacex_position.json

Answers three things the rest of the dashboard kept asserting without showing:
  1. WHERE the "~$262M Friday SpaceX buy" number comes from (full derivation).
  2. At what PRICE / how many SHARES that buy was (and why the $ is a close-mark,
     not necessarily the cash).
  3. The CURRENT SpaceX holding split into (a) the pre-IPO disclosed position vs
     (b) the 6/12 IPO-day add, valued at each daily mark.

Everything is sourced: the pre-IPO basis is the 3/31 NPORT-P gross LMV; the marks
are the SPCX closes from the daily log; the buy is the recalibration's back-solve.
Pure stdlib, network-free (reads recalibration.json + the daily-log marks).
"""

import json
import os

import daily_nav_log as dl

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

# Pre-IPO SpaceX position: 3/31 NPORT-P gross LMV at the $1.25T merger mark, split-adj.
PRE_BASIS_USD = 3.89026788e9
PRE_PER_SHARE = 105.32          # $/sh, 5-for-1 split-adjusted ($526.59 / 5)
PRE_SHARES = PRE_BASIS_USD / PRE_PER_SHARE   # ~36.94M split-adj shares

IPO_PRICE = 135.0               # 6/12 IPO price
VWAP_EST = 162.91               # ~6/12 VWAP (typical price); used for the cash range only


def _marks():
    """SPCX close per date from the daily log (BASE + ENTRIES). Latest = current mark."""
    m = [(dl.BASE["date"], dl.BASE["spcx"])]
    for e in dl.ENTRIES:
        m.append((e["date"], e["spcx"]))
    return m


def _buy():
    """Friday (6/12) SpaceX add, from the recalibration's back-solve (close-marked $)."""
    try:
        b = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "recalibration.json"),
                           encoding="utf-8"))["belief"]["posterior"]
        return b["friday_buy_m"] * 1e6, [x * 1e6 for x in b["friday_buy_band_m"]]
    except Exception:
        return 262e6, [259e6, 344e6]


def _derivation(buy_usd, fri_close):
    """The step-by-step back-solve of the Friday buy (what the user couldn't find)."""
    return [
        {"step": "Observe 6/15", "detail": "BPTIX NAV 289.98 -> 307.55 = +6.06%. SPCX 160.95 -> 192.50 = +19.6%. "
         "Public basket ~flat (+0.02% to +0.14% across the disclosed weightings)."},
        {"step": "Required SpaceX weight", "detail": "For NAV +6.06% with a ~flat basket and SpaceX +19.6%, the "
         "start-of-Monday SpaceX weight must be (6.06% - basket)/(19.6% - basket) ~= 30.4% of net."},
        {"step": "No-buy baseline", "detail": "Carrying only the disclosed 3/31 shares: SpaceX $5.945B at the 6/12 "
         "close ($160.95) / AUM $20.4B = 29.14%."},
        {"step": "The gap = a buy", "detail": "30.4%% implies SpaceX $ at the 6/12 close = 30.4%% x $20.4B = $6.21B, "
         "vs the $5.945B no-buy mark -> ~$%.0fM EXTRA SpaceX value was on the books Friday close = the IPO-day add."
         % (buy_usd / 1e6)},
        {"step": "Shares & price", "detail": "$%.0fM / $%.2f close = ~%.2fM shares added. Cash spent = shares x the "
         "execution price: ~$%.0fM if IPO-allocated at $%.0f, ~$%.0fM at the ~$%.2f VWAP. The $%.0fM everyone quotes "
         "is the Friday-CLOSE marked value, not necessarily the cash."
         % (buy_usd / 1e6, fri_close, buy_usd / fri_close / 1e6,
            buy_usd / fri_close * IPO_PRICE / 1e6, IPO_PRICE,
            buy_usd / fri_close * VWAP_EST / 1e6, VWAP_EST, buy_usd / 1e6)},
    ]


def build_payload():
    marks = _marks()
    fri_date, fri_close = marks[0]                 # 6/12 close = the buy's mark
    cur_date, cur_mark = marks[-1]                 # latest SPCX mark
    buy_usd, buy_band = _buy()
    buy_shares = buy_usd / fri_close
    pre_cash_low = buy_shares * IPO_PRICE          # if IPO-allocated at $135
    pre_cash_vwap = buy_shares * VWAP_EST          # if bought at the day's VWAP

    def row(date, px):
        pre = PRE_SHARES * px
        fri = buy_shares * px
        return {"date": date, "spcx": px, "pre_ipo_usd": round(pre, 0), "friday_usd": round(fri, 0),
                "total_usd": round(pre + fri, 0), "friday_pct": round(fri / (pre + fri) * 100, 2)}

    value_path = [row(d, px) for d, px in marks]
    cur = value_path[-1]
    total_shares = PRE_SHARES + buy_shares

    # per-BPTIX-share look-through: how many SpaceX shares back one BPTIX share.
    # BPTIX shares outstanding = AUM / NAV (latest day where both are known).
    au = nv = audate = None
    for e in dl.ENTRIES:
        if e.get("aum") and e.get("actual_nav"):
            au, nv, audate = float(e["aum"]), e["actual_nav"], e["date"]
    if au is None:
        au, nv, audate = dl.BASE["aum"], dl.BASE["nav"], dl.BASE["date"]
    bptix_shares_out = au / nv
    spx_per_bptix = total_shares / bptix_shares_out          # SpaceX shares per 1 BPTIX share
    usd_per_bptix = spx_per_bptix * cur_mark                 # $ of SpaceX per BPTIX share (latest mark)

    return {
        "meta": {
            "title": "SpaceX position — pre-IPO holding vs the 6/12 IPO-day buy",
            "as_of": cur_date,
            "headline": ("The fund's SpaceX holding = the disclosed pre-IPO position (3/31 NPORT) PLUS a ~%.1fM-share "
                         "add on the 6/12 IPO day. The '$%.0fM Friday buy' is that add valued at the 6/12 close."
                         % (buy_shares / 1e6, buy_usd / 1e6)),
            "disclaimer": "The IPO-day add is an ESTIMATE back-solved from 6/15's NAV (band $%.0f-%.0fM); the pre-IPO "
                          "position is the disclosed 3/31 figure. Share count is split-adjusted (post 5-for-1)."
                          % (buy_band[0] / 1e6, buy_band[1] / 1e6),
        },
        "derivation": _derivation(buy_usd, fri_close),
        "pre_ipo": {"shares": round(PRE_SHARES, 0), "per_share_basis": PRE_PER_SHARE,
                    "basis_value_3_31": PRE_BASIS_USD, "source": "3/31 NPORT-P SpaceX gross LMV, $1.25T merger mark"},
        "friday_buy": {"mark_date": fri_date, "mark_close": fri_close, "close_value_usd": round(buy_usd, 0),
                       "close_value_band_usd": [round(buy_band[0], 0), round(buy_band[1], 0)],
                       "shares": round(buy_shares, 0),
                       "cash_low_usd": round(pre_cash_low, 0), "cash_low_price": IPO_PRICE,
                       "cash_vwap_usd": round(pre_cash_vwap, 0), "cash_vwap_price": VWAP_EST,
                       "ipo_intraday": "6/12 SPCX: IPO $135, open $150, low $149.34, high $176.52, close $160.95"},
        "current": {"as_of": cur_date, "spcx": cur_mark, "total_shares": round(total_shares, 0),
                    "total_value_usd": round(cur["total_usd"], 0),
                    "pre_ipo_value_usd": round(cur["pre_ipo_usd"], 0), "friday_value_usd": round(cur["friday_usd"], 0),
                    "friday_pct": cur["friday_pct"],
                    "spx_shares_per_bptix": round(spx_per_bptix, 4), "usd_per_bptix": round(usd_per_bptix, 2),
                    "lookthrough_basis": "%s AUM $%.1fB / NAV $%.2f = %.1fM BPTIX shares" % (audate, au / 1e9, nv, bptix_shares_out / 1e6)},
        "value_path": value_path,
    }


def write_json():
    payload = build_payload()
    out = os.path.join(_REPO_ROOT, "dashboard", "data", "spacex_position.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return out


if __name__ == "__main__":
    p = build_payload()
    print(p["meta"]["title"], "| as of", p["meta"]["as_of"])
    fb = p["friday_buy"]
    print("Friday buy: $%.0fM close-value = %.2fM shares @ $%.2f close (cash $%.0fM @IPO$135 .. $%.0fM @VWAP$%.2f)"
          % (fb["close_value_usd"] / 1e6, fb["shares"] / 1e6, fb["mark_close"],
             fb["cash_low_usd"] / 1e6, fb["cash_vwap_usd"] / 1e6, fb["cash_vwap_price"]))
    c = p["current"]
    print("Current (%s): %.2fM shares = $%.2fB (pre-IPO $%.2fB + Friday $%.0fM = %.1f%%)"
          % (c["as_of"], c["total_shares"] / 1e6, c["total_value_usd"] / 1e9,
             c["pre_ipo_value_usd"] / 1e9, c["friday_value_usd"] / 1e6, c["friday_pct"]))
    for s in p["derivation"]:
        print(" -", s["step"] + ":", s["detail"])
    print("wrote", write_json())
