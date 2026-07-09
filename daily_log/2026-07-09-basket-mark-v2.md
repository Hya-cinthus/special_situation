# Position-mark basket — v2 (actual 6/30 weights)

**Built 2026-07-09, priced as of the 2026-07-08 close (BPTIX NAV $283.37).** Supersedes
[v1](2026-07-07-basket-mark-v1.md). Append-only. Machine-readable:
`situations/spacex_baron/data/position_mark_basket_v2_2026-07-08.csv`.

## What changed from v1

v1 guessed the public weights (5/31 disclosure + a TSLA trim). v2 uses the **actual 6/30 holdings**
(Baron's website, % of total investments), so:
- Real weights for all 29 names (no guessing) — TSLA now at its true ~14.1% of gross.
- **Adds the 6 new names** v1 was missing: MORN, AMZN, MRNA, GOOG, LLY, GOOGL.
- SpaceX still **0.60 SPCX-equiv shares** (disclosed 3/31 count; the 6/30 filing confirms ~33%).
- Cash ~$0 (L≈1.0; a finer read hints L≈1.05 — pending the NPORT; see the verification note).

v1 marked to within ~0.1–0.2% of NAV over its life, so v2 should be at least as good and better on
days the new names move.

## The basket

Per BPTIX share = **0.60 SPCX + the 29 public stocks below + $0 cash** (= $283.37 = NAV).

| Component | shares / BPTIX | × 130,000 | % NAV | px (7/8) | new |
|---|---:|---:|---:|---:|:--:|
| **SPCX** (SpaceX) | 0.60000 | 78,000 | 31.4% | 148.30 | |
| TSLA | 0.10381 | 13,496 | 14.4% | 394.06 | |
| SCHW | 0.11411 | 14,835 | 4.1% | 101.70 | |
| H | 0.06193 | 8,051 | 4.1% | 187.40 | |
| MSCI | 0.01873 | 2,434 | 4.0% | 604.23 | |
| SHOP | 0.09004 | 11,706 | 3.8% | 119.22 | |
| ACGL | 0.09386 | 12,202 | 3.4% | 102.01 | |
| SPOT | 0.01854 | 2,410 | 3.2% | 485.22 | |
| FDS | 0.03044 | 3,957 | 2.7% | 247.82 | |
| IT | 0.05386 | 7,001 | 2.6% | 134.68 | |
| MTN | 0.04646 | 6,040 | 2.4% | 143.63 | |
| VRSK | 0.03518 | 4,574 | 2.4% | 189.67 | |
| IDXX | 0.01201 | 1,561 | 2.4% | 555.67 | |
| CHH | 0.06272 | 8,154 | 2.4% | 106.39 | |
| CSGP | 0.22744 | 29,567 | 2.4% | 29.34 | |
| GWRE | 0.04702 | 6,113 | 2.3% | 135.74 | |
| RRR | 0.08706 | 11,318 | 1.9% | 63.32 | |
| BIRK | 0.11805 | 15,346 | 1.8% | 44.24 | |
| KNSL | 0.01426 | 1,853 | 1.7% | 345.96 | |
| ONON | 0.12760 | 16,588 | 1.6% | 36.38 | |
| MORN | 0.02637 | 3,428 | 1.5% | 165.03 | ✓ |
| AMZN | 0.00953 | 1,239 | 0.8% | 243.62 | ✓ |
| MRNA | 0.02752 | 3,578 | 0.7% | 73.80 | ✓ |
| GLPI | 0.02705 | 3,516 | 0.4% | 42.91 | |
| GOOG | 0.00324 | 421 | 0.4% | 358.71 | ✓ |
| FIG | 0.05356 | 6,962 | 0.4% | 21.67 | |
| LLY | 0.00072 | 93 | 0.3% | 1215.83 | ✓ |
| HEI | 0.00250 | 325 | 0.3% | 347.78 | |
| HEI-A | 0.00231 | 301 | 0.2% | 251.03 | |
| GOOGL | 0.00080 | 104 | 0.1% | 361.92 | ✓ |
| **CASH** | — | $0 | 0.0% | — | |
| **TOTAL** | | | 100.0% | ≈ $283.37 | |

## How to mark / caveats

`basket value(t) = 0.60·SPCX(t) + Σ shares_i·price_i(t)` per BPTIX share, ×130,000 for the position.
Reconcile to actual BPTIX NAV (Yahoo, ~1-day lag); the gap is proxy error (small). Caveats:
- SpaceX 0.60 = disclosed 3/31 count; ~0.63 if you include the estimated 6/12 buy (~±1.7% of NAV).
- Cash 0 / L≈1.0 is the working assumption; if the NPORT shows L≈1.05 there's a small (~5%) public
  over-size + a negative-cash (borrow) line — a v2.1 tweak at the filing.
- Weights are 6/30; they drift between disclosures (the daily NAV log tracks that drift).

## Data used
6/30 weights: `fund_snapshots.WEIGHTS_6_30` (Baron website). Prices: 7/8 closes (23 from the daily
log + AMZN/GOOGL/GOOG/LLY/MRNA/MORN fetched from Yahoo). NAV/SpaceX-share anchors: the 7/8 daily-log
row. Verdict on our prior theory: [2026-07-09 verification](2026-07-09-verification-6-30-holdings.md).
