#!/usr/bin/env python3
"""Contract notice deadline calculator with renewal roll-forward and calendar export.

Purpose
  Computes the termination notice deadline for each contract, rolls auto-renewing
  contracts forward when a deadline has already passed, flags deadlines coming up,
  and writes calendar reminders (.ics) so no renewal window is missed.

Input columns
  Contracts CSV: contract, counterparty, start_date, end_date, auto_renew (yes/no),
    renewal_term_months, and notice_period_months and/or notice_days.
    optional: notice_form (for example "email and registered letter")
  end_date is the last day of the current or initial term.

Formulas and rules
  notice deadline = end date minus notice_period_months (calendar months; if the day does not
                    exist the last day of that month is used, e.g. 31 Aug - 6 months = 28/29 Feb),
                    or end date minus notice_days. If both are given the earlier date is used.
  roll-forward    = for auto_renew = yes, while the deadline is before today the term is renewed:
                    next end = end + renewal_term_months (a month-end date stays month-end).
  send by         = deadline - --buffer-days (delivery time for registered post, receipt rules);
                    moved back to Friday if it falls on a weekend.
  status          = ACT NOW (send-by date passed, deadline not), DUE (deadline within --window-days),
                    RENEWED (a deadline was missed and the contract rolled over), OK, ENDS / EXPIRED
                    (no auto-renewal).
  Notice deadlines are calculated from the contract terms given; check the clause for how
  "before the end of the term" and receipt are defined. This is not legal advice.

Example
  python3 scripts/notice_deadlines.py assets/contracts_template.csv --today 2026-11-16 \
      --window-days 90 --buffer-days 5 --ics reminders.ics
"""
import argparse
import calendar
import csv
import io
import json
import re
import sys
from datetime import date, datetime, timedelta

REQUIRED = ["contract", "counterparty", "start_date", "end_date", "auto_renew", "renewal_term_months"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

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


def parse_number(value):
    if value is None or not str(value).strip():
        return None
    t = str(value).strip().replace(" ", "")
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    return float(t)


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


def is_month_end(d):
    return d.day == calendar.monthrange(d.year, d.month)[1]


def roll(end, months):
    """Add months to a term end; a month-end date stays month-end (28 Feb 2027 + 12 = 29 Feb 2028)."""
    r = add_months(end, months)
    if is_month_end(end):
        r = date(r.year, r.month, calendar.monthrange(r.year, r.month)[1])
    return r

# ---------------------------------------------------------------- core


def notice_deadline(end, months, days):
    cands = []
    if months is not None:
        cands.append(add_months(end, -int(months)))
    if days is not None:
        cands.append(end - timedelta(days=int(days)))
    return min(cands)


def analyse(rows, today, window_days=90, buffer_days=5, default_term_months=12):
    warnings, out, seen = [], [], {}
    for r in rows:
        line, name = r["_line"], r.get("contract", "") or f"line {r['_line']}"
        k = (name.lower(), r.get("counterparty", "").lower())
        if k in seen:
            warnings.append(f"Line {line} ({name}): duplicates line {seen[k]}, skipped.")
            continue
        seen[k] = line
        try:
            start = parse_date(r.get("start_date"))
            end = parse_date(r.get("end_date"))
        except ValueError as e:
            warnings.append(f"Line {line} ({name}): {e}, skipped.")
            continue
        if end is None:
            warnings.append(f"Line {line} ({name}): end_date missing, skipped.")
            continue
        if start and start > end:
            warnings.append(f"Line {line} ({name}): start_date {start} is after end_date {end}, skipped (check the dates).")
            continue
        try:
            months = parse_number(r.get("notice_period_months"))
            days = parse_number(r.get("notice_days"))
            term = parse_number(r.get("renewal_term_months"))
        except ValueError:
            warnings.append(f"Line {line} ({name}): notice period or term is not a number, skipped.")
            continue
        if months is None and days is None:
            warnings.append(f"Line {line} ({name}): no notice period given, deadline not calculated (check the contract).")
            continue
        if months is not None and days is not None:
            warnings.append(f"Line {line} ({name}): both notice months and days given, the earlier deadline is used.")
        auto = parse_yes(r.get("auto_renew", ""))
        if auto and not term:
            term = default_term_months
            warnings.append(f"Line {line} ({name}): renewal_term_months missing, {default_term_months} months assumed.")
        cur_end, renewals = end, 0
        dl = notice_deadline(cur_end, months, days)
        missed = []
        if auto:
            while dl < today:
                missed.append(dl.isoformat())
                renewals += 1
                cur_end = roll(end, renewals * int(term))
                dl = notice_deadline(cur_end, months, days)
        send_by = dl - timedelta(days=buffer_days)
        while send_by.weekday() >= 5:
            send_by -= timedelta(days=1)
        to_dl = (dl - today).days
        if not auto:
            if end < today:
                status, action = "EXPIRED", f"ended {end.isoformat()}: confirm it has been replaced or closed."
            elif (end - today).days <= window_days:
                status, action = "ENDS", f"ends in {(end - today).days} days without renewal: renegotiate or replace."
            else:
                status, action = "ENDS", "no auto-renewal: diary the end date."
        elif send_by < today <= dl:
            status, action = "ACT NOW", f"send notice today if terminating: deadline in {to_dl} days, delivery buffer used up."
        elif to_dl <= window_days:
            status, action = "DUE", f"decide renew or terminate; send notice by {send_by.isoformat()}."
        else:
            status, action = "OK", ""
        if renewals and status in ("OK", "DUE", "ACT NOW"):
            status = "RENEWED" if status == "OK" else status + " (renewed)"
            action = (f"notice deadline {missed[0]} missed: renewed {renewals}x, now ends {cur_end.isoformat()}. "
                      + action).strip()
        if auto and dl.weekday() >= 5:
            action = (action + f" Deadline falls on a {WEEKDAYS[dl.weekday()]}: aim for receipt by the Friday before.").strip()
        out.append({"contract": name, "counterparty": r.get("counterparty", ""), "start_date": start.isoformat() if start else "",
                    "original_end": end.isoformat(), "auto_renew": auto, "renewal_term_months": int(term) if term else None,
                    "notice": (f"{int(months)} month{'s' if int(months) != 1 else ''}" if months is not None else "") +
                              (" / " if months is not None and days is not None else "") +
                              (f"{int(days)} day{'s' if int(days) != 1 else ''}" if days is not None else ""),
                    "notice_form": r.get("notice_form", ""), "current_term_end": cur_end.isoformat(),
                    "renewals_rolled": renewals, "missed_deadlines": missed, "notice_deadline": dl.isoformat(),
                    "deadline_weekday": WEEKDAYS[dl.weekday()], "send_by": send_by.isoformat(),
                    "days_to_deadline": to_dl, "days_left": to_dl if auto else (end - today).days,
                    "status": status, "action": action})
    order = {"ACT NOW": 0, "ACT NOW (renewed)": 0, "DUE": 1, "DUE (renewed)": 1, "ENDS": 2, "RENEWED": 3, "OK": 4, "EXPIRED": 5}
    out.sort(key=lambda x: (order.get(x["status"], 9), x["notice_deadline"] if x["auto_renew"] else x["current_term_end"]))
    return {"today": today.isoformat(), "window_days": window_days, "buffer_days": buffer_days,
            "contracts": out, "warnings": warnings}


def reminder_lines(res):
    lines = []
    for c in res["contracts"]:
        if c["auto_renew"]:
            lines.append(f"{c['send_by'].replace('-', '')} | Send notice if terminating: {c['contract']} ({c['counterparty']}) | "
                         f"deadline {c['notice_deadline']} | term ends {c['current_term_end']}"
                         + (f" | form: {c['notice_form']}" if c["notice_form"] else ""))
        elif c["status"] != "EXPIRED":
            lines.append(f"{c['current_term_end'].replace('-', '')} | Contract ends: {c['contract']} ({c['counterparty']}) | no auto-renewal")
    return sorted(lines)


def ics_escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line):
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 75:
            out.append(cur)
            cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def build_ics(res, alarm_days=14):
    stamp = res["today"].replace("-", "") + "T000000Z"
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//department-skills//notice-deadlines//EN",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for c in res["contracts"]:
        if c["auto_renew"]:
            day = date.fromisoformat(c["send_by"])
            summary = f"Send notice if terminating: {c['contract']} ({c['counterparty']})"
            desc = (f"Notice deadline {c['notice_deadline']} ({c['deadline_weekday']}). Current term ends "
                    f"{c['current_term_end']}; otherwise renews for {c['renewal_term_months']} months. Notice: {c['notice']}"
                    + (f", form: {c['notice_form']}" if c["notice_form"] else "") + ".")
        elif c["status"] != "EXPIRED":
            day = date.fromisoformat(c["current_term_end"])
            summary = f"Contract ends: {c['contract']} ({c['counterparty']})"
            desc = "No auto-renewal. Renegotiate or replace before this date."
        else:
            continue
        uid = re.sub(r"[^a-z0-9]+", "-", f"{c['contract']}-{c['counterparty']}".lower()).strip("-")
        L += ["BEGIN:VEVENT", f"UID:{uid}-{day.strftime('%Y%m%d')}@notice-deadlines", f"DTSTAMP:{stamp}",
              f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
              f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
              f"SUMMARY:{ics_escape(summary)}", f"DESCRIPTION:{ics_escape(desc)}",
              "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{ics_escape(summary)}", f"TRIGGER:-P{alarm_days}D",
              "END:VALARM", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(x) for x in L) + "\r\n"


def render(res):
    cs = res["contracts"]
    urgent = [c for c in cs if c["status"].startswith(("ACT NOW", "DUE"))]
    renewed = [c for c in cs if c["renewals_rolled"]]
    o = [f"# Contract notice deadlines (as of {res['today']}, window {res['window_days']} days, "
         f"delivery buffer {res['buffer_days']} days)", ""]
    o.append(f"**{len(cs)} contracts. Action needed within the window: {len(urgent)}. "
             f"Missed notice deadlines (contract rolled over): {len(renewed)}.**")
    o.append("")
    o.append("## Key dates")
    o.append("| Contract | Counterparty | Auto-renew | Notice | Current term ends | Notice deadline | Send by | Days left | Status |")
    o.append("|---|---|---|---|---|---|---|---:|---|")
    for c in cs:
        o.append(f"| {c['contract']} | {c['counterparty']} | {'yes' if c['auto_renew'] else 'no'} | {c['notice']} | "
                 f"{c['current_term_end']} | {c['notice_deadline']} ({c['deadline_weekday'][:3]}) | {c['send_by']} | "
                 f"{c['days_left']} | {c['status']} |")
    acts = [c for c in cs if c["action"]]
    if acts:
        o += ["", "## Actions"]
        for c in acts:
            o.append(f"- **{c['contract']}** ({c['status']}): {c['action']}" + (f" Form: {c['notice_form']}." if c["notice_form"] else ""))
    o += ["", "## Reminder lines (date | reminder)", "```"] + reminder_lines(res) + ["```"]
    if res["warnings"]:
        o += ["", "## Data quality and warnings"] + [f"- {w}" for w in res["warnings"]]
    o += ["", "Check each clause for how notice must be given and when it counts as received. Not legal advice."]
    return "\n".join(o)


def write_csv(path, res):
    cols = ["contract", "counterparty", "start_date", "original_end", "auto_renew", "renewal_term_months", "notice",
            "notice_form", "current_term_end", "renewals_rolled", "notice_deadline", "deadline_weekday", "send_by",
            "days_to_deadline", "status", "action"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for c in res["contracts"]:
            w.writerow(["" if c[k] is None else c[k] for k in cols])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contracts", help="contracts CSV")
    ap.add_argument("--today", help="as-of date (default: system date)")
    ap.add_argument("--window-days", type=int, default=90, help="flag notice deadlines within this many days (default: 90)")
    ap.add_argument("--buffer-days", type=int, default=5,
                    help="calendar days before the deadline to send notice, for delivery and receipt (default: 5)")
    ap.add_argument("--default-term-months", type=int, default=12,
                    help="renewal term assumed when auto_renew is yes and the term is missing (default: 12)")
    ap.add_argument("--ics", help="write calendar reminders to this .ics file")
    ap.add_argument("--alarm-days", type=int, default=14, help="calendar alarm this many days before each reminder (default: 14)")
    ap.add_argument("--out", help="write the key dates table to this CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    try:
        header, rows = read_csv(a.contracts, REQUIRED, ["notice_period_months", "notice_days", "notice_form"])
        if "notice_period_months" not in header and "notice_days" not in header:
            raise ValueError(f"{a.contracts}: need a notice_period_months or notice_days column. Expected columns: "
                             f"{', '.join(REQUIRED)}, notice_period_months and/or notice_days (optional: notice_form)")
        today = parse_date(a.today) if a.today else date.today()
        res = analyse(rows, today, a.window_days, a.buffer_days, a.default_term_months)
        if a.ics:
            with open(a.ics, "w", encoding="utf-8", newline="") as fh:
                fh.write(build_ics(res, a.alarm_days))
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if a.out:
        write_csv(a.out, res)
    print(json.dumps(res, indent=2) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
