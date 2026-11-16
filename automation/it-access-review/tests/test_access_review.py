import importlib.util
import json
import os
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("access_review", os.path.join(ROOT, "scripts", "access_review.py"))
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

ACC_COLS = ["system", "account", "display_name", "email", "role", "last_login", "is_admin"]
HR_COLS = ["employee_id", "name", "email", "department", "job_role", "status", "end_date"]


def rows(*dicts):
    return [dict(d, _line=i) for i, d in enumerate(dicts, start=2)]


def codes(res, account):
    r = next(x for x in res["results"] if x["account"] == account)
    return [c for c, _ in r["findings"]]


class TestSmallCases(unittest.TestCase):
    def setUp(self):
        self.hr = rows(
            {"employee_id": "1", "name": "Søren Holm", "email": "sh@x.dk", "department": "Finance",
             "job_role": "Bookkeeper", "status": "active", "end_date": ""},
            {"employee_id": "2", "name": "Rasmus Friis", "email": "rf@x.dk", "department": "Sales",
             "job_role": "Sales", "status": "leaver", "end_date": "2026-10-31"},
        )

    def test_leaver_days_and_login_after_end(self):
        acc = rows({"system": "M365", "account": "rf", "display_name": "Rasmus Friis", "email": "RF@x.dk",
                    "role": "User", "last_login": "2026-11-03", "is_admin": "no"})
        res = ar.review(acc, self.hr, date(2026, 11, 16))
        r = res["results"][0]
        self.assertEqual(r["match_method"], "email")
        self.assertIn("16 days later", r["findings"][0][1])
        self.assertIn("LOGIN-AFTER-END", codes(res, "rf"))

    def test_fuzzy_danish_name_and_dormant(self):
        acc = rows({"system": "ERP", "account": "SHOLM", "display_name": "Soren Holm", "email": "",
                    "role": "Accountant", "last_login": "2026-08-01", "is_admin": "no"})
        res = ar.review(acc, self.hr, date(2026, 11, 16), dormant_days=90)
        r = res["results"][0]
        self.assertEqual(r["match_method"], "fuzzy name")
        self.assertEqual(r["person"], "Søren Holm")
        self.assertIn("107 days ago", dict(r["findings"])["DORMANT"])  # 1 Aug to 16 Nov = 107 days

    def test_generic_orphan_admin(self):
        acc = rows(
            {"system": "M365", "account": "info", "display_name": "Info", "email": "info@x.dk", "role": "Mailbox",
             "last_login": "2026-11-15", "is_admin": "no"},
            {"system": "ERP", "account": "EXT01", "display_name": "Ext Consultant", "email": "c@partner.dk",
             "role": "SUPER", "last_login": "2026-11-15", "is_admin": "yes"},
            {"system": "ERP", "account": "SHOLM", "display_name": "Søren Holm", "email": "sh@x.dk",
             "role": "SUPER", "last_login": "2026-11-15", "is_admin": "yes"},
            {"system": "ERP", "account": "adm-sholm", "display_name": "Søren Holm (admin)", "email": "",
             "role": "SUPER", "last_login": "2026-11-15", "is_admin": "yes"},
        )
        res = ar.review(acc, self.hr, date(2026, 11, 16))
        self.assertEqual(codes(res, "info"), ["SHARED"])
        self.assertEqual(codes(res, "EXT01"), ["ORPHANED"])
        self.assertIn("ADMIN-DAILY", codes(res, "SHOLM"))
        self.assertNotIn("ADMIN-DAILY", codes(res, "adm-sholm"))
        self.assertNotIn("ADMIN-NO-DAILY", codes(res, "adm-sholm"))

    def test_role_map(self):
        acc = rows({"system": "ERP", "account": "SHOLM", "display_name": "Søren Holm", "email": "sh@x.dk",
                    "role": "Accountant|Payroll", "last_login": "2026-11-15", "is_admin": "no"})
        res = ar.review(acc, self.hr, date(2026, 11, 16), role_map={"bookkeeper": {"ERP": ["Accountant"]}})
        detail = dict(res["results"][0]["findings"])["ROLE-MISMATCH"]
        self.assertIn("Payroll", detail)
        self.assertNotIn("Accountant,", detail)


class TestSampleAsset(unittest.TestCase):
    def test_sample(self):
        _, acc = ar.read_csv(os.path.join(ROOT, "assets", "accounts_template.csv"), ACC_COLS)
        _, hr = ar.read_csv(os.path.join(ROOT, "assets", "hr_template.csv"), HR_COLS)
        with open(os.path.join(ROOT, "assets", "role_map_template.json"), encoding="utf-8") as fh:
            rmap = json.load(fh)
        res = ar.review(acc, hr, date(2026, 11, 16), rmap)
        self.assertEqual(res["accounts"], 16)  # 17 rows, one duplicate
        c = res["counts"]
        self.assertEqual(c["LEAVER"], 2)
        self.assertEqual(c["SHARED"], 3)
        self.assertEqual(c["ORPHANED"], 1)
        self.assertEqual(c["ADMIN-DAILY"], 2)
        self.assertEqual(c["ROLE-MISMATCH"], 3)
        self.assertEqual(c["DORMANT"], 3)
        self.assertIn("LOGIN-AFTER-END", codes(res, "rasmus.friis"))
        self.assertTrue(any("duplicates" in w for w in res["warnings"]))
        self.assertTrue(any("31-13-2026" in w for w in res["warnings"]))

    def test_missing_column(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("system;account;email\nM365;x;x@y.dk\n")
        with self.assertRaises(ValueError) as cm:
            ar.read_csv(fh.name, ACC_COLS)
        os.unlink(fh.name)
        self.assertIn("display_name", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
