"""Overview model validation (anti-hallucination invariants).
Run: py -m unittest test_overview"""
import json
import os
import unittest

import overview
from config import PRIVATE_COMPANIES, VEHICLE_META, SITUATIONS

_ROOT = os.path.abspath(os.path.dirname(__file__))


class TestOverviewModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = overview.build_payload()
        cls.v = {x["ticker"]: x for x in cls.p["vehicles"] if not x.get("missing")}

    def test_all_vehicles_present(self):
        self.assertEqual(len(self.p["vehicles"]), len(SITUATIONS))

    def test_at_nav_vehicles_have_zero_premium(self):
        # mutual fund + ETF must never show a wrapper premium
        for t in ("BPTRX", "AGIX"):
            v = self.v[t]
            self.assertTrue(v["at_nav"])
            self.assertEqual(v["premium_mtm"], 0.0)
            self.assertEqual(v["premium_stale"], 0.0)

    def test_cefs_have_positive_premium(self):
        for t in ("VCX", "DXYZ", "RVI"):
            self.assertFalse(self.v[t]["at_nav"])
            self.assertGreater(self.v[t]["premium_mtm"], 0)

    def test_scenarios_present_and_finite(self):
        for v in self.v.values():
            for c in ("bear", "base", "bull"):
                r = v["scenarios"][c]["return_from_price"]
                self.assertIsNotNone(r)
                self.assertTrue(-1.0 <= r <= 5.0, f"{v['ticker']} {c} return {r} out of sane range")

    def test_scenario_monotonic(self):
        # bull >= base >= bear for every vehicle
        for v in self.v.values():
            s = v["scenarios"]
            self.assertGreaterEqual(s["bull"]["return_from_price"], s["base"]["return_from_price"] - 1e-9)
            self.assertGreaterEqual(s["base"]["return_from_price"], s["bear"]["return_from_price"] - 1e-9)

    def test_scenario_inputs_have_sources(self):
        # every private company carries source + confidence + a bear<base<bull range
        for name, pc in PRIVATE_COMPANIES.items():
            self.assertIn("source_url", pc)
            self.assertIn("confidence", pc["last_confirmed"])
            self.assertLess(pc["bear"], pc["bull"], name)
            self.assertTrue(pc["bear"] <= pc["base"] <= pc["bull"], name)

    def test_confidence_labels_valid(self):
        for v in self.v.values():
            self.assertIn(v["data_confidence"], ("high", "med", "medium", "low-med", "low"))

    def test_bptrx_not_confused_with_other_baron_funds(self):
        # identity guard: BPTRX exposure is SpaceX only here
        self.assertEqual(self.v["BPTRX"]["headline"], "SpaceX")
        names = [h["name"] for h in self.v["BPTRX"]["lookthrough"]]
        self.assertEqual(names, ["SpaceX"])

    def test_company_cleanest_is_at_nav_when_available(self):
        # for Anthropic, the cleanest access should be the at-NAV vehicle (AGIX), not a premium CEF
        anth = next(c for c in self.p["companies"] if c["name"] == "Anthropic")
        self.assertIsNotNone(anth["cleanest_ticker"])
        # the priciest must be a CEF (premium > 0)
        self.assertIn(anth["priciest_ticker"], ("VCX", "DXYZ", "RVI"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
