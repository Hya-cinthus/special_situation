"""
Hedged SpaceX-isolation book -> dashboard/data/hedge_book.json

A delta-1 portfolio entered 2026-05-20 (EOD): LONG BPTIX, SHORT its public
holdings (Arch, CoStar, Tesla, Hyatt, Schwab, ...) at fixed share counts, to
strip out the public book and isolate the SpaceX (+ other private) exposure
inside the fund. Two accounts; we report the TOTAL only.

P&L_t per position = shares * (close_t - close_entry).  (shares<0 for shorts)
Three daily lines: Long (BPTIX leg), Short (sum of short legs), Total.
Prices: Yahoo daily closes from entry to latest. Pure stdlib.
"""

import json
import os
import sys
import datetime
import statistics
import urllib.request

import nport_holdings
import fund_snapshots

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
_UA = {"User-Agent": "Mozilla/5.0"}
ENTRY = "2026-05-20"

# Total shares (account1 + account2) from the book. Yahoo tickers (HEI/A -> HEI-A).
# Long BPTIX; everything else short (negative).
POSITIONS = {
    "BPTIX": 130000,
    "ACGL": -16369, "BIRK": -13423, "CHH": -9569, "CSGP": -27884, "FDS": -4982,
    "FIG": -4835, "GLPI": -6827, "GWRE": -6517, "H": -9022, "HEI": -483,
    "HEI-A": -450, "IDXX": -1654, "IT": -7405, "KNSL": -1417, "MSCI": -2507,
    "MTN": -6923, "ONON": -11341, "RRR": -12077, "SCHW": -15428, "SHOP": -7092,
    "SPOT": -2015, "TSLA": -16836, "VRSK": -2869,
}


# Manual NAV/price points for days Yahoo hasn't posted yet (mutual-fund NAV lags
# ~1 day). Provenance must be a real reported figure, not an estimate. Only used
# where Yahoo doesn't already have the day (setdefault). Currently empty: Yahoo has
# caught up through 6/5 (the earlier BPTIX 6/4=$279.60 manual mark now matches the
# published Yahoo close, so it's no longer needed).
MANUAL_PX = {}


def _epoch(d):
    return int(datetime.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())


def _series(tk, start, end):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
         f"?period1={_epoch(start)}&period2={_epoch(end)}&interval=1d")
    j = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=_UA), timeout=30).read())
    r = j["chart"]["result"][0]
    ts, cl = r["timestamp"], r["indicators"]["quote"][0]["close"]
    out = {}
    for t, c in zip(ts, cl):
        if c is None:
            continue
        out[datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat()] = float(c)
    return out


def build_payload():
    end = (datetime.date(2026, 6, 10) + datetime.timedelta(days=1)).isoformat()
    px = {tk: _series(tk, ENTRY, end) for tk in POSITIONS}
    # merge manual points (only where Yahoo doesn't already have the day)
    for tk, days in MANUAL_PX.items():
        for d, v in days.items():
            px.setdefault(tk, {}).setdefault(d, v)
    px["SPY"] = _series("SPY", ENTRY, end)   # market proxy used by the 5/31 snapshot

    # trading-day calendar = dates where BPTIX has a price (the long anchor)
    dates = sorted(d for d in px["BPTIX"] if d >= ENTRY)
    entry_px = {tk: px[tk].get(ENTRY) for tk in POSITIONS}
    LONG_SH = POSITIONS["BPTIX"]                     # 130,000

    # Fund-level series (SpaceX $, net NAV, SpaceX weight) for two extra studies:
    #  (a) strip the SpaceX re-mark out of the long/total P&L (toggle on the chart);
    #  (b) the implied perfect-hedge leverage each day.
    try:
        sbx_data = json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "spacex_baron.json"), encoding="utf-8"))
        sbx = {r["date"]: r for r in sbx_data["series"]}
        assumed_lev = sbx_data["aum_overrides"][0]["leverage_ratio"]
    except Exception:
        sbx, assumed_lev = {}, None

    # --- alternative basket constructions (chart toggle) ----------------------
    # The LONG (130k BPTIX) is fixed; only the SHORT changes by method:
    #   ACTUAL    = your real fixed shares.
    #   CONSTANT  = sized RIGHT at entry (fund weights × your gross public exposure),
    #               then held fixed. allocation + leverage scale, no rebalance.
    #   DYNAMIC   = rebalanced every day to your CURRENT gross public exposure
    #               (NAV & SpaceX-weight drift), fund weights held at 3/31.
    shorts = [tk for tk in POSITIONS if POSITIONS[tk] < 0]
    fw = nport_holdings.public_weights_by_ticker()        # {tk:{weight,price,fund_shares}}
    wspx_e = sbx.get(ENTRY, {}).get("spacex_weight")
    short_tot_e = sum(-POSITIONS[tk] * entry_px[tk] for tk in shorts)   # your short total @ entry (~net)
    gpe_e = (LONG_SH * entry_px["BPTIX"] * (assumed_lev - wspx_e)
             if (assumed_lev and wspx_e is not None) else None)   # gross public exposure @ entry
    # RE-WEIGHT (net scale): fund weights at YOUR total -> isolates the allocation fix
    rw_sh = {tk: short_tot_e * fw[tk]["weight"] / entry_px[tk] for tk in shorts} if fw else {}
    const_sh = {tk: gpe_e * fw[tk]["weight"] / entry_px[tk] for tk in shorts} if gpe_e else {}
    dyn_prev = dict(const_sh)                              # yesterday's dynamic shares
    dyn_prev_px = {tk: entry_px[tk] for tk in shorts}
    dyn_cum = 0.0
    actual_abs = {tk: abs(POSITIONS[tk]) for tk in shorts}
    # collectors for the 2-factor min-variance fit (TSLA own ratio + rest scale)
    L_daily, dpx_daily, px_snap = [], {tk: [] for tk in shorts}, []
    prev_longex, prev_snap = 0.0, dict(entry_px)

    series = []
    last = {tk: entry_px[tk] for tk in POSITIONS}   # carry-forward for any missing day
    short_pnl_by_tk = {tk: [] for tk in POSITIONS if POSITIONS[tk] < 0}
    # SpaceX re-mark accumulator: cumulative re-mark contribution to NAV per BPTIX
    # share. The mark steps only on a re-mark day; the % impact (Δspacex / prior net)
    # applies to all share classes, so contribution = prior BPTIX NAV × that %.
    remark_cum_ps = 0.0
    prev_spx = sbx.get(ENTRY, {}).get("spacex_value_usd")
    prev_net = sbx.get(ENTRY, {}).get("total_nav_usd")
    prev_navb = entry_px["BPTIX"]
    for di, d in enumerate(dates):
        longp = shortp = 0.0
        for tk, sh in POSITIONS.items():
            p = px[tk].get(d, last[tk])
            last[tk] = p
            pnl = sh * (p - entry_px[tk])
            if sh > 0:
                longp += pnl
            else:
                shortp += pnl
                short_pnl_by_tk[tk].append(round(pnl, 2))
        navb = last["BPTIX"]
        short_notl = sum(-sh * last[tk] for tk, sh in POSITIONS.items() if sh < 0)  # |sh|×px
        row = sbx.get(d)
        w = row.get("spacex_weight") if row else None
        if row:
            spx, net = row["spacex_value_usd"], row["total_nav_usd"]
            if prev_spx is not None and abs(spx - prev_spx) > 1 and prev_net:
                remark_cum_ps += prev_navb * (spx - prev_spx) / prev_net
            prev_spx, prev_net, prev_navb = spx, net, navb
        remark_pnl = LONG_SH * remark_cum_ps
        # collect daily long-ex-remark P&L + price changes for the 2-factor fit
        long_ex = longp - remark_pnl
        snap = {tk: last[tk] for tk in shorts}
        if di > 0:
            L_daily.append(long_ex - prev_longex)
            for tk in shorts:
                dpx_daily[tk].append(snap[tk] - prev_snap[tk])
        prev_longex, prev_snap = long_ex, snap
        px_snap.append(snap)
        # implied leverage that makes the fixed short EXACTLY hedge the long's gross
        # public exposure: L* = spacex_weight + short_notional / (long_shares × NAV)
        implied_lev = (w + short_notl / (LONG_SH * navb)) if (w is not None and navb) else None

        # --- RE-WEIGHT (net scale) short P&L --------------------------------
        net_rw = None
        if rw_sh:
            net_rw = longp - sum(rw_sh[tk] * (last[tk] - entry_px[tk]) for tk in shorts)
        # --- CONSTANT-perfect & DYNAMIC-perfect short P&L (cumulative) ---------
        net_const = net_dyn = None
        if gpe_e:
            short_const = -sum(const_sh[tk] * (last[tk] - entry_px[tk]) for tk in shorts)
            net_const = longp + short_const
            if di > 0:   # dynamic: hold yesterday's shares through today's move
                dyn_cum += -sum(dyn_prev[tk] * (last[tk] - dyn_prev_px[tk]) for tk in shorts)
            net_dyn = longp + dyn_cum
            wt = w if w is not None else wspx_e            # rebalance for tomorrow
            gpet = LONG_SH * navb * (assumed_lev - wt)
            dyn_prev = {tk: gpet * fw[tk]["weight"] / last[tk] for tk in shorts}
            dyn_prev_px = {tk: last[tk] for tk in shorts}

        series.append({"date": d,
                       "long_pnl": round(longp, 2), "short_pnl": round(shortp, 2),
                       "total_pnl": round(longp + shortp, 2),
                       "spacex_remark_pnl": round(remark_pnl, 2),
                       "long_pnl_ex_remark": round(longp - remark_pnl, 2),
                       "total_pnl_ex_remark": round(longp + shortp - remark_pnl, 2),
                       "net_reweight": round(net_rw, 2) if net_rw is not None else None,
                       "net_reweight_ex_remark": round(net_rw - remark_pnl, 2) if net_rw is not None else None,
                       "net_const": round(net_const, 2) if net_const is not None else None,
                       "net_const_ex_remark": round(net_const - remark_pnl, 2) if net_const is not None else None,
                       "net_dyn": round(net_dyn, 2) if net_dyn is not None else None,
                       "net_dyn_ex_remark": round(net_dyn - remark_pnl, 2) if net_dyn is not None else None,
                       "short_notional_t": round(short_notl, 0), "nav_bptix": round(navb, 2),
                       "spacex_weight": round(w, 4) if w is not None else None,
                       "implied_leverage": round(implied_lev, 4) if implied_lev is not None else None})

    # per-ticker daily P&L for the SHORT legs, sorted alphabetically by display ticker
    short_legs_pnl = sorted(
        ({"ticker": tk.replace("-", "/"), "shares": POSITIONS[tk], "pnl": short_pnl_by_tk[tk]}
         for tk in short_pnl_by_tk),
        key=lambda r: r["ticker"])

    # gross notional at entry (for context / return scaling)
    long_notional = sum(sh * entry_px[tk] for tk, sh in POSITIONS.items() if sh > 0)
    short_notional = sum(-sh * entry_px[tk] for tk, sh in POSITIONS.items() if sh < 0)

    # per-name entry detail (for a small reference table)
    legs = sorted(({"ticker": tk.replace("-", "/"), "shares": sh,
                    "entry_px": round(entry_px[tk], 2),
                    "notional": round(sh * entry_px[tk], 0),
                    "side": "long" if sh > 0 else "short"}
                   for tk, sh in POSITIONS.items()),
                  key=lambda x: x["notional"])

    # 2-factor min-variance optimal basket (TSLA own ratio + rest scale), held
    # CONSTANT; then the net P&L under it (so the chart can show "Optimal" too).
    opt_sh = {}
    if len(L_daily) > 2:
        m = len(L_daily)
        Mt = dpx_daily["TSLA"]
        Mr = [sum(actual_abs[tk] * dpx_daily[tk][j] for tk in shorts if tk != "TSLA") for j in range(m)]
        a = sum(x * x for x in Mt); b = sum(Mt[j] * Mr[j] for j in range(m)); c = sum(x * x for x in Mr)
        u = sum(Mt[j] * L_daily[j] for j in range(m)); v = sum(Mr[j] * L_daily[j] for j in range(m))
        det = a * c - b * b
        if det:
            h1 = (u * c - v * b) / det; h2 = (a * v - b * u) / det
            opt_sh = {tk: round(actual_abs[tk] * h2) for tk in shorts if tk != "TSLA"}
            opt_sh["TSLA"] = round(h1)
    if opt_sh:
        for idx, r in enumerate(series):
            snap = px_snap[idx]
            short_opt = -sum(opt_sh[tk] * (snap[tk] - entry_px[tk]) for tk in shorts)
            r["net_optimal"] = round(r["long_pnl"] + short_opt, 2)
            r["net_optimal_ex_remark"] = round(r["long_pnl"] + short_opt - r["spacex_remark_pnl"], 2)

    # --- Disclosure-based constant baskets (fund's real weights at 3/31, 4/30,
    # 5/31, and a 4/30-5/31 blend), scaled to your short total (~net; 5/31 is net
    # cash, so no leverage uplift). SPY is the market proxy for the 5/31 residual.
    snap_names = shorts + ["SPY"]
    epx = {t: px[t].get(ENTRY) for t in snap_names if t in px and px[t].get(ENTRY)}
    FS = fund_snapshots
    blend = {t: 0.5 * (FS.WEIGHTS_4_30.get(t, 0) + FS.WEIGHTS_5_31.get(t, 0))
             for t in set(FS.WEIGHTS_4_30) | set(FS.WEIGHTS_5_31)}
    wsets = {"fund_3_31": FS.WEIGHTS_3_31, "fund_4_30": FS.WEIGHTS_4_30,
             "fund_5_31": FS.WEIGHTS_5_31, "blend": blend}
    baskets = {m: {t: short_tot_e * w.get(t, 0) / epx[t] for t in snap_names if epx.get(t)}
               for m, w in wsets.items()}
    lastp = dict(epx)
    for idx, r in enumerate(series):
        d = r["date"]
        for t in snap_names:
            if t in px:
                lastp[t] = px[t].get(d, lastp[t])
        for m, bsk in baskets.items():
            sm = -sum(bsk[t] * (lastp[t] - epx[t]) for t in bsk)
            r["net_" + m] = round(r["long_pnl"] + sm, 2)
            r["net_" + m + "_ex_remark"] = round(r["long_pnl"] + sm - r["spacex_remark_pnl"], 2)

    # per-method basket composition (shares + weight) for the side panel
    def _comp(bsk):
        tv = sum(bsk[t] * epx[t] for t in bsk if epx.get(t)) or 1
        return sorted(({"ticker": t.replace("-", "/"), "shares": round(bsk[t]),
                        "weight": round(bsk[t] * epx[t] / tv, 4)} for t in bsk if epx.get(t)),
                      key=lambda x: -x["weight"])
    compositions = {m: _comp(bsk) for m, bsk in baskets.items()}
    compositions["actual"] = _comp(actual_abs)
    if opt_sh:
        compositions["optimal"] = _comp(opt_sh)

    # residual swing per method = stdev of the ex-remark net (lower = better hedge).
    def _swing(key):
        vals = [r[key] for r in series if r.get(key) is not None]
        return round(statistics.pstdev(vals), 0) if len(vals) > 1 else None
    residual_swing = {
        "actual": _swing("total_pnl_ex_remark"),
        "fund_3_31": _swing("net_fund_3_31_ex_remark"), "fund_4_30": _swing("net_fund_4_30_ex_remark"),
        "fund_5_31": _swing("net_fund_5_31_ex_remark"), "blend": _swing("net_blend_ex_remark"),
        "optimal": _swing("net_optimal_ex_remark"),
        "reweight": _swing("net_reweight_ex_remark"),
        "const": _swing("net_const_ex_remark"), "dyn": _swing("net_dyn_ex_remark"),
    }

    last_row = series[-1] if series else {}
    return {
        "meta": {
            "title": "Hedged SpaceX-isolation book — long BPTIX vs short public holdings",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_date": ENTRY,
            "disclaimer": ("Analysis, not investment advice. Delta-1 book entered " + ENTRY + " EOD: long "
                           "130,000 BPTIX, short the fund's public holdings at fixed share counts (combined "
                           "across 2 accounts) to isolate the private (SpaceX) exposure. P&L = shares × "
                           "(close − entry close), Yahoo daily closes. Two accounts shown as TOTAL only. "
                           "Excludes financing/borrow, dividends, and BPTIX's leverage/fees. Model, not a "
                           "statement of record."),
            "long_notional": round(long_notional, 0),
            "short_notional": round(short_notional, 0),
            "n_shorts": sum(1 for s in POSITIONS.values() if s < 0),
            "long_shares": LONG_SH,
            "assumed_leverage": round(assumed_lev, 4) if assumed_lev else None,
            "residual_swing": residual_swing,
            "basket_compositions": compositions,
            "snapshot_leverage": fund_snapshots.LEVERAGE,
            "last_data_day": last_row.get("date"),
            "manual_marks": [{"ticker": tk, "date": d, "value": v,
                              "source": "user-provided (Baron/brokerage), pending Yahoo"}
                             for tk, days in MANUAL_PX.items() for d, v in days.items()],
        },
        "kpis": {
            "as_of": last_row.get("date"),
            "long_pnl": last_row.get("long_pnl"),
            "short_pnl": last_row.get("short_pnl"),
            "total_pnl": last_row.get("total_pnl"),
            "total_pnl_ex_remark": last_row.get("total_pnl_ex_remark"),
            "spacex_remark_pnl": last_row.get("spacex_remark_pnl"),
            "implied_leverage": last_row.get("implied_leverage"),
            "assumed_leverage": round(assumed_lev, 4) if assumed_lev else None,
        },
        "series": series,
        "legs": legs,
        "short_legs_pnl": short_legs_pnl,
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "hedge_book.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    print(f"entry {pl['meta']['entry_date']} | long notional ${pl['meta']['long_notional']/1e6:.1f}M "
          f"| short notional ${pl['meta']['short_notional']/1e6:.1f}M | {pl['meta']['n_shorts']} shorts")
    print(f"{'date':12s} {'long':>12s} {'short':>12s} {'total':>12s}")
    for r in pl["series"]:
        print(f"{r['date']:12s} {r['long_pnl']:>12,.0f} {r['short_pnl']:>12,.0f} {r['total_pnl']:>12,.0f}")
    p = write_json()
    print("wrote", p, f"({os.path.getsize(p)/1024:.0f} KB)")
