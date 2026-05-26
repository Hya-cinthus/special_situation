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
SITUATIONS = ["spacex_baron"]


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
    EDGAR_CIK = "0001217673"          # Baron Select Funds (verified via EDGAR)
    EDGAR_SERIES_NAME = "Baron Partners Fund"  # match in NPORT-P <seriesName>

    # The private holding we are tracking, as it appears in NPORT-P.
    HOLDING_NAME_MATCH = "Space Exploration"   # substring match (case-insensitive)

    # --- Daily NAV source --------------------------------------------------
    # Yahoo Finance chart API (no key required). Stooq now gates behind a key.
    NAV_TICKER = "BPTRX"

    # --- The user's assumed entry --------------------------------------------
    ENTRY_DATE = "2026-05-20"   # day the user bought; SpaceX S-1 also filed this day

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


def situation_dir(key: str) -> str:
    return f"situations/{key}"
