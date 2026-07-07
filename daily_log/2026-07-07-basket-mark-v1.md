# Position-mark basket — v1 (for marking BPTIX P&L)

**Built 2026-07-07, priced as of the 2026-07-06 close (BPTIX NAV $295.04).** Append-only; this is
v1 of the mark methodology and will be superseded by a dated v2 (not edited in place). Machine-readable
copy: `situations/spacex_baron/data/position_mark_basket_2026-07-06.csv`.

## What this is

A fixed replicating basket for **one BPTIX share**: hold it (SpaceX marked via SPCX + the public stocks
+ cash) and its value tracks BPTIX's NAV, so day-to-day changes ≈ the P&L on the BPTIX position. Scaled
to the **130,000-share position** in the last column. It is a PROXY (not the fund's exact book, which is
disclosed only quarterly) — good enough to mark daily P&L between filings.

## The basket

Per BPTIX share = **0.60 SPCX (SpaceX) + the 23 public stocks below + $0 cash** (≈ $295, = NAV).

| Component | shares / BPTIX sh | shares × 130,000 | % of NAV | px (7/6) |
|---|---:|---:|---:|---:|
| **SPCX** (SpaceX, private→marked via SPCX) | 0.60000 | 78,000 | 32.6% | 160.42 |
| TSLA | 0.10418 | 13,544 | 14.8% | 419.77 |
| MSCI | 0.02326 | 3,024 | 4.8% | 614.04 |
| H | 0.06755 | 8,782 | 4.4% | 193.48 |
| SCHW | 0.11783 | 15,318 | 4.0% | 100.62 |
| SHOP | 0.09612 | 12,495 | 3.9% | 120.14 |
| ACGL | 0.10452 | 13,588 | 3.6% | 101.81 |
| IT | 0.07419 | 9,645 | 3.4% | 135.11 |
| SPOT | 0.02016 | 2,620 | 3.3% | 483.01 |
| FDS | 0.03493 | 4,541 | 3.0% | 252.20 |
| GWRE | 0.06193 | 8,051 | 2.9% | 137.59 |
| CSGP | 0.27540 | 35,802 | 2.7% | 28.70 |
| IDXX | 0.01344 | 1,748 | 2.6% | 564.98 |
| CHH | 0.06213 | 8,077 | 2.3% | 107.67 |
| BIRK | 0.13154 | 17,101 | 2.1% | 46.16 |
| ONON | 0.16469 | 21,410 | 2.1% | 36.87 |
| VRSK | 0.03080 | 4,004 | 2.0% | 187.79 |
| KNSL | 0.01227 | 1,595 | 1.4% | 347.23 |
| MTN | 0.02679 | 3,483 | 1.3% | 142.12 |
| RRR | 0.05855 | 7,611 | 1.3% | 65.04 |
| FIG | 0.08690 | 11,297 | 0.6% | 21.08 |
| GLPI | 0.03498 | 4,548 | 0.5% | 43.54 |
| HEI | 0.00169 | 220 | 0.2% | 365.31 |
| HEI-A | 0.00235 | 306 | 0.2% | 262.63 |
| **CASH** | — | $0 | 0.0% | — |
| **TOTAL** | | | 100.0% | ≈ $295.06 |

## The high-confidence directions it uses

1. **SpaceX ≈ 33% of NAV, held constant.** = the disclosed 3/31 SpaceX share count ÷ current BPTIX
   shares out = **0.60 SPCX-equivalent shares** per BPTIX share (matches the main page's 32.7%). The
   SpaceX weight is validated — on 6/22 SPCX moved −16.4% and we nailed the NAV, so the sizing is right.
2. **Leverage = 1.0 → cash ≈ $0** (fully invested; the ~3% / ~$0.65B buffer was consumed by ~$2.6B of
   redemptions by mid-June and has stayed gone). Confirmed by every big-basket day since 6/16.
3. **Underweight TSLA.** The public sleeve is the freshest disclosed BPTIX weights (5/31) with TSLA
   **trimmed 24.7% → 22%** — the one adjustment we've validated bidirectionally (7/2 TSLA-down: actual
   above the snapshots; 7/6 TSLA-up: actual below; error ordering flips with TSLA's direction). The 22%
   level is corroborated by the NAV-implied ~2–3% overweight and by RONB 17.9% / optimal 21.7%.

## What it deliberately does NOT do (to avoid overfitting)

- **No per-name mid-cap tuning.** We're confident the fund is overweight the mid-caps (FDS/FIG/GWRE/KNSL),
  but the TSLA trim is spread **pro-rata** across all 22 other names, not hand-loaded onto those four —
  the per-name magnitude isn't known to that precision, so hard-coding it would fit noise.
- **No fitted basket.** We did NOT use the min-variance "optimal" basket (it's optimized to our own
  history) or swap in RONB's roster (Baron's ETF holds different names — IBKR/MORN/FIGS/ABNB/LYV — and
  omits IT/CSGP/FIG that BPTIX holds). Only SEC-disclosed BPTIX names, freshest disclosed weights, one
  validated tilt.

## Known caveats / bands (so the mark isn't over-trusted)

- **SpaceX 0.60 vs 0.63.** 0.60 uses only the SEC-hard 3/31 share count. If you fold in the estimated
  ~$262M 6/12 IPO-day buy, it's ~0.63 (weight ~34%), which tracked the 6/22 move marginally better. Band
  ≈ ±1.7% of NAV. SPCX is the public mark of a private, still-locked-up holding.
- **TSLA 22% ± ~2%** and the mid-cap tilt is under-captured — expect a small miss on days those specific
  names move a lot (our residuals have been ≈ ±0.3–0.5% of NAV on such days).
- **It's a proxy, not the book.** Excludes fees, exact intraday timing, and any post-5/31 holding changes
  we can't see yet.

## How to mark

`basket value(t) = 0.60·SPCX(t) + Σ (shares_i · price_i(t)) + cash` for one BPTIX share, ×130,000 for the
position. The daily change ≈ the day's P&L on the BPTIX position. Reconcile to the actual BPTIX NAV when
it posts (Yahoo, ~1-day lag) — the gap is the proxy error (should be small).

## Data used / reproduce

- **7/6 fund anchors** (`dashboard/data/daily_nav_log.json`, row 2026-07-06): NAV 295.04, SpaceX weight,
  leverage 1.0, shares-out; **SpaceX shares** from the disclosed 3/31 NPORT count.
- **Public weights**: `meta.compositions.fund_5_31` (the 5/31 NPORT-P disclosure) with TSLA trimmed to 22%.
- **Prices**: the 2026-07-06 closes in `daily_nav_log.ENTRIES`.
- **The tilt rationale**: [2026-07-02 drift diagnosis](2026-07-02-analysis-drift-diagnosis.md).
- CSV: `situations/spacex_baron/data/position_mark_basket_2026-07-06.csv`.

## Next update

The **6/30/2026 NPORT-P (~Aug 27)** gives the true current weights — at that point rebuild as **v2**
(a new dated file) with the actual TSLA / mid-cap sizing and the confirmed SpaceX share count.
See [[next-nport-verification]].
