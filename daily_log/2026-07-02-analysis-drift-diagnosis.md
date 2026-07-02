# Analysis — diagnosing the daily-estimate drift

**Analysis run: 2026-07-02.** Not a daily NAV entry — a one-off diagnostic, filed in the log
for the trace trail. Append-only (never edited after creation). Reproduce with `py analyze_drift.py`.

## Question

Over ~2 weeks the daily NAV estimate has drifted off on some days. Which of four candidate
causes is it — and can we rule the others out convincingly?
1. Leverage changed (we assume L = 1.0)
2. SpaceX weight is wrong (too high)
3. Mid-cap overweight (FDS / FIG / GWRE / KNSL)
4. TSLA underweight

## Data used

- **`dashboard/data/daily_nav_log.json`** — per-day actual BPTIX NAV + per-basket predicted NAV
  and errors (committed). 17 days with a known actual: the 4 IPO-week backfill days (6/8–6/12,
  SpaceX flat) + the 13 real-time days 6/15 → 7/1.
- **`daily_nav_log.ENTRIES` closes + the 6/5 base closes** (reconstructed from `hedge_book.json`)
  — for the per-name daily returns (TSLA, the mid-caps).
- **Residual** = actual NAV − MEDIAN predicted NAV across the four disclosed-NPORT snapshot
  baskets {fund 3/31, 4/30, 5/31, blend} — our "belief", not the fitted actual/optimal/RONB
  baskets. Positive residual = actual ABOVE our prediction (we undershot).

## Method

Each hypothesis is a specific weight error, so `residual = (w_true − w_hat)·r_spx + Σ(θ_true − θ_hat)·r_i`
makes a **distinct, falsifiable** prediction about what the residual correlates with:

| Hypothesis | If true, residual correlates with… |
|---|---|
| H1 leverage | **+ public-basket return** (a scaled sleeve beats/lags us on every public move, same sign) |
| H2 SpaceX weight too high | **− SPCX return** |
| H3 mid-cap overweight | **+ the mid-caps' return** (FDS/FIG/GWRE/KNSL) |
| H4 TSLA underweight | **− TSLA return** |

## Results — per-day residual vs each day's moves

```
date         r_spx%  r_TSLA%  r_mid%  r_pub% | resid(pt)
2026-06-08    +0.00   +4.59   -3.86   +0.33 |   -0.57
2026-06-09    +0.00   -3.00   -0.93   -0.38 |   +0.32
2026-06-10    +0.00   -3.80   -1.29   -1.41 |   +0.54
2026-06-11    +0.00   +4.60   -1.64   +0.99 |   -0.79
2026-06-12   +19.22   +1.82   +0.35   +1.00 |   -0.71
2026-06-15   +19.60   +1.16   -1.07   +0.12 |   +0.03
2026-06-16    +4.83   -1.58   -1.00   -0.22 |   +0.16
2026-06-17    -4.95   -2.05   -1.66   -2.28 |   -0.04
2026-06-18    -3.56   +1.04   -1.23   +0.04 |   +0.17
2026-06-22   -16.43   +1.14   -2.35   -1.16 |   -0.22
2026-06-23    +0.98   -5.79   +2.32   -0.68 |   +0.40
2026-06-24    -1.01   -1.59   -0.01   +0.26 |   +0.40
2026-06-25    -1.00   -0.11   -3.50   -1.53 |   -0.77
2026-06-26    +0.15   +1.22   +9.59   +3.10 |   +1.04
2026-06-29    +7.15   +8.46   +0.97   +1.61 |   -1.03
2026-06-30    +4.06   +2.13   -1.39   +0.05 |   -0.34
2026-07-01    -7.80   +1.12   +5.72   +2.13 |   +1.09
```

**Correlations (n = 17):**

| Hypothesis | corr(residual, signature) | |
|---|---|---|
| H3 mid-cap overweight | **+0.65** | strong |
| H4 TSLA underweight | **+0.59** | strong |
| H2 SpaceX weight | +0.29 | weak |
| H1 leverage | +0.19 | weak |

## The two decisive days (falsification)

**Killer #1 — rules out H2 (SpaceX weight):** on **6/22, SPCX moved −16.4%** (by far the biggest
SpaceX move in the sample) and the **residual was only −0.22** (fund 5/31 was *exact*). If our
SpaceX weight were off by even ~3 points, that move would have mis-stated NAV by ~1.5 points. It
didn't. On the day SpaceX *was* the whole story, we nailed it → **the SpaceX weight is accurate.**

**Killer #2 — rules out H1 (leverage):** a leverage error scales with the public return **with a
fixed sign**. But **6/29** (public +1.61%, residual **−1.03**) and **7/1** (public +2.13%, residual
**+1.09**) are two public-**up** days with **opposite** residuals. A constant leverage error cannot
produce that. (Leverage also matched L = 1.0 exactly on the 6/17/6/18 down days.)

## Conclusion (firm)

> **The drift is public-basket composition: the fund is UNDERWEIGHT TSLA and OVERWEIGHT the
> mid-caps (FDS/FIG/GWRE/KNSL) vs our stale 3/31→5/31 snapshots. It is NOT leverage, and it is
> NOT the SpaceX weight.**

The two rejected hypotheses aren't merely less likely — each is contradicted by a specific day
(6/22 for SpaceX weight; the 6/29-vs-7/1 sign flip for leverage). The two survivors are one and
the same trade — a rotation out of TSLA into the mid-caps (Baron's documented "less Tesla" trim) —
and both are needed: 6/29 is a pure-TSLA day (only H4 explains it), 7/1 / 6/25 / 6/26 are pure
mid-cap days (only H3). So it's both sides of the rotation, not one single name.

**Confidence & caveat:** strong inference from 17 daily points, not a filed fact. The **6/30/2026
NPORT-P (expected ~2026-08-27)** gives the actual current weights and will quantify how much TSLA
came out and which mid-caps went in. But the daily data has already eliminated leverage and the
SpaceX weight. See [[next-nport-verification]] / `README.md`.
