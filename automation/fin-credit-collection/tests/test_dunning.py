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
        # weights 30/40/15/15. Big: 30 x 1 + 40 x 10/90 + 0 + 0 = 34.4 ; Old: 15 + 40 + 15 + 0 = 70.0
        self.assertEqual(by["Big"]["priority"], 34.4)
        self.assertEqual(by["Old"]["priority"], 70.0)
        self.assertEqual(res["open"][0]["invoice"], "Old")

    def test_priority_days_and_repeat_lateness_beat_amount(self):
        # Big: 100,000, 5 days, single invoice: 30 + 40 x 5/90 = 32.2
        # Rep1/Rep2: same customer, 20,000 each, 60 days:
        #   30 x 0.2 + 40 x 60/90 + 0 + 15 x min((2 - 1) / 2, 1) = 6 + 26.67 + 7.5 = 40.2
        items = [inv("Big", 100000.0, date(2026, 2, 24)),
                 inv("Rep1", 20000.0, date(2025, 12, 31)), inv("Rep2", 20000.0, date(2025, 12, 31))]
        for i in items[1:]:
            i["customer"] = "Slow Payer ApS"
        res = dn.analyse(items, date(2026, 3, 1), reference_rate=2.0)
        by = {i["invoice"]: i for i in res["open"]}
        self.assertEqual(by["Big"]["priority"], 32.2)
        self.assertEqual(by["Rep1"]["priority"], 40.2)
        self.assertEqual(by["Rep1"]["customer_open_overdue"], 2)
        self.assertEqual(res["open"][-1]["invoice"], "Big")
        # custom weights: amount only reproduces a pure size ranking
        res2 = dn.analyse(items, date(2026, 3, 1), reference_rate=2.0,
                          weights=dn.parse_weights("amount=100,days=0,reminders=0,repeat=0"))
        self.assertEqual(res2["open"][0]["invoice"], "Big")

    def test_legal_limit_warnings(self):
        res = dn.analyse([inv("A", 1000.0, date(2026, 1, 1))], date(2026, 3, 1), reference_rate=2.0,
                         fee=150.0, max_reminders=4, min_days_between=7)
        lw = res["limit_warnings"]
        self.assertEqual(len(lw), 3)
        self.assertTrue(all("renteloven section 9 b, stk. 2 limit; verify" in x for x in lw))
        self.assertIn("above", lw[0])
        self.assertIn("below", lw[2])
        md = dn.render_markdown(res)
        self.assertIn("**WARNING: --fee DKK 150.00", md)
        self.assertNotIn("cap", md.lower())
        ok = dn.analyse([inv("A", 1000.0, date(2026, 1, 1))], date(2026, 3, 1), reference_rate=2.0)
        self.assertEqual(ok["limit_warnings"], [])
        md_ok = dn.render_markdown(ok)
        self.assertNotIn("WARNING", md_ok)
        self.assertIn("renteloven section 9 a, stk. 3", md_ok)
        self.assertNotIn("cap", md_ok.lower())

    def test_contract_rate(self):
        # 10,000 x 12% x 60 / 365 = 197.26
        res = dn.analyse([inv("A", 10000.0, date(2026, 1, 1))], date(2026, 3, 2), reference_rate=None,
                         contract_rate=12.0)
        self.assertEqual(res["rate_basis"], "contract")
        self.assertEqual(res["open"][0]["interest"], 197.26)
        self.assertIn("agreed contractual rate (user supplied)", dn.render_markdown(res))
        # contract rate wins over the statutory rate when both are given
        both = dn.analyse([inv("A", 10000.0, date(2026, 1, 1))], date(2026, 3, 2), reference_rate=2.0,
                          contract_rate=12.0)
        self.assertEqual(both["open"][0]["interest"], 197.26)
        ns = dn.build_parser().parse_args([os.path.join(ROOT, "assets", "overdue_invoices.csv"), "--contract-rate", "12"])
        self.assertEqual(ns.contract_rate, 12.0)


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
        by = {i["invoice"]: i for i in res["open"]}
        # Holst 2026-311: 30 x 84,500/210,000 + 40 x 62/90 + 15 x 1/3 + 15 x 0.5 = 52.1 (second Holst invoice open)
        self.assertEqual(res["open"][0]["invoice"], "2026-311")
        self.assertEqual(by["2026-311"]["priority"], 52.1)
        # 210,000 x 10.10% x 16 / 365
        self.assertEqual(by["2026-362"]["interest"], 929.75)
        self.assertEqual(t["compensation"], 6 * 310.0)

    def test_reference_rate_required(self):
        with self.assertRaises(SystemExit):
            dn.build_parser().parse_args([os.path.join(ROOT, "assets", "overdue_invoices.csv")])


if __name__ == "__main__":
    unittest.main()
