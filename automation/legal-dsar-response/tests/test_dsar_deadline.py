import importlib.util
import os
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("dsar_deadline", os.path.join(ROOT, "scripts", "dsar_deadline.py"))
dd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dd)

T = date(2026, 11, 16)


class TestCalendarMonth(unittest.TestCase):
    def test_same_day_next_month(self):
        r = dd.assess(date(2026, 10, 3), T)
        self.assertEqual(r["deadline"], "2026-11-03")
        self.assertEqual(r["status"], "OVERDUE")
        self.assertEqual(r["days_overdue"], 13)
        self.assertEqual(r["extension_possible"], "no (first month has passed)")

    def test_month_end_rule(self):
        r = dd.assess(date(2027, 1, 31), date(2027, 2, 1))
        self.assertEqual(r["deadline"], "2027-02-28")
        self.assertEqual(r["extended_deadline"], "2027-04-28")  # conservative: 28 Feb + 2 months
        self.assertEqual(dd.assess(date(2028, 1, 31), date(2028, 2, 1))["deadline"], "2028-02-29")  # leap year
        self.assertEqual(dd.assess(date(2026, 8, 31), T)["deadline"], "2026-09-30")

    def test_valid_and_invalid_extension(self):
        ok = dd.assess(date(2026, 9, 20), T, extension=True, extension_notified=date(2026, 10, 10))
        self.assertTrue(ok["extension_valid"])
        self.assertEqual(ok["effective_deadline"], "2026-12-20")
        self.assertEqual(ok["days_left"], 34)
        late = dd.assess(date(2026, 9, 10), T, extension=True, extension_notified=date(2026, 10, 15))
        self.assertFalse(late["extension_valid"])
        self.assertEqual(late["effective_deadline"], "2026-10-10")
        self.assertEqual(late["days_overdue"], 37)

    def test_extension_still_possible_and_due_soon(self):
        r = dd.assess(date(2026, 10, 20), T)
        self.assertEqual(r["status"], "due soon")
        self.assertTrue(r["extension_possible"].startswith("yes"))

    def test_closed(self):
        r = dd.assess(date(2026, 7, 1), T, extension=True, extension_notified=date(2026, 7, 20),
                      responded=date(2026, 10, 5))
        self.assertEqual(r["status"], "closed late")
        self.assertEqual(r["days_late"], 4)

    def test_clock_from_verification_and_weekend_roll(self):
        r = dd.assess(date(2026, 10, 1), T, verified=date(2026, 10, 5), clock_start="verification")
        self.assertEqual(r["deadline"], "2026-11-05")
        r2 = dd.assess(date(2026, 9, 5), T, roll_weekend=True)  # 5 Oct 2026 is a Monday
        self.assertEqual(r2["deadline"], "2026-10-05")
        r3 = dd.assess(date(2026, 9, 3), T, roll_weekend=True)  # 3 Oct 2026 is a Saturday -> Monday 5 Oct
        self.assertEqual(r3["deadline"], "2026-10-05")


class TestSampleAsset(unittest.TestCase):
    def test_tracker(self):
        _, rows = dd.read_csv(os.path.join(ROOT, "assets", "dsar_log_template.csv"), ["request_id", "received_date"])
        res = dd.tracker(rows, T)
        c = res["counts"]
        self.assertEqual(c["OVERDUE"], 2)
        self.assertEqual(c["due soon"], 1)
        self.assertEqual(c["open"], 3)
        self.assertEqual(c["closed late"], 1)
        self.assertEqual(c["closed on time"], 1)
        self.assertEqual(res["requests"][0]["request_id"], "DSR-2026-034")
        w = " ".join(res["warnings"])
        self.assertIn("duplicates", w)
        self.assertIn("received_date missing", w)

    def test_missing_column(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("id;date\n1;2026-01-01\n")
        with self.assertRaises(ValueError) as cm:
            dd.read_csv(fh.name, ["request_id", "received_date"])
        os.unlink(fh.name)
        self.assertIn("request_id", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
