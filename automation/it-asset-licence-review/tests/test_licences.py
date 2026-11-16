import importlib.util
import os
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("licences", os.path.join(ROOT, "scripts", "licences.py"))
lc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)

SUB_COLS = ["product", "vendor", "licences", "cost_per_licence_month", "renewal_date", "notice_days"]


def rows(*dicts):
    return [dict(d, _line=i) for i, d in enumerate(dicts, start=2)]


def item(res, product):
    return next(i for i in res["items"] if i["product"] == product)


class TestSmallCases(unittest.TestCase):
    def test_waste_and_saving(self):
        subs = rows({"product": "Tool", "vendor": "V", "licences": "10", "cost_per_licence_month": "100",
                     "renewal_date": "2027-06-01", "notice_days": "30"})
        usage = rows(*[{"product": "tool", "user": f"u{i}", "last_active_date": "2026-11-01"} for i in range(6)],
                     {"product": "Tool", "user": "old", "last_active_date": "2026-01-01"})
        res = lc.analyse(subs, usage, date(2026, 11, 16), buffer_pct=10)
        i = item(res, "Tool")
        self.assertEqual(i["active_users"], 6)
        self.assertEqual(i["unused"], 4)
        self.assertEqual(i["waste_monthly"], 400)
        self.assertEqual(i["recommended"], 7)  # ceil(6 x 1.10) = 7
        self.assertEqual(i["saving_annual"], 3 * 100 * 12)
        self.assertEqual(i["notice_deadline"], "2027-05-02")  # 1 Jun 2027 minus 30 days
        # effective 2027-06-01, horizon 2027-11-16: 168 days
        self.assertAlmostEqual(i["saving_next_12m"], 3600 * 168 / 365)

    def test_passed_deadline_and_rollover(self):
        subs = rows({"product": "Chat", "vendor": "V", "licences": "5", "cost_per_licence_month": "50",
                     "renewal_date": "2026-01-10", "notice_days": "60"})
        res = lc.analyse(subs, [], date(2026, 11, 16))
        i = item(res, "Chat")
        self.assertEqual(i["next_renewal"], "2027-01-10")  # rolled forward from 2026-01-10
        self.assertTrue(i["deadline_passed"])  # 2027-01-10 minus 60 days = 2026-11-11
        self.assertEqual(i["effective_date"], "2028-01-10")
        self.assertEqual(i["action_deadline"], "2027-11-11")

    def test_over_deployment_and_duplicates(self):
        subs = rows({"product": "Zoom Pro", "vendor": "Z", "licences": "1", "cost_per_licence_month": "110",
                     "renewal_date": "2027-01-01", "notice_days": "0"},
                    {"product": "Microsoft 365 E3", "vendor": "M", "licences": "2", "cost_per_licence_month": "270",
                     "renewal_date": "2027-01-01", "notice_days": "0"})
        usage = rows({"product": "Zoom Pro", "user": "a", "last_active_date": "2026-11-15"},
                     {"product": "Zoom Pro", "user": "b", "last_active_date": "15-11-2026"})
        res = lc.analyse(subs, usage, date(2026, 11, 16))
        self.assertEqual(item(res, "Zoom Pro")["over_deployed"], 1)
        self.assertIn("video meetings", [d["category"] for d in res["duplicates"]])

    def test_add_months(self):
        self.assertEqual(lc.add_months(date(2026, 1, 31), 1), date(2026, 2, 28))


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        _, subs = lc.read_csv(os.path.join(ROOT, "assets", "subscriptions_template.csv"), SUB_COLS)
        _, usage = lc.read_csv(os.path.join(ROOT, "assets", "usage_template.csv"), ["product", "user", "last_active_date"])
        res = lc.analyse(subs, usage, date(2026, 11, 16))
        t = res["totals"]
        self.assertEqual(t["monthly_cost"], 5525)
        self.assertEqual(t["waste_monthly"], 1510)
        self.assertEqual(t["saving_annual"], 12240)
        self.assertEqual(item(res, "Adobe Acrobat Pro")["active_users"], 2)
        self.assertEqual(item(res, "Slack Pro")["saving_next_12m"], 0)
        self.assertEqual(item(res, "AutoCAD LT")["over_deployed"], 1)
        w = " ".join(res["warnings"])
        self.assertIn("duplicates line", w)
        self.assertIn("canva pro", w)
        self.assertIn("cost_per_licence_month missing", w)

    def test_missing_column(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("product;licences\nX;3\n")
        with self.assertRaises(ValueError) as cm:
            lc.read_csv(fh.name, SUB_COLS)
        os.unlink(fh.name)
        self.assertIn("renewal_date", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
