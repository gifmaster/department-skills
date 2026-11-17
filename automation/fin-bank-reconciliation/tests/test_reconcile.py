import importlib.util
import os
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("reconcile", os.path.join(ROOT, "scripts", "reconcile.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def item(side, n, d, text, amount):
    return {"id": "%s%d" % ("B" if side == "bank" else "L", n), "side": side, "line": n + 1, "date": d,
            "text": text, "amount": amount, "cents": int(round(amount * 100))}


class TestParsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(rc.parse_number("-48.750,00"), -48750.0)
        self.assertEqual(rc.parse_number("1234.56"), 1234.56)
        self.assertEqual(rc.parse_number("1,234.56"), 1234.56)
        self.assertEqual(rc.parse_number("125,5"), 125.5)
        self.assertEqual(rc.parse_number("1.234"), 1234.0)
        self.assertIsNone(rc.parse_number(""))

    def test_dates(self):
        self.assertEqual(rc.parse_date("15-10-2026"), date(2026, 10, 15))
        self.assertEqual(rc.parse_date("2026-10-15"), date(2026, 10, 15))
        self.assertIsNone(rc.parse_date("31-02-2026"))

    def test_missing_column_message(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write("date;tekst\n2026-10-01;x\n")
            path = fh.name
        with self.assertRaises(rc.InputError) as cm:
            rc.load_side(path, "bank")
        self.assertIn("amount", str(cm.exception))
        self.assertIn("Expected columns: date, text, amount", str(cm.exception))
        os.unlink(path)


class TestSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bank, cls.w1 = rc.load_side(os.path.join(ROOT, "assets", "bank_statement.csv"), "bank")
        ledger, cls.w2 = rc.load_side(os.path.join(ROOT, "assets", "ledger.csv"), "ledger")
        cls.res = rc.reconcile(bank, ledger, bank_balance=150371.58, ledger_balance=350073.00)

    def test_missing_amount_detected(self):
        self.assertTrue(any("missing amount" in w for w in self.w2))

    def test_statement(self):
        st = self.res["statement"]
        # 96,800 (sign error) + 24,000 (Ribe) + 2,500 (old July item)
        self.assertAlmostEqual(st["ledger_receipts_not_in_bank"], 123300.00, places=2)
        self.assertAlmostEqual(st["ledger_payments_not_in_bank"], -8952.00, places=2)
        # bank receipts 18,750 + 9,865.40
        self.assertAlmostEqual(st["bank_receipts_not_in_ledger"], -28615.40, places=2)
        # 125 + 96,800 + 12,480 + 1,840.22 + 8,973.60
        self.assertAlmostEqual(st["bank_payments_not_in_ledger"], 120218.82, places=2)
        self.assertAlmostEqual(st["computed_ledger_balance"], 356323.00, places=2)
        # the skipped Grafisk Hus line (-6,250) is the unexplained difference
        self.assertAlmostEqual(st["unexplained_difference"], -6250.00, places=2)

    def test_matches_and_flags(self):
        ms = self.res["matched_summary"]
        self.assertEqual(ms["1:1"]["matches"], 6)
        self.assertEqual(ms["1:many"]["ledger_lines"], 2)
        self.assertEqual(ms["fuzzy"]["matches"], 1)
        self.assertEqual([(b["id"], l["id"]) for b, l in self.res["sign_errors"]], [("B6", "L5")])
        self.assertEqual([(x["id"], y["id"]) for x, y in self.res["duplicates"]], [("B7", "B8")])
        self.assertEqual([i["id"] for i in self.res["old_items"]], ["L1"])
        self.assertEqual(self.res["old_items"][0]["age_days"], 111)
        self.assertAlmostEqual(self.res["amount_differences"][0][2], -21.60, places=2)


class TestHandBuilt(unittest.TestCase):
    def test_window_and_group(self):
        bank = [item("bank", 1, date(2026, 1, 1), "Kunde A", 100.0),
                item("bank", 2, date(2026, 1, 10), "Samlet indbetaling", 300.0)]
        ledger = [item("ledger", 1, date(2026, 1, 8), "Faktura 77", 100.0),
                  item("ledger", 2, date(2026, 1, 9), "Fak 1", 120.0),
                  item("ledger", 3, date(2026, 1, 11), "Fak 2", 180.0)]
        res = rc.reconcile(bank, ledger, window=5, bank_balance=1000.0, ledger_balance=1000.0)
        # 7 days apart and dissimilar text: not matched
        self.assertEqual(bank[0]["status"], "unmatched")
        self.assertEqual(ledger[0]["status"], "unmatched")
        # 300 = 120 + 180
        self.assertEqual(bank[1]["match_type"], "1:2")
        self.assertEqual(res["statement"]["unexplained_difference"], 0.0)

    def test_difference_formula(self):
        bank = [item("bank", 1, date(2026, 3, 2), "Gebyr", -50.0)]
        ledger = [item("ledger", 1, date(2026, 3, 31), "Check 12", -400.0)]
        res = rc.reconcile(bank, ledger, bank_balance=5000.0, ledger_balance=4650.0)
        # 5000 - 400 (ledger payment not in bank) + 50 (bank payment not in ledger) = 4650
        self.assertEqual(res["statement"]["computed_ledger_balance"], 4650.0)
        self.assertEqual(res["statement"]["unexplained_difference"], 0.0)
        self.assertEqual(bank[0]["category"], "Bank fees")
        self.assertEqual(ledger[0]["category"], "Timing (in ledger, not yet in bank)")


class TestOpeningItems(unittest.TestCase):
    def _write(self, text):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def test_opening_items_match_and_stay_in_statement(self):
        path = self._write("dato;tekst;beløb;side\n"
                           "29-09-2026;Leverandør Nord fak 551;-5.000,00;ledger\n"
                           "30-09-2026;Ukendt indbetaling;700,00;bank\n"
                           "28-09-2026;Check 9;x;ledger\n"
                           "28-09-2026;Check 10;-10,00;kasse\n")
        ob, ol, warns = rc.load_opening(path)
        self.assertEqual([i["id"] for i in ol], ["OL1"])
        self.assertEqual([i["id"] for i in ob], ["OB1"])
        self.assertEqual(len(warns), 2)
        bank = [item("bank", 1, date(2026, 10, 2), "Leverandør Nord 551", -5000.0)]
        ledger = [item("ledger", 1, date(2026, 10, 15), "Kunde Syd", 2000.0)]
        res = rc.reconcile(bank + ob, ledger + ol, bank_balance=10000.0, ledger_balance=11300.0)
        # the September ledger payment clears against the October bank line
        self.assertEqual(ol[0]["status"], "matched")
        self.assertEqual(bank[0]["match_id"], ol[0]["match_id"])
        st = res["statement"]
        # 10,000 + 2,000 (ledger receipt not in bank) - 700 (opening bank receipt still open) = 11,300
        self.assertEqual(st["computed_ledger_balance"], 11300.0)
        self.assertEqual(st["unexplained_difference"], 0.0)
        self.assertEqual(st["opening_items"], {"count": 2, "cleared": 1, "still_open": 1,
                                               "still_open_ledger_net": 0.0, "still_open_bank_net": 700.0})
        self.assertIn("brought forward, still open", ob[0]["flags"])

    def test_without_opening_items_bank_line_is_unexplained(self):
        bank = [item("bank", 1, date(2026, 10, 2), "Leverandør Nord 551", -5000.0)]
        res = rc.reconcile(bank, [], bank_balance=10000.0, ledger_balance=10000.0)
        self.assertEqual(bank[0]["category"], "Missing in ledger")
        self.assertNotIn("opening_items", res["statement"])
        self.assertEqual(res["statement"]["unexplained_difference"], -5000.0)

    def test_cli_opening_items(self):
        import io
        import json
        from contextlib import redirect_stdout
        path = self._write("date,text,amount,side\n2026-09-30,Husleje okt,-48750.00,ledger\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc.main([os.path.join(ROOT, "assets", "bank_statement.csv"), os.path.join(ROOT, "assets", "ledger.csv"),
                     "--opening-items", path, "--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(data["statement"]["opening_items"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
