# SpaceX / OpenAI / Anthropic via ARK Venture Fund (ARKVX)

**Situation memo.** A new structure type for the monitor — an actively-managed
**interval fund** — and the cleanest, fully SEC-named private basket of the set.

> **Analysis, not investment advice.** ARKVX transacts at NAV (no wrapper premium
> like the CEFs), but redemptions are **gated** to ~quarterly tenders capped near
> 5% — so the risk frame is a **liquidity discount, not a premium**. Private
> holdings are **directly SEC-named** in NPORT (high confidence). Underlying
> valuation marks are press-sourced estimates.

## Why this one is different (methodology)

Unlike the prior six vehicles, ARKVX is an **interval fund**:
- **At NAV** — like BPTRX (mutual fund) and AGIX (ETF), no premium/discount to exploit.
- **But not freely redeemable** — you can only exit via periodic repurchase offers
  (quarterly, typically ≤5% of the fund). In a rush you may be stuck or sell below
  NAV. That illiquidity is the cost; the page frames it as a **liquidity discount**.
- **Actively managed** — ARK sources private deals directly, so concentration shifts.

So the analysis pivots away from premium math (irrelevant here) toward
**look-through concentration + mark-to-market + liquidity risk**.

## Key findings (SEC-verified, NPORT 2026-01-30)

- **Cleanest disclosure of the whole monitor**: SpaceX, OpenAI, Anthropic, xAI,
  Neuralink, Figure AI, Groq, etc. are **named directly** — no SPV codenames.
- **SpaceX is the top holding**: 8.06% + 2.87% = **~10.9%** at 1/30. ARK's own
  site shows **~17.0% at 3/31** (newer; fund growth + SpaceX re-rate). We use the
  SEC-verified 1/30 figure and flag the newer ARK number.
- **OpenAI ~2.9%** (3 tranches), **Anthropic ~2.5%** — total tracked private
  exposure ~16% of the fund; the rest is other privates + cash/Treasuries.
- **Concentration history** (fund grew $55M → $554M, ~10×):

  | Quarter | Net assets | SpaceX | OpenAI | Anthropic |
  |---|---|---|---|---|
  | 2024-04 | $55M | 13.4% | 4.2% | 4.9% |
  | 2025-01 | $123M | 17.0% | 3.0% | 4.0% |
  | 2025-07 | $207M | 11.6% | 5.2% | 2.5% |
  | 2025-10 | $378M | 7.7% | 4.3% | 3.3% |
  | 2026-01 | $554M | 10.9% | 2.9% | 2.5% |

- **Scenario NAV** (at NAV, return ≈ NAV move): bull **+8%** / bear **−5%** —
  modest, because the private basket is only ~16% of the fund.
- **High fee**: ~2.88%/yr (active interval fund) — the priciest of the set.

## Verdict

The most honest *structure* (at NAV, SEC-named) but you pay for it twice: a high
~2.9% fee and **locked-up liquidity**. Good for a patient, diversified private-AI
basket; bad if you need to get out or want a concentrated SpaceX bet (BPTRX is
cleaner for that).

## Data lineage

| Series | Source | Confidence |
|---|---|---|
| ARKVX daily NAV | Yahoo Finance | measured/high |
| Net assets + holdings (quarterly) | SEC NPORT-P, CIK 1905088, names summed by tranche | measured/high |
| SpaceX/OpenAI/Anthropic weights | SEC NPORT (directly named) | high |
| Underlying valuation timeline | press (shared registry) | med |

## Reproduce
```bash
py build.py arkvx_arkventure
cd dashboard && py -m http.server 8000   # open arkvx.html
```
