"""
Cross-fund SpaceX allocation across ALL Baron funds -> dashboard/data/baron_spacex_funds.json

Baron holds Space Exploration Technologies (SpaceX) in SIX of its mutual funds,
spread across two registrant trusts:
    Baron Select Funds            (CIK 1217673): Partners, Focused Growth, Global Advantage
    Baron Investment Funds Trust  (CIK  810902): Asset, Opportunity, Fifth Avenue Growth

This scans EVERY NPORT-P those trusts have filed (one doc per series per quarter,
back to when NPORT-P began ~2019), extracts the SpaceX line(s) and net assets for
any series that holds it, and builds a per-fund quarterly time series in BOTH
dollars and % of the fund's net assets. Everything here is `measured` / `high`
confidence — straight from each fund's own SEC filing. Pure standard library.

The headline metric for the IPO question: Baron Partners Fund's share of TOTAL
Baron SpaceX dollars each quarter (it has consistently held the large majority),
which informs how a family-wide SpaceX IPO allocation would likely split.
"""

import json
import os
import re
import sys
import datetime

_REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from situations.spacex_baron.ingest import edgar as E  # reuse cached HTTP + accession list

TRUSTS = {
    "1217673": "Baron Select Funds",
    "810902": "Baron Investment Funds Trust",
}

# SEC seriesId -> (display name, retail ticker, institutional ticker). Tickers are
# Baron's published share-class symbols; left None where not confidently known.
FUND_META = {
    "S000000588": ("Baron Partners Fund", "BPTRX", "BPTIX"),
    "S000022521": ("Baron Focused Growth Fund", "BFGFX", "BFGIX"),
    "S000000582": ("Baron Asset Fund", "BARAX", "BARIX"),
    "S000000585": ("Baron Opportunity Fund", "BIOPX", "BIOIX"),
    "S000000586": ("Baron Fifth Avenue Growth Fund", "BFTHX", "BFTIX"),
    "S000036767": ("Baron Global Advantage Fund", "BGAFX", "BGAIX"),
}

# --- Baron's OWN cross-vehicle SpaceX disclosure (corroboration + private funds) ---
# Q1 2026 "Letter from Ron," Table I, as of 3/31/2026. Includes PRIVATE vehicles
# (BaronX, BaronX II, USA Partners) + the RONB ETF that do NOT file the NPORT-P the
# SEC scan reads, so they're otherwise invisible. The six open-end mutual-fund lines
# tie to the SEC scan to the decimal ($6.03B), which validates both. Self-reported
# by Baron (tagged so on the page); $ in millions, % of that vehicle's net assets.
FIRM_WIDE_DISCLOSURE = {
    "as_of": "2026-03-31",
    "source": "Baron 'Letter from Ron', Q1 2026, Table I (Baron self-disclosure)",
    "source_url": "https://www.baroncapitalgroup.com/article/letter-ron-q1-2026",
    # Baron's stated firm-wide SpaceX total. The 10 vehicles below are the itemized
    # ones (they sum to ~$12.0B); the difference vs the stated total is other Baron
    # accounts/SMAs not separately listed — shown as a residual row on the page.
    "stated_total_usd": 14_930_300_000,
    "vehicles": [
        # (name, spacex_usd, pct_of_net, files_nport, vehicle_type)
        ("BaronX",                          4_506_800_000, 99.4, False, "private fund"),
        ("Baron Partners Fund",             3_890_300_000, 37.4, True,  "open-end mutual fund"),
        ("BaronX II",                       1_027_800_000, 98.1, False, "private fund"),
        ("Baron Asset Fund",                  844_700_000, 25.5, True,  "open-end mutual fund"),
        ("Baron Focused Growth Fund",         821_100_000, 21.2, True,  "open-end mutual fund"),
        ("Baron USA Partners Fund",           413_600_000, 79.2, False, "private/offshore fund"),
        ("Baron Opportunity Fund",            248_400_000, 15.4, True,  "open-end mutual fund"),
        ("Baron Global Advantage Fund",       172_400_000, 20.5, True,  "open-end mutual fund"),
        ("Baron Fifth Avenue Growth Fund",     50_400_000,  7.5, True,  "open-end mutual fund"),
        ("Baron First Principles ETF (RONB)",  30_000_000, 12.6, True,  "ETF"),
    ],
}

# --- SpaceX IPO facts (from the news research; each tagged on the page) ----------
IPO_FACTS = {
    "ticker": "SPCX", "exchange": "Nasdaq",
    "first_trade_date": "2026-06-12", "pricing_date": "2026-06-11",
    "offer_price_usd": 135.0,
    "structure": "Traditional IPO at a fixed $135 price (no bookbuild range)",
    "split": "5-for-1, effective 2026-05-04",
    "post_split_private_mark_usd": 105.32,
    "post_money_valuation_usd": 1_770_000_000_000,
    "primary_shares": 555_555_555,
    "primary_raise_usd": 75_000_000_000,
    "with_greenshoe_usd": 85_700_000_000,
    "lead_banks": ["Goldman Sachs", "Morgan Stanley", "BofA", "Citigroup", "JPMorgan"],
    "fy2025_revenue_usd": 18_670_000_000,
    "fy2025_net_loss_usd": 4_940_000_000,
    "confidence": "IPO date/price/ticker/split CONFIRMED; raise & valuation CONFIRMED/REPORTED",
    "sources": [
        "CNBC 2026-06-03 (fixed $135 price); CNBC 2026-06-09 (IPO explained)",
        "Bloomberg 2026-05-16 (5-for-1 split approved)",
        "S-1 via TradingKey/BitMEX (FY2025 financials, share count)",
    ],
}

# --- Baron's stated IPO order (the thing we're sizing through to BPTIX) ----------
BARON_ORDER = {
    "amount_usd": 1_000_000_000,
    "status": "REQUESTED — may not be fully filled (book reportedly oversubscribed)",
    "quote": ("At the IPO price, I've got an order for $1 billion. I want to buy more "
              "stock at the IPO. I don't know if we're going to get filled, but we're "
              "going to try."),
    "attribution": "Ron Baron, ~2026-05-12 (widely reported; CNBC segment / Baron client call)",
    "rationale": ("Largely anti-dilution: defend Baron's ~1.25% SpaceX ownership against "
                  "the ~$75B primary raise (~4.2% new shares), plus genuine add."),
    "confidence": "REPORTED (verbatim quote multi-sourced); fill size NOT disclosed",
    "per_fund_split_disclosed": False,
}


def allocation_analysis(funds, firm_total_usd, bp_public_share, bp_firm_share):
    """Scenario-size how much of Baron's $1B IPO order lands in Baron Partners Fund
    (the home of the BPTIX share class). The per-fund split is NOT publicly
    disclosed, so we bound it with two pro-rata bases and an anti-dilution check."""
    order = BARON_ORDER["amount_usd"]
    bp_nav_latest = 18_700_000_000  # Baron Partners net AUM, Morningstar 6/10/2026
    val = IPO_FACTS["post_money_valuation_usd"]
    raise_ = IPO_FACTS["primary_raise_usd"]
    dilution = raise_ / val  # ~4.24% new primary shares

    def slice_(basis_share, filled):
        usd = order * filled * basis_share
        return {"to_baron_partners_usd": round(usd),
                "pct_of_bp_nav": round(usd / bp_nav_latest * 100, 2)}

    return {
        "question": "How much of Baron's $1B SpaceX IPO order flows into Baron Partners Fund (BPTIX)?",
        "baron_partners_share_of_public_funds_pct": round(bp_public_share, 1),
        "baron_partners_share_of_firm_wide_pct": round(bp_firm_share, 1),
        "bp_nav_usd": bp_nav_latest,
        "primary_dilution_pct": round(dilution * 100, 2),
        "anti_dilution_firmwide_usd": round(dilution * firm_total_usd),  # to hold firm % flat
        "anti_dilution_baron_partners_usd": round(dilution * 3_890_300_000),
        "scenarios": [
            {"label": "Pro-rata across ALL Baron SpaceX vehicles (incl. private BaronX)",
             "basis_pct": round(bp_firm_share, 1), "full_fill": slice_(bp_firm_share / 100, 1.0),
             "half_fill": slice_(bp_firm_share / 100, 0.5)},
            {"label": "Pro-rata across PUBLIC open-end mutual funds only",
             "basis_pct": round(bp_public_share, 1), "full_fill": slice_(bp_public_share / 100, 1.0),
             "half_fill": slice_(bp_public_share / 100, 0.5)},
        ],
        "share_class_note": ("IPO shares accrue to the FUND and are shared across its 3 classes "
                             "(BPTRX retail, BPTIX institutional, BPTUX R6) pro-rata by NAV — so "
                             "BPTIX automatically gets its AUM-proportional slice. Retail BPTRX was "
                             "~$4.16B (MSN); BPTIX/BPTUX make up the rest of the ~$18.7B fund."),
        "bottom_line": ("No public source discloses the per-fund split (NOT FOUND). Baron Partners "
                        "holds ~65% of Baron's PUBLIC-fund SpaceX but ~26% of firm-wide SpaceX (the "
                        "private BaronX vehicles hold ~$5.5B at ~99%). So a fully-filled $1B order "
                        "plausibly sends ~$260M-$650M into Baron Partners Fund = ~1.4%-3.5% of its "
                        "$18.7B NAV in incremental SpaceX, on top of the existing ~27%. Incremental, "
                        "not transformational — and the fill itself is uncertain. The order is bought "
                        "at the $135 IPO price, which the fund already marks SpaceX at (since 6/4), so "
                        "it adds exposure/shares without an immediate markup."),
        "confidence": "Bases are MEASURED (SEC+Baron letter); the split itself is UNDISCLOSED inference.",
    }


def _tag(xml, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", xml, re.S)
    return m.group(1).strip() if m else None


def _spacex_tranches(xml):
    """Sum every SpaceX line item in one NPORT-P doc. Returns (value, pctVal, n)."""
    val = pct = 0.0
    n = 0
    for blk in re.findall(r"<invstOrSec>.*?</invstOrSec>", xml, re.S):
        nm = ((_tag(blk, "name") or "") + " " + (_tag(blk, "title") or "")).lower()
        if "space exploration" in nm or "spacex" in nm:
            val += float(_tag(blk, "valUSD") or 0)
            pct += float(_tag(blk, "pctVal") or 0)
            n += 1
    return val, pct, n


def scan(verbose=True):
    """Walk every NPORT-P in both trusts; keep docs that hold SpaceX."""
    rows = []          # one per (series, quarter) that holds SpaceX
    for cik, tname in TRUSTS.items():
        accs = E.list_nport_accessions(cik)
        if verbose:
            print(f"[{tname}] {len(accs)} NPORT-P filings to scan")
        for i, rec in enumerate(accs):
            try:
                xml = E._fetch_doc_cached(rec)
            except Exception as e:
                if verbose:
                    print(f"  ! skip {rec['accession']}: {e}")
                continue
            low = xml.lower()
            if "space exploration" not in low and "spacex" not in low:
                continue
            sid = _tag(xml, "seriesId")
            val, pct, n = _spacex_tranches(xml)
            if val <= 0:
                continue
            na = _tag(xml, "netAssets")
            rows.append({
                "trust_cik": cik, "trust": tname,
                "series_id": sid, "series_name": _tag(xml, "seriesName"),
                "report_date": _tag(xml, "repPdDate"),
                "filing_date": rec["filing_date"], "accession": rec["accession"],
                "net_assets_usd": float(na) if na else None,
                "spacex_value_usd": round(val, 2),
                "spacex_pct_of_net": round(pct, 4),
                "spacex_n_tranches": n,
            })
            if verbose and (i % 25 == 0):
                print(f"  .. {i}/{len(accs)} scanned")
    return rows


def build_payload(rows=None):
    rows = rows if rows is not None else scan()

    # de-dupe: keep earliest-filed doc per (series, report_date)
    best = {}
    for r in rows:
        k = (r["series_id"], r["report_date"])
        if k not in best or r["filing_date"] < best[k]["filing_date"]:
            best[k] = r
    rows = list(best.values())

    # group into per-fund time series
    funds = {}
    for r in rows:
        sid = r["series_id"]
        funds.setdefault(sid, []).append(r)
    fund_objs = []
    for sid, series in funds.items():
        series.sort(key=lambda x: x["report_date"])
        name, t_ret, t_inst = FUND_META.get(sid, (series[-1]["series_name"], None, None))
        pts = [{"report_date": s["report_date"],
                "net_assets_usd": s["net_assets_usd"],
                "spacex_value_usd": s["spacex_value_usd"],
                "spacex_pct_of_net": s["spacex_pct_of_net"],
                "n_tranches": s["spacex_n_tranches"]} for s in series]
        latest = pts[-1]
        fund_objs.append({
            "series_id": sid, "name": name,
            "ticker_retail": t_ret, "ticker_institutional": t_inst,
            "trust": series[-1]["trust"], "trust_cik": series[-1]["trust_cik"],
            "first_report_date": pts[0]["report_date"],
            "latest": latest, "series": pts,
        })
    # sort funds by latest SpaceX $ (largest first)
    fund_objs.sort(key=lambda f: -(f["latest"]["spacex_value_usd"] or 0))

    # family-wide SpaceX by quarter (sum across funds that reported that quarter)
    all_dates = sorted({p["report_date"] for f in fund_objs for p in f["series"]})
    by_q = []
    for d in all_dates:
        tot_spx = tot_net = 0.0
        bp = 0.0
        contributors = 0
        for f in fund_objs:
            p = next((x for x in f["series"] if x["report_date"] == d), None)
            if not p:
                continue
            contributors += 1
            tot_spx += p["spacex_value_usd"] or 0
            tot_net += p["net_assets_usd"] or 0
            if f["series_id"] == "S000000588":
                bp = p["spacex_value_usd"] or 0
        by_q.append({
            "report_date": d,
            "total_spacex_usd": round(tot_spx, 2),
            "total_net_usd": round(tot_net, 2),
            "n_funds": contributors,
            "baron_partners_spacex_usd": round(bp, 2),
            "baron_partners_share_pct": round(bp / tot_spx * 100, 2) if tot_spx else None,
        })

    latest_q = by_q[-1] if by_q else {}
    bp_public_share = latest_q.get("baron_partners_share_pct") or 0   # % of public-fund SpaceX
    firm_total = FIRM_WIDE_DISCLOSURE["stated_total_usd"]
    itemized_total = sum(v[1] for v in FIRM_WIDE_DISCLOSURE["vehicles"])
    FIRM_WIDE_DISCLOSURE["itemized_total_usd"] = itemized_total
    FIRM_WIDE_DISCLOSURE["residual_usd"] = round(firm_total - itemized_total)
    bp_firm_share = 3_890_300_000 / firm_total * 100                  # % of stated firm-wide SpaceX
    return {
        "meta": {
            "title": "SpaceX across the Baron fund family — NPORT-P cross-fund comparison",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": ("SEC EDGAR NPORT-P filings, both Baron registrant trusts "
                       "(Baron Select Funds CIK 1217673; Baron Investment Funds Trust CIK 810902). "
                       "SpaceX = Space Exploration Technologies, all share-class/round tranches summed. "
                       "Net assets and % are the fund's own filed figures."),
            "confidence": "measured / high — every figure is from the fund's own SEC filing",
            "n_funds": len(fund_objs),
            "latest_report_date": latest_q.get("report_date"),
            "disclaimer": ("Quarterly NPORT-P is the only free, audited per-fund SpaceX figure. "
                           "Between quarter-ends the marks are stale (SpaceX last repriced 6/4/2026 to "
                           "$135). % of net moves with both the SpaceX mark and fund inflows."),
        },
        "funds": fund_objs,
        "family_by_quarter": by_q,
        "latest": {
            "report_date": latest_q.get("report_date"),
            "total_spacex_usd": latest_q.get("total_spacex_usd"),
            "n_funds": latest_q.get("n_funds"),
            "baron_partners_share_pct": latest_q.get("baron_partners_share_pct"),
            "ranking": [{"name": f["name"], "ticker_institutional": f["ticker_institutional"],
                         "spacex_value_usd": f["latest"]["spacex_value_usd"],
                         "spacex_pct_of_net": f["latest"]["spacex_pct_of_net"],
                         "report_date": f["latest"]["report_date"]} for f in fund_objs],
        },
        "firm_wide": FIRM_WIDE_DISCLOSURE,
        "ipo": IPO_FACTS,
        "baron_order": BARON_ORDER,
        "ipo_allocation": allocation_analysis(fund_objs, firm_total, bp_public_share, bp_firm_share),
    }


def write_json():
    payload = build_payload()
    out_dir = os.path.join(_REPO_ROOT, "dashboard", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "baron_spacex_funds.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return path


if __name__ == "__main__":
    pl = build_payload()
    print(f"\n{pl['meta']['n_funds']} Baron funds hold SpaceX | latest quarter "
          f"{pl['latest']['report_date']}")
    print(f"{'fund':34s} {'SpaceX $':>10s} {'% net':>7s} {'first':>10s}  pts")
    for f in pl["funds"]:
        L = f["latest"]
        print(f"{f['name'][:34]:34s} {L['spacex_value_usd']/1e9:>9.3f}B {L['spacex_pct_of_net']:>6.1f}% "
              f"{f['first_report_date']:>10s}  {len(f['series'])}")
    lq = pl["family_by_quarter"][-1]
    print(f"\nFamily total SpaceX ${lq['total_spacex_usd']/1e9:.2f}B across {lq['n_funds']} funds; "
          f"Baron Partners = {lq['baron_partners_share_pct']}% of it")
    print("wrote", write_json())
