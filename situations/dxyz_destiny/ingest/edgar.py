"""EDGAR ingest for Destiny Tech100 (DXYZ), CIK 1843974. NPORT-P net assets + holdings.
Like VCX, OpenAI/Anthropic are held via SPVs; look-through is sponsor-disclosed."""
import json, os, re, sys, time, urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import DxyzDestiny as CFG, SEC_USER_AGENT  # noqa: E402

_RAW = os.path.join(_REPO_ROOT, "situations", "dxyz_destiny", "data", "raw", "edgar")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "dxyz_destiny", "data", "processed")


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


def list_nport(cik):
    sub = json.loads(_get("https://data.sec.gov/submissions/CIK%s.json" % cik.zfill(10)))
    r = sub["filings"]["recent"]
    out = [{"accession": r["accessionNumber"][i], "nodash": r["accessionNumber"][i].replace("-", ""),
            "filing_date": r["filingDate"][i], "cik": cik.zfill(10)}
           for i, f in enumerate(r["form"]) if f == "NPORT-P"]
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


def fetch_anchors(verbose=True):
    anchors = []
    for rec in list_nport(CFG.EDGAR_CIK):
        try:
            x = _doc(rec)
        except Exception as e:
            if verbose:
                print("  ! skip", rec["accession"], e)
            continue
        na, ta = _tag(x, "netAssets"), _tag(x, "totAssets")
        holdings = []
        for blk in re.findall(r'<invstOrSec>.*?</invstOrSec>', x, re.S):
            holdings.append({"name": _tag(blk, "name") or "", "valUSD": float(_tag(blk, "valUSD") or 0),
                             "pctVal": float(_tag(blk, "pctVal") or 0)})
        holdings.sort(key=lambda h: -h["pctVal"])
        anchors.append({"report_date": _tag(x, "repPdDate"), "filing_date": rec["filing_date"],
                        "accession": rec["accession"], "net_assets_usd": float(na) if na else None,
                        "total_assets_usd": float(ta) if ta else None, "n_holdings": len(holdings),
                        "top_holdings": holdings[:15], "source": "measured", "confidence": "high"})
        if verbose:
            print("  + %s: net $%.1fM, %d holdings" % (anchors[-1]["report_date"], (float(na) or 0) / 1e6, len(holdings)))
    anchors.sort(key=lambda a: a["report_date"])
    return anchors


def write_anchors(anchors):
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "nport_anchors.json")
    json.dump(anchors, open(path, "w", encoding="utf-8"), indent=2)
    return path


if __name__ == "__main__":
    a = fetch_anchors(); print("wrote", write_anchors(a), "|", len(a), "anchors")
