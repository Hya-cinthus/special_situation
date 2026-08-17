# v4.1 — fixing the tail: buy-and-hold, not constant-weight

**2026-08-12.** Append-only. Supersedes v4 (same day's anchor). File:
`situations/spacex_baron/data/position_mark_basket_v4_1_2026-07-31.csv`.

## The bug in v4's tail

7/31 disclosed only the **top-10** (70.9% of gross) + the leverage line. The other **19 names**
(29.3% of gross) had to be inferred. In v4 I filled them by **re-imposing their 6/30 WEIGHTS**
pro-rata onto the residual. Because `shares = $ / price`, that silently **rebalanced**: names whose
price rose got their share count CUT, names that fell got shares ADDED —
`corr(price change, share change) = −0.981`.

| tail name | price 6/30→7/31 | v4 share change |
|---|---|---|
| FIG | +34.4% | **−26.2%** |
| MORN | +23.4% | −19.6% |
| IT | +16.5% | −14.9% |
| MRNA | −21.7% | **+26.7%** |
| BIRK | −10.0% | +10.2% |

That is exactly the constant-weight "sell winners / buy losers" behaviour we had already shown the
fund does NOT do — the same flaw v2.x had, reintroduced in the tail.

## The constraint (why the tail has no free total)

Gross-per-BPTIX is pinned by the disclosed leverage, and SpaceX + the 9 disclosed names are pinned too:
`residual = 276.36 (gross) − 68.41 (SpaceX) − 126.85 (9 disclosed) = 81.10`. Holding the 6/30 tail
SHARES outright would be worth **86.32** — 5.22 too much. So the tail total is forced; only the SPLIT
is a choice.

## The fix (v4.1)

Keep the tail's **6/30 SHARE structure** and apply **one uniform haircut** `k = 81.10/86.32 = 0.9396`
(**every tail name −6.04% shares**). Winners keep the larger weight their rally earned; losers keep the
smaller one. No cross-sectional rebalancing. Economically this is "the fund sold publics pro-rata to
meet redemptions and didn't reshuffle among them" — consistent with SpaceX being locked (SpaceX per
BPTIX ROSE 0.5971→0.6313 while public per-BPTIX shares fell ~6%).

## Which is right — the decisive test

The 8-day forward tracking test **favoured v4** (RMS 0.141 vs 0.239) but is low-powered: n=8, the tail
is only 29% of gross, and both errors are tiny (0.05% vs 0.09% of NAV) — inside the noise.

The decisive test uses the **9 disclosed names, where we know the TRUE 6/30 and 7/31 weights**, and asks
which rule reproduces the observed weight evolution:

| hypothesis | RMS error predicting the 7/31 disclosed weights |
|---|---|
| Constant-weight (v4's tail rule) | **1.247** |
| **Buy-and-hold (v4.1's tail rule)** | **0.260** |

Buy-and-hold wins on **all 9 names**, ~5× better overall. The extreme case is **TSLA**: price −26.0%,
constant-weight predicts it still at 15.83% of gross, **truth 12.40%**, buy-and-hold 11.81% — the fund
plainly did NOT buy the TSLA dip to hold its weight. Adopted v4.1.

(Residual detail: buy-and-hold under-predicts the disclosed nine by a mean −0.21pp, i.e. the top-10
holds ~1.9pp more of gross than pure price drift implies — so the tail was trimmed slightly MORE than
uniformly. v4.1's forced-residual haircut absorbs exactly that.)

## Engine

`_build_static_basket(..., prior_shares=...)` now does the buy-and-hold tail (falls back to weights only
when there is no prior book). `meta.mark_basket` reports **v4.1**. The v4 CSV is retained for the record.
