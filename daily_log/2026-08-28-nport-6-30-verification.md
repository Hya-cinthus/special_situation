# 6/30/2026 NPORT-P — scoring every standing theory

_Filed 2026-08-28, pulled and verified 2026-08-31. Accession `0001410368-26-088301`,
seriesId `S000000588` (Baron Partners Fund), registrant CIK 1217673. Raw book committed to
`situations/spacex_baron/data/nport_holdings_2026-06-30.csv`. Append-only: this file is not
edited after creation._

This is the filing the project has been waiting for since June. Ten NPORT-P filings landed for
the trust on 8/28; the Baron Partners one is identified by seriesId, not by name (a sibling,
Baron Focused Growth `S000022521`, also holds SpaceX and would otherwise contaminate the data).

**Filing lag: 59 days** (6/30 → 8/28), inside the 51–61 day historical range with one trading
day to spare. Prior: 6/30/2025 → 8/27/2025 = 58d; 3/31/2026 → 5/22/2026 = 52d. On 8/27 the note
said that if it did not land Friday the filing itself became an anomaly. It landed Friday.

## Fund level

| | filed 6/30 |
|---|---|
| net assets | $18.0511B |
| total assets | $19.3104B |
| total liabilities | $1.2593B |
| **leverage (gross/net)** | **1.0698** |
| cash (SSgA money-market) | $39.0M = 0.216% of net |
| BPTIX NAV 6/30 | 292.60 → 61.6921M shares out |
| holdings | 29 public names + SpaceX + 1 cash line |

## The scorecard

### 1. Leverage — HIT

Filed **1.0698** against the v3 model's **1.066**: off by 0.4%. Combined with the 7/31 disclosed
1.10, this confirms the fund **levered up during July**, which is exactly what the slow-variable
tracker flagged on 7/21 — about three weeks before the disclosure existed. That estimator was
built to catch active re-levering that the fixed-borrowings model structurally could not see, and
this filing is its out-of-sample vindication.

### 2. SpaceX share count — the assumed Friday buy is FALSIFIED

| | shares |
|---|---|
| filed 6/30 | **36,938,300** |
| our 3/31 basis (3.89026788e9 / 105.32) | 36,937,599 |
| delta | +701 sh = **+0.002%** |

The share count is **unchanged from 3/31 through 6/30**. The assumed ~$262M 6/12 "Friday buy",
which would have added ~1.63M shares and taken the count to ~38.57M, **did not happen**.

Two consequences, pulling in opposite directions:

- The **mark baskets were right**. v3/v4/v4.1/v4.2 all mark only the disclosed 36.94M, and all of
  `config.SPACEX_REMARKS` marks that flat count. Nothing there needs changing.
- The **recalibration card's Friday-buy estimate is wrong**. `FRIDAY_SPACEX_BUY` = $262M, booked on
  6/12, is a live assumption in `daily_nav_log`. It needs a decision (see open items).

Implied 6/30 mark: $170.86/share.

### 3. Cash — HIT

$39.0M of money-market against $18.05B of net assets, **0.216%**. The 5/31-disclosed ~3.2%
net-cash buffer (~$0.65B) is gone, consumed by redemptions exactly as the leverage schedule
assumed when it stepped 0.968 → 1.00 on 6/16.

### 4. Basket drift — CONFIRMED, and monotone

TSLA public-book-relative weight, each snapshot against the filed truth:

| snapshot | TSLA wt | vs filed |
|---|---|---|
| fund 3/31 | 30.43% | **+45.1%** |
| fund 4/30 | 26.56% | +26.6% |
| fund 5/31 | 24.67% | +17.6% |
| website 6/30 | 21.05% | +0.3% |
| **FILED 6/30** | **20.98%** | — |

Perfectly monotone: the older the snapshot, the more TSLA it carries. And this ordering is
**exactly** the per-basket daily error ranking measured on 8/24, the day TSLA fell 3.83% and a
single-name regression explained R² = 0.956 of the cross-basket spread. The drift theory, first
inferred on 6/26 from a high-dispersion mirror day, is now confirmed against filed weights.

### 5. Buy-and-hold — VINDICATED

TSLA absolute share count: **6.455M at 6/30 → 6.443M implied at 7/31, a change of −0.2%.** The
fund barely traded its largest public position over that month. Per-BPTIX shares rose only because
redemptions shrank the denominator, and the weight fell only because the price fell.

That is precisely the assumption v4.1 introduced and v4.2 inherits: hold the prior **share** book
and apply one uniform haircut, rather than re-imposing prior **weights**, which would silently sell
winners and buy losers. It was already validated against the nine disclosed 7/31 names (RMS 0.26
vs 1.25) and stress-tested by MRNA +176.9% on 8/19. This is the third, cleanest confirmation.

### 6. MRNA — the back-solve was measuring a real trade

MRNA is the one holding we had **no disclosure for** and reverse-engineered purely from NAV moves
across seven price shocks.

| | sh/BPTIX |
|---|---|
| filed 6/30 | **0.03225** |
| v4.1 carried (6/30 shares × uniform haircut) | 0.02942 |
| our August back-solve (7 shocks, precision-weighted) | **0.02418 ± 0.00123** |

The filed 6/30 number is **+33% above** our August figure. Read correctly, that is not an error —
it means the fund **cut MRNA roughly 25% between 6/30 and mid-August**. The 8/19 note said the
fund "trimmed the tail MORE than a uniform haircut, or partly exited MRNA." Confirmed.

This is the single most important methodological result in the filing: **a holding with no
disclosure was recovered from NAV moves alone, and the filing corroborates both the level and the
direction of the subsequent trade.**

### 7. Baron's website book — accurate, with one real error

We had been using Baron's website holdings as `WEIGHTS_6_30`. Against the filing, on the
public-relative basis: **mean |error| 0.072pp, max 0.61pp** across 29 names. That is a good source.

Its one genuine mistake: **GOOGL and GOOG are swapped.** Site had GOOGL 0.149% / GOOG 0.597%;
filed is GOOGL 0.759% / GOOG 0.148%.

`WEIGHTS_6_30` has been replaced with the filed values (same fraction-of-gross basis, so `_nospy`
renormalization downstream is unchanged).

### 8. No v5 — the filing does NOT improve the mark basket

Four candidate baskets were built from the filed 6/30 share counts and scored over 8/3–8/28 (n=20):

| basket | RMS | bias |
|---|---|---|
| **v4.2 (published)** | **0.196** | +0.131 |
| v5f — filed 6/30 tail, MRNA pinned to 0.02418 | 0.229 | +0.156 |
| v5c — filed shares, SpaceX pinned | 0.426 | +0.229 |
| v5a — filed shares, uniform scale to 7/31 | 0.561 | −0.259 |
| v5e — filed tail, MRNA free | 0.519 | +0.387 |

The best filed-based candidate loses to v4.2 by 0.033, which against a standard error of ~0.031
on the RMS is **1.1 SE — not significant**, and in the wrong direction anyway.

The reason is structural: **v4.2 is already anchored on the fresher 7/31 disclosure**, and the tail
the filing would improve is only ~20% of gross. A two-month-stale precise book does not beat a
one-month-stale approximate one. **v4.2 stays the published basket.**

## What this leaves open

- **`FRIDAY_SPACEX_BUY` = $262M is falsified** and still live in `daily_nav_log`. Setting it to
  zero is the correct use of the vintage system — the frozen AS-OF rows stay untouched by design,
  and the REVISED view updates to reflect what the filing proved — but it changes the
  recalibration card's core narrative, so it is a decision, not a cleanup.
- **v4.2's +0.13 bias** is persistent (retracted the decay reading on 8/27). De-meaning would cut
  RMS 0.196 → 0.146. The filing did not explain the offset, so it is not stale-tail drift.
- **Next filing:** 9/30/2026 NPORT-P, expected ~late November on the same 51–61 day lag.
