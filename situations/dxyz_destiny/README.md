# Pre-IPO tech (SpaceX/OpenAI/Anthropic) via Destiny Tech100 (DXYZ)

**Situation memo.** A second closed-end-fund premium case — and a deliberate
**contrast** to VCX.

> **Analysis, not investment advice.** Figures trace to a public source or are
> labeled estimates with a confidence level. SpaceX/OpenAI/Anthropic are held via
> codenamed SPVs (e.g. "DXYZ SpaceX I LLC", "DXYZ OAI I LLC"); look-through
> weights are **sponsor/press-disclosed, not SEC-verifiable**.

## Why this one (vs VCX)

| | VCX (Fundrise) | **DXYZ (Destiny)** |
|---|---|---|
| Premium vs **stale** NAV | ~+1,000% (extreme) | **~+110%** (modest) |
| Premium vs **mark-to-market** NAV | ~+480% | **~+85%** |
| NAV disclosure | sponsor, sticky | **quarterly, published** → measurable signal |
| Cash drag | low | **~46% cash/Treasuries** at base |
| Character | extreme dislocation | **sentiment signal** |

DXYZ is the "measurable premium" case: NAV is published each quarter, so the
premium reads like a tradeable sentiment gauge rather than a stale-mark illusion.
It has swung from roughly +300% to +2,000% historically and now sits near +110%.

## Key honest findings

- **Mark-to-market barely moves the premium** (+110% → +85%). Two reasons, both
  documented: (1) the fund is **~46% cash/Treasuries** (NPORT 12/31), which can't
  re-rate; (2) from the 3/31 NAV base only **Anthropic** has had a new round
  (Series G $380B → Series H $965B); SpaceX and OpenAI are flat since their 3/31
  marks. So unlike VCX, DXYZ's NAV is *not* badly stale — the premium is mostly
  real sentiment, not a marking artifact.
- **NPORT confirms the SPV structure**: SpaceX via "DXYZ SpaceX I LLC" (12.4%) +
  "MWAM VC SpaceX-II" (3.6%); OpenAI via "DXYZ OAI I LLC" (2.1%); plus ~46% in
  First American Treasury. OpenAI/Anthropic are not named directly.
- **Anthropic weight is the least certain input** — sources span ~6% to ~18.1%
  (a May-12 filing reference). We use 10% and flag the sensitivity.
- **No single dated lockup** (unlike VCX's 9/19); instead an **ATM-offering
  overhang** — Destiny issues new shares into the premium (raised ~$570M via ATM
  in 2025), which structurally caps it.

## Data lineage

| Series | Source | Confidence |
|---|---|---|
| DXYZ daily price | Yahoo Finance | measured / high |
| NAV per share (quarterly) | Destiny / CEFConnect + NPORT net assets | high (sparse) |
| Net assets / holdings | SEC NPORT-P, CIK 1843974 | measured (SPV-codenamed) |
| Look-through weights | sponsor/press | **low–med, not SEC-verifiable** |
| Underlying valuations | press (shared with VCX timelines) | med |

## Reproduce

```bash
py build.py dxyz_destiny
cd dashboard && py -m http.server 8000   # open dxyz.html
```
