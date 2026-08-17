# Position-mark basket v4 — re-anchored to the 7/31 disclosure (+ clean-split backtest)

**2026-08-11.** Append-only. Baron posted a **7/31 as-of holdings** update (top-10 + leverage line).
Rebuilt the mark basket from it. Supersedes v3 (6/30). File:
`situations/spacex_baron/data/position_mark_basket_v4_2026-07-31.csv`.

## What 7/31 disclosed (and what it confirmed)

Top-10 (% of **Total Investments = GROSS**): SpaceX 24.8, TSLA 12.4, SCHW 5.3, MSCI 4.7, SHOP 4.4,
H 4.3, ACGL 4.0, SPOT 3.9, FDS 3.7, GWRE 3.2 (top-10 = 70.9%). **Long Equity 110.0% of Net, Cash −10.0%**.

- **Leverage = 1.10** (gross/net), NOT the ~1.078 our fixed-$1.15B borrowings model implied. True
  borrowings ≈ 10% of net ≈ **$1.47B** on 7/31. Leverage rose over July (~1.07 at 6/30 → 1.10),
  i.e. the fund ADDED borrowing (cash −6%→−10%) — partial revision of the earlier "borrowings flat"
  read; it levered up to hold through the SpaceX drawdown.
- **SpaceX marking validated + it pins the leverage.** Our SpaceX $ (36.94M disclosed sh × SPCX 108.37)
  = $4.00B. At **L=1.10** that is 4.00/(1.10×14.7) = **24.8% of gross = the disclosed figure exactly**
  (at L=1.078 it would be 25.3% — off). So 24.8% independently confirms BOTH the 36.94M share count AND
  L=1.10.
- **Weights drifted exactly as buy-and-hold predicts:** SpaceX −8.2 and TSLA −1.7 (of gross); every
  public name ROSE, most of all the mid-cap winners (FDS +1.1, GWRE +1.0, SPOT/MSCI +0.8, ACGL/SHOP +0.7).
  Hard confirmation of the constant-weight-vs-buy-and-hold finding.

## v4 construction (conventions written out to avoid the past % ambiguity)

- **Anchor:** 7/31 closes; NAV 251.24; AUM (net) 14.7B; shares-out = AUM/NAV = 58.51M.
- **Leverage L = gross/net = 1.10.** gross-per-BPTIX = NAV × L = **276.36**. borrow-per-BPTIX =
  NAV × (L−1) = **−25.12** (= cash −10% of net = −9.09% of gross).
- **Weights: stock $ per BPTIX = weight_gross × 276.36.** SpaceX uses the exact disclosed share count
  (36.94M / 58.51M = **0.6313 sh/BPTIX**, = 24.76% gross ≈ disclosed 24.8%). The 9 disclosed publics use
  their 7/31 % of gross. The tail-20 use 6/30 proportions scaled to fill the remaining 29.3% of gross.
- **Two percent columns in the CSV:** `pct_of_nav` (stocks sum to **110.0%**, cash −10%, net 100%) and
  `pct_of_gross` (stocks sum to **100.0%**). Marking: `mark = Σ(sh_i × live_px_i) − 25.12`.
  Check: Σ stock $ = 276.36 = 110% net = 100% gross; − 25.12 = 251.24 = NAV. ✓
- SpaceX per BPTIX 0.6313 (v4) vs 0.5971 (v3) — the rise is redemptions shrinking shares-out (58.5M vs
  61.9M), SpaceX shares locked; NOT a weight change.

## Clean-split backtest (v3 vs v4, valid window 7/8→8/10, all 29 names priced)

Marked each day with both static baskets (v3: 6/30 shares, borrow −19.31; v4: 7/31 shares, borrow −25.12).

| window | winner |
|---|---|
| 7/8, 7/9, 7/10 | **v3** (err +0.2–0.3; v4 +0.5–0.7) |
| 7/13 onward | **v4** every day (v3 drifts +0.4→+2.6; v4 stays ±0.1–0.9) |

**Optimal clean split: use v3 through 7/10, switch to v4 on 2026-07-13.** Totals (abs err over the
window): v3-only 27.16, v4-only 7.45, **split-at-7/13 = 6.44 (best)**. Crossover ~7/13 (earlier than the
6/30–7/31 calendar midpoint because SpaceX fell + mid-caps rose fast in early July, and v4's L=1.10 helps
sooner). Interpretation: the fund's book effectively "became" the 7/31 book by ~7/13.

Follow-ups still pending user go-ahead: (1) set the daily engine leverage to 1.10 (from ~1.078);
(2) implement buy-and-hold fund_6_30_bh (verified 4.5× tracking-sd cut). v4 already bakes in L=1.10.
