import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("spend", os.path.join(UNIT, "scripts", "spend.py"))
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)
ASSET = os.path.join(UNIT, "assets", "ap_spend.csv")
STRIP = ("danmark", "denmark", "dk")


def write_tmp(text, suffix=".csv"):
    fh = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


class TestNormalisation(unittest.TestCase):
    def test_supplier_keys(self):
        k = lambda n: sp.supplier_key(n, set(STRIP))
        self.assertEqual(k("Lyreco Danmark A/S"), "lyreco")
        self.assertEqual(k("LYRECO DK"), "lyreco")
        self.assertEqual(k("Amazon EU S.à r.l."), "amazon eu")
        self.assertEqual(k("Würth Danmark A/S"), "wurth")
        self.assertEqual(k("Jysk Industri-Service ApS"), "jysk industri service")
        self.assertEqual(k("Nordisk Ståhl I/S"), "nordisk stahl")
        self.assertEqual(k("Müller GmbH"), "muller")
        self.assertEqual(k("Nordic Parts AB"), "nordic parts")
        self.assertEqual(k("Bolt Supply Ltd."), "bolt supply")
        self.assertEqual(k("Ny Kaffe IVS"), "ny kaffe")

    def test_keyword_word_start(self):
        self.assertTrue(sp.kw_match("pakke", "pakkeforsendelser"))
        self.assertFalse(sp.kw_match("ups", "groups"))


class TestAsset(unittest.TestCase):
    def setUp(self):
        self.res = sp.compute(sp.read_table(ASSET, sp.REQUIRED))
        self.sup = {s["supplier"]: s for s in self.res["suppliers"]}
        self.cat = {c["category"]: c for c in self.res["categories"]}

    def test_totals_and_grouping(self):
        self.assertAlmostEqual(self.res["total"], 2359300)
        self.assertEqual(self.res["raw_suppliers"], 16)
        self.assertEqual(self.res["suppliers_after"], 13)
        self.assertAlmostEqual(self.sup["Lyreco Danmark A/S"]["spend"], 61100)
        self.assertAlmostEqual(self.sup["Smurfit Westrock Danmark A/S"]["spend"], 637500)  # 624,000 + 31,500 - 18,000
        self.assertAlmostEqual(self.sup["Ahlsell Danmark ApS"]["spend"], 111000)
        self.assertIn("DSV A/S", self.sup)  # not merged, listed for review instead
        self.assertTrue(any("DSV" in r["a"] for r in self.res["review_pairs"]))

    def test_categories(self):
        self.assertAlmostEqual(self.cat["Freight and logistics"]["spend"], 997000)
        self.assertAlmostEqual(self.cat["Packaging"]["spend"], 878500)  # credit note via supplier's main category
        self.assertAlmostEqual(self.cat["Uncategorised"]["spend"], 22400)
        self.assertTrue(self.cat["Packaging"]["fragmented"])
        self.assertFalse(self.cat["MRO, tools and fasteners"]["fragmented"])

    def test_tail_and_savings(self):
        self.assertEqual(self.res["tail"]["suppliers"], 6)
        self.assertAlmostEqual(self.res["tail"]["spend"], 345800)
        # 5-10 % of 997,000 + 878,500 and 5-15 % of 291,800 tail outside fragmented categories
        self.assertAlmostEqual(self.res["savings_low"], 0.05 * 1875500 + 0.05 * 291800)
        self.assertAlmostEqual(self.res["savings_high"], 0.10 * 1875500 + 0.15 * 291800)
        self.assertEqual(self.res["suppliers_for_80pct"], 7)

    def test_quality_warnings(self):
        w = " ".join(self.res["warnings"])
        self.assertIn("Possible duplicate payment", w)
        self.assertIn("credit note", w)

    def test_cli(self):
        buf = io.StringIO()
        out = os.path.join(tempfile.mkdtemp(), "o.csv")
        with redirect_stdout(buf):
            rc = sp.main([ASSET, "--out", out, "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["lines"], 18)


class TestHandCase(unittest.TestCase):
    def test_custom_map_accounts_and_params(self):
        csv_text = ("supplier,amount,date,account,description\n"
                    "Alfa A/S,1000,2026-01-05,4000,Widgets\n"
                    "Beta ApS,500,2026-01-06,4000,Widgets\n"
                    "Gamma IVS,300,2026-01-07,4000,Widgets\n"
                    "Delta AB,150,2026-01-08,7000,Coffee beans\n"
                    "Epsilon Ltd,50,2026-01-09,9999,Misc\n")
        cats = write_tmp(json.dumps({"Coffee": ["coffee"], "_accounts": {"4000": "Components"}}), ".json")
        c, acc = sp.load_categories(cats)
        res = sp.compute(sp.read_table(write_tmp(csv_text), sp.REQUIRED), c, acc, STRIP,
                         consolidation=(10.0, 20.0), tail=(0.0, 10.0), tail_share=0.1)
        by = {x["category"]: x for x in res["categories"]}
        self.assertAlmostEqual(by["Components"]["spend"], 1800)
        self.assertEqual(by["Components"]["suppliers"], 3)
        self.assertAlmostEqual(by["Coffee"]["spend"], 150)
        # total 2,000; tail = suppliers after 90 % cumulative: Delta (90 % before) and Epsilon
        self.assertEqual(res["tail"]["suppliers"], 2)
        self.assertAlmostEqual(res["savings_low"], 180)               # 10 % of 1,800
        self.assertAlmostEqual(res["savings_high"], 360 + 20)         # 20 % of 1,800 + 10 % of 200

    def test_missing_column(self):
        with self.assertRaises(sp.InputError) as ctx:
            sp.read_table(write_tmp("supplier,amount\nA,1\n"), sp.REQUIRED)
        self.assertIn("Expected columns: supplier, amount, date, account, description", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
