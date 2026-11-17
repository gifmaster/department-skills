import importlib.util
import os
import unittest
from datetime import date, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("je_tests", os.path.join(ROOT, "scripts", "je_tests.py"))
je = importlib.util.module_from_spec(spec)
spec.loader.exec_module(je)


def line(eid, d, user, account, desc, amount, manual=False, t=None):
    return {"entry_id": eid, "date": d, "time": t, "user": user, "account": account, "description": desc,
            "amount": amount, "cents": int(round(abs(amount) * 100)), "manual": manual, "line": 2}


class TestHolidays(unittest.TestCase):
    def test_easter_based(self):
        h = je.danish_holidays(2026)
        self.assertEqual(je.easter_sunday(2026), date(2026, 4, 5))
        self.assertEqual(h[date(2026, 4, 2)], "Maundy Thursday")
        self.assertEqual(h[date(2026, 4, 3)], "Good Friday")
        self.assertEqual(h[date(2026, 4, 6)], "Easter Monday")
        self.assertEqual(h[date(2026, 5, 14)], "Ascension Day")
        self.assertEqual(h[date(2026, 5, 25)], "Whit Monday")
        self.assertNotIn(date(2026, 5, 1), h)  # Great Prayer Day abolished from 2024
        self.assertIn(date(2023, 5, 5), je.danish_holidays(2023))  # Great Prayer Day 2023


class TestRules(unittest.TestCase):
    def test_boundaries(self):
        lines = [line("A", date(2026, 3, 3), "U1", "2800", "x", 45000.0),   # 90% of limit: hit T4 and T3
                 line("B", date(2026, 3, 3), "U1", "2800", "y", 44999.0),   # below band
                 line("C", date(2026, 3, 3), "U1", "2800", "z", 50000.0),   # at limit: not T4
                 line("D", date(2026, 3, 3), "U1", "2800", "w", 4000.0)]    # round but under round-min
        res = je.run_tests(lines, approval_limit=50000.0, rare_user_max=0)
        by = {r["entry_id"]: r for r in res["ranked"]}
        self.assertEqual(by["A"]["tests"], ["T3", "T4"])
        self.assertEqual(by["A"]["score"], 4)
        self.assertNotIn("B", by)
        self.assertEqual(by["C"]["tests"], ["T3"])
        self.assertNotIn("D", by)

    def test_hours_known_users_mask(self):
        lines = [line("A", date(2026, 3, 3), "NEW", "1010", "Salg", -1234.0, manual=True, t=time(6, 59)),
                 line("B", date(2026, 3, 3), "OLD", "2800", "Ok", 1234.0, t=time(7, 0))]
        res = je.run_tests(lines, known_users=["OLD"], mask_users=True)
        self.assertEqual(len(res["ranked"]), 1)
        r = res["ranked"][0]
        self.assertEqual(r["tests"], ["T2", "T6", "T7"])
        self.assertEqual(r["score"], 6)
        self.assertEqual(r["user"], "U1")  # NEW sorts before OLD

    def test_unbalanced_entry_warning(self):
        w = []
        je.run_tests([line("A", date(2026, 3, 3), "U", "2800", "x", 100.0),
                      line("A", date(2026, 3, 3), "U", "5820", "x", -90.0)], warnings=w)
        self.assertTrue(any("does not balance" in x for x in w))


class TestSample(unittest.TestCase):
    def test_sample(self):
        w = []
        lines, has_time = je.load(os.path.join(ROOT, "assets", "journal.csv"), w)
        self.assertTrue(has_time)
        self.assertTrue(any("JE1011" in x and "skipped" in x for x in w))
        res = je.run_tests(lines, approval_limit=50000.0, warnings=w)
        ranked = res["ranked"]
        self.assertEqual(len(ranked), 7)
        self.assertEqual((ranked[0]["entry_id"], ranked[0]["score"]), ("JE1002", 9))
        by = {r["entry_id"]: r for r in ranked}
        self.assertIn("T5", by["JE1005"]["tests"])
        self.assertIn("T5", by["JE1006"]["tests"])
        self.assertEqual(by["JE1004"]["details"]["T1"], "Maundy Thursday")
        self.assertEqual(by["JE1007"]["details"]["T1"], "Easter Monday")
        self.assertEqual(sorted(r["entry_id"] for r in ranked if "T7" in r["tests"]), ["JE1007", "JE1009"])

    def test_report_describes_facts_only(self):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            je.main([os.path.join(ROOT, "assets", "journal.csv"), "--approval-limit", "50000"])
        text = buf.getvalue().lower()
        for word in ("suspect", "fraudster", "guilty", "culprit"):
            self.assertNotIn(word, text)
        self.assertIn("not conclusions about any person", text)


if __name__ == "__main__":
    unittest.main()
