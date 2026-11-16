import importlib.util
import os
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("dunning", os.path.join(ROOT, "scripts", "dunning.py"))
dn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dn)


def inv(invoice, amount, due, disputed=False, b2b=True, sent=0, last=None):
    return {"customer": "C" + invoice, "invoice": invoice, "amount": amount, "due": due, "disputed": disputed,
            "b2b": b2b, "reminders_sent": sent, "last_reminder": last, "line": 2}


class TestHandBuilt(unittest.TestCase):
    def test_interest_fee_compensation(self):
        res = dn.analyse([inv("A", 10000.0, date(2026, 1, 1))], date(2026, 3, 2), reference_rate=2.0)
        i = res["open"][0]
        self.assertEqual(i["days_overdue"], 60)
        # 10,000 x 10% x 60 / 365 = 164.38
        self.assertEqual(i["interest"], 164.38)
        self.assertEqual(i["next_fee"], 100.0)
        self.assertEqual(i["compensation"], 310.0)
        self.assertEqual(i["claim_after_next"], 10574.38)
        self.assertEqual(i["bucket"], "31-60")

    def test_spacing_cap_and_dispute(self):
        items = [inv("W", 1000.0, date(2026, 1, 1), sent=1, last=date(2026, 2, 25)),
                 inv("M", 1000.0, date(2026, 1, 1), sent=3, last=date(2026, 2, 1)),
                 inv("D", 5000.0, date(2026, 1, 1), disputed=True),
                 inv("N", 700.0, date(2026, 4, 1))]
        res = dn.analyse(items, date(2026, 3, 1), reference_rate=2.0, fee=100.0)
        by = {i["invoice"]: i for i in res["open"]}
        self.assertEqual(by["W"]["next_fee"], 0.0)             # only 4 days since last reminder
        self.assertIn("2026-03-07", by["W"]["action"])
        self.assertEqual(by["M"]["next_fee"], 0.0)             # cap of 3 reached
        self.assertEqual(by["M"]["fees_to_date"], 300.0)
        self.assertEqual([i["invoice"] for i in res["disputed"]], ["D"])
        self.assertEqual(res["disputed"][0]["interest"], 0.0)
        self.assertEqual(res["totals"]["not_yet_due"], 700.0)

    def test_priority(self):
        items = [inv("Big", 1000.0, date(2026, 2, 19)), inv("Old", 500.0, date(2025, 11, 1), sent=3)]
        res = dn.analyse(items, date(2026, 3, 1), reference_rate=2.0)
        by = {i["invoice"]: i for i in res["open"]}
        # Big: 50 x 1 + 30 x 10/90 + 0 = 53.3 ; Old: 25 + 30 + 20 = 75.0
        self.assertEqual(by["Big"]["priority"], 53.3)
        self.assertEqual(by["Old"]["priority"], 75.0)
        self.assertEqual(res["open"][0]["invoice"], "Old")


class TestSample(unittest.TestCase):
    def test_sample(self):
        w = []
        invs = dn.load(os.path.join(ROOT, "assets", "overdue_invoices.csv"), w)
        self.assertTrue(any("appears twice" in x for x in w))
        self.assertTrue(any("b2b blank" in x for x in w))
        res = dn.analyse(invs, date(2026, 11, 16), reference_rate=2.10, warnings=w)
        t = res["totals"]
        self.assertEqual(t["overdue_undisputed"], 426100.00)
        self.assertEqual(t["overdue_disputed"], 126000.00)
        self.assertEqual(t["not_yet_due"], 92300.00)
        top = res["open"][0]
        self.assertEqual(top["invoice"], "2026-362")
        # 210,000 x 10.10% x 16 / 365
        self.assertEqual(top["interest"], 929.75)
        self.assertEqual(t["compensation"], 6 * 310.0)

    def test_reference_rate_required(self):
        with self.assertRaises(SystemExit):
            dn.build_parser().parse_args([os.path.join(ROOT, "assets", "overdue_invoices.csv")])


if __name__ == "__main__":
    unittest.main()
