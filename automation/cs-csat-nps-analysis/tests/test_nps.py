import importlib.util
import io
import json
import math
import os
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("nps", os.path.join(UNIT, "scripts", "nps.py"))
nps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nps)
ASSET = os.path.join(UNIT, "assets", "responses_template.csv")


def rows_from(scores, segments=None, comments=None):
    out = []
    for i, s in enumerate(scores):
        out.append((i + 2, {"response_id": "X%d" % i, "date": "2026-10-01", "score": str(s),
                            "segment": segments[i] if segments else "", "comment": comments[i] if comments else ""}))
    return out


class TestFormulas(unittest.TestCase):
    def test_nps_and_moe(self):
        s = nps.nps_stats([10] * 6 + [8] * 2 + [2] * 2)
        self.assertAlmostEqual(s["score"], 40.0)
        # variance = 0.6 + 0.2 - 0.4^2 = 0.64; MoE = 1.96 * sqrt(0.064) * 100
        self.assertAlmostEqual(s["variance"], 0.64)
        self.assertAlmostEqual(s["moe"], 1.96 * math.sqrt(0.064) * 100)
        self.assertAlmostEqual(s["moe"], 49.58, places=2)

    def test_wilson_8_of_10(self):
        lo, hi = nps.wilson(8, 10)
        self.assertAlmostEqual(lo, 49.02, places=2)
        self.assertAlmostEqual(hi, 94.33, places=2)

    def test_detect_scale(self):
        self.assertEqual(nps.detect_scale([1, 2, 5, 4]), "csat")
        self.assertEqual(nps.detect_scale([0, 3, 5]), "nps")
        self.assertEqual(nps.detect_scale([7, 3]), "nps")

    def test_csat_and_segment_threshold(self):
        scores = [5] * 40 + [2] * 10 + [4] * 20 + [3] * 10
        segs = ["A"] * 50 + ["B"] * 30 + []
        segs += ["C"] * (len(scores) - len(segs))
        rep = nps.analyse(rows_from(scores, segs), min_n=30)
        self.assertEqual(rep["scale"], "csat")
        self.assertAlmostEqual(rep["overall"]["score"], 75.0)  # 60 of 80 scored 4 or 5
        a = [s for s in rep["segments"] if s["segment"] == "A"][0]
        b = [s for s in rep["segments"] if s["segment"] == "B"][0]
        self.assertAlmostEqual(a["score"], 80.0)  # 40 of 50
        self.assertAlmostEqual(b["score"], 66.7, places=1)  # 20 of 30
        # pooled test A vs rest: 0.8 vs 0.6667, pooled 0.75, se = sqrt(.75*.25*(1/50+1/30))
        se = math.sqrt(0.75 * 0.25 * (1 / 50 + 1 / 30)) * 100
        self.assertAlmostEqual(a["z"], (80 - 200 / 3) / se)
        self.assertFalse(a["meaningful"])  # z = 1.33

    def test_small_segment_not_scored(self):
        rep = nps.analyse(rows_from([10] * 31 + [0] * 5, ["big"] * 31 + ["small"] * 5), min_n=30)
        small = [s for s in rep["segments"] if s["segment"] == "small"][0]
        self.assertNotIn("score", small)
        self.assertIn("below minimum", small["status"])

    def test_themes_danish_and_english(self):
        rep = nps.analyse(rows_from([2, 3, 9], comments=["Ventede længe på svar", "The app keeps crashing",
                                                         "Apparently fine"]), min_n=1)
        t = {x["theme"]: x["comments"] for x in rep["themes"]}
        self.assertEqual(t["waiting and response time"], 1)
        self.assertEqual(t["chatbot and self-service"], 1)  # "Apparently" must not match "app"

    def test_theme_override(self):
        rep = nps.analyse(rows_from([2], comments=["Kassen var flækket"]), min_n=1, themes={"packaging": ["kasse*"]})
        self.assertEqual(rep["themes"][0]["comments"], 1)


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        headers, rows = nps.read_csv(ASSET)
        rep = nps.analyse(rows, min_n=5)
        o = rep["overall"]
        self.assertEqual(rep["scale"], "nps")
        self.assertEqual((o["n"], o["promoters"], o["passives"], o["detractors"]), (17, 8, 2, 7))
        self.assertAlmostEqual(o["score"], 100 / 17)
        var = 15 / 17 - (1 / 17) ** 2
        self.assertAlmostEqual(o["moe"], 1.96 * math.sqrt(var / 17) * 100)
        w = " ".join(rep["warnings"])
        self.assertIn("duplicate response_id R017", w)
        self.assertIn("R018", w)
        self.assertIn("R019", w)

    def test_cli_json_and_missing_columns(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            nps.main([ASSET, "--json", "--min-n", "5"])
        self.assertEqual(json.loads(buf.getvalue())["overall"]["n"], 17)
        bad = os.path.join(HERE, "_bad.csv")
        with open(bad, "w") as fh:
            fh.write("id;rating\n1;9\n")
        try:
            with self.assertRaises(SystemExit) as cm:
                nps.main([bad])
            self.assertIn("response_id", str(cm.exception))
        finally:
            os.remove(bad)


if __name__ == "__main__":
    unittest.main()
