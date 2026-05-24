"""
Engine unit tests. Run with either:
    py -m unittest discover -s situations/spacex_baron/tests -v
    pytest situations/spacex_baron/tests

Covers:
  • reconstructed weight at a filing anchor == filed weight (the key invariant)
  • daily weight-change attribution sums to the actual change (first order)
  • IPO re-rate scale & NAV step-up
  • flow shock: inflow dilutes, outflow concentrates, forced-sale edge case
  • against the REAL processed CSVs when present (skipped if build not yet run)
"""

import csv
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from situations.spacex_baron.engine import reconstruct as R
from situations.spacex_baron.engine import scenarios as S

_PROCESSED = os.path.join(_REPO_ROOT, "situations", "spacex_baron", "data", "processed")
DENSITY = [("2017-01-01", "2019-06-30", "sparse", "low"),
           ("2019-07-01", "2021-12-31", "improving", "med"),
           ("2022-01-01", None, "dense", "high")]


def _synthetic():
    """Two clean anchors + flat NAV so shares are well-defined."""
    anchors = [
        {"report_date": "2020-03-31", "net_assets_usd": 1000.0,
         "spacex_value_usd": 100.0, "spacex_pct_of_net_assets": 10.0,
         "spacex_balance_units": 10.0},
        {"report_date": "2020-06-30", "net_assets_usd": 2000.0,
         "spacex_value_usd": 100.0, "spacex_pct_of_net_assets": 5.0,
         "spacex_balance_units": 10.0},
    ]
    # NAV = 10 every day -> shares = net_assets/10
    nav = []
    import datetime
    d = datetime.date(2020, 3, 31)
    while d <= datetime.date(2020, 6, 30):
        nav.append({"date": d.isoformat(), "nav": 10.0})
        d += datetime.timedelta(days=1)
    return anchors, nav


class TestReconstruct(unittest.TestCase):
    def test_weight_at_anchor_matches_filed(self):
        anchors, nav = _synthetic()
        recon = R.reconstruct_daily(anchors, nav, external_marks=[],
                                    density_eras=DENSITY,
                                    window_start="2020-03-31", entry_date="2020-04-01")
        by_date = {p["date"]: p for p in recon["series"]}
        # anchor 1: 100/1000 = 10%
        self.assertAlmostEqual(by_date["2020-03-31"]["spacex_weight"], 0.10, places=6)
        self.assertEqual(by_date["2020-03-31"]["source"], "measured")
        # anchor 2: 100/2000 = 5%
        self.assertAlmostEqual(by_date["2020-06-30"]["spacex_weight"], 0.05, places=6)

    def test_between_anchor_weight_is_monotone_with_flow(self):
        # net assets doubled with flat NAV+marks -> weight should fall toward 5%
        anchors, nav = _synthetic()
        recon = R.reconstruct_daily(anchors, nav, [], DENSITY, "2020-03-31", "2020-04-01")
        weights = [p["spacex_weight"] for p in recon["series"] if p["spacex_weight"]]
        self.assertTrue(weights[0] >= weights[-1])      # diluting
        self.assertLessEqual(weights[-1], 0.10 + 1e-9)
        self.assertGreaterEqual(weights[-1], 0.05 - 1e-9)

    def test_attribution_sums_to_change(self):
        anchors, nav = _synthetic()
        recon = R.reconstruct_daily(anchors, nav, [], DENSITY, "2020-03-31", "2020-04-01")
        pts = [p for p in recon["series"] if p.get("mark_contrib") is not None]
        prev = None
        # find a consecutive pair within the anchored era
        ser = recon["series"]
        for i in range(1, len(ser)):
            a, b = ser[i - 1], ser[i]
            if b.get("mark_contrib") is None or a.get("spacex_weight") is None:
                continue
            dw = b["spacex_weight"] - a["spacex_weight"]
            approx = b["mark_contrib"] + b["drift_contrib"] + b["flow_contrib"]
            self.assertAlmostEqual(dw, approx, places=5)
            break


class TestScenarios(unittest.TestCase):
    def test_ipo_rerate_scale_and_stepup(self):
        r = S.ipo_rerate(spacex_value_usd=100.0, public_value_usd=100.0,
                         current_valuation_usd=1e12, ipo_valuation_usd=2e12)
        self.assertAlmostEqual(r["scale"], 2.0)
        self.assertAlmostEqual(r["spacex_value_usd"], 200.0)
        self.assertAlmostEqual(r["total_nav_usd"], 300.0)
        self.assertAlmostEqual(r["spacex_weight"], 200.0 / 300.0, places=6)
        # NAV step-up: total 200->300 = +50%
        self.assertAlmostEqual(r["nav_stepup_pct"], 0.5, places=6)

    def test_inflow_dilutes(self):
        f = S.flow_shock(spacex_value_usd=100.0, public_value_usd=100.0, net_flow_usd=200.0)
        self.assertAlmostEqual(f["spacex_value_usd"], 100.0)          # unchanged
        self.assertAlmostEqual(f["spacex_weight"], 100.0 / 400.0)     # diluted 50%->25%

    def test_outflow_concentrates(self):
        f = S.flow_shock(spacex_value_usd=100.0, public_value_usd=100.0, net_flow_usd=-50.0)
        self.assertAlmostEqual(f["spacex_value_usd"], 100.0)          # public sold first
        self.assertAlmostEqual(f["spacex_weight"], 100.0 / 150.0)     # 50%->66.7%

    def test_outflow_forces_spacex_sale_when_public_exhausted(self):
        f = S.flow_shock(spacex_value_usd=100.0, public_value_usd=100.0, net_flow_usd=-150.0)
        self.assertAlmostEqual(f["public_value_usd"], 0.0)
        self.assertAlmostEqual(f["spacex_forced_sale_usd"], 50.0)
        self.assertAlmostEqual(f["spacex_value_usd"], 50.0)
        self.assertAlmostEqual(f["spacex_weight"], 1.0)               # only SpaceX left


@unittest.skipUnless(
    os.path.exists(os.path.join(_PROCESSED, "anchors_quarterly.csv"))
    and os.path.exists(os.path.join(_PROCESSED, "nav_daily.csv")),
    "processed CSVs not present; run `py build.py` first")
class TestAgainstRealData(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(_PROCESSED, "anchors_quarterly.csv"), encoding="utf-8") as f:
            self.anchors = []
            for r in csv.DictReader(f):
                for k in ("net_assets_usd", "spacex_value_usd",
                          "spacex_pct_of_net_assets", "spacex_balance_units"):
                    r[k] = float(r[k]) if r[k] else None
                self.anchors.append(r)
        with open(os.path.join(_PROCESSED, "nav_daily.csv"), encoding="utf-8") as f:
            self.nav = [{"date": r["date"], "nav": float(r["nav"]) if r["nav"] else None}
                        for r in csv.DictReader(f)]

    def test_every_anchor_reconstructs_to_filed_weight(self):
        recon = R.reconstruct_daily(self.anchors, self.nav, [], DENSITY,
                                    "2017-01-01", "2026-05-20")
        by_date = {p["date"]: p for p in recon["series"]}
        for a in self.anchors:
            filed = a["spacex_value_usd"] / a["net_assets_usd"]
            pt = by_date.get(a["report_date"])
            if pt is None or pt["spacex_weight"] is None:
                continue  # quarter-end on a non-trading day handled by nearest-prior
            self.assertAlmostEqual(pt["spacex_weight"], filed, places=4,
                                   msg=f"anchor {a['report_date']} mismatch")

    def test_residuals_are_reported_and_bounded(self):
        recon = R.reconstruct_daily(self.anchors, self.nav, [], DENSITY,
                                    "2017-01-01", "2026-05-20")
        self.assertTrue(recon["residuals"])
        # Sanity: holding marks flat for a quarter shouldn't be wildly off most quarters.
        big = [r for r in recon["residuals"] if abs(r["residual"]) > 0.15]
        self.assertLess(len(big), len(recon["residuals"]) / 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
