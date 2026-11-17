import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("otif", os.path.join(UNIT, "scripts", "otif.py"))
ot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ot)
ASSET = os.path.join(UNIT, "assets", "order_lines.csv")
HEADER = "order_id;line;customer;item;promised_date;delivered_date;ordered_qty;delivered_qty;reason\n"


def write_tmp(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


def run(text, **kw):
    return ot.compute(ot.read_table(write_tmp(text), ot.REQUIRED, ot.OPTIONAL), **kw)


class TestAsset(unittest.TestCase):
    def setUp(self):
        self.res = ot.compute(ot.read_table(ASSET, ot.REQUIRED, ot.OPTIONAL))

    def test_line_and_order_level(self):
        # hand count: 9 of 17 lines OTIF, 10 on time, 15 in full; 7 of 15 orders OTIF
        t, o = self.res["line_level"], self.res["order_level"]
        self.assertEqual(t["lines"], 17)
        self.assertAlmostEqual(t["otif"], 9 / 17)
        self.assertAlmostEqual(t["on_time"], 10 / 17)
        self.assertAlmostEqual(t["in_full"], 15 / 17)
        self.assertAlmostEqual(o["otif"], 7 / 15)
        self.assertAlmostEqual(o["on_time"], 8 / 15)

    def test_fill_rates(self):
        # ordered 900; delivered capped 850; delivered by due date 585
        self.assertAlmostEqual(self.res["line_level"]["fill_rate"], 850 / 900)
        self.assertAlmostEqual(self.res["line_level"]["on_time_fill_rate"], 585 / 900)
        self.assertAlmostEqual(self.res["avg_days_late"], 2.5)

    def test_pareto_and_warnings(self):
        top = self.res["pareto"][0]
        self.assertEqual((top["reason"], top["lines"]), ("stock", 4))
        self.assertAlmostEqual(top["share"], 0.5)
        w = " ".join(self.res["warnings"])
        self.assertIn("over-delivered", w)
        self.assertIn("no reason code", w)

    def test_split_delivery_line(self):
        l = [x for x in self.res["lines"] if x["order_id"] == "SO-8804"][0]
        self.assertEqual(l["deliveries_count"], 2)
        self.assertEqual(l["completion_date"], date(2026, 10, 9))
        self.assertFalse(l["on_time"])
        self.assertTrue(l["in_full"])

    def test_cli(self):
        buf = io.StringIO()
        out = os.path.join(tempfile.mkdtemp(), "o.csv")
        with redirect_stdout(buf):
            rc = ot.main([ASSET, "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("Root cause Pareto", buf.getvalue())


class TestParameters(unittest.TestCase):
    TEXT = HEADER + ("A;1;C1;X;01-10-2026;02-10-2026;100;99;transport\n"
                     "B;1;C1;Y;2026-10-01;2026-10-01;100;100;\n"
                     "C;1;C2;Y;2026-10-01;2026-09-25;10;10;\n"
                     "D;1;C2;Y;2026-12-01;;10;0;\n")

    def test_strict_default(self):
        res = run(self.TEXT, as_of=date(2026, 10, 31))
        self.assertEqual(res["open_lines"], 1)       # D not yet due
        self.assertAlmostEqual(res["line_level"]["otif"], 2 / 3)   # A late and short

    def test_tolerances(self):
        res = run(self.TEXT, tolerance_days=1, qty_tolerance_pct=2, as_of=date(2026, 10, 31))
        self.assertAlmostEqual(res["line_level"]["otif"], 1.0)

    def test_early_penalty(self):
        res = run(self.TEXT, tolerance_days=1, qty_tolerance_pct=2, early_days=3, as_of=date(2026, 10, 31))
        c = [l for l in res["lines"] if l["order_id"] == "C"][0]
        self.assertFalse(c["on_time"])

    def test_late_partial_after_complete_qty(self):
        # 98 on time reaches the 2 % tolerance, the late 2 do not make the line late
        text = HEADER + "E;1;C;X;2026-10-01;2026-10-01;100;98;\nE;1;C;X;2026-10-01;2026-10-05;100;2;\n"
        res = run(text, qty_tolerance_pct=2)
        self.assertTrue(res["lines"][0]["otif"])
        res = run(text)
        self.assertFalse(res["lines"][0]["on_time"])

    def test_missing_column(self):
        with self.assertRaises(ot.InputError) as ctx:
            ot.read_table(write_tmp("order_id,line\nA,1\n"), ot.REQUIRED, ot.OPTIONAL)
        self.assertIn("promised_date", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
