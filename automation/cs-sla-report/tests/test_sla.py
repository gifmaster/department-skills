import importlib.util
import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("sla", os.path.join(UNIT, "scripts", "sla.py"))
sla = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sla)
ASSET = os.path.join(UNIT, "assets", "tickets_template.csv")


def run(rows, as_of, mode="business", targets=None, **kw):
    headers = sla.REQUIRED
    parsed = [(i + 2, dict(zip(headers, r))) for i, r in enumerate(rows)]
    cal = sla.Calendar(sla.parse_open_hours("08:00-16:00", "mon,tue,wed,thu,fri"), "dk")
    tickets, warnings, as_of = sla.analyse(parsed, targets or sla.load_targets(None), cal, mode,
                                           datetime.strptime(as_of, "%Y-%m-%d %H:%M"), **kw)
    return {t["ticket_id"]: t for t in tickets}, warnings


class TestHolidays(unittest.TestCase):
    def test_easter(self):
        self.assertEqual(sla.easter_sunday(2026), date(2026, 4, 5))
        self.assertEqual(sla.easter_sunday(2024), date(2024, 3, 31))
        self.assertEqual(sla.easter_sunday(2025), date(2025, 4, 20))

    def test_store_bededag_abolished_from_2024(self):
        self.assertIn(date(2023, 5, 5), sla.danish_holidays(2023))
        self.assertNotIn(date(2024, 4, 26), sla.danish_holidays(2024))
        self.assertEqual(len(sla.danish_holidays(2026)), 10)
        self.assertEqual(sla.danish_holidays(2026)[date(2026, 5, 14)], "Kristi himmelfartsdag")


class TestBusinessHours(unittest.TestCase):
    def test_over_easter(self):
        # Wed 1 Apr 14:30 to Tue 7 Apr 08:45: 1.5 h Wednesday, Thu to Mon closed, 0.75 h Tuesday
        t, _ = run([["A", "2026-04-01 14:30", "2026-04-07 08:45", "2026-04-08 12:00", "P3", "email"]], "2026-04-15 00:00")
        self.assertAlmostEqual(t["A"]["fr_hours"], 2.25)
        self.assertAlmostEqual(t["A"]["res_hours"], 13.5)  # 1.5 + 8 + 4

    def test_weekend_start(self):
        t, _ = run([["B", "2026-04-10 16:30", "2026-04-13 08:20", "2026-04-13 15:00", "P3", "email"]], "2026-04-15 00:00")
        self.assertAlmostEqual(t["B"]["fr_hours"], 20 / 60)
        self.assertAlmostEqual(t["B"]["res_hours"], 7.0)

    def test_calendar_mode_dst(self):
        # DST starts 29 Mar 2026: 22:00 Sat to 04:00 Sun local is 5 real hours, not 6
        t, _ = run([["C", "2026-03-28 22:00", "2026-03-28 22:30", "2026-03-29 04:00", "P1", "phone"]],
                   "2026-03-30 00:00", mode="calendar")
        self.assertAlmostEqual(t["C"]["res_hours"], 5.0)
        # DST ends 25 Oct 2026: 00:00 to 06:00 local is 7 real hours
        t, _ = run([["D", "2026-10-25 00:00", "2026-10-25 00:10", "2026-10-25 06:00", "P1", "phone"]],
                   "2026-10-26 00:00", mode="calendar")
        self.assertAlmostEqual(t["D"]["res_hours"], 7.0)

    def test_utc_input(self):
        # 06:30 UTC in April is 08:30 Copenhagen time, 30 business minutes before 09:00 local (07:00 UTC)
        t, _ = run([["E", "2026-04-08 06:30", "2026-04-08 07:00", "", "P2", "email"]], "2026-04-08 08:00",
                   input_tz="utc")
        self.assertAlmostEqual(t["E"]["fr_hours"], 0.5)

    def test_open_breach_and_pending(self):
        t, _ = run([["F", "2026-04-14 14:00", "", "", "P1", "phone"]], "2026-04-15 00:00")
        self.assertEqual(t["F"]["fr_status"], "breached (open)")
        self.assertEqual(t["F"]["res_status"], "pending")
        self.assertAlmostEqual(t["F"]["age_business_h"], 2.0)


class TestStats(unittest.TestCase):
    def test_percentile(self):
        self.assertAlmostEqual(sla.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertAlmostEqual(sla.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9), 9.1)


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        headers, rows = sla.read_csv(ASSET)
        cal = sla.Calendar(sla.parse_open_hours("08:00-16:00", "mon,tue,wed,thu,fri"), "dk")
        tickets, warnings, as_of = sla.analyse(rows, sla.load_targets(None), cal, "business",
                                               datetime(2026, 4, 15, 0, 0))
        rep = sla.build_report(tickets, warnings, as_of, sla.load_targets(None), cal, "business")
        o = rep["overall"]
        self.assertEqual(o["tickets"], 16)
        self.assertEqual(o["open"], 3)
        self.assertEqual((o["fr_met"], o["fr_breached"]), (11, 3))
        self.assertEqual((o["res_met"], o["res_breached"]), (10, 2))
        self.assertAlmostEqual(rep["by_priority"]["P1"]["res_median"], (3 + 55 / 60 + 8 + 55 / 60) / 2)
        joined = " ".join(warnings)
        self.assertIn("duplicate ticket_id T1011", joined)
        self.assertIn("T1010", joined)
        self.assertIn("HASTER", joined)
        self.assertEqual([h["name"] for h in rep["closed_days_in_period"]],
                         ["Skaertorsdag", "Langfredag", "2. paaskedag"])

    def test_cli_and_missing_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sla.main([ASSET, "--as-of", "2026-04-15 00:00"])
        self.assertIn("## Breaches", buf.getvalue())
        bad = os.path.join(HERE, "_bad.csv")
        with open(bad, "w") as fh:
            fh.write("id;created\n1;2026-01-01\n")
        try:
            with self.assertRaises(SystemExit) as cm:
                sla.main([bad])
            self.assertIn("ticket_id", str(cm.exception))
        finally:
            os.remove(bad)


if __name__ == "__main__":
    unittest.main()
