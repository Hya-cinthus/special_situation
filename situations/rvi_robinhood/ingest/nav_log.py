"""RVI NAV log — Robinhood publishes NAV periodically. cowork/bookmarklet appends; merge with seed."""
import json, os, sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import RviRobinhood as CFG  # noqa: E402

_SRC = "https://robinhood.com/ventures"


def read_log():
    path = os.path.join(_REPO_ROOT, CFG.NAV_LOG)
    out = []
    if not os.path.exists(path):
        return out
    for ln, raw in enumerate(open(path, encoding="utf-8"), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError as e:
            print("[rvi nav_log] skip line %d: %s" % (ln, e))
    return out


def resolve_nav_anchors():
    by = {}
    for d in getattr(CFG, "NAV_REPORTED", []):
        if d.get("nav_per_share") is None:
            continue
        by[d["date"]] = {"date": d["date"], "nav_per_share": float(d["nav_per_share"]),
                         "source": d["source"], "source_url": d.get("source_url", _SRC),
                         "confidence": d.get("confidence", "med")}
    pick = {}
    for r in read_log():
        dt, nav = r.get("as_of_date_iso"), r.get("nav_per_share")
        if not dt or not isinstance(nav, (int, float)):
            continue
        if dt not in pick or r.get("captured_at", "") > pick[dt].get("captured_at", ""):
            pick[dt] = r
    for dt, r in pick.items():
        by[dt] = {"date": dt, "nav_per_share": float(r["nav_per_share"]),
                  "source": "cowork/bookmarklet scrape (captured %s)" % r.get("captured_at", "?"),
                  "source_url": _SRC, "confidence": "med"}
    return sorted(by.values(), key=lambda x: x["date"])


if __name__ == "__main__":
    for a in resolve_nav_anchors():
        print("  %s  NAV $%.2f  [%s]" % (a["date"], a["nav_per_share"], a["confidence"]))
