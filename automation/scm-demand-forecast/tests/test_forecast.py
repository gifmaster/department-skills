import importlib.util
import io
import math
import os
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("forecast", os.path.join(UNIT, "scripts", "forecast.py"))
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)
ASSET = os.path.join(UNIT, "assets", "demand_history.csv")


def write_tmp(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


class TestModels(unittest.TestCase):
    def test_moving_average(self):
        f, p = fc.ma_forecast([10, 20, 30, 40], [False] * 4, 2, 3)
        self.assertEqual(f, [30, 30])

    def test_ses_fixed_alpha(self):
        # level 10 -> 0.5*20 + 0.5*10 = 15 -> 0.5*30 + 0.5*15 = 22.5
        f, p = fc.ses_forecast([10, 20, 30], [False] * 3, 1, [0.5])
        self.assertAlmostEqual(f[0], 22.5)

    def test_stockout_excluded(self):
        excl = [False, True, False]
        self.assertAlmostEqual(fc.ses_forecast([10, 100, 20], excl, 1, [0.5])[0][0], 15)
        self.assertAlmostEqual(fc.ma_forecast([10, 100, 20], excl, 1, 3)[0][0], 15)

    def test_accuracy(self):
        acc = fc.accuracy([100, 50], [90, 70], [False, False])
        self.assertAlmostEqual(acc["wape"], 0.2)
        self.assertAlmostEqual(acc["mape"], 0.25)
        self.assertAlmostEqual(acc["bias"], 10 / 150)
        acc = fc.accuracy([100, 50, 999], [90, 70, 0], [False, False, True])
        self.assertAlmostEqual(acc["wape"], 0.2)

    def test_period_helpers(self):
        self.assertEqual(fc.add_months("2026-11", 3), "2027-02")
        self.assertEqual(fc.norm_period("2026-3"), "2026-03")
        self.assertEqual(fc.norm_period("15-03-2026"), "2026-03")


class TestHoltWinters(unittest.TestCase):
    def test_seasonal_series_selects_hw(self):
        pattern = [-30, -25, -10, 10, 40, 60, 50, 20, 0, -20, -40, -55]
        lines = ["item;period;quantity;stockout"]
        for t in range(36):
            per = fc.add_months("2024-01", t)
            q = 200 + 2 * t + pattern[t % 12]
            lines.append("S1;%s;%s;%s" % (per, str(q).replace(".", ","), "nej"))
        res = fc.compute(fc.read_table(write_tmp("\n".join(lines) + "\n"), fc.REQUIRED, fc.OPTIONAL),
                         horizon=12, holdout=3)
        item = res["items"][0]
        self.assertIn("HW", item["tests"])
        self.assertEqual(item["method"], "HW")
        self.assertLess(item["wape"], 0.03)
        # next January: 200 + 2*36 - 30 = 242
        self.assertAlmostEqual(item["forecast"][0], 242, delta=8)

    def test_hw_not_used_below_minimum(self):
        lines = ["item,period,quantity"] + ["S2,%s,%d" % (fc.add_months("2025-01", t), 50 + t) for t in range(20)]
        res = fc.compute(fc.read_table(write_tmp("\n".join(lines) + "\n"), fc.REQUIRED, fc.OPTIONAL))
        self.assertNotIn("HW", res["items"][0]["tests"])


class TestAsset(unittest.TestCase):
    def setUp(self):
        self.res = fc.compute(fc.read_table(ASSET, fc.REQUIRED, fc.OPTIONAL))
        self.by = {i["item"]: i for i in self.res["items"]}

    def test_quality_warnings(self):
        w = " ".join(self.res["warnings"])
        self.assertIn("duplicate row", w)
        self.assertIn("2026-07, treated as missing", w)
        pa = self.by["PA-120 Parasol 3m grey"]
        self.assertEqual(pa["history"], [38, 44, None, 41, 36, 35])
        self.assertEqual(pa["missing_periods"], ["2026-07"])
        # 6 periods: too short for rolling origin (3 < min-train 6), single hold-out on Aug to Oct.
        # MA fitted on May 38, Jun 44 (Jul missing, not zero) = 41
        self.assertEqual(pa["evaluation"], "single")
        self.assertAlmostEqual(pa["tests"]["MA"]["forecast"][0], 41.0)
        self.assertTrue(any("missing month" in r for r in pa["review"]))

    def test_fill_zero_restores_zero_month(self):
        res = fc.compute(fc.read_table(ASSET, fc.REQUIRED, fc.OPTIONAL), fill_zero=True)
        pa = {i["item"]: i for i in res["items"]}["PA-120 Parasol 3m grey"]
        self.assertEqual(pa["history"], [38, 44, 0, 41, 36, 35])
        self.assertEqual(pa["zero_filled_periods"], ["2026-07"])
        # MA on May 38, Jun 44, Jul 0 = 27.33
        self.assertAlmostEqual(pa["tests"]["MA"]["forecast"][0], 82 / 3)
        self.assertIn("filled with 0 (--fill-zero)", " ".join(res["warnings"]))

    def test_blank_quantity_is_missing(self):
        text = "item,period,quantity\nB,2026-01,10\nB,2026-02,\nB,2026-03,20\nB,2026-04,30\n"
        res = fc.compute(fc.read_table(write_tmp(text), fc.REQUIRED, fc.OPTIONAL), holdout=0)
        self.assertEqual(res["items"][0]["missing_periods"], ["2026-02"])
        self.assertEqual(res["items"][0]["history"], [10, None, 20, 30])
        # the forecast equals SES on the valid months 10, 20, 30 only; a zero would pull it down
        alphas = [round(0.1 * k, 1) for k in range(1, 10)]
        expected = fc.ses_forecast([10, 20, 30], [False] * 3, 1, alphas)[0][0]
        self.assertAlmostEqual(res["items"][0]["forecast"][0], expected)

    def test_lounge_set(self):
        ls = self.by["LS-400 Lounge set Fano"]
        self.assertEqual(ls["stockout_periods"], ["2026-05"])
        self.assertEqual(ls["evaluation"], "rolling")
        # Rolling origin, 3 origins. MA one-step forecasts: Apr 430, Jun 540, Jul 298 (May excluded) = 422.67;
        # Jun, Jul, Aug = 336.33; Jul, Aug, Sep = 178.33.
        self.assertAlmostEqual(ls["tests"]["MA"]["forecast"][0], 1268 / 3)
        self.assertAlmostEqual(ls["tests"]["MA"]["forecast"][2], 535 / 3)
        # pooled pairs: origin Aug forecasts Aug, Sep, Oct; origin Sep forecasts Sep, Oct; origin Oct forecasts Oct
        f1, f2, f3 = 1268 / 3, 1009 / 3, 535 / 3
        errs = [abs(171 - f1), abs(66 - f1), abs(58 - f1), abs(66 - f2), abs(58 - f2), abs(58 - f3)]
        self.assertEqual(ls["tests"]["MA"]["n"], 6)
        self.assertAlmostEqual(ls["tests"]["MA"]["wape"], sum(errs) / (171 + 66 + 58 + 66 + 58 + 58))
        self.assertEqual(ls["method"], "SES")
        self.assertEqual(ls["same_periods_last_year_total"], 988)
        self.assertTrue(any("last year" in r for r in ls["review"]))

    def test_cli_json_and_csv(self):
        out = os.path.join(tempfile.mkdtemp(), "o.csv")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = fc.main([ASSET, "--json", "--out", out])
        self.assertEqual(rc, 0)
        import json
        data = json.loads(buf.getvalue())
        self.assertEqual(len(data["items"]), 2)
        with open(out, encoding="utf-8") as fh:
            rows = list(__import__("csv").reader(fh))
        self.assertEqual(sum(1 for r in rows[1:] if r[2] == "forecast"), 12)

    def test_missing_column(self):
        with self.assertRaises(fc.InputError) as ctx:
            fc.read_table(write_tmp("item,month,qty\n"), fc.REQUIRED, fc.OPTIONAL)
        self.assertIn("Expected columns: item, period, quantity", str(ctx.exception))


class TestEvaluation(unittest.TestCase):
    def test_rolling_vs_single_and_holdout_limit(self):
        y = [10.0, 12, 14, 16, 18, 20, 22, 24, 26]
        mode, tests = fc.evaluate(y, [False] * 9, ["MA"], 3, 6, {"ma_window": 1}, min_train=6)
        # MA(1) = last value: origins 6, 7, 8 -> forecasts 20 (for 22, 24, 26), 22 (24, 26), 24 (26)
        self.assertEqual(mode, "rolling")
        self.assertEqual(tests["MA"]["forecast"], [20, 22, 24])
        self.assertAlmostEqual(tests["MA"]["wape"], (2 + 4 + 6 + 2 + 4 + 2) / (22 + 24 + 26 + 24 + 26 + 26))
        mode, tests = fc.evaluate(y, [False] * 9, ["MA"], 3, 6, {"ma_window": 1}, min_train=7)
        self.assertEqual(mode, "single")
        self.assertAlmostEqual(tests["MA"]["wape"], (2 + 4 + 6) / 72)
        # horizon 1 limits each origin to one step
        mode, tests = fc.evaluate(y, [False] * 9, ["MA"], 3, 1, {"ma_window": 1}, min_train=6)
        self.assertEqual(tests["MA"]["n"], 3)
        from contextlib import redirect_stderr
        with redirect_stderr(io.StringIO()):
            self.assertEqual(fc.main([ASSET, "--holdout", "13"]), 2)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(fc.main([ASSET, "--holdout", "12"]), 0)


if __name__ == "__main__":
    unittest.main()
