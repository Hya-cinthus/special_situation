"""DXYZ emit smoke test. The premium/MTM math is covered by the VCX engine tests
(shared modules); here we just confirm the DXYZ payload builds sanely."""
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_PRICE = os.path.join(_REPO_ROOT, "situations", "dxyz_destiny", "data", "processed", "price_daily.csv")


@unittest.skipUnless(os.path.exists(_PRICE), "run `py build.py dxyz_destiny` first")
class TestDxyzEmit(unittest.TestCase):
    def test_payload_builds(self):
        from situations.dxyz_destiny import emit
        p = emit.build_payload()
        k = p["kpis"]
        self.assertGreater(k["price"], 0)
        self.assertGreater(k["nav"], 0)
        # premium = price/nav - 1
        self.assertAlmostEqual(k["premium"], k["price"] / k["nav"] - 1, places=4)
        # marking NAV up (holdings re-rated) must SHRINK the premium vs stale
        self.assertLessEqual(k["premium_mtm"], k["premium"] + 1e-9)
        self.assertGreaterEqual(k["nav_mtm"], k["nav"] - 1e-9)
        # holding marks present for the disclosed names
        names = {h["name"] for h in p["holding_marks"]}
        self.assertIn("SpaceX", names)
        self.assertTrue(len(p["series"]) > 50)

    def test_lookthrough_flagged_low_confidence(self):
        from config import DxyzDestiny as CFG
        # OpenAI/Anthropic look-through must be flagged (not SEC-verifiable)
        for l in CFG.LOOKTHROUGH:
            if l["name"] in ("OpenAI", "Anthropic"):
                self.assertIn(l["confidence"], ("low", "med"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
