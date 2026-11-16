#!/usr/bin/env python3
"""Sales pipeline review: coverage, weighted pipeline, stage ageing, deal flags and the deals that decide the period.

Purpose
  Reads a CRM pipeline export and reports won to date, open pipeline closing in the period,
  coverage of the remaining target, weighted pipeline, age by stage, per-owner totals and flags
  (close date in the past, no next step, stale activity, pushed close date, data errors).
  Owners are shown exactly as given. Standard library only.

Input columns (CSV, comma or semicolon, header names case-insensitive)
  deal, owner, stage, amount, close_date, created_date, last_activity_date
  optional: next_step, probability (0-100 or 0-1, overrides the stage default), previous_close_date

Formulas and rules
  Open deal = stage not in --won-stages or --lost-stages. Closed deals never count as open pipeline.
  Won in period = won deals with close_date in [period start, period end].
  Remaining target = max(target - won in period, 0).
  Open in period = open deals with close_date in [period start, period end] (overdue deals inside the
  period are included and flagged; deals dated before the period are flagged and left out).
  Coverage = open in period / remaining target. Weighted = sum(amount x probability).
  Forecast on probabilities = won in period + weighted open in period.
  Deal age = today - created_date (time in the current stage needs stage history, not in a normal export).
  Stale = today - last_activity_date > --stale-days. Pushed = close_date later than previous_close_date.
  Deals that decide the period = largest open in-period deals by amount, added until their sum covers
  the remaining target (at most --key-deals).

Example
  python3 scripts/pipeline.py assets/pipeline_template.csv --today 2026-11-16 --target 4200000
  python3 scripts/pipeline.py export.csv --today 2026-11-16 --period-start 2026-10-01 --period-end 2026-12-31 \\
      --target 4200000 --stages "Discovery:10,Qualification:20,Proposal:40,Negotiation:70" --stale-days 21
"""
import argparse
import csv
import io
import json
import re
import statistics
from datetime import date, datetime, timedelta

REQUIRED = ["deal", "owner", "stage", "amount", "close_date", "created_date", "last_activity_date"]
OPTIONAL = ["next_step", "probability", "previous_close_date"]
NO_VALUES = {"", "no", "nej", "false", "0", "none", "n/a", "-", "ingen"}


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
    """Accepts 1234.56, 1234,56, 1.234,56 and 1,234.56. With a semicolon file, 420.000 means 420000."""
    s = re.sub(r"(?i)[\s ]|dkk|kr\.?|eur|€|%", "", s or "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif s.count(".") > 1 or (delim == ";" and re.fullmatch(r"-?\d{1,3}\.\d{3}", s)):
        s = s.replace(".", "")
    return float(s)


def parse_date(s):
    s = (s or "").strip().split("T")[0].split(" ")[0]
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("unrecognised date '%s'" % s)


def quarter_bounds(d):
    q0 = 3 * ((d.month - 1) // 3) + 1
    start = date(d.year, q0, 1)
    end = date(d.year + (q0 == 10), 1 if q0 == 10 else q0 + 3, 1) - timedelta(days=1)
    return start, end


def parse_stages(spec):
    order = []
    probs = {}
    for part in [p for p in spec.split(",") if p.strip()]:
        if ":" in part:
            name, p = part.rsplit(":", 1)
            probs[name.strip().lower()] = float(p) / 100.0 if float(p) > 1 else float(p)
        else:
            name = part
        order.append(name.strip())
    return order, probs


def analyse(rows, delim, today, period_start, period_end, target=None, stale_days=14,
            stages="Discovery:10,Qualification:20,Proposal:40,Negotiation:70",
            won_stages="closed won,won,vundet", lost_stages="closed lost,lost,tabt", key_deals=5):
    warnings = []
    order, probs = parse_stages(stages)
    order_l = [o.lower() for o in order]
    won = {s.strip().lower() for s in won_stages.split(",") if s.strip()}
    lost = {s.strip().lower() for s in lost_stages.split(",") if s.strip()}
    deals = []
    seen = set()
    unknown_stages = set()
    for line, r in rows:
        name = r.get("deal", "")
        if not name:
            warnings.append("Line %d: missing deal name, row skipped" % line)
            continue
        if name in seen:
            warnings.append("Line %d: duplicate deal '%s', later row ignored" % (line, name))
            continue
        seen.add(name)
        d = {"deal": name, "owner": r.get("owner", "") or "(no owner)", "stage": r.get("stage", ""), "flags": []}
        try:
            d["amount"] = parse_number(r["amount"], delim)
        except ValueError:
            d["amount"] = None
        if d["amount"] is None:
            warnings.append("Deal %s: amount missing or not a number, counted as 0" % name)
            d["flags"].append("amount missing")
            d["amount"] = 0.0
        elif d["amount"] < 0:
            warnings.append("Deal %s: negative amount %.0f, check sign" % (name, d["amount"]))
            d["flags"].append("negative amount")
        for col in ("close_date", "created_date", "last_activity_date", "previous_close_date"):
            try:
                d[col] = parse_date(r.get(col, ""))
            except ValueError as exc:
                d[col] = None
                warnings.append("Deal %s: %s %s" % (name, col, exc))
        st = d["stage"].lower()
        d["status"] = "won" if st in won else "lost" if st in lost else "open"
        if d["status"] == "open" and st not in order_l:
            unknown_stages.add(d["stage"] or "(blank)")
        prob = None
        if r.get("probability"):
            try:
                prob = parse_number(r["probability"], delim)
                prob = prob / 100.0 if prob > 1 else prob
            except ValueError:
                warnings.append("Deal %s: probability not a number, stage default used" % name)
        if prob is None:
            prob = probs.get(st, 0.0)
        if d["status"] == "won":
            prob = 1.0
        elif d["status"] == "lost":
            prob = 0.0
        d["probability"] = prob
        d["weighted"] = d["amount"] * prob
        if d["status"] == "open":
            if d["close_date"] is None:
                d["flags"].append("no close date")
            elif d["close_date"] < today:
                d["flags"].append("close date in the past (%s)" % d["close_date"].isoformat())
            if "next_step" in r and r.get("next_step", "").strip().lower() in NO_VALUES:
                d["flags"].append("no next step")
            if d["last_activity_date"] is None:
                d["flags"].append("no activity date")
            else:
                idle = (today - d["last_activity_date"]).days
                d["days_idle"] = idle
                if idle > stale_days:
                    d["flags"].append("stale: %d days since activity" % idle)
            if d["previous_close_date"] and d["close_date"] and d["close_date"] > d["previous_close_date"]:
                d["flags"].append("close date pushed %d days" % (d["close_date"] - d["previous_close_date"]).days)
            if d["created_date"]:
                d["age_days"] = (today - d["created_date"]).days
        if d["created_date"] and d["close_date"] and d["close_date"] < d["created_date"]:
            warnings.append("Deal %s: close_date before created_date" % name)
            d["flags"].append("close before created")
        if d["last_activity_date"] and d["last_activity_date"] > today:
            warnings.append("Deal %s: last activity %s is after today" % (name, d["last_activity_date"]))
        deals.append(d)
    if "next_step" not in {k for _, r in rows[:1] for k in r}:
        warnings.append("No next_step column: missing next steps cannot be checked")
    if unknown_stages:
        warnings.append("Open stage(s) not in --stages: %s. Probability 0 and placed last in the stage table."
                        % ", ".join(sorted(unknown_stages)))

    def in_period(d):
        return d["close_date"] is not None and period_start <= d["close_date"] <= period_end

    won_p = [d for d in deals if d["status"] == "won" and in_period(d)]
    open_all = [d for d in deals if d["status"] == "open"]
    open_p = [d for d in open_all if in_period(d)]
    before = [d for d in open_all if d["close_date"] and d["close_date"] < period_start]
    after = [d for d in open_all if d["close_date"] and d["close_date"] > period_end]
    won_amt = sum(d["amount"] for d in won_p)
    open_amt = sum(d["amount"] for d in open_p)
    weighted = sum(d["weighted"] for d in open_p)
    remaining = max(target - won_amt, 0.0) if target is not None else None
    coverage = (open_amt / remaining if remaining else None) if target is not None else None

    # stage table
    stage_rows = []
    names = order + sorted({d["stage"] for d in open_all if d["stage"].lower() not in order_l})
    for s in names:
        ds = [d for d in open_all if d["stage"].lower() == s.lower()]
        if not ds:
            stage_rows.append({"stage": s, "deals": 0, "amount": 0.0, "weighted_in_period": 0.0, "median_age": None,
                               "mean_age": None, "median_idle": None})
            continue
        ages = [d["age_days"] for d in ds if "age_days" in d]
        idles = [d["days_idle"] for d in ds if "days_idle" in d]
        stage_rows.append({"stage": s, "deals": len(ds), "amount": sum(d["amount"] for d in ds),
                           "weighted_in_period": sum(d["weighted"] for d in ds if in_period(d)),
                           "median_age": statistics.median(ages) if ages else None,
                           "mean_age": statistics.mean(ages) if ages else None,
                           "median_idle": statistics.median(idles) if idles else None})

    owners = []
    for o in sorted({d["owner"] for d in deals}):
        ds = [d for d in deals if d["owner"] == o]
        owners.append({"owner": o, "won_in_period": sum(d["amount"] for d in ds if d in won_p),
                       "open_in_period": sum(d["amount"] for d in ds if d in open_p),
                       "weighted_in_period": sum(d["weighted"] for d in ds if d in open_p),
                       "open_deals": sum(1 for d in ds if d["status"] == "open"),
                       "flagged_deals": sum(1 for d in ds if d["status"] == "open" and d["flags"])})

    key = []
    cum = 0.0
    for d in sorted(open_p, key=lambda x: (-x["amount"], x["deal"])):
        if len(key) >= key_deals or (remaining is not None and cum >= remaining and key):
            break
        cum += d["amount"]
        key.append({"deal": d["deal"], "owner": d["owner"], "stage": d["stage"], "amount": d["amount"],
                    "probability": d["probability"], "close_date": d["close_date"].isoformat(),
                    "share_of_remaining": 100 * d["amount"] / remaining if remaining else None,
                    "cumulative_share": 100 * cum / remaining if remaining else None, "flags": d["flags"]})

    flagged = [d for d in open_all if d["flags"]]
    flagged.sort(key=lambda d: (-len(d["flags"]), -d["amount"], d["deal"]))
    return {
        "today": today.isoformat(), "period_start": period_start.isoformat(), "period_end": period_end.isoformat(),
        "target": target, "won_in_period": won_amt, "won_deals": len(won_p), "remaining_target": remaining,
        "open_in_period": open_amt, "open_deals_in_period": len(open_p), "weighted_in_period": weighted,
        "forecast_on_probabilities": won_amt + weighted, "coverage": coverage,
        "open_before_period": [d["deal"] for d in before], "open_after_period_amount": sum(d["amount"] for d in after),
        "open_after_period_deals": len(after), "lost_deals": sum(1 for d in deals if d["status"] == "lost"),
        "stages": stage_rows, "owners": owners, "key_deals": key,
        "flagged": [{"deal": d["deal"], "owner": d["owner"], "stage": d["stage"], "amount": d["amount"],
                     "close_date": d["close_date"].isoformat() if d["close_date"] else "",
                     "flags": d["flags"]} for d in flagged],
        "stale_days": stale_days, "warnings": warnings, "deals": deals}


# ---------------------------------------------------------------- output
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def m(x):
    return "-" if x is None else "{:,.0f}".format(x)


def deals_txt(k):
    return "%d deal%s" % (k, "" if k == 1 else "s")


def n1(x):
    return "-" if x is None else "%.0f" % x


def markdown(rep):
    L = ["# Pipeline review", "",
         "Today %s. Period %s to %s. Stale after %d days without activity." % (
             rep["today"], rep["period_start"], rep["period_end"], rep["stale_days"]), "",
         "## Pipeline health summary", ""]
    rows = [["Won in period", "%s (%s)" % (m(rep["won_in_period"]), deals_txt(rep["won_deals"]))]]
    if rep["target"] is not None:
        rows += [["Target", m(rep["target"])], ["Remaining to target", m(rep["remaining_target"])]]
    rows += [["Open pipeline closing in period", "%s (%s)" % (m(rep["open_in_period"]), deals_txt(rep["open_deals_in_period"]))],
             ["Weighted open pipeline in period", m(rep["weighted_in_period"])],
             ["Won + weighted", m(rep["forecast_on_probabilities"]) + (
                 " (%.0f%% of target)" % (100 * rep["forecast_on_probabilities"] / rep["target"]) if rep["target"] else "")]]
    if rep["target"] is not None:
        rows.append(["Coverage (open in period / remaining target)",
                     "target already met" if not rep["remaining_target"] else "%.2fx" % rep["coverage"]])
    rows.append(["Open pipeline dated after the period", "%s (%s)" % (m(rep["open_after_period_amount"]),
                                                                    deals_txt(rep["open_after_period_deals"]))])
    L.append(table(["Metric", "Value"], rows))
    if rep["target"] is None:
        L += ["", "No --target given, so coverage and remaining target are not calculated."]
    if rep["open_before_period"]:
        L += ["", "Open deals with a close date before the period (left out, need a new date): %s."
              % ", ".join(rep["open_before_period"])]
    L += ["", "## Stage ageing (open deals)", "",
          table(["Stage", "Deals", "Amount", "Weighted in period", "Median age days", "Mean age days",
                 "Median days since activity"],
                [[s["stage"], s["deals"], m(s["amount"]), m(s["weighted_in_period"]), n1(s["median_age"]),
                  n1(s["mean_age"]), n1(s["median_idle"])] for s in rep["stages"]]),
          "", "Age is days since the deal was created; time in the current stage needs stage history from the CRM.",
          "", "## By owner", "",
          table(["Owner", "Won in period", "Open in period", "Weighted in period", "Open deals", "Flagged"],
                [[o["owner"], m(o["won_in_period"]), m(o["open_in_period"]), m(o["weighted_in_period"]),
                  o["open_deals"], o["flagged_deals"]] for o in rep["owners"]]),
          "", "## Flagged deals", ""]
    if rep["flagged"]:
        L.append(table(["Deal", "Owner", "Stage", "Amount", "Close date", "Flags"],
                       [[d["deal"], d["owner"], d["stage"], m(d["amount"]), d["close_date"], "; ".join(d["flags"])]
                        for d in rep["flagged"]]))
    else:
        L.append("No flags.")
    L += ["", "## Deals that decide the period", ""]
    if rep["key_deals"]:
        L.append(table(["Deal", "Owner", "Stage", "Amount", "Probability", "Close date", "Share of remaining",
                        "Cumulative", "Flags"],
                       [[k["deal"], k["owner"], k["stage"], m(k["amount"]), "%.0f%%" % (100 * k["probability"]),
                         k["close_date"], "-" if k["share_of_remaining"] is None else "%.0f%%" % k["share_of_remaining"],
                         "-" if k["cumulative_share"] is None else "%.0f%%" % k["cumulative_share"],
                         "; ".join(k["flags"]) or "-"] for k in rep["key_deals"]]))
    else:
        L.append("No open deals close in the period.")
    L += ["", "## Data quality warnings", ""]
    L += ["- " + w for w in rep["warnings"]] or ["- None found."]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pipeline review: coverage, weighted pipeline, ageing and deal flags.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Expected columns: %s (optional: %s)" % (", ".join(REQUIRED), ", ".join(OPTIONAL)))
    ap.add_argument("csv", help="pipeline export CSV")
    ap.add_argument("--today", help="date to compare against, yyyy-mm-dd (default: system date; pass it for "
                                    "reproducible output)")
    ap.add_argument("--period-start", help="period start (default: first day of the quarter containing --period-end)")
    ap.add_argument("--period-end", help="period end (default: last day of the quarter containing today)")
    ap.add_argument("--target", help="sales target for the period (amount)")
    ap.add_argument("--stale-days", type=int, default=14, help="days without activity before a deal is stale (default 14)")
    ap.add_argument("--stages", default="Discovery:10,Qualification:20,Proposal:40,Negotiation:70",
                    help="open stages in order with default win probability in percent "
                         "(default 'Discovery:10,Qualification:20,Proposal:40,Negotiation:70'; use your CRM values)")
    ap.add_argument("--won-stages", default="Closed Won,Won,Vundet", help="stage names meaning won")
    ap.add_argument("--lost-stages", default="Closed Lost,Lost,Tabt", help="stage names meaning lost")
    ap.add_argument("--key-deals", type=int, default=5, help="maximum deals listed as deciding the period (default 5)")
    ap.add_argument("--out", help="write per-deal detail CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    try:
        today = parse_date(a.today) if a.today else date.today()
        pend = parse_date(a.period_end) if a.period_end else quarter_bounds(today)[1]
        pstart = parse_date(a.period_start) if a.period_start else quarter_bounds(pend)[0]
    except ValueError as exc:
        raise SystemExit("Bad date parameter: %s" % exc)
    if pstart > pend:
        raise SystemExit("--period-start is after --period-end")
    headers, rows, delim = read_csv(a.csv)
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise SystemExit("Missing column(s): %s. Expected columns: %s (optional: %s). Found: %s"
                         % (", ".join(missing), ", ".join(REQUIRED), ", ".join(OPTIONAL), ", ".join(headers) or "(none)"))
    target = None
    if a.target:
        try:
            target = parse_number(a.target, ";" if "." in a.target and "," not in a.target and
                                  re.fullmatch(r"\d{1,3}(\.\d{3})+", a.target) else ",")
        except ValueError:
            raise SystemExit("Bad --target value: %s" % a.target)
    rep = analyse(rows, delim, today, pstart, pend, target, a.stale_days, a.stages, a.won_stages, a.lost_stages,
                  a.key_deals)
    if not a.today:
        rep["warnings"].insert(0, "No --today given: system date %s used." % today.isoformat())
    if a.out:
        cols = ["deal", "owner", "stage", "status", "amount", "probability", "weighted", "close_date", "created_date",
                "last_activity_date", "age_days", "days_idle", "flags"]
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for d in rep["deals"]:
                w.writerow([("; ".join(d[c]) if c == "flags" else ("" if d.get(c) is None else d.get(c, ""))) for c in cols])
    if a.json:
        out = {k: v for k, v in rep.items() if k != "deals"}
        print(json.dumps(out, indent=2, default=str, ensure_ascii=False))
    else:
        print(markdown(rep))


if __name__ == "__main__":
    main()
