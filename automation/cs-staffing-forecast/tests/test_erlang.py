import importlib.util
import io
import math
import os
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("erlang", os.path.join(UNIT, "scripts", "erlang.py"))
erlang = importlib.util.module_from_spec(spec)
spec.loader.exec_module(erlang)
ASSET = os.path.join(UNIT, "assets", "intervals_template.csv")


class TestErlang(unittest.TestCase):
    def test_erlang_b_and_c_by_hand(self):
        # B(1)=2/3, B(2)=0.4, B(3)=0.8/3.8; C(3, 2) = 4/9
        self.assertAlmostEqual(erlang.erlang_b(2, 2.0), 0.4)
        self.assertAlmostEqual(erlang.erlang_b(3, 2.0), 0.8 / 3.8)
        self.assertAlmostEqual(erlang.erlang_c(3, 2.0), 4 / 9)
        self.assertEqual(erlang.erlang_c(2, 2.0), 1.0)

    def test_service_level_and_asa_by_hand(self):
        # N=3, A=2, AHT 180 s, T 20 s: SL = 1 - 4/9 * exp(-1 * 20/180); ASA = 4/9 * 180 / 1 = 80 s
        m = erlang.metrics(3, 2.0, 180, 20)
        self.assertAlmostEqual(m["sl"], 1 - 4 / 9 * math.exp(-20 / 180))
        self.assertAlmostEqual(m["asa"], 80.0)
        self.assertAlmostEqual(m["occupancy"], 2 / 3)

    def test_large_traffic_is_stable(self):
        n, m, _ = erlang.required_agents(500.0, 300, 0.8, 20, 1.0)
        self.assertTrue(500 < n < 560)
        self.assertGreaterEqual(m["sl"], 0.8)

    def test_black_friday_hour(self):
        # 88 calls in 60 min, AHT 330 s: A = 8.07 Erlangs, 11 agents give 80.4% in 30 s.
        # Cross-check against the closed-form Erlang C with factorials.
        a = 88 * 330 / 3600
        top = a ** 11 / math.factorial(11) * 11 / (11 - a)
        c = top / (sum(a ** k / math.factorial(k) for k in range(11)) + top)
        n, m, binding = erlang.required_agents(a, 330, 0.8, 30, 1.0)
        self.assertEqual(n, 11)
        self.assertAlmostEqual(m["pw"], c)
        self.assertAlmostEqual(m["sl"], 1 - c * math.exp(-(11 - a) * 30 / 330))
        self.assertAlmostEqual(m["sl"], 0.8044, places=4)
        self.assertEqual(binding, "service level")

    def test_occupancy_cap_binds(self):
        n_free, _, _ = erlang.required_agents(40.0, 300, 0.5, 60, 1.0)
        n_cap, m, binding = erlang.required_agents(40.0, 300, 0.5, 60, 0.85)
        self.assertEqual(n_cap, 48)  # 40 / 48 = 83.3%, 40 / 47 = 85.1%
        self.assertLess(n_free, n_cap)
        self.assertEqual(binding, "max occupancy")

    def test_shrinkage_and_totals(self):
        rep = erlang.analyse([{"label": "a", "contacts": 0}, {"label": "b", "contacts": 0}], 300, 30, 0.8, 20, 0.85,
                             0.3, min_agents=2)
        self.assertEqual(rep["totals"]["agent_hours"], 2.0)
        self.assertAlmostEqual(rep["totals"]["paid_hours"], 2 / 0.7)
        self.assertEqual(rep["intervals"][0]["scheduled_rounded"], 3)


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        intervals, warnings = erlang.load_intervals(ASSET, 30)
        self.assertEqual(len(intervals), 16)
        w = " ".join(warnings)
        self.assertIn("duplicate interval", w)
        self.assertIn("contacts missing", w)
        self.assertIn("Gap in intervals", w)
        rep = erlang.analyse(intervals, 330, 30, 0.8, 30, 0.85, 0.3)
        self.assertEqual(rep["totals"]["contacts"], 430)
        first = rep["intervals"][0]
        self.assertAlmostEqual(first["erlangs"], 14 * 330 / 1800)
        self.assertEqual(first["agents"], 5)
        for r in rep["intervals"]:
            self.assertGreaterEqual(r["service_level"], 0.8)
            self.assertLessEqual(r["occupancy"], 0.85)

    def test_cli_contacts_and_missing_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            erlang.main(["--contacts", "88", "--interval-minutes", "60", "--aht", "330", "--answer-time", "30",
                         "--max-occupancy", "1"])
        self.assertIn("| interval 1 | 88 | 8.07 | 11 | 80.4%", buf.getvalue())
        bad = os.path.join(HERE, "_bad.csv")
        with open(bad, "w") as fh:
            fh.write("time;calls\n08:00;10\n")
        try:
            with self.assertRaises(SystemExit) as cm:
                erlang.main([bad])
            self.assertIn("interval_start", str(cm.exception))
        finally:
            os.remove(bad)

    def test_danish_numbers(self):
        self.assertEqual(erlang.parse_number("1.234,5", ";"), 1234.5)
        self.assertEqual(erlang.parse_number("12,5", ","), 12.5)
        self.assertEqual(erlang.parse_number("1.234", ";"), 1234.0)


class TestAvailable(unittest.TestCase):
    def _write(self, name, text):
        path = os.path.join(HERE, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_gap_and_achievable_service_level_by_hand(self):
        # 88 calls, 60 min, AHT 330 s: A = 8.0667, 11 agents required (max occupancy 1).
        # With 10 available: gap -1, SL from Erlang C with N = 10.
        a = 88 * 330 / 3600
        top = a ** 10 / math.factorial(10) * 10 / (10 - a)
        c10 = top / (sum(a ** k / math.factorial(k) for k in range(10)) + top)
        rep = erlang.analyse([{"label": "x", "contacts": 88, "available": 10},
                              {"label": "y", "contacts": 88, "available": 13}], 330, 60, 0.8, 30, 1.0, 0.3)
        s = erlang.available_metrics(rep)
        x, y = rep["intervals"]
        self.assertEqual((x["agents"], x["available_on_queue"], x["gap"], x["gap_status"]), (11, 10, -1, "shortfall"))
        self.assertAlmostEqual(x["available_service_level"], 1 - c10 * math.exp(-(10 - a) * 30 / 330))
        self.assertEqual((y["gap"], y["gap_status"]), (2, "surplus"))
        self.assertEqual(s["intervals_short"], 1)
        self.assertEqual((s["shortfall_agent_hours"], s["surplus_agent_hours"]), (1.0, 2.0))
        # scheduled basis: 11 scheduled x 0.7 = 7.7 -> 7 on queue <= A 8.07, unstable queue, SL 0
        rep = erlang.analyse([{"label": "x", "contacts": 88, "available": 11}], 330, 60, 0.8, 30, 1.0, 0.3)
        erlang.available_metrics(rep, "scheduled")
        self.assertEqual(rep["intervals"][0]["available_on_queue"], 7)
        self.assertEqual(rep["intervals"][0]["available_service_level"], 0.0)

    def test_cli_available_file_column_and_list(self):
        import json
        av = self._write("_av.csv", "interval_start;agents_available\n2026-11-30 08:00;3\n2026-11-30 08:30;9\n"
                                    "2026-11-30 23:00;4\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            erlang.main([ASSET, "--aht", "330", "--answer-time", "30", "--available", av, "--json"])
        data = json.loads(buf.getvalue())
        first, second = data["intervals"][0], data["intervals"][1]
        self.assertEqual((first["agents"], first["gap"]), (5, -2))
        self.assertEqual(second["gap_status"], "surplus")
        self.assertEqual(data["available_summary"]["intervals_with_data"], 2)
        self.assertTrue(any("match no interval" in w for w in data["warnings"]))
        col = self._write("_col.csv", "interval_start,contacts,agents_available\n08:00,14,5\n08:30,22,4\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            erlang.main([col, "--aht", "330", "--answer-time", "30"])
        self.assertIn("## Available agents vs requirement", buf.getvalue())
        self.assertIn("| 08:30 | 7 | 4 | -3 | shortfall |", buf.getvalue())
        buf = io.StringIO()
        with redirect_stdout(buf):
            erlang.main(["--contacts", "88", "--interval-minutes", "60", "--aht", "330", "--answer-time", "30",
                         "--max-occupancy", "1", "--available", "11"])
        self.assertIn("| interval 1 | 11 | 11 | +0 | exact | 80.4%", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
