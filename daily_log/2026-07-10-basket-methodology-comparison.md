# Basket methodology — our v2.x vs Leon's team, and v3

**2026-07-10.** Another team (Leon) built a 6/30 mark basket. Comparison + verdict. Append-only.

## The one real difference: anchor date

Both baskets use the same 6/30 weights and land on the SAME leverage (**~1.066** — Leon states
106.6% invested; we derived 1.06–1.07 from the borrowings model and the return regression — an
independent cross-validation of the single most important parameter). They differ only in the
**anchor**:
- **Leon:** anchors everything to **6/30** — weights, NAV ($292.60) and each stock's price all on the
  same date — then holds SHARES fixed and reprices forward. `shares = weight × NAV(6/30) ÷ price(6/30)`.
- **Ours (v2.x):** anchored to **7/8** (latest actual NAV) and re-imposed the 6/30 weights on 7/8 prices.

## Verdict: Leon's anchor is more correct

Fixing shares at the disclosure date is right, because on 6/30 the weights/NAV/prices are synchronized
and represent the fund's ACTUAL shares. Holding those fixed and repricing reproduces NAV (Leon's check;
and I confirmed it reprices to within ~0.1–0.5 across 6/30→7/9 with a slow positive drift = the fund's
financing drag ~1–1.3 bp/day). Our 7/8 re-anchor **re-imposes the 6/30 weights on newer prices**, which
silently REBALANCES: e.g. TSLA fell 6/30→7/8, so imposing the same weight at the lower 7/8 price makes
us hold MORE TSLA shares (0.114) than the fund actually does (~0.105) — as if we bought the dip to hold
the weight, which the fund didn't. Net: our public shares are off toward the fallers (over) and risers
(under); Leon's are closer to the fund's true holdings. **Leon is right; we should adopt the 6/30 anchor.**

Reconstructed with the 6/30 anchor, our numbers match Leon's (TSLA 0.105 vs 0.104, SCHW 0.136 vs 0.136,
FDS 0.0354 vs 0.0356) — the small residuals are rounding + his k-scaling.

## Where we're complementary (keep these)

- **Dynamic leverage:** Leon uses a static 1.066; we model `L = 1 + borrowings/net` so it drifts up as
  redemptions shrink net (~1.064→1.067). Same today; ours ages better over weeks.
- **Dynamic SpaceX/BPTIX:** SpaceX shares are locked but BPTIX shares outstanding fall with redemptions,
  so SpaceX-per-BPTIX RISES (0.597 at 6/30 → ~0.607 now). A fixed number (either team's ~0.60) slowly
  understates it; our look-through recomputes it daily.

## v3 = adopt the 6/30 anchor (recommended for marking)

`situations/spacex_baron/data/position_mark_basket_v3_2026-06-30.csv` — public shares anchored at 6/30
(≈ Leon), SpaceX 0.597 (disclosed ÷ 6/30 shares-out), borrow −$19.31/BPTIX (L 1.066). Supersedes v2.x.
Follow-up: re-anchor the dashboard look-through card's public shares to 6/30 too (it currently
re-imposes current weights — the same flaw v2.x had).
