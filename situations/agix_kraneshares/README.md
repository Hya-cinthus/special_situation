# Anthropic exposure via KraneShares AI & Technology ETF (AGIX)

**Situation memo.** The **control case** — structurally different from the rest,
and an honest, SEC-verified small-concentration story.

> **Analysis, not investment advice.** AGIX is an ETF: create/redeem keeps price
> at/near NAV, so there is **no premium-to-NAV play**. Anthropic is a **direct,
> SEC-named holding** (NPORT title "ANTHROPIC, PBC SERIES E-1 PREFERRED STOCK").
> All figures are from SEC NPORT-P (seriesId S000085506).

## Why this one is different

VCX, DXYZ and RVI are closed-end funds where the analysis is the **wrapper
premium**. AGIX is an **ETF**, so that thesis doesn't apply. The analysis pivots
to **concentration**: how much Anthropic you actually own, and how it's changing.

## Key findings (all SEC-verified)

- **Trades at NAV** (ETF arbitrage). No premium to exploit or fear.
- **Lowest fee** of the set: 0.99%.
- **Anthropic is a direct, SEC-named line item** — verifiable, unlike the SPV
  codenames in VCX/DXYZ/RVI. High confidence.
- **Concentration is SMALL and has been DILUTED** as the fund grew on inflows —
  the same mechanism as the Baron/SpaceX case (new cash buys the rest of the
  book, shrinking the headline name's weight):

  | Quarter | Fund net assets | Anthropic $ | Anthropic % |
  |---|---|---|---|
  | 2025-06-30 | $28.3M | $1.00M | 3.53% |
  | 2025-09-30 | $89.7M | $2.98M | 3.32% |
  | 2025-12-31 | $92.6M | $3.89M | 4.20% |
  | 2026-03-31 | $171.5M | $4.72M | **2.76%** |

  Anthropic peaked at 4.20% (Dec) and fell to **2.76%** (Mar) as assets nearly
  doubled. Estimated **~5–6%** now if you re-rate the sleeve for Series H and
  hold everything else flat (`med` confidence).
- **The Anthropic sleeve is up ~50×** since AGIX entered (~$18B → ~$965B), but at
  ~3% of the fund it moves the NAV only modestly.

## Trade-off

Clean, liquid, low-fee, no premium risk, SEC-verifiable — **but low and falling
concentration**. The right vehicle for honest Anthropic exposure without wrapper
games; the wrong one for a concentrated, levered bet.

## Honest correction (process note)

An earlier draft hardcoded "10.74% / $875M" from a bad web read and a parser that
missed the Anthropic line (its NPORT `<name>` is "N/A"; the identity is in
`<title>`). That was wrong. This memo uses the corrected parser reading `<title>`,
giving the SEC-verified ~2.76% above.

## Data lineage

| Series | Source | Confidence |
|---|---|---|
| AGIX daily price | Yahoo Finance | measured/high |
| Net assets + Anthropic % (quarterly) | SEC NPORT-P, **seriesId S000085506**, Anthropic by `<title>` | measured/high |
| Anthropic valuation timeline | press (shared) | med |

Identity note: Krane Shares Trust (CIK 1547576) files NPORT for 100+ ETFs; the
ingest filters strictly on **seriesId S000085506** so no sibling ETF can
contaminate the data.

## Reproduce
```bash
py build.py agix_kraneshares
cd dashboard && py -m http.server 8000   # open agix.html
```
