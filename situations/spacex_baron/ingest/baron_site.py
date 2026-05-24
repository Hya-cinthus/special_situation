"""
Baron Capital website ingestion — STUB / future hook.

Baron's product pages and quarterly letters (baroncapitalgroup.com) carry
stated top-holding weights and manager commentary on SpaceX marks and fund
flows. They are useful as an independent cross-check on the NPORT-P-derived
anchors and for the sparse pre-2019 era.

This is intentionally NOT scraped automatically in v1:
  - The pages are JS-rendered / PDF and not stably machine-readable.
  - The authoritative figures we need (share count, fair value, net assets)
    already come cleanly from NPORT-P (see edgar.py), which is the regulatory
    source of record.

So this module exposes the manually-curated marks that *are* sourced from
Baron/press narrative (the pre-2019 anchor and the forward IPO scenario), read
from data/spacex_marks.csv, and leaves a documented hook for a future scraper.

If you fill the gap later: parse the BPTRX product page "Top 10 Holdings" table
and the quarterly letter PDFs, and emit rows shaped like read_external_marks().
"""

import csv
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_MARKS_CSV = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "spacex_marks.csv")


def read_external_marks() -> list[dict]:
    """Curated SpaceX valuation marks with provenance + confidence.

    These are externally-sourced whole-company valuations (the 2017 init anchor,
    the current $1.25T standing mark, the forward IPO scenarios). The dense-era
    marks the engine actually relies on are *derived from filings* in edgar.py.
    """
    rows = []
    with open(_MARKS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["whole_company_valuation_usd"] = float(r["whole_company_valuation_usd"])
            r["per_share_usd"] = float(r["per_share_usd"]) if r["per_share_usd"] else None
            rows.append(r)
    rows.sort(key=lambda r: r["date"])
    return rows


def scrape_top_holdings():  # pragma: no cover - future hook
    """TODO: parse the BPTRX product page top-holdings table as an NPORT cross-check."""
    raise NotImplementedError("Baron site scraper not implemented; see data_gaps.md item #1.")


if __name__ == "__main__":
    for m in read_external_marks():
        print(f"{m['date']}  ${m['whole_company_valuation_usd']/1e9:>8.1f}B  "
              f"[{m['confidence']:>4}]  {m['source_desc'][:70]}")
