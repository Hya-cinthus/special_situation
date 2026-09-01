# CORRECTION — the 6/12 SpaceX buy happened. It was sold before quarter-end.

_Written 2026-09-01. This **retracts the "FALSIFIED" verdict** in
[`2026-08-28-nport-6-30-verification.md`](2026-08-28-nport-6-30-verification.md) §2. That file is
append-only and stays as written; this is the correction record. Prompted by the user pushing back:
"之前研究的不是说 spcx 周五买了才 make sense 吗？你确定 nport 日期对吗" — the challenge was right._

## What I got wrong

On 8/28 the filed 6/30 NPORT showed SpaceX at **36,938,300 shares**, identical to the 3/31 position
once the IPO split is undone. I concluded the assumed ~$262M 6/12 "Friday buy" **never happened**.

That inference was too fast. "The position is flat at quarter-end" does not imply "nothing was
bought during the quarter." A round trip inside the quarter is invisible to a quarter-end snapshot,
and that is exactly what the daily data shows.

## First, the things that did check out

The share-count reconciliation itself is solid, and worth recording because it was not obvious:

3/31 does not report one SpaceX line, it reports **five**, across two share classes:

| class | shares | price | value |
|---|---|---|---|
| common (EC) ×2 lines | 2,518,520 | $526.59 | $1,326.23M |
| preferred (EP) ×3 lines | 486,914 | $5,265.90 | $2,564.04M |
| **total** | | | **$3,890.27M** |

The preferred is priced at exactly **10×** the common, i.e. 1:10 conversion, so common-equivalent
shares are 2,518,520 + 486,914×10 = **7,387,660**. Our code's constant `3.89026788e9` matches the
total value exactly. The IPO split factor is 526.59 / 105.32 = **5.0**, so 7,387,660 × 5 =
**36,938,300** — the 6/30 filed balance, to the share.

And the 6/30 mark is a clean market price: SPCX closed **170.86** on 6/30, the filing's implied
unit price is **170.86**, and 36,938,300 × 170.86 = $6.3113B against the filed $6.31128B.
`fairValLevel` moved 3 → 1 and `isRestrictedSec` Y → N at the IPO, as expected.

So the arithmetic was right. The **inference from it** was wrong.

## The daily data says the buy was real

Hold the share count **flat** at the filed 36,938,300 (the no-buy world), predict each day's NAV
with the now-filed 6/30 weights, and regress the residual on SPCX's dollar move. The slope is the
**extra SpaceX shares per BPTIX** the fund must have held beyond the flat count.

A genuine $262M buy at the 6/12 close of 160.95 = 1.628M shares = **0.02314 sh/BPTIX**.

| window | slope (sh/BPTIX) | significance |
|---|---|---|
| **6/15 residual alone** | **+0.02336** | matches a $262M buy to **1%** |
| 6/15 – 6/18 | **+0.02400** | **6.4 σ** |
| 6/22 – 6/25 | +0.01425 | 1.2 σ (halved) |
| 7/1 – 7/10 | +0.00013 | 0.0 σ (gone) |
| July control | +0.01441 | 0.7 σ |
| August control | +0.01189 | 0.5 σ |

The 6/15 residual is +0.74/BPTIX — about **5× the daily model SD** of 0.146, so it is not noise.
And critically, the 6/15 back-solve is **not fragile**: solving `NAV_ret = w·s + (L−w)·b` across
L ∈ {0.968, 1.00, 1.0698} and b ∈ {0, the 5/31 basket, the filed 6/30 basket} gives implied w_spx
between **30.38% and 30.91%** — a half-point spread. SPCX moved +19.6% that day while the public
book moved +0.13%, so the answer is pinned by SpaceX and essentially immune to the leverage and
basket assumptions. The original 30.4%-vs-29.1% reading was sound.

## And then it was sold

The exposure decays through late June and is **completely gone by July**: 6.4σ in 6/15–6/18,
1.2σ in 6/22–6/25, 0.0σ from 7/1. Cumulative residual peaks at **+0.96** on 6/16 and unwinds to
−0.72 by 6/30, flat thereafter.

**Caveat, stated plainly:** the 6/26–6/30 segment regresses to −0.046 sh/BPTIX at a nominal −32σ,
which I am *not* treating as a clean exit signal. `LEVERAGE_FOR` steps from 1.00 to
`1 + BORROWINGS/net` (≈1.06) exactly on 6/26, so that segment is contaminated by our own leverage
assumption changing mid-window. The filing now gives the true 6/30 leverage (1.0698), so that
segment could be redone properly — but the exit conclusion does not rest on it. It rests on the
decay from 6.4σ to 1.2σ to 0.0σ, and on the flat quarter-end balance.

## Corrected conclusion

**The fund bought ~$262M of SpaceX on the 6/12 IPO day, held it for roughly two weeks, and exited
before 6/30.** All three pieces of evidence now agree:

- the 6/15 NAV jump, sized to within 1% of $262M;
- the exposure fading to zero across late June and staying at zero through July and August;
- the flat 6/30 quarter-end share count.

The earlier "falsified" call came from treating a quarter-end snapshot as if it constrained
intra-quarter activity. It does not.

## What this does and does not change

- **`FRIDAY_SPACEX_BUY` = $262M on 6/12 is CORRECT and stays.** My 8/28 note called it a live wrong
  assumption; it is not.
- **The model is still missing the exit.** It carries the buy forward indefinitely, which is why our
  6/30 SpaceX weight reads **35.37%** against the filed **34.963%** — long by +0.41pp, or +1.632M
  shares. Booking a matching sale in late June would close that gap. Note that *stripping* the buy,
  which is what my 8/28 reading implied, would have moved the weight to −1.13pp — **worse**. That
  disagreement between the two error signs was the clue I should have followed on 8/28.
- **The mark baskets are unaffected.** v3/v4/v4.1/v4.2 and `config.SPACEX_REMARKS` all mark only the
  disclosed flat count and never included the buy, so nothing there needs changing — the reason
  they were right is different from what I said on 8/28, but they were right.
- Everything else in the 8/28 scorecard stands: leverage 1.0698 vs our 1.066; cash gone; drift
  confirmed and monotone; buy-and-hold vindicated; the MRNA back-solve validated; no v5.

## Open item

Booking the exit needs a date and a size. The honest read of the decay is a **staged sale across
roughly 6/19–6/26**, not a single ticket, and the leverage step on 6/26 blurs the tail of it.
Re-running the segmentation with the filed 1.0698 leverage would sharpen it. That is a modelling
decision, not a cleanup, so it is left open rather than assumed.
