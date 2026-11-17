import importlib.util
import os
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("sales_forecast", os.path.join(ROOT, "scripts", "sales_forecast.py"))
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)


def rows(*dicts):
    out = []
    for i, d in enumerate(dicts, start=2):
        d = dict(d)
        d["_line"] = i
        out.append(d)
    return out


class TestHelpers(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(sf.parse_number("1.234,56"), 1234.56)
        self.assertEqual(sf.parse_number("1234.56"), 1234.56)
        self.assertEqual(sf.parse_number("310.000,00"), 310000.0)
        self.assertEqual(sf.parse_number("1.200"), 1200.0)
        self.assertAlmostEqual(sf.parse_prob("35%"), 0.35)
        self.assertAlmostEqual(sf.parse_prob("0,6"), 0.6)

    def test_dates(self):
        self.assertEqual(sf.parse_date("15-12-2026"), date(2026, 12, 15))
        self.assertEqual(sf.parse_date("2026-12-15"), date(2026, 12, 15))
        self.assertEqual(sf.quarter_bounds(date(2026, 11, 16)), (date(2026, 10, 1), date(2026, 12, 31)))


class TestSmallCase(unittest.TestCase):
    def test_hand_case(self):
        stages = sf.parse_stage_defaults("Proposal=0.4,Negotiation=0.6")
        pipe = rows(
            {"deal": "A", "stage": "Proposal", "amount": "100000", "close_date": "2026-12-01", "rep_commit": "yes"},
            {"deal": "B", "stage": "Negotiation", "amount": "200000", "close_date": "2026-12-01", "rep_commit": "no", "probability": "50"},
            {"deal": "C", "stage": "Negotiation", "amount": "500000", "close_date": "2027-01-15", "rep_commit": "yes"},
        )
        # history: 4 deals reached Proposal (1 won), 2 of them reached Negotiation (1 won)
        hist = rows(
            {"deal": "h1", "stage_reached": "Negotiation", "won": "yes", "amount": "1", "cycle_days": "60"},
            {"deal": "h2", "stage_reached": "Negotiation", "won": "no", "amount": "1", "cycle_days": "50"},
            {"deal": "h3", "stage_reached": "Proposal", "won": "no", "amount": "1", "cycle_days": "40"},
            {"deal": "h4", "stage_reached": "Proposal", "won": "no", "amount": "1", "cycle_days": "30"},
        )
        r = sf.forecast(pipe, hist, date(2026, 10, 1), date(2026, 12, 31), date(2026, 11, 16), stages,
                        min_sample=2, closed_won=50000)
        self.assertAlmostEqual(r["rates"]["Proposal"]["rate"], 0.25)
        self.assertAlmostEqual(r["rates"]["Negotiation"]["rate"], 0.5)
        m = r["methods"]
        self.assertAlmostEqual(m["weighted_pipeline"], 100000 * 0.4 + 200000 * 0.5)  # 140,000
        self.assertAlmostEqual(m["historical_conversion"], 100000 * 0.25 + 200000 * 0.5)  # 125,000
        self.assertAlmostEqual(m["rep_commit_face_value"], 100000)
        self.assertAlmostEqual(m["rep_commit_risk_adjusted"], 25000)
        s = r["scenarios"]
        self.assertAlmostEqual(s["commit"], 75000)
        self.assertAlmostEqual(s["most_likely"], 175000)
        self.assertAlmostEqual(s["best_case"], 190000)
        self.assertEqual(r["excluded"]["outside_period"], 1)

    def test_fallback_when_sample_small(self):
        stages = sf.parse_stage_defaults("Proposal=0.4")
        hist = rows({"deal": "h1", "stage_reached": "Proposal", "won": "yes", "amount": "1", "cycle_days": "10"})
        r = sf.forecast(rows({"deal": "A", "stage": "Proposal", "amount": "1000", "close_date": "2026-11-20"}),
                        hist, date(2026, 10, 1), date(2026, 12, 31), date(2026, 11, 16), stages, min_sample=5)
        self.assertAlmostEqual(r["rates"]["Proposal"]["rate"], 0.4)
        self.assertIn("stage default", r["rates"]["Proposal"]["source"])


class TestClosedWonAndStageRates(unittest.TestCase):
    PIPE = (
        {"deal": "W", "stage": "Closed won", "amount": "150000", "close_date": "2026-10-20"},
        {"deal": "A", "stage": "Proposal", "amount": "100000", "close_date": "2026-12-01", "rep_commit": "no"},
    )

    def run_case(self, **kw):
        stages = sf.parse_stage_defaults("Proposal=0.4,Negotiation=0.6")
        return sf.forecast(rows(*self.PIPE), None, date(2026, 10, 1), date(2026, 12, 31), date(2026, 11, 16),
                           stages, **kw)

    def test_double_counting_warned_and_not_summed(self):
        r = self.run_case(closed_won=200000)
        self.assertEqual(r["closed_won"], 150000)               # file rows used, not 350,000
        w = [x for x in r["warnings"] if "double counting" in x]
        self.assertEqual(len(w), 1)
        self.assertIn("difference 50,000", w[0])
        self.assertAlmostEqual(r["scenarios"]["most_likely"], 150000 + 100000 * 0.4)
        self.assertEqual(self.run_case(closed_won=200000, closed_won_basis="argument")["closed_won"], 200000)
        self.assertEqual(self.run_case(closed_won=200000, closed_won_basis="sum")["closed_won"], 350000)

    def test_no_warning_when_only_one_source(self):
        r = self.run_case()
        self.assertEqual(r["closed_won"], 150000)
        self.assertFalse(any("double counting" in x for x in r["warnings"]))

    def test_user_supplied_stage_rates(self):
        r = self.run_case(stage_rates=sf.parse_stage_defaults("Proposal=0.3"))
        self.assertAlmostEqual(r["rates"]["Proposal"]["rate"], 0.3)
        self.assertEqual(r["rates"]["Proposal"]["source"], "historical (user supplied)")
        self.assertEqual(r["rates"]["Negotiation"]["source"], "stage default (no history)")
        self.assertAlmostEqual(r["methods"]["historical_conversion"], 30000)
        self.assertIn("historical (user supplied)", sf.render(r))
        with self.assertRaises(ValueError):
            self.run_case(stage_rates={"Unknown": 0.5})


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        _, p = sf.read_csv(os.path.join(ROOT, "assets", "pipeline_template.csv"), ["deal", "stage", "amount", "close_date"])
        _, h = sf.read_csv(os.path.join(ROOT, "assets", "history_template.csv"),
                           ["deal", "stage_reached", "won", "amount", "cycle_days"])
        r = sf.forecast(p, h, date(2026, 10, 1), date(2026, 12, 31), date(2026, 11, 16))
        self.assertEqual(r["open_deals_in_period"], 8)
        self.assertAlmostEqual(r["rates"]["Negotiation"]["rate"], 4 / 9)
        self.assertAlmostEqual(r["rates"]["Proposal"]["rate"], 4 / 14)
        self.assertAlmostEqual(r["methods"]["weighted_pipeline"], 1502250)
        self.assertAlmostEqual(r["methods"]["rep_commit_face_value"], 1820000)
        self.assertAlmostEqual(r["methods"]["historical_conversion"], 1264610.65, places=1)
        self.assertAlmostEqual(r["closed_won"], 150000)
        self.assertAlmostEqual(r["scenarios"]["best_case"], 1970000)
        w = " ".join(r["warnings"])
        self.assertIn("duplicate", w)
        self.assertIn("amount missing", w)

    def test_missing_column(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("deal;stage;value\nA;Proposal;100\n")
        with self.assertRaises(ValueError) as cm:
            sf.read_csv(fh.name, ["deal", "stage", "amount", "close_date"])
        os.unlink(fh.name)
        self.assertIn("Expected columns", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
