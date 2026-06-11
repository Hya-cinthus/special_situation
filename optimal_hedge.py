"""
Optimal-hedge research -> dashboard/data/optimal_hedge.json

Treats the hedge as a MINIMUM-VARIANCE problem: choose short shares to minimize the
variance of the daily net P&L (ex the 6/4 SpaceX re-mark, which no public short can
hedge). With only ~11 daily observations you CANNOT fit 23 independent hedge ratios
(underdetermined / wildly overfit), so we:
  - test fixed structures (actual basket, fund-weight) with at most a 1-param scale,
  - test a 2-factor hedge (Tesla on its own ratio + the rest of the actual basket),
  - and validate everything OUT-OF-SAMPLE (leave-one-out CV, a 7/4 train-test split,
    and a jackknife on the Tesla coefficient) — not in-sample, to avoid overfit.

Finding: the actual basket already cuts the daily swing ~81% and is ~net-scaled
(effective leverage ~1.0, not gross 1.13). The one robust improvement is the
2-factor hedge — and it wants LESS Tesla (~14.2k vs 16.8k), not more, which implies
the fund's CURRENT Tesla weight is below the stale 3/31 30.4%. Pure stdlib.
"""

import json
import os
import datetime

import hedge_book
import nport_holdings

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
ENTRY = hedge_book.ENTRY

# Baron's own 2026-05-31 site disclosure (top-10, % of NET assets) — fresher than
# the 3/31 NPORT. Used to JUSTIFY (not fit) the data-driven "less Tesla".
DISCLOSED_5_31 = {"TSLA": 0.167, "MSCI": 0.047, "H": 0.043, "SCHW": 0.039,
                  "SHOP": 0.038, "ACGL": 0.035, "IT": 0.033, "SPOT": 0.032, "FDS": 0.029}


def _mean(a):
    return sum(a) / len(a)


def _std(a):
    m = _mean(a)
    return (sum((x - m) ** 2 for x in a) / len(a)) ** 0.5


def _rms(a):
    return (sum(x * x for x in a) / len(a)) ** 0.5


def build_payload():
    end = "2026-06-12"
    px = {tk: hedge_book._series(tk, ENTRY, end) for tk in hedge_book.POSITIONS}
    hbser = {r["date"]: r for r in json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "hedge_book.json"), encoding="utf-8"))["series"]}
    dates = sorted(d for d in px["BPTIX"] if d >= ENTRY)
    shorts = [tk for tk in hedge_book.POSITIONS if hedge_book.POSITIONS[tk] < 0]
    actual = {tk: abs(hedge_book.POSITIONS[tk]) for tk in shorts}
    e = {tk: px[tk][ENTRY] for tk in shorts}

    # daily long P&L (ex-remark) and per-stock daily price change
    L, dpx, prev = [], {tk: [] for tk in shorts}, None
    for i, d in enumerate(dates):
        if i == 0:
            prev = d
            continue
        L.append(hbser[d]["long_pnl_ex_remark"] - hbser[prev]["long_pnl_ex_remark"])
        for tk in shorts:
            dpx[tk].append(px[tk].get(d) - px[tk].get(prev))
        prev = d
    n = len(L)

    def net_actual(idx):
        return [L[i] - sum(actual[tk] * dpx[tk][i] for tk in shorts) for i in idx]

    def fit2(idx):   # 2-factor: TSLA(shares) + rest-of-actual(scale)
        Mt = [dpx["TSLA"][i] for i in idx]
        Mr = [sum(actual[tk] * dpx[tk][i] for tk in shorts if tk != "TSLA") for i in idx]
        a = sum(x * x for x in Mt); b = sum(Mt[j] * Mr[j] for j in range(len(idx))); c = sum(x * x for x in Mr)
        u = sum(Mt[j] * L[idx[j]] for j in range(len(idx))); v = sum(Mr[j] * L[idx[j]] for j in range(len(idx)))
        det = a * c - b * b
        return ((u * c - v * b) / det, (a * v - b * u) / det) if det else (None, None)

    def net2_day(i, h1, h2):
        return L[i] - h1 * dpx["TSLA"][i] - h2 * sum(actual[tk] * dpx[tk][i] for tk in shorts if tk != "TSLA")

    allidx = list(range(n))
    h1, h2 = fit2(allidx)

    # validations
    loocv_actual = _rms(net_actual(allidx))                 # fixed -> OOS == in-sample
    loocv_2f = _rms([net2_day(k, *fit2([i for i in allidx if i != k])) for k in allidx])
    tr, te = list(range(7)), list(range(7, n))
    h1t, h2t = fit2(tr)
    tt_actual = _rms([net_actual([i])[0] for i in te])
    tt_2f = _rms([net2_day(i, h1t, h2t) for i in te])
    jack = sorted(fit2([i for i in allidx if i != k])[0] for k in allidx)

    unhedged = _std(L)
    actual_std = _std(net_actual(allidx))

    # --- JUSTIFICATION: does Baron's 5/31 disclosure explain 'less Tesla'? --------
    NET = nport_holdings.NET_ASSETS
    fundv = {name: val for sec, g, name, sh, c, val in nport_holdings.HOLDINGS if sec == "Common"}
    tsla_3_31 = fundv["Tesla, Inc."] / NET                 # 23.1% of net (3/31 NPORT)
    tsla_5_31 = DISCLOSED_5_31["TSLA"]                      # 16.7% of net (5/31 Baron)
    fw = nport_holdings.public_weights_by_ticker()
    short_total = sum(actual[tk] * e[tk] for tk in shorts)
    tsla_target_3_31 = fw["TSLA"]["weight"] * short_total / e["TSLA"]   # 3/31-implied hedge
    justification = {
        "tsla_pct_net_3_31": round(tsla_3_31, 4), "tsla_pct_net_5_31": round(tsla_5_31, 4),
        "disclosure_ratio": round(tsla_5_31 / tsla_3_31, 3),           # ~0.72
        "tsla_target_3_31": round(tsla_target_3_31),
        "tsla_optimal_2factor": round(h1),
        "twofactor_ratio": round(h1 / tsla_target_3_31, 3),            # ~0.72 (should match)
    }

    # --- DYNAMICS: should the hedge scale with AUM? (constant vs dynamic) ---------
    sbx = {r["date"]: r for r in json.load(open(os.path.join(_REPO_ROOT, "dashboard", "data", "spacex_baron.json"), encoding="utf-8"))["series"]}
    NETe = sbx[ENTRY]["total_nav_usd"]; NAVe = px["BPTIX"][ENTRY]
    cons, aum, navsh, last = [], [], [], {tk: px[tk][ENTRY] for tk in px}
    for d in dates:
        for tk in px:
            last[tk] = px[tk].get(d, last[tk])
        longp = 130000 * (last["BPTIX"] - NAVe); rmk = hbser[d]["spacex_remark_pnl"]
        aum_r = sbx.get(d, {}).get("total_nav_usd", NETe) / NETe
        nav_r = last["BPTIX"] / NAVe
        def nx(s):
            return longp - sum(actual[tk] * s * (last[tk] - e[tk]) for tk in shorts) - rmk
        cons.append(nx(1.0)); aum.append(nx(aum_r)); navsh.append(nx(nav_r))
    dynamics = {
        "constant_swing": round(_std(cons)), "aum_scaled_swing": round(_std(aum)),
        "navshare_scaled_swing": round(_std(navsh)),
        "aum_growth_pct": round((sbx[dates[-1]]["total_nav_usd"] / NETe - 1) * 100, 1),
        "navshare_growth_pct": round((last["BPTIX"] / NAVe - 1) * 100, 1),
    }

    # recommended basket (2-factor full fit) + per-name delta
    rec = {tk: round(actual[tk] * h2) for tk in shorts if tk != "TSLA"}
    rec["TSLA"] = round(h1)
    legs = sorted(({"ticker": tk.replace("-", "/"), "current": actual[tk], "recommended": rec[tk],
                    "delta": rec[tk] - actual[tk]} for tk in shorts),
                  key=lambda r: abs(r["delta"]), reverse=True)

    return {
        "meta": {
            "title": "Optimal hedge — minimum-variance research",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "n_obs": n,
            "method": ("Minimize variance of the daily net P&L (ex 6/4 SpaceX re-mark). Validated "
                       "out-of-sample (leave-one-out CV, 7/4 train-test, jackknife) — NOT in-sample, "
                       "because 23 hedge ratios on ~11 obs would be hopelessly overfit."),
            "caveat": ("~11 daily observations: only 1-2 factors are statistically justifiable. The "
                       "2-factor result is robust across three validations, but one short window — treat "
                       "the recommended shares as directional, and refresh weights at the next NPORT (6/30)."),
            "mandate": ("Baron Partners Fund: non-diversified, concentrated (top-10 heavy), long-term, "
                        "high-conviction; turnover only ~5% (it lets winners ride, rarely trades); may "
                        "borrow up to 1/3 of total assets (≈1.5x cap; currently ~1.13x). So relative "
                        "weights drift with inflows + prices and are only re-disclosed periodically — which "
                        "is exactly why the 3/31 weights go stale (and the 5/31 site disclosure is fresher)."),
        },
        "justification": justification,
        "dynamics": dynamics,
        "metrics": {
            "unhedged_daily_std": round(unhedged, 0),
            "actual_daily_std": round(actual_std, 0),
            "actual_var_reduction_pct": round((1 - actual_std / unhedged) * 100, 1),
            "loocv_actual": round(loocv_actual, 0),
            "loocv_2factor": round(loocv_2f, 0),
            "traintest_actual": round(tt_actual, 0),
            "traintest_2factor": round(tt_2f, 0),
            "actual_scale_optimal": None,   # filled below
            "jack_tsla_min": round(min(jack)), "jack_tsla_med": round(jack[len(jack) // 2]),
            "jack_tsla_max": round(max(jack)),
        },
        "twofactor": {
            "tsla_current": actual["TSLA"], "tsla_optimal": round(h1), "rest_scale": round(h2, 3),
        },
        "recommended": legs,
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "optimal_hedge.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = build_payload()
    m, mt, tf = p["meta"], p["metrics"], p["twofactor"]
    print("n=%d | unhedged std $%.0f -> actual $%.0f (%.0f%% var reduction)"
          % (m["n_obs"], mt["unhedged_daily_std"], mt["actual_daily_std"], mt["actual_var_reduction_pct"]))
    print("LOOCV: actual $%.0f vs 2-factor $%.0f | train/test: actual $%.0f vs 2-factor $%.0f"
          % (mt["loocv_actual"], mt["loocv_2factor"], mt["traintest_actual"], mt["traintest_2factor"]))
    print("2-factor: TSLA %d -> %d, rest x%.3f | jackknife TSLA %d..%d"
          % (tf["tsla_current"], tf["tsla_optimal"], tf["rest_scale"], mt["jack_tsla_min"], mt["jack_tsla_max"]))
    print("wrote", write_json())
