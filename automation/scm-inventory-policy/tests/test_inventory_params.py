import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("inventory_params", os.path.join(UNIT, "scripts", "inventory_params.py"))
ip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ip)
ASSET = os.path.join(UNIT, "assets", "inventory_items.csv")
HEADER = "item,avg_daily_demand,sd_daily_demand,lead_time_days,sd_lead_time_days,unit_cost,order_cost,holding_rate,moq,pack_size\n"


def write_tmp(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


class TestNormal(unittest.TestCase):
    def test_inverse_normal(self):
        self.assertAlmostEqual(ip.norm_ppf(0.5), 0.0, places=7)
        self.assertAlmostEqual(ip.norm_ppf(0.95), 1.644854, places=5)
        self.assertAlmostEqual(ip.norm_ppf(0.975), 1.959964, places=5)
        self.assertAlmostEqual(ip.norm_ppf(0.99), 2.326348, places=5)
        self.assertAlmostEqual(ip.norm_ppf(0.01), -2.326348, places=5)

    def test_number_formats(self):
        self.assertEqual(ip.parse_number("1.234,56"), 1234.56)
        self.assertEqual(ip.parse_number("1234.56"), 1234.56)
        self.assertEqual(ip.parse_number("4,80"), 4.8)
        self.assertEqual(ip.parse_number(""), None)


class TestHandCase(unittest.TestCase):
    def test_single_item(self):
        # d=10, sd=3, L=9, sdL=2 -> sigma = sqrt(9*9 + 100*4) = sqrt(481) = 21.932
        # SS = ceil(1.6449*21.932 = 36.08) = 37 ; ROP = 90 + 37 = 127
        # EOQ = sqrt(2*3650*100/(20*0.2)) = 427.2 -> packs of 50 -> 450
        path = write_tmp(HEADER + "A,10,3,9,2,20,100,0.2,100,50\n")
        res = ip.compute(ip.read_table(path, ip.REQUIRED, ip.OPTIONAL))
        i = res["items"][0]
        self.assertAlmostEqual(i["sigma_lead_time_demand"], 21.9317, places=3)
        self.assertEqual(i["safety_stock"], 37)
        self.assertEqual(i["reorder_point"], 127)
        self.assertAlmostEqual(i["eoq"], 427.20, places=2)
        self.assertEqual(i["order_qty"], 450)
        self.assertAlmostEqual(i["expected_fill_rate"], 0.99898, places=4)
        self.assertAlmostEqual(i["value_proposed"], (37 + 225) * 20)

    def test_moq_dominates_and_semicolon_danish(self):
        # EOQ = sqrt(2*365*50/(10*0.25)) = 120.8 -> MOQ 500 -> pack 120 -> 600
        text = HEADER.replace(",", ";") + "B;1;0;5;0;10,00;50;25;500;120\n"
        res = ip.compute(ip.read_table(write_tmp(text), ip.REQUIRED, ip.OPTIONAL))
        i = res["items"][0]
        self.assertEqual(i["safety_stock"], 0)
        self.assertEqual(i["reorder_point"], 5)
        self.assertEqual(i["order_qty"], 600)
        self.assertTrue(any("percentage" in w for w in res["warnings"]))
        self.assertTrue(any("MOQ is not a multiple" in f for f in i["flags"]))

    def test_missing_column_message(self):
        path = write_tmp("item,avg_daily_demand\nA,1\n")
        with self.assertRaises(ip.InputError) as ctx:
            ip.read_table(path, ip.REQUIRED, ip.OPTIONAL)
        self.assertIn("Expected columns", str(ctx.exception))
        self.assertIn("pack_size", str(ctx.exception))


class TestAsset(unittest.TestCase):
    def setUp(self):
        self.res = ip.compute(ip.read_table(ASSET, ip.REQUIRED, ip.OPTIONAL))
        self.by = {i["item"]: i for i in self.res["items"]}

    def test_counts_and_quality(self):
        self.assertEqual(len(self.res["items"]), 8)
        w = " ".join(self.res["warnings"])
        self.assertIn("duplicate item", w)
        self.assertIn("missing unit_cost", w)
        self.assertIn("percentage", w)

    def test_ball_valve(self):
        # sqrt(35*8.3^2 + 9.3^2*10^2) = sqrt(2411.15 + 8649) = 105.17; x1.6449 = 172.99 -> 173
        i = self.by["HX-344 Ball valve 1in"]
        self.assertEqual(i["safety_stock"], 173)
        self.assertEqual(i["reorder_point"], 499)  # 325.5 + 173 = 498.5 -> 499
        self.assertEqual(i["order_qty"], 310)

    def test_unit_flags(self):
        self.assertTrue(any("UNITS?" in f for f in self.by["HX-430 Thermostatic valve"]["flags"]))
        self.assertTrue(any("600 days" in f for f in self.by["HX-615 Radiator bracket"]["flags"]))
        self.assertTrue(any("lumpy" in f for f in self.by["HX-901 Pump kit OEM"]["flags"]))

    def test_cli_markdown_and_csv(self):
        out = os.path.join(tempfile.mkdtemp(), "o.csv")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ip.main([ASSET, "--out", out])
        self.assertEqual(rc, 0)
        self.assertIn("## 4. Items needing manual review", buf.getvalue())
        self.assertTrue(os.path.getsize(out) > 0)


if __name__ == "__main__":
    unittest.main()
