import importlib.util
import os
import tempfile
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("cash13", os.path.join(ROOT, "scripts", "cash13.py"))
c13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c13)
A = lambda n: os.path.join(ROOT, "assets", n)


def write(text):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    fh.write(text)
    fh.close()
    return fh.name


class TestCalendar(unittest.TestCase):
    def test_easter(self):
        self.assertEqual(c13.easter_sunday(2026), date(2026, 4, 5))
        self.assertEqual(c13.easter_sunday(2027), date(2027, 3, 28))

    def test_banking_days(self):
        cal = c13.BankCalendar()
        self.assertFalse(cal.is_banking_day(date(2026, 5, 14)))  # Ascension
        self.assertFalse(cal.is_banking_day(date(2026, 5, 15)))  # bank closing day after Ascension
        self.assertFalse(cal.is_banking_day(date(2026, 6, 5)))   # Constitution Day
        self.assertEqual(cal.last_banking_day(2026, 12), date(2026, 12, 30))
        self.assertEqual(cal.roll(date(2027, 1, 1)), date(2027, 1, 4))

    def test_atax_timing(self):
        cal = c13.BankCalendar()
        row = {"name": "A-skat", "amount": -100.0, "first_date": date(2026, 11, 1), "frequency": "monthly",
               "day": "", "category": "atax", "end_date": None}
        large, _ = c13.expand_recurring(row, date(2026, 11, 2), date(2027, 1, 31), cal, "large", "following", [])
        small, _ = c13.expand_recurring(row, date(2026, 11, 2), date(2027, 1, 31), cal, "small", "following", [])
        self.assertEqual([d for d, _, _ in large], [date(2026, 11, 30), date(2026, 12, 30), date(2027, 1, 29)])
        # Nov paid 10 Dec; Dec salary month has the special 17 January deadline (17 Jan 2027 is a Sunday -> 18 Jan)
        self.assertEqual([d for d, _, _ in small], [date(2026, 12, 10), date(2027, 1, 18)])

    def test_atax_small_december_deadline(self):
        cal = c13.BankCalendar()
        row = {"name": "A-skat", "amount": -100.0, "first_date": date(2025, 11, 1), "frequency": "monthly",
               "day": "", "category": "atax", "end_date": None}
        small, _ = c13.expand_recurring(row, date(2025, 11, 2), date(2026, 2, 28), cal, "small", "following", [])
        # Nov 2025 -> 10 Dec 2025; Dec 2025 -> Sat 17 Jan 2026 rolls to Mon 19 Jan; Jan 2026 -> Tue 10 Feb 2026
        self.assertEqual([d for d, _, _ in small], [date(2025, 12, 10), date(2026, 1, 19), date(2026, 2, 10)])
        self.assertIn("salary month 2025-12", small[1][2])
        custom, _ = c13.expand_recurring(row, date(2025, 11, 2), date(2026, 2, 28), cal, "small", "following", [],
                                         atax_small_day=12, atax_december_day=20)
        self.assertEqual([d for d, _, _ in custom], [date(2025, 12, 12), date(2026, 1, 20), date(2026, 2, 12)])

    def test_once_frequency(self):
        cal = c13.BankCalendar()
        row = {"name": "New van", "amount": -250000.0, "first_date": date(2026, 12, 5), "frequency": "once",
               "day": "", "category": "", "end_date": None}
        occ, _ = c13.expand_recurring(row, date(2026, 11, 23), date(2027, 2, 21), cal, "large", "following", [])
        self.assertEqual(occ, [(date(2026, 12, 7), -250000.0, "New van")])   # Sat 5 Dec rolls to Mon 7 Dec
        outside, _ = c13.expand_recurring(dict(row, first_date=date(2027, 3, 1)), date(2026, 11, 23),
                                          date(2027, 2, 21), cal, "large", "following", [])
        self.assertEqual(outside, [])
        r = write("customer,amount,due_date\nKunde,0,2026-01-07\n")
        q = write("name,amount,first_date,frequency,day\nBonus,-300,2026-01-07,once,\n")
        w = []
        recs, pays, recur = c13.load_inputs(r, None, q, 0, w)
        self.assertEqual(len(recur), 1)
        res = c13.forecast(1000.0, date(2026, 1, 5), recs, pays, recur, weeks=2)
        self.assertEqual(res["weeks"][0]["closing"], 700.0)
        self.assertEqual(res["weeks"][1]["closing"], 700.0)
        os.unlink(r)
        os.unlink(q)


class TestHandBuilt(unittest.TestCase):
    def test_one_week(self):
        r = write("customer,amount,due_date,avg_days_late\nKunde,500,2026-01-07,2\n")
        p = write("supplier,amount,due_date\nLev,800,2026-01-06\n")
        w = []
        recs, pays, recur = c13.load_inputs(r, p, None, 0, w)
        res = c13.forecast(1000.0, date(2026, 1, 5), recs, pays, recur, weeks=1, min_buffer=300.0)
        # 1000 - 800 on Tue 6 Jan = 200 (lowest), +500 on Fri 9 Jan = 700
        self.assertEqual(res["lowest_day"], (date(2026, 1, 6), 200.0))
        self.assertEqual(res["weeks"][0]["closing"], 700.0)
        self.assertEqual(len(res["days_below_buffer"]), 3)  # Tue, Wed, Thu
        os.unlink(r)
        os.unlink(p)

    def test_missing_column(self):
        r = write("customer;beløb\nX;1\n")
        with self.assertRaises(c13.InputError) as cm:
            c13.load_inputs(r, None, None, 0, [])
        self.assertIn("Expected columns: customer, amount, due_date", str(cm.exception))
        os.unlink(r)


class TestSample(unittest.TestCase):
    def test_sample(self):
        w = []
        recs, pays, recur = c13.load_inputs(A("receivables.csv"), A("payables.csv"), A("recurring.csv"), 0, w)
        res = c13.forecast(850000.0, date(2026, 11, 23), recs, pays, recur, weeks=13, min_buffer=250000.0,
                           facility=500000.0, warnings=w)
        self.assertTrue(any("Vestergaard" in x and "skipped" in x for x in w))
        self.assertTrue(any("48,750" in x and "overdue" in x for x in w))
        self.assertEqual(res["lowest_day"], (date(2026, 12, 30), -439252.0))
        self.assertEqual(res["weeks"][-1]["closing"], 655498.0)
        # week 2: 911,070 + 18,000 - 164,210 - 785,000 - 190,000 = -210,140
        self.assertEqual(res["weeks"][1]["closing"], -210140.0)
        self.assertEqual(res["weeks"][1]["atax"], -190000.0)
        # totals tie: opening + in + out = final closing
        self.assertAlmostEqual(850000 + res["total_in"] + res["total_out"], res["weeks"][-1]["closing"], places=2)


if __name__ == "__main__":
    unittest.main()
