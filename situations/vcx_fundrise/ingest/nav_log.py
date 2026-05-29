"""
VCX NAV log ingest — Fundrise's sponsor-published NAV per share.

VCX NAV is published periodically by Fundrise (not daily, and not cleanly in
SEC filings: NPORT gives total net assets but no unit count). The cowork
browser agent / bookmarklet appends one JSON line per observation to
`config.NAV_LOG`; this resolver merges that with the committed `NAV_REPORTED`
seed (log wins on date collision) and returns NAV anchors sorted by date.

Log line schema (extra fields ignored):
  {"as_of_date_iso":"YYYY-MM-DD","nav_per_share":18.97,"captured_at":"<ISO>", ...}
"""

import json
import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import VcxFundrise as CFG  # noqa: E402

_SRC = "https://fundrise.com/vcx"


def read_log() -> list[dict]:
    path = os.path.join(_REPO_ROOT, CFG.NAV_LOG)
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
                print(f"[vcx nav_log] skip line {ln}: {e}")
    return out


def resolve_nav_anchors() -> list[dict]:
    by_date: dict[str, dict] = {}
    for d in getattr(CFG, "NAV_REPORTED", []):
        by_date[d["date"]] = {
            "date": d["date"], "nav_per_share": float(d["nav_per_share"]),
            "source": d["source"], "source_url": d.get("source_url", _SRC),
            "confidence": d.get("confidence", "med"),
        }
    pick: dict[str, dict] = {}
    for r in read_log():
        date = r.get("as_of_date_iso")
        nav = r.get("nav_per_share")
        if not date or not isinstance(nav, (int, float)):
            continue
        cur = pick.get(date)
        if cur is None or r.get("captured_at", "") > cur.get("captured_at", ""):
            pick[date] = r
    for date, r in pick.items():
        by_date[date] = {
            "date": date, "nav_per_share": float(r["nav_per_share"]),
            "source": f"cowork/bookmarklet scrape of Fundrise VCX NAV (captured {r.get('captured_at','?')})",
            "source_url": _SRC, "confidence": "med",
        }
    return sorted(by_date.values(), key=lambda x: x["date"])


if __name__ == "__main__":
    for a in resolve_nav_anchors():
        print(f"  {a['date']}  NAV ${a['nav_per_share']:.2f}  [{a['confidence']}]  {a['source'][:60]}")
