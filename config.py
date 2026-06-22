"""
Repo-wide configuration for the Special Situations research repo.

Everything time-sensitive or situation-specific that the pipeline needs lives
here so the code stays declarative. All dates are ISO (YYYY-MM-DD).

NOTE ON DATA HONESTY: the marks/dates below were web-verified on 2026-05-24
(see situations/spacex_baron/README.md for sources). They carry knowledge-cutoff
risk and should be re-verified at runtime. Confidence labels travel with every
datapoint downstream; nothing here is treated as ground truth without a source.
"""

from datetime import date

# ---------------------------------------------------------------------------
# Global
# ---------------------------------------------------------------------------

# A descriptive User-Agent is REQUIRED by SEC EDGAR (they 403 generic agents).
# Put a real contact per SEC fair-access policy.
SEC_USER_AGENT = "special-situations-research weipeng_shao@berkeley.edu"

# Folder the frontend reads from. build.py writes one JSON per situation here.
DASHBOARD_DATA_DIR = "dashboard/data"

# Situations the build pipeline knows about. Each maps to situations/<key>/.
SITUATIONS = ["spacex_baron", "vcx_fundrise", "dxyz_destiny", "rvi_robinhood",
              "agix_kraneshares", "arkvx_arkventure"]


# ===========================================================================
# CROSS-VEHICLE OVERVIEW: normalized private-company + vehicle registries
# ===========================================================================
# These power the one-page research memo (dashboard/overview.html). They are
# CURATED, web-verified scenario inputs — every number carries a source +
# confidence. bear/base/bull are WHOLE-COMPANY valuations (USD). `current` is
# the mark the vehicles are presently carrying (what scenarios scale FROM).
# Ranges, not false precision: where reports conflict we widen bear..bull.

PRIVATE_COMPANIES = {
    "SpaceX": {
        "sector": "Space / satellite (Starlink)",
        # IPO PRICED 2026-06-03: $135/sh, 555.6M shares = $75B raise, $1.77T valuation.
        # The IPO mark is now CONFIRMED (no longer a target). base = IPO price.
        "current": 1.77e12,
        "bear": 1.40e12, "base": 1.77e12, "bull": 2.20e12,
        "last_confirmed": {"val": 1.77e12, "date": "2026-06-03",
                           "source_type": "IPO priced ($135/sh)", "confidence": "high"},
        "rumored_range": "IPO PRICED $135/sh = $1.77T (6/3); 555.6M shares ($75B raise) + 83.3M greenshoe; first trade 6/12 Nasdaq SPCX",
        "source_url": "https://www.cnbc.com/2026/06/03/spacex-ipo-stock-price-roadshow-musk.html",
        "notes": "IPO priced $135/sh at $1.77T (6/3/2026), assuming EchoStar spectrum + Cursor deals close. "
                 "Bull = first-day pop; bear = trades below offer. Funds still carry the stale $1.25T "
                 "private mark until they re-mark to the public price after 6/12.",
    },
    "OpenAI": {
        "sector": "AI foundation models",
        "current": 852e9,
        "bear": 500e9, "base": 852e9, "bull": 1.10e12,
        "last_confirmed": {"val": 852e9, "date": "2026-03-31",
                           "source_type": "funding round", "confidence": "high"},
        "rumored_range": "$852B last round; secondary chatter $1T+; no firm IPO date",
        "source_url": "https://www.cnbc.com/2026/03/31/openai-funding-round-ipo.html",
        "notes": "Heavy losses ($4.9B+); bull on revenue scale, bear on AI-capex sentiment turn.",
    },
    "Anthropic": {
        "sector": "AI foundation models (Claude)",
        "current": 965e9,
        "bear": 500e9, "base": 965e9, "bull": 1.30e12,
        "last_confirmed": {"val": 965e9, "date": "2026-05-28",
                           "source_type": "funding round (Series H)", "confidence": "high"},
        "rumored_range": "Series H ~$965B; IPO TARGET only $400–500B (Oct-2026) — could re-rate DOWN",
        "source_url": "https://www.cnbc.com/2026/05/28/anthropic-open-ai-startup-value.html",
        "notes": "KEY ASYMMETRY: latest private mark ($965B) is ABOVE the reported IPO target ($400-500B). "
                 "Bear reflects an IPO at/below target.",
    },
    "Databricks": {
        "sector": "Data / AI infrastructure",
        "current": 134e9, "bear": 100e9, "base": 134e9, "bull": 200e9,
        "last_confirmed": {"val": 134e9, "date": "2025-12-16",
                           "source_type": "funding round (Series L)", "confidence": "high"},
        "rumored_range": "$134B Series L (Dec-2025); 2026 IPO candidate",
        "source_url": "https://www.cnbc.com/2025/12/16/databricks-funding-valuation.html",
        "notes": "Profitable-ish, ~$5B+ ARR; cleaner story than the AI labs.",
    },
    "Anduril": {
        "sector": "Defense tech",
        "current": 61e9, "bear": 40e9, "base": 61e9, "bull": 90e9,
        "last_confirmed": {"val": 61e9, "date": "2026-05-13",
                           "source_type": "funding round (Series H)", "confidence": "high"},
        "rumored_range": "$61B Series H (May-2026); secondary chatter higher",
        "source_url": "https://techcrunch.com/2026/05/13/anduril-raises-5b-doubles-valuation-to-61b/",
        "notes": "Doubled in ~1yr; defense-budget tailwind.",
    },
    "Ramp": {
        "sector": "Fintech (spend mgmt)",
        "current": 32e9, "bear": 22e9, "base": 32e9, "bull": 45e9,
        "last_confirmed": {"val": 32e9, "date": "2025-11-17",
                           "source_type": "funding round", "confidence": "high"},
        "rumored_range": "$32B (Nov-2025); in talks at $40B+ (May-2026)",
        "source_url": "https://news.crunchbase.com/venture/fintech-unicorn-ramp-300m-raise-lightspeed/",
        "notes": "Fast revenue growth; bull on the rumored $40B+ round.",
    },
}

# Curated per-vehicle research metadata (type, structure risk, data-quality
# rationale, the one key risk, and how clean the exposure is). Numbers come from
# the emitted per-vehicle JSON; these are the qualitative judgments.
VEHICLE_META = {
    "spacex_baron": {
        "ticker": "BPTIX", "name": "Baron Partners Fund", "type": "Open-end mutual fund",
        "headline": "SpaceX", "buyable": "Mutual fund (buy at NAV daily)",
        "fee": "1.05% (+ ~0.95% interest on leverage)", "liquidity": "Daily at NAV",
        "data_confidence": "high",
        "confidence_reasons": "SEC NPORT-P quarterly, SpaceX re-marked each filing; only between-filing AUM is estimated.",
        "structure_note": "Levered (~113% long). At NAV — no wrapper premium.",
        "key_risk": "Stale $1.25T SpaceX mark + flow dilution; leverage cuts both ways.",
        "reason_buy": "Cleanest large SpaceX exposure at NAV; IPO re-rate not yet in NAV.",
        "reason_avoid": "Diluted by heavy inflows (37%→~27%); not a pure-play.",
    },
    "vcx_fundrise": {
        "ticker": "VCX", "name": "Fundrise Innovation Fund", "type": "Closed-end fund",
        "headline": "Anthropic", "buyable": "NYSE (or at NAV via Fundrise platform)",
        "fee": "~1.85% all-in", "liquidity": "Exchange (no redemption); 9/19 lockup",
        "data_confidence": "low",
        "confidence_reasons": "OpenAI/Anthropic held via codenamed SPVs; weights sponsor-disclosed, NAV stale & sticky.",
        "structure_note": "Extreme premium to NAV; lockup-expiry supply shock 2026-09-19.",
        "key_risk": "~+1,000% stale / ~+480% MTM premium — premium compression dwarfs upside.",
        "reason_buy": "Highest Anthropic concentration of the set (if premium holds).",
        "reason_avoid": "You massively overpay through the wrapper; opaque SPVs.",
    },
    "dxyz_destiny": {
        "ticker": "DXYZ", "name": "Destiny Tech100", "type": "Closed-end fund",
        "headline": "SpaceX", "buyable": "NYSE", "fee": "~2.5%",
        "liquidity": "Exchange; ATM-offering overhang",
        "data_confidence": "low",
        "confidence_reasons": "SpaceX/OpenAI/Anthropic via SPVs; ~46% cash; quarterly NAV.",
        "structure_note": "Moderate, measurable premium; quarterly-published NAV.",
        "key_risk": "Sentiment-driven premium (~+110%); ATM issuance caps upside.",
        "reason_buy": "Most measurable premium signal; diversified pre-IPO basket.",
        "reason_avoid": "~46% cash dilutes exposure; premium still rich.",
    },
    "rvi_robinhood": {
        "ticker": "RVI", "name": "Robinhood Ventures Fund I", "type": "Closed-end fund",
        "headline": "OpenAI", "buyable": "NYSE", "fee": "~2.5%",
        "liquidity": "Exchange (no redemption)",
        "data_confidence": "med",
        "confidence_reasons": "NPORT names holdings directly (cleanest CEF), but OpenAI stake post-dates 3/31 filing; ~53% cash.",
        "structure_note": "Newest CEF; premium spiked ~+190% then faded to ~+90%.",
        "key_risk": "~53% cash + premium; OpenAI weight not yet in a filing.",
        "reason_buy": "Cleanest disclosure; direct OpenAI access with modest-ish premium.",
        "reason_avoid": "Half cash; still a premium; OpenAI weight unconfirmed in SEC data.",
    },
    "agix_kraneshares": {
        "ticker": "AGIX", "name": "KraneShares AI & Technology ETF", "type": "ETF",
        "headline": "Anthropic", "buyable": "NYSE/Nasdaq (ETF, at NAV)", "fee": "0.99%",
        "liquidity": "Intraday at NAV (create/redeem)",
        "data_confidence": "high",
        "confidence_reasons": "Anthropic is a DIRECT SEC-named holding; ETF trades at NAV.",
        "structure_note": "At NAV — no premium. Low, falling concentration (4.2%→2.76%).",
        "key_risk": "Low concentration (~3%) and diluted by inflows; mostly public AI stocks.",
        "reason_buy": "Clean, liquid, low-fee, SEC-verifiable Anthropic sliver; no premium risk.",
        "reason_avoid": "Too diluted for a concentrated private-AI bet.",
    },
    "arkvx_arkventure": {
        "ticker": "ARKVX", "name": "ARK Venture Fund", "type": "Interval fund (active)",
        "headline": "SpaceX", "buyable": "At NAV (ARK / brokerages); $500 min",
        "fee": "~2.88%", "liquidity": "Gated — quarterly tenders, ~5% cap",
        "data_confidence": "high",
        "confidence_reasons": "Holdings DIRECTLY SEC-named (SpaceX/OpenAI/Anthropic/xAI/Neuralink); transacts at NAV.",
        "structure_note": "At NAV (no premium), but redemptions are gated -> liquidity discount, not premium.",
        "key_risk": "Gated redemptions: you may not exit at NAV when you want; high ~2.9% fee.",
        "reason_buy": "Cleanest SEC-named multi-name private basket (SpaceX ~11-17% + OpenAI + Anthropic), at NAV.",
        "reason_avoid": "Locked-up liquidity; pricey; diluted by ~84% other holdings/cash.",
    },
}


# ---------------------------------------------------------------------------
# Situation: SpaceX exposure via Baron Partners Fund
# ---------------------------------------------------------------------------

class SpacexBaron:
    KEY = "spacex_baron"
    TITLE = "SpaceX exposure via Baron Partners Fund (BPTIX)"

    # Analysis window. Baron initiated SpaceX in 2017; we run from then to today.
    WINDOW_START = "2017-01-01"

    # --- Fund identity -----------------------------------------------------
    # One fund, multiple share classes (identical underlying portfolio):
    #   BPTRX = Retail, BPTIX = Institutional, BPTUX = R6.
    # SpaceX % weight is identical across classes. We use BPTIX — the institutional
    # class the user actually holds — for NAV; BPTRX/BPTUX track the same portfolio.
    PRIMARY_TICKER = "BPTIX"
    SHARE_CLASSES = {"BPTRX": "Retail", "BPTIX": "Institutional", "BPTUX": "R6"}

    # SEC EDGAR registrant: Baron Partners Fund is a series of "Baron Select Funds".
    # Identity forensically verified (see tests/test_identity.py): the SEC official
    # mutual-fund ticker master maps BPTRX/BPTIX/BPTUX -> CIK 1217673, seriesId
    # S000000588. The seriesId is the PRIMARY identity key — a filing must carry it
    # to be accepted, so a same-trust sibling that also holds SpaceX (Baron Focused
    # Growth, seriesId S000022521) can never contaminate the data.
    EDGAR_CIK = "0001217673"          # Baron Select Funds (trust / registrant)
    EDGAR_SERIES_ID = "S000000588"    # Baron Partners Fund — PRIMARY identity key
    EDGAR_SERIES_NAME = "Baron Partners Fund"  # secondary check in NPORT-P <seriesName>
    EDGAR_CLASS_IDS = {              # for traceability; all map to S000000588
        "BPTRX": "C000001642",       # Retail
        "BPTIX": "C000077805",       # Institutional
        "BPTUX": "C000174760",       # R6
    }

    # The private holding we are tracking, as it appears in NPORT-P.
    HOLDING_NAME_MATCH = "Space Exploration"   # substring match (case-insensitive)

    # --- Daily NAV source --------------------------------------------------
    # Yahoo Finance chart API (no key required). Stooq now gates behind a key.
    NAV_TICKER = "BPTIX"

    # --- The user's assumed entry --------------------------------------------
    ENTRY_DATE = "2026-05-20"   # day the user bought; SpaceX S-1 also filed this day

    # --- Post-filing AUM true-up (manually-sourced) ------------------------
    # The last PUBLIC holdings filing is 2026-03-31; the next is 2026-06-30
    # (~Aug 2026). Fund AUM in between is in NO SEC filing, but reported total
    # net assets move with net flows. Each datapoint trues up the reconstruction
    # AFTER the last filing: AUM = the sourced figure; SpaceX $ is carried forward
    # (no new mark; private shares can't be added). Tagged external_aum / not SEC.
    # ADD rows here as fresher AUM prints appear; keep the source + date honest.
    # Leverage reference (for the 33%-of-investments vs 37.5%-of-net-assets
    # reconciliation, NOT for AUM): 3/31 NPORT gross $11.77B / net $10.36B = ~1.136.
    LEVERAGE_RATIO_LAST = 11767988975.60 / 10360633779.17  # ~1.1358 (3/31 NPORT-P)
    # --- Net-vs-gross switch + leverage (the one place that controls it) -----
    # CONFIRMED 2026-05-31: Baron's own site discloses SpaceX = 23.2% of NET assets.
    # SpaceX $3.89B / 0.232 = $16.77B net == Morningstar "Total Assets" (~16.6-17.0B
    # late May). So Morningstar "Total Assets" is NET AUM, NOT gross. (Under the old
    # gross assumption SpaceX came out 26.6% -> wrong.) Leverage (1.1358) still exists
    # and applies ON TOP for gross public-exposure math: gross = net x LEVERAGE_RATIO.
    LEVERAGE_RATIO = 11_782_549_084 / 10_394_470_144   # 1.1335 — exact, from the 3/31
    # Portfolio of Investments: Total Investments $11,782,549,084 (113.35% of net) /
    # Net Assets $10,394,470,144. (i.e. borrowings = -13.35% of net, as stated.)
    ASSUME_TOTAL_ASSETS_GROSS = False

    # Daily Morningstar "Total Assets" prints feed the AUM true-up. The cowork
    # browser scraper APPENDS one JSON line per day to this log, which is the live
    # source of truth; AUM_REPORTED below is just a committed fallback/seed. Values
    # are stored as REPORTED (gross-or-net per the page); the switch above converts
    # to the net weight-denominator. See ingest/morningstar_log.py.
    MORNINGSTAR_AUM_LOG = "situations/spacex_baron/data/morningstar_aum_log.jsonl"
    AUM_REPORTED = [
        {"date": "2026-04-30", "reported_total_assets_usd": 12.0e9, "confidence": "med",
         "source": "Morningstar 'Total Assets' $12.0B (4/30 month-end, lagged)",
         "source_url": "https://www.morningstar.com/funds/XNAS/BPTIX/quote"},
        {"date": "2026-05-26", "reported_total_assets_usd": 15.6e9, "confidence": "med",
         "source": "Morningstar website 'Total Assets' $15.6B (5/26)",
         "source_url": "https://www.morningstar.com/funds/XNAS/BPTIX/quote"},
        {"date": "2026-05-27", "reported_total_assets_usd": 15.9e9, "confidence": "med",
         "source": "Morningstar website 'Total Assets' $15.9B (5/27 close)",
         "source_url": "https://www.morningstar.com/funds/XNAS/BPTIX/quote"},
    ]

    # --- SpaceX holding re-marks (private mark steps, applied post-last-filing) ---
    # Between NPORT filings the SpaceX $ is carried flat EXCEPT at an explicit mark
    # event. The 6/4 IPO reprice is the first such step. CRITICAL: the holding
    # re-marks by the PER-SHARE price change ($105.32 split-adj @ $1.25T -> $135),
    # i.e. +28.2%, NOT by the post-money valuation ratio (1.77/1.25 = +41.6%, which
    # would double-count the $75B IPO raise / new-share dilution). 3.89026788e9 is
    # the 3/31 NPORT-P SpaceX gross LMV at $1.25T ($526.59 pre-split = $105.32 post).
    SPACEX_REMARKS = [
        {"date": "2026-06-04",
         "spacex_value_usd": 3.89026788e9 * (135.0 / 105.32),  # ~$4.987B
         "per_share_old_split_adj": 105.32, "per_share_new": 135.0,
         "valuation_post_money_usd": 1.77e12,
         "basis": ("Baron S-1 statement: SpaceX private common repriced $135.00 (preferred "
                   "$6,750) on 2026-06-04. Holding re-marks by per-share $105.32->$135 (+28.2%), "
                   "not the +41.6% post-money valuation ratio. Confirmed by the +6.6% NAV move."),
         "source_url": "https://www.baroncapitalgroup.com/product-detail/baron-partners-fund-bptrx",
         "confidence": "high"},
        {"date": "2026-06-12",
         "spacex_value_usd": 3.89026788e9 * (160.95 / 105.32),  # ~$5.946B
         "per_share_old_split_adj": 105.32, "per_share_new": 160.95,
         "valuation_post_money_usd": 1.77e12,
         "basis": ("SpaceX (SPCX) first public trade 2026-06-12, closing $160.95 (+19.2% vs the "
                   "$135 IPO price). Holding now marks to the LIVE market: re-marks by per-share "
                   "$105.32->$160.95 (+52.8% off the 3/31 split-adj basis). First market-based mark; "
                   "supersedes the $135 IPO-price mark. Assumes the fund's SpaceX share count is "
                   "unchanged (no confirmed IPO add yet)."),
         "source_url": "https://finance.yahoo.com/quote/SPCX",
         "confidence": "high"},
        {"date": "2026-06-15",
         "spacex_value_usd": 3.89026788e9 * (192.50 / 105.32),  # ~$7.111B
         "per_share_old_split_adj": 105.32, "per_share_new": 192.50,
         "valuation_post_money_usd": 1.77e12,
         "basis": ("SPCX closed $192.50 on 2026-06-15 (+19.6% vs 6/12 $160.95). Holding marks to the "
                   "live market: per-share $105.32->$192.50 (+82.8% off the 3/31 split-adj basis). "
                   "Marks the DISCLOSED 3/31 share count only; a ~$260M Friday SpaceX add is an "
                   "ESTIMATE that lives in the recalibration card, NOT booked into this hard mark."),
         "source_url": "https://finance.yahoo.com/quote/SPCX",
         "confidence": "high"},
        {"date": "2026-06-16",
         "spacex_value_usd": 3.89026788e9 * (201.80 / 105.32),  # ~$7.454B
         "per_share_old_split_adj": 105.32, "per_share_new": 201.80,
         "valuation_post_money_usd": 1.77e12,
         "basis": ("SPCX closed $201.80 on 2026-06-16 (+4.8% vs 6/15 $192.50), per Bloomberg; Yahoo's $192.50 "
                   "print is stale (the +1.64% BPTIX NAV on a ~flat public basket confirms SpaceX rose). Marks "
                   "the DISCLOSED 3/31 share count; the ~$262M Friday add stays an estimate in recalibration."),
         "source_url": "https://finance.yahoo.com/quote/SPCX",
         "confidence": "high"},
        {"date": "2026-06-17",
         "spacex_value_usd": 3.89026788e9 * (191.82 / 105.32),  # ~$7.087B
         "per_share_old_split_adj": 105.32, "per_share_new": 191.82,
         "valuation_post_money_usd": 1.77e12,
         "basis": ("SPCX closed $191.82 on 2026-06-17 (-4.9% vs 6/16 $201.80), per Bloomberg. Marks the DISCLOSED "
                   "3/31 share count. This first big-down-basket day pinned the fund's leverage at ~1.0 (actual "
                   "NAV 302.28 matched the L=1.0 estimate, not L=0.968), confirming the net-cash buffer was "
                   "consumed by redemptions."),
         "source_url": "https://finance.yahoo.com/quote/SPCX",
         "confidence": "high"},
        {"date": "2026-06-18",
         "spacex_value_usd": 3.89026788e9 * (185.00 / 105.32),  # ~$6.834B
         "per_share_old_split_adj": 105.32, "per_share_new": 185.00,
         "valuation_post_money_usd": 1.77e12,
         "basis": ("SPCX closed $185.00 on 2026-06-18 (-3.6% vs 6/17 $191.82), per Bloomberg. Marks the DISCLOSED "
                   "3/31 share count. (6/19 = Juneteenth market holiday.) BPTIX NAV 298.47 (our estimate 298.36). "
                   "Cross-checked by RONB (Baron's daily-transparent ETF), which moved in line."),
         "source_url": "https://finance.yahoo.com/quote/SPCX",
         "confidence": "high"},
    ]

    # --- Key dated events (annotated on the timeline) ----------------------
    # (date, label, kind)  kind in {init, mark, corporate, filing, ipo, lockup}
    # All values web-verified 2026-05-24 (see data/spacex_marks.csv for sources).
    EVENTS = [
        ("2017-01-01", "Baron initiates SpaceX (~$20B val, ~4% wt)", "init"),
        ("2021-02-18", "Series J, ~$74B (Sequoia-led)", "mark"),
        ("2022-12-13", "Tender ~$140B ($77/sh)", "mark"),
        ("2023-06-23", "Tender ~$150B (>$80/sh)", "mark"),
        ("2023-12-06", "Tender ~$175B", "mark"),
        ("2024-12-10", "Tender ~$350B ($185/sh)", "mark"),
        ("2025-07-01", "Secondary ~$400B ($212/sh)", "mark"),
        ("2025-12-13", "Secondary ~$800B ($421/sh)", "mark"),
        ("2026-02-02", "SpaceX + xAI merger, $1.25T combined", "corporate"),
        ("2026-05-04", "SpaceX 5-for-1 stock split", "corporate"),
        ("2026-05-20", "SpaceX files S-1; user entry", "filing"),
        ("2026-06-03", "IPO PRICED $135/sh = $1.77T (555.6M sh, $75B)", "ipo"),
        ("2026-06-12", "First trade, Nasdaq: SPCX", "ipo"),
        ("2026-12-09", "Projected ~180-day lockup expiry", "lockup"),
    ]

    # --- IPO facts (PRICED 2026-06-03; web-verified) ------------------------
    IPO_TICKER = "SPCX"
    IPO_EXCHANGE = "Nasdaq"
    IPO_PRICING_DATE = "2026-06-03"
    IPO_FIRST_TRADE_DATE = "2026-06-12"
    IPO_PRICE_PER_SHARE = 135.0
    IPO_VALUATION_USD = 1.77e12
    IPO_SHARES = 555.6e6
    IPO_RAISE_USD = 75e9
    LOCKUP_EXPIRY_DATE = "2026-12-09"   # ~180 days after first trade

    # --- Data-density eras (drives confidence + the "soft estimate" shading) -
    # (start, end, label, confidence)
    DENSITY_ERAS = [
        ("2017-01-01", "2019-06-30", "Sparse: heavy interpolation, single points/yr", "low"),
        ("2019-07-01", "2021-12-31", "Improving: NPORT-P begins, quarterly", "med"),
        ("2022-01-01", None,         "Dense: clean quarterly NPORT-P", "high"),
    ]

    # --- Scenario defaults (the frontend recomputes these client-side) ------
    # Funds still carry SpaceX at the stale $1.25T private mark; the IPO PRICED at
    # $1.77T (6/3), so that is now the confirmed re-rate target. Scenarios: the
    # confirmed IPO price, plus first-day pop upside.
    CURRENT_SPACEX_VALUATION_USD = 1.25e12
    IPO_VALUATION_SCENARIOS_USD = [1.77e12, 2.1e12, 2.5e12]   # priced / +20% pop / +40% pop
    DEFAULT_NET_FLOW_SHOCK_USD = 0.0    # slider default; +inflow dilutes, -outflow concentrates


# ---------------------------------------------------------------------------
# Situation: OpenAI / Anthropic exposure via Fundrise Innovation Fund (VCX)
# ---------------------------------------------------------------------------
# Structurally the MIRROR IMAGE of the Baron case. Baron is an open-end fund
# priced AT NAV carrying a stale-LOW private mark -> you buy cheap before a
# re-rate. VCX is a closed-end fund trading at a HUGE PREMIUM to NAV -> even if
# the underlying marks are stale-low, you OVERPAY through the wrapper. The thesis
# here is the premium-to-NAV gap (and its compression risk, esp. at lockup),
# not the underlying mark. Three stacked opacities: wrapper premium, NAV
# staleness, and SPV look-through (OpenAI/Anthropic held via codenamed SPVs,
# so their weights are SPONSOR-DISCLOSED, not SEC-verifiable).

class VcxFundrise:
    KEY = "vcx_fundrise"
    TITLE = "OpenAI / Anthropic exposure via Fundrise Innovation Fund (VCX)"

    WINDOW_START = "2026-03-19"   # NYSE direct-listing date

    PRIMARY_TICKER = "VCX"
    PRICE_TICKER = "VCX"          # Yahoo chart API
    EDGAR_CIK = "0001867090"      # Fundrise Innovation Fund, LLC
    EDGAR_SERIES_ID = None        # single-series LLC; NPORT filed at entity level

    LISTING_DATE = "2026-03-19"
    LOCKUP_EXPIRY_DATE = "2026-09-19"   # ~6mo; restricted pre-listing holders can sell -> premium-compression catalyst

    # --- Sponsor-disclosed look-through (NOT SEC-verifiable; SPV codenames) ---
    # Source: Fundrise VCX disclosures / press (web-verified 2026-05-29). In the
    # NPORT-P these sit inside codenamed SPVs (DBH1 LP, Quiet OA Access LP, etc.),
    # so treat as sponsor-disclosed with explicit low/med confidence.
    LOOKTHROUGH = [
        {"name": "Anthropic", "weight": 0.207, "as_of": "2026-02-15", "confidence": "med",
         "source": "Fundrise VCX disclosure / Motley Fool, Investing.com (Anthropic ~20.7%, largest position)",
         "source_url": "https://www.investing.com/analysis/how-to-invest-in-anthropic-via-etfs-and-term-trusts-200674883"},
        {"name": "Databricks", "weight": 0.177, "as_of": "2026-02-15", "confidence": "med",
         "source": "Fundrise VCX disclosure", "source_url": "https://fundrise.com/vcx"},
        {"name": "OpenAI", "weight": 0.099, "as_of": "2026-02-15", "confidence": "med",
         "source": "Fundrise VCX participated in OpenAI's $122B round; ~9.9% disclosed",
         "source_url": "https://fundrise.com/vcx/newsroom/vcx-participates-in-openai-122-billion-funding-round"},
        {"name": "Anduril", "weight": 0.069, "as_of": "2026-02-15", "confidence": "med",
         "source": "Fundrise VCX disclosure", "source_url": "https://fundrise.com/vcx"},
        {"name": "Ramp", "weight": 0.051, "as_of": "2026-02-15", "confidence": "med",
         "source": "Fundrise VCX disclosure", "source_url": "https://fundrise.com/vcx"},
        {"name": "SpaceX", "weight": 0.050, "as_of": "2026-02-15", "confidence": "med",
         "source": "Fundrise VCX disclosure", "source_url": "https://fundrise.com/vcx"},
    ]

    # --- Underlying private valuation marks (whole-company, web-verified) -----
    # For the IPO/re-rate scenario on the two headline names.
    UNDERLYING_MARKS = {
        "Anthropic": {"current_valuation_usd": 965e9, "current_basis": "Series H ~$965B (May 2026)",
                      "ipo_target_usd": 450e9, "ipo_window": "Oct 2026 (target $400-500B)",
                      "source_url": "https://www.cnbc.com/2026/05/28/anthropic-open-ai-startup-value.html",
                      "note": "Series H ($965B) is ABOVE the reported $400-500B IPO target -> re-rate could be DOWN."},
        "OpenAI": {"current_valuation_usd": 852e9, "current_basis": "$122B round ~$852B (Mar 2026)",
                   "ipo_target_usd": 852e9, "ipo_window": "late 2026 / 2027 (unconfirmed)",
                   "source_url": "https://techcrunch.com/2026/03/31/openai-not-yet-public-raises-3b-from-retail-investors-in-monster-122b-fund-raise/",
                   "note": "Last primary ~$852B; no firm IPO date."},
    }

    # --- NAV log (sponsor-published NAV; cowork/bookmarklet appends) ----------
    NAV_LOG = "situations/vcx_fundrise/data/vcx_nav_log.jsonl"
    # Committed seed NAV prints (web-verified). NAV is published periodically by
    # Fundrise; price is daily (Yahoo). Premium = price/NAV - 1.
    NAV_REPORTED = [
        {"date": "2025-12-31", "nav_per_share": 18.26, "confidence": "high",
         "source": "VCX NPORT-P net assets / units (2025-12-31)",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001867090&type=NPORT-P"},
        {"date": "2026-03-31", "nav_per_share": 18.97, "confidence": "med",
         "source": "Fundrise-reported NAV ~$18.97 (late Apr 2026 disclosure)",
         "source_url": "https://www.crowdfundedwealth.com/articles/fundrise-vcx-review"},
    ]

    # --- Underlying private-company valuation timelines (web-verified 2026-05-29) -
    # Each entry: (date, whole_company_valuation_usd, round_label, source_url).
    # Used to MARK-TO-MARKET the fund's NAV: the sponsor NAV is stale/sticky, so
    # we re-mark each holding by how much its whole-company valuation has moved
    # since the NAV base date. Step function (jumps only on a new observable round).
    VALUATION_TIMELINE = {
        "Anthropic": [
            ("2024-01-01", 18e9, "early 2024", "https://sacra.com/c/anthropic/"),
            ("2025-03-01", 61.5e9, "Series E ~$61.5B", "https://sacra.com/c/anthropic/"),
            ("2025-09-01", 183e9, "Series F $183B", "https://www.anthropic.com/news/anthropic-raises-series-f-at-usd183b-post-money-valuation"),
            ("2026-02-12", 380e9, "Series G $380B", "https://www.anthropic.com/news/anthropic-raises-30-billion-series-g-funding-380-billion-post-money-valuation"),
            ("2026-05-28", 965e9, "Series H ~$965B", "https://www.cnbc.com/2026/05/28/anthropic-open-ai-startup-value.html"),
        ],
        "OpenAI": [
            ("2024-10-02", 157e9, "$6.6B round $157B", "https://techcrunch.com/2024/10/02/openai-raises-6-6-billion-in-funding-at-157-billion-valuation/"),
            ("2025-03-31", 300e9, "$40B SoftBank $300B", "https://apnews.com/article/openai-chatgpt-funding-softbank-d3fb52f922acf226d9b285b87a5e8a13"),
            ("2025-10-01", 500e9, "employee tender $500B", "https://www.reuters.com/technology/openai-500-billion-valuation/"),
            ("2026-03-31", 852e9, "$122B round $852B", "https://techcrunch.com/2026/03/31/openai-not-yet-public-raises-3b-from-retail-investors-in-monster-122b-fund-raise/"),
        ],
        "Databricks": [
            ("2024-12-01", 62e9, "Series J $62B", "https://www.databricks.com/company/newsroom/press-releases/databricks-raising-10b-series-j-investment-62b-valuation"),
            ("2025-08-01", 100e9, "Series K >$100B", "https://www.databricks.com/company/newsroom/press-releases/databricks-raising-series-k-investment-100-billion-valuation"),
            ("2025-12-16", 134e9, "Series L $134B", "https://www.cnbc.com/2025/12/16/databricks-funding-valuation.html"),
        ],
        "Anduril": [
            ("2025-06-05", 30.5e9, "Series G $30.5B", "https://www.cnbc.com/2025/06/05/anduril-valuation-founders-fund.html"),
            ("2026-05-13", 61e9, "Series H $61B", "https://techcrunch.com/2026/05/13/anduril-raises-5b-doubles-valuation-to-61b/"),
        ],
        "Ramp": [
            ("2025-07-01", 22.5e9, "Series E-2 $22.5B", "https://www.prnewswire.com/news-releases/ramp-raises-500-million-at-22-5-billion-valuation-to-accelerate-ai-and-build-the-future-of-finance-302516953.html"),
            ("2025-11-17", 32e9, "$300M round $32B", "https://news.crunchbase.com/venture/fintech-unicorn-ramp-300m-raise-lightspeed/"),
        ],
        "SpaceX": [
            ("2025-12-13", 800e9, "secondary $800B", "https://www.cnbc.com/2025/12/13/musk-spacex-insider-share-sale-sets-800-billion-valuation.html"),
            ("2026-02-02", 1250e9, "SpaceX+xAI $1.25T", "https://www.cnbc.com/2026/02/03/musk-xai-spacex-biggest-merger-ever.html"),
        ],
    }

    # Base date for the mark-to-market: the cleanest full NPORT snapshot (NAV +
    # per-holding $). At this date each holding is assumed marked at its last
    # observable round (see VALUATION_TIMELINE); NAV re-marks forward from here.
    NAV_MTM_BASE_DATE = "2025-12-31"
    NAV_MTM_BASE_NAV = 18.26
    # Weight of holdings NOT individually re-marked (cash + many small names),
    # held flat -> makes the MTM NAV estimate CONSERVATIVE (understates it).
    NAV_MTM_OTHER_WEIGHT_FLAT = True

    # (date, label, kind) kind in {listing, mark, ipo, lockup, corporate}
    EVENTS = [
        ("2026-03-19", "NYSE direct listing (VCX)", "listing"),
        ("2026-02-11", "DXYZ/peers add Anthropic SPVs; AI pre-IPO frenzy", "mark"),
        ("2026-05-28", "Anthropic Series H ~$965B (tops OpenAI)", "mark"),
        ("2026-09-19", "~6-month lockup expiry (premium-compression risk)", "lockup"),
        ("2026-10-15", "Anthropic IPO target window (~$400-500B)", "ipo"),
    ]

    # Headline scenario name + premium normalization targets for the lab.
    HEADLINE_NAME = "Anthropic"
    PREMIUM_SCENARIOS = [0.0, 0.25, 0.50, 1.0]   # premium-to-NAV the price could revert to


# ---------------------------------------------------------------------------
# Situation: Pre-IPO tech (SpaceX/OpenAI/Anthropic) via Destiny Tech100 (DXYZ)
# ---------------------------------------------------------------------------
# A second closed-end-fund premium case, and a useful CONTRAST to VCX: DXYZ
# publishes NAV quarterly (so the premium is more measurable as a tradeable
# signal) and trades at a far MORE MODEST premium (~+120% vs VCX's stale +1000%).
# Same three opacities (wrapper premium, NAV staleness, SPV look-through) but the
# magnitudes make it the "measurable premium signal" case rather than the
# "extreme dislocation" case.

class DxyzDestiny:
    KEY = "dxyz_destiny"
    TITLE = "Pre-IPO tech (SpaceX/OpenAI/Anthropic) via Destiny Tech100 (DXYZ)"

    WINDOW_START = "2025-06-01"     # ~1y of liquid trading history
    PRIMARY_TICKER = "DXYZ"
    PRICE_TICKER = "DXYZ"
    EDGAR_CIK = "0001843974"        # Destiny Tech100 Inc.
    EDGAR_SERIES_ID = None
    LISTING_DATE = "2024-03-26"
    LOCKUP_EXPIRY_DATE = None       # no single dated lockup like VCX; ATM-offering overhang instead

    # Sponsor-disclosed look-through (Destiny holdings page; SPV-held). Weights are
    # of total assets, web-verified 2026-05-29; flagged med / not-SEC-verifiable.
    # Sponsor/press-disclosed look-through, held via SPVs (see NPORT codenames like
    # "DXYZ SpaceX I LLC", "DXYZ OAI I LLC"). The fund is ALSO ~46% cash/Treasuries
    # at the base date (NPORT 12/31), which heavily dampens the mark-to-market uplift.
    # Anthropic weight is the most uncertain: sources span ~6% (early) to ~18.1%
    # (a May-12 filing reference). We use 10% and FLAG the sensitivity.
    LOOKTHROUGH = [
        {"name": "SpaceX", "weight": 0.162, "as_of": "2026-03-31", "confidence": "med",
         "source": "Destiny disclosure: SpaceX largest holding ~16.2% (NPORT SPVs 'DXYZ SpaceX I' + 'MWAM VC SpaceX-II')",
         "source_url": "https://www.destiny.xyz/holdings"},
        {"name": "Anthropic", "weight": 0.10, "as_of": "2026-05-12", "confidence": "low",
         "source": "Sponsor/press disclosed; sources span ~6% to ~18.1% (May-12 filing). Added via ~$100M Magnitude ANC III SPV in Feb-2026. Using 10% (uncertain).",
         "source_url": "https://www.destiny.xyz/holdings"},
        {"name": "OpenAI", "weight": 0.058, "as_of": "2026-03-31", "confidence": "low",
         "source": "Sponsor/press disclosed ~5.8% (SPV 'DXYZ OAI I LLC')",
         "source_url": "https://www.destiny.xyz/holdings"},
    ]

    # Reuse the SpaceX/OpenAI/Anthropic valuation timelines from VcxFundrise so the
    # mark-to-market is consistent across situations.
    @staticmethod
    def valuation_timeline():
        return VcxFundrise.VALUATION_TIMELINE

    UNDERLYING_MARKS = {
        "SpaceX": {"current_valuation_usd": 1.25e12, "ipo_target_usd": 1.77e12,
                   "source_url": "https://www.cnbc.com/2026/06/03/spacex-ipo-stock-price-roadshow-musk.html"},
    }

    NAV_LOG = "situations/dxyz_destiny/data/dxyz_nav_log.jsonl"
    NAV_REPORTED = [
        {"date": "2025-12-31", "nav_per_share": 19.97, "confidence": "high",
         "source": "Destiny reported NAV $19.97 (12/31/2025); ~= NPORT net assets",
         "source_url": "https://www.cefconnect.com/fund/DXYZ"},
        {"date": "2026-03-31", "nav_per_share": 24.56, "confidence": "high",
         "source": "Destiny reported NAV $24.56 (3/31/2026)",
         "source_url": "https://www.cefconnect.com/fund/DXYZ"},
    ]

    # mark-to-market base: use the FRESHEST reported NAV (3/31, $24.56), not the
    # 12/31 NPORT — because DXYZ raised hundreds of millions via ATM offerings
    # between those dates, moving NAV/share for reasons unrelated to holding marks.
    # From the 3/31 base to now, only Anthropic re-rated (Series G $380B -> Series
    # H $965B); SpaceX and OpenAI are flat (no new round since their 3/31 marks).
    NAV_MTM_BASE_DATE = "2026-03-31"
    NAV_MTM_BASE_NAV = 24.56
    NAV_MTM_OTHER_WEIGHT_FLAT = True

    EVENTS = [
        ("2024-03-26", "NYSE listing (DXYZ)", "listing"),
        ("2026-02-11", "Adds ~$100M Anthropic SPV", "mark"),
        ("2026-05-20", "SpaceX files S-1 (largest holding)", "ipo"),
        ("2026-06-12", "SpaceX IPO first trade (SPCX, $135/$1.77T)", "ipo"),
    ]

    HEADLINE_NAME = "SpaceX"
    PREMIUM_SCENARIOS = [0.0, 0.25, 0.50, 1.0]


# ---------------------------------------------------------------------------
# Situation: OpenAI exposure via Robinhood Ventures Fund I (RVI)
# ---------------------------------------------------------------------------
# A third closed-end-fund premium case, but the CLEANEST holdings disclosure of
# the three: RVI's NPORT names its positions directly (Databricks, Revolut,
# Stripe, Ramp, ElevenLabs...) rather than via codenamed SPVs. Two honest
# wrinkles: (1) it's ~53% cash at 3/31, which dampens both NAV moves and the
# economic exposure; (2) its headline OpenAI stake ($75M, bought 2026-04-17) is
# NOT in the 3/31 filing — it post-dates the report period, so OpenAI look-through
# is sponsor-disclosed until the next NPORT.

class RviRobinhood:
    KEY = "rvi_robinhood"
    TITLE = "OpenAI exposure via Robinhood Ventures Fund I (RVI)"
    WINDOW_START = "2026-03-06"          # NYSE listing
    PRIMARY_TICKER = "RVI"
    PRICE_TICKER = "RVI"
    EDGAR_CIK = "0002085091"
    EDGAR_SERIES_ID = None               # single-series
    LISTING_DATE = "2026-03-06"
    LOCKUP_EXPIRY_DATE = None            # CEF; no single dated lockup

    # Sponsor/press-disclosed look-through. OpenAI added 2026-04-17 ($75M) — NOT in
    # the 3/31 NPORT yet. Databricks/Ramp ARE named in the filing. Weights approximate
    # (OpenAI $75M / ~$655M net ~ 11%, but cash-heavy book so economic weight is fluid).
    LOOKTHROUGH = [
        {"name": "OpenAI", "weight": 0.11, "as_of": "2026-04-17", "confidence": "low",
         "source": "RVI bought ~$75M OpenAI on 2026-04-17 (post 3/31 NPORT); ~11% of ~$655M net assets",
         "source_url": "https://robinhood.com/us/en/newsroom/rvi-openai/"},
        {"name": "Databricks", "weight": 0.124, "as_of": "2026-03-31", "confidence": "med",
         "source": "RVI NPORT 3/31: Databricks Series L+K = ~12.4% (named directly)",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0002085091&type=NPORT-P"},
        {"name": "Ramp", "weight": 0.038, "as_of": "2026-03-31", "confidence": "med",
         "source": "RVI NPORT 3/31: Ramp Series E-3 + Class A = ~3.8%",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0002085091&type=NPORT-P"},
    ]

    @staticmethod
    def valuation_timeline():
        return VcxFundrise.VALUATION_TIMELINE

    UNDERLYING_MARKS = {
        "OpenAI": {"current_valuation_usd": 852e9, "ipo_target_usd": 852e9,
                   "source_url": "https://www.cnbc.com/2026/03/31/openai-funding-round-ipo.html"},
    }

    NAV_LOG = "situations/rvi_robinhood/data/rvi_nav_log.jsonl"
    NAV_REPORTED = [
        {"date": "2026-03-31", "nav_per_share": 25.59, "confidence": "med",
         "source": "RVI NPORT net assets $655.3M / ~25.6M shares (approx NAV/share)",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0002085091&type=NPORT-P"},
    ]
    NAV_MTM_BASE_DATE = "2026-03-31"
    NAV_MTM_BASE_NAV = 25.59
    NAV_MTM_OTHER_WEIGHT_FLAT = True

    EVENTS = [
        ("2026-03-06", "NYSE listing (RVI)", "listing"),
        ("2026-04-17", "Buys ~$75M OpenAI (post-NPORT)", "mark"),
    ]
    HEADLINE_NAME = "OpenAI"
    PREMIUM_SCENARIOS = [0.0, 0.10, 0.25, 0.50]


# ---------------------------------------------------------------------------
# Situation: Anthropic exposure via KraneShares AI & Technology ETF (AGIX)
# ---------------------------------------------------------------------------
# The CONTROL case, and structurally different: AGIX is an ETF, so create/redeem
# keeps price ~ NAV (no premium-to-NAV play). Anthropic is a DIRECT, SEC-named
# holding (its title is "ANTHROPIC, PBC SERIES E-1 PREFERRED STOCK"; the NPORT
# <name> field is "N/A", so the parser must read <title>). All numbers below are
# SEC-VERIFIED from the AGIX series (S000085506) NPORT-P, not web-scraped.
#
# Verified Anthropic concentration history (NPORT, seriesId S000085506):
#   2025-06-30  net $28.3M  Anthropic $1.00M = 3.53%
#   2025-09-30  net $89.7M  Anthropic $2.98M = 3.32%
#   2025-12-31  net $92.6M  Anthropic $3.89M = 4.20%
#   2026-03-31  net $171.5M Anthropic $4.72M = 2.76%   <- diluted as fund grew
# So this is the at-NAV, low-concentration, INFLOW-DILUTED case (a clean parallel
# to the Baron dilution story, opposite to the CEF premium traps).

class AgixKraneshares:
    KEY = "agix_kraneshares"
    TITLE = "Anthropic exposure via KraneShares AI & Technology ETF (AGIX)"
    WINDOW_START = "2025-02-01"
    PRIMARY_TICKER = "AGIX"
    PRICE_TICKER = "AGIX"
    EDGAR_CIK = "0001547576"             # Krane Shares Trust (multi-series!)
    EDGAR_SERIES_ID = "S000085506"       # AGIX — REQUIRED to filter the right series
    LISTING_DATE = "2025-01-23"
    LOCKUP_EXPIRY_DATE = None
    IS_ETF = True

    # Anthropic identified by NPORT <title> (name is "N/A"). SEC-verified, high conf.
    HOLDING_TITLE_MATCH = "anthropic"
    LOOKTHROUGH = [
        {"name": "Anthropic", "weight": 0.0276, "as_of": "2026-03-31", "confidence": "high",
         "source": "AGIX NPORT 3/31 (seriesId S000085506): 'ANTHROPIC, PBC SERIES E-1 PREFERRED' "
                   "$4.72M = 2.76% — DIRECT named holding (in <title>)",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001547576&type=NPORT-P"},
    ]

    @staticmethod
    def valuation_timeline():
        return VcxFundrise.VALUATION_TIMELINE

    UNDERLYING_MARKS = {
        "Anthropic": {"current_valuation_usd": 965e9, "ipo_target_usd": 450e9,
                      "source_url": "https://www.cnbc.com/2026/05/28/anthropic-open-ai-startup-value.html"},
    }

    EXPENSE_RATIO = 0.0099
    # AGIX entered Anthropic ~Feb-2025 (~$18B valuation); flag approx.
    ANTHROPIC_COST_BASIS_VALUATION = 18e9

    EVENTS = [
        ("2025-02-01", "AGIX adds direct Anthropic stake (~$18B val)", "mark"),
        ("2026-05-28", "Anthropic Series H ~$965B", "mark"),
        ("2026-10-15", "Anthropic IPO target (~$400-500B)", "ipo"),
    ]
    HEADLINE_NAME = "Anthropic"


# ---------------------------------------------------------------------------
# Situation: SpaceX/OpenAI/Anthropic via ARK Venture Fund (ARKVX)
# ---------------------------------------------------------------------------
# A NEW STRUCTURE TYPE: an actively-managed, continuously-offered INTERVAL FUND.
# Methodology differs from the others:
#   - Like a mutual fund/ETF it transacts AT NAV — there is NO wrapper premium to
#     exploit/fear (unlike the CEFs VCX/DXYZ/RVI).
#   - BUT it is NOT freely redeemable: redemptions are gated to periodic tenders
#     (~quarterly, typically capped ~5% of fund). So the right risk frame is a
#     LIQUIDITY DISCOUNT, not a premium — you may not get out at NAV when you want.
#   - Holdings are DIRECTLY SEC-NAMED (no SPV codenames): cleanest disclosure of
#     the whole set. SpaceX is the top position.
# So the page emphasizes: look-through to multiple private names, mark-to-market
# of the (ARK-marked) NAV, and the liquidity/gating risk — not premium math.

class ArkvxArkVenture:
    KEY = "arkvx_arkventure"
    TITLE = "SpaceX / OpenAI / Anthropic via ARK Venture Fund (ARKVX)"
    WINDOW_START = "2025-06-01"
    PRIMARY_TICKER = "ARKVX"
    PRICE_TICKER = "ARKVX"
    EDGAR_CIK = "0001905088"          # ARK Venture Fund (interval fund)
    EDGAR_SERIES_ID = None            # single-series
    LISTING_DATE = "2022-09-27"       # fund inception (continuously offered)
    LOCKUP_EXPIRY_DATE = None
    IS_ETF = False
    IS_INTERVAL = True                # transacts at NAV but redemptions are gated
    AT_NAV = True                     # no wrapper premium
    REDEMPTION_NOTE = "Quarterly repurchase offers, typically capped ~5% of fund (interval fund)"
    EXPENSE_RATIO = 0.0288            # ~2.88% net (web; flag approx)

    # DIRECTLY SEC-NAMED look-through (NPORT 2026-01-30), tranches summed.
    # SEC-verified, high confidence — unusual for this set. ARK's own site shows
    # SpaceX ~17% at 3/31 (post our NPORT date); we use the SEC-verified 1/30
    # figure and flag the newer ARK number.
    LOOKTHROUGH = [
        {"name": "SpaceX", "weight": 0.1093, "as_of": "2026-01-30", "confidence": "high",
         "source": "ARKVX NPORT 1/30: 'Space Exploration Technologies' 8.06%+2.87% = 10.9% (SEC-named). "
                   "ARK's own site shows ~17.0% at 3/31/2026 (newer; growth + SpaceX re-rate).",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001905088&type=NPORT-P"},
        {"name": "Anthropic", "weight": 0.0249, "as_of": "2026-01-30", "confidence": "high",
         "source": "ARKVX NPORT 1/30: 'Anthropic, Inc.' 2.49% (SEC-named)",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001905088&type=NPORT-P"},
        {"name": "OpenAI", "weight": 0.0286, "as_of": "2026-01-30", "confidence": "high",
         "source": "ARKVX NPORT 1/30: OpenAI Group PBC 1.42%+0.93% + OpenAI Global LLC 0.51% = 2.86% (SEC-named)",
         "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001905088&type=NPORT-P"},
    ]

    @staticmethod
    def valuation_timeline():
        return VcxFundrise.VALUATION_TIMELINE

    UNDERLYING_MARKS = {
        "SpaceX": {"current_valuation_usd": 1.25e12, "ipo_target_usd": 1.77e12,
                   "source_url": "https://www.cnbc.com/2026/06/03/spacex-ipo-stock-price-roadshow-musk.html"},
    }

    NAV_LOG = "situations/arkvx_arkventure/data/arkvx_nav_log.jsonl"
    # ARK publishes ARKVX NAV daily (interval fund priced daily). Seed from NPORT
    # net assets; price (Yahoo) IS the NAV for an at-NAV vehicle.
    NAV_REPORTED = [
        {"date": "2026-01-30", "nav_per_share": None, "confidence": "high",
         "source": "Interval fund priced daily at NAV; per-share NAV = market price (Yahoo)",
         "source_url": "https://www.ark-funds.com/funds/arkvx"},
    ]
    NAV_MTM_BASE_DATE = "2026-01-30"
    NAV_MTM_BASE_NAV = None           # at-NAV: price == NAV, handled in emit
    NAV_MTM_OTHER_WEIGHT_FLAT = True

    EVENTS = [
        ("2026-04-01", "SpaceX confidential S-1 (ARK is a holder)", "ipo"),
        ("2026-05-28", "Anthropic Series H ~$965B", "mark"),
        ("2026-06-12", "SpaceX IPO first trade (SPCX, $135/$1.77T)", "ipo"),
    ]
    HEADLINE_NAME = "SpaceX"


def situation_dir(key: str) -> str:
    return f"situations/{key}"
