"""
Drift diagnosis: WHY does the daily NAV estimate miss? -> stdout (reproducible).

Question (2026-07-02): the daily estimate has drifted off on recent days. Four candidate
causes — (1) leverage changed, (2) SpaceX weight wrong, (3) mid-cap overweight, (4) TSLA
underweight. Each makes a DIFFERENT, falsifiable prediction about how the daily residual
(actual NAV move - our predicted move) should correlate with that day's moves:

    residual = (w_true - w_hat)*r_spx + Σ (θ_true,i - θ_hat,i) * r_i     (weight-error * return)

  H1 leverage      : all public weights scaled -> residual ∝ +public_basket_return
  H2 SpaceX weight : w_spx off        -> residual ∝ -r_spx  (if w_spx too high)
  H3 mid-cap OW    : θ off on FDS/FIG/GWRE/KNSL -> residual ∝ +their return
  H4 TSLA UW       : θ_TSLA too high  -> residual ∝ -r_TSLA

DATA: dashboard/data/daily_nav_log.json (per-day actual NAV + per-basket predicted NAV/errors,
committed) + daily_nav_log.ENTRIES closes (+ the 6/5 base closes from hedge_book.json) for the
per-name daily returns. Residual = actual - MEDIAN predicted NAV across the four disclosed-NPORT
snapshot baskets {fund_3_31, fund_4_30, fund_5_31, blend} (our "belief", not the fitted actual/
optimal/RONB baskets). Positive residual = actual ABOVE our prediction (we undershot).

Run: `py analyze_drift.py`
"""

import json
import statistics

import daily_nav_log as dl

SNAP = ["fund_3_31", "fund_4_30", "fund_5_31", "blend"]   # our disclosed-snapshot belief
MID = ["FDS", "FIG", "GWRE", "KNSL"]                       # the suspected-overweight mid-caps


def _corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else 0.0


def main():
    d = json.load(open("dashboard/data/daily_nav_log.json", encoding="utf-8"))
    rows = {r["date"]: r for r in d["rows"]}
    WS, H = dl._weightings()
    closes = {dl.BASE["date"]: dl._base_closes(H)}
    for e in dl.ENTRIES:
        closes[e["date"]] = e["closes"]
    order = [dl.BASE["date"]] + [e["date"] for e in dl.ENTRIES]

    recs = []
    print("%-11s %7s %7s %7s %7s | %9s" % ("date", "r_spx%", "r_TSLA%", "r_mid%", "r_pub%", "resid(pt)"))
    for i in range(1, len(order)):
        dt, pd_ = order[i], order[i - 1]
        r = rows.get(dt)
        if not r or r.get("actual_nav") is None or not r.get("errors"):
            continue
        resid = -statistics.median(r["errors"][m] for m in SNAP if m in r["errors"])  # actual - median pred
        r_spx = r["spcx_ret_pct"] / 100.0

        def ret(tk):
            a, b = closes[pd_].get(tk), closes[dt].get(tk)
            return (b / a - 1) if (a and b) else None

        r_tsla = ret("TSLA") or 0.0
        mids = [ret(t) for t in MID if ret(t) is not None]
        r_mid = sum(mids) / len(mids) if mids else 0.0
        r_pub = statistics.median(r["preds"][m]["basket_ret_pct"] for m in SNAP) / 100.0
        recs.append((dt, r_spx, r_tsla, r_mid, r_pub, resid))
        print("%-11s %+6.2f %+7.2f %+7.2f %+7.2f | %+9.2f" % (dt, r_spx * 100, r_tsla * 100, r_mid * 100, r_pub * 100, resid))

    resid = [x[5] for x in recs]
    print("\nCorrelation of residual with each hypothesis' signature (n=%d days):" % len(recs))
    print("  H1 leverage    corr(resid, +public_ret) = %+.2f" % _corr([x[4] for x in recs], resid))
    print("  H2 SpaceX wt   corr(resid, -r_spx)      = %+.2f" % _corr([-x[1] for x in recs], resid))
    print("  H3 mid-cap OW  corr(resid, +r_mid)      = %+.2f" % _corr([x[3] for x in recs], resid))
    print("  H4 TSLA UW     corr(resid, -r_TSLA)     = %+.2f" % _corr([-x[2] for x in recs], resid))

    print("\nKiller observations:")
    by = {x[0]: x for x in recs}
    for dt in ("2026-06-22", "2026-06-29", "2026-07-01"):
        if dt in by:
            _, rs, rt, rm, rp, rd = by[dt]
            print("  %s: r_spx=%+.1f%% public=%+.2f%% r_mid=%+.2f%% r_TSLA=%+.1f%% -> resid %+.2f" % (
                dt, rs * 100, rp * 100, rm * 100, rt * 100, rd))
    print("  6/22: biggest SpaceX move (-16.4%) -> ~zero residual => SpaceX weight is RIGHT (kills H2).")
    print("  6/29 vs 7/1: both public-UP days, OPPOSITE residual signs => not a constant leverage (kills H1).")


if __name__ == "__main__":
    main()
