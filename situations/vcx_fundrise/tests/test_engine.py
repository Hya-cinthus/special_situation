"""VCX engine tests. Run: py -m unittest discover -s situations/vcx_fundrise/tests"""
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
from situations.vcx_fundrise.engine import premium as P
from situations.vcx_fundrise.engine import scenarios as S
from situations.vcx_fundrise.engine import nav_markto as M


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


class TestMarkToMarket(unittest.TestCase):
    def setUp(self):
        self.tl = {
            "Anthropic": [("2025-09-01", 183e9, "F", "u"), ("2026-02-12", 380e9, "G", "u"),
                          ("2026-05-28", 965e9, "H", "u")],
            "OpenAI": [("2025-10-01", 500e9, "tender", "u"), ("2026-03-31", 852e9, "round", "u")],
        }
        self.lt = [{"name": "Anthropic", "weight": 0.2, "confidence": "med"},
                   {"name": "OpenAI", "weight": 0.1, "confidence": "med"}]

    def test_valuation_step_lookup(self):
        self.assertEqual(M.valuation_at(self.tl["Anthropic"], "2026-01-01"), 183e9)
        self.assertEqual(M.valuation_at(self.tl["Anthropic"], "2026-03-01"), 380e9)
        self.assertEqual(M.valuation_at(self.tl["Anthropic"], "2026-06-01"), 965e9)
        self.assertIsNone(M.valuation_at(self.tl["Anthropic"], "2025-01-01"))

    def test_nav_mtm_remarks_up(self):
        # base 12/31/2025: Anthropic $183B, OpenAI $500B; NAV0=$18.26
        # as of 6/1/2026: Anthropic $965B (5.27x), OpenAI $852B (1.70x)
        nav = M.nav_mtm_at(self.lt, self.tl, "2025-12-31", 18.26, "2026-06-01")
        # mult = .2*965/183 + .1*852/500 + .7(other flat) = 1.0546+0.1704+0.7 = 1.925
        self.assertAlmostEqual(nav, 18.26 * (0.2*965/183 + 0.1*852/500 + 0.7), places=2)
        self.assertGreater(nav, 18.26)   # re-marked up

    def test_holding_marks_growth(self):
        rows = M.holding_marks(self.lt, self.tl, "2025-12-31", "2026-06-01")
        anth = next(r for r in rows if r["name"] == "Anthropic")
        self.assertAlmostEqual(anth["growth_mult"], 965e9/183e9, places=3)
        self.assertEqual(anth["base_valuation_usd"], 183e9)
        self.assertEqual(anth["cur_valuation_usd"], 965e9)

    def test_mtm_premium_lower_than_stale(self):
        price = [{"date": "2026-06-01", "price": 219.59}]
        s = M.build_mtm_series(price, self.lt, self.tl, "2025-12-31", 18.26)
        mtm_prem = s[0]["premium_mtm"]
        stale_prem = 219.59 / 18.26 - 1
        self.assertLess(mtm_prem, stale_prem)   # re-marking NAV up shrinks the premium


if __name__ == "__main__":
    unittest.main(verbosity=2)
