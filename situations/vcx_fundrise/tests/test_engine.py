"""VCX engine tests. Run: py -m unittest discover -s situations/vcx_fundrise/tests"""
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from situations.vcx_fundrise.engine import premium as P
from situations.vcx_fundrise.engine import scenarios as S


class TestPremium(unittest.TestCase):
    def setUp(self):
        self.price = [{"date": "2026-03-19", "price": 76.0},
                      {"date": "2026-03-20", "price": 100.0},
                      {"date": "2026-04-01", "price": 95.0}]
        self.nav = [{"date": "2025-12-31", "nav_per_share": 18.26, "confidence": "high"},
                    {"date": "2026-03-31", "nav_per_share": 19.0, "confidence": "med"}]

    def test_premium_uses_last_published_nav(self):
        s = P.build_premium_series(self.price, self.nav)
        by = {p["date"]: p for p in s}
        # 3/19 and 3/20 carry the 12/31 NAV (18.26)
        self.assertAlmostEqual(by["2026-03-20"]["premium"], 100.0 / 18.26 - 1, places=5)
        self.assertEqual(by["2026-03-20"]["source"], "nav_carried")
        # 4/01 carries the 3/31 NAV (19.0)
        self.assertAlmostEqual(by["2026-04-01"]["premium"], 95.0 / 19.0 - 1, places=5)

    def test_nav_age_increases(self):
        s = P.build_premium_series(self.price, self.nav)
        by = {p["date"]: p for p in s}
        self.assertEqual(by["2026-04-01"]["nav_age_days"], 1)   # 3/31 -> 4/01
        self.assertGreater(by["2026-03-20"]["nav_age_days"], 0)  # 12/31 -> 3/20

    def test_current_state_lookthrough(self):
        s = P.build_premium_series(self.price, self.nav)
        st = P.current_state(s, [{"name": "Anthropic", "weight": 0.2, "confidence": "med"}])
        self.assertEqual(st["as_of"], "2026-04-01")
        self.assertAlmostEqual(st["price_multiple"], 95.0 / 19.0, places=4)
        self.assertAlmostEqual(st["lookthrough"][0]["nav_value_per_share"], 19.0 * 0.2, places=4)


class TestScenarios(unittest.TestCase):
    def test_right_on_rerate_but_premium_collapses_loses(self):
        # price 100, nav 20 (premium +400%). Anthropic doubles NAV via 20% weight
        # = +20% NAV change. But premium normalizes to 0 -> price -> new_nav.
        nc = S.headline_nav_change(0.2, 500e9, 1000e9)  # +20% NAV
        self.assertAlmostEqual(nc, 0.2, places=6)
        r = S.scenario_return(price=100.0, nav=20.0, nav_change=nc, target_premium=0.0)
        self.assertAlmostEqual(r["new_nav"], 24.0, places=4)
        self.assertAlmostEqual(r["new_price"], 24.0, places=4)
        self.assertAlmostEqual(r["total_return"], 24.0 / 100.0 - 1, places=5)  # -76% despite +20% NAV
        self.assertLess(r["total_return"], 0)

    def test_premium_held_amplifies_rerate(self):
        r = S.scenario_return(price=100.0, nav=20.0, nav_change=0.2, target_premium=4.0)
        # premium stays +400%: new_price = 24 * 5 = 120 -> +20%
        self.assertAlmostEqual(r["new_price"], 120.0, places=4)
        self.assertAlmostEqual(r["total_return"], 0.2, places=5)

    def test_grid_shape(self):
        g = S.scenario_grid(100.0, 20.0, [0.0, 0.2], [0.0, 1.0, 4.0])
        self.assertEqual(len(g), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
