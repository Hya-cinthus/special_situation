"""
ARK / SpaceX-IPO Tracker -> dashboard/data/ark_tracker.json

A scenario/probability module (NOT a vehicle valuation). It estimates, from ARK's
*actual historical IPO behavior*, which ARK ETF would most likely receive SpaceX
shares, the expected dollar exposure under valuation scenarios, and the evidence.

ANTI-SPECULATION DESIGN:
  - The allocation ranking is driven by an EMPIRICAL history table (which ETF
    actually bought past IPOs first day) + a transparent theme-fit rubric. Every
    fit score shows its reasoning; the empirical column dominates.
  - bear/base/bull SpaceX valuations + position-size buckets are explicit,
    user-readable assumptions, labeled estimates.
  - Every datapoint (AUM, IPO buy, weight) carries a source + confidence.
  - SpaceX is private -> ARK can only buy at/after IPO. Dollar exposure =
    assumed_position_weight x ETF AUM (separate from portfolio weight, as asked).

All AUM + IPO facts web-verified 2026-06-02; re-verify at runtime.
"""

import json
import os
import sys
import datetime

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import DASHBOARD_DATA_DIR  # noqa: E402

SRC_SA = "https://stockanalysis.com/etf/{}/"
SRC_ARK = "https://www.ark-funds.com/funds/{}"

# --- 1. ETF profiles (web-verified 2026-06-02). Tracked SEPARATELY, never summed.
ETFS = {
    "ARKK": {
        "name": "ARK Innovation ETF", "theme": "Flagship / broad disruptive innovation",
        "aum_usd": 7.26e9, "aum_date": "2026-06-02", "price": 79.94,
        "top_holdings": "Tesla ~10%, AMD, CRISPR, Tempus AI, Roku, Coinbase, Robinhood, Circle",
        "spacex_now": False, "source_url": SRC_SA.format("arkk"), "confidence": "high",
    },
    "ARKW": {
        "name": "ARK Next Generation Internet ETF", "theme": "Internet infra / fintech / Starlink-adjacent",
        "aum_usd": 1.83e9, "aum_date": "2026-06-02", "price": None,
        "top_holdings": "AMD ~9%, Tesla ~9%, ARKB (bitcoin), Robinhood, Roku, Coinbase, Circle",
        "spacex_now": False, "source_url": SRC_SA.format("arkw"), "confidence": "high",
    },
    "ARKQ": {
        "name": "ARK Autonomous Technology & Robotics ETF", "theme": "Robotics / autonomy / aerospace",
        "aum_usd": 2.36e9, "aum_date": "2026-06-02", "price": None,
        "top_holdings": "Tesla ~11%, AMD, Teradyne, Rocket Lab ~6%, Kratos, AeroVironment",
        "spacex_now": False, "source_url": SRC_SA.format("arkq"), "confidence": "high",
    },
    "ARKX": {
        "name": "ARK Space & Defense Innovation ETF", "theme": "Space / launch / satellite / defense",
        "aum_usd": 1.11e9, "aum_date": "2026-06-02", "price": None,
        "top_holdings": "Rocket Lab ~9%, AMD, L3Harris, Teradyne, Kratos; SpaceX NOT held yet",
        "spacex_now": False, "source_url": SRC_SA.format("arkx"), "confidence": "high",
    },
}

# --- 2. Historical IPO-participation database (web-verified). The empirical core.
# Per-event: which ETFs bought, $ allocation, and the INITIAL WEIGHT in EACH ETF
# (weights dict; None where not disclosed). offer_price = the IPO pricing; the
# impact engine separately measures the first exchange print (open).
IPO_HISTORY = [
    {"company": "Circle (CRCL)", "ipo_date": "2025-06-05", "first_day": True,
     "etfs": ["ARKK", "ARKW", "ARKF"], "alloc_usd": 373.4e6, "offer_price": 31.0,
     "weights": {"ARKK": 0.044, "ARKW": 0.044, "ARKF": 0.043},
     "note": "Bought $373M on NYSE debut across ARKK/ARKW/ARKF; trimmed Coinbase/Robinhood to fund it. "
             "Priced $31 -> closed $83.23 (+168% offer->close); +20.6% open->close.",
     "source_url": "https://www.theblock.co/post/357271/", "confidence": "high"},
    {"company": "Coinbase (COIN)", "ipo_date": "2021-04-14", "first_day": True,
     "etfs": ["ARKK", "ARKW", "ARKF"], "alloc_usd": 246e6, "offer_price": 250.0,
     "weights": {"ARKK": 0.04, "ARKW": 0.04, "ARKF": 0.04},
     "note": "Direct listing (ref price $250); bought across the broad funds. Still a top-10 ARKK name.",
     "source_url": "https://www.theblock.co/post/357271/", "confidence": "med"},
    {"company": "Roblox (RBLX)", "ipo_date": "2021-03-10", "first_day": True,
     "etfs": ["ARKK", "ARKW", "ARKF"], "alloc_usd": 27e6, "offer_price": 45.0,
     "weights": {"ARKK": 0.01, "ARKW": 0.01, "ARKF": 0.01},
     "note": "Direct listing (ref $45); 740k shares (~$27M) for ARKK/ARKW/ARKF.",
     "source_url": "https://cointelegraph.com/news/ark-sell-31m-robinhood-stacks-roblox", "confidence": "med"},
    {"company": "UiPath (PATH)", "ipo_date": "2021-04-21", "first_day": True,
     "etfs": ["ARKK", "ARKW", "ARKQ"], "alloc_usd": None, "offer_price": 56.0,
     "weights": {"ARKK": None, "ARKW": None, "ARKQ": None},
     "note": "Priced $56; bought 2.7M shares at IPO (incl. ARKQ — robotics fit); fully exited by 2025.",
     "source_url": "https://stockcircle.com/portfolio/cathie-wood/path/transactions", "confidence": "med"},
    {"company": "Robinhood (HOOD)", "ipo_date": "2021-07-29", "first_day": True,
     "etfs": ["ARKK", "ARKW", "ARKF"], "alloc_usd": None, "offer_price": 38.0,
     "weights": {"ARKK": None, "ARKW": None, "ARKF": None},
     "note": "Priced $38; bought on IPO day across broad funds. Still a top-10 ARKK/ARKW holding.",
     "source_url": "https://www.coindesk.com/markets/2025/08/20/", "confidence": "med"},
    {"company": "Reddit (RDDT)", "ipo_date": "2024-03-21", "first_day": True,
     "etfs": ["ARKK", "ARKW"], "alloc_usd": None, "offer_price": 34.0,
     "weights": {"ARKK": None, "ARKW": None},
     "note": "Priced $34; bought around the IPO across ARKK/ARKW (internet fit).",
     "source_url": "https://www.benzinga.com/25/01/43073132/", "confidence": "low"},
    {"company": "Tempus AI (TEM)", "ipo_date": "2024-06-14", "first_day": True,
     "etfs": ["ARKK", "ARKG"], "alloc_usd": 294e6, "offer_price": 37.0,
     "weights": {"ARKK": 0.05, "ARKG": None},
     "note": "Priced $37; ARKK + ARKG (genomics fit); grew to ARKK's #3 holding (~5%, ~$294M).",
     "source_url": "https://www.investing.com/news/company-news/93CH-4069113", "confidence": "high"},
]

# --- 2b. ARK position-sizing rubric (from ARK's own help center; web-verified).
# Used as the SpaceX-allocation GUIDANCE: what weight Cathie Wood typically starts
# a new high-conviction name at, and the ceiling.
SIZING_RUBRIC = {
    "typical_min": 0.01, "median": 0.02, "high_conviction_start": 0.045, "max": 0.10,
    "top10_share": 0.50,
    "source": "ARK help center: median position ~2%, max ~10%, top-10 ~50% of fund.",
    "source_url": "https://helpcenter.ark-funds.com/what-is-the-typical-position-weight-of-a-security-in-an-ark-etf",
    "note": "High-conviction NEW IPOs (Circle, Tempus) entered at ~4.4–5% — that is the best "
            "empirical guide for a SpaceX day-1 weight in the broad funds (ARKK/ARKW). A pure-theme "
            "sector fund (ARKX) could go higher relative to its small size.",
}

# --- 3. Theme-fit rubric (transparent, 0-100). Each factor scored with reasoning.
# Empirical weight: ARKK always participates; broad funds (ARKW) usually; sector
# funds (ARKQ/ARKX) only on strong theme fit. SpaceX = space(ARKX) + launch/
# aerospace(ARKQ) + Starlink/internet(ARKW) + flagship(ARKK).
FIT = {
    "ARKK": {"score": 95,
             "reasons": ["Flagship: bought EVERY major IPO in the history table first-day (Circle, Coinbase, "
                         "Roblox, UiPath, Robinhood, Reddit, Tempus).",
                         "SpaceX is the highest-conviction private name in ARK's universe; ARKK already "
                         "holds it indirectly via ARKVX's manager.",
                         "Largest AUM ($7.26B) -> biggest absolute buy capacity."],
             "empirical": "7/7 historical IPOs"},
    "ARKW": {"score": 78,
             "reasons": ["Bought 6/7 historical IPOs first-day alongside ARKK.",
                         "Strong thematic fit via Starlink (satellite internet) = next-gen internet infra.",
                         "Mid AUM ($1.83B)."],
             "empirical": "6/7 historical IPOs"},
    "ARKQ": {"score": 70,
             "reasons": ["Direct aerospace/launch theme fit (already holds Rocket Lab ~6%, Kratos, AeroVironment).",
                         "Participated in robotics/autonomy IPOs (UiPath) but NOT the fintech/internet ones.",
                         "Most natural SECTOR home for a launch company; AUM $2.36B."],
             "empirical": "selective (theme-only IPOs)"},
    "ARKX": {"score": 82,
             "reasons": ["Purest thematic fit: space & launch is the entire mandate.",
                         "Already concentrated in space names (Rocket Lab ~9%); SpaceX would likely become a TOP holding.",
                         "BUT smallest AUM ($1.11B) -> largest WEIGHT impact, smallest DOLLAR buy.",
                         "Newer fund, thinner IPO-participation track record."],
             "empirical": "thin history, strongest theme"},
}

# --- 4. SpaceX IPO valuation scenarios + assumed ARK position-size buckets.
SPACEX_SCENARIOS = {"bear": 300e9, "base": 500e9, "bull": 1.0e12}  # whole-company, per user
POSITION_SIZES = [0.02, 0.05, 0.10, 0.15]  # assumed portfolio weight ARK would target

# --- 5. Monitoring timeline (dated, sourced evidence). confirmed/rumor labeled.
TIMELINE = [
    {"date": "2026-04-01", "cat": "SpaceX", "kind": "filing",
     "text": "SpaceX submitted a confidential draft S-1 to the SEC (per ARK's own SpaceX-IPO guide).",
     "source_url": "https://www.ark-funds.com/articles/venture-fund/arks-guide-to-the-spacex-ipo",
     "confidence": "high"},
    {"date": "2026-05-20", "cat": "SpaceX", "kind": "filing",
     "text": "SpaceX publicly filed its S-1; ~$1.75T target, Nasdaq SPCX, first trade ~June 12.",
     "source_url": "https://www.cnbc.com/2026/05/20/spacex-ipo-live-updates.html", "confidence": "high"},
    {"date": "2026-05-04", "cat": "ARK", "kind": "thesis",
     "text": "ARK published 'ARK's Guide To The SpaceX IPO' — signals intent to participate.",
     "source_url": "https://www.ark-funds.com/articles/venture-fund/arks-guide-to-the-spacex-ipo",
     "confidence": "high"},
    {"date": "2026-01-30", "cat": "ARK", "kind": "holding",
     "text": "ARK Venture Fund (ARKVX) holds SpaceX at ~11% (top holding) — ARK already a SpaceX backer.",
     "source_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001905088&type=NPORT-P",
     "confidence": "high"},
    {"date": "2026-05-04", "cat": "Cathie Wood", "kind": "commentary",
     "text": "ARK reiterates SpaceX/Starlink as a core disruptive-innovation theme ahead of the IPO.",
     "source_url": "https://www.ark-funds.com/articles/venture-fund/arks-guide-to-the-spacex-ipo",
     "confidence": "med"},
]


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def build_payload():
    # IPO stats by ETF (empirical)
    etf_ipo_count = {t: 0 for t in ETFS}
    for ev in IPO_HISTORY:
        for t in ev["etfs"]:
            if t in etf_ipo_count:
                etf_ipo_count[t] += 1
    n_ipos = len(IPO_HISTORY)

    # ranking = fit score (which already encodes the empirical history)
    ranking = sorted(ETFS.keys(), key=lambda t: FIT[t]["score"], reverse=True)

    # dollar-exposure matrix: weight x AUM (NOT valuation-dependent for the ETF $,
    # but we show how the ASSUMED weight ARK targets might scale with conviction).
    exposure = {}
    for t in ETFS:
        aum = ETFS[t]["aum_usd"]
        exposure[t] = [{"weight": w, "dollar": round(w * aum, 0)} for w in POSITION_SIZES]

    # "buying pressure" = sum across the broad funds at a base 5% assumption
    base_w = 0.05
    pressure_base = sum(ETFS[t]["aum_usd"] * base_w for t in ranking[:3])

    payload = {
        "meta": {
            "title": "ARK / SpaceX-IPO Tracker", "generated_at": _now_iso(),
            "disclaimer": ("Analysis, not investment advice. This estimates ARK's LIKELY SpaceX-IPO "
                           "participation from its ACTUAL historical IPO behavior + a transparent theme-fit "
                           "rubric — not a prediction. SpaceX is private; ARK can only buy at/after IPO. "
                           "AUM and IPO facts are web-verified with sources; valuation scenarios and "
                           "position-size buckets are explicit assumptions, labeled estimates. ETFs are "
                           "tracked separately, never aggregated."),
            "spacex_scenarios": SPACEX_SCENARIOS, "position_sizes": POSITION_SIZES,
        },
        "key_answers": {
            "most_likely_shares": {"etf": "ARKK", "why": "Bought 7/7 major IPOs first-day; flagship + largest AUM."},
            "largest_dollar": {"etf": "ARKK", "why": "$7.26B AUM x ~5% = ~$363M, far above any sector fund."},
            "highest_weight": {"etf": "ARKX", "why": "Smallest fund ($1.11B) + purest space theme -> SpaceX could be a top weight."},
            "buying_pressure_base_usd": pressure_base,
        },
        "etfs": [{"ticker": t, **ETFS[t], "ipo_participation": etf_ipo_count[t],
                  "fit": FIT[t], "exposure": exposure[t]} for t in ranking],
        "ranking": ranking,
        "ipo_history": IPO_HISTORY,
        "ipo_stats": {"n_ipos": n_ipos, "by_etf": etf_ipo_count},
        "sizing_rubric": SIZING_RUBRIC,
        "timeline": sorted(TIMELINE, key=lambda x: x["date"], reverse=True),
    }
    # Always carry the IPO-impact block: reuse the committed cache so a no-fetch
    # rebuild (e.g. the GitHub Action) never drops it.
    try:
        import ark_ipo_impact
        cached = ark_ipo_impact.load_cached()
        if cached:
            payload["ipo_impact"] = cached
    except Exception:
        pass
    return payload


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, DASHBOARD_DATA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "ark_tracker.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    p = write_json()
    print(f"Wrote {p} ({os.path.getsize(p)/1024:.0f} KB)")
