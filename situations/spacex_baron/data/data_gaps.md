# Data gaps & TODOs — spacex_baron

A running, honest ledger of everything the automated pipeline could **not**
obtain from free public sources, what it would take to fill the gap, and how the
value enters the model. The dashboard renders this file in its Data-Quality
panel. **Nothing here is silently guessed** — gaps are filled with clearly
labeled placeholders so the pipeline still runs end to end.

Legend for "enters model as": how the missing value is currently handled.

---

## Open gaps

### 1. Pre-2019 SpaceX position detail (2017 H1 – 2019 H1) — `confidence: low`
- **Missing:** quarterly SpaceX share count, fair-value mark, and total net
  assets before NPORT-P coverage begins (~2019-Q3). Baron initiated a ~4%
  SpaceX position in 2017 at a ~$20B valuation; granular data is thin.
- **Where to get it:** Baron N-CSR / N-CSRS annual & semi-annual reports
  (2017–2019) and Baron quarterly letters (PDF, baroncapitalgroup.com). These
  are narrative/PDF, not machine-readable XBRL, so they need manual extraction.
- **Enters model as:** a single low-confidence anchor (`spacex_marks.csv`,
  2017 row) plus interpolation. The whole 2017–2019 span is tagged `low` and
  shaded as "soft estimate" on the chart. No fake daily wiggle is manufactured.

### 2. Daily fund shares-outstanding / true daily AUM — `confidence: med`
- **Missing:** free daily shares-outstanding for BPTRX. We have daily NAV/share
  (Yahoo) and quarterly net assets (NPORT-P), but not the daily share count.
- **Where to get it:** Baron transfer-agent data, a paid feed
  (Bloomberg `FUND_TOTAL_ASSETS`, Morningstar Direct), or N-CSR share-activity
  tables (semi-annual only).
- **Enters model as:** shares-outstanding is **linearly interpolated** between
  filing anchors (derived as net_assets / NAV_per_share at each filing). This is
  the primary source of between-anchor reconstruction error and is labeled
  `interpolated` on every affected point. Net flows are inferred from the change
  in derived shares across anchors.
- **Post-last-filing true-up:** the most recent PUBLIC holdings filing is
  2026-03-31; the next is the 2026-06-30 report (filed ~Aug 2026). Monthly NPORT
  reports for Apr/May exist but are **non-public** until the quarter-end filing,
  so fund AUM between is in NO SEC filing. To avoid understating dilution, a
  manually-sourced **reported total net assets** datapoint (`config.AUM_DATAPOINTS`)
  trues up the open segment: AUM = the sourced figure (Bloomberg ~$12.27B /
  Dividend.com ~$12.0B, 2026-05-12, all classes); SpaceX $ is **carried forward**
  from the 3/31 filing (no new mark, private shares can't be added). These points
  are tagged `external_aum`, drawn as a distinct amber hollow diamond, and never
  enter the NPORT anchor table or residuals. This is why the current weight
  (~31%) sits below the 2026-03-31 filed weight (37.5%): ~$1.7–1.9B of net
  inflows since the filing have diluted SpaceX.

### 3. Full public-holdings book at daily resolution — `confidence: med`
- **Missing:** daily prices for every public holding (Tesla, CoStar, Arch
  Capital, Gartner, FactSet, Hyatt, …) to rebuild the public book bottom-up.
- **Where to get it:** the NPORT-P holdings list (we already parse it) + daily
  closes per name (Yahoo, per ticker). Heavy for v1.
- **Enters model as:** v1 anchors the public book at each filing and **drifts it
  daily by a blended proxy** (Tesla daily return for the Tesla sleeve + a
  broad-market growth proxy for the remainder). Method is labeled `proxy_drift`.
  v2 hook: `ingest/public_book.py` to rebuild bottom-up.

### 4. Intermediate SpaceX marks between filings — `confidence: med`
- **Missing:** exact dates Baron re-marked SpaceX between quarter-ends.
- **Where to get it:** Baron quarterly letters often note re-marks; tender-offer
  press dates.
- **Enters model as:** SpaceX dollar value is a **step function** reset to the
  measured NPORT-P value at each filing, with known external mark events
  (`spacex_marks.csv`) applied as step jumps in between. Flat otherwise (mutual
  funds do not re-mark illiquid holdings daily).

### 5. SEC 15% illiquid-cap reconciliation — `confidence: n/a (qualitative)`
- **Missing:** Baron's formal liquidity-classification of SpaceX under Rule
  22e-4. SpaceX is ~26–35% of the fund, far above the 15% illiquid cap.
- **Where to get it:** N-CSR liquidity-risk-management disclosure; NPORT-P
  liquidity classification buckets (`<liquidityCls>` tags, when populated).
- **Enters model as:** documented qualitatively in the situation README; the
  pipeline reads the NPORT liquidity tag where present and flags it.

### 6. Forward IPO realization — `confidence: med (scenario)`
- **Missing:** the IPO has not priced/traded as of 2026-05-24. $1.75T target,
  June 11 pricing, June 12 first trade are S-1 / press targets, not facts.
- **Enters model as:** an explicit, user-adjustable **scenario** ($1.75T /
  $2.0T / $2.4T), never as a realized mark. The status-quo view holds SpaceX at
  the $1.25T standing mark.

---

## Resolved / not needed
- **SpaceX share count & fair value 2019-Q3 → present:** RESOLVED — parsed
  directly from Baron Partners NPORT-P (`ingest/edgar.py`), summing all SpaceX
  tranches. These are `measured`, `high` confidence.
- **External SpaceX valuation marks (2017–2026):** RESOLVED (2026-05-24) — every
  mark in `spacex_marks.csv` was web-verified to a dated primary source
  (Bloomberg / CNBC / Fortune), replacing earlier loosely-attributed figures.
  As an independent check, the publicly-reported per-share tender prices
  RECONCILE with the NPORT-P marks: e.g. 2024-09→2024-12 fund SpaceX value rose
  ×1.65 vs the $112→$185 tender price (×1.65); 2025-09→2025-12 rose ×1.98 vs
  $212→$421 (×1.99). The marks are display/cross-check only — they do NOT feed
  the reconstruction, which uses the filing values directly.
- **Daily BPTRX NAV/share:** RESOLVED — Yahoo Finance chart API (no key).
