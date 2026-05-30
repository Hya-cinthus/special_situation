"""EDGAR ingest for KraneShares AI & Technology ETF (AGIX).

Krane Shares Trust (CIK 1547576) files NPORT-P for 100+ ETFs, so we MUST filter
by seriesId S000085506. CRITICAL parsing detail: Anthropic's NPORT <name> is
"N/A"; its identity is in <title> ("ANTHROPIC, PBC SERIES E-1 PREFERRED STOCK").
So we match on title, not name. All figures are SEC-verified.
"""
import json, os, re, sys, time, urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import AgixKraneshares as CFG, SEC_USER_AGENT  # noqa: E402

_RAW = os.path.join(_REPO_ROOT, "situations", "agix_kraneshares", "data", "raw", "edgar")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "agix_kraneshares", "data", "processed")


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


def _holding_name(blk):
    """Prefer <title> when <name> is 'N/A' (Anthropic etc. are titled, not named)."""
    name = _tag(blk, "name") or ""
    title = _tag(blk, "title") or ""
    if name in ("", "N/A") and title:
        return title
    return name


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


def fetch_anchors(verbose=True, max_scan=160):
    """Scan NPORT newest-first, keep ONLY series S000085506, sum Anthropic by title."""
    anchors, scanned, seen = [], 0, set()
    for rec in list_nport(CFG.EDGAR_CIK):
        if scanned >= max_scan:
            break
        try:
            x = _doc(rec)
        except Exception as e:
            if verbose:
                print("  ! skip", rec["accession"], e)
            continue
        scanned += 1
        if _tag(x, "seriesId") != CFG.EDGAR_SERIES_ID:
            continue
        rep = _tag(x, "repPdDate")
        if rep in seen:
            continue
        seen.add(rep)
        na, ta = _tag(x, "netAssets"), _tag(x, "totAssets")
        holdings = []
        anth_val = 0.0
        anth_pct = 0.0
        for blk in re.findall(r'<invstOrSec>.*?</invstOrSec>', x, re.S):
            nm = _holding_name(blk)
            val = float(_tag(blk, "valUSD") or 0)
            pctv = float(_tag(blk, "pctVal") or 0)
            holdings.append({"name": nm, "valUSD": val, "pctVal": pctv})
            if CFG.HOLDING_TITLE_MATCH in (nm or "").lower():
                anth_val += val
                anth_pct += pctv
        holdings.sort(key=lambda h: -h["pctVal"])
        anchors.append({"report_date": rep, "filing_date": rec["filing_date"],
                        "accession": rec["accession"], "series_id": _tag(x, "seriesId"),
                        "series_name": _tag(x, "seriesName"),
                        "net_assets_usd": float(na) if na else None,
                        "total_assets_usd": float(ta) if ta else None, "n_holdings": len(holdings),
                        "anthropic_value_usd": anth_val if anth_val else None,
                        "anthropic_pct": round(anth_pct, 4) if anth_pct else None,
                        "top_holdings": holdings[:15], "source": "measured", "confidence": "high"})
        if verbose:
            print("  + %s: net $%.1fM, Anthropic %s%%" % (
                rep, (float(na) or 0) / 1e6, round(anth_pct, 2) if anth_pct else "n/a"))
    anchors.sort(key=lambda a: a["report_date"])
    bad = [a for a in anchors if a["series_id"] != CFG.EDGAR_SERIES_ID]
    if bad:
        raise RuntimeError("identity check failed: non-AGIX series leaked in")
    return anchors


def write_anchors(anchors):
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "nport_anchors.json")
    json.dump(anchors, open(path, "w", encoding="utf-8"), indent=2)
    return path


if __name__ == "__main__":
    a = fetch_anchors(); print("wrote", write_anchors(a), "|", len(a), "AGIX anchors")
