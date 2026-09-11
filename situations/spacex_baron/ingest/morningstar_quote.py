"""Scrape BPTIX's Morningstar quote page for the EXACT Total Assets figure.

Why this exists
---------------
The daily workflow has always taken AUM as a user-reported rounded string ("16.5B"), which
caps net-flow precision at +/-$0.05B on each of two days — a +/-$100M band that swallowed
every flow signal smaller than a large redemption. The quote page carries the unrounded
number in an embedded JS payload:

    fundSize:{value:15782010255, ... label:"Total Assets", source:"Surveyed"}

so the same figure the page renders as "15.8B" is available to the dollar. It also carries
`nav`, which cross-checks against Yahoo's BPTIX close and tells you which day the page is
as-of.

Scope / etiquette
-----------------
- robots.txt (checked 2026-09-11) disallows /api*, /search, /login, /analyst-research* and a
  few others. **/funds/ is not disallowed**, so fetching the rendered quote page is allowed.
  Do NOT hit their /api* endpoints — those are explicitly off limits.
- One request per run. This is a manual/local step, NOT part of `build.py`: the CI rebuild
  must stay network-free apart from the known Yahoo/EDGAR fetches, and adding a third-party
  scrape there would ship blank sections the day the markup changes.
- The parse is deliberately defensive: if either the payload or the rendered span is missing,
  it returns what it found and flags the rest rather than guessing.

Usage
-----
    py -m situations.spacex_baron.ingest.morningstar_quote
    py -m situations.spacex_baron.ingest.morningstar_quote --json
"""

import json
import re
import sys
import urllib.request

URL = "https://www.morningstar.com/funds/xnas/bptix/quote"
_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _html(timeout=30):
    req = urllib.request.Request(URL, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def _rendered_rows(t):
    """{label: displayed value} from the visible quote table (rounded, e.g. '15.8B')."""
    out = {}
    for m in re.finditer(
            r'quote__label__mdc"><span>([^<]{2,40})</span></span>\s*<span class="quote__value__mdc">(.*?)</li>',
            t, re.S):
        lbl = m.group(1).strip()
        val = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        # the page uses typographic minus / non-breaking space; normalize so the strings
        # survive a cp1252 console and compare cleanly against our own records
        val = val.replace("−", "-").replace("–", "-").replace("\xa0", " ")
        if val:
            out[lbl] = val.strip()
    return out


def fetch(timeout=30):
    """Return the parsed quote. `total_assets_usd` is EXACT; `total_assets_raw` is what the
    page displays (the rounded string the manual workflow used)."""
    t = _html(timeout)
    out = {"url": URL, "ticker": "BPTIX"}

    m = re.search(r"\bfundSize:\{value:(\d+)", t)
    out["total_assets_usd"] = int(m.group(1)) if m else None

    m = re.search(r"\bnav:\{value:([\d.]+)", t)
    out["nav_per_share"] = float(m.group(1)) if m else None

    rows = _rendered_rows(t)
    out["total_assets_raw"] = rows.get("Total Assets")
    out["nav_row"] = rows.get("NAV / 1-Day Return")
    out["expense_ratio"] = rows.get("Expense Ratio")
    out["turnover"] = rows.get("Turnover")

    missing = [k for k in ("total_assets_usd", "nav_per_share") if out.get(k) is None]
    out["ok"] = not missing
    if missing:
        out["error"] = ("markup changed: could not parse %s — re-check the page before "
                        "trusting any field" % ", ".join(missing))
    return out


def main(argv):
    q = fetch()
    if "--json" in argv:
        print(json.dumps(q, indent=1))
        return 0 if q["ok"] else 1
    if not q["ok"]:
        print("FAILED:", q["error"])
        return 1
    ta = q["total_assets_usd"]
    print("BPTIX Morningstar quote")
    print("  Total Assets  $%s  (page shows %s)" % (format(ta, ","), q["total_assets_raw"]))
    print("                 = %.6fB exact, vs %.1fB rounded -> rounding hides $%s"
          % (ta / 1e9, round(ta / 1e9, 1), format(abs(ta - round(ta / 1e9, 1) * 1e9), ",.0f")))
    print("  NAV           %s   (%s)" % (q["nav_per_share"], q["nav_row"]))
    print("  expense %s | turnover %s" % (q["expense_ratio"], q["turnover"]))
    print("\n  cross-check the NAV against Yahoo's BPTIX close to confirm which day this is as-of.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
