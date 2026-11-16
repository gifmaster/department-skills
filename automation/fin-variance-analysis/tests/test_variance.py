import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("variance", os.path.join(ROOT, "scripts", "variance.py"))
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)


def ln(name, typ, b, a, bq=None, aq=None):
    return {"line": name, "type": typ, "budget": b, "actual": a, "budget_qty": bq, "actual_qty": aq, "row": 2}


class TestHandBuilt(unittest.TestCase):
    def test_fa_and_pct(self):
        res = va.analyse([ln("Sales", "revenue", 1000.0, 1200.0), ln("Rent", "cost", 500.0, 550.0)],
                         abs_threshold=100.0, pct_threshold=10.0, pct_floor=0.0)
        s, r = res["lines"]
        self.assertEqual((s["variance"], s["pct"], s["fa"]), (200.0, 20.0, "F"))
        self.assertEqual((r["variance"], r["pct"], r["fa"]), (50.0, 10.0, "A"))
        self.assertTrue(s["material"] and r["material"])  # rent: 10% and >= floor 0
        self.assertEqual(res["totals"]["result_variance"], 150.0)
        self.assertTrue(all(c["ok"] for c in res["checks"]))

    def test_negative_costs(self):
        res = va.analyse([ln("Sales", "revenue", 1000.0, 1000.0), ln("Rent", "cost", -500.0, -450.0)])
        self.assertEqual(res["cost_sign"], "negative")
        self.assertEqual(res["lines"][1]["fa"], "F")
        self.assertEqual(res["totals"]["result_variance"], 50.0)

    def test_price_volume(self):
        # budget 100 units at 10 = 1,000; actual 120 units at 9 = 1,080
        res = va.analyse([ln("Units", "revenue", 1000.0, 1080.0, 100.0, 120.0)])
        r = res["lines"][0]
        self.assertEqual(r["volume"], 200.0)   # (120 - 100) x 10
        self.assertEqual(r["price"], -120.0)   # (9 - 10) x 120
        self.assertEqual(r["volume"] + r["price"], r["variance"])

    def test_materiality_floor(self):
        res = va.analyse([ln("Small", "cost", 2000.0, 3000.0)], abs_threshold=50000.0, pct_threshold=10.0, pct_floor=10000.0)
        self.assertFalse(res["lines"][0]["material"])  # 50% but only 1,000

    def test_control_total_fail(self):
        res = va.analyse([ln("Sales", "revenue", 100.0, 100.0)], controls=[ln("Result", "total", 100.0, 90.0)])
        self.assertFalse(res["checks"][-1]["ok"])


class TestSample(unittest.TestCase):
    def test_sample(self):
        w = []
        lines, controls = va.load(os.path.join(ROOT, "assets", "budget_actual.csv"), w)
        self.assertTrue(any("Travel" in x and "missing" in x for x in w))
        res = va.analyse(lines, controls, abs_threshold=100000.0, pct_threshold=10.0, warnings=w)
        t = res["totals"]
        self.assertEqual(t["result_budget"], 3995000.0)
        self.assertEqual(t["result_actual"], 3317300.0)
        self.assertEqual(t["result_variance"], -677700.0)
        by = {r["line"]: r for r in res["lines"]}
        sp = by["Sales standard pumps"]
        # volume (4600 - 4000) x 2,500 = 1,500,000 ; price (2,420 - 2,500) x 4600 = -368,000
        self.assertEqual((sp["volume"], sp["price"]), (1500000.0, -368000.0))
        self.assertEqual(len(res["material"]), 8)
        # reported actual result 3,269,100 vs computed 3,317,300: the missing travel actual of 48,200
        failed = [c for c in res["checks"] if not c["ok"]]
        self.assertEqual(len(failed), 1)
        self.assertEqual(round(failed[0]["got"] - failed[0]["expected"], 2), 48200.0)

    def test_missing_column(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write("line,budget,actual\nA,1,2\n")
        with self.assertRaises(va.InputError) as cm:
            va.load(fh.name, [])
        self.assertIn("Expected columns: line, type, budget, actual", str(cm.exception))
        os.unlink(fh.name)


if __name__ == "__main__":
    unittest.main()
