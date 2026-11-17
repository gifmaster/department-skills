#!/usr/bin/env python3
"""SLA report for support tickets: response and resolution times, attainment, backlog and breaches.

Purpose
  Calculates first response time (FRT) and resolution time per ticket in business hours
  (opening hours, weekends and Danish public holidays excluded) or calendar hours, then
  reports median, p90 and SLA attainment by priority and channel, the backlog age of open
  tickets and a list of breaches. Standard library only.

Input columns (CSV, comma or semicolon, header names case-insensitive)
  ticket_id, created_at, first_response_at, resolved_at, priority, channel
  Timestamps: yyyy-mm-dd HH:MM[:SS] or dd-mm-yyyy HH:MM (also "T" separator).
  Common helpdesk export headers are accepted as aliases (Zendesk, Freshdesk, HubSpot, Danish),
  e.g. "Ticket ID"/id, "Created at"/created, "First response time"/first_response,
  "Resolved at"/solved/"Closed at", "Source"/via. Full list in --help (HEADER_ALIASES).
  Matching ignores case, spaces and punctuation. Where two aliases are present, the first
  in the list wins (resolved before solved before closed). The first response column must
  hold a timestamp, not a duration in minutes.
  Blank first_response_at = no response yet; blank resolved_at = ticket still open.

Formulas and rules
  Business hours = sum over open days of overlap(ticket interval, [open, close]).
  Calendar hours = UTC difference (Europe/Copenhagen DST applied, EU rule: last Sunday of
  March and October at 01:00 UTC), so a DST night does not add or remove an hour.
  Naive timestamps are read as Europe/Copenhagen local time (use --input-tz utc for UTC exports).
  Attainment = met / (met + breached). Open tickets already past target count as breached;
  open tickets still within target are pending and left out of attainment.
  Median and p90 use linear interpolation (same as Excel PERCENTILE.INC) on completed intervals.
  Danish public holidays: Nytaarsdag, Skaertorsdag, Langfredag, Paaskedag, 2. paaskedag,
  Store Bededag (only years up to 2023, abolished from 2024), Kristi himmelfartsdag, Pinsedag,
  2. pinsedag, Juledag, 2. juledag. Easter by the Gregorian computus.

Example
  python3 scripts/sla.py assets/tickets_template.csv --as-of "2026-04-15 00:00"
  python3 scripts/sla.py tickets.csv --targets targets.json --open-hours 08:00-16:00 --out detail.csv
"""
import argparse
import csv
import io
import json
import math
import re
import sys
from datetime import date, datetime, time, timedelta

REQUIRED = ["ticket_id", "created_at", "first_response_at", "resolved_at", "priority", "channel"]

DEFAULT_TARGETS = {
    "P1": {"first_response_hours": 1, "resolution_hours": 8},
    "P2": {"first_response_hours": 4, "resolution_hours": 16},
    "P3": {"first_response_hours": 8, "resolution_hours": 40},
    "P4": {"first_response_hours": 16, "resolution_hours": 80},
}
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Accepted header aliases per required column, in order of preference (normalised: lower case,
# non-alphanumerics turned into "_"). Zendesk, Freshdesk, HubSpot and Danish export names.
HEADER_ALIASES = {
    "ticket_id": ["ticket_id", "id", "ticket", "ticket_number", "ticket_no", "ticket_nr", "sagsnr", "sags_id"],
    "created_at": ["created_at", "created", "created_time", "created_date", "create_date", "created_on",
                   "creation_date", "opened_at", "oprettet"],
    "first_response_at": ["first_response_at", "first_response", "first_response_time", "first_responded_at",
                          "first_responded_time", "first_reply_at", "first_reply_time", "initial_response_time",
                          "first_agent_reply_date", "first_agent_email_response_date", "foerste_svar", "første_svar"],
    "resolved_at": ["resolved_at", "resolved", "resolved_time", "resolved_date", "solved_at", "solved",
                    "solved_time", "closed_at", "closed", "closed_time", "close_date", "closed_date", "loest", "løst"],
    "priority": ["priority", "ticket_priority", "prioritet"],
    "channel": ["channel", "via", "source", "ticket_source", "source_type", "kanal"],
}


def norm_header(h):
    return re.sub(r"[^\w]+", "_", (h or "").strip().lstrip("\ufeff").lower()).strip("_")


def alias_help():
    return "; ".join("%s: %s" % (k, ", ".join(v[1:])) for k, v in HEADER_ALIASES.items())


def header_map(raw_headers):
    """Map raw header -> canonical name. First alias present (in preference order) wins."""
    normed = {}
    for h in raw_headers:
        normed.setdefault(norm_header(h), h)
    mapping = {}
    for canon, names in HEADER_ALIASES.items():
        for n in names:
            if n in normed and normed[n] not in mapping:
                mapping[normed[n]] = canon
                break
    return mapping


# ---------------------------------------------------------------- CSV and parsing helpers
def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        text = f.read()
    first = text.splitlines()[0] if text.strip() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    mapping = header_map(reader.fieldnames or [])

    def key(h):
        return mapping.get(h, norm_header(h))

    headers = [key(h) for h in (reader.fieldnames or [])]
    rows = []
    for line_no, raw in enumerate(reader, start=2):
        row = {key(k): (v or "").strip() for k, v in raw.items() if k is not None and not isinstance(v, list)}
        if not any(row.values()):
            continue
        rows.append((line_no, row))
    return headers, rows


def check_columns(headers, required):
    missing = [c for c in required if c not in headers]
    if missing:
        raise SystemExit("Missing column(s): %s. Expected columns: %s. Found: %s. Accepted aliases: %s"
                         % (", ".join(missing), ", ".join(required), ", ".join(headers) or "(none)", alias_help()))


_DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"]
_TIME_FORMATS = ["%H:%M:%S", "%H:%M"]


def parse_datetime(s):
    """Return (naive datetime, utc_offset_hours or None). Raises ValueError."""
    s = s.strip()
    offset = None
    m = re.search(r"(Z|[+-]\d{2}:?\d{2})$", s)
    if m and ("T" in s or " " in s):
        tz = m.group(1)
        s = s[: m.start()].strip()
        if tz == "Z":
            offset = 0.0
        else:
            sign = 1 if tz[0] == "+" else -1
            digits = tz[1:].replace(":", "")
            offset = sign * (int(digits[:2]) + int(digits[2:]) / 60.0)
    parts = re.split(r"[T ]", s, maxsplit=1)
    d = None
    for fmt in _DATE_FORMATS:
        try:
            d = datetime.strptime(parts[0], fmt)
            break
        except ValueError:
            pass
    if d is None:
        raise ValueError("unrecognised date '%s'" % s)
    if len(parts) > 1 and parts[1].strip():
        tpart = parts[1].strip().split(".")[0]
        t = None
        for fmt in _TIME_FORMATS:
            try:
                t = datetime.strptime(tpart, fmt).time()
                break
            except ValueError:
                pass
        if t is None:
            raise ValueError("unrecognised time '%s'" % s)
        d = datetime.combine(d.date(), t)
    return d, offset


def percentile(values, q):
    """Linear interpolation between closest ranks (Excel PERCENTILE.INC)."""
    v = sorted(values)
    if not v:
        return None
    pos = (len(v) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


# ---------------------------------------------------------------- Time zone (Europe/Copenhagen)
def last_sunday(year, month):
    d = date(year, month, 31)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def cph_local_to_utc(dt):
    """Return (utc datetime, note or None). EU DST rule."""
    start = datetime.combine(last_sunday(dt.year, 3), time(2, 0))   # 02:00 local jumps to 03:00
    end = datetime.combine(last_sunday(dt.year, 10), time(3, 0))    # 03:00 CEST falls back to 02:00
    if start <= dt < start + timedelta(hours=1):
        return dt - timedelta(hours=1), "non-existent local time (DST spring forward)"
    if end - timedelta(hours=1) <= dt < end:
        return dt - timedelta(hours=2), "ambiguous local time (DST fall back), summer time assumed"
    if start + timedelta(hours=1) <= dt < end:
        return dt - timedelta(hours=2), None
    return dt - timedelta(hours=1), None


def utc_to_cph_local(dt):
    start = datetime.combine(last_sunday(dt.year, 3), time(1, 0))
    end = datetime.combine(last_sunday(dt.year, 10), time(1, 0))
    return dt + timedelta(hours=2 if start <= dt < end else 1)


# ---------------------------------------------------------------- Holidays and calendar
def easter_sunday(year):
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
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def danish_holidays(year, customary=False):
    e = easter_sunday(year)
    hol = {
        date(year, 1, 1): "Nytaarsdag",
        e - timedelta(days=3): "Skaertorsdag",
        e - timedelta(days=2): "Langfredag",
        e: "Paaskedag",
        e + timedelta(days=1): "2. paaskedag",
        e + timedelta(days=39): "Kristi himmelfartsdag",
        e + timedelta(days=49): "Pinsedag",
        e + timedelta(days=50): "2. pinsedag",
        date(year, 12, 25): "Juledag",
        date(year, 12, 26): "2. juledag",
    }
    if year <= 2023:  # Store Bededag abolished as a public holiday from 2024
        hol[e + timedelta(days=26)] = "Store Bededag"
    if customary:  # common closing days that are not statutory public holidays
        hol.setdefault(date(year, 6, 5), "Grundlovsdag (customary)")
        hol.setdefault(date(year, 12, 24), "Juleaftensdag (customary)")
        hol.setdefault(date(year, 12, 31), "Nytaarsaftensdag (customary)")
    return hol


def parse_hhmm(s):
    return datetime.strptime(s.strip(), "%H:%M").time()


def parse_open_hours(spec, workdays):
    """'08:00-16:00' for every workday, or 'mon=08:00-16:00,fri=08:00-15:30' (listed days only)."""
    hours = {}
    if "=" in spec:
        for part in spec.split(","):
            day, rng = part.split("=")
            day = day.strip().lower()[:3]
            if day not in DAY_NAMES:
                raise SystemExit("Unknown day '%s' in --open-hours" % day)
            o, c = rng.split("-")
            hours[DAY_NAMES.index(day)] = (parse_hhmm(o), parse_hhmm(c))
    else:
        o, c = spec.split("-")
        for d in workdays.split(","):
            d = d.strip().lower()[:3]
            if d not in DAY_NAMES:
                raise SystemExit("Unknown day '%s' in --workdays" % d)
            hours[DAY_NAMES.index(d)] = (parse_hhmm(o), parse_hhmm(c))
    for wd, (o, c) in hours.items():
        if c <= o:
            raise SystemExit("Opening hours must close after they open (overnight shifts: use --mode calendar)")
    return hours


class Calendar:
    def __init__(self, hours, holiday_mode="dk", customary=False, extra_closed=None):
        self.hours = hours
        self.holiday_mode = holiday_mode
        self.customary = customary
        self.extra = set(extra_closed or [])
        self._cache = {}

    def holidays(self, year):
        if year not in self._cache:
            self._cache[year] = danish_holidays(year, self.customary) if self.holiday_mode == "dk" else {}
        return self._cache[year]

    def closed_reason(self, d):
        if d in self.extra:
            return "extra closed day"
        return self.holidays(d.year).get(d)

    def window(self, d):
        if d.weekday() not in self.hours or self.closed_reason(d):
            return None
        o, c = self.hours[d.weekday()]
        return datetime.combine(d, o), datetime.combine(d, c)

    def business_hours(self, start, end):
        if end <= start:
            return 0.0
        total = 0.0
        d = start.date()
        while d <= end.date():
            w = self.window(d)
            if w:
                s, e = max(start, w[0]), min(end, w[1])
                if e > s:
                    total += (e - s).total_seconds()
            d += timedelta(days=1)
        return total / 3600.0

    def is_open_at(self, dt):
        w = self.window(dt.date())
        return bool(w and w[0] <= dt <= w[1])


# ---------------------------------------------------------------- Core analysis
def load_targets(arg):
    if not arg:
        return {k.upper(): dict(v) for k, v in DEFAULT_TARGETS.items()}
    try:
        if arg.strip().startswith("{"):
            data = json.loads(arg)
        else:
            with open(arg, encoding="utf-8") as f:
                data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit("Could not read --targets: %s" % exc)
    out = {}
    for k, v in data.items():
        if "first_response_hours" not in v or "resolution_hours" not in v:
            raise SystemExit("Target for %s needs first_response_hours and resolution_hours" % k)
        out[k.strip().upper()] = v
    return out


def analyse(rows, targets, cal, mode="business", as_of=None, input_tz="local",
            resolution_counts_as_response=False):
    warnings = []
    tickets = []
    seen = set()
    dst_notes = 0

    def conv(raw, label, line, tid):
        nonlocal dst_notes
        if not raw:
            return None, None
        try:
            dt, off = parse_datetime(raw)
        except ValueError as exc:
            warnings.append("Line %d (%s): %s %s, value ignored" % (line, tid, label, exc))
            return None, None
        if off is not None:
            utc = dt - timedelta(hours=off)
            return utc_to_cph_local(utc), utc
        if input_tz == "utc":
            return utc_to_cph_local(dt), dt
        utc, note = cph_local_to_utc(dt)
        if note:
            dst_notes += 1
            warnings.append("Line %d (%s): %s %s %s" % (line, tid, label, raw, note))
        return dt, utc

    for line, r in rows:
        tid = r.get("ticket_id", "")
        if not tid:
            warnings.append("Line %d: missing ticket_id, row skipped" % line)
            continue
        if tid in seen:
            warnings.append("Line %d: duplicate ticket_id %s, later row ignored" % (line, tid))
            continue
        seen.add(tid)
        created, created_u = conv(r["created_at"], "created_at", line, tid)
        if created is None:
            warnings.append("Line %d (%s): created_at missing or invalid, row skipped" % (line, tid))
            continue
        fr, fr_u = conv(r["first_response_at"], "first_response_at", line, tid)
        res, res_u = conv(r["resolved_at"], "resolved_at", line, tid)
        tickets.append({"line": line, "ticket_id": tid, "priority": r["priority"].strip().upper() or "(blank)",
                        "channel": r["channel"].strip().lower() or "(blank)", "created": created, "created_u": created_u,
                        "fr": fr, "fr_u": fr_u, "res": res, "res_u": res_u})

    if not tickets:
        raise SystemExit("No usable tickets found.")

    if as_of is None:
        latest = max(max(x for x in (t["created"], t["fr"], t["res"]) if x is not None) for t in tickets)
        as_of = latest
        warnings.append("No --as-of given: backlog measured to the latest timestamp in the file (%s). "
                        "Pass the export time for correct backlog ages." % as_of.strftime("%Y-%m-%d %H:%M"))
    as_of_u, _ = cph_local_to_utc(as_of) if input_tz == "local" else (as_of, None)
    if input_tz == "utc":
        as_of = utc_to_cph_local(as_of)

    def duration(t, start_l, start_u, end_l, end_u, pmode):
        if pmode == "calendar":
            return (end_u - start_u).total_seconds() / 3600.0
        return cal.business_hours(start_l, end_l)

    unknown_prios = set()
    outside = 0
    after_asof = 0
    for t in tickets:
        tgt = targets.get(t["priority"])
        if tgt is None:
            unknown_prios.add(t["priority"])
        pmode = (tgt or {}).get("mode", mode)
        t["mode"] = pmode
        t["fr_target"] = tgt["first_response_hours"] if tgt else None
        t["res_target"] = tgt["resolution_hours"] if tgt else None
        for key in ("fr", "res"):
            if t[key] is not None and t[key] > as_of:
                after_asof += 1
        # validity
        if t["res"] is not None and t["res"] < t["created"]:
            warnings.append("Ticket %s: resolved_at (%s) before created_at (%s), resolution excluded"
                            % (t["ticket_id"], t["res"].strftime("%Y-%m-%d %H:%M"), t["created"].strftime("%Y-%m-%d %H:%M")))
            t["res_invalid"] = True
        if t["fr"] is not None and t["fr"] < t["created"]:
            warnings.append("Ticket %s: first_response_at before created_at, first response excluded" % t["ticket_id"])
            t["fr_invalid"] = True
        if t["fr"] is not None and t["res"] is not None and t["fr"] > t["res"] and not t.get("res_invalid"):
            warnings.append("Ticket %s: first response after resolution, check the export" % t["ticket_id"])
        if pmode == "business":
            for key in ("fr", "res"):
                if t[key] is not None and not t.get(key + "_invalid") and not cal.is_open_at(t[key]):
                    outside += 1

        # first response
        fr_eff, fr_eff_u = t["fr"], t["fr_u"]
        if fr_eff is None and resolution_counts_as_response and t["res"] is not None and not t.get("res_invalid"):
            fr_eff, fr_eff_u = t["res"], t["res_u"]
        t["fr_hours"] = None
        if t.get("fr_invalid"):
            t["fr_status"] = "invalid"
        elif fr_eff is not None:
            t["fr_hours"] = duration(t, t["created"], t["created_u"], fr_eff, fr_eff_u, pmode)
            t["fr_status"] = "n/a" if t["fr_target"] is None else ("met" if t["fr_hours"] <= t["fr_target"] else "breached")
        elif t["res"] is not None:
            t["fr_status"] = "no response recorded"
            warnings.append("Ticket %s: resolved without a recorded first response, excluded from first response metrics"
                            % t["ticket_id"])
        else:
            age = duration(t, t["created"], t["created_u"], as_of, as_of_u, pmode)
            t["fr_hours_running"] = age
            if t["fr_target"] is None:
                t["fr_status"] = "n/a"
            else:
                t["fr_status"] = "breached (open)" if age > t["fr_target"] else "pending"
        # resolution
        t["res_hours"] = None
        t["open"] = t["res"] is None
        if t.get("res_invalid"):
            t["res_status"] = "invalid"
        elif t["res"] is not None:
            t["res_hours"] = duration(t, t["created"], t["created_u"], t["res"], t["res_u"], pmode)
            t["res_status"] = "n/a" if t["res_target"] is None else ("met" if t["res_hours"] <= t["res_target"] else "breached")
        else:
            t["age_business_h"] = cal.business_hours(t["created"], as_of)
            t["age_calendar_h"] = (as_of_u - t["created_u"]).total_seconds() / 3600.0
            age = t["age_calendar_h"] if pmode == "calendar" else t["age_business_h"]
            t["res_hours_running"] = age
            if t["res_target"] is None:
                t["res_status"] = "n/a"
            else:
                t["res_status"] = "breached (open)" if age > t["res_target"] else "pending"

    if unknown_prios:
        warnings.append("Priority value(s) with no SLA target: %s. Counted in volumes, left out of attainment. "
                        "Add them with --targets." % ", ".join(sorted(unknown_prios)))
    if outside:
        warnings.append("%d response or resolution timestamp(s) fall outside opening hours (weekend, evening or "
                        "holiday work, or a time zone issue). Check whether the SLA clock should run then." % outside)
    if after_asof:
        warnings.append("%d timestamp(s) are later than the as-of time; check --as-of." % after_asof)

    return tickets, warnings, as_of


def group_stats(ts):
    fr_vals = [t["fr_hours"] for t in ts if t["fr_hours"] is not None]
    res_vals = [t["res_hours"] for t in ts if t["res_hours"] is not None]

    def att(key):
        met = sum(1 for t in ts if t[key] == "met")
        br = sum(1 for t in ts if t[key].startswith("breached"))
        return met, br, (100.0 * met / (met + br) if met + br else None)

    fm, fb, fa = att("fr_status")
    rm, rb, ra = att("res_status")
    return {
        "tickets": len(ts), "open": sum(1 for t in ts if t["open"]),
        "fr_n": len(fr_vals), "fr_median": percentile(fr_vals, 0.5), "fr_p90": percentile(fr_vals, 0.9),
        "fr_met": fm, "fr_breached": fb, "fr_attainment": fa,
        "res_n": len(res_vals), "res_median": percentile(res_vals, 0.5), "res_p90": percentile(res_vals, 0.9),
        "res_met": rm, "res_breached": rb, "res_attainment": ra,
    }


def build_report(tickets, warnings, as_of, targets, cal, mode):
    overall = group_stats(tickets)
    by_prio = {}
    for p in sorted({t["priority"] for t in tickets}):
        by_prio[p] = group_stats([t for t in tickets if t["priority"] == p])
    by_chan = {}
    for c in sorted({t["channel"] for t in tickets}):
        by_chan[c] = group_stats([t for t in tickets if t["channel"] == c])
    open_t = sorted([t for t in tickets if t["open"] and not t.get("res_invalid")], key=lambda t: t["created"])
    buckets = {"under 1 day": 0, "1-3 days": 0, "3-7 days": 0, "over 7 days": 0}
    for t in open_t:
        d = t["age_calendar_h"] / 24.0
        key = "under 1 day" if d < 1 else "1-3 days" if d < 3 else "3-7 days" if d < 7 else "over 7 days"
        buckets[key] += 1
    breaches = []
    for t in tickets:
        if t["fr_status"].startswith("breached"):
            actual = t["fr_hours"] if t["fr_hours"] is not None else t["fr_hours_running"]
            breaches.append({"ticket_id": t["ticket_id"], "priority": t["priority"], "channel": t["channel"],
                             "metric": "first response", "status": t["fr_status"], "hours": actual,
                             "target": t["fr_target"], "over_by": actual - t["fr_target"]})
        if t["res_status"].startswith("breached"):
            actual = t["res_hours"] if t["res_hours"] is not None else t["res_hours_running"]
            breaches.append({"ticket_id": t["ticket_id"], "priority": t["priority"], "channel": t["channel"],
                             "metric": "resolution", "status": t["res_status"], "hours": actual,
                             "target": t["res_target"], "over_by": actual - t["res_target"]})
    breaches.sort(key=lambda b: (-b["over_by"], b["ticket_id"]))
    first = min(t["created"] for t in tickets).date()
    last = max(as_of.date(), max(t["created"] for t in tickets).date())
    hols = []
    if mode == "business" or any(t["mode"] == "business" for t in tickets):
        d = first
        while d <= last:
            reason = cal.closed_reason(d)
            if reason and d.weekday() in cal.hours:
                hols.append({"date": d.isoformat(), "name": reason})
            d += timedelta(days=1)
    return {"as_of": as_of.strftime("%Y-%m-%d %H:%M"), "mode": mode, "period_from": first.isoformat(),
            "period_to": max(t["created"] for t in tickets).date().isoformat(),
            "closed_days_in_period": hols, "overall": overall, "by_priority": by_prio, "by_channel": by_chan,
            "backlog": {"open": len(open_t), "age_buckets": buckets,
                        "tickets": [{"ticket_id": t["ticket_id"], "priority": t["priority"], "channel": t["channel"],
                                     "created": t["created"].strftime("%Y-%m-%d %H:%M"),
                                     "age_calendar_h": t["age_calendar_h"], "age_business_h": t["age_business_h"],
                                     "res_status": t["res_status"], "fr_status": t["fr_status"]} for t in open_t]},
            "breaches": breaches, "targets": targets, "warnings": warnings}


# ---------------------------------------------------------------- Output
def f(x, nd=2):
    return "-" if x is None else ("%.*f" % (nd, x))


def pct(x):
    return "-" if x is None else "%.1f%%" % x


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def markdown(rep):
    o = rep["overall"]
    unit = "business hours" if rep["mode"] == "business" else "calendar hours"
    lines = ["# SLA report", "",
             "Tickets created %s to %s. Backlog measured at %s. Times in %s (Europe/Copenhagen)."
             % (rep["period_from"], rep["period_to"], rep["as_of"], unit), ""]
    if rep["closed_days_in_period"]:
        lines.append("Closed days excluded from the clock: " + ", ".join(
            "%s %s" % (h["date"], h["name"]) for h in rep["closed_days_in_period"]) + ".")
        lines.append("")
    lines += ["## Headline metrics", "",
              table(["Metric", "Value"], [
                  ["Tickets", o["tickets"]],
                  ["Open at as-of time", o["open"]],
                  ["First response SLA attainment", "%s (%d met, %d breached)" % (pct(o["fr_attainment"]), o["fr_met"], o["fr_breached"])],
                  ["Resolution SLA attainment", "%s (%d met, %d breached)" % (pct(o["res_attainment"]), o["res_met"], o["res_breached"])],
                  ["First response median / p90 (h)", "%s / %s (n=%d)" % (f(o["fr_median"]), f(o["fr_p90"]), o["fr_n"])],
                  ["Resolution median / p90 (h)", "%s / %s (n=%d)" % (f(o["res_median"]), f(o["res_p90"]), o["res_n"])],
              ]), "", "## By priority", ""]
    rows = []
    for p, s in rep["by_priority"].items():
        tg = rep["targets"].get(p)
        rows.append([p, s["tickets"], tg["first_response_hours"] if tg else "none", f(s["fr_median"]), f(s["fr_p90"]),
                     "%s (%d/%d)" % (pct(s["fr_attainment"]), s["fr_met"], s["fr_met"] + s["fr_breached"]),
                     tg["resolution_hours"] if tg else "none", f(s["res_median"]), f(s["res_p90"]),
                     "%s (%d/%d)" % (pct(s["res_attainment"]), s["res_met"], s["res_met"] + s["res_breached"])])
    lines.append(table(["Priority", "Tickets", "FR target h", "FR median", "FR p90", "FR attainment",
                        "Res target h", "Res median", "Res p90", "Res attainment"], rows))
    lines += ["", "## By channel", ""]
    rows = [[c, s["tickets"], f(s["fr_median"]), f(s["fr_p90"]), pct(s["fr_attainment"]),
             f(s["res_median"]), f(s["res_p90"]), pct(s["res_attainment"]), s["open"]]
            for c, s in rep["by_channel"].items()]
    lines.append(table(["Channel", "Tickets", "FR median", "FR p90", "FR attainment", "Res median", "Res p90",
                        "Res attainment", "Open"], rows))
    b = rep["backlog"]
    lines += ["", "## Backlog (open tickets)", "",
              "Open: %d. Age (calendar): %s." % (b["open"], ", ".join("%s %d" % kv for kv in b["age_buckets"].items())), ""]
    if b["tickets"]:
        lines.append(table(["Ticket", "Priority", "Channel", "Created", "Age calendar h", "Age business h",
                            "First response", "Resolution"],
                           [[t["ticket_id"], t["priority"], t["channel"], t["created"], f(t["age_calendar_h"], 1),
                             f(t["age_business_h"], 1), t["fr_status"], t["res_status"]] for t in b["tickets"]]))
    lines += ["", "## Breaches", ""]
    if rep["breaches"]:
        lines.append(table(["Ticket", "Priority", "Channel", "Metric", "Status", "Actual h", "Target h", "Over by h"],
                           [[x["ticket_id"], x["priority"], x["channel"], x["metric"], x["status"], f(x["hours"]),
                             x["target"], f(x["over_by"])] for x in rep["breaches"]]))
    else:
        lines.append("No breaches.")
    lines += ["", "## Data quality warnings", ""]
    lines += ["- " + w for w in rep["warnings"]] or ["- None found."]
    lines += ["", "Method: attainment = met / (met + breached); open tickets past target count as breached, open "
              "tickets within target are pending. Median and p90 use linear interpolation. Holidays are computed "
              "Danish public holidays (Store Bededag only up to 2023), verify against your contract."]
    return "\n".join(lines)


def write_detail(path, tickets):
    cols = ["ticket_id", "priority", "channel", "mode", "created", "first_response", "resolved", "fr_hours",
            "fr_target", "fr_status", "res_hours", "res_target", "res_status", "open_age_business_h", "open_age_calendar_h"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for t in tickets:
            def ts(x):
                return x.strftime("%Y-%m-%d %H:%M") if x else ""
            frh = t["fr_hours"] if t["fr_hours"] is not None else t.get("fr_hours_running")
            w.writerow([t["ticket_id"], t["priority"], t["channel"], t["mode"], ts(t["created"]), ts(t["fr"]), ts(t["res"]),
                        "%.4f" % frh if frh is not None else "",
                        t["fr_target"] if t["fr_target"] is not None else "", t["fr_status"],
                        "%.4f" % t["res_hours"] if t["res_hours"] is not None else "",
                        t["res_target"] if t["res_target"] is not None else "", t["res_status"],
                        "%.4f" % t["age_business_h"] if "age_business_h" in t else "",
                        "%.4f" % t["age_calendar_h"] if "age_calendar_h" in t else ""])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Support SLA report from a ticket CSV (business or calendar hours, "
                                             "Danish holidays, Europe/Copenhagen time).",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Expected columns: " + ", ".join(REQUIRED) + ". Accepted header aliases "
                                        "(case, spaces and punctuation ignored; first match wins): " + alias_help()
                                        + ". The first response column must be a timestamp, not a duration.")
    ap.add_argument("csv", help="ticket CSV")
    ap.add_argument("--targets", help="SLA targets as JSON text or a JSON file path, e.g. "
                    "'{\"P1\": {\"first_response_hours\": 1, \"resolution_hours\": 8, \"mode\": \"calendar\"}}'. "
                    "Optional per-priority 'mode' overrides --mode. Default: P1 1/8, P2 4/16, P3 8/40, P4 16/80 hours "
                    "(examples only, use your contract values)")
    ap.add_argument("--mode", choices=["business", "calendar"], default="business",
                    help="measure in business hours (default) or calendar hours (24/7 SLAs)")
    ap.add_argument("--open-hours", default="08:00-16:00",
                    help="opening hours, '08:00-16:00' (default) or per day 'mon=08:00-16:00,fri=08:00-15:30'")
    ap.add_argument("--workdays", default="mon,tue,wed,thu,fri", help="open weekdays when --open-hours is one range")
    ap.add_argument("--holidays", choices=["dk", "none"], default="dk",
                    help="exclude Danish public holidays (default dk; Store Bededag only up to 2023). Verify current calendar")
    ap.add_argument("--customary-closed", action="store_true",
                    help="also close on Grundlovsdag (5 Jun), 24 Dec and 31 Dec (customary, not statutory)")
    ap.add_argument("--closed-dates", default="", help="extra closed dates, comma separated yyyy-mm-dd")
    ap.add_argument("--as-of", help="export time for backlog age and open breaches, e.g. '2026-10-31 23:59' "
                    "(default: latest timestamp in the file)")
    ap.add_argument("--input-tz", choices=["local", "utc"], default="local",
                    help="naive timestamps are Europe/Copenhagen local (default) or UTC")
    ap.add_argument("--resolution-counts-as-response", action="store_true",
                    help="use resolved_at as first response when first_response_at is blank")
    ap.add_argument("--out", help="write per-ticket detail CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)

    headers, rows = read_csv(a.csv)
    check_columns(headers, REQUIRED)
    targets = load_targets(a.targets)
    extra = []
    for s in [x for x in a.closed_dates.split(",") if x.strip()]:
        try:
            extra.append(parse_datetime(s)[0].date())
        except ValueError:
            raise SystemExit("Bad date in --closed-dates: %s" % s)
    cal = Calendar(parse_open_hours(a.open_hours, a.workdays), a.holidays, a.customary_closed, extra)
    as_of = None
    if a.as_of:
        try:
            as_of = parse_datetime(a.as_of)[0]
        except ValueError:
            raise SystemExit("Bad --as-of value: %s" % a.as_of)
        if len(a.as_of.strip()) <= 10:
            as_of = datetime.combine(as_of.date(), time(0, 0))
    tickets, warnings, as_of = analyse(rows, targets, cal, a.mode, as_of, a.input_tz, a.resolution_counts_as_response)
    rep = build_report(tickets, warnings, as_of, targets, cal, a.mode)
    if a.out:
        write_detail(a.out, tickets)
    if a.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(markdown(rep))


if __name__ == "__main__":
    main()
