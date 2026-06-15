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

ORDER_CAP = 1_000_000_000   # Baron's news-confirmed ~$1B firm-wide SpaceX IPO order (BPTIX <= this)
LEV_CAP = 1.25              # leverage ceiling 1.25x (user-specified working cap; mandate max is 1.5x)


def _two_anchor_days(sbx):
    """Latest two daily points carrying a reported (external_aum) AUM."""
    pts = [p for p in sbx["series"] if p.get("source") == "external_aum" and p.get("total_nav_usd")]
    return (pts[-2], pts[-1]) if len(pts) >= 2 else (None, None)


def _ohlc(tk, day):
    """Yahoo OHLC for one ticker on one date (for the SPCX intraday range)."""
    import urllib.request

    def ep(x):
        return int(datetime.datetime.strptime(x, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())
    lo = (datetime.date.fromisoformat(day) - datetime.timedelta(days=2)).isoformat()
    hi = (datetime.date.fromisoformat(day) + datetime.timedelta(days=2)).isoformat()
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
         f"?period1={ep(lo)}&period2={ep(hi)}&interval=1d")
    try:
        j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        r = j["chart"]["result"][0]
        q = r["indicators"]["quote"][0]
        for i, t in enumerate(r["timestamp"]):
            if datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat() == day:
                return {"open": round(q["open"][i], 2), "high": round(q["high"][i], 2),
                        "low": round(q["low"][i], 2), "close": round(q["close"][i], 2)}
    except Exception:
        pass
    return None


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
    # public-basket return d0->d1 is KNOWN market data; only the WEIGHTING is a
    # choice. We use the fund's three disclosed weight versions (3/31 NPORT, 4/30,
    # 5/31 back-solve; 5/31 includes an SPY residual). 5/31 is freshest -> the
    # central estimate; the spread across versions is the (small) error band.
    wsets = [("3/31", fund_snapshots.WEIGHTS_3_31), ("4/30", fund_snapshots.WEIGHTS_4_30),
             ("5/31", fund_snapshots.WEIGHTS_5_31)]
    # ALSO pull the best-fit baskets from the hedge study (optimal min-variance, blend)
    # as extra weight versions for the locus chart — their weights are the data-driven
    # estimate of the fund's effective public exposure.
    extra_wsets = []
    try:
        H = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "hedge_book.json"), encoding="utf-8"))
        comps = H["meta"]["basket_compositions"]
        for m, lab in (("optimal", "optimal (min-var)"), ("blend", "blend 4/30+5/31")):
            if m in comps:
                extra_wsets.append((lab, {r["ticker"].replace("/", "-"): r["weight"] for r in comps[m]}))
    except Exception:
        pass
    locus_wsets = wsets + extra_wsets
    allnames = sorted(set().union(*[set(w) for _, w in locus_wsets]))
    px = {tk: hedge_book._series(tk, d0, end) for tk in allnames}

    def _ret(tk):
        a, b = px.get(tk, {}).get(d0), px.get(tk, {}).get(d1)
        return (b / a - 1) if (a and b) else None

    def _basket(W):
        num = den = 0.0
        for tk, w in W.items():
            r = _ret(tk)
            if w and r is not None:
                num += w * r
                den += w
        return num / den if den else 0.0

    pub_by_version = {lab: _basket(W) for lab, W in locus_wsets}
    pub_central = pub_by_version["5/31"]               # freshest = the estimate
    pub_vals = [pub_by_version[lab] for lab, _ in wsets]   # band from the 3 disclosed only
    pub_lo, pub_hi = min(pub_vals), max(pub_vals)

    # growth rates
    aum_g = aum1 / aum0 - 1
    nav_g = nav1 / nav0 - 1
    inflow = aum1 - aum0 * (1 + nav_g)                  # AUM growth beyond the per-share return

    # AUM change decomposition (position unchanged)
    remark_gain = spx1_val - spx0_val
    public_gain = aum0 * (1 - w_spx0) * pub_central

    # predicted NAV band (position unchanged) and the implied-buy check
    def pred(pub):
        return w_spx0 * spx_ret + (1 - w_spx0) * pub

    pred_lo, pred_hi = sorted([pred(pub_lo), pred(pub_hi)])
    pred_central = pred(pub_central)

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

    split_solve = []
    for lab, _W in wsets:
        rp = pub_by_version[lab]
        X, B = _solve(rp)
        split_solve.append({"label": "fund " + lab + " weights", "r_pub_pct": round(rp * 100, 3),
                            "spacex_ipo_buy_usd": round(X), "neutral_inflow_usd": round(B),
                            "total_in_usd": round(X + B), "is_central": lab == "5/31"})
    total_inflow = round(sum(s["total_in_usd"] for s in split_solve) / len(split_solve))

    # --- Boundary: a SpaceX buy at an UNKNOWN price. The NAV pins the trade's P&L
    # (= the small leftover), NOT its size. Bound the buy across extreme prices: a
    # buy below the close gains intraday (would lift NAV -> ruled out beyond ~0); a
    # buy AT the close has 0 P&L -> invisible to NAV (limited only by available cash).
    g_actual = nav_g * aum0
    g_spx_exist = spx0_val * spx_ret
    leftover = g_actual - g_spx_exist - pub0 * pub_central    # ~ -$47M
    close_px, ipo_px = spx_px_new, spx_px_old
    bound_rows = []
    for P in (ipo_px, round((ipo_px + close_px) / 2, 2), close_px,
              round(close_px * 1.025, 2), round(close_px * 1.12, 2)):
        ret = close_px / P - 1
        if abs(ret) < 1e-4:
            bound_rows.append({"price": P, "ret_pct": 0.0, "max_buy_usd": None,
                               "verdict": "invisible to NAV (0 intraday P&L) — limited only by cash"})
        else:
            C = leftover / ret
            bound_rows.append({"price": P, "ret_pct": round(ret * 100, 1), "max_buy_usd": round(C),
                               "verdict": "ruled out (a gain would push NAV above actual)" if C < 0 else "consistent"})
    bounds = {
        "leftover_trading_pnl_usd": round(leftover), "close_px": close_px, "ipo_px": ipo_px,
        "cash_funded_max_usd": total_inflow, "rows": bound_rows,
        "mechanics": ("Forward pricing: same-day subscriptions strike at the CLOSING NAV, so they don't "
                      "dilute or drag that day's per-share NAV; the cash drags returns only later, until "
                      "deployed. Share count changes at the close; actual holdings change when the manager "
                      "trades — possibly days later and at market, which stays invisible to daily NAV/AUM."),
        "summary": ("The NAV pins the trade's P&L (~$%.0fM, ~0), not its size. A buy below the $%.2f close "
                    "is ruled out (it would lift NAV above the actual); a buy AT the close has ~0 P&L and is "
                    "invisible — indistinguishable from a cash subscription, bounded only by the ~$%.0fM of "
                    "new cash (more if funded by selling public). So: no cheap / IPO-priced grab, but an "
                    "at-market add up to ~$%.0fM cannot be excluded. Only the 6/30 NPORT share count settles it."
                    % (leftover / 1e6, close_px, total_inflow / 1e6, total_inflow / 1e6)),
    }

    # --- All-SpaceX counter-test: force B=0 (every new dollar buys SpaceX). Cash
    # spent C = the inflow (pinned); closing value V = aum1 - existing marked. The
    # implied avg execution price P = C * close / V. If the actual NAV sits BELOW
    # the no-add line, the buy must lose intraday -> P lands ABOVE the close.
    spcx_ohlc = _ohlc("SPCX", d1)
    allspx_rows = []
    for lab, _W in wsets:
        rp = pub_by_version[lab]
        V = aum1 - spx1_val - pub0 * (1 + rp)           # closing value of the new SpaceX
        P = inflow * close_px / V if V else None
        allspx_rows.append({"label": "fund " + lab, "r_pub_pct": round(rp * 100, 3),
                            "exec_price": round(P, 2) if P else None,
                            "premium_to_close_pct": round((P / close_px - 1) * 100, 1) if P else None,
                            "above_intraday_high": bool(spcx_ohlc and P and P > spcx_ohlc["high"])})
    p_lo = min(r["exec_price"] for r in allspx_rows)
    p_hi = max(r["exec_price"] for r in allspx_rows)
    all_spacex = {
        "cash_spent_usd": round(inflow), "close_px": close_px, "intraday": spcx_ohlc,
        "rows": allspx_rows, "exec_price_lo": p_lo, "exec_price_hi": p_hi,
        "summary": ("Force B=0 — every new dollar buys SpaceX. Cash spent = the ${:.0f}M inflow (pinned); "
                    "to match BOTH the NAV and the AUM the average execution price must be ${:.0f}-${:.0f} "
                    "— ABOVE the ${:.2f} close{}. The day's range was only ${}-${}, so that's impossible "
                    "(you can't buy above the high). The reason is counter-intuitive: the actual NAV sits "
                    "slightly BELOW the no-add line, so any SpaceX added must LOSE intraday — i.e. be bought "
                    "ABOVE the close, not cheaply. This rules out 'all the new money was a SpaceX buy' and "
                    "is the opposite of a cheap grab. The only buy that fits the data is one made AT the "
                    "close (≈0 P&L, invisible), up to the ~${:.0f}M cash.").format(
                        inflow / 1e6, p_lo, p_hi, close_px,
                        (" and even above the $%.2f intraday high" % spcx_ohlc["high"]) if spcx_ohlc else "",
                        ("%.2f" % spcx_ohlc["low"]) if spcx_ohlc else "?",
                        ("%.2f" % spcx_ohlc["high"]) if spcx_ohlc else "?",
                        inflow / 1e6),
    }

    # --- Funding channels incl. LEVERAGE. Given Baron's never-sell style, any add is
    # funded by subscriptions or borrowing, not by selling. Leverage opens a channel
    # invisible to BOTH NAV and AUM (only the gross/net ratio moves) -> the real upper
    # bound on an undetectable at-market add is the borrow cap, not the inflow.
    borrow_cap = aum1 * 0.5            # mandate: borrow up to 1/3 of gross -> gross <= 1.5x net
    funding = {
        "net_aum_usd": aum1, "borrow_cap_usd": round(borrow_cap), "gross_cap_usd": round(aum1 * 1.5),
        "subscription_cap_usd": round(inflow),
        "hist_leverage": {"2026-03-31": 1.134, "2026-04-30": 1.071, "2026-05-31": 0.968},
        "channels": [
            {"funding": "New subscriptions", "cheap_buy": "ruled out (NAV would spike)",
             "at_market_buy": "visible in AUM (≤ ~$" + str(round(inflow / 1e6)) + "M inflow); NAV-neutral"},
            {"funding": "Leverage (borrow)", "cheap_buy": "ruled out (NAV would spike)",
             "at_market_buy": "INVISIBLE to NAV & AUM — only gross/net moves; up to ~$" + str(round(borrow_cap / 1e9, 1)) + "B"},
            {"funding": "Sell old holdings", "cheap_buy": "excluded", "at_market_buy": "excluded — Baron's never-sell style"},
        ],
        "summary": ("Nothing extreme actually happened: the +" + str(round(nav_g * 100, 1)) + "% NAV is almost "
                    "entirely the existing SpaceX re-marking +" + str(int(round(spx_ret * 100))) + "% (+"
                    + str(round(w_spx0 * spx_ret * 100, 1)) + "% on its own) plus ~+0.7% public; the leftover "
                    "is only ~−0.25% (model noise — public-return estimate, a possible small lockup mark-discount, "
                    "or cash). The 'extreme' $" + str(p_lo) + "–$" + str(p_hi) + " price in 5 only appears because "
                    "a tiny ~−$47M residual is forced onto a small buy. With leverage in play: Baron never sells, "
                    "so any add is funded by subscriptions OR borrowing. A cheap / IPO-priced add is ruled out "
                    "under every funding (it spikes NAV). An at-market add is NAV-neutral, and if funded by "
                    "leverage it is AUM-neutral too — invisible up to the ~$" + str(round(borrow_cap / 1e9, 1))
                    + "B borrow cap. So one day of NAV+AUM CANNOT rule out a sizeable at-market leveraged add; "
                    "only the 6/30 NPORT (share count) or a gross-vs-net leverage read settles it."),
    }

    # --- (amount x avg-execution-price) locus for a SpaceX buy. The NAV pins
    # C*(close/P - 1) = leftover(version) -> P(C) = close / (1 + leftover/C). One
    # curve per weight version; the JS draws it with the day's range shaded so you
    # can see where a buy is physically possible (P within the day's range).
    locus_versions = []
    for lab, _W in locus_wsets:
        rp = pub_by_version[lab]
        lo = nav_g * aum0 - spx0_val * spx_ret - pub0 * rp
        cmin = (abs(lo) / (spcx_ohlc["high"] / close_px - 1)) if spcx_ohlc else None
        # price implied at the $1B order cap (if the buy is the full $1B)
        p_at_order = (close_px / (1 + lo / ORDER_CAP)) if ORDER_CAP else None
        fundlab = lab if lab.startswith(("optimal", "blend")) else "fund " + lab
        locus_versions.append({"label": fundlab, "r_pub_pct": round(rp * 100, 3),
                               "leftover_usd": round(lo),
                               "min_plausible_buy_usd": round(cmin) if cmin else None,
                               "price_at_order_cap": round(p_at_order, 2) if p_at_order else None,
                               "is_central": lab == "5/31"})
    cmin_c = next((v["min_plausible_buy_usd"] for v in locus_versions if v["is_central"]), None)
    p_at_order_c = next((v["price_at_order_cap"] for v in locus_versions if v["is_central"]), None)
    lo_c = next((v["leftover_usd"] for v in locus_versions if v["is_central"]), 0)
    spx_c_pct = w_spx0 * spx_ret * 100                 # existing SpaceX re-mark contribution
    pub_c_pct = pub0 * pub_central / aum0 * 100         # public contribution (5/31)
    buy_c_pct = lo_c / aum0 * 100                       # the buy's P&L = leftover, as % of NAV
    nav_identity = ("How every point reconciles (5/31): actual +" + str(round(nav_g * 100, 2))
                    + "% NAV = +" + str(round(spx_c_pct, 2)) + "% (existing SpaceX re-marking +"
                    + str(int(round(spx_ret * 100))) + "%) + " + str(round(pub_c_pct, 2)) + "% (public book) "
                    + ("+" if buy_c_pct >= 0 else "") + str(round(buy_c_pct, 2))
                    + "% (the new buy's intraday P&L = the leftover). EVERY point on the curve produces that "
                    "same " + str(round(buy_c_pct, 2)) + "% buy-P&L — only the size×price split moves: P&L = "
                    "C × (close/P − 1), held fixed at $" + str(round(lo_c / 1e6)) + "M.")

    # Two hard caps on how much SpaceX BPTIX could have bought:
    #  (1) Baron's news-confirmed ~$1B firm-wide order (BPTIX <= this).
    #  (2) Leverage cap 1.25x: max SpaceX add = (1.25 - entry leverage) x net base.
    #      Two timing cases for the base: Thu close (no Fri inflow) vs Fri (incl inflow).
    L_entry = 0.968                                    # most recent (5/31) net-cash leverage
    lev_cap_thu = (LEV_CAP - L_entry) * aum0           # base = Thu net (no new money)
    lev_cap_fri = (LEV_CAP - L_entry) * aum1           # base = Fri net (new money leverable too)
    price_locus = {
        "close_px": close_px, "ipo_px": ipo_px,
        "intraday_high": spcx_ohlc["high"] if spcx_ohlc else None,
        "intraday_low": spcx_ohlc["low"] if spcx_ohlc else None,
        "net_flow_usd": round(inflow), "versions": locus_versions,
        "order_cap_usd": ORDER_CAP, "lev_cap": LEV_CAP, "entry_leverage": L_entry,
        "lev_cap_thu_usd": round(lev_cap_thu), "lev_cap_fri_usd": round(lev_cap_fri),
        "feasible_lo_usd": round(cmin_c) if cmin_c else None, "feasible_hi_usd": ORDER_CAP,
        "nav_identity": nav_identity,
        "spx_contrib_pct": round(spx_c_pct, 2), "actual_nav_pct": round(nav_g * 100, 2),
        "aum_prior_usd": round(aum0),
        "note": ("Curve: avg price P(C) = close / (1 + leftover/C); P is always above the $" + str(close_px)
                 + " close, so a buy is only real where P ≤ the day's $" + (str(spcx_ohlc["high"]) if spcx_ohlc else "?")
                 + " high → C ≥ ~$" + (str(round((cmin_c or 0) / 1e6)) if cmin_c else "?") + "M. TWO hard caps box "
                 "the buy in: Baron's news-confirmed $1B order (BPTIX ≤ $1B) and the 1.25× leverage ceiling "
                 "(headroom ~$" + str(round(lev_cap_thu / 1e9, 1)) + "B on Thu's base, ~$" + str(round(lev_cap_fri / 1e9, 1))
                 + "B if Fri's inflow is leverable too — both far above $1B, so the ORDER binds). Net flow is "
                 "fixed at +$" + str(round(inflow / 1e6)) + "M, so a >$357M buy must be LEVERAGE-funded. Feasible "
                 "interval (if a buy happened at all): ~$" + (str(round((cmin_c or 0) / 1e6)) if cmin_c else "?")
                 + "M–$1B, at ~$" + (str(p_at_order_c) if p_at_order_c else "?") + "–$"
                 + (str(spcx_ohlc["high"]) if spcx_ohlc else "?") + " — a tight, plausible band."),
    }

    # detectability floor: buy that lifts NAV by more than the proxy noise band
    noise = abs(pub_hi - pub_lo) * (1 - w_spx0)         # NAV uncertainty from public proxy
    detect_floor = noise / spx_ret * aum1               # $ buy that would clear the noise

    return {
        "meta": {
            "title": "IPO-day reconciliation — can the marks reproduce the AUM? (no IPO add, no leverage)",
            "date": d1, "prior_date": d0,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "assumptions": "SpaceX share count unchanged (no IPO add); no leverage (net = sum of marks); "
                           "preferred tracks common proportionally. Public-basket return = known stock "
                           "returns x the fund's disclosed weights (3/31 NPORT, 4/30, 5/31 back-solve).",
            "disclaimer": "Analysis, not advice. The public return is KNOWN (market data); only the weighting "
                          "is a choice — 5/31 is freshest (the estimate), the 3/31->5/31 spread is the band.",
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
            "public_return_central_pct": round(pub_central * 100, 3),
            "predicted_nav_lo_pct": round(pred_lo * 100, 3), "predicted_nav_hi_pct": round(pred_hi * 100, 3),
            "predicted_nav_central_pct": round(pred_central * 100, 3),
            "actual_nav_pct": round(nav_g * 100, 3),
            "implied_spacex_weight_lo_pct": round(iw_lo * 100, 2), "implied_spacex_weight_hi_pct": round(iw_hi * 100, 2),
            "implied_buy_lo_usd": round(buy_lo), "implied_buy_hi_usd": round(buy_hi),
            "detect_floor_usd": round(detect_floor),
        },
        "buy_scenarios": scen,
        "bounds": bounds,
        "all_spacex": all_spacex,
        "funding": funding,
        "price_locus": price_locus,
        "split_solve": {
            "rows": split_solve, "total_inflow_usd": total_inflow,
            "note": ("2 equations (NAV, AUM), 3 unknowns (X, B, public return) — so the split needs the "
                     "public-basket return fixed. Total new cash X+B is pinned ~$%.0fM regardless; only the "
                     "IPO-buy share X moves with the public assumption, and it brackets ~0." % (total_inflow / 1e6)),
        },
        "spacex_value": {"prior_usd": round(spx0_val), "current_usd": round(spx1_val),
                         "weight_now_pct": round(spx1_val / aum1 * 100, 2)},
        "conclusion": (
            "AUM grew +{:.1f}% ({:.1f}B->{:.1f}B) but per-share NAV only +{:.1f}% — the {:.1f}-point gap is "
            "~${:.0f}M of net subscriptions, not an IPO buy. The +{:.1f}% NAV is almost entirely the existing "
            "SpaceX re-marking +{:.0f}% (worth +{:.1f}% on its own); adding the public book's known +{:.1f}% to "
            "+{:.1f}% return brings the no-add prediction to +{:.1f}%-+{:.1f}%, slightly ABOVE the actual "
            "+{:.1f}%. So solving for an IPO add gives a NEGATIVE number in all three fund-weight versions "
            "(X ${:+.0f}M to ${:+.0f}M) — i.e. NO add (you can't buy negative; the small shortfall is model "
            "noise — weight drift, cash in the sleeve, preferred-vs-common tracking). Net subscriptions absorb "
            "the full ~${:.0f}M. So as of {} close there is no evidence of a CHEAP / IPO-priced SpaceX grab "
            "(that would have spiked NAV). BUT an at-MARKET add (bought near the $160.95 close) has ~0 intraday "
            "P&L and is INVISIBLE to NAV — it could be anywhere from $0 to ~${:.0f}M (the new cash), or more "
            "via rotation, and cannot be excluded. Central read: ~$0 (new money is subscriptions); only the "
            "6/30 NPORT share count settles whether they added at market. The firm-wide $1B order more likely "
            "sits in the private BaronX vehicles or hasn't settled into this NAV yet."
        ).format(aum_g * 100, aum0 / 1e9, aum1 / 1e9, nav_g * 100, (aum_g - nav_g) * 100, inflow / 1e6,
                 nav_g * 100, spx_ret * 100, w_spx0 * spx_ret * 100, pub_lo * 100, pub_hi * 100,
                 pred_lo * 100, pred_hi * 100, nav_g * 100, buy_lo / 1e6, buy_hi / 1e6,
                 total_inflow / 1e6, d1, total_inflow / 1e6),
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
