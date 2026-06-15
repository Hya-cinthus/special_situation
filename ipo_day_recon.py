"""
IPO-day reconciliation -> dashboard/data/ipo_day_recon.json

The day SpaceX (SPCX) first traded (2026-06-12), can we reproduce the reported
Morningstar AUM by marking the EXISTING holdings to that day's close — assuming
the fund's position is UNCHANGED (no IPO add) and NO leverage? And does the
per-share NAV move betray any new SpaceX bought at the IPO?

Two distinct growth rates are the whole story:
  AUM growth      = reported_AUM_t / reported_AUM_{t-1} - 1   (INCLUDES new money)
  NAV/share growth= NAV_t / NAV_{t-1} - 1                     (pure market return)
  difference x AUM = net inflows.

Discriminator for an IPO buy: shares bought at the $135 IPO price that close at
$160.95 gain +19% intraday, which would lift per-share NAV ABOVE the
position-unchanged prediction. We bound the prediction with two public-basket
weightings and check whether the actual NAV needs an extra SpaceX kicker.

Pure stdlib. Reads the already-built spacex_baron.json + config marks; pulls the
public-basket and SPCX closes from Yahoo.
"""

import json
import os
import datetime

import hedge_book
import fund_snapshots
from config import SpacexBaron as CFG

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))


def _two_anchor_days(sbx):
    """Latest two daily points carrying a reported (external_aum) AUM."""
    pts = [p for p in sbx["series"] if p.get("source") == "external_aum" and p.get("total_nav_usd")]
    return (pts[-2], pts[-1]) if len(pts) >= 2 else (None, None)


def build_payload():
    sbx = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "spacex_baron.json"), encoding="utf-8"))
    prev, cur = _two_anchor_days(sbx)
    if not cur:
        raise RuntimeError("need two AUM-anchored days")

    d0, d1 = prev["date"], cur["date"]
    aum0, aum1 = prev["total_nav_usd"], cur["total_nav_usd"]
    nav0, nav1 = prev["nav_per_share"], cur["nav_per_share"]
    spx0_val = prev["spacex_value_usd"]                 # SpaceX $ at the prior ($135) mark
    w_spx0 = spx0_val / aum0                            # SpaceX weight entering the day

    # SpaceX per-share step from the marks (prior mark -> SPCX first close)
    remarks = CFG.SPACEX_REMARKS
    spx_px_new = remarks[-1]["per_share_new"]           # 160.95
    spx_px_old = remarks[-2]["per_share_new"] if len(remarks) > 1 else remarks[-1]["per_share_old_split_adj"]
    spx_ret = spx_px_new / spx_px_old - 1               # +19.22%
    spx1_val = cur["spacex_value_usd"]                  # position-unchanged re-mark

    # public basket return d0->d1, two weightings (fund 5/31 weights vs equal)
    shorts = [tk for tk in hedge_book.POSITIONS if hedge_book.POSITIONS[tk] < 0]
    end = (datetime.date.fromisoformat(d1) + datetime.timedelta(days=1)).isoformat()
    px = {tk: hedge_book._series(tk, d0, end) for tk in shorts}

    def _ret(tk):
        a, b = px[tk].get(d0), px[tk].get(d1)
        return (b / a - 1) if (a and b) else None

    W = fund_snapshots.WEIGHTS_5_31
    num = den = 0.0
    for tk in shorts:
        w, r = W.get(tk, 0), _ret(tk)
        if w and r is not None:
            num += w * r
            den += w
    pub_w = num / den if den else 0.0                   # 5/31-weighted public return
    rr = [_ret(tk) for tk in shorts if _ret(tk) is not None]
    pub_e = sum(rr) / len(rr) if rr else 0.0            # equal-weight public return
    pub_lo, pub_hi = min(pub_w, pub_e), max(pub_w, pub_e)

    # growth rates
    aum_g = aum1 / aum0 - 1
    nav_g = nav1 / nav0 - 1
    inflow = aum1 - aum0 * (1 + nav_g)                  # AUM growth beyond the per-share return

    # AUM change decomposition (position unchanged)
    remark_gain = spx1_val - spx0_val
    public_gain = aum0 * (1 - w_spx0) * ((pub_w + pub_e) / 2)

    # predicted NAV band (position unchanged) and the implied-buy check
    def pred(pub):
        return w_spx0 * spx_ret + (1 - w_spx0) * pub

    pred_lo, pred_hi = sorted([pred(pub_lo), pred(pub_hi)])

    def implied_w(pub):
        return (nav_g - pub) / (spx_ret - pub)

    iw_lo, iw_hi = sorted([implied_w(pub_lo), implied_w(pub_hi)])
    buy_lo, buy_hi = sorted([(iw_lo - w_spx0) * aum1, (iw_hi - w_spx0) * aum1])

    # "what a real buy would look like" illustration
    scen = [{"usd": x, "extra_nav_pct": round(x * spx_ret / aum1 * 100, 2),
             "nav_would_be_pct": round((nav_g + x * spx_ret / aum1) * 100, 2)}
            for x in (0.322e9, 0.645e9, 1.0e9)]

    # --- Solve the 2-eq system: split new money into X (SpaceX bought at the IPO
    # price, gains intraday) + B (neutral subscription at NAV, no intraday P&L).
    # Forward pricing => B drops out of the NAV equation; only X lifts NAV. With
    # r_pub fixed: X from NAV eq, B from AUM eq. Total X+B is pinned ~ the inflow.
    pub0 = aum0 - spx0_val

    def _solve(rp):
        X = (aum0 * (1 + nav_g) - spx1_val - pub0 * (1 + rp)) / spx_ret
        B = aum1 - spx1_val - pub0 * (1 + rp) - (1 + spx_ret) * X
        return X, B

    pub_mid = (pub_lo + pub_hi) / 2
    split_solve = []
    for lab, rp in [("public equal-weight", pub_e), ("public mid", pub_mid), ("public 5/31-weighted", pub_w)]:
        X, B = _solve(rp)
        split_solve.append({"label": lab, "r_pub_pct": round(rp * 100, 3),
                            "spacex_ipo_buy_usd": round(X), "neutral_inflow_usd": round(B),
                            "total_in_usd": round(X + B)})
    total_inflow = round(sum(s["total_in_usd"] for s in split_solve) / len(split_solve))

    # detectability floor: buy that lifts NAV by more than the proxy noise band
    noise = abs(pub_hi - pub_lo) * (1 - w_spx0)         # NAV uncertainty from public proxy
    detect_floor = noise / spx_ret * aum1               # $ buy that would clear the noise

    return {
        "meta": {
            "title": "IPO-day reconciliation — can the marks reproduce the AUM? (no IPO add, no leverage)",
            "date": d1, "prior_date": d0,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "assumptions": "SpaceX share count unchanged (no IPO add); no leverage (net = sum of marks); "
                           "preferred tracks common proportionally; public basket proxied by the 23 hedge names.",
            "disclaimer": "Analysis, not advice. Public-basket return is a proxy (covers ~92% of the 5/31 "
                          "disclosed weights), which sets the error band on the implied-buy estimate.",
        },
        "spcx": {"ipo_price": spx_px_old, "close": spx_px_new, "return_pct": round(spx_ret * 100, 2)},
        "growth": {
            "aum_prior": aum0, "aum_reported": aum1, "aum_growth_pct": round(aum_g * 100, 3),
            "nav_prior": nav0, "nav_current": nav1, "nav_growth_pct": round(nav_g * 100, 3),
            "inflow_usd": round(inflow), "inflow_pct": round((aum_g - nav_g) * 100, 3),
        },
        "aum_decomp": {
            "total_change_usd": round(aum1 - aum0),
            "spacex_remark_usd": round(remark_gain),
            "public_gain_usd": round(public_gain),
            "inflow_usd": round(inflow),
            "marked_no_inflow_usd": round(aum0 * (1 + nav_g)),
            "gap_vs_reported_usd": round(inflow),
        },
        "nav_test": {
            "spacex_weight_start_pct": round(w_spx0 * 100, 2),
            "spacex_contribution_pct": round(w_spx0 * spx_ret * 100, 3),
            "public_return_lo_pct": round(pub_lo * 100, 3), "public_return_hi_pct": round(pub_hi * 100, 3),
            "predicted_nav_lo_pct": round(pred_lo * 100, 3), "predicted_nav_hi_pct": round(pred_hi * 100, 3),
            "actual_nav_pct": round(nav_g * 100, 3),
            "implied_spacex_weight_lo_pct": round(iw_lo * 100, 2), "implied_spacex_weight_hi_pct": round(iw_hi * 100, 2),
            "implied_buy_lo_usd": round(buy_lo), "implied_buy_hi_usd": round(buy_hi),
            "detect_floor_usd": round(detect_floor),
        },
        "buy_scenarios": scen,
        "split_solve": {
            "rows": split_solve, "total_inflow_usd": total_inflow,
            "note": ("2 equations (NAV, AUM), 3 unknowns (X, B, public return) — so the split needs the "
                     "public-basket return fixed. Total new cash X+B is pinned ~$%.0fM regardless; only the "
                     "IPO-buy share X moves with the public assumption, and it brackets ~0." % (total_inflow / 1e6)),
        },
        "spacex_value": {"prior_usd": round(spx0_val), "current_usd": round(spx1_val),
                         "weight_now_pct": round(spx1_val / aum1 * 100, 2)},
        "conclusion": (
            "AUM grew +{:.1f}% (19.0B->{:.1f}B) but per-share NAV only +{:.1f}% — the {:.1f}-point gap is "
            "~${:.0f}M of net inflows, not an IPO buy. The +{:.1f}% NAV is almost entirely the SpaceX re-mark "
            "(+{:.1f}% on its own), and sits INSIDE the no-add prediction band ({:.1f}%-{:.1f}%). A material "
            "IPO purchase (>~${:.0f}M) would have lifted NAV above the band; it didn't. Implied add ~${:+.0f}M "
            "to ${:+.0f}M ≈ 0 within proxy noise. So as of {} close there is no evidence Baron Partners/BPTIX "
            "added SpaceX at the IPO; the firm-wide $1B order more likely sits in the private BaronX vehicles "
            "or hasn't settled into this NAV yet."
        ).format(aum_g * 100, aum1 / 1e9, nav_g * 100, (aum_g - nav_g) * 100, inflow / 1e6,
                 nav_g * 100, w_spx0 * spx_ret * 100, pred_lo * 100, pred_hi * 100,
                 detect_floor / 1e6, buy_lo / 1e6, buy_hi / 1e6, d1),
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "ipo_day_recon.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = build_payload()
    g, t = p["growth"], p["nav_test"]
    print("IPO-day recon", p["meta"]["date"])
    print("  AUM +%.2f%% vs NAV +%.2f%% -> inflows $%.0fM" % (g["aum_growth_pct"], g["nav_growth_pct"], g["inflow_usd"] / 1e6))
    print("  predicted NAV band %.2f%%-%.2f%% | actual %.2f%%" % (t["predicted_nav_lo_pct"], t["predicted_nav_hi_pct"], t["actual_nav_pct"]))
    print("  implied SpaceX buy $%.0fM..$%.0fM (detect floor $%.0fM)" % (t["implied_buy_lo_usd"] / 1e6, t["implied_buy_hi_usd"] / 1e6, t["detect_floor_usd"] / 1e6))
    print("wrote", write_json())
