"""
EDGAR ingestion — Baron Partners Fund quarterly anchors from NPORT-P.

Pulls every NPORT-P filed by the registrant (Baron Select Funds, CIK 1217673),
keeps the ones whose <seriesName> is "Baron Partners Fund", sums ALL SpaceX
tranches (the holding appears as multiple line items — common / preferred /
different rounds), and records total net assets. The result is the quarterly
"anchor" table that the reconstruction engine ties to.

Pure standard library. Raw filings are cached under data/raw/edgar/ so re-runs
are fast and offline-friendly.

Every figure produced here is `measured` / `high` confidence: it comes straight
out of the fund's own SEC filing.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime

# Make `config` importable whether run from repo root or as a module.
import sys
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import SpacexBaron as CFG, SEC_USER_AGENT  # noqa: E402

_RAW_DIR = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "raw", "edgar")
_PROCESSED = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "processed")
_THROTTLE_S = 0.12  # SEC fair-access: stay well under 10 req/s


def _http_get(url: str, max_retries: int = 4) -> bytes:
    headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    last = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                time.sleep(_THROTTLE_S)
                return raw
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"GET failed after {max_retries} tries: {url} ({last})")


def _submissions(cik: str) -> dict:
    cik10 = cik.zfill(10)
    return json.loads(_http_get(f"https://data.sec.gov/submissions/CIK{cik10}.json"))


def list_nport_accessions(cik: str) -> list[dict]:
    """All NPORT-P filings for the registrant, newest first.

    Pages through the older `filings.files` shards too, so history is complete
    back to when NPORT-P began (~2019), not just the most recent ~1000 filings.
    """
    cik10 = cik.zfill(10)
    sub = _submissions(cik)
    blocks = [sub["filings"]["recent"]]
    for extra in sub["filings"].get("files", []):
        blocks.append(json.loads(_http_get(f"https://data.sec.gov/submissions/{extra['name']}")))

    out = []
    for b in blocks:
        forms = b.get("form", [])
        for i, form in enumerate(forms):
            if form != "NPORT-P":
                continue
            acc = b["accessionNumber"][i]
            out.append({
                "accession": acc,
                "accession_nodash": acc.replace("-", ""),
                "filing_date": b["filingDate"][i],
                "primary_doc": b.get("primaryDocument", [""] * len(forms))[i],
                "cik": cik10,
            })
    out.sort(key=lambda d: d["filing_date"], reverse=True)
    return out


def _primary_doc_url(rec: dict) -> str:
    # primaryDocument is often a styled xslt path; the raw XML is primary_doc.xml.
    return (f"https://www.sec.gov/Archives/edgar/data/{int(rec['cik'])}/"
            f"{rec['accession_nodash']}/primary_doc.xml")


def _fetch_doc_cached(rec: dict) -> str:
    os.makedirs(_RAW_DIR, exist_ok=True)
    path = os.path.join(_RAW_DIR, f"{rec['accession_nodash']}.xml")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    text = _http_get(_primary_doc_url(rec)).decode("utf-8", "replace")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def _tag(xml: str, name: str):
    m = re.search(rf"<{name}>(.*?)</{name}>", xml, re.S)
    return m.group(1).strip() if m else None


def _series_name(xml: str):
    return _tag(xml, "seriesName")


def _parse_baron_partners(xml: str, rec: dict):
    """Extract the Baron Partners anchor from one NPORT-P XML, or None.

    Identity is keyed on the SEC **seriesId** (S000000588), not the series name —
    a string match alone is brittle and could collide with a renamed/legacy
    series. The name and registrant CIK are kept as secondary corroboration. A
    same-trust sibling that also holds SpaceX (Baron Focused Growth, S000022521)
    fails the seriesId gate and is rejected.
    """
    series_id = _tag(xml, "seriesId")
    if series_id != CFG.EDGAR_SERIES_ID:
        return None
    # Defense in depth: secondary identifiers must also agree.
    reg_cik = (_tag(xml, "regCik") or "").lstrip("0")
    if (_series_name(xml) or "").strip().lower() != CFG.EDGAR_SERIES_NAME.lower():
        return None
    if reg_cik and reg_cik != CFG.EDGAR_CIK.lstrip("0"):
        return None

    rep_date = _tag(xml, "repPdDate")
    net_assets = _tag(xml, "netAssets")
    tot_assets = _tag(xml, "totAssets")

    spacex_value = 0.0
    spacex_balance = 0.0
    spacex_pct = 0.0
    tranches = []
    liquidity_buckets = set()
    needle = CFG.HOLDING_NAME_MATCH.lower()
    for blk in re.findall(r"<invstOrSec>.*?</invstOrSec>", xml, re.S):
        name = (_tag(blk, "name") or "")
        title = (_tag(blk, "title") or "")
        if needle not in name.lower() and needle not in title.lower():
            continue
        val = float(_tag(blk, "valUSD") or 0)
        bal = float(_tag(blk, "balance") or 0)
        pct = float(_tag(blk, "pctVal") or 0)
        liq = _tag(blk, "invstmtClass") or _tag(blk, "liquidityCls")
        if liq:
            liquidity_buckets.add(liq)
        spacex_value += val
        spacex_balance += bal
        spacex_pct += pct
        tranches.append({"name": name, "balance": bal, "valUSD": val, "pctVal": pct})

    if not tranches:
        return None

    return {
        "report_date": rep_date,
        "filing_date": rec["filing_date"],
        "accession": rec["accession"],
        "series_id": series_id,
        "series_name": _series_name(xml),
        "reg_cik": reg_cik,
        "net_assets_usd": float(net_assets) if net_assets else None,
        "total_assets_usd": float(tot_assets) if tot_assets else None,
        "spacex_value_usd": round(spacex_value, 2),
        "spacex_balance_units": round(spacex_balance, 4),
        "spacex_pct_of_net_assets": round(spacex_pct, 6),
        "spacex_n_tranches": len(tranches),
        "spacex_liquidity_buckets": "|".join(sorted(liquidity_buckets)) or "",
        "source": "measured",
        "confidence": "high",
    }


def fetch_anchors(limit_filings: int | None = None, verbose: bool = True) -> list[dict]:
    """Build the Baron Partners quarterly anchor table from NPORT-P filings.

    Iterates filings newest-first; within each filing date (a quarterly batch of
    ~12 sibling series) it stops as soon as it finds the Baron Partners doc, so
    it rarely downloads more than a handful of docs per quarter.
    """
    accs = list_nport_accessions(CFG.EDGAR_CIK)
    if limit_filings:
        accs = accs[:limit_filings]

    anchors_by_period = {}
    # Group by filing date so we can short-circuit each quarterly batch.
    batches: dict[str, list[dict]] = {}
    for rec in accs:
        batches.setdefault(rec["filing_date"], []).append(rec)

    for fdate in sorted(batches, reverse=True):
        found = False
        for rec in batches[fdate]:
            try:
                xml = _fetch_doc_cached(rec)
            except Exception as e:  # keep going on a single bad doc
                if verbose:
                    print(f"  ! skip {rec['accession']}: {e}")
                continue
            anchor = _parse_baron_partners(xml, rec)
            if anchor:
                key = anchor["report_date"]
                # Keep the earliest-filed doc for a given report period.
                if key not in anchors_by_period or anchor["filing_date"] < anchors_by_period[key]["filing_date"]:
                    anchors_by_period[key] = anchor
                if verbose:
                    print(f"  + {key}: SpaceX ${anchor['spacex_value_usd']/1e9:.2f}B "
                          f"({anchor['spacex_pct_of_net_assets']:.1f}% of net), "
                          f"net ${(anchor['net_assets_usd'] or 0)/1e9:.2f}B "
                          f"[{anchor['spacex_n_tranches']} tranches]")
                found = True
                break  # Baron Partners found for this batch; move on
        if not found and verbose:
            print(f"  . {fdate}: no Baron Partners NPORT-P in batch")

    anchors = sorted(anchors_by_period.values(), key=lambda a: a["report_date"])

    # Forensic post-condition: every accepted anchor MUST be the canonical series.
    offenders = [a for a in anchors if a.get("series_id") != CFG.EDGAR_SERIES_ID]
    if offenders:
        raise RuntimeError(
            f"identity check failed: {len(offenders)} anchor(s) not seriesId "
            f"{CFG.EDGAR_SERIES_ID}: {[a['accession'] for a in offenders]}")
    if verbose and anchors:
        print(f"  identity OK: all {len(anchors)} anchors are seriesId "
              f"{CFG.EDGAR_SERIES_ID} ({CFG.EDGAR_SERIES_NAME})")
    return anchors


def write_anchors_csv(anchors: list[dict]) -> str:
    os.makedirs(_PROCESSED, exist_ok=True)
    path = os.path.join(_PROCESSED, "anchors_quarterly.csv")
    cols = ["report_date", "filing_date", "accession", "series_id", "series_name",
            "reg_cik", "net_assets_usd", "total_assets_usd", "spacex_value_usd",
            "spacex_balance_units", "spacex_pct_of_net_assets", "spacex_n_tranches",
            "spacex_liquidity_buckets", "source", "confidence"]
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for a in anchors:
            w.writerow(a)
    return path


if __name__ == "__main__":
    print("Fetching Baron Partners NPORT-P anchors from EDGAR...")
    anchors = fetch_anchors()
    path = write_anchors_csv(anchors)
    print(f"\nWrote {len(anchors)} anchors -> {path}")
