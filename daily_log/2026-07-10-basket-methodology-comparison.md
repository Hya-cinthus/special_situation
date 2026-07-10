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

## Empirical arbiter — daily tracking vs the ACTUAL NAV moves (not Baron's stated weights)

The right judge isn't the methodology argument, it's: does `Σ shares × daily price change` reproduce
the ACTUAL daily ΔNAV? (This is robust to Baron's posting being imprecise — reality is the ground
truth.) Tested both teams' exact share counts, day-over-day 6/30→7/9 (per BPTIX $):

| day | actual ΔNAV | Leon err | ours err |
|---|---|---|---|
| 7/1 | −3.24 | −0.03 | −0.18 |
| 7/2 | +3.42 | +0.00 | **−0.43** |
| 7/6 | +2.26 | +0.01 | +0.20 |
| 7/7 | −6.34 | +0.10 | −0.13 |
| 7/8 | −5.33 | +0.11 | +0.06 |
| 7/9 | +4.45 | −0.06 | +0.08 |
| **RMS** | | **$0.067** | **$0.218** |

**Leon's basket reproduces the real daily BPTIX move ~3× more accurately** ($0.067 vs $0.218 per
BPTIX; on 30k BPTIX that's ~$2/day vs ~$6.5/day of tracking noise). So it's not just methodologically
cleaner — it's empirically better against the actual NAV. And because Leon's (built from Baron's 6/30
weights) tracks reality to ~$0.07/day, **Baron's 6/30 posting is validated** — the weights are accurate.
Leon's small residual is a **+$0.022/day upward drift = the fund's financing cost** (it pays interest on
~$1.15B of borrowings; a fixed basket doesn't) — known, ~1 bp/day, and subtractable if we want.

## Does a redemption adjustment help? NO — it makes tracking WORSE (tested)

Intuition: redemptions shrink the fund daily, so SpaceX-per-BPTIX rises and leverage edges up — adjust
the basket daily for it. Tested it (dynamic SpaceX = disclosed ÷ N_t, dynamic borrow = $1.15B ÷ N_t,
N_t from the daily AUM):

| basket | RMS daily error | drift/day |
|---|---|---|
| **Leon STATIC** (fixed shares + fixed borrow) | **$0.067** | +$0.022 |
| + redemption adj (dynamic off daily AUM) | **$0.282** | +$0.242 |
| + financing accrual | $0.279 | +$0.239 |

**It gets ~4× WORSE.** Why: the daily AUM figure (Morningstar, rounded to $0.1B ≈ 0.55% of $18B, ~1-day
lagged) is too noisy — recomputing SpaceX-shares and borrow off it each day injects ~$0.25/day of
*rounding* noise, which swamps the real redemption effect (~$0.02/day). The theory is right but the
input is too coarse to exploit daily. Financing accrual also barely moves the drift (so the +$0.022/day
isn't mainly interest — it's intra-quarter weight drift). **Conclusion: keep the STATIC basket; do NOT
adjust daily off AUM. Re-anchor only at a fresh disclosure (or if AUM moves large and cleanly).** (Note:
this is specific to the MARK basket. The daily NAV-log's dynamic leverage is fine there because it
re-anchors to prior actual each day.)

## v3 = adopt the 6/30 anchor (recommended for marking)

`situations/spacex_baron/data/position_mark_basket_v3_2026-06-30.csv` — public shares anchored at 6/30
(≈ Leon), SpaceX 0.597 (disclosed ÷ 6/30 shares-out), borrow −$19.31/BPTIX (L 1.066). Supersedes v2.x.
Follow-up: re-anchor the dashboard look-through card's public shares to 6/30 too (it currently
re-imposes current weights — the same flaw v2.x had).
