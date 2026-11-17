#!/usr/bin/env python3
"""Journal entry testing: rule-based red-flag tests, scored and ranked per journal entry.

Purpose
  Runs documented tests over a journal export and ranks entries by a transparent score so
  the user knows which entries to follow up first. Results are FACTS about postings, not
  findings about people: the report never names or ranks a person as a suspect, and user
  IDs can be masked with --mask-users.

Input columns (header names case-insensitive; comma or semicolon; "1.234,56" or "1234.56")
  entry_id, date, user, account, description, amount, manual (yes/no)   [, time (HH:MM)]

Tests (weight in brackets; an entry scores each test once, however many lines hit it)
  T1 weekend or Danish public holiday posting [2]
     Holidays computed per year: New Year's Day, Maundy Thursday, Good Friday, Easter Sunday,
     Easter Monday, Ascension Day, Whit Sunday, Whit Monday, Christmas Day, Boxing Day,
     Great Prayer Day up to 2023, plus --extra-holidays (default 06-05, 12-24, 12-31).
  T2 out-of-hours posting, time before --work-start or after --work-end [2] (skipped without time)
  T3 round amount: |amount| is a multiple of --round-unit and >= --round-min [1]
  T4 just below approval limit: limit x (1 - --below-pct/100) <= |amount| < limit [3]
     (skipped unless --approval-limit is given)
  T5 duplicate: same account, amount and description in another entry within --dup-days [3]
  T6 manual entry to a revenue or cash account (account starts with --revenue-prefixes or
     --cash-prefixes) [2]
  T7 new or rare user: user not in --known-users, or (without that list) a user with at most
     --rare-user-max entries in the file [2]
  Score = sum of weights of the tests the entry hits. Ranked by score, then largest amount.

Example
  python3 scripts/je_tests.py assets/journal.csv --approval-limit 50000
"""

import argparse
import csv
import io
import json
import re
import sys
from datetime import date, datetime, time, timedelta

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


def parse_time(raw):
    s = (raw or "").strip().replace(".", ":")
    if not s:
        return None
    for f in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, f).time()
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
    if s in ("yes", "y", "ja", "j", "true", "1", "x", "manual", "manuel"):
        return True
    if s in ("no", "n", "nej", "false", "0", "auto", "automatic"):
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


# ----------------------------------------------------------------- Danish holidays


def easter_sunday(year):
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def danish_holidays(year, extra=("06-05", "12-24", "12-31")):
    e = easter_sunday(year)
    days = {
        date(year, 1, 1): "New Year's Day",
        e - timedelta(days=3): "Maundy Thursday",
        e - timedelta(days=2): "Good Friday",
        e: "Easter Sunday",
        e + timedelta(days=1): "Easter Monday",
        e + timedelta(days=39): "Ascension Day",
        e + timedelta(days=49): "Whit Sunday",
        e + timedelta(days=50): "Whit Monday",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "Boxing Day",
    }
    if year <= 2023:
        days[e + timedelta(days=26)] = "Great Prayer Day"
    names = {"06-05": "Constitution Day", "12-24": "Christmas Eve", "12-31": "New Year's Eve"}
    for md in extra:
        md = md.strip()
        if md:
            mm, dd = md.split("-")
            days.setdefault(date(year, int(mm), int(dd)), names.get(md, "Extra closing day"))
    return days


# ----------------------------------------------------------------- tests

REQUIRED = ["entry_id", "date", "user", "account", "description", "amount", "manual"]
OPTIONAL = ["time"]
ALIASES = {"bilag": "entry_id", "bilagsnr": "entry_id", "voucher": "entry_id", "entry": "entry_id",
           "dato": "date", "tid": "time", "tidspunkt": "time", "bruger": "user", "user_id": "user",
           "konto": "account", "tekst": "description", "text": "description", "beløb": "amount", "beloeb": "amount",
           "manuel": "manual"}
WEIGHTS = {"T1": 2, "T2": 2, "T3": 1, "T4": 3, "T5": 3, "T6": 2, "T7": 2}
NAMES = {"T1": "Weekend or public holiday", "T2": "Out of hours", "T3": "Round amount", "T4": "Just below approval limit",
         "T5": "Possible duplicate", "T6": "Manual entry to revenue or cash account", "T7": "New or rare user"}


def load(path, warnings):
    rows = read_table(path, REQUIRED, OPTIONAL, ALIASES)
    out = []
    has_time = False
    for r in rows:
        ln = r["_line"]
        d = parse_date(r["date"])
        try:
            amt = parse_number(r["amount"])
        except ValueError:
            amt = None
        if d is None or amt is None:
            warnings.append("line %d (entry %s): missing or invalid date or amount, row skipped" % (ln, r["entry_id"]))
            continue
        if not r["entry_id"]:
            warnings.append("line %d: missing entry_id, row skipped" % ln)
            continue
        if not r["user"]:
            warnings.append("line %d (entry %s): missing user" % (ln, r["entry_id"]))
        manual = parse_yes_no(r["manual"])
        if manual is None:
            warnings.append("line %d (entry %s): manual '%s' not understood, treated as no" % (ln, r["entry_id"], r["manual"]))
            manual = False
        t = parse_time(r.get("time", ""))
        if r.get("time", "") and t is None:
            warnings.append("line %d (entry %s): time '%s' not understood" % (ln, r["entry_id"], r["time"]))
        has_time = has_time or t is not None
        out.append({"entry_id": r["entry_id"], "date": d, "time": t, "user": r["user"], "account": r["account"],
                    "description": r["description"], "amount": amt, "cents": int(round(abs(amt) * 100)),
                    "manual": manual, "line": ln})
    return out, has_time


def _norm(text):
    return " ".join(re.split(r"[^0-9a-zæøå]+", text.lower())).strip()


def run_tests(lines, approval_limit=0.0, below_pct=10.0, round_unit=1000.0, round_min=5000.0,
              work_start=time(7, 0), work_end=time(19, 0), dup_days=3, revenue_prefixes=("1",),
              cash_prefixes=("58",), known_users=None, rare_user_max=2, extra_holidays=("06-05", "12-24", "12-31"),
              mask_users=False, warnings=None):
    warnings = warnings if warnings is not None else []
    hol_cache = {}
    entries = {}
    for l in lines:
        entries.setdefault(l["entry_id"], []).append(l)
    for eid, ls in sorted(entries.items()):
        net = sum(int(round(x["amount"] * 100)) for x in ls)
        if len(ls) > 1 and net != 0:
            warnings.append("entry %s does not balance: lines sum to %s" % (eid, fmt(net / 100.0)))
    users_entries = {}
    for eid, ls in entries.items():
        for u in {x["user"] for x in ls}:
            users_entries.setdefault(u, set()).add(eid)
    if mask_users:
        order = sorted(users_entries)
        masks = {u: "U%d" % (i + 1) for i, u in enumerate(order)}
    else:
        masks = {u: u for u in users_entries}
    if known_users is not None:
        known = {u.strip().lower() for u in known_users}
        new_users = {u for u in users_entries if u.lower() not in known}
    else:
        new_users = {u for u, es in users_entries.items() if len(es) <= rare_user_max}
    hits = {eid: {} for eid in entries}  # eid -> test -> detail

    def hit(eid, test, detail):
        hits[eid].setdefault(test, detail)

    has_time = any(l["time"] for l in lines)
    for l in lines:
        y = l["date"].year
        if y not in hol_cache:
            hol_cache[y] = danish_holidays(y, extra_holidays)
        if l["date"].weekday() >= 5:
            hit(l["entry_id"], "T1", l["date"].strftime("%A"))
        elif l["date"] in hol_cache[y]:
            hit(l["entry_id"], "T1", hol_cache[y][l["date"]])
        if l["time"] and (l["time"] < work_start or l["time"] > work_end):
            hit(l["entry_id"], "T2", l["time"].strftime("%H:%M"))
        unit = int(round(round_unit * 100))
        if unit > 0 and l["cents"] and l["cents"] % unit == 0 and abs(l["amount"]) >= round_min:
            hit(l["entry_id"], "T3", fmt(abs(l["amount"]), 0))
        if approval_limit and approval_limit * (1 - below_pct / 100.0) <= abs(l["amount"]) < approval_limit:
            hit(l["entry_id"], "T4", "%s (%.1f%% of limit)" % (fmt(abs(l["amount"]), 0), abs(l["amount"]) / approval_limit * 100))
        acct = l["account"].strip()
        if l["manual"]:
            if any(acct.startswith(p) for p in revenue_prefixes if p):
                hit(l["entry_id"], "T6", "revenue account %s" % acct)
            elif any(acct.startswith(p) for p in cash_prefixes if p):
                hit(l["entry_id"], "T6", "cash account %s" % acct)
        if l["user"] in new_users:
            hit(l["entry_id"], "T7", "user with %d entr%s in file%s" % (
                len(users_entries[l["user"]]), "y" if len(users_entries[l["user"]]) == 1 else "ies",
                "" if known_users is None else ", not on known-users list"))
    # duplicates across different entries
    by_key = {}
    for l in lines:
        by_key.setdefault((l["account"].strip(), l["cents"], _norm(l["description"])), []).append(l)
    for key, group in by_key.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a["entry_id"] != b["entry_id"] and abs((a["date"] - b["date"]).days) <= dup_days:
                    hit(a["entry_id"], "T5", "same account, amount and text as entry %s" % b["entry_id"])
                    hit(b["entry_id"], "T5", "same account, amount and text as entry %s" % a["entry_id"])
    ranked = []
    for eid, tests in hits.items():
        if not tests:
            continue
        ls = entries[eid]
        main = max(ls, key=lambda x: (abs(x["amount"]), x["line"]))
        ranked.append({
            "entry_id": eid, "date": main["date"], "time": main["time"], "user": ", ".join(sorted({masks[x["user"]] for x in ls})),
            "accounts": ", ".join(sorted({x["account"] for x in ls})), "description": main["description"],
            "amount": abs(main["amount"]), "lines": len(ls), "manual": any(x["manual"] for x in ls),
            "tests": sorted(tests), "details": {k: tests[k] for k in sorted(tests)},
            "score": sum(WEIGHTS[k] for k in tests)})
    ranked.sort(key=lambda r: (-r["score"], -r["amount"], r["entry_id"]))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    summary = []
    for t in sorted(WEIGHTS):
        n = sum(1 for r in ranked if t in r["tests"])
        summary.append({"test": t, "name": NAMES[t], "weight": WEIGHTS[t], "entries": n})
    skipped = []
    if not has_time:
        skipped.append("T2 not run: no time column or no readable times.")
    if not approval_limit:
        skipped.append("T4 not run: give --approval-limit.")
    total_amount = sum(abs(l["amount"]) for l in lines if l["amount"] > 0)
    return {"ranked": ranked, "summary": summary, "skipped": skipped, "warnings": warnings,
            "population": {"lines": len(lines), "entries": len(entries), "users": len(users_entries),
                           "debit_total": round(total_amount, 2),
                           "from": min(l["date"] for l in lines) if lines else None,
                           "to": max(l["date"] for l in lines) if lines else None},
            "masked": mask_users}


# ----------------------------------------------------------------- output


def render_markdown(res, args, top):
    p = res["population"]
    out = ["# Journal entry testing", ""]
    out.append("Population: %d lines in %d entries, %s to %s, %d user IDs. Entries with at least one exception: **%d**." % (
        p["lines"], p["entries"], p["from"].isoformat() if p["from"] else "-", p["to"].isoformat() if p["to"] else "-",
        p["users"], len(res["ranked"])))
    out.append("Exceptions are facts about postings to follow up, not conclusions about any person. Many have ordinary explanations.")
    out += ["", "## 1. Tests performed", ""]
    rules = {
        "T1": "Saturday, Sunday or Danish holiday (extra: %s)" % args.extra_holidays,
        "T2": "time before %s or after %s" % (args.work_start, args.work_end),
        "T3": "multiple of %s and >= %s" % (fmt(args.round_unit, 0), fmt(args.round_min, 0)),
        "T4": ("%s to below %s (%.0f%% band)" % (fmt(args.approval_limit * (1 - args.below_pct / 100.0), 0), fmt(args.approval_limit, 0), args.below_pct))
              if args.approval_limit else "not run",
        "T5": "same account, amount and text in another entry within %d days" % args.dup_days,
        "T6": "manual to accounts starting %s (revenue) or %s (cash)" % (args.revenue_prefixes, args.cash_prefixes),
        "T7": ("not on known-users list" if args.known_users else "user with <= %d entries in the file" % args.rare_user_max),
    }
    out.append(md_table(["Test", "Name", "Rule", "Weight", "Entries hit"],
                        [[s["test"], s["name"], rules[s["test"]], s["weight"], s["entries"]] for s in res["summary"]]))
    out += ["", "## 2. Ranked exceptions (top %d)" % top, ""]
    if res["ranked"]:
        rows = []
        for r in res["ranked"][:top]:
            rows.append([r["rank"], r["entry_id"], r["date"].isoformat(), r["time"].strftime("%H:%M") if r["time"] else "",
                         r["user"], r["accounts"], r["description"], fmt(r["amount"]), "yes" if r["manual"] else "no",
                         "; ".join("%s %s" % (k, v) for k, v in r["details"].items()), r["score"]])
        out.append(md_table(["#", "Entry", "Date", "Time", "Posted by (user ID)", "Accounts", "Description", "Amount",
                             "Manual", "Tests hit", "Score"], rows))
    else:
        out.append("No exceptions.")
    out += ["", "## 3. Follow-up", ""]
    out.append("- For each top entry request the voucher, the approval evidence and the business reason; record the outcome per entry.")
    out.append("- Keep the results to the smallest group that needs them and refer to user IDs, not names (GDPR data minimisation). Take legal or HR advice before acting on any concern about an employee.")
    out += ["", "## 4. Data quality and assumptions", ""]
    notes = list(res["warnings"]) + res["skipped"]
    notes.append("Weights: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(WEIGHTS.items())) + ". Score = sum of weights of tests hit per entry.")
    notes.append("Account prefixes and approval limit are company-specific: set them to your chart of accounts and approval policy.")
    if res["masked"]:
        notes.append("User IDs are masked (U1, U2, ...) in this report.")
    out += ["- " + n for n in notes]
    return "\n".join(out)


def to_jsonable(res):
    def conv(v):
        if isinstance(v, (date, time)):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, (list, tuple, set)):
            return [conv(x) for x in v]
        return v
    return conv(res)


def write_csv(path, res):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "entry_id", "date", "time", "user_id", "accounts", "description", "amount", "lines", "manual",
                    "tests", "details", "score"])
        for r in res["ranked"]:
            w.writerow([r["rank"], r["entry_id"], r["date"].isoformat(), r["time"].strftime("%H:%M") if r["time"] else "",
                        r["user"], r["accounts"], r["description"], "%.2f" % r["amount"], r["lines"],
                        "yes" if r["manual"] else "no", " ".join(r["tests"]),
                        "; ".join("%s %s" % (k, v) for k, v in r["details"].items()), r["score"]])


def build_parser():
    p = argparse.ArgumentParser(description="Red-flag tests on a journal export, scored and ranked per entry. Describes facts only.")
    p.add_argument("csv", help="Journal CSV: " + ", ".join(REQUIRED) + " [, time]")
    p.add_argument("--approval-limit", type=float, default=0.0, help="Approval limit in DKK; enables T4 (company policy, no default)")
    p.add_argument("--below-pct", type=float, default=10.0, help="T4 band: within this %% below the limit (default 10)")
    p.add_argument("--round-unit", type=float, default=1000.0, help="T3: multiple that counts as round (default 1,000)")
    p.add_argument("--round-min", type=float, default=5000.0, help="T3: ignore amounts below this (default 5,000)")
    p.add_argument("--work-start", default="07:00", help="T2: start of normal hours HH:MM (default 07:00)")
    p.add_argument("--work-end", default="19:00", help="T2: end of normal hours HH:MM (default 19:00)")
    p.add_argument("--dup-days", type=int, default=3, help="T5: max days between duplicates (default 3)")
    p.add_argument("--revenue-prefixes", default="1", help="T6: revenue account prefixes, comma separated (default 1; set to your chart)")
    p.add_argument("--cash-prefixes", default="58", help="T6: cash and bank account prefixes, comma separated (default 58; set to your chart)")
    p.add_argument("--known-users", default="", help="T7: comma-separated list of established user IDs (optional)")
    p.add_argument("--rare-user-max", type=int, default=2, help="T7 without a list: users with at most this many entries (default 2)")
    p.add_argument("--extra-holidays", default="06-05,12-24,12-31",
                   help="T1: extra closing days mm-dd besides the built-in Danish public holidays "
                        "(default 06-05,12-24,12-31; verify current value)")
    p.add_argument("--mask-users", action="store_true", help="Replace user IDs with U1, U2, ... in the output")
    p.add_argument("--top", type=int, default=15, help="Number of ranked exceptions to show (default 15)")
    p.add_argument("--out", help="Write all ranked exceptions to this CSV")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    warnings = []
    try:
        ws, we = parse_time(args.work_start), parse_time(args.work_end)
        if ws is None or we is None:
            raise InputError("--work-start and --work-end must be HH:MM")
        lines, _ = load(args.csv, warnings)
    except InputError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    known = [u for u in args.known_users.split(",") if u.strip()] or None
    res = run_tests(lines, approval_limit=args.approval_limit, below_pct=args.below_pct, round_unit=args.round_unit,
                    round_min=args.round_min, work_start=ws, work_end=we, dup_days=args.dup_days,
                    revenue_prefixes=tuple(x.strip() for x in args.revenue_prefixes.split(",")),
                    cash_prefixes=tuple(x.strip() for x in args.cash_prefixes.split(",")), known_users=known,
                    rare_user_max=args.rare_user_max, extra_holidays=tuple(args.extra_holidays.split(",")),
                    mask_users=args.mask_users, warnings=warnings)
    if args.out:
        write_csv(args.out, res)
    print(json.dumps(to_jsonable(res), indent=2, ensure_ascii=False) if args.json else render_markdown(res, args, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
