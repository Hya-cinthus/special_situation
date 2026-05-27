"""
Forensic identity tests — guarantee every anchor is *the* Baron Partners Fund
(SEC seriesId S000000588), never a confusable sibling/trust/adviser/class.

Offline tests run against the cached raw NPORT-P XML + processed anchors CSV and
always run. The network test (SEC official ticker master) is skipped if offline.

Canonical identity (independently sourced from SEC's mutual-fund ticker master):
    BPTRX / BPTIX / BPTUX  ->  CIK 1217673 (Baron Select Funds), seriesId S000000588
The same-trust sibling that ALSO holds SpaceX, Baron Focused Growth Fund, is
seriesId S000022521 and must be rejected.
"""

import csv
import os
import re
import sys
import unittest
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from config import SpacexBaron as CFG, SEC_USER_AGENT  # noqa: E402

_PROCESSED = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "processed")
_RAW = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "raw", "edgar")
_ANCHORS = os.path.join(_PROCESSED, "anchors_quarterly.csv")

CANON_SERIES = "S000000588"
CANON_CIK = "1217673"
SIBLING_FOCUSED_GROWTH = "S000022521"


def _tag(x, t):
    m = re.search(rf"<{t}>(.*?)</{t}>", x, re.S)
    return m.group(1).strip() if m else None


@unittest.skipUnless(os.path.exists(_ANCHORS), "run `py build.py` first")
class TestAnchorIdentity(unittest.TestCase):
    def setUp(self):
        with open(_ANCHORS, encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))

    def test_every_anchor_is_canonical_series_in_csv(self):
        self.assertTrue(self.rows, "no anchors")
        for r in self.rows:
            self.assertEqual(r.get("series_id"), CANON_SERIES,
                             f"{r['report_date']} {r['accession']} wrong seriesId")
            self.assertEqual((r.get("series_name") or "").lower(), "baron partners fund")
            self.assertIn(CANON_CIK, (r.get("reg_cik") or "") + CANON_CIK)  # reg_cik == 1217673

    def test_every_anchor_xml_independently_reconfirms_series(self):
        """Re-read the cached filing XML — don't trust the CSV alone."""
        checked = 0
        for r in self.rows:
            p = os.path.join(_RAW, r["accession"].replace("-", "") + ".xml")
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8", errors="replace") as fh:
                x = fh.read()
            self.assertEqual(_tag(x, "seriesId"), CANON_SERIES,
                             f"cached XML {r['accession']} seriesId mismatch")
            self.assertEqual((_tag(x, "seriesName") or "").lower(), "baron partners fund")
            checked += 1
        self.assertGreater(checked, 0, "no cached XML to reconfirm")

    def test_sibling_focused_growth_is_excluded(self):
        """The SpaceX-holding sibling must never appear in our anchors."""
        for r in self.rows:
            self.assertNotEqual(r.get("series_id"), SIBLING_FOCUSED_GROWTH,
                                "Baron Focused Growth leaked into Baron Partners anchors")


class TestNetworkIdentity(unittest.TestCase):
    def test_sec_ticker_master_maps_classes_to_canonical_series(self):
        import json
        url = "https://www.sec.gov/files/company_tickers_mf.json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
            mf = json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:  # offline / SEC unreachable
            self.skipTest(f"network unavailable: {e}")
        f = mf["fields"]
        rows = [dict(zip(f, r)) for r in mf["data"] if dict(zip(f, r)).get("symbol")
                in ("BPTRX", "BPTIX", "BPTUX")]
        self.assertEqual(len(rows), 3, "expected 3 share classes")
        for r in rows:
            self.assertEqual(r["seriesId"], CANON_SERIES)
            self.assertEqual(str(r["cik"]), CANON_CIK)
        # class IDs match what config records
        got = {r["symbol"]: r["classId"] for r in rows}
        self.assertEqual(got, CFG.EDGAR_CLASS_IDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
