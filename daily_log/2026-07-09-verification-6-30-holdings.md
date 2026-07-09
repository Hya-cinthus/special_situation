# Verification — our theory vs the actual 6/30 holdings

**Analysis 2026-07-09.** Source: **Baron's website holdings as of 2026-06-30** (% of total
investments), provided by the user. NOTE: the SEC **6/30 NPORT-P is NOT filed yet** (latest is
still 3/31, filed 5/22; the 6/30 NPORT-P is expected ~Aug 27) — so this website disclosure is
ahead of the filing. Append-only.

## Scorecard — did our directions hold?

| # | Our call | 6/30 actual | Verdict |
|---|---|---|---|
| 1 | **SpaceX ~33% of the fund** | **32.9%** of total investments | ✅ **RIGHT** |
| 2 | **Underweight TSLA** (vs 24.7% 5/31 snapshot) | **14.1% of gross = ~21.0% of the public sleeve** | ✅✅ **RIGHT & nearly exact** |
| 3 | **Overweight the mid-caps** (FDS/FIG/GWRE/KNSL) | 3 of 4 are LOWER than 5/31; only KNSL up | ⚠️ **mostly WRONG / over-read** |
| 4 | (didn't predict new names) | added MORN/AMZN/MRNA/GOOG/LLY/GOOGL (~3.8% gross) | ❌ **couldn't see these** |
| 5 | **Leverage ~1.0** | consistent; possible slight refinement to ~1.05 | ✅ right to first order |

### 1. SpaceX weight — RIGHT
Baron: SpaceX **32.9%** of total investments. We carried ~33% (32.7% disclosed / ~34% with the
IPO-buy estimate), and validated it on the big SPCX-move days (6/22 −16.4% and 7/7 −6.8%, both
nailed). Confirmed.

### 2. Underweight TSLA — RIGHT, and the magnitude was nearly exact
TSLA is **14.1% of gross = ~21.0% of the public sleeve** — well below our 5/31 snapshot (24.7%)
and 3/31 (30%). Our v1 mark basket trimmed TSLA to **22%** → within ~1 point of the actual 21%.
Of the candidates: optimal (21.7%) was closest, **v1 (22%) excellent**, RONB (17.9%) over-trimmed,
the raw snapshots (24.7–30%) too high. This is the one direction we both called AND sized right,
and it drove the bidirectional daily confirmations (7/2 TSLA-down → actual above; 7/6 TSLA-up →
actual below).

### 3. "Overweight mid-caps" — the one we got WRONG
We inferred the fund was overweight FDS/FIG/GWRE/KNSL. Actual 6/30 vs 5/31 (% of public):
FDS 3.88 vs 4.28 (−0.40), FIG 0.60 vs 0.89 (−0.29), GWRE 3.28 vs 4.14 (−0.86), KNSL 2.54 vs 2.07
(+0.47). So three of the four were **trimmed**, not added. The drift-analysis correlation of the
residual with these names' returns (+0.65) was a **side-effect of the underweight-TSLA**, not a
genuine overweight: with less TSLA, the rest of the book carries relatively more weight, so when
the mid/small-caps move the fund tracks them more than our TSLA-heavy snapshots predict. Lesson:
that correlation didn't prove a *specific* overweight — one name (TSLA) explains it.

### 4. The new names we couldn't see
The fund added six names absent from every snapshot we had (only RONB carried MORN): **Morningstar
1.5%, Amazon 0.8%, Moderna 0.7%, Alphabet-C 0.4%, Eli Lilly 0.3%, Alphabet-A 0.1%** (~3.8% of
gross, ~5.7% of the public sleeve). Our basket spread that weight across the names we tracked,
which is exactly what produced v1's small over-shoot on 7/8 (it over-held the visible names).

### 5. Leverage — right to first order, small possible refinement
The list sums to ~100% of investments (cash ~0, consistent with L≈1.0). A finer read: SpaceX $
(disclosed 36.94M × $170.86 = ~$6.31B) ÷ net AUM $18.1B = ~34.9% of NET, but Baron shows 32.9% of
GROSS → implies gross ≈ $19.2B and **L ≈ 1.05–1.06** (a touch of borrowing back). Our daily tests
couldn't distinguish 1.0 from ~1.06 (the difference is < our daily noise), so "L~1.0" was right to
first order; the 6/30 **NPORT-P (~Aug 27, with net + total assets) settles the exact leverage.**

## Bottom line

Our **headline calls were correct**: SpaceX weight (~33%), underweight-TSLA (nearly exact), and
leverage (~1.0) all held. The **one over-reach** was reading a specific "mid-cap overweight" — the
data says it was really just the TSLA trim, redeployed into **new large/mega-caps** (Amazon,
Alphabet, Eli Lilly, Moderna, Morningstar) we couldn't observe. Net: the daily model tracked well
(~±0.3% typical), the v1 basket marked to ~0.1%, and the framework's discipline (validate TSLA
bidirectionally, don't hand-load the mid-caps) kept us honest — the pro-rata choice was safer than
guessing the mid-cap overweight that turned out not to exist.

## What we changed (going forward, use the 6/30 book)

- **`fund_6_30`** added as a daily NAV-log weighting (`fund_snapshots.WEIGHTS_6_30`), the freshest
  disclosed public book — it already beats `fund_5_31` on most recent days and is often the best
  method. (It uses the 23 names we paste daily; the 6 new names drop out until added — see below.)
- **v2 mark basket** built from the actual 6/30 weights (all 29 names): see
  [2026-07-09 basket-mark v2](2026-07-09-basket-mark-v2.md).
- **Recommend**: add the 6 new tickers (AMZN, GOOGL, GOOG, LLY, MRNA, MORN) to the daily close
  paste so `fund_6_30` and the mark basket capture the full book.
- **Still pending**: the 6/30 NPORT-P (~Aug 27) for the exact leverage + SpaceX share count.
  See [[next-nport-verification]].
