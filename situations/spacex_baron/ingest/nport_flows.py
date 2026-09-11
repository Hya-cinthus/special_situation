"""Extract MONTHLY subscription/redemption flows from every Baron Partners NPORT-P.

Why this exists
---------------
Until now every flow number in this project was BACK-SOLVED from two rounded AUM prints:
`flow = AUM_end - AUM_prev * NAV_end/NAV_prev`, with a +/-$100M band baked in by the rounding.
NPORT-P carries the real thing. Each filing reports three months of flows in
`mon1Flow` / `mon2Flow` / `mon3Flow`, each with exact `sales`, `redemption` and `reinvestment`:

    <mon3Flow redemption="3161706297.81" reinvestment="0.00" sales="2744626083.75"/>

That is the fund's own subscription and redemption ledger, to the cent, for every month back
to 2019. It settles questions the daily series can only estimate — most importantly it
separates GROSS CHURN from a net run (June 2026: $3.16B redeemed against $2.74B sold, so a
violent-looking month was only -$417M net).

Identity is gated on seriesId S000000588, same as edgar.py — a sibling that also holds SpaceX
would otherwise contaminate the series.

Scope
-----
Quarterly cadence, so this is a LOCAL step run when a new NPORT lands, not part of `build.py`
(the CI rebuild stays network-free apart from the known Yahoo/EDGAR fetches).

Usage
-----
    py -m situations.spacex_baron.ingest.nport_flows          # print the table
    py -m situations.spacex_baron.ingest.nport_flows --csv    # rewrite the committed CSV
"""

import csv
import json
import os
import re
import sys
import urllib.request

_UA = {"User-Agent": "weipeng shao weipeng_shao@berkeley.edu"}
_CIK = "1217673"
_SERIES = "S000000588"
_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "nport_monthly_flows.csv")


def _get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=_UA),
                                  timeout=timeout).read().decode("utf-8", "ignore")


def _tag(x, n):
    m = re.search(r"<(?:\w+:)?%s\b[^>]*>(.*?)</(?:\w+:)?%s>" % (n, n), x, re.S)
    return m.group(1).strip() if m else None


def _shift(rep_date, i):
    """mon1/mon2/mon3 are the first/second/third month of the reporting quarter."""
    y, m, _ = (int(v) for v in rep_date.split("-"))
    mon = m - 2 + i
    if mon <= 0:
        y, mon = y - 1, mon + 12
    return "%04d-%02d" % (y, mon)


def fetch(verbose=True):
    j = json.loads(_get("https://data.sec.gov/submissions/CIK%010d.json" % int(_CIK)))
    r = j["filings"]["recent"]
    rows, seen = [], set()
    for fd, form, acc, rd in zip(r["filingDate"], r["form"], r["accessionNumber"], r["reportDate"]):
        if form != "NPORT-P" or rd in seen:
            continue
        try:
            t = _get("https://www.sec.gov/Archives/edgar/data/%s/%s/primary_doc.xml"
                     % (_CIK, acc.replace("-", "")))
        except Exception:
            continue
        if _tag(t, "seriesId") != _SERIES:
            continue
        seen.add(rd)
        net = _tag(t, "netAssets")
        tot = _tag(t, "totAssets")
        for i, fl in enumerate(("mon1Flow", "mon2Flow", "mon3Flow")):
            m = re.search(r'<(?:\w+:)?%s\b([^>]*)/>' % fl, t)
            if not m:
                continue
            a = dict(re.findall(r'(\w+)="([\d.\-]+)"', m.group(1)))
            sales = float(a.get("sales", 0))
            red = float(a.get("redemption", 0))
            rein = float(a.get("reinvestment", 0))
            rows.append({
                "month": _shift(rd, i), "report_date": rd, "accession": acc,
                "sales_usd": sales, "redemption_usd": red, "reinvestment_usd": rein,
                "net_flow_usd": sales - red,
                # net/total assets are reported once per filing, at the QUARTER END only
                "quarter_end_net_assets_usd": (float(net) if (net and i == 2) else ""),
                "quarter_end_total_assets_usd": (float(tot) if (tot and i == 2) else ""),
            })
        if verbose:
            print("  %s (filed %s) -> 3 months" % (rd, fd), file=sys.stderr)
    rows.sort(key=lambda x: x["month"])
    return rows


def write_csv(rows, path=_OUT):
    cols = ["month", "sales_usd", "redemption_usd", "reinvestment_usd", "net_flow_usd",
            "quarter_end_net_assets_usd", "quarter_end_total_assets_usd", "report_date", "accession"]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})
    return path


def main(argv):
    rows = fetch()
    print("%-9s %16s %16s %16s %18s" % ("month", "sales", "redemption", "NET", "qtr-end net assets"))
    for r in rows:
        qe = r["quarter_end_net_assets_usd"]
        print("%-9s %16s %16s %+16s %18s"
              % (r["month"], format(r["sales_usd"], ",.0f"), format(r["redemption_usd"], ",.0f"),
                 format(r["net_flow_usd"], ",.0f"), format(qe, ",.0f") if qe else ""))
    print("\n%d months, cumulative net flow %s"
          % (len(rows), format(sum(r["net_flow_usd"] for r in rows), "+,.0f")))
    if "--csv" in argv:
        print("wrote", write_csv(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
