# Look-through design (recorded) + where our old errors came from

**2026-07-09.** Append-only. Two items: (1) record the new look-through representation; (2) with the
corrected model (6/30 weights + calibrated leverage) now in hand, attribute where our *prior* errors
came from.

## 1. Recorded — the look-through mark representation

New primitive for representing the fund under DYNAMIC leverage: the **per-BPTIX-share look-through** —
what 1 BPTIX share owns = shares of each underlier + a borrowing line. Two layers:
- **Slow** (updates only at a disclosure, ~quarterly): the holdings weights (now 6/30, next ~9/30).
- **Fast** (drifts daily off AUM/NAV): per-BPTIX share counts, leverage, borrowing, redemptions.

Marking = `Σ(shares × live price) − borrow`. It handles dynamic leverage naturally (leverage = the
borrow line) and separates the slow disclosure layer from the fast daily layer. Kept as a SEPARATE
track from the multi-basket daily NAV log (research: "which weighting predicts best"); the
look-through is the single highest-confidence MARK object. Implemented as: `meta.lookthrough` +
`borrowings_b` per row in `daily_nav_log.py`, and a new **"Fund look-through per BPTIX share"** card
(KPIs + the mark table + a daily-state history: leverage / borrowings / AUM / net flow / SpaceX-per-
BPTIX). Latest mark basket: `situations/spacex_baron/data/position_mark_basket_v2_2_2026-07-08.csv`.

## 2. Where our prior errors came from (attribution)

Method: for each recent day, take the OLD model (5/31 weights, L = 1.0) error and split it into the
two things we've since corrected — the **leverage fix** (L 1.0 → ~1.06) and the **weight fix**
(5/31 → 6/30, dominated by TSLA) — using the corrected model as the ~truth. Units = % of NAV.

| source | RMS | where it shows up |
|---|---|---|
| **SpaceX / SPCX** | **~0 (accurate)** | biggest single mover (−6.1% on 6/22) yet ~0 error — the SpaceX weight was validated (6/22, 7/7). |
| **TSLA weight** (5/31 overweight) | **0.090%** | on TSLA-move days: 6/29 −0.16, 7/2 +0.12, 6/23 +0.10, 7/6 −0.11. |
| **Leverage** (L 1.0 vs ~1.06) | **0.072%** | on big-public-move days: 6/26 +0.21, 7/1 +0.14, 7/8 −0.13, 7/6 +0.11. |
| **Residual (new model)** | **0.116%** | what's LEFT after both fixes — intra-quarter drift + noise; biggest is 6/25 −0.21 (the concentrated mid-cap crash). |
| Total OLD-model error | 0.193% | fixing weights + leverage roughly HALVED it → 0.116%. |

### Read-out (answering the question directly)

- **SpaceX / SPCX: the accurate part.** It's the single biggest driver of daily NAV (e.g. −6.1% of
  the −6.94% on 6/22), and we nail it — the SpaceX weight (~33%) was right, confirmed on the big-SPCX
  days. So SPCX is NOT where the error is.
- **TSLA: the biggest WEIGHT error** (~0.09% RMS). The stale 5/31 snapshot carried TSLA at ~24.7% vs
  the true ~21%, so on days TSLA moved a lot we mis-attributed. Now fixed with the 6/30 weights.
- **Leverage: YES, a real effect** (~0.07% RMS, up to ~0.2% on the biggest-basket days). Using L = 1.0
  vs the true ~1.06 under-scaled the whole public sleeve by ~6%, which surfaced on big public-move days
  (the 6/26 rebound +0.21, the 7/8 drop −0.13) and had the SAME sign as the basket return. Now fixed.
- **What's LEFT (~0.12% RMS): small, and it's the public MID-caps, not SpaceX/TSLA/leverage.** The
  residual concentrates on high-dispersion days where specific mid-caps move hard (6/25 the worst) —
  because the 6/30 weights are a quarter-end snapshot and the fund drifts intra-quarter, and because
  a name-level over/under-weight we can't see (below disclosure granularity) shows up only when that
  name moves. This is near the floor of what a public-basket proxy can do (~10 bps/day).

**Bottom line:** SpaceX is accurate; the two things that used to hurt us — TSLA (stale overweight) and
leverage (1.0 vs ~1.06) — are now both corrected and were of similar size (~0.07–0.09%); the remaining
~0.12% is public mid-cap intra-quarter drift/noise. The corrected model's typical error is ~0.1% of
NAV. (Reproduce: the components come from `daily_nav_log.json` rows — SpaceX contrib, fund_5_31 vs
fund_6_30 basket returns, and the per-row leverage.)
