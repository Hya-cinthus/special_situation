# SpaceX exposure via Baron Partners Fund (BPTRX)

**Situation memo.** Reconstructing the effective SpaceX weight inside the Baron
Partners Fund over time, and pricing the IPO re-rating for an investor who
bought the fund on **2026-05-20**.

> **This is analysis, not investment advice.** Every figure traces to a public
> source or is a clearly-labeled estimate/interpolation with a confidence level.
> No datapoint is fabricated. See [`data/data_gaps.md`](data/data_gaps.md) for
> everything we could *not* source.

---

## 1. Thesis

Baron Partners Fund (BPTRX, retail; BPTIX inst.; BPTUX R6 — one portfolio, three
share classes) is the most liquid, lowest-friction way for a public-markets
investor to hold a large SpaceX position **before** the IPO. As of the user's
2026-05-20 entry the fund carried SpaceX at roughly the **$1.25T private mark**
(the post-xAI-merger combined entity). SpaceX filed its S-1 the same day, with
an IPO targeted at **~$1.75T** (pricing ~2026-06-11, first trade ~2026-06-12 on
Nasdaq as **SPCX**). When SpaceX trades publicly the fund must mark-to-market,
mechanically stepping up both NAV and the SpaceX weight.

**Headline reconstructed figures (data through 2026-05-22):**

| | Value |
|---|---|
| Est. SpaceX weight now | **~36%** of fund NAV |
| Your effective SpaceX exposure per $1 invested on 2026-05-20 | **~$0.37** |
| SpaceX $ held by the fund (last filing, all tranches) | ~$3.9B |
| Reconstructed fund AUM | ~$10.8B |
| Standing private mark | $1.25T |
| IPO re-rating (status → $1.75T / $2.0T / $2.4T) | weight **36% → 44% / 48% / 52%**, NAV step-up **+14% / +22% / +33%** |

The alpha is the **stale-mark re-rating**: you are buying NAV that still embeds a
$1.25T SpaceX before a likely $1.75T+ public mark.

## 2. Mechanism — what actually moves the weight

The fund is an **open-end mutual fund** (converted from a partnership 2003-04-30),
priced daily at NAV with daily creations/redemptions. SpaceX is **private** and
can only be accumulated through episodic primary rounds / secondaries; Baron
marks it at fair value, anchored to the latest observable transaction. So the
daily SpaceX weight `w = S / (S + P)` is driven by three channels:

1. **Mark** — Baron re-marks SpaceX (`S`) on discrete dates (tenders, the xAI
   merger). Step function, not daily drift.
2. **Public-drift** — the public book `P` (Tesla, CoStar, Arch Capital, Gartner,
   FactSet, Hyatt, …) moves with daily prices.
3. **Flow** — net creations/redemptions change total NAV. A private holding
   can't absorb new cash, so **inflows dilute** SpaceX; **redemptions are met by
   selling liquid public names first, so they concentrate** SpaceX.

**Empirical decomposition (first filing → today, cumulative Δ weight):**

| Channel | Contribution |
|---|---|
| Mark (re-marks) | **+37 pp** |
| Public-drift | −12 pp |
| Flow | −2.4 pp |

The SpaceX weight grew from ~6% (2019) to ~36% (2026) **almost entirely on
re-marks**, lightly offset by a rising public book and modest net inflows. (The
first-order attribution sums to ~+23 pp vs the actual +30 pp; the gap is the
expected linearization error over very large moves and is shown, not hidden.)

## 3. The user's dilution hypothesis — verdict

> User's assumption: *"private shares can't be added, so net inflows dilute the
> SpaceX weight."*

**Directionally correct, but incomplete — and we tested it against the filings.**

- **"Can't add" holds in practice.** Across 27 quarterly NPORT-P filings
  (2019-Q3 → 2026-Q1), the SpaceX position size was **flat in 24 of 26
  quarter-over-quarter transitions**. Baron changed it only episodically:
  step-ups consistent with primary-round participation (2020-Q3; a 2022-Q1
  change discussed below) and one ~2% trim (2024-Q3).
- **But it's bidirectional, not one-way.** The 2024-Q3 trim is consistent with
  selling SpaceX-adjacent exposure, and redemptions structurally *raise* the
  weight (public sold first). Our scenario lab models both directions.
- **Caveat on share counts.** NPORT-P `<balance>` units for SpaceX are *not* a
  clean share count — tranches are denominated inconsistently (some ~10× others;
  the 2022-Q1 unit jump coincided with ~flat dollar value, i.e. a denomination
  change, **not** a ~$2B purchase). The reliable economic signals are the
  **dollar fair value** and the **per-tranche mark**, which is what the engine
  uses. We do **not** claim trades from raw unit deltas.

Net: inflows do dilute, but the dominant driver of the weight has been re-marks,
not flows — so an investor's exposure has *risen* despite net inflows.

## 4. The SEC 15% illiquid cap

Open-end funds are limited to ~15% in **illiquid** investments (not sellable
within 7 days without a significant price impact) under Rule 22e-4. SpaceX is
~36% of BPTRX — far above 15% **if** it were classified illiquid.

**Finding:** the only way the fund is compliant is that it does **not** classify
SpaceX as "illiquid." The plausible justification is the **active, recurring
secondary market** in SpaceX stock — roughly semi-annual tender offers that
provide a real exit channel — letting Baron place it in a more-liquid bucket.

**Honest limitation:** we cannot *prove* the classification from public data.
Rule 22e-4 liquidity buckets are reported in the **non-public** portion of
NPORT-P (the `<liquidityCls>` tags are blank in the public filing), so the bucket
Baron assigns to SpaceX is **not publicly disclosed**. This is logged as
[`data_gaps.md` #5](data/data_gaps.md). The cap nonetheless **bounds** how high
the weight can structurally go and is a key risk flag: a freeze in the secondary
market would pressure the classification.

## 5. Data lineage

| Series | Source | Method | Confidence |
|---|---|---|---|
| SpaceX share count, fair value, net assets (quarterly) | SEC **NPORT-P**, Baron Select Funds CIK 1217673, series "Baron Partners Fund"; all SpaceX tranches summed | `ingest/edgar.py` | **measured / high** (2019-Q3→) |
| Daily NAV/share | Yahoo Finance chart API (no key) | `ingest/nav.py` | **measured / high** |
| SpaceX valuation marks (2017 init; current $1.25T; IPO scenarios) | Web-verified news/press (CNBC, Bloomberg) + Baron narrative; see [`spacex_marks.csv`](data/spacex_marks.csv) | curated, sourced | high (recent), low (2017) |
| Daily SpaceX weight | reconstruction | `engine/reconstruct.py` | mixed; labeled per point |
| Shares outstanding / daily AUM | derived `net_assets / NAV` at filings, **interpolated** between | engine | med (interpolated) |
| Public book daily | total NAV − SpaceX value (cash folded in) | engine | med |

The reconstruction is **pinned to the measured filing values at every anchor**,
so by construction the reconstructed weight at a filing equals the filed weight
(enforced by `tests/test_engine.py`).

## 6. Model limitations (read before trusting a number)

- **Daily weight is reconstructed, not observed.** Between quarterly filings we
  hold the SpaceX mark and share count flat and interpolate shares-outstanding.
  The **anchor-to-anchor residual** chart shows where this misses — notably
  **2025-Q4 (predicted 16% vs measured 32%)**, where a large between-filing
  re-mark is invisible to a flat-carry model. We surface this loudly.
- **Public book is a proxy.** v1 treats public + cash as a residual that drifts
  with reconstructed AUM, not a bottom-up rebuild of each holding × daily price.
- **AUM is an estimate** between filings (interpolated shares). Third-party AUM
  prints disagree (one source $4.16B — likely a single share class — vs ~$10–12B
  all-in); we anchor to NPORT net assets ($10.36B at 2026-03-31).
- **The IPO is a scenario, not a fact.** $1.75T / June 12 / SPCX are S-1 and
  press *targets* as of 2026-05-24, not realized. The status-quo view holds
  SpaceX at $1.25T.
- **2017–2019 is soft.** Pre-NPORT-P, the weight is interpolated from a single
  low-confidence 2017 narrative anchor (~4% at ~$20B). Shaded as "soft estimate";
  no fake daily detail is manufactured.

## 7. What would make this more precise

1. **Bottom-up public book** — rebuild each public holding × daily close from
   NPORT-P (we already parse the holdings list). Removes the proxy-drift error.
2. **Real daily shares-outstanding / flows** — a paid feed (Bloomberg
   `FUND_TOTAL_ASSETS`, Morningstar Direct) replaces the interpolation; clean
   hooks left in `data_gaps.md` #2.
3. **Exact intra-quarter re-mark dates** — from Baron quarterly letters — would
   collapse the 2025-Q4-style residual.
4. **N-CSR liquidity disclosure** — to firm up the 15%-cap classification.

## 8. Reproduce

```bash
py build.py                 # ingest -> reconstruct -> emit dashboard/data/spacex_baron.json
py -m unittest discover -s situations/spacex_baron/tests -v
cd dashboard && py -m http.server 8000   # open http://localhost:8000
```
