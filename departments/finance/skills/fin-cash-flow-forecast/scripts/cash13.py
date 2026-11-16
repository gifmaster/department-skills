#!/usr/bin/env python3
"""13-week cash flow forecast (weekly table plus day-level low point).

Purpose
  Builds a rolling weekly cash forecast from an opening bank balance, open receivables
  (shifted by each customer's actual lateness), open payables and recurring items such as
  salaries, A-tax and AM contribution, rent, VAT and loan instalments. Reports the lowest
  balance at week end AND on any single banking day, and warns when cash goes below the
  minimum buffer or beyond the overdraft facility.

Input columns (header names case-insensitive; comma or semicolon; "1.234,56" or "1234.56")
  receivables CSV (positional): customer, amount, due_date [, avg_days_late]
  payables CSV (--payables):     supplier, amount, due_date
  recurring CSV (--recurring):   name, amount, first_date, frequency, day [, category, end_date]
    frequency: weekly | monthly | quarterly
    day: weekly = weekday 1-7 (1 = Monday) or mon..sun; monthly/quarterly = day of month 1-31
         or "last" (last banking day). Blank = same day as first_date.
    category: optional. "atax" marks A-tax + AM contribution (also detected from names
         containing a-skat, a-tax, am-bidrag); its date follows --atax-timing.
    end_date: optional last date of the item.
  Signs: receivables and payables are positive amounts (a negative is a credit note).
         Recurring amounts are signed: negative = cash out, positive = cash in.

Formulas and rules
  expected receipt date = due_date + avg_days_late (blank: --default-days-late, default 0)
  overdue items (expected date before --start) are put on the first banking day (warning).
  A date on a weekend or Danish bank closing day is moved to the next banking day
  (--roll following) or the previous one (--roll preceding). "last" = last banking day.
  --atax-timing large: A-tax and AM for salary month M paid on the last banking day of M.
  --atax-timing small: paid on the 10th of month M+1 (next banking day if closed).
  Week w runs Monday to Sunday; closing = opening + receipts - payments.
  Daily low = lowest end-of-day balance over all banking days in the horizon.

Example
  python3 scripts/cash13.py assets/receivables.csv --payables assets/payables.csv \
      --recurring assets/recurring.csv --opening 850000 --start 2026-11-23 --min-buffer 250000
"""

import argparse
import calendar
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


def fmt(v, dec=0):
    return ("{:,.%df}" % dec).format(v)


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out)


# ----------------------------------------------------------------- Danish banking calendar


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


def bank_closing_days(year, fixed_extra=("06-05", "12-24", "12-31")):
    """Danish public holidays plus bank closing days (default 5 June, 24 and 31 December,
    and the Friday after Ascension). Store bededag counted only up to 2023."""
    e = easter_sunday(year)
    days = {
        date(year, 1, 1): "New Year's Day",
        e - timedelta(days=3): "Maundy Thursday",
        e - timedelta(days=2): "Good Friday",
        e: "Easter Sunday",
        e + timedelta(days=1): "Easter Monday",
        e + timedelta(days=39): "Ascension Day",
        e + timedelta(days=40): "Bank closing day after Ascension",
        e + timedelta(days=49): "Whit Sunday",
        e + timedelta(days=50): "Whit Monday",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "Boxing Day",
    }
    if year <= 2023:
        days[e + timedelta(days=26)] = "Great Prayer Day"
    for md in fixed_extra:
        md = md.strip()
        if md:
            m, d = md.split("-")
            days[date(year, int(m), int(d))] = "Bank closing day"
    return days


class BankCalendar:
    def __init__(self, fixed_extra=("06-05", "12-24", "12-31"), extra_dates=()):
        self.fixed_extra = fixed_extra
        self.extra = set(extra_dates)
        self._cache = {}

    def is_banking_day(self, d):
        if d.weekday() >= 5 or d in self.extra:
            return False
        if d.year not in self._cache:
            self._cache[d.year] = bank_closing_days(d.year, self.fixed_extra)
        return d not in self._cache[d.year]

    def roll(self, d, how="following"):
        step = timedelta(days=1 if how == "following" else -1)
        while not self.is_banking_day(d):
            d += step
        return d

    def last_banking_day(self, year, month):
        return self.roll(date(year, month, calendar.monthrange(year, month)[1]), "preceding")


# ----------------------------------------------------------------- forecast logic

WEEKDAYS = {"mon": 0, "man": 0, "tue": 1, "tir": 1, "wed": 2, "ons": 2, "thu": 3, "tor": 3,
            "fri": 4, "fre": 4, "sat": 5, "lør": 5, "lor": 5, "sun": 6, "søn": 6, "son": 6}
ATAX_RE = re.compile(r"(?i)a-?skat|a-?tax|am-?bidrag|am contribution")
ALIASES = {"kunde": "customer", "debitor": "customer", "leverandør": "supplier", "kreditor": "supplier",
           "beløb": "amount", "beloeb": "amount", "forfald": "due_date", "due": "due_date",
           "navn": "name", "frekvens": "frequency", "dag": "day", "kategori": "category"}


def add_months(y, m, k):
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def expand_recurring(row, start, end, cal, atax_timing, roll, warnings):
    """Return list of (pay_date, amount, label) for one recurring row within [start, end]."""
    name = row["name"]
    amount = row["amount"]
    first = row["first_date"]
    freq = row["frequency"]
    day = (row["day"] or "").strip().lower()
    last = row.get("end_date")
    is_atax = row.get("category", "").lower() in ("atax", "a-tax", "a-skat", "askat") or bool(ATAX_RE.search(name))
    out = []
    if freq == "weekly":
        if day:
            wd = int(day) - 1 if day.isdigit() else WEEKDAYS.get(day[:3])
            if wd is None or not 0 <= wd <= 6:
                warnings.append("recurring '%s': weekday '%s' not understood, using first_date's weekday" % (name, day))
                wd = first.weekday()
        else:
            wd = first.weekday()
        d = first + timedelta(days=(wd - first.weekday()) % 7)
        while d <= end:
            if last and d > last:
                break
            pd = cal.roll(d, roll)
            if start <= pd <= end:
                out.append((pd, amount, name))
            d += timedelta(days=7)
        return out, is_atax
    step = 1 if freq == "monthly" else 3
    y, m = first.year, first.month
    if is_atax and day:
        warnings.append("recurring '%s': A-tax date follows --atax-timing; day '%s' ignored" % (name, day))
    while True:
        # salary month (y, m)
        if is_atax:
            if atax_timing == "large":
                pd = cal.last_banking_day(y, m)
            else:
                ny, nm = add_months(y, m, 1)
                pd = cal.roll(date(ny, nm, 10), "following")
            nominal = date(y, m, 1)
        else:
            if day == "last":
                pd = cal.last_banking_day(y, m)
                nominal = pd
            else:
                dom = int(day) if day.isdigit() else first.day
                dom = min(max(dom, 1), calendar.monthrange(y, m)[1])
                nominal = date(y, m, dom)
                pd = cal.roll(nominal, roll)
        if nominal > end and pd > end:
            break
        if last and nominal > last:
            break
        if (is_atax or nominal >= first) and start <= pd <= end:
            out.append((pd, amount, name + (" (salary month %04d-%02d)" % (y, m) if is_atax else "")))
        y, m = add_months(y, m, step)
        if date(y, m, 1) > end + timedelta(days=40):
            break
    return out, is_atax


def load_inputs(receivables_path, payables_path, recurring_path, default_days_late, warnings):
    rec_rows = read_table(receivables_path, ["customer", "amount", "due_date"], ["avg_days_late"], ALIASES)
    recs = []
    for r in rec_rows:
        try:
            amt = parse_number(r["amount"])
        except ValueError:
            amt = None
        due = parse_date(r["due_date"])
        if amt is None or due is None:
            warnings.append("receivables line %d (%s): missing or invalid amount or due_date, row skipped" % (r["_line"], r["customer"]))
            continue
        late_raw = r.get("avg_days_late", "")
        try:
            late = parse_number(late_raw)
        except ValueError:
            late = None
        if late is None:
            late = default_days_late
            if "avg_days_late" in r:
                warnings.append("receivables line %d (%s): avg_days_late blank, default %d days used" % (r["_line"], r["customer"], default_days_late))
        if amt < 0:
            warnings.append("receivables line %d (%s): negative amount treated as a credit note" % (r["_line"], r["customer"]))
        recs.append({"name": r["customer"], "amount": amt, "due": due, "late": int(round(late)), "line": r["_line"]})
    pays = []
    if payables_path:
        for r in read_table(payables_path, ["supplier", "amount", "due_date"], (), ALIASES):
            try:
                amt = parse_number(r["amount"])
            except ValueError:
                amt = None
            due = parse_date(r["due_date"])
            if amt is None or due is None:
                warnings.append("payables line %d (%s): missing or invalid amount or due_date, row skipped" % (r["_line"], r["supplier"]))
                continue
            pays.append({"name": r["supplier"], "amount": amt, "due": due, "line": r["_line"]})
    recur = []
    if recurring_path:
        for r in read_table(recurring_path, ["name", "amount", "first_date", "frequency", "day"], ["category", "end_date"], ALIASES):
            try:
                amt = parse_number(r["amount"])
            except ValueError:
                amt = None
            first = parse_date(r["first_date"])
            freq = r["frequency"].strip().lower()
            if amt is None or first is None or freq not in ("weekly", "monthly", "quarterly"):
                warnings.append("recurring line %d (%s): needs amount, first_date and frequency weekly|monthly|quarterly, row skipped" % (r["_line"], r["name"]))
                continue
            recur.append({"name": r["name"], "amount": amt, "first_date": first, "frequency": freq, "day": r["day"],
                          "category": r.get("category", ""), "end_date": parse_date(r.get("end_date", "")), "line": r["_line"]})
        if recur and all(x["amount"] > 0 for x in recur):
            warnings.append("all recurring amounts are positive (cash in). Recurring amounts are signed: use negative for payments.")
    return recs, pays, recur


def forecast(opening, start, recs, pays, recur, weeks=13, min_buffer=0.0, facility=0.0,
             atax_timing="large", roll="following", cal=None, warnings=None):
    warnings = warnings if warnings is not None else []
    cal = cal or BankCalendar()
    week0 = start - timedelta(days=start.weekday())
    end = week0 + timedelta(days=7 * weeks - 1)
    first_bd = cal.roll(max(start, week0), "following")
    flows = []  # (date, kind, amount signed, label)
    outside = {"receipts": 0.0, "payables": 0.0}
    overdue_r, overdue_p = 0.0, 0.0
    for r in recs:
        exp = r["due"] + timedelta(days=r["late"])
        if exp < first_bd:
            overdue_r += r["amount"]
            exp = first_bd
        pd = cal.roll(exp, "following")
        if pd > end:
            outside["receipts"] += r["amount"]
            continue
        flows.append((pd, "receipts", r["amount"], r["name"]))
    for p in pays:
        exp = p["due"]
        if exp < first_bd:
            overdue_p += p["amount"]
            exp = first_bd
        pd = cal.roll(exp, roll)
        if pd > end:
            outside["payables"] += p["amount"]
            continue
        flows.append((pd, "suppliers", -p["amount"], p["name"]))
    dated_items = []
    for it in recur:
        occ, is_atax = expand_recurring(it, first_bd, end, cal, atax_timing, roll, warnings)
        for pd, amt, label in occ:
            kind = "atax" if is_atax else ("other_in" if amt > 0 else "recurring_out")
            flows.append((pd, kind, amt, label))
            dated_items.append((pd, label, amt))
    if overdue_r:
        warnings.append("receivables of %s are already overdue on expected date; assumed received on %s (optimistic, check)" % (fmt(overdue_r), first_bd.isoformat()))
    if overdue_p:
        warnings.append("payables of %s are overdue; assumed paid on %s" % (fmt(overdue_p), first_bd.isoformat()))

    # daily balances
    by_day = {}
    for d, _, amt, _ in flows:
        by_day[d] = by_day.get(d, 0.0) + amt
    bal = opening
    daily = []
    d = week0
    while d <= end:
        bal += by_day.get(d, 0.0)
        daily.append((d, round(bal, 2)))
        d += timedelta(days=1)
    banking_daily = [(d, b) for d, b in daily if cal.is_banking_day(d)] or daily
    low_day = min(banking_daily, key=lambda t: (t[1], t[0]))

    table = []
    opening_w = opening
    for w in range(weeks):
        ws = week0 + timedelta(days=7 * w)
        we = ws + timedelta(days=6)
        sums = {"receipts": 0.0, "other_in": 0.0, "suppliers": 0.0, "recurring_out": 0.0, "atax": 0.0}
        for fd, kind, amt, _ in flows:
            if ws <= fd <= we:
                sums[kind] += amt
        net = sum(sums.values())
        closing = round(opening_w + net, 2)
        wk_days = [b for dd, b in banking_daily if ws <= dd <= we]
        low_in_week = min(wk_days) if wk_days else closing
        flags = []
        if closing < min_buffer:
            flags.append("below buffer")
        if low_in_week < min_buffer and closing >= min_buffer:
            flags.append("below buffer intra-week")
        if facility and low_in_week < -facility:
            flags.append("beyond facility")
        elif low_in_week < 0:
            flags.append("overdraft used")
        table.append({"week": w + 1, "start": ws, "end": we, "opening": round(opening_w, 2),
                      "receipts": round(sums["receipts"], 2), "other_in": round(sums["other_in"], 2),
                      "suppliers": round(sums["suppliers"], 2), "recurring_out": round(sums["recurring_out"], 2),
                      "atax": round(sums["atax"], 2), "net": round(net, 2), "closing": closing,
                      "low_in_week": round(low_in_week, 2), "flags": flags})
        opening_w = closing
    low_week = min(table, key=lambda t: (t["closing"], t["week"]))
    days_below = [(d, b) for d, b in banking_daily if b < min_buffer]
    return {
        "opening": opening, "start": week0, "end": end, "weeks": table, "flows": sorted(flows),
        "dated_items": sorted(dated_items), "lowest_day": low_day, "lowest_week": low_week,
        "days_below_buffer": days_below, "outside_horizon": outside,
        "total_in": round(sum(f[2] for f in flows if f[2] > 0), 2),
        "total_out": round(sum(f[2] for f in flows if f[2] < 0), 2),
        "min_buffer": min_buffer, "facility": facility, "atax_timing": atax_timing, "warnings": warnings,
    }


# ----------------------------------------------------------------- output


def render_markdown(res):
    t = res["weeks"]
    out = ["# %d-week cash flow forecast, %s to %s" % (len(t), res["start"].isoformat(), res["end"].isoformat()), ""]
    ld, lb = res["lowest_day"]
    lw = res["lowest_week"]
    out.append("Opening balance %s. Receipts %s, payments %s, closing week %d %s." % (
        fmt(res["opening"]), fmt(res["total_in"]), fmt(res["total_out"]), len(t), fmt(t[-1]["closing"])))
    out.append("**Lowest banking-day balance: %s on %s.** Lowest week-end balance: %s (week %d, w/c %s). Minimum buffer %s." % (
        fmt(lb), ld.isoformat(), fmt(lw["closing"]), lw["week"], lw["start"].isoformat(), fmt(res["min_buffer"])))
    out += ["", "## 1. Weekly forecast table", ""]
    rows = []
    for w in t:
        rows.append([w["week"], "%s to %s" % (w["start"].strftime("%d %b"), w["end"].strftime("%d %b")), fmt(w["opening"]),
                     fmt(w["receipts"]), fmt(w["other_in"]), fmt(w["suppliers"]), fmt(w["recurring_out"]), fmt(w["atax"]),
                     fmt(w["net"]), fmt(w["closing"]), fmt(w["low_in_week"]), ", ".join(w["flags"])])
    out.append(md_table(["Wk", "Dates", "Opening", "AR receipts", "Other in", "Suppliers", "Recurring out", "A-tax + AM",
                         "Net", "Closing", "Low in week", "Flag"], rows))
    out += ["", "Formula: closing = opening + receipts + other in + (negative) payments. 'Low in week' is the lowest end-of-day balance on a banking day.", ""]
    out += ["## 2. Lowest cash point and buffer", ""]
    if res["days_below_buffer"]:
        out.append("- %d banking day(s) below the %s buffer, first on %s, worst %s on %s." % (
            len(res["days_below_buffer"]), fmt(res["min_buffer"]), res["days_below_buffer"][0][0].isoformat(), fmt(lb), ld.isoformat()))
    else:
        out.append("- No banking day below the %s buffer." % fmt(res["min_buffer"]))
    if res["facility"]:
        headroom = lb + res["facility"]
        out.append("- Facility %s: headroom at the lowest point %s%s." % (
            fmt(res["facility"]), fmt(headroom), " (FACILITY EXCEEDED)" if headroom < 0 else ""))
    out += ["", "## 3. Dated recurring payments", ""]
    if res["dated_items"]:
        out.append(md_table(["Date", "Item", "Amount"], [[d.isoformat(), lab, fmt(a)] for d, lab, a in res["dated_items"]]))
    else:
        out.append("None.")
    out += ["", "## 4. Data quality and assumptions", ""]
    notes = list(res["warnings"])
    oh = res["outside_horizon"]
    if oh["receipts"] or oh["payables"]:
        notes.append("Outside the horizon: receipts %s, payables %s." % (fmt(oh["receipts"]), fmt(oh["payables"])))
    notes.append("A-tax + AM timing: %s employer (%s). Verify current value and your classification in TastSelv Erhverv; December and other deadlines can differ." % (
        res["atax_timing"], "last banking day of the salary month" if res["atax_timing"] == "large" else "10th of the following month"))
    notes.append("Non-banking days follow the Danish calendar (public holidays plus 5 June, 24 and 31 December, Friday after Ascension). Verify.")
    notes.append("Receipts use due date + average days late; they are estimates, not actuals.")
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
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["week", "week_start", "week_end", "opening", "ar_receipts", "other_in", "suppliers", "recurring_out",
                    "atax_am", "net", "closing", "low_in_week", "flags"])
        for r in res["weeks"]:
            w.writerow([r["week"], r["start"].isoformat(), r["end"].isoformat()] +
                       ["%.2f" % r[k] for k in ("opening", "receipts", "other_in", "suppliers", "recurring_out", "atax", "net", "closing", "low_in_week")] +
                       ["; ".join(r["flags"])])
        w.writerow([])
        w.writerow(["date", "kind", "amount", "item"])
        for d, kind, amt, lab in res["flows"]:
            w.writerow([d.isoformat(), kind, "%.2f" % amt, lab])


def build_parser():
    p = argparse.ArgumentParser(description="Weekly cash flow forecast (default 13 weeks) with day-level low point.")
    p.add_argument("receivables_csv", help="Receivables: customer, amount, due_date [, avg_days_late]")
    p.add_argument("--payables", help="Payables CSV: supplier, amount, due_date")
    p.add_argument("--recurring", help="Recurring items CSV: name, amount (negative = out), first_date, frequency, day [, category, end_date]")
    p.add_argument("--opening", type=float, required=True, help="Opening bank balance at the start date (must tie to the bank)")
    p.add_argument("--start", help="Forecast start date; week 1 starts on that week's Monday (default: today)")
    p.add_argument("--weeks", type=int, default=13, help="Number of weeks (default 13)")
    p.add_argument("--min-buffer", type=float, default=0.0, help="Minimum cash buffer to warn against (default 0)")
    p.add_argument("--facility", type=float, default=0.0, help="Undrawn overdraft facility, positive number (default 0)")
    p.add_argument("--atax-timing", choices=("large", "small"), default="large",
                   help="Danish A-tax + AM payment timing. large = last banking day of the salary month; "
                        "small = 10th of the following month. Default large. Verify current value and your "
                        "classification with Skattestyrelsen (TastSelv Erhverv).")
    p.add_argument("--default-days-late", type=int, default=0, help="Days late for customers without avg_days_late (default 0)")
    p.add_argument("--roll", choices=("following", "preceding"), default="following",
                   help="Move payments on non-banking days to the next (default) or previous banking day")
    p.add_argument("--closing-days", default="06-05,12-24,12-31",
                   help="Extra fixed bank closing days as mm-dd, comma separated (default 06-05,12-24,12-31; verify current value)")
    p.add_argument("--extra-closed-dates", default="", help="Further closed dates yyyy-mm-dd, comma separated")
    p.add_argument("--out", help="Write the weekly table and all dated flows to this CSV")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    warnings = []
    try:
        start = parse_date(args.start) if args.start else date.today()
        if start is None:
            raise InputError("--start '%s' is not a valid date" % args.start)
        extra = []
        for s in [x for x in args.extra_closed_dates.split(",") if x.strip()]:
            d = parse_date(s)
            if d is None:
                raise InputError("--extra-closed-dates: '%s' is not a valid date" % s)
            extra.append(d)
        cal = BankCalendar(tuple(x for x in args.closing_days.split(",") if x.strip()), extra)
        recs, pays, recur = load_inputs(args.receivables_csv, args.payables, args.recurring, args.default_days_late, warnings)
    except InputError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    if not args.start:
        warnings.append("no --start given; today's date %s used" % start.isoformat())
    res = forecast(args.opening, start, recs, pays, recur, weeks=args.weeks, min_buffer=args.min_buffer,
                   facility=args.facility, atax_timing=args.atax_timing, roll=args.roll, cal=cal, warnings=warnings)
    if args.out:
        write_csv(args.out, res)
    print(json.dumps(to_jsonable(res), indent=2, ensure_ascii=False) if args.json else render_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
