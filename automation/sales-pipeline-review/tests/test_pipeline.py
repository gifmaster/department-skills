import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("pipeline", os.path.join(UNIT, "scripts", "pipeline.py"))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
ASSET = os.path.join(UNIT, "assets", "pipeline_template.csv")
TODAY = date(2026, 11, 16)
Q4 = (date(2026, 10, 1), date(2026, 12, 31))


def deal(name, stage, amount, close, created="2026-09-01", activity="2026-11-10", next_step="Call", prob="", prev=""):
    return (2, {"deal": name, "owner": "Owner A", "stage": stage, "amount": str(amount), "close_date": close,
                "created_date": created, "last_activity_date": activity, "next_step": next_step,
                "probability": prob, "previous_close_date": prev})


class TestRules(unittest.TestCase):
    def test_coverage_and_closed_excluded(self):
        rows = [deal("W", "Closed Won", 200000, "2026-10-15"), deal("L", "Closed Lost", 999999, "2026-11-01"),
                deal("A", "Proposal", 300000, "2026-12-01"), deal("B", "Negotiation", 500000, "2026-12-15"),
                deal("C", "Proposal", 400000, "2027-01-15")]
        rep = pipeline.analyse(rows, ",", TODAY, *Q4, target=1000000)
        self.assertEqual(rep["won_in_period"], 200000)
        self.assertEqual(rep["remaining_target"], 800000)
        self.assertEqual(rep["open_in_period"], 800000)            # C is after the period, L is closed
        self.assertAlmostEqual(rep["coverage"], 1.0)
        self.assertAlmostEqual(rep["weighted_in_period"], 300000 * 0.4 + 500000 * 0.7)
        self.assertEqual(rep["open_after_period_amount"], 400000)

    def test_flags(self):
        rows = [deal("Past", "Proposal", 100, "2026-11-01", activity="2026-10-01", next_step="", prev="2026-10-15")]
        rep = pipeline.analyse(rows, ",", TODAY, *Q4, target=None, stale_days=14)
        flags = " ".join(rep["flagged"][0]["flags"])
        self.assertIn("close date in the past", flags)
        self.assertIn("no next step", flags)
        self.assertIn("stale: 46 days", flags)
        self.assertIn("close date pushed 17 days", flags)

    def test_probability_override_and_key_deals(self):
        rows = [deal("Big", "Discovery", 900, "2026-12-01", prob="50"), deal("Mid", "Proposal", 500, "2026-12-01"),
                deal("Small", "Proposal", 100, "2026-12-01", prob="0,9")]
        rep = pipeline.analyse(rows, ",", TODAY, *Q4, target=1200)
        self.assertAlmostEqual(rep["weighted_in_period"], 450 + 200 + 90)
        self.assertEqual([k["deal"] for k in rep["key_deals"]], ["Big", "Mid"])  # 900 + 500 covers 1,200

    def test_quarter_bounds(self):
        self.assertEqual(pipeline.quarter_bounds(date(2026, 11, 16)), Q4)
        self.assertEqual(pipeline.quarter_bounds(date(2026, 2, 3)), (date(2026, 1, 1), date(2026, 3, 31)))


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        headers, rows, delim = pipeline.read_csv(ASSET)
        rep = pipeline.analyse(rows, delim, TODAY, *Q4, target=4200000)
        self.assertEqual(rep["won_in_period"], 760000)
        self.assertEqual(rep["open_in_period"], 5820000)
        self.assertAlmostEqual(rep["weighted_in_period"], 2260000)  # Brandt overridden to 60%
        self.assertAlmostEqual(rep["coverage"], 5820000 / 3440000)
        w = " ".join(rep["warnings"])
        self.assertIn("duplicate deal 'Holm Medico", w)
        self.assertIn("Vejle Varme", w)
        fyn = [d for d in rep["flagged"] if d["deal"].startswith("Fyn")][0]
        self.assertIn("close date pushed 36 days", "; ".join(fyn["flags"]))

    def test_cli_json_and_missing_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            pipeline.main([ASSET, "--today", "2026-11-16", "--target", "4.200.000", "--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(data["target"], 4200000)
        bad = os.path.join(HERE, "_bad.csv")
        with open(bad, "w") as fh:
            fh.write("deal;owner;value\nA;B;1\n")
        try:
            with self.assertRaises(SystemExit) as cm:
                pipeline.main([bad, "--today", "2026-11-16"])
            self.assertIn("close_date", str(cm.exception))
        finally:
            os.remove(bad)


if __name__ == "__main__":
    unittest.main()
