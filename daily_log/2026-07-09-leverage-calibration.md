# Leverage — calibrated (and why the basket needs its own)

**Analysis 2026-07-09.** Two questions from the user: (1) the different basket weightings don't each
carry a leverage — shouldn't the 6/30 basket have one? (2) if the 6/30 basket is accurate, the
leverage should be visible in the *scale* of recent returns — so stop guessing 1.05/1.06/1.10.
Both correct. Append-only.

## The fix to my earlier hand-waving: solve for it

With the **real 6/30 weights** now known, the daily identity is
`NAV_ret = w_spx·SPCX_ret + (L − w_spx)·basket_ret`, i.e. a linear model
`NAV_ret = a·SPCX_ret + b·basket_ret6/30` with **a = SpaceX weight, b = public weight, L = a + b.**
So an OLS of actual NAV returns on [SPCX return, 6/30-basket return] (no intercept) reads the
leverage straight off the return scale. (Earlier I said the daily data couldn't distinguish 1.0
from 1.06 — that was with the STALE 5/31 weights, whose error masked it. With the correct 6/30
weights the residual collapses and the leverage pops out.)

| window | n | SpaceX wt (a) | public wt (b) | **L = a+b** | resid sd |
|---|---|---|---|---|---|
| last 10 days | 10 | 0.335 | 0.733 | **1.068** | 0.10% |
| post-6/30 (7/1–7/8) | 5 | 0.341 | 0.720 | **1.061** | 0.11% |
| all completed (6/16–7/8) | 20 | 0.308 | 0.725 | 1.034 | 0.33% |

**Result: L ≈ 1.06–1.07 now**, fit to ~0.10% of NAV. The regression also independently recovers the
**SpaceX weight at ~0.335** (≈ our 33%). The 20-day blend (1.034 = avg of ~1.0 and ~1.07) shows the
fund **re-levered from ~1.0 to ~1.07 around late June** — climbing back toward its ~1.13 mandate as
redemptions slowed.

## Two independent methods agree

1. **Structural (6/30 disclosure):** SpaceX $ (disclosed 36.94M × $170.86 = $6.31B) is 34.9% of NET
   ($18.1B Morningstar) but Baron reports 32.9% of GROSS → gross ≈ $19.2B → **L ≈ 1.06.** Cross-check
   that pins L>1.0: if Morningstar were GROSS instead of net, it would imply 34.9M SpaceX shares,
   *below* the disclosed 36.94M — impossible (SpaceX is locked up, can't sell). So Morningstar is
   net and L>1.0 is near-certain.
2. **Empirical (regression above):** L = 1.06–1.07.

## Answering (1): leverage is ONE fund-level number, applied to every weighting

Leverage = gross investments / net assets — a single fund-level scalar. It is the SAME for all the
basket weightings on a given day (the weighting is the *public split*; the leverage is the *scale*
of the public sleeve). It is **time-varying**, so we carry a schedule, not a constant. Updated
`daily_nav_log.LEVERAGE_FOR`:

- **≤ 6/15: 0.968** (5/31 net-cash buffer)
- **6/16–6/25: 1.00** (buffer consumed by redemptions; 6/17 confirmed)
- **≥ 6/26: 1.06** (re-levered; both methods above)

Every weighting (fund 3/31…6/30, RONB, optimal, actual) now uses that day's L.

## Answering (2)/the basket: v2 used L=1.0 — too low. v2.1 uses L=1.06

The v2 mark basket (`..._v2_2026-07-08.csv`) was built fully-invested (L=1.0, no borrow), so it
under-held the public sleeve. **v2.1** rebuilds at **L = 1.06**:
`situations/spacex_baron/data/position_mark_basket_v2_1_2026-07-08.csv`. Difference vs v2 (per BPTIX
share, anchored 7/8, NAV $283.37):
- Public sleeve grossed up **$194.39 → $211.39** (+8.7%; every public share count ×1.087).
- A **borrow line: CASH = −$17.00 / BPTIX** (−6.0% of NAV; −$2.21M for the 130k position).
- SpaceX unchanged (0.60 SPCX). Sum still = NAV.

**Use v2.1 for marking.** Caveats: L is ~1.06 ± a touch (band ~1.05–1.10 depending on the exact
SpaceX share count / net-AUM figure); the 6/30 **NPORT-P (~Aug 27, net + total assets)** gives the
exact leverage. If it lands materially different, that's a v2.2 re-anchor.
