import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("paygap", os.path.join(UNIT, "scripts", "paygap.py"))
paygap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paygap)
ASSET = os.path.join(UNIT, "assets", "payroll_template.csv")


def person(ref, g, cat, base, var, hours):
    return (2, {"employee_ref": ref, "gender": g, "category": cat, "base_pay_annual": str(base),
                "variable_pay_annual": str(var), "hours_per_week": str(hours), "fte": ""})


class TestFormulas(unittest.TestCase):
    def test_hourly_normalisation_part_time(self):
        # A part-timer on 30 h with 312,000 earns the same hourly as a full-timer on 37 h with 384,800
        people, _, _ = paygap.load([person("A", "M", "X", 384800, 0, 37), person("B", "K", "X", 312000, 0, 30)], ",")
        self.assertAlmostEqual(people[0]["hourly_base"], 200.0)
        self.assertAlmostEqual(people[1]["hourly_base"], 200.0)
        rep = paygap.analyse(people, min_group=1)
        self.assertAlmostEqual(rep["overall"]["gaps"]["hourly_base_mean"], 0.0)

    def test_gap_formula_and_flag(self):
        rows = [person("M%d" % i, "M", "Sales", 52 * 37 * 200, 52 * 37 * 20, 37) for i in range(5)]
        rows += [person("W%d" % i, "K", "Sales", 52 * 37 * 188, 0, 37) for i in range(5)]
        people, _, _ = paygap.load(rows, ",")
        rep = paygap.analyse(people, min_group=5, threshold=5)
        cat = rep["categories"][0]
        self.assertAlmostEqual(cat["gaps"]["hourly_base_mean"], 6.0)          # (200 - 188) / 200
        self.assertAlmostEqual(cat["gaps"]["hourly_total_mean"], 100 * (220 - 188) / 220)
        self.assertEqual(len(cat["flags"]), 2)
        self.assertEqual(rep["overall"]["men"]["variable_share"], 100.0)
        self.assertEqual(rep["overall"]["women"]["variable_share"], 0.0)

    def test_suppression(self):
        rows = [person("M%d" % i, "M", "Ops", 400000, 0, 37) for i in range(6)]
        rows += [person("W%d" % i, "F", "Ops", 300000, 0, 37) for i in range(4)]
        people, _, _ = paygap.load(rows, ",")
        rep = paygap.analyse(people, min_group=5)
        self.assertTrue(rep["categories"][0]["suppressed"])
        self.assertEqual(rep["categories"][0]["flags"], [])

    def test_quartiles(self):
        rows = [person("P%d" % i, "M" if i % 2 else "K", "X", 100000 * (i + 1), 0, 37) for i in range(8)]
        people, _, _ = paygap.load(rows, ",")
        q = paygap.quartiles(people, "total")
        self.assertEqual([x["n"] for x in q], [2, 2, 2, 2])
        self.assertEqual([(x["men"], x["women"]) for x in q], [(1, 1)] * 4)

    def test_danish_numbers(self):
        self.assertEqual(paygap.parse_number("412.000", ";"), 412000.0)
        self.assertEqual(paygap.parse_number("412.000,50", ";"), 412000.5)
        self.assertEqual(paygap.parse_number("DKK 1.234.567", ","), 1234567.0)


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        headers, rows, delim = paygap.read_csv(ASSET)
        people, warnings, _ = paygap.load(rows, delim)
        self.assertEqual(len(people), 19)
        rep = paygap.analyse(people)
        ks = [c for c in rep["categories"] if c["category"] == "Kundeservice"][0]
        men = 2120000 / 1924 / 5
        women = (1605000 / 1924 + 330000 / 1560) / 5
        self.assertAlmostEqual(ks["gaps"]["hourly_base_mean"], 100 * (men - women) / men)
        self.assertAlmostEqual(ks["gaps"]["hourly_base_mean"], 5.09, places=2)
        self.assertTrue(ks["flags"])
        self.assertTrue([c for c in rep["categories"] if c["category"] == "Ledelse"][0]["suppressed"])
        w = " ".join(warnings)
        self.assertIn("duplicate employee_ref S03", w)
        self.assertIn("S10: variable_pay_annual blank", w)

    def test_cli_json_hides_suppressed_and_missing_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            paygap.main([ASSET, "--json"])
        data = json.loads(buf.getvalue())
        led = [c for c in data["categories"] if c["category"] == "Ledelse"][0]
        self.assertEqual(led, {"category": "Ledelse", "suppressed": True})
        bad = os.path.join(HERE, "_bad.csv")
        with open(bad, "w") as fh:
            fh.write("id,gender,salary\n1,M,1\n")
        try:
            with self.assertRaises(SystemExit) as cm:
                paygap.main([bad])
            self.assertIn("employee_ref", str(cm.exception))
        finally:
            os.remove(bad)


if __name__ == "__main__":
    unittest.main()
