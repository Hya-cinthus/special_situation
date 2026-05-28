"""
Morningstar AUM log ingest.

The cowork browser agent runs daily, scrapes the BPTRX quote page, and APPENDS
one JSON object per line to `config.MORNINGSTAR_AUM_LOG`. This module reads that
log (plus the committed `config.AUM_REPORTED` seed as fallback), dedupes by date
(log wins — fresher), and applies the central gross/net switch
(`CFG.ASSUME_TOTAL_ASSETS_GROSS`) to produce the NET AUM datapoints the
reconstruction engine consumes.

Log line schema (the cowork prompt outputs exactly this; extra fields ignored):
  {
    "as_of_date_iso": "YYYY-MM-DD",        # effective date of Total Assets / NAV
    "total_assets_usd": 15900000000,        # numeric, USD (as reported on the page)
    "total_assets_raw": "15.9B",            # the literal string shown
    "captured_at": "<ISO datetime>",        # when cowork ran
    ... (nav_per_share, total_assets_definition, net_assets_field, etc.)
  }

A line without `as_of_date_iso` or `total_assets_usd` is skipped. If multiple
records share a date, the latest `captured_at` wins.
"""

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import SpacexBaron as CFG  # noqa: E402


def _to_net(reported_usd: float) -> float:
    if reported_usd is None:
        return None
    return reported_usd / CFG.LEVERAGE_RATIO if CFG.ASSUME_TOTAL_ASSETS_GROSS else reported_usd


def read_log() -> list[dict]:
    """Read the cowork append-only JSONL log; return raw records (no dedupe)."""
    path = os.path.join(_REPO_ROOT, CFG.MORNINGSTAR_AUM_LOG)
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError as e:
                print(f"[morningstar_log] skip line {ln}: {e}")
    return out


def resolve_aum_datapoints() -> list[dict]:
    """Merge config.AUM_REPORTED (seed) + log (fresher), dedupe by date, apply
    the gross/net switch. Returns the list of NET AUM datapoints in the shape
    the engine expects.
    """
    by_date: dict[str, dict] = {}
    src_url = "https://www.morningstar.com/funds/XNAS/BPTRX/quote"

    # 1) Seed from config (committed fallback, in case the log is missing).
    for d in getattr(CFG, "AUM_REPORTED", []):
        by_date[d["date"]] = {
            "date": d["date"],
            "total_net_assets_usd": _to_net(d["reported_total_assets_usd"]),
            "reported_total_assets_usd": d["reported_total_assets_usd"],
            "source": d["source"],
            "source_url": d.get("source_url", src_url),
            "confidence": d.get("confidence", "med"),
        }

    # 2) Overlay log records (cowork output). Tie-break by captured_at.
    pick: dict[str, dict] = {}  # date -> raw record with latest captured_at
    for r in read_log():
        date = r.get("as_of_date_iso")
        ta = r.get("total_assets_usd")
        if not date or not isinstance(ta, (int, float)):
            continue
        cur = pick.get(date)
        if cur is None or (r.get("captured_at", "") > cur.get("captured_at", "")):
            pick[date] = r

    for date, r in pick.items():
        ta = float(r["total_assets_usd"])
        raw = r.get("total_assets_raw") or f"${ta/1e9:.1f}B"
        by_date[date] = {
            "date": date,
            "total_net_assets_usd": _to_net(ta),
            "reported_total_assets_usd": ta,
            "source": f"cowork scrape of Morningstar quote page · Total Assets {raw} "
                      f"({'GROSS assumed' if CFG.ASSUME_TOTAL_ASSETS_GROSS else 'NET'}; captured {r.get('captured_at','?')})",
            "source_url": src_url,
            "confidence": "med",
        }

    return sorted(by_date.values(), key=lambda x: x["date"])


if __name__ == "__main__":
    rows = resolve_aum_datapoints()
    print(f"{len(rows)} AUM datapoints (ASSUME_GROSS={CFG.ASSUME_TOTAL_ASSETS_GROSS}, "
          f"leverage={CFG.LEVERAGE_RATIO:.4f}):")
    for r in rows:
        print(f"  {r['date']}  reported ${r['reported_total_assets_usd']/1e9:.2f}B  "
              f"-> net ${r['total_net_assets_usd']/1e9:.2f}B  [{r['confidence']}]")
