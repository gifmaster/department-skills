#!/usr/bin/env python3
"""GDPR data subject request deadline calculator and tracker (Art. 12(3) GDPR).

Purpose
  Calculates the response deadline for one data subject request (access, erasure,
  rectification, objection, portability) or for a whole request log, says whether
  an extension is still possible, and flags overdue requests with an action note.

Rule implemented (verify current value against the GDPR text and Datatilsynet/EDPB guidance)
  - Respond within one month of receipt (--base-months, default 1).
  - Calendar month rule: same day number in the following month; if that day does not
    exist, the last day of that month (31 Jan -> 28/29 Feb, 31 Aug -> 30 Sep).
  - Extendable by two further months (--extension-months, default 2) only if the data
    subject is informed of the extension and the reasons within the first month.
  - Extended deadline = the earlier of (start + 3 months) and (one-month deadline + 2 months),
    which is the conservative reading when the month-end rule shortens the first month.
  - An extension notification date counts as an extension even if extension is not marked
    yes (a warning is shown). Once a notification date exists the report never says an
    extension is still possible: it is either valid or flagged as invalid.
  - Clock start: by default the clock runs from receipt. Where identity verification is
    needed, check current EDPB guidance (Guidelines 01/2022 on the right of access) and
    Datatilsynet practice before using --clock-start verification. This is an assumption to verify.
  - Optional --roll-weekend moves a deadline on a Saturday, Sunday or listed holiday to the
    next working day (Regulation 1182/71 approach). Off by default, which is the safer choice.

Input
  Single request: --received (plus optional --verified, --extension yes/no, --extension-notified,
    --responded). Request log CSV: request_id, received_date
    optional: request_type, identity_verified_date, extension (yes/no), extension_notified_date,
    response_sent_date

Output
  Deadline, extended deadline, whether an extension is still possible, days left or days
  overdue and an action note; for a log, a tracker table sorted by urgency.

Example
  python3 scripts/dsar_deadline.py assets/dsar_log_template.csv --today 2026-11-16
  python3 scripts/dsar_deadline.py --received 2026-10-03 --today 2026-11-16
"""
import argparse
import calendar
import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta

OVERDUE_NOTE = ("Respond without further delay: send a holding reply today (acknowledge, apologise, give a firm date), "
                "then the full response. Extension is no longer available. Record the cause of the delay; "
                "a complaint to Datatilsynet is a real risk.")

# ---------------------------------------------------------------- helpers


def norm_col(name):
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def read_csv(path, required, optional=()):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first:
        raise ValueError(f"{path} is empty")
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    header, rows = None, []
    for rec in reader:
        if not any(c.strip() for c in rec):
            continue
        if header is None:
            header = [norm_col(h) for h in rec]
            missing = [c for c in required if c not in header]
            if missing:
                raise ValueError(
                    f"{path}: missing column(s) {', '.join(missing)}. Expected columns: "
                    f"{', '.join(required)}" + (f" (optional: {', '.join(optional)})" if optional else ""))
            continue
        rec = rec + [""] * (len(header) - len(rec))
        row = {h: rec[i].strip() for i, h in enumerate(header)}
        row["_line"] = reader.line_num
        rows.append(row)
    return header, rows


def parse_date(value):
    if value is None or not str(value).strip():
        return None
    t = str(value).strip().split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date '{value}' (use yyyy-mm-dd or dd-mm-yyyy)")


def parse_yes(value):
    return str(value).strip().lower() in ("yes", "y", "ja", "j", "true", "1", "x")


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def next_working_day(d, holidays):
    while d.weekday() >= 5 or d in holidays:
        d += timedelta(days=1)
    return d

# ---------------------------------------------------------------- core


def assess(received, today, verified=None, extension=False, extension_notified=None, responded=None,
           clock_start="receipt", base_months=1, extension_months=2, roll_weekend=False, holidays=(),
           warn_days=7, request_id="", request_type=""):
    notes, warnings = [], []
    if verified and verified < received:
        warnings.append(f"identity verified ({verified}) before received ({received}): check dates")
    start = received
    if clock_start == "verification":
        if verified:
            start = max(verified, received)
            notes.append("clock from identity verification (verify against current EDPB guidance)")
        else:
            notes.append("identity not verified yet: clock shown from receipt")
    deadline = add_months(start, base_months)
    ext_deadline = min(add_months(start, base_months + extension_months), add_months(deadline, extension_months))
    if roll_weekend:
        hs = set(holidays)
        deadline, ext_deadline = next_working_day(deadline, hs), next_working_day(ext_deadline, hs)
    if received > today:
        warnings.append(f"received date {received} is after today")

    ext_valid = False
    ext_problem = None
    if extension_notified is not None and not extension:
        extension = True
        warnings.append(f"extension_notified_date {extension_notified} given but extension not marked yes: "
                        "treated as an extension (set extension to yes in the log)")
    if extension:
        if extension_notified is None:
            warnings.append("extension marked yes but no extension_notified_date: treated as not extended")
        elif extension_notified > deadline:
            ext_problem = f"notified {extension_notified.isoformat()}, after the first-month deadline: not valid"
            warnings.append(f"extension notified {extension_notified}, after the first-month deadline {deadline}: extension not valid")
        elif extension_notified < received:
            ext_problem = f"notified {extension_notified.isoformat()}, before receipt: check the dates"
            warnings.append("extension notified before receipt: check dates")
        else:
            ext_valid = True
    effective = ext_deadline if ext_valid else deadline

    if responded:
        ext_possible = "n/a (closed)"
        late = (responded - effective).days
        status = "closed late" if late > 0 else "closed on time"
        days = -late
        action = f"responded {late} days late: record cause and fix intake" if late > 0 else ""
    else:
        if ext_valid:
            ext_possible = "already extended"
        elif ext_problem:
            ext_possible = f"no, extension already recorded ({ext_problem})"
        elif today <= deadline:
            ext_possible = f"yes, notify the data subject with reasons by {deadline.isoformat()}"
        else:
            ext_possible = "no (first month has passed)"
        days = (effective - today).days
        if days < 0:
            status, action = "OVERDUE", OVERDUE_NOTE
        elif days <= warn_days:
            status, action = "due soon", "Finalise search and response now."
        else:
            status, action = "open", ""
    return {"request_id": request_id, "request_type": request_type, "received": received.isoformat(),
            "clock_start": start.isoformat(), "deadline": deadline.isoformat(),
            "extended_deadline": ext_deadline.isoformat(), "extension_valid": ext_valid,
            "effective_deadline": effective.isoformat(), "extension_possible": ext_possible,
            "responded": responded.isoformat() if responded else "", "status": status,
            "days_left": days if status not in ("closed late", "closed on time") else None,
            "days_overdue": -days if status == "OVERDUE" else 0,
            "days_late": -days if status == "closed late" else 0,
            "action": action, "notes": notes, "warnings": warnings}


def tracker(rows, today, **kw):
    out, warnings, seen = [], [], {}
    for r in rows:
        rid = r.get("request_id", "") or f"line {r['_line']}"
        if rid in seen:
            warnings.append(f"Line {r['_line']}: request_id {rid} duplicates line {seen[rid]}, skipped.")
            continue
        seen[rid] = r["_line"]
        try:
            rec = parse_date(r.get("received_date"))
            ver = parse_date(r.get("identity_verified_date"))
            notified = parse_date(r.get("extension_notified_date"))
            resp = parse_date(r.get("response_sent_date"))
        except ValueError as e:
            warnings.append(f"Line {r['_line']} ({rid}): {e}, skipped.")
            continue
        if rec is None:
            warnings.append(f"Line {r['_line']} ({rid}): received_date missing, deadline cannot be calculated.")
            continue
        res = assess(rec, today, ver, parse_yes(r.get("extension", "")), notified, resp,
                     request_id=rid, request_type=r.get("request_type", ""), **kw)
        for w in res["warnings"]:
            warnings.append(f"Line {r['_line']} ({rid}): {w}.")
        out.append(res)
    order = {"OVERDUE": 0, "due soon": 1, "open": 2, "closed late": 3, "closed on time": 4}
    out.sort(key=lambda x: (order[x["status"]], x["effective_deadline"]))
    counts = {}
    for x in out:
        counts[x["status"]] = counts.get(x["status"], 0) + 1
    return {"today": today.isoformat(), "requests": out, "counts": counts, "warnings": warnings}


def render_one(r, today):
    o = [f"# Data subject request deadline (as of {today.isoformat()})", ""]
    o.append("| Item | Value |")
    o.append("|---|---|")
    for k, label in (("received", "Received"), ("clock_start", "Clock starts"), ("deadline", "One-month deadline"),
                     ("extended_deadline", "Extended deadline (if validly extended)"),
                     ("effective_deadline", "Deadline that applies now"), ("extension_possible", "Extension still possible"),
                     ("status", "Status")):
        o.append(f"| {label} | {r[k]} |")
    if r["status"] == "OVERDUE":
        o.append(f"| Days overdue | {r['days_overdue']} |")
    elif r["days_left"] is not None:
        o.append(f"| Days left | {r['days_left']} |")
    if r["action"]:
        o += ["", f"**Action:** {r['action']}"]
    for n in r["notes"] + r["warnings"]:
        o.append(f"- {n}")
    o += ["", "Legal information, not legal advice. Verify the rule against the GDPR text and current guidance."]
    return "\n".join(o)


def render_log(res):
    c = res["counts"]
    o = [f"# Data subject request tracker (as of {res['today']})", ""]
    o.append(f"**Overdue {c.get('OVERDUE', 0)} | Due within warning window {c.get('due soon', 0)} | Open {c.get('open', 0)} | "
             f"Closed late {c.get('closed late', 0)} | Closed on time {c.get('closed on time', 0)}**")
    o.append("")
    o.append("| Request | Type | Received | Deadline | Extended | Applies | Status | Days | Extension possible |")
    o.append("|---|---|---|---|---|---|---|---:|---|")
    for r in res["requests"]:
        days = (f"{r['days_overdue']} over" if r["status"] == "OVERDUE" else
                f"{r['days_late']} late" if r["status"] == "closed late" else
                "" if r["days_left"] is None else f"{r['days_left']} left")
        o.append(f"| {r['request_id']} | {r['request_type']} | {r['received']} | {r['deadline']} | "
                 f"{r['extended_deadline'] if r['extension_valid'] else '-'} | {r['effective_deadline']} | {r['status']} | "
                 f"{days} | {r['extension_possible']} |")
    overdue = [r for r in res["requests"] if r["status"] == "OVERDUE"]
    if overdue:
        o += ["", "## Overdue: action today"]
        for r in overdue:
            o.append(f"- {r['request_id']}: {r['days_overdue']} days overdue (deadline {r['effective_deadline']}). {r['action']}")
    soon = [r for r in res["requests"] if r["status"] == "due soon"]
    if soon:
        o += ["", "## Due soon"]
        for r in soon:
            o.append(f"- {r['request_id']}: due {r['effective_deadline']} ({r['days_left']} days). Extension: {r['extension_possible']}.")
    if res["warnings"]:
        o += ["", "## Data quality and warnings"]
        o += [f"- {w}" for w in res["warnings"]]
    o += ["", "Legal information, not legal advice. Clock runs from receipt unless --clock-start verification is used."]
    return "\n".join(o)


def write_csv(path, requests):
    cols = ["request_id", "request_type", "received", "clock_start", "deadline", "extended_deadline", "extension_valid",
            "effective_deadline", "extension_possible", "responded", "status", "days_left", "days_overdue",
            "days_late", "action"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in requests:
            w.writerow(["" if r[c] is None else r[c] for c in cols])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", nargs="?", help="optional request log CSV (tracker mode)")
    ap.add_argument("--received", help="single request: date received by the organisation")
    ap.add_argument("--verified", help="single request: date identity was verified")
    ap.add_argument("--extension", default="no", help="single request: extension claimed yes/no (default: no)")
    ap.add_argument("--extension-notified", help="single request: date the data subject was told of the extension and reasons "
                         "(implies --extension yes; a warning is shown if --extension is not yes)")
    ap.add_argument("--responded", help="single request: date the full response was sent")
    ap.add_argument("--today", help="as-of date (default: system date)")
    ap.add_argument("--clock-start", choices=["receipt", "verification"], default="receipt",
                    help="when the clock starts (default: receipt). Verify the practice for identity checks "
                         "against current EDPB guidance before choosing 'verification'.")
    ap.add_argument("--base-months", type=int, default=1, help="response period in months, GDPR Art. 12(3) (default: 1, verify current value)")
    ap.add_argument("--extension-months", type=int, default=2,
                    help="further months allowed when validly extended (default: 2, verify current value)")
    ap.add_argument("--roll-weekend", action="store_true",
                    help="move deadlines on weekends or --holidays to the next working day (default: off)")
    ap.add_argument("--holidays", default="", help="comma list of public holidays yyyy-mm-dd, used with --roll-weekend")
    ap.add_argument("--warn-days", type=int, default=7, help="flag open requests due within this many days (default: 7)")
    ap.add_argument("--out", help="write the tracker to this CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    try:
        today = parse_date(a.today) if a.today else date.today()
        hol = [parse_date(h) for h in a.holidays.split(",") if h.strip()]
        kw = dict(clock_start=a.clock_start, base_months=a.base_months, extension_months=a.extension_months,
                  roll_weekend=a.roll_weekend, holidays=hol, warn_days=a.warn_days)
        if a.log:
            _, rows = read_csv(a.log, ["request_id", "received_date"],
                               ["request_type", "identity_verified_date", "extension", "extension_notified_date",
                                "response_sent_date"])
            res = tracker(rows, today, **kw)
            if a.out:
                write_csv(a.out, res["requests"])
            print(json.dumps(res, indent=2) if a.json else render_log(res))
        elif a.received:
            r = assess(parse_date(a.received), today, parse_date(a.verified), parse_yes(a.extension),
                       parse_date(a.extension_notified), parse_date(a.responded), **kw)
            if a.out:
                write_csv(a.out, [r])
            print(json.dumps(r, indent=2) if a.json else render_one(r, today))
        else:
            raise ValueError("give a request log CSV or --received yyyy-mm-dd")
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
