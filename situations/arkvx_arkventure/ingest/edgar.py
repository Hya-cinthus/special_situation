"""EDGAR ingest for ARK Venture Fund (ARKVX), CIK 1905088.

ARKVX names its private holdings DIRECTLY (SpaceX, OpenAI, Anthropic, xAI,
Neuralink...) — the cleanest disclosure of the whole set. We sum tranches per
company and track the SpaceX/OpenAI/Anthropic concentration per quarter.
"""
import json, os, re, sys, time, urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import ArkvxArkVenture as CFG, SEC_USER_AGENT  # noqa: E402

_RAW = os.path.join(_REPO_ROOT, "situations", "arkvx_arkventure", "data", "raw", "edgar")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "arkvx_arkventure", "data", "processed")

# canonical private names we track, with substring matchers (sum tranches)
_TRACK = {
    "SpaceX": ["space exploration"],
    "OpenAI": ["openai"],
    "Anthropic": ["anthropic"],
}


def _get(url):
    for a in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT}), timeout=45)
            time.sleep(0.12); return r.read()
        except Exception:
            time.sleep(0.5 * (a + 1))
    raise RuntimeError("GET failed: " + url)


def _tag(s, t):
    m = re.search(r'<%s>(.*?)</%s>' % (t, t), s, re.S)
    return m.group(1).strip() if m else None


def _disp(blk):
    nm = _tag(blk, "name") or ""
    ti = _tag(blk, "title") or ""
    return nm if nm not in ("", "N/A") else ti


def list_nport(cik):
    sub = json.loads(_get("https://data.sec.gov/submissions/CIK%s.json" % cik.zfill(10)))
    blocks = [sub["filings"]["recent"]]
    for extra in sub["filings"].get("files", []):
        blocks.append(json.loads(_get("https://data.sec.gov/submissions/%s" % extra["name"])))
    out = []
    for b in blocks:
        for i, f in enumerate(b.get("form", [])):
            if f == "NPORT-P":
                acc = b["accessionNumber"][i]
                out.append({"accession": acc, "nodash": acc.replace("-", ""),
                            "filing_date": b["filingDate"][i], "cik": cik.zfill(10)})
    out.sort(key=lambda d: d["filing_date"], reverse=True)
    return out


def _doc(rec):
    os.makedirs(_RAW, exist_ok=True)
    p = os.path.join(_RAW, "%s.xml" % rec["nodash"])
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return open(p, encoding="utf-8", errors="replace").read()
    t = _get("https://www.sec.gov/Archives/edgar/data/%d/%s/primary_doc.xml" % (int(rec["cik"]), rec["nodash"])).decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(t)
    return t


def fetch_anchors(verbose=True, max_scan=24):
    anchors, seen = [], set()
    for rec in list_nport(CFG.EDGAR_CIK)[:max_scan]:
        try:
            x = _doc(rec)
        except Exception as e:
            if verbose:
                print("  ! skip", rec["accession"], e)
            continue
        rep = _tag(x, "repPdDate")
        if not rep or rep in seen:
            continue
        seen.add(rep)
        na, ta = _tag(x, "netAssets"), _tag(x, "totAssets")
        holdings, tracked = [], {c: 0.0 for c in _TRACK}
        tracked_pct = {c: 0.0 for c in _TRACK}
        for blk in re.findall(r'<invstOrSec>.*?</invstOrSec>', x, re.S):
            nm = _disp(blk)
            val = float(_tag(blk, "valUSD") or 0)
            pctv = float(_tag(blk, "pctVal") or 0)
            holdings.append({"name": nm, "valUSD": val, "pctVal": pctv})
            low = nm.lower()
            for comp, needles in _TRACK.items():
                if any(n in low for n in needles):
                    tracked[comp] += val
                    tracked_pct[comp] += pctv
        holdings.sort(key=lambda h: -h["pctVal"])
        anchors.append({"report_date": rep, "filing_date": rec["filing_date"],
                        "accession": rec["accession"],
                        "net_assets_usd": float(na) if na else None,
                        "total_assets_usd": float(ta) if ta else None, "n_holdings": len(holdings),
                        "tracked_value_usd": {c: round(v, 2) for c, v in tracked.items()},
                        "tracked_pct": {c: round(p, 4) for c, p in tracked_pct.items()},
                        "top_holdings": holdings[:18], "source": "measured", "confidence": "high"})
        if verbose:
            print("  + %s net $%.0fM  SpaceX %.1f%%  OpenAI %.1f%%  Anthropic %.1f%%" % (
                rep, (float(na) or 0) / 1e6, tracked_pct["SpaceX"], tracked_pct["OpenAI"], tracked_pct["Anthropic"]))
    anchors.sort(key=lambda a: a["report_date"])
    return anchors


def write_anchors(anchors):
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "nport_anchors.json")
    json.dump(anchors, open(path, "w", encoding="utf-8"), indent=2)
    return path


if __name__ == "__main__":
    a = fetch_anchors(); print("wrote", write_anchors(a), "|", len(a), "ARKVX anchors")
