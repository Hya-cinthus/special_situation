"""
EDGAR ingest for the Fundrise Innovation Fund (VCX), CIK 1867090.

Pulls NPORT-P: total net assets (a cross-check on the sponsor NAV) and the
holdings list. IMPORTANT: OpenAI/Anthropic do NOT appear as named line items —
they are held through codenamed SPVs/LPs (e.g. "Quiet OA Access LP",
"DBH1 LP"). So this module returns the raw holdings (by whatever name the filing
uses) for transparency; the OpenAI/Anthropic look-through weights come from the
sponsor's disclosure (config.LOOKTHROUGH), clearly flagged as not SEC-verifiable.

Pure stdlib; raw filings cached under data/raw/edgar/.
"""

import json
import os
import re
import sys
import time
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import VcxFundrise as CFG, SEC_USER_AGENT  # noqa: E402

_RAW = os.path.join(_REPO_ROOT, "situations", "vcx_fundrise", "data", "raw", "edgar")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "vcx_fundrise", "data", "processed")


def _get(url: str) -> bytes:
    for attempt in range(4):
        try:
            r = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT}), timeout=45)
            time.sleep(0.12)
            return r.read()
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"GET failed: {url}")


def _tag(s, t):
    m = re.search(rf"<{t}>(.*?)</{t}>", s, re.S)
    return m.group(1).strip() if m else None


def list_nport(cik: str) -> list[dict]:
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"))
    r = sub["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form == "NPORT-P":
            acc = r["accessionNumber"][i]
            out.append({"accession": acc, "nodash": acc.replace("-", ""),
                        "filing_date": r["filingDate"][i], "cik": cik.zfill(10)})
    out.sort(key=lambda d: d["filing_date"], reverse=True)
    return out


def _doc(rec: dict) -> str:
    os.makedirs(_RAW, exist_ok=True)
    p = os.path.join(_RAW, f"{rec['nodash']}.xml")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return open(p, encoding="utf-8", errors="replace").read()
    url = f"https://www.sec.gov/Archives/edgar/data/{int(rec['cik'])}/{rec['nodash']}/primary_doc.xml"
    t = _get(url).decode("utf-8", "replace")
    open(p, "w", encoding="utf-8").write(t)
    return t


def fetch_anchors(verbose: bool = True) -> list[dict]:
    anchors = []
    for rec in list_nport(CFG.EDGAR_CIK):
        try:
            x = _doc(rec)
        except Exception as e:
            if verbose:
                print("  ! skip", rec["accession"], e)
            continue
        na = _tag(x, "netAssets")
        ta = _tag(x, "totAssets")
        holdings = []
        for blk in re.findall(r"<invstOrSec>.*?</invstOrSec>", x, re.S):
            nm = _tag(blk, "name") or ""
            val = float(_tag(blk, "valUSD") or 0)
            pct = float(_tag(blk, "pctVal") or 0)
            holdings.append({"name": nm, "valUSD": val, "pctVal": pct})
        holdings.sort(key=lambda h: -h["pctVal"])
        anchors.append({
            "report_date": _tag(x, "repPdDate"),
            "filing_date": rec["filing_date"],
            "accession": rec["accession"],
            "net_assets_usd": float(na) if na else None,
            "total_assets_usd": float(ta) if ta else None,
            "n_holdings": len(holdings),
            "top_holdings": holdings[:15],
            "source": "measured", "confidence": "high",
        })
        if verbose:
            print(f"  + {anchors[-1]['report_date']}: net ${(float(na) or 0)/1e6:.1f}M, "
                  f"{len(holdings)} holdings")
    anchors.sort(key=lambda a: a["report_date"])
    return anchors


def write_anchors(anchors: list[dict]) -> str:
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "nport_anchors.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(anchors, f, indent=2)
    return path


if __name__ == "__main__":
    print("Fetching VCX NPORT-P anchors...")
    a = fetch_anchors()
    print("wrote", write_anchors(a), "|", len(a), "anchors")
    if a:
        print("latest top holdings:")
        for h in a[-1]["top_holdings"][:8]:
            print(f"  {h['pctVal']:5.1f}%  {h['name'][:46]}")
