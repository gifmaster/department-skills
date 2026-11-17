import importlib.util
import os
import tempfile
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("notice_deadlines", os.path.join(ROOT, "scripts", "notice_deadlines.py"))
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)

T = date(2026, 11, 16)


def row(**kw):
    base = {"contract": "C", "counterparty": "P", "start_date": "2025-01-01", "end_date": "", "auto_renew": "yes",
            "renewal_term_months": "12", "notice_period_months": "", "notice_days": "", "notice_form": "", "_line": 2}
    base.update(kw)
    return base


def one(res):
    return res["contracts"][0]


class TestDateMaths(unittest.TestCase):
    def test_month_subtraction_and_roll(self):
        self.assertEqual(nd.notice_deadline(date(2027, 1, 31), 6, None), date(2026, 7, 31))
        self.assertEqual(nd.notice_deadline(date(2027, 8, 31), 6, None), date(2027, 2, 28))
        self.assertEqual(nd.notice_deadline(date(2027, 1, 31), None, 60), date(2026, 12, 2))
        self.assertEqual(nd.notice_deadline(date(2027, 1, 31), 2, 90), date(2026, 11, 2))  # earlier of 30 Nov and 2 Nov
        self.assertEqual(nd.roll(date(2027, 2, 28), 12), date(2028, 2, 29))  # month-end stays month-end
        self.assertEqual(nd.roll(date(2026, 11, 30), 6), date(2027, 5, 31))
        self.assertEqual(nd.roll(date(2026, 12, 14), 12), date(2027, 12, 14))


class TestCases(unittest.TestCase):
    def test_passed_deadline_rolls_forward(self):
        res = nd.analyse([row(end_date="2027-01-31", notice_period_months="6")], T)
        c = one(res)
        self.assertEqual(c["current_term_end"], "2028-01-31")
        self.assertEqual(c["notice_deadline"], "2027-07-31")
        self.assertEqual(c["renewals_rolled"], 1)
        self.assertEqual(c["status"], "RENEWED")
        self.assertEqual(c["send_by"], "2027-07-26")  # 31 Jul minus 5 days = 26 Jul (Monday)

    def test_multiple_rollovers(self):
        res = nd.analyse([row(start_date="2023-07-01", end_date="2024-06-30", notice_days="30", renewal_term_months="12")], T)
        c = one(res)
        self.assertEqual(c["renewals_rolled"], 3)
        self.assertEqual(c["current_term_end"], "2027-06-30")  # 2024-06-30 -> 2025 -> 2026 -> 2027 (each 31 May deadline passed)

    def test_due_and_act_now(self):
        due = one(nd.analyse([row(end_date="2026-12-31", notice_period_months="1")], T))
        self.assertEqual(due["status"], "DUE")
        self.assertEqual(due["days_to_deadline"], 14)
        now = one(nd.analyse([row(end_date="2026-12-18", notice_period_months="1")], T, buffer_days=5))
        self.assertEqual(now["notice_deadline"], "2026-11-18")
        self.assertEqual(now["status"], "ACT NOW")

    def test_weekend_send_by_moves_back(self):
        # deadline Mon 30 Nov 2026, buffer 2 days -> Sat 28 Nov -> Fri 27 Nov
        c = one(nd.analyse([row(end_date="2026-12-31", notice_period_months="1")], T, buffer_days=2))
        self.assertEqual(c["send_by"], "2026-11-27")

    def test_no_auto_renew(self):
        c = one(nd.analyse([row(end_date="2027-01-10", auto_renew="no", notice_period_months="3")], T))
        self.assertEqual(c["status"], "ENDS")
        self.assertEqual(c["current_term_end"], "2027-01-10")


class TestSampleAsset(unittest.TestCase):
    def test_sample_and_ics(self):
        _, rows = nd.read_csv(os.path.join(ROOT, "assets", "contracts_template.csv"), nd.REQUIRED)
        res = nd.analyse(rows, T)
        self.assertEqual(len(res["contracts"]), 9)
        by = {c["contract"]: c for c in res["contracts"]}
        self.assertEqual(by["Packaging supply agreement"]["notice_deadline"], "2027-07-31")
        self.assertEqual(by["ERP subscription"]["current_term_end"], "2027-12-14")
        self.assertEqual(by["Waste collection"]["notice_deadline"], "2026-12-02")
        self.assertEqual(by["Marketing retainer"]["current_term_end"], "2027-05-31")
        self.assertEqual(sum(1 for c in res["contracts"] if c["status"].startswith("DUE")), 3)
        w = " ".join(res["warnings"])
        self.assertIn("duplicates", w)
        self.assertIn("after end_date", w)
        self.assertIn("no notice period", w)
        ics = nd.build_ics(res)
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertEqual(ics.count("BEGIN:VEVENT"), 9)
        self.assertTrue(all(len(l.encode("utf-8")) <= 75 for l in ics.split("\r\n")))

    def test_cli_missing_notice_column(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("contract;counterparty;start_date;end_date;auto_renew;renewal_term_months\nA;B;2025-01-01;2026-12-31;yes;12\n")
        rc = nd.main([fh.name])
        os.unlink(fh.name)
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
