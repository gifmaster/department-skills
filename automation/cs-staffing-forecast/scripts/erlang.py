#!/usr/bin/env python3
"""Erlang C staffing calculator per interval: required agents, service level, ASA, occupancy, headcount.

Purpose
  For each interval, finds the smallest number of agents that meets the service level target
  (for example 80% answered within 20 seconds) without exceeding the maximum occupancy, then
  converts agent hours to scheduled (paid) hours after shrinkage. Standard library only.

Input
  CSV with columns: interval_start, contacts   (optional columns: aht_seconds, overrides --aht per row;
  agents_available, agents planned per interval)
  or no CSV and --contacts "88,139,151" (one value per interval).
  Optional --available: a CSV with interval_start, agents_available (overrides the column), or a
  comma separated list with one value per interval (with --contacts).

Formulas
  Traffic A (Erlangs) = contacts x AHT / (interval minutes x 60).
  Erlang B by recursion (numerically stable): B(0) = 1, B(k) = A x B(k-1) / (k + A x B(k-1)).
  Erlang C (probability of waiting) for N agents > A: C = N x B(N) / (N - A x (1 - B(N))).
  Service level = 1 - C x exp(-(N - A) x T / AHT), T = target answer time in seconds.
  ASA = C x AHT / (N - A). Occupancy = A / N.
  Scheduled agents = N / (1 - shrinkage). Agent hours = N x interval minutes / 60.
  Available agents (when given): on-queue agents = agents_available (--available-basis on-queue,
  default) or agents_available x (1 - shrinkage) (--available-basis scheduled), rounded down to
  whole agents. Gap = on-queue available - required agents (positive surplus, negative shortfall).
  Achievable service level, ASA and occupancy use the same Erlang C formulas with N = available;
  with N <= A the queue is unstable and the service level is reported as 0.
  Limits: Erlang C assumes no abandonment, no retries, steady arrivals within the interval and
  agents handling one contact at a time, so it tends to overstate staff when queues are long.

Example
  python3 scripts/erlang.py assets/intervals_template.csv --aht 330 --sl 0.8 --answer-time 30
  python3 scripts/erlang.py --contacts 88,139,151 --interval-minutes 60 --aht 330 --answer-time 30
"""
import argparse
import csv
import io
import json
import math
import os
import re
from datetime import datetime

REQUIRED = ["interval_start", "contacts"]


# ---------------------------------------------------------------- helpers
def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        text = f.read()
    first = text.splitlines()[0] if text.strip() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    rows = []
    for line_no, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k is not None and not isinstance(v, list)}
        if any(row.values()):
            rows.append((line_no, row))
    return headers, rows, delim


def parse_number(s, delim=","):
    """Accepts 1234.56, 1234,56, 1.234,56 and 1,234.56. With a semicolon file, 1.234 means 1234."""
    s = re.sub(r"[\s ]", "", s or "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif s.count(".") > 1 or (delim == ";" and re.fullmatch(r"-?\d{1,3}\.\d{3}", s)):
        s = s.replace(".", "")
    return float(s)


def parse_interval(s):
    s = s.strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2}|\d{2}[-./]\d{2}[-./]\d{4})[T ](\d{1,2}:\d{2})", s)
    if m:
        dpart = m.group(1)
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                d = datetime.strptime(dpart, fmt)
                h, mi = m.group(2).split(":")
                return d.replace(hour=int(h), minute=int(mi))
            except ValueError:
                pass
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        return datetime(1900, 1, 1, int(m.group(1)), int(m.group(2)))
    raise ValueError("unrecognised interval_start '%s' (use yyyy-mm-dd HH:MM or HH:MM)" % s)


# ---------------------------------------------------------------- Erlang maths
def erlang_b(n, a):
    b = 1.0
    for k in range(1, n + 1):
        b = a * b / (k + a * b)
    return b


def erlang_c(n, a):
    if n <= a:
        return 1.0
    b = erlang_b(n, a)
    return n * b / (n - a * (1 - b))


def metrics(n, a, aht, answer_time):
    if a == 0:
        return {"pw": 0.0, "sl": 1.0, "asa": 0.0, "occupancy": 0.0}
    if n <= a:
        return {"pw": 1.0, "sl": 0.0, "asa": None, "occupancy": None}
    c = erlang_c(n, a)
    return {"pw": c, "sl": 1 - c * math.exp(-(n - a) * answer_time / aht), "asa": c * aht / (n - a),
            "occupancy": a / n}


def required_agents(a, aht, sl_target, answer_time, max_occ, min_agents=0):
    """Smallest N meeting the service level and the occupancy cap. Returns (N, metrics, binding)."""
    if a == 0:
        n = min_agents
        return n, metrics(n, 0, aht, answer_time), "no contacts"
    n = max(int(math.floor(a)) + 1, min_agents, 1)
    sl_n = None
    while True:
        m = metrics(n, a, aht, answer_time)
        if sl_n is None and m["sl"] >= sl_target:
            sl_n = n
        if m["sl"] >= sl_target and m["occupancy"] <= max_occ:
            break
        n += 1
        if n > 100000:
            raise SystemExit("No solution below 100,000 agents; check inputs.")
    binding = "service level" if sl_n == n else "max occupancy"
    if n == min_agents and sl_n is not None and sl_n < n:
        binding = "minimum agents"
    return n, m, binding


# ---------------------------------------------------------------- analysis
def analyse(intervals, aht, interval_minutes, sl_target, answer_time, max_occ, shrinkage, min_agents=0,
            volume_factor=1.0, hours_per_fte=7.4):
    if not 0 <= shrinkage < 1:
        raise SystemExit("--shrinkage must be between 0 and 1 (e.g. 0.3 for 30%)")
    if not 0 < sl_target < 1:
        raise SystemExit("--sl must be between 0 and 1 (e.g. 0.8)")
    if not 0 < max_occ <= 1:
        raise SystemExit("--max-occupancy must be above 0 and at most 1")
    secs = interval_minutes * 60.0
    res = []
    for iv in intervals:
        contacts = iv["contacts"] * volume_factor
        h = iv.get("aht") or aht
        a = contacts * h / secs
        n, m, binding = required_agents(a, h, sl_target, answer_time, max_occ, min_agents)
        res.append({"interval": iv["label"], "contacts": contacts, "aht": h, "erlangs": a, "agents": n,
                    "service_level": m["sl"], "asa_seconds": m["asa"], "occupancy": m["occupancy"],
                    "prob_wait": m["pw"], "binding": binding, "scheduled": n / (1 - shrinkage),
                    "scheduled_rounded": int(math.ceil(n / (1 - shrinkage) - 1e-9)),
                    "available": iv.get("available")})
    agent_hours = sum(r["agents"] for r in res) * interval_minutes / 60.0
    paid = agent_hours / (1 - shrinkage)
    total_contacts = sum(r["contacts"] for r in res)
    workload_h = sum(r["erlangs"] for r in res) * interval_minutes / 60.0
    answered_in_t = sum(r["contacts"] * r["service_level"] for r in res)
    return {"intervals": res, "totals": {
        "contacts": total_contacts, "workload_hours": workload_h, "agent_hours": agent_hours,
        "paid_hours": paid, "fte_days": paid / hours_per_fte if hours_per_fte else None,
        "peak_agents": max((r["agents"] for r in res), default=0),
        "peak_scheduled": max((r["scheduled_rounded"] for r in res), default=0),
        "weighted_service_level": answered_in_t / total_contacts if total_contacts else None,
        "average_occupancy": workload_h / agent_hours if agent_hours else None},
        "params": {"aht_seconds": aht, "interval_minutes": interval_minutes, "sl_target": sl_target,
                   "answer_time_seconds": answer_time, "max_occupancy": max_occ, "shrinkage": shrinkage,
                   "min_agents": min_agents, "volume_factor": volume_factor, "hours_per_fte": hours_per_fte}}


def available_metrics(rep, basis="on-queue"):
    """Add gap and achievable service level per interval where 'available' is known. Returns a summary."""
    p = rep["params"]
    shrink, minutes = p["shrinkage"], p["interval_minutes"]
    rows = [r for r in rep["intervals"] if r.get("available") is not None]
    if not rows:
        return None
    short_h = surplus_h = 0.0
    answered = contacts = 0.0
    n_short = 0
    for r in rows:
        raw = r["available"]
        on_queue = raw * (1 - shrink) if basis == "scheduled" else raw
        n = int(math.floor(on_queue + 1e-9))
        m = metrics(n, r["erlangs"], r["aht"], p["answer_time_seconds"])
        gap = n - r["agents"]
        r.update({"available_on_queue": n, "gap": gap,
                  "gap_status": "shortfall" if gap < 0 else ("surplus" if gap > 0 else "exact"),
                  "available_service_level": m["sl"], "available_asa_seconds": m["asa"],
                  "available_occupancy": m["occupancy"]})
        if gap < 0:
            n_short += 1
            short_h += -gap * minutes / 60.0
        else:
            surplus_h += gap * minutes / 60.0
        answered += r["contacts"] * m["sl"]
        contacts += r["contacts"]
    return {"basis": basis, "intervals_with_data": len(rows),
            "intervals_without_data": len(rep["intervals"]) - len(rows),
            "intervals_short": n_short, "shortfall_agent_hours": short_h, "surplus_agent_hours": surplus_h,
            "weighted_service_level_available": answered / contacts if contacts else None}


def load_available(path, interval_minutes):
    """Read interval_start, agents_available. Returns ({start: value}, warnings)."""
    headers, rows, delim = read_csv(path)
    need = ["interval_start", "agents_available"]
    missing = [c for c in need if c not in headers]
    if missing:
        raise SystemExit("Available file is missing column(s): %s. Expected columns: %s. Found: %s"
                         % (", ".join(missing), ", ".join(need), ", ".join(headers) or "(none)"))
    out, warnings = {}, []
    for line, r in rows:
        try:
            start = parse_interval(r["interval_start"])
            v = parse_number(r["agents_available"], delim)
        except ValueError as exc:
            warnings.append("Available line %d: %s, row skipped" % (line, exc))
            continue
        if v is None or v < 0:
            warnings.append("Available line %d: agents_available missing or negative, row skipped" % line)
            continue
        if start in out:
            warnings.append("Available line %d: duplicate interval %s, later row ignored" % (line, r["interval_start"]))
            continue
        out[start] = v
    return out, warnings


def parse_number_list(text, name):
    vals = []
    for v in [v for v in re.split(r"[;,]\s*", text) if v.strip()]:
        try:
            c = float(v)
        except ValueError:
            raise SystemExit("Bad value in %s: %s" % (name, v))
        if c < 0:
            raise SystemExit("%s cannot be negative: %s" % (name, v))
        vals.append(c)
    return vals


def load_intervals(path, interval_minutes):
    headers, rows, delim = read_csv(path)
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise SystemExit("Missing column(s): %s. Expected columns: %s (optional: aht_seconds). Found: %s"
                         % (", ".join(missing), ", ".join(REQUIRED), ", ".join(headers) or "(none)"))
    warnings = []
    out = []
    seen = {}
    for line, r in rows:
        try:
            start = parse_interval(r["interval_start"])
        except ValueError as exc:
            warnings.append("Line %d: %s, row skipped" % (line, exc))
            continue
        try:
            c = parse_number(r["contacts"], delim)
        except ValueError:
            c = "bad"
        if c is None or c == "bad":
            warnings.append("Line %d (%s): contacts missing or not a number, row skipped" % (line, r["interval_start"]))
            continue
        if c < 0:
            warnings.append("Line %d (%s): negative contacts (%s), row skipped" % (line, r["interval_start"], r["contacts"]))
            continue
        aht = None
        if r.get("aht_seconds"):
            try:
                aht = parse_number(r["aht_seconds"], delim)
            except ValueError:
                warnings.append("Line %d: aht_seconds not a number, default AHT used" % line)
            if aht is not None and aht <= 0:
                warnings.append("Line %d: aht_seconds must be positive, default AHT used" % line)
                aht = None
        if start in seen:
            warnings.append("Line %d: duplicate interval %s (first on line %d), later row ignored"
                            % (line, r["interval_start"], seen[start]))
            continue
        if start.minute % interval_minutes and interval_minutes <= 60:
            warnings.append("Line %d: interval %s is not aligned to %d-minute intervals" % (line, r["interval_start"], interval_minutes))
        seen[start] = line
        label = start.strftime("%H:%M") if start.year == 1900 else start.strftime("%Y-%m-%d %H:%M")
        rec = {"start": start, "label": label, "contacts": c, "aht": aht}
        if "agents_available" in headers and r.get("agents_available"):
            try:
                av = parse_number(r["agents_available"], delim)
            except ValueError:
                av = -1
            if av is None or av < 0:
                warnings.append("Line %d: agents_available not a number or negative, ignored" % line)
            else:
                rec["available"] = av
        out.append(rec)
    out.sort(key=lambda x: x["start"])
    for prev, cur in zip(out, out[1:]):
        gap = (cur["start"] - prev["start"]).total_seconds() / 60
        if prev["start"].date() == cur["start"].date() and gap > interval_minutes:
            warnings.append("Gap in intervals between %s and %s (missing interval rows?)" % (prev["label"], cur["label"]))
    return out, warnings


# ---------------------------------------------------------------- output
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def pct(x):
    return "-" if x is None else "%.1f%%" % (100 * x)


def markdown(rep, warnings):
    p, t = rep["params"], rep["totals"]
    L = ["# Staffing requirement (Erlang C)", "",
         "Target %.0f%% answered within %d s, AHT %d s, %d-minute intervals, max occupancy %.0f%%, shrinkage %.0f%%%s."
         % (100 * p["sl_target"], p["answer_time_seconds"], p["aht_seconds"], p["interval_minutes"],
            100 * p["max_occupancy"], 100 * p["shrinkage"],
            "" if p["volume_factor"] == 1 else ", volumes multiplied by %g" % p["volume_factor"]), "",
         "## Headline", "",
         table(["Metric", "Value"], [
             ["Contacts", "%.0f" % t["contacts"]],
             ["Workload (hours of handling)", "%.1f" % t["workload_hours"]],
             ["Agent hours on queue (sum of required agents)", "%.1f" % t["agent_hours"]],
             ["Paid hours after shrinkage", "%.1f" % t["paid_hours"]],
             ["Full-day equivalents (%.1f h)" % p["hours_per_fte"], "-" if t["fte_days"] is None else "%.1f" % t["fte_days"]],
             ["Peak agents on queue / scheduled", "%d / %d" % (t["peak_agents"], t["peak_scheduled"])],
             ["Contact-weighted service level", pct(t["weighted_service_level"])],
             ["Average occupancy", pct(t["average_occupancy"])],
         ]), "", "## Per interval", ""]
    rows = [[r["interval"], "%.0f" % r["contacts"], "%.2f" % r["erlangs"], r["agents"], pct(r["service_level"]),
             "-" if r["asa_seconds"] is None else "%.0f" % r["asa_seconds"], pct(r["occupancy"]),
             r["scheduled_rounded"], r["binding"]] for r in rep["intervals"]]
    L.append(table(["Interval", "Contacts", "Erlangs", "Agents", "Service level", "ASA s", "Occupancy",
                    "Scheduled", "Set by"], rows))
    L += ["", "Scheduled = agents / (1 - shrinkage), rounded up per interval. Headcount needs depend on shift "
          "patterns, breaks and working time rules (11-hour daily rest, weekly rest day, collective agreement).", "",
          ]
    av = rep.get("available_summary")
    if av:
        L += ["## Available agents vs requirement", "",
              "Basis: %s (%s). Gap = available on queue - required agents; negative is a shortfall."
              % (av["basis"], "agents_available used as on-queue agents" if av["basis"] == "on-queue"
                 else "agents_available x (1 - shrinkage), rounded down"), "",
              table(["Metric", "Value"], [
                  ["Intervals short / with data", "%d / %d" % (av["intervals_short"], av["intervals_with_data"])],
                  ["Shortfall agent hours", "%.1f" % av["shortfall_agent_hours"]],
                  ["Surplus agent hours", "%.1f" % av["surplus_agent_hours"]],
                  ["Contact-weighted service level with available agents", pct(av["weighted_service_level_available"])],
              ]), ""]
        rows = [[r["interval"], r["agents"], r["available_on_queue"], "%+d" % r["gap"], r["gap_status"],
                 pct(r["available_service_level"]),
                 "-" if r["available_asa_seconds"] is None else "%.0f" % r["available_asa_seconds"],
                 pct(r["available_occupancy"])]
                for r in rep["intervals"] if r.get("gap") is not None]
        L += [table(["Interval", "Required", "Available on queue", "Gap", "Status", "Achievable SL", "ASA s",
                     "Occupancy"], rows), ""]
        if av["intervals_without_data"]:
            L += ["%d interval(s) have no available-agent figure and are left out of the gap." % av["intervals_without_data"], ""]
    L += ["## Data quality warnings", ""]
    L += ["- " + w for w in warnings] or ["- None found."]
    L += ["", "## Erlang C limits", "",
          "- Assumes callers never abandon or retry, so with long queues it overstates the staff needed; "
          "an Erlang A model with patience data is more accurate there.",
          "- Assumes steady random arrivals within each interval and one contact per agent at a time "
          "(not valid for chat concurrency or email backlog work).",
          "- Results are only as good as the volume forecast and AHT; test +10% AHT and volume as a sensitivity check."]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Erlang C staffing per interval with shrinkage.",
                                 epilog="CSV columns: interval_start, contacts (optional aht_seconds). "
                                        "Or use --contacts without a CSV.")
    ap.add_argument("csv", nargs="?", help="interval CSV (omit when using --contacts)")
    ap.add_argument("--contacts", help="comma or semicolon separated contacts per interval, instead of a CSV")
    ap.add_argument("--aht", type=float, default=300, help="average handle time in seconds (default 300)")
    ap.add_argument("--interval-minutes", type=int, default=30, help="interval length in minutes (default 30)")
    ap.add_argument("--sl", type=float, default=0.8, help="service level target as a share, from your service policy or client contract (default 0.8)")
    ap.add_argument("--answer-time", type=float, default=20, help="target answer time in seconds, from your service policy or client contract (default 20)")
    ap.add_argument("--max-occupancy", type=float, default=0.85, help="maximum occupancy, a workforce policy limit (default 0.85)")
    ap.add_argument("--shrinkage", type=float, default=0.30,
                    help="share of paid time not available for contacts: breaks, meetings, training, absence; use your own measured figure (default 0.30)")
    ap.add_argument("--min-agents", type=int, default=0, help="minimum agents per open interval (default 0)")
    ap.add_argument("--volume-factor", type=float, default=1.0, help="multiply all contacts, e.g. 3 for a campaign day")
    ap.add_argument("--hours-per-fte", type=float, default=7.4,
                    help="paid hours per full-time day for the FTE figure (default 7.4 = 37 h / 5 days; verify "
                         "current value in your collective agreement)")
    ap.add_argument("--available",
                    help="agents available per interval: a CSV with interval_start, agents_available, or with "
                         "--contacts a comma separated list. An agents_available column in the main CSV is used "
                         "automatically. Reports the gap (surplus or shortfall) and achievable service level")
    ap.add_argument("--available-basis", choices=["on-queue", "scheduled"], default="on-queue",
                    help="on-queue (default): agents_available are agents taking contacts; scheduled: paid "
                         "headcount, reduced by --shrinkage first")
    ap.add_argument("--out", help="write per-interval results CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    if a.aht <= 0 or a.interval_minutes <= 0 or a.answer_time < 0:
        raise SystemExit("--aht and --interval-minutes must be positive, --answer-time not negative")
    if a.contacts:
        vals = parse_number_list(a.contacts, "--contacts")
        intervals = [{"label": "interval %d" % (i + 1), "contacts": c, "aht": None} for i, c in enumerate(vals)]
        warnings = []
        if a.available:
            if os.path.isfile(a.available):
                raise SystemExit("With --contacts, give --available as a comma separated list, not a file.")
            avs = parse_number_list(a.available, "--available")
            if len(avs) != len(intervals):
                warnings.append("--available has %d values for %d intervals; extra or missing values ignored"
                                % (len(avs), len(intervals)))
            for iv, v in zip(intervals, avs):
                iv["available"] = v
    elif a.csv:
        intervals, warnings = load_intervals(a.csv, a.interval_minutes)
        if a.available:
            if not os.path.isfile(a.available):
                raise SystemExit("--available file not found: %s (expected columns: interval_start, "
                                 "agents_available)" % a.available)
            avail, w2 = load_available(a.available, a.interval_minutes)
            warnings += w2
            for iv in intervals:
                iv.pop("available", None)
                if iv["start"] in avail:
                    iv["available"] = avail.pop(iv["start"])
            if avail:
                warnings.append("%d available-agent row(s) match no interval and were ignored" % len(avail))
    else:
        raise SystemExit("Give an interval CSV (columns: interval_start, contacts) or --contacts.")
    if not intervals:
        raise SystemExit("No usable intervals.")
    rep = analyse(intervals, a.aht, a.interval_minutes, a.sl, a.answer_time, a.max_occupancy, a.shrinkage,
                  a.min_agents, a.volume_factor, a.hours_per_fte)
    av_summary = available_metrics(rep, a.available_basis)
    if av_summary:
        rep["available_summary"] = av_summary
        missing_av = [r["interval"] for r in rep["intervals"] if r.get("available") is None]
        if missing_av:
            warnings.append("No agents_available for %d interval(s): %s" % (len(missing_av), ", ".join(missing_av)))
    else:
        for r in rep["intervals"]:
            r.pop("available", None)
    rep["warnings"] = warnings
    if a.out:
        cols = ["interval", "contacts", "aht", "erlangs", "agents", "service_level", "asa_seconds", "occupancy",
                "prob_wait", "scheduled", "scheduled_rounded", "binding"]
        if av_summary:
            cols += ["available", "available_on_queue", "gap", "gap_status", "available_service_level",
                     "available_asa_seconds", "available_occupancy"]
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in rep["intervals"]:
                w.writerow([("%.4f" % r.get(c)) if isinstance(r.get(c), float) else ("" if r.get(c) is None else r[c])
                            for c in cols])
    if a.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        print(markdown(rep, warnings))


if __name__ == "__main__":
    main()
