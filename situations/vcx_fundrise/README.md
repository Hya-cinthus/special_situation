# OpenAI / Anthropic exposure via Fundrise Innovation Fund (VCX)

**Situation memo.** A pre-IPO bet on OpenAI and Anthropic through a NYSE-listed
closed-end fund — and why the **premium to NAV**, not the underlying AI marks, is
the thing that will determine your return.

> **This is analysis, not investment advice.** Figures trace to a public source
> or are labeled estimates with a confidence level. VCX's OpenAI/Anthropic
> weights are **sponsor-disclosed (Fundrise), not SEC-verifiable** — in the
> NPORT-P they sit inside codenamed SPVs. No datapoint is fabricated.

---

## 1. Thesis — the mirror image of the Baron/SpaceX trade

| | Baron / SpaceX (BPTRX) | **Fundrise / VCX** |
|---|---|---|
| Wrapper | open-end mutual fund | **closed-end fund** (no redemption) |
| Price vs NAV | **at NAV** | **huge premium** (~+1,000%) |
| Underlying mark | stale-**low** (you benefit) | stale-low, but **you overpay through the premium** |
| The edge/risk | re-rating of the underlying | **whether the premium holds or collapses** |

Baron let you buy SpaceX *cheap* before a re-rate. VCX makes you pay ~**11× NAV**
for the same kind of pre-IPO names. You can be completely right on the AI re-rate
and still lose badly if the premium compresses.

**Headline figures (web-verified 2026-05-29; see dashboard for live values):**

| | Value |
|---|---|
| VCX price (5/28) | ~$219.59 |
| NAV/share (sponsor, ~3/31) | ~$18.97 |
| **Premium to NAV** | **~+1,050% (≈11.6× NAV)** |
| Premium range since listing | ~+305% to ~+1,980% |
| For $1 of Anthropic NAV value, you pay | ~$11.60 |
| Lockup expiry (premium-compression catalyst) | 2026-09-19 |

## 2. Three stacked opacities

1. **Wrapper premium** — closed-end funds have no creation/redemption to tether
   price to NAV. VCX has traded between ~4× and ~20× NAV since its 2026-03-19
   direct listing. This is the dominant driver of return.
2. **NAV staleness** — Fundrise publishes NAV periodically, not daily; the
   dashboard carries the last print forward (and shows its age). The underlying
   privates are themselves marked infrequently.
3. **SPV look-through** — OpenAI and Anthropic are **not** named line items in
   the SEC filing. They're held via codenamed SPVs ("Quiet OA Access LP",
   "DBH1 LP", "8VC ANSE SPV", …). The 20.7%/9.9% weights come from Fundrise's
   marketing disclosure and are labeled `med`/sponsor-disclosed throughout.

## 3. The two-way bet (scenario lab)

Return owns two independent legs:

```
new_NAV   = NAV  × (1 + nav_change_from_AI_rerate)
new_price = new_NAV × (1 + target_premium)
return    = new_price / price − 1
```

- **Right on AI, premium collapses → you lose.** A +20% NAV gain with the
  premium normalizing to 0 gives roughly −90% (verified in `tests/test_engine.py`).
- **Premium holds → the AI leg flows through.** But a +1,000% premium holding is
  the bet, not the base case.
- **The AI leg may even be DOWN:** Anthropic's Series H (~$965B) is already
  *above* its reported $400–500B IPO target, so an IPO could re-rate the mark
  **down**.

## 4. Data lineage

| Series | Source | Method | Confidence |
|---|---|---|---|
| VCX daily price | Yahoo Finance chart API | `ingest/price.py` | measured / high |
| NAV per share | Fundrise sponsor disclosure + NPORT net assets | `ingest/nav_log.py` (cowork/bookmarklet log + seed) | med |
| Net assets / holdings | SEC **NPORT-P**, CIK 1867090 | `ingest/edgar.py` | measured / high (but SPV-codenamed) |
| OpenAI/Anthropic weights | Fundrise disclosure | `config.LOOKTHROUGH` | **med, sponsor-disclosed** |
| Underlying valuations | press (CNBC/TechCrunch/Anthropic) | `config.UNDERLYING_MARKS` | med |
| Premium series | computed | `engine/premium.py` (pure, unit-tested) | mixed; per-point labeled |

## 5. Limitations

- **NAV is periodic and sponsor-marked.** The premium shown is price ÷
  last-published NAV; the "true" instantaneous premium could differ.
- **Look-through is not verifiable.** If Fundrise's weights are off, the per-name
  exposure figures move; the premium math (price ÷ NAV) is unaffected.
- **Buying at NAV vs on-exchange.** Existing Fundrise account holders may access
  the fund nearer NAV via the platform; the NYSE price is what this study uses.
- **Lockup dynamics are a catalyst, not a forecast.** We annotate 9/19; we don't
  predict the post-lockup premium.

## 6. Reproduce

```bash
py build.py vcx_fundrise         # ingest price + NPORT -> dashboard/data/vcx_fundrise.json
py -m unittest discover -s situations/vcx_fundrise/tests -v
cd dashboard && py -m http.server 8000    # open vcx.html
```
