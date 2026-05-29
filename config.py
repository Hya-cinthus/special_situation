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
SITUATIONS = ["spacex_baron", "vcx_fundrise"]


# ---------------------------------------------------------------------------
# Situation: SpaceX exposure via Baron Partners Fund
# ---------------------------------------------------------------------------

class SpacexBaron:
    KEY = "spacex_baron"
    TITLE = "SpaceX exposure via Baron Partners Fund (BPTRX)"

    # Analysis window. Baron initiated SpaceX in 2017; we run from then to today.
    WINDOW_START = "2017-01-01"

    # --- Fund identity -----------------------------------------------------
    # One fund, multiple share classes (identical underlying portfolio):
    #   BPTRX = Retail, BPTIX = Institutional, BPTUX = R6.
    # SpaceX % weight is identical across classes. We use BPTRX for the clean
    # public NAV history; the user originally referenced BPTIX (same portfolio).
    PRIMARY_TICKER = "BPTRX"
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
    NAV_TICKER = "BPTRX"

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
    # WORKING ASSUMPTION (pending 5/31 month-end): Morningstar "Total Assets" is
    # GROSS (leveraged), so net = reported / LEVERAGE_RATIO. Flip ASSUME_..._GROSS
    # to False once confirmed net (Morningstar's glossary says net), and rebuild.
    LEVERAGE_RATIO = 11767988975.60 / 10360633779.17   # ~1.1358 (3/31 NPORT-P gross/net)
    ASSUME_TOTAL_ASSETS_GROSS = True

    # Daily Morningstar "Total Assets" prints feed the AUM true-up. The cowork
    # browser scraper APPENDS one JSON line per day to this log, which is the live
    # source of truth; AUM_REPORTED below is just a committed fallback/seed. Values
    # are stored as REPORTED (gross-or-net per the page); the switch above converts
    # to the net weight-denominator. See ingest/morningstar_log.py.
    MORNINGSTAR_AUM_LOG = "situations/spacex_baron/data/morningstar_aum_log.jsonl"
    AUM_REPORTED = [
        {"date": "2026-04-30", "reported_total_assets_usd": 12.0e9, "confidence": "med",
         "source": "Morningstar 'Total Assets' $12.0B (4/30 month-end, lagged)",
         "source_url": "https://www.morningstar.com/funds/XNAS/BPTRX/quote"},
        {"date": "2026-05-26", "reported_total_assets_usd": 15.6e9, "confidence": "med",
         "source": "Morningstar website 'Total Assets' $15.6B (5/26)",
         "source_url": "https://www.morningstar.com/funds/XNAS/BPTRX/quote"},
        {"date": "2026-05-27", "reported_total_assets_usd": 15.9e9, "confidence": "med",
         "source": "Morningstar website 'Total Assets' $15.9B (5/27 close)",
         "source_url": "https://www.morningstar.com/funds/XNAS/BPTRX/quote"},
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
        ("2026-06-11", "Projected IPO pricing (~$1.75T)", "ipo"),
        ("2026-06-12", "Projected first trade, Nasdaq: SPCX", "ipo"),
        ("2026-12-09", "Projected ~180-day lockup expiry", "lockup"),
    ]

    # --- IPO facts (web-verified 2026-05-24; RE-VERIFY at runtime) ----------
    IPO_TICKER = "SPCX"
    IPO_EXCHANGE = "Nasdaq"
    IPO_PRICING_DATE = "2026-06-11"
    IPO_FIRST_TRADE_DATE = "2026-06-12"
    LOCKUP_EXPIRY_DATE = "2026-12-09"   # ~180 days after first trade

    # --- Data-density eras (drives confidence + the "soft estimate" shading) -
    # (start, end, label, confidence)
    DENSITY_ERAS = [
        ("2017-01-01", "2019-06-30", "Sparse: heavy interpolation, single points/yr", "low"),
        ("2019-07-01", "2021-12-31", "Improving: NPORT-P begins, quarterly", "med"),
        ("2022-01-01", None,         "Dense: clean quarterly NPORT-P", "high"),
    ]

    # --- Scenario defaults (the frontend recomputes these client-side) ------
    # Current standing SpaceX mark = combined post-xAI entity. The fund's
    # 2026-03-31 NPORT marks SpaceX at the $1.25T-era basis ($526.59/sh pre-split).
    CURRENT_SPACEX_VALUATION_USD = 1.25e12
    IPO_VALUATION_SCENARIOS_USD = [1.75e12, 2.0e12, 2.4e12]
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


def situation_dir(key: str) -> str:
    return f"situations/{key}"
