#!/usr/bin/env python3
"""Bank reconciliation: match a bank statement export against the ledger cash account.

Purpose
  Deterministic matching of bank and ledger lines, classification of what is left,
  and a reconciliation statement from the balance per bank to the balance per ledger.

Input columns (both files, header names case-insensitive)
  date, text, amount
  Danish headers are accepted too: dato, tekst, beloeb/beløb.
  Delimiter comma or semicolon (auto-detected). Amounts "1.234,56" or "1234.56".
  Dates yyyy-mm-dd or dd-mm-yyyy (also dd.mm.yyyy and dd/mm/yyyy).
  Sign convention for BOTH files: positive = money into the account, negative = money out.

Matching passes (each line is used at most once)
  1. One-to-one: identical amount (to the cent), dates within --window days (default 5).
     Pairs are taken in order of smallest date gap.
  2. One-to-many: one line equals the sum of 2 to --max-group (default 3) unmatched lines
     on the OTHER side, all with the same sign, all within --window days of the single line.
     Tried bank-to-ledger first, then ledger-to-bank; smaller groups first.
  3. Fuzzy: identical amount, text similarity >= --similarity (default 0.5) and dates within
     --fuzzy-window days (default 45).
  Text similarity = max(difflib ratio, share of the shorter text's words found in the other).

Flags on unmatched lines
  possible sign error   : bank amount = -(ledger amount), similar text or within --window days
  possible amount diff. : similar text, same sign, difference <= --amount-tolerance-pct (FX, fees)
  possible duplicate    : same side, same amount, dates within --dup-days, similar text (all lines)
  old item              : age at --as-of greater than --old-days (default 60)

Reconciliation statement (formula)
  computed ledger balance = bank balance
                            + ledger lines not in bank (receipts and payments, signed)
                            - bank lines not in ledger (signed)
  unexplained difference  = ledger balance (parameter) - computed ledger balance
  Zero means the difference is fully explained by the listed items. Both files must cover
  everything since the last fully reconciled date, including old open items.

Example
  python3 scripts/reconcile.py assets/bank_statement.csv assets/ledger.csv \
      --bank-balance 150371.58 --ledger-balance 350073.00
"""

import argparse
import csv
import difflib
import io
import itertools
import json
import re
import sys
from datetime import date, datetime

# ----------------------------------------------------------------- shared input helpers


class InputError(Exception):
    """Raised for unusable input; the message is shown to the user."""


DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")


def parse_date(raw):
    """Return a date or None. Accepts ISO and Danish day-first formats."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.split(" ")[0].split("T")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(raw):
    """Parse '1.234,56', '1234.56', '-48.750,00', '1,234.56', '(500)' or '500-'.

    A single dot followed by exactly three digits (e.g. '1.234') is read as a Danish
    thousands separator, i.e. 1234. Returns None for blank input; raises ValueError
    for text that is not a number.
    """
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
    value = float(s)
    return -value if neg else value


def normalise_header(h):
    return (h or "").strip().lstrip("﻿").strip().lower().replace(" ", "_")


def read_table(path, required, optional=(), aliases=None):
    """Read a CSV with auto-detected delimiter. Returns (rows, warnings).

    Each row is a dict keyed by canonical column name plus '_line' (file line number).
    """
    aliases = aliases or {}
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except FileNotFoundError:
        raise InputError("File not found: %s" % path)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise InputError("%s is empty. Expected columns: %s" % (path, ", ".join(required)))
    header_line = lines[0]
    delimiter = ";" if header_line.count(";") > header_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows_raw = [r for r in reader]
    while rows_raw and not any(c.strip() for c in rows_raw[0]):
        rows_raw.pop(0)
    header = [aliases.get(normalise_header(h), normalise_header(h)) for h in rows_raw[0]]
    missing = [c for c in required if c not in header]
    if missing:
        raise InputError(
            "%s is missing column(s): %s. Expected columns: %s%s. Found: %s"
            % (
                path,
                ", ".join(missing),
                ", ".join(required),
                (" (optional: %s)" % ", ".join(optional)) if optional else "",
                ", ".join(header),
            )
        )
    rows, warnings = [], []
    for i, raw in enumerate(rows_raw[1:], start=2):
        if not any(c.strip() for c in raw):
            continue
        rec = {"_line": i}
        for j, name in enumerate(header):
            rec[name] = raw[j].strip() if j < len(raw) else ""
        rows.append(rec)
    return rows, warnings


def fmt(v):
    return "" if v is None else "{:,.2f}".format(v)


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out)


# ----------------------------------------------------------------- reconciliation logic

ALIASES = {
    "dato": "date", "bogfoeringsdato": "date", "bogføringsdato": "date", "posteringsdato": "date",
    "tekst": "text", "beskrivelse": "text", "description": "text", "posteringstekst": "text",
    "beløb": "amount", "beloeb": "amount", "belob": "amount",
}

FEE_WORDS = re.compile(r"(?i)gebyr|\bfee|charge|omkostning")
INTEREST_WORDS = re.compile(r"(?i)\brente|\brenter|interest")


def load_side(path, side):
    rows, warnings = read_table(path, ["date", "text", "amount"], (), ALIASES)
    items = []
    prefix = "B" if side == "bank" else "L"
    for r in rows:
        d = parse_date(r["date"])
        try:
            a = parse_number(r["amount"])
        except ValueError:
            warnings.append("%s line %d: amount '%s' is not a number, row skipped" % (side, r["_line"], r["amount"]))
            continue
        if d is None:
            warnings.append("%s line %d: missing or unreadable date '%s', row skipped" % (side, r["_line"], r["date"]))
            continue
        if a is None:
            warnings.append("%s line %d: missing amount, row skipped" % (side, r["_line"]))
            continue
        if not r["text"]:
            warnings.append("%s line %d: empty text" % (side, r["_line"]))
        items.append({
            "id": "%s%d" % (prefix, len(items) + 1), "side": side, "line": r["_line"], "date": d,
            "text": r["text"], "amount": round(a, 2), "cents": int(round(a * 100)),
            "status": "unmatched", "match_id": "", "match_type": "", "category": "", "flags": [],
        })
    return items, warnings


def _words(text):
    return [w for w in re.split(r"[^0-9a-zæøå]+", text.lower()) if len(w) >= 3 or w.isdigit()]


def similarity(a, b):
    """max(difflib ratio of normalised text, share of shorter text's words present in the other)."""
    na = " ".join(_words(a))
    nb = " ".join(_words(b))
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    wa, wb = set(na.split()), set(nb.split())
    overlap = len(wa & wb) / float(min(len(wa), len(wb)))
    return round(max(ratio, overlap), 3)


def reconcile(bank, ledger, window=5, max_group=3, similarity_min=0.5, fuzzy_window=45,
              dup_days=3, old_days=60, amount_tol_pct=2.0, as_of=None,
              bank_balance=None, ledger_balance=None):
    for it in bank + ledger:
        it.update(status="unmatched", match_id="", match_type="", category="", flags=[])
    all_items = bank + ledger
    if as_of is None:
        as_of = max([it["date"] for it in all_items]) if all_items else date.today()
    counter = [0]

    def new_match():
        counter[0] += 1
        return "M%d" % counter[0]

    def gap(x, y):
        return abs((x["date"] - y["date"]).days)

    # Pass 1: one-to-one
    cands = []
    for bi, b in enumerate(bank):
        for li, l in enumerate(ledger):
            if b["cents"] == l["cents"] and gap(b, l) <= window:
                cands.append((gap(b, l), bi, li))
    for _, bi, li in sorted(cands):
        b, l = bank[bi], ledger[li]
        if b["status"] == "unmatched" and l["status"] == "unmatched":
            mid = new_match()
            for x in (b, l):
                x.update(status="matched", match_id=mid, match_type="1:1")

    # Pass 2: one-to-many
    for one_side, many_side in ((bank, ledger), (ledger, bank)):
        for x in sorted(one_side, key=lambda t: (t["date"], t["id"])):
            if x["status"] != "unmatched" or x["cents"] == 0:
                continue
            pool = [y for y in many_side if y["status"] == "unmatched" and y["cents"] != 0
                    and (y["cents"] > 0) == (x["cents"] > 0) and gap(x, y) <= window
                    and abs(y["cents"]) < abs(x["cents"])]
            pool.sort(key=lambda y: (gap(x, y), y["id"]))
            pool = pool[:20]
            found = None
            for k in range(2, max_group + 1):
                for combo in itertools.combinations(pool, k):
                    if sum(y["cents"] for y in combo) == x["cents"]:
                        found = combo
                        break
                if found:
                    break
            if found:
                mid = new_match()
                x.update(status="matched", match_id=mid, match_type="1:%d" % len(found))
                for y in found:
                    y.update(status="matched", match_id=mid, match_type="1:%d" % len(found))

    # Pass 3: fuzzy text with amount match, wider date window
    cands = []
    for bi, b in enumerate(bank):
        if b["status"] != "unmatched":
            continue
        for li, l in enumerate(ledger):
            if l["status"] != "unmatched" or b["cents"] != l["cents"] or gap(b, l) > fuzzy_window:
                continue
            s = similarity(b["text"], l["text"])
            if s >= similarity_min:
                cands.append((-s, gap(b, l), bi, li))
    for _, _, bi, li in sorted(cands):
        b, l = bank[bi], ledger[li]
        if b["status"] == "unmatched" and l["status"] == "unmatched":
            mid = new_match()
            for x in (b, l):
                x.update(status="matched", match_id=mid, match_type="fuzzy")

    # Flags: sign errors
    sign_pairs, amount_pairs = [], []
    cands = []
    for bi, b in enumerate(bank):
        for li, l in enumerate(ledger):
            if b["status"] == "unmatched" and l["status"] == "unmatched" and b["cents"] == -l["cents"] and b["cents"] != 0:
                s = similarity(b["text"], l["text"])
                if (s >= similarity_min and gap(b, l) <= fuzzy_window) or gap(b, l) <= window:
                    cands.append((-s, gap(b, l), bi, li))
    used = set()
    for _, _, bi, li in sorted(cands):
        if ("b", bi) in used or ("l", li) in used:
            continue
        used.update({("b", bi), ("l", li)})
        b, l = bank[bi], ledger[li]
        b["flags"].append("possible sign error vs %s" % l["id"])
        l["flags"].append("possible sign error vs %s" % b["id"])
        sign_pairs.append((b, l))

    # Flags: amount differences (FX, fees, rounding)
    cands = []
    for bi, b in enumerate(bank):
        for li, l in enumerate(ledger):
            if ("b", bi) in used or ("l", li) in used:
                continue
            if b["status"] != "unmatched" or l["status"] != "unmatched" or b["cents"] == l["cents"]:
                continue
            if (b["cents"] > 0) != (l["cents"] > 0) or gap(b, l) > fuzzy_window:
                continue
            diff = abs(b["cents"] - l["cents"])
            if diff <= abs(l["cents"]) * amount_tol_pct / 100.0:
                s = similarity(b["text"], l["text"])
                if s >= similarity_min:
                    cands.append((-s, diff, bi, li))
    for _, _, bi, li in sorted(cands):
        if ("b", bi) in used or ("l", li) in used:
            continue
        used.update({("b", bi), ("l", li)})
        b, l = bank[bi], ledger[li]
        d = round(b["amount"] - l["amount"], 2)
        b["flags"].append("possible amount difference vs %s (%s)" % (l["id"], fmt(d)))
        l["flags"].append("possible amount difference vs %s (%s)" % (b["id"], fmt(d)))
        amount_pairs.append((b, l, d))

    # Flags: duplicates within a side (matched or not)
    duplicates = []
    for side_items in (bank, ledger):
        for i, x in enumerate(side_items):
            for y in side_items[i + 1:]:
                if x["cents"] == y["cents"] and gap(x, y) <= dup_days and similarity(x["text"], y["text"]) >= 0.8:
                    x["flags"].append("possible duplicate of %s" % y["id"])
                    y["flags"].append("possible duplicate of %s" % x["id"])
                    duplicates.append((x, y))

    # Old items and categories
    for it in all_items:
        it["age_days"] = (as_of - it["date"]).days
        if it["status"] != "unmatched":
            it["category"] = "matched"
            continue
        if it["age_days"] > old_days:
            it["flags"].append("old item, %d days" % it["age_days"])
        fl = " ".join(it["flags"])
        if "sign error" in fl:
            cat = "Error: possible sign error"
        elif "duplicate" in fl:
            cat = "Possible duplicate"
        elif "amount difference" in fl:
            cat = "Amount difference (FX, fee or rounding)"
        elif it["age_days"] > old_days:
            cat = "Old item (over %d days)" % old_days
        elif FEE_WORDS.search(it["text"]):
            cat = "Bank fees"
        elif INTEREST_WORDS.search(it["text"]):
            cat = "Interest"
        elif it["side"] == "ledger" and it["age_days"] <= window:
            cat = "Timing (in ledger, not yet in bank)"
        elif it["side"] == "bank":
            cat = "Missing in ledger"
        else:
            cat = "In ledger, not in bank: investigate"
        it["category"] = cat

    un_bank = [x for x in bank if x["status"] == "unmatched"]
    un_ledger = [x for x in ledger if x["status"] == "unmatched"]
    r2 = lambda v: round(v + 0.0, 2)
    st = {
        "bank_balance": bank_balance,
        "ledger_receipts_not_in_bank": r2(sum(x["amount"] for x in un_ledger if x["amount"] > 0)),
        "ledger_payments_not_in_bank": r2(sum(x["amount"] for x in un_ledger if x["amount"] < 0)),
        "bank_receipts_not_in_ledger": r2(-sum(x["amount"] for x in un_bank if x["amount"] > 0)),
        "bank_payments_not_in_ledger": r2(-sum(x["amount"] for x in un_bank if x["amount"] < 0)),
    }
    net_items = r2(st["ledger_receipts_not_in_bank"] + st["ledger_payments_not_in_bank"]
                   + st["bank_receipts_not_in_ledger"] + st["bank_payments_not_in_ledger"])
    st["net_reconciling_items"] = net_items
    st["computed_ledger_balance"] = r2(bank_balance + net_items) if bank_balance is not None else None
    st["ledger_balance"] = ledger_balance
    if bank_balance is not None and ledger_balance is not None:
        st["unexplained_difference"] = r2(ledger_balance - st["computed_ledger_balance"])
    else:
        st["unexplained_difference"] = None

    matched_summary = {}
    for it in all_items:
        if it["status"] == "matched":
            key = it["match_type"] if it["match_type"] in ("1:1", "fuzzy") else "1:many"
            m = matched_summary.setdefault(key, {"matches": set(), "bank_lines": 0, "ledger_lines": 0, "bank_total": 0.0})
            m["matches"].add(it["match_id"])
            m[it["side"] + "_lines"] += 1
            if it["side"] == "bank":
                m["bank_total"] += it["amount"]
    for m in matched_summary.values():
        m["matches"] = len(m["matches"])
        m["bank_total"] = round(m["bank_total"], 2)

    return {
        "as_of": as_of, "statement": st, "matched_summary": matched_summary,
        "unmatched_bank": un_bank, "unmatched_ledger": un_ledger,
        "sign_errors": sign_pairs, "amount_differences": amount_pairs, "duplicates": duplicates,
        "old_items": [x for x in un_bank + un_ledger if x["age_days"] > old_days],
        "items": all_items,
    }


# ----------------------------------------------------------------- output


def render_markdown(res, warnings, args):
    st = res["statement"]
    out = ["# Bank reconciliation at %s" % res["as_of"].isoformat(), ""]
    n_un = len(res["unmatched_bank"]) + len(res["unmatched_ledger"])
    head = "Lines: %d bank, %d ledger. Unmatched: %d bank, %d ledger." % (
        len([i for i in res["items"] if i["side"] == "bank"]), len([i for i in res["items"] if i["side"] == "ledger"]),
        len(res["unmatched_bank"]), len(res["unmatched_ledger"]))
    out.append(head)
    if st["unexplained_difference"] is not None:
        out.append("**Unexplained difference: %s**%s" % (
            fmt(st["unexplained_difference"]),
            " (fully explained by the items listed)" if abs(st["unexplained_difference"]) < 0.005 else
            " (NOT explained: check balances, period coverage and opening open items)"))
    out += ["", "## 1. Reconciliation statement", ""]
    rows = [
        ["Balance per bank statement", fmt(st["bank_balance"]) if st["bank_balance"] is not None else "not provided"],
        ["Add: receipts in ledger not yet in bank", fmt(st["ledger_receipts_not_in_bank"])],
        ["Less: payments in ledger not yet in bank", fmt(st["ledger_payments_not_in_bank"])],
        ["Less: receipts in bank not in ledger", fmt(st["bank_receipts_not_in_ledger"])],
        ["Add: payments in bank not in ledger", fmt(st["bank_payments_not_in_ledger"])],
        ["Computed balance per ledger", fmt(st["computed_ledger_balance"]) if st["computed_ledger_balance"] is not None else "n/a"],
        ["Balance per ledger (given)", fmt(st["ledger_balance"]) if st["ledger_balance"] is not None else "not provided"],
        ["Unexplained difference", fmt(st["unexplained_difference"]) if st["unexplained_difference"] is not None else "n/a"],
    ]
    out.append(md_table(["Item", "DKK"], rows))
    out += ["", "## 2. Matched summary", ""]
    ms = res["matched_summary"]
    rows = [[k, v["matches"], v["bank_lines"], v["ledger_lines"], fmt(v["bank_total"])] for k, v in sorted(ms.items())]
    out.append(md_table(["Match type", "Matches", "Bank lines", "Ledger lines", "Bank amount"], rows) if rows else "No matches.")
    special = [i for i in res["items"] if i["status"] == "matched" and i["match_type"] != "1:1"]
    if special:
        out += ["", "One-to-many and fuzzy matches (check these):", ""]
        out.append(md_table(["Match", "Type", "Side", "Date", "Text", "Amount"],
                            [[i["match_id"], i["match_type"], i["side"], i["date"].isoformat(), i["text"], fmt(i["amount"])]
                             for i in sorted(special, key=lambda t: (int(t["match_id"][1:]), t["side"]))]))
    out += ["", "## 3. Unmatched items by category", ""]
    un = sorted(res["unmatched_bank"] + res["unmatched_ledger"], key=lambda t: (t["category"], t["side"], t["date"], t["id"]))
    if un:
        out.append(md_table(["ID", "Side", "Date", "Text", "Amount", "Category", "Age (days)", "Flags"],
                            [[i["id"], i["side"], i["date"].isoformat(), i["text"], fmt(i["amount"]), i["category"],
                              i["age_days"], "; ".join(i["flags"])] for i in un]))
    else:
        out.append("None.")
    out += ["", "## 4. Flags", ""]
    if res["sign_errors"]:
        out.append("- Possible sign errors: " + "; ".join(
            "%s %s vs %s %s" % (b["id"], fmt(b["amount"]), l["id"], fmt(l["amount"])) for b, l in res["sign_errors"])
            + ". A sign error in the ledger moves the difference by twice the amount.")
    if res["amount_differences"]:
        out.append("- Possible amount differences: " + "; ".join(
            "%s vs %s difference %s" % (b["id"], l["id"], fmt(d)) for b, l, d in res["amount_differences"]))
    if res["duplicates"]:
        out.append("- Possible duplicates: " + "; ".join(
            "%s and %s (%s, %s)" % (x["id"], y["id"], x["side"], fmt(x["amount"])) for x, y in res["duplicates"]))
    if res["old_items"]:
        out.append("- Items older than %d days: " % args.old_days + "; ".join(
            "%s %s %s (%d days)" % (i["id"], i["text"], fmt(i["amount"]), i["age_days"]) for i in res["old_items"]))
    if not (res["sign_errors"] or res["amount_differences"] or res["duplicates"] or res["old_items"]):
        out.append("No flags.")
    out += ["", "## Data quality and assumptions", ""]
    notes = list(warnings)
    if warnings and st["unexplained_difference"] not in (None, 0.0) and any("skipped" in w for w in warnings):
        notes.append("Some rows were skipped; their amounts are not in the matching and may explain the unexplained difference.")
    if st["bank_balance"] is None or st["ledger_balance"] is None:
        notes.append("Closing balances not given (--bank-balance, --ledger-balance), so the difference cannot be tested.")
    notes.append("Sign convention assumed: positive = money in, negative = money out, in both files.")
    notes.append("Matching window %d days, one-to-many up to %d lines, fuzzy similarity >= %.2f within %d days."
                 % (args.window, args.max_group, args.similarity, args.fuzzy_window))
    notes.append("Proposed correcting entries are NOT produced by this script; draft them for review from the categories above.")
    out += ["- " + n for n in notes]
    return "\n".join(out)


def to_jsonable(res, warnings):
    def item(i):
        return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in i.items() if k != "cents"}
    return {
        "as_of": res["as_of"].isoformat(),
        "statement": res["statement"],
        "matched_summary": res["matched_summary"],
        "unmatched_bank": [item(i) for i in res["unmatched_bank"]],
        "unmatched_ledger": [item(i) for i in res["unmatched_ledger"]],
        "old_items": [i["id"] for i in res["old_items"]],
        "sign_errors": [[b["id"], l["id"]] for b, l in res["sign_errors"]],
        "amount_differences": [[b["id"], l["id"], d] for b, l, d in res["amount_differences"]],
        "duplicates": [[x["id"], y["id"]] for x, y in res["duplicates"]],
        "warnings": warnings,
    }


def write_csv(path, res):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "side", "source_line", "date", "text", "amount", "status", "match_id", "match_type",
                    "category", "age_days", "flags"])
        for i in res["items"]:
            w.writerow([i["id"], i["side"], i["line"], i["date"].isoformat(), i["text"], "%.2f" % i["amount"],
                        i["status"], i["match_id"], i["match_type"], i["category"], i["age_days"], "; ".join(i["flags"])])


def build_parser():
    p = argparse.ArgumentParser(description="Reconcile a bank statement CSV against a ledger cash account CSV "
                                            "(columns: date, text, amount; positive = money in).")
    p.add_argument("bank_csv", help="Bank statement export: date, text, amount")
    p.add_argument("ledger_csv", help="Ledger cash account export: date, text, amount")
    p.add_argument("--bank-balance", type=float, help="Closing balance per bank statement")
    p.add_argument("--ledger-balance", type=float, help="Closing balance per ledger account")
    p.add_argument("--as-of", help="Reconciliation date for ageing (default: latest date in the files)")
    p.add_argument("--window", type=int, default=5, help="Date window in days for 1:1 and 1:many matches (default 5)")
    p.add_argument("--max-group", type=int, default=3, help="Max lines summed in a 1:many match (default 3)")
    p.add_argument("--similarity", type=float, default=0.5, help="Min text similarity 0-1 for fuzzy matches (default 0.5)")
    p.add_argument("--fuzzy-window", type=int, default=45, help="Date window in days for fuzzy and sign-error checks (default 45)")
    p.add_argument("--dup-days", type=int, default=3, help="Days apart for duplicate detection on one side (default 3)")
    p.add_argument("--old-days", type=int, default=60, help="Flag unmatched items older than this many days (default 60)")
    p.add_argument("--amount-tolerance-pct", type=float, default=2.0,
                   help="Max %% difference to flag a near match, e.g. FX or fees (default 2.0)")
    p.add_argument("--out", help="Write all lines with match status to this CSV")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        bank, w1 = load_side(args.bank_csv, "bank")
        ledger, w2 = load_side(args.ledger_csv, "ledger")
        as_of = None
        if args.as_of:
            as_of = parse_date(args.as_of)
            if as_of is None:
                raise InputError("--as-of '%s' is not a valid date (use yyyy-mm-dd or dd-mm-yyyy)" % args.as_of)
    except InputError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    res = reconcile(bank, ledger, window=args.window, max_group=args.max_group, similarity_min=args.similarity,
                    fuzzy_window=args.fuzzy_window, dup_days=args.dup_days, old_days=args.old_days,
                    amount_tol_pct=args.amount_tolerance_pct, as_of=as_of,
                    bank_balance=args.bank_balance, ledger_balance=args.ledger_balance)
    warnings = w1 + w2
    if args.out:
        write_csv(args.out, res)
    if args.json:
        print(json.dumps(to_jsonable(res, warnings), indent=2, ensure_ascii=False))
    else:
        print(render_markdown(res, warnings, args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
