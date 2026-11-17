import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("abcxyz", os.path.join(UNIT, "scripts", "abcxyz.py"))
ax = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ax)
ASSET = os.path.join(UNIT, "assets", "abcxyz_consumption.csv")


def write_tmp(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


def hand_case():
    lines = ["item,period,quantity,unit_value"]
    for m in range(1, 13):
        per = "2026-%02d" % m
        lines.append("P1,%s,10,100" % per)                       # value 12,000, CoV 0
        lines.append("P2,%s,%d,30" % (per, 0 if m % 2 else 20))  # mean 10, SD 10, CoV 1.0
        lines.append("P3,%s,%d,20" % (per, 5 if m % 2 else 15))  # mean 10, SD 5, CoV 0.5
        lines.append("P4,%s,1,50" % per)                          # value 600
    return write_tmp("\n".join(lines) + "\n")


class TestHandCase(unittest.TestCase):
    def setUp(self):
        self.res = ax.compute(ax.read_table(hand_case(), ax.REQUIRED))
        self.by = {r["item"]: r for r in self.res["items"]}

    def test_abc(self):
        # total 18,600: P1 64.5 % -> A, P2 cum 83.9 % -> B, P3 cum 96.8 % -> C, P4 -> C
        self.assertAlmostEqual(self.res["total_value"], 18600)
        self.assertEqual(self.by["P1"]["abc"], "A")
        self.assertAlmostEqual(self.by["P2"]["cum_share"], 15600 / 18600)
        self.assertEqual(self.by["P2"]["abc"], "B")
        self.assertEqual(self.by["P3"]["abc"], "C")
        self.assertEqual(self.by["P4"]["abc"], "C")

    def test_xyz_boundaries_and_pattern(self):
        self.assertEqual(self.by["P1"]["xyz"], "X")
        self.assertAlmostEqual(self.by["P3"]["cov"], 0.5)
        self.assertEqual(self.by["P3"]["xyz"], "Y")   # 0.5 is not below 0.5
        self.assertAlmostEqual(self.by["P2"]["cov"], 1.0)
        self.assertEqual(self.by["P2"]["xyz"], "Z")
        self.assertEqual(self.by["P2"]["pattern"], "intermittent")
        self.assertAlmostEqual(self.by["P2"]["zero_share"], 0.5)

    def test_nine_box(self):
        box = self.res["nine_box"]
        self.assertEqual(box["AX"]["count"], 1)
        self.assertEqual(box["CX"]["count"], 1)
        self.assertAlmostEqual(box["BZ"]["value"], 3600)

    def test_custom_thresholds(self):
        res = ax.compute(ax.read_table(hand_case(), ax.REQUIRED), a=0.9, b=0.97)
        by = {r["item"]: r["abc"] for r in res["items"]}
        self.assertEqual(by["P2"], "A")
        self.assertEqual(by["P3"], "B")


class TestEdgeCases(unittest.TestCase):
    def test_duplicates_dates_and_lumpy(self):
        rows = ["item;period;quantity;unit_value"]
        qs = [0, 0, 50, 0, 2, 0, 0, 30, 0, 1]
        for m, q in enumerate(qs, start=1):
            rows.append("L1;15-%02d-2026;%d;10,5" % (m, q))
        rows.append("L1;15-03-2026;10;10,5")  # duplicate period -> summed
        res = ax.compute(ax.read_table(write_tmp("\n".join(rows) + "\n"), ax.REQUIRED))
        r = res["items"][0]
        self.assertEqual(r["history_periods"], 10)
        self.assertEqual(r["total_qty"], 93)
        self.assertEqual(r["pattern"], "lumpy")
        self.assertTrue(any("duplicate" in w for w in res["warnings"]))

    def test_dead_item(self):
        rows = ["item,period,quantity,unit_value"]
        for m in range(1, 13):
            rows.append("D,2026-%02d,%d,5" % (m, 10 if m <= 6 else 0))
        res = ax.compute(ax.read_table(write_tmp("\n".join(rows) + "\n"), ax.REQUIRED))
        self.assertEqual(res["delisting_candidates"], ["D"])

    def test_missing_column(self):
        with self.assertRaises(ax.InputError) as ctx:
            ax.read_table(write_tmp("item,period,qty\nA,2026-01,1\n"), ax.REQUIRED)
        self.assertIn("Expected columns: item, period, quantity, unit_value", str(ctx.exception))


class TestAsset(unittest.TestCase):
    def test_asset(self):
        res = ax.compute(ax.read_table(ASSET, ax.REQUIRED))
        by = {r["item"]: r for r in res["items"]}
        self.assertEqual(len(res["items"]), 3)
        self.assertAlmostEqual(by["VP-110 Impeller bronze 160"]["value"], 31800)  # missing unit value filled
        self.assertAlmostEqual(by["VP-220 Bearing 6205-2RS"]["cov"], 12.802 / 136.667, places=3)
        self.assertEqual(by["VP-220 Bearing 6205-2RS"]["segment"], "BX")
        self.assertEqual(res["short_history"][0]["item"], "VP-440 Seal kit v2")
        self.assertAlmostEqual(res["short_history"][0]["run_rate_value"], 30705)
        self.assertTrue(any("negative quantity" in w for w in res["warnings"]))

    def test_cli(self):
        buf = io.StringIO()
        out = os.path.join(tempfile.mkdtemp(), "o.csv")
        with redirect_stdout(buf):
            rc = ax.main([ASSET, "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("9-box", buf.getvalue())
        self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
