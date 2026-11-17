#!/usr/bin/env python3
"""Dunning list: ageing, priority, next action, statutory interest and lawful reminder fees.

Purpose
  Turns an overdue-invoice export into a prioritised collection list with the next action
  per invoice, Danish statutory late-payment interest, reminder fees within the legal cap and
  B2B fixed compensation. Disputed invoices get no fees, interest or compensation and are
  listed separately.

Input columns (header names case-insensitive; comma or semicolon; "1.234,56" or "1234.56")
  customer, invoice, amount, due_date, disputed (yes/no), b2b (yes/no), reminders_sent
  optional: last_reminder_date (needed to check the minimum spacing between reminders)

Formulas (all policy figures are parameters; verify current values)
  days overdue       = as-of date - due date (only > 0 counts)
  interest           = amount x annual rate / 100 x days overdue / day count
                       annual rate = --contract-rate (agreed contractual rate, user supplied) when
                       given, otherwise statutory = reference rate + margin. --reference-rate
                       (Danmarks Nationalbank, set each 1 January and 1 July) is REQUIRED unless
                       --contract-rate is given; margin default 8 percentage points; day count
                       default 365. Simple interest from the due date.
  reminder fees      = fee (default DKK 100) per reminder, at most --max-reminders (default 3),
                       only when at least --min-days-between (default 10) days since the last.
                       Legal limits, renteloven section 9 b, stk. 2: at most DKK 100 per reminder,
                       at most 3 reminders, at least 10 days apart (verify). User values beyond
                       these limits are reported as warnings.
  B2B compensation   = fixed amount per invoice when b2b = yes, renteloven section 9 a, stk. 3
                       (amount set by executive order, default DKK 310, verify).
  ageing buckets     = 1-30, 31-60, 61-90, over 90 days (configurable with --buckets).
  priority score     = Wa x amount / largest open amount
                       + Wd x min(days overdue / 90, 1)
                       + Wr x min(reminders sent / max reminders, 1)
                       + Wc x min((open overdue invoices of the same customer - 1) / 2, 1)
                       default weights Wa=30 (amount), Wd=40 (days overdue), Wr=15 (reminders),
                       Wc=15 (repeat lateness), total 100; change with --priority-weights.

Example
  python3 scripts/dunning.py assets/overdue_invoices.csv --reference-rate 2.10 --as-of 2026-11-16
"""

import argparse
import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta

# ----------------------------------------------------------------- shared input helpers


class InputError(Exception):
    """Raised for unusable input; the message is shown to the user."""


DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")


def parse_date(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.split(" ")[0].split("T")[0]
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None


def parse_number(raw):
    """Parse Danish '1.234,56' or plain '1234.56'. A lone '1.234' is read as 1234."""
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "").replace(" ", "")
    s = re.sub(r"(?i)^(dkk|kr\.?|eur)", "", s)
    s = re.sub(r"(?i)(dkk|kr\.?|eur)$", "", s)
    if s in ("", "-"):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-") and len(s) > 1:
        neg, s = True, s[:-1]
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if re.fullmatch(r"[-+]?\d{1,3}(,\d{3}){2,}", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        if re.fullmatch(r"[-+]?\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")
    v = float(s)
    return -v if neg else v


def parse_yes_no(raw):
    s = (raw or "").strip().lower()
    if s in ("yes", "y", "ja", "j", "true", "1", "x"):
        return True
    if s in ("no", "n", "nej", "false", "0"):
        return False
    return None


def normalise_header(h):
    return (h or "").strip().lstrip("﻿").strip().lower().replace(" ", "_")


def read_table(path, required, optional=(), aliases=None):
    aliases = aliases or {}
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except FileNotFoundError:
        raise InputError("File not found: %s" % path)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise InputError("%s is empty. Expected columns: %s" % (path, ", ".join(required)))
    delim = ";" if lines[0].count(";") > lines[0].count(",") else ","
    raw_rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)]
    while raw_rows and not any(c.strip() for c in raw_rows[0]):
        raw_rows.pop(0)
    header = [aliases.get(normalise_header(h), normalise_header(h)) for h in raw_rows[0]]
    missing = [c for c in required if c not in header]
    if missing:
        raise InputError("%s is missing column(s): %s. Expected columns: %s%s. Found: %s" % (
            path, ", ".join(missing), ", ".join(required),
            (" (optional: %s)" % ", ".join(optional)) if optional else "", ", ".join(header)))
    rows = []
    for i, raw in enumerate(raw_rows[1:], start=2):
        if not any(c.strip() for c in raw):
            continue
        rec = {"_line": i}
        for j, name in enumerate(header):
            rec[name] = raw[j].strip() if j < len(raw) else ""
        rows.append(rec)
    return rows


def fmt(v, dec=2):
    return ("{:,.%df}" % dec).format(v)


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out)


# ----------------------------------------------------------------- dunning logic

# Legal limits used only to warn about user settings (renteloven section 9 b, stk. 2; verify).
LEGAL_MAX_FEE = 100.0
LEGAL_MAX_REMINDERS = 3
LEGAL_MIN_DAYS_BETWEEN = 10
LIMIT_NOTE = "above the renteloven section 9 b, stk. 2 limit; verify"
DEFAULT_WEIGHTS = {"amount": 30.0, "days": 40.0, "reminders": 15.0, "repeat": 15.0}


def legal_limit_warnings(fee, max_reminders, min_days_between):
    """Warnings for user settings beyond the statutory reminder-fee limits."""
    out = []
    if fee > LEGAL_MAX_FEE:
        out.append("--fee DKK %s per reminder is %s (max DKK %s per reminder)" % (fmt(fee), LIMIT_NOTE, fmt(LEGAL_MAX_FEE, 0)))
    if max_reminders > LEGAL_MAX_REMINDERS:
        out.append("--max-reminders %d is %s (max %d fee-bearing reminders per claim)" % (max_reminders, LIMIT_NOTE, LEGAL_MAX_REMINDERS))
    if min_days_between < LEGAL_MIN_DAYS_BETWEEN:
        out.append("--min-days-between %d is %s (at least %d days between fee-bearing reminders)" % (
            min_days_between, LIMIT_NOTE.replace("above", "below"), LEGAL_MIN_DAYS_BETWEEN))
    return out


def parse_weights(raw):
    w = dict(DEFAULT_WEIGHTS)
    for part in (raw or "").split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise InputError("--priority-weights must look like amount=30,days=40,reminders=15,repeat=15")
        k, v = part.split("=", 1)
        k = k.strip().lower()
        if k not in w:
            raise InputError("--priority-weights: unknown key '%s' (use amount, days, reminders, repeat)" % k)
        try:
            w[k] = float(v)
        except ValueError:
            raise InputError("--priority-weights: '%s' is not a number" % v.strip())
    return w

REQUIRED = ["customer", "invoice", "amount", "due_date", "disputed", "b2b", "reminders_sent"]
OPTIONAL = ["last_reminder_date"]
ALIASES = {"kunde": "customer", "debitor": "customer", "faktura": "invoice", "fakturanr": "invoice",
           "beløb": "amount", "beloeb": "amount", "forfald": "due_date", "due": "due_date",
           "tvist": "disputed", "omtvistet": "disputed", "rykkere": "reminders_sent",
           "sidste_rykker": "last_reminder_date"}


def load(path, warnings):
    rows = read_table(path, REQUIRED, OPTIONAL, ALIASES)
    invs = []
    seen = {}
    for r in rows:
        ln = r["_line"]
        try:
            amt = parse_number(r["amount"])
        except ValueError:
            amt = None
        due = parse_date(r["due_date"])
        if amt is None or due is None:
            warnings.append("line %d (%s %s): missing or invalid amount or due_date, row skipped" % (ln, r["customer"], r["invoice"]))
            continue
        disputed = parse_yes_no(r["disputed"])
        if disputed is None:
            if r["disputed"]:
                warnings.append("line %d: disputed '%s' not understood, treated as no" % (ln, r["disputed"]))
            disputed = False
        b2b = parse_yes_no(r["b2b"])
        if b2b is None:
            warnings.append("line %d (%s): b2b blank or unclear, treated as NOT B2B (no compensation)" % (ln, r["customer"]))
            b2b = False
        try:
            sent = parse_number(r["reminders_sent"])
        except ValueError:
            sent = None
        if sent is None:
            warnings.append("line %d (%s): reminders_sent blank, treated as 0" % (ln, r["customer"]))
            sent = 0
        sent = int(sent)
        if amt <= 0:
            warnings.append("line %d (%s %s): amount %s is not positive (credit note?), row skipped" % (ln, r["customer"], r["invoice"], fmt(amt)))
            continue
        key = r["invoice"].strip().lower()
        if key in seen:
            warnings.append("invoice %s appears twice (lines %d and %d): possible duplicate, second row skipped" % (r["invoice"], seen[key], ln))
            continue
        seen[key] = ln
        last = parse_date(r.get("last_reminder_date", ""))
        invs.append({"customer": r["customer"], "invoice": r["invoice"], "amount": amt, "due": due,
                     "disputed": disputed, "b2b": b2b, "reminders_sent": sent, "last_reminder": last, "line": ln})
    return invs


def bucket_label(days, edges):
    lo = 1
    for e in edges:
        if days <= e:
            return "%d-%d" % (lo, e)
        lo = e + 1
    return "over %d" % edges[-1]


def analyse(invs, as_of, reference_rate, margin=8.0, fee=100.0, max_reminders=3, min_days_between=10,
            b2b_compensation=310.0, day_count=365, edges=(30, 60, 90), warnings=None, contract_rate=None,
            weights=None):
    warnings = warnings if warnings is not None else []
    weights = dict(DEFAULT_WEIGHTS, **(weights or {}))
    limit_warnings = legal_limit_warnings(fee, max_reminders, min_days_between)
    warnings.extend(limit_warnings)
    if contract_rate is not None:
        rate, rate_basis = contract_rate, "contract"
    else:
        if reference_rate is None:
            raise InputError("give --reference-rate (statutory interest) or --contract-rate (agreed rate)")
        rate, rate_basis = reference_rate + margin, "statutory"
    open_items, disputed, not_due = [], [], []
    for inv in invs:
        days = (as_of - inv["due"]).days
        inv = dict(inv, days_overdue=max(days, 0))
        if days <= 0:
            not_due.append(inv)
            continue
        inv["bucket"] = bucket_label(days, edges)
        if inv["disputed"]:
            inv.update(interest=0.0, fees_to_date=0.0, next_fee=0.0, compensation=0.0,
                       action="Disputed: no reminder, fee, interest or compensation. Resolve the dispute and agree the undisputed part.")
            disputed.append(inv)
            continue
        if inv["reminders_sent"] > max_reminders:
            warnings.append("%s: %d reminders recorded, more than the --max-reminders setting of %d; fees counted for %d only" % (
                inv["invoice"], inv["reminders_sent"], max_reminders, max_reminders))
        inv["interest"] = round(inv["amount"] * rate / 100.0 * days / day_count, 2)
        inv["fees_to_date"] = round(min(inv["reminders_sent"], max_reminders) * fee, 2)
        inv["compensation"] = b2b_compensation if inv["b2b"] else 0.0
        n = inv["reminders_sent"]
        earliest = None
        if n > 0 and inv["last_reminder"]:
            earliest = inv["last_reminder"] + timedelta(days=min_days_between)
        if n >= max_reminders:
            inv["next_fee"] = 0.0
            inv["action"] = "Reminder limit reached: phone the customer, then decide on debt collection (your decision)."
        elif earliest and as_of < earliest:
            inv["next_fee"] = 0.0
            inv["action"] = "Wait: next reminder with fee allowed from %s (%d-day rule)." % (earliest.isoformat(), min_days_between)
        else:
            inv["next_fee"] = fee
            label = {0: "1st reminder, friendly", 1: "2nd reminder, firm", 2: "Final reminder, state next step"}.get(n, "Reminder %d" % (n + 1))
            inv["action"] = label + (" (last reminder date unknown: check the %d-day spacing)" % min_days_between
                                     if n > 0 and not inv["last_reminder"] else "")
        inv["claim_after_next"] = round(inv["amount"] + inv["interest"] + inv["fees_to_date"] + inv["next_fee"] + inv["compensation"], 2)
        open_items.append(inv)
    max_amt = max([i["amount"] for i in open_items], default=0.0)
    per_customer = {}
    for i in open_items:
        k = i["customer"].strip().lower()
        per_customer[k] = per_customer.get(k, 0) + 1
    for i in open_items:
        i["customer_open_overdue"] = per_customer[i["customer"].strip().lower()]
        rem = min(i["reminders_sent"] / float(max_reminders), 1.0) if max_reminders > 0 else 0.0
        score = (weights["amount"] * i["amount"] / max_amt if max_amt else 0.0) \
            + weights["days"] * min(i["days_overdue"] / 90.0, 1.0) \
            + weights["reminders"] * rem \
            + weights["repeat"] * min((i["customer_open_overdue"] - 1) / 2.0, 1.0)
        i["priority"] = round(score, 1)
    open_items.sort(key=lambda i: (-i["priority"], i["invoice"]))
    for rank, i in enumerate(open_items, start=1):
        i["rank"] = rank
    labels = ["%d-%d" % (lo, hi) for lo, hi in zip((1,) + tuple(e + 1 for e in edges[:-1]), edges)] + ["over %d" % edges[-1]]
    ageing = []
    for lab in labels:
        o = [i for i in open_items if i["bucket"] == lab]
        d = [i for i in disputed if i["bucket"] == lab]
        ageing.append({"bucket": lab, "count": len(o), "amount": round(sum(i["amount"] for i in o), 2),
                       "disputed_count": len(d), "disputed_amount": round(sum(i["amount"] for i in d), 2)})
    totals = {
        "overdue_undisputed": round(sum(i["amount"] for i in open_items), 2),
        "overdue_disputed": round(sum(i["amount"] for i in disputed), 2),
        "not_yet_due": round(sum(i["amount"] for i in not_due), 2),
        "interest": round(sum(i["interest"] for i in open_items), 2),
        "fees_to_date": round(sum(i["fees_to_date"] for i in open_items), 2),
        "next_fees": round(sum(i["next_fee"] for i in open_items), 2),
        "compensation": round(sum(i["compensation"] for i in open_items), 2),
    }
    return {"as_of": as_of, "rate": rate, "rate_basis": rate_basis, "reference_rate": reference_rate, "margin": margin,
            "limit_warnings": limit_warnings, "weights": weights, "open": open_items,
            "disputed": disputed, "not_due": not_due, "ageing": ageing, "totals": totals, "warnings": warnings,
            "params": {"fee": fee, "max_reminders": max_reminders, "min_days_between": min_days_between,
                       "b2b_compensation": b2b_compensation, "day_count": day_count}}


# ----------------------------------------------------------------- output


def render_markdown(res):
    t = res["totals"]
    p = res["params"]
    out = ["# Collection list at %s" % res["as_of"].isoformat(), ""]
    out.append("Overdue, undisputed: **%s** (%d invoices). Disputed: %s (%d). Not yet due: %s." % (
        fmt(t["overdue_undisputed"]), len(res["open"]), fmt(t["overdue_disputed"]), len(res["disputed"]), fmt(t["not_yet_due"])))
    if res["rate_basis"] == "contract":
        rate_txt = "Interest rate used: %.2f%% = agreed contractual rate (user supplied), used instead of the statutory rate." % res["rate"]
    else:
        rate_txt = "Statutory interest rate used: %.2f%% = reference rate %.2f%% + %.2f pp." % (
            res["rate"], res["reference_rate"], res["margin"])
    out.append(rate_txt + " Interest accrued %s; fees charged to date %s; fees on next reminders %s; B2B compensation %s." % (
        fmt(t["interest"]), fmt(t["fees_to_date"]), fmt(t["next_fees"]), fmt(t["compensation"])))
    for lw in res.get("limit_warnings", []):
        out += ["", "**WARNING: %s. Do not claim fees beyond the legal limit.**" % lw]
    out += ["", "## 1. Prioritised collection list", ""]
    rows = [[i["rank"], i["customer"], i["invoice"], fmt(i["amount"]), i["due"].isoformat(), i["days_overdue"], i["bucket"],
             i["reminders_sent"], fmt(i["interest"]), fmt(i["next_fee"]), fmt(i["compensation"]), fmt(i["claim_after_next"]),
             i["priority"], i["action"]] for i in res["open"]]
    out.append(md_table(["#", "Customer", "Invoice", "Amount", "Due", "Days", "Bucket", "Reminders", "Interest",
                         "Next fee", "B2B comp.", "Claim after next", "Score", "Next action"], rows) if rows else "No undisputed overdue invoices.")
    out += ["", "## 2. Disputed invoices (excluded from fees, interest and compensation)", ""]
    if res["disputed"]:
        out.append(md_table(["Customer", "Invoice", "Amount", "Due", "Days", "Action"],
                            [[i["customer"], i["invoice"], fmt(i["amount"]), i["due"].isoformat(), i["days_overdue"], i["action"]]
                             for i in res["disputed"]]))
    else:
        out.append("None.")
    out += ["", "## 3. Ageing", ""]
    out.append(md_table(["Days overdue", "Invoices", "Amount", "Disputed invoices", "Disputed amount"],
                        [[a["bucket"], a["count"], fmt(a["amount"]), a["disputed_count"], fmt(a["disputed_amount"])] for a in res["ageing"]]))
    out += ["", "## 4. Data quality and assumptions", ""]
    notes = list(res["warnings"])
    if res["rate_basis"] == "contract":
        notes.append("Contractual rate %.2f%% supplied by the user: it replaces the statutory rate only if the customer validly accepted it (check the terms of sale)." % res["rate"])
    else:
        notes.append("Reference rate %.2f%% supplied by the user: verify the current Danmarks Nationalbank rate for the period (it is fixed each 1 January and 1 July)." % res["reference_rate"])
    notes.append("Settings used: reminder fee DKK %s per reminder, at most %d fee-bearing reminders, at least %d days apart. Legal limits (renteloven section 9 b, stk. 2): at most DKK %s per reminder, at most %d reminders, at least %d days apart; verify current values." % (
        fmt(p["fee"], 0), p["max_reminders"], p["min_days_between"], fmt(LEGAL_MAX_FEE, 0), LEGAL_MAX_REMINDERS, LEGAL_MIN_DAYS_BETWEEN))
    notes.append("B2B fixed compensation DKK %s per invoice (renteloven section 9 a, stk. 3; amount set by executive order; verify current value)." % fmt(p["b2b_compensation"], 0))
    notes.append("Interest is simple, from the due date, on a %d-day year. Consumer claims without an agreed due date accrue interest only 30 days after a demand. Check with an adviser." % p["day_count"])
    w = res["weights"]
    notes.append("Priority score = %g x amount / largest + %g x min(days / 90, 1) + %g x min(reminders / max, 1) + %g x min((customer's open overdue invoices - 1) / 2, 1)." % (
        w["amount"], w["days"], w["reminders"], w["repeat"]))
    notes.append("Fees to date assume each reminder sent carried a fee. Escalation to debt collection or a debtor register is the user's decision.")
    out += ["- " + n for n in notes]
    return "\n".join(out)


def to_jsonable(res):
    def conv(v):
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [conv(x) for x in v]
        return v
    return conv(res)


def write_csv(path, res):
    cols = ["rank", "customer", "invoice", "amount", "due", "days_overdue", "bucket", "disputed", "b2b", "reminders_sent",
            "interest", "fees_to_date", "next_fee", "compensation", "claim_after_next", "priority", "action"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in res["open"] + res["disputed"]:
            w.writerow([i.get(c, "") if not isinstance(i.get(c), date) else i[c].isoformat() for c in cols])


class RateParser(argparse.ArgumentParser):
    """Requires --reference-rate unless --contract-rate is given."""

    def parse_args(self, args=None, namespace=None):
        ns = super().parse_args(args, namespace)
        if ns.reference_rate is None and ns.contract_rate is None:
            self.error("--reference-rate is required unless --contract-rate is given")
        return ns


def build_parser():
    p = RateParser(description="Prioritise overdue invoices with Danish statutory interest, reminder fees and B2B compensation.")
    p.add_argument("csv", help="Overdue invoices: " + ", ".join(REQUIRED) + " [, last_reminder_date]")
    p.add_argument("--reference-rate", type=float,
                   help="REQUIRED unless --contract-rate is given. Danmarks Nationalbank reference rate in %% (e.g. 2.10). Verify current value; it changes each 1 January and 1 July.")
    p.add_argument("--margin", type=float, default=8.0, help="Percentage points added to the reference rate (default 8.0; verify current value)")
    p.add_argument("--contract-rate", type=float,
                   help="Agreed annual interest rate in %% from the terms of sale; used instead of the statutory rate when given (only valid if the customer accepted it)")
    p.add_argument("--as-of", help="Date to age from (default: today)")
    p.add_argument("--fee", type=float, default=100.0,
                   help="Reminder fee per reminder in DKK (default 100 = renteloven section 9 b, stk. 2 maximum; verify current value; higher values are flagged)")
    p.add_argument("--max-reminders", type=int, default=3,
                   help="Max reminders that may carry a fee (default 3 = renteloven section 9 b, stk. 2 maximum; verify current value; higher values are flagged)")
    p.add_argument("--min-days-between", "--min-days", dest="min_days_between", type=int, default=10,
                   help="Min days between fee-bearing reminders (default 10 = renteloven section 9 b, stk. 2 minimum; verify current value; lower values are flagged)")
    p.add_argument("--b2b-compensation", type=float, default=310.0,
                   help="Fixed B2B compensation per invoice in DKK, renteloven section 9 a, stk. 3 (amount set by executive order; default 310; verify current value)")
    p.add_argument("--priority-weights", default="",
                   help="Priority weights, e.g. amount=30,days=40,reminders=15,repeat=15 (the defaults). repeat = other open overdue invoices of the same customer")
    p.add_argument("--day-count", type=int, default=365, help="Days per year for interest (default 365)")
    p.add_argument("--buckets", default="30,60,90", help="Ageing bucket upper edges in days (default 30,60,90)")
    p.add_argument("--out", help="Write the detailed list to this CSV")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    warnings = []
    try:
        as_of = parse_date(args.as_of) if args.as_of else date.today()
        if as_of is None:
            raise InputError("--as-of '%s' is not a valid date" % args.as_of)
        try:
            edges = tuple(sorted(int(x) for x in args.buckets.split(",") if x.strip()))
        except ValueError:
            raise InputError("--buckets must be whole numbers, e.g. 30,60,90")
        if not edges:
            raise InputError("--buckets needs at least one number")
        weights = parse_weights(args.priority_weights)
        invs = load(args.csv, warnings)
    except InputError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    if not args.as_of:
        warnings.append("no --as-of given; today's date %s used" % as_of.isoformat())
    res = analyse(invs, as_of, args.reference_rate, margin=args.margin, fee=args.fee, max_reminders=args.max_reminders,
                  min_days_between=args.min_days_between, b2b_compensation=args.b2b_compensation,
                  day_count=args.day_count, edges=edges, warnings=warnings, contract_rate=args.contract_rate,
                  weights=weights)
    if args.out:
        write_csv(args.out, res)
    print(json.dumps(to_jsonable(res), indent=2, ensure_ascii=False) if args.json else render_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
