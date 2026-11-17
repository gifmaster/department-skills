#!/usr/bin/env python3
"""Gender pay gap analysis from an anonymised payroll extract, normalised to hourly pay.

Purpose
  Calculates mean and median gender pay gaps for base and total pay, gaps per category of
  equal work or work of equal value, flags category gaps at or above a threshold (default 5%,
  the Directive (EU) 2023/970 joint pay assessment trigger), shares of women and men in each pay
  quartile and the share receiving variable pay. Groups with fewer than --min-group people of
  either gender are suppressed; a group with no women or no men is "not calculable". Standard library only.
  A gap is a statistic, not a finding of discrimination: unexplained gaps need an objective,
  gender-neutral justification or correction.

Input columns (CSV, comma or semicolon, header names case-insensitive)
  employee_ref, gender, category, base_pay_annual, variable_pay_annual, hours_per_week
  optional: fte (used for hours when hours_per_week is blank: hours = fte x --full-time-hours)
  Pay is the annual amount actually paid for the contracted hours. Gender values: M/male/man/mand
  and F/K/female/woman/kvinde; other values are counted but not part of the binary gap.

Formulas
  Hourly base = base_pay_annual / (hours_per_week x 52).
  Hourly total = (base_pay_annual + variable_pay_annual) / (hours_per_week x 52).
  Gap = (men - women) / men x 100, for mean and for median. Positive = men paid more.
  Category flag: |mean gap| >= threshold on base or total hourly pay.
  Quartiles: everyone sorted by hourly pay (ties by employee_ref), split into four groups as equal
  as possible (person i of n goes to quartile floor(4i/n) + 1).

Example
  python3 scripts/paygap.py assets/payroll_template.csv
  python3 scripts/paygap.py payroll.csv --min-group 5 --threshold 5 --quartile-basis base --out detail.csv
"""
import argparse
import csv
import io
import json
import math
import re
import statistics

REQUIRED = ["employee_ref", "gender", "category", "base_pay_annual", "variable_pay_annual", "hours_per_week"]
MEN = {"m", "male", "man", "men", "mand", "maend", "mænd", "han"}
WOMEN = {"f", "k", "female", "woman", "women", "kvinde", "kvinder", "hun", "w"}


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
    """Accepts 1234.56, 1234,56, 1.234,56 and 1,234.56. With a semicolon file, 412.000 means 412000."""
    s = re.sub(r"(?i)[\s ]|dkk|kr\.?", "", s or "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif s.count(".") > 1 or (delim == ";" and re.fullmatch(r"-?\d{1,3}\.\d{3}", s)):
        s = s.replace(".", "")
    return float(s)


def gap(men, women):
    if not men or men == 0 or women is None:
        return None
    return 100.0 * (men - women) / men


def gender_of(v):
    v = v.strip().lower()
    if v in MEN:
        return "men"
    if v in WOMEN:
        return "women"
    return None


def load(rows, delim, full_time_hours=37.0):
    warnings = []
    people = []
    seen = set()
    other = 0
    for line, r in rows:
        ref = r.get("employee_ref", "")
        if not ref:
            warnings.append("Line %d: missing employee_ref, row skipped" % line)
            continue
        if ref in seen:
            warnings.append("Line %d: duplicate employee_ref %s, later row ignored" % (line, ref))
            continue
        seen.add(ref)
        g = gender_of(r["gender"])
        if g is None:
            other += 1
            continue
        nums = {}
        bad = False
        for col in ("base_pay_annual", "variable_pay_annual", "hours_per_week", "fte"):
            try:
                nums[col] = parse_number(r.get(col, ""), delim)
            except ValueError:
                warnings.append("Line %d (%s): %s is not a number ('%s')" % (line, ref, col, r.get(col)))
                nums[col] = None
                if col in ("base_pay_annual", "hours_per_week"):
                    bad = True
        if bad:
            warnings.append("Line %d (%s): row skipped" % (line, ref))
            continue
        hours = nums["hours_per_week"]
        if hours is None and nums["fte"]:
            hours = nums["fte"] * full_time_hours
            warnings.append("%s: hours_per_week blank, derived from fte %.2f x %.1f h" % (ref, nums["fte"], full_time_hours))
        elif hours is not None and nums["fte"] and abs(hours - nums["fte"] * full_time_hours) > 0.05 * hours:
            warnings.append("%s: hours_per_week %.1f does not match fte %.2f x %.1f h, hours_per_week used"
                            % (ref, hours, nums["fte"], full_time_hours))
        if not hours or hours <= 0:
            warnings.append("Line %d (%s): hours_per_week missing or zero, row skipped" % (line, ref))
            continue
        if hours > 60:
            warnings.append("%s: %.1f hours per week looks wrong (monthly hours?), check" % (ref, hours))
        base = nums["base_pay_annual"]
        if base is None or base <= 0:
            warnings.append("Line %d (%s): base_pay_annual missing, zero or negative, row skipped" % (line, ref))
            continue
        var = nums["variable_pay_annual"]
        if var is None:
            var = 0.0
            warnings.append("%s: variable_pay_annual blank, treated as 0" % ref)
        if var < 0:
            warnings.append("%s: negative variable pay (%.0f), check for clawback or sign error; treated as 0" % (ref, var))
            var = 0.0
        if base < 100000 and hours >= 15:
            warnings.append("%s: base pay %.0f looks like a monthly figure, check that it is annual" % (ref, base))
        cat = r.get("category", "") or "(no category)"
        if cat == "(no category)":
            warnings.append("%s: category blank, grouped as '(no category)'" % ref)
        annual_hours = hours * 52
        people.append({"ref": ref, "gender": g, "category": cat, "hours": hours, "base": base, "variable": var,
                       "hourly_base": base / annual_hours, "hourly_total": (base + var) / annual_hours})
    if other:
        warnings.append("%d employee(s) with a gender value other than woman or man: counted in headcount, not in "
                        "the binary gap figures" % other)
    return people, warnings, other


def stats_for(group):
    out = {}
    for g in ("men", "women"):
        ps = [p for p in group if p["gender"] == g]
        out[g] = {"n": len(ps)}
        for key in ("hourly_base", "hourly_total"):
            vals = [p[key] for p in ps]
            out[g][key + "_mean"] = statistics.mean(vals) if vals else None
            out[g][key + "_median"] = statistics.median(vals) if vals else None
        out[g]["variable_share"] = 100.0 * sum(1 for p in ps if p["variable"] > 0) / len(ps) if ps else None
    out["gaps"] = {}
    for key in ("hourly_base_mean", "hourly_base_median", "hourly_total_mean", "hourly_total_median"):
        out["gaps"][key] = gap(out["men"][key], out["women"][key])
    return out


def not_calculable(s):
    """Return 'no women' / 'no men' when one gender is absent (no gap exists), else None."""
    if s["women"]["n"] == 0:
        return "no women"
    if s["men"]["n"] == 0:
        return "no men"
    return None


def suppressed(s, k):
    """Suppressed = both genders present but fewer than k of either (gap exists, too few to show)."""
    return not_calculable(s) is None and (s["men"]["n"] < k or s["women"]["n"] < k)


def status_of(s):
    nc = not_calculable(s)
    if nc:
        return "not calculable (%s)" % nc
    return "suppressed" if s["suppressed"] else "shown"


def quartiles(people, basis):
    key = "hourly_total" if basis == "total" else "hourly_base"
    srt = sorted(people, key=lambda p: (p[key], p["ref"]))
    n = len(srt)
    q = {1: [], 2: [], 3: [], 4: []}
    for i, p in enumerate(srt):
        q[(4 * i) // n + 1].append(p)
    out = []
    for i in range(1, 5):
        ps = q[i]
        m = sum(1 for p in ps if p["gender"] == "men")
        w = len(ps) - m
        out.append({"quartile": i, "n": len(ps), "men": m, "women": w,
                    "men_pct": 100.0 * m / len(ps) if ps else None, "women_pct": 100.0 * w / len(ps) if ps else None,
                    "min_hourly": ps[0][key] if ps else None, "max_hourly": ps[-1][key] if ps else None})
    return out


def analyse(people, min_group=5, threshold=5.0, quartile_basis="total"):
    if not people:
        raise SystemExit("No usable employees (need gender woman/man, hours and base pay).")
    warnings = []
    overall = stats_for(people)
    overall["suppressed"] = suppressed(overall, min_group)
    overall["status"] = status_of(overall)
    cats = []
    for c in sorted({p["category"] for p in people}):
        s = stats_for([p for p in people if p["category"] == c])
        s["category"] = c
        s["suppressed"] = suppressed(s, min_group)
        s["status"] = status_of(s)
        s["flags"] = []
        if s["status"] == "shown":
            for key, label in (("hourly_base_mean", "base"), ("hourly_total_mean", "total")):
                gv = s["gaps"][key]
                if gv is not None and abs(gv) >= threshold:
                    s["flags"].append("mean %s pay gap %.1f%%" % (label, gv))
        cats.append(s)
    q = quartiles(people, quartile_basis)
    if any(x["n"] < min_group for x in q):
        warnings.append("At least one pay quartile has fewer than %d people; quartile shares may identify "
                        "individuals, do not publish them" % min_group)
    return {"overall": overall, "categories": cats, "quartiles": q, "quartile_basis": quartile_basis,
            "min_group": min_group, "threshold": threshold, "n": len(people), "warnings": warnings}


# ---------------------------------------------------------------- output
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def money(x):
    return "-" if x is None else "%.2f" % x


def pc(x):
    return "-" if x is None else "%.1f%%" % x


def markdown(rep, load_warnings):
    o = rep["overall"]
    k = rep["min_group"]
    L = ["# Gender pay gap analysis", "",
         "%d employees in the binary gap figures (%d men, %d women). Pay normalised to hourly: annual pay / "
         "(hours per week x 52). Gap = (men - women) / men. Positive means men are paid more." %
         (rep["n"], o["men"]["n"], o["women"]["n"]), "", "## Pay gap metrics", ""]
    if o["status"].startswith("not calculable"):
        L.append("Overall gap %s: the binary gap needs both women and men." % o["status"])
    elif o["suppressed"]:
        L.append("Suppressed: fewer than %d men or women in total." % k)
    else:
        rows = []
        for key, label in (("hourly_base_mean", "Mean hourly base pay"), ("hourly_base_median", "Median hourly base pay"),
                           ("hourly_total_mean", "Mean hourly total pay"), ("hourly_total_median", "Median hourly total pay")):
            rows.append([label, money(o["men"][key]), money(o["women"][key]), pc(o["gaps"][key])])
        rows.append(["Share receiving variable pay", pc(o["men"]["variable_share"]), pc(o["women"]["variable_share"]), ""])
        L.append(table(["Metric", "Men", "Women", "Gap"], rows))
    L += ["", "## Categories of equal work or work of equal value", ""]
    rows = []
    for c in rep["categories"]:
        if c["status"].startswith("not calculable"):
            rows.append([c["category"], "%d / %d" % (c["men"]["n"], c["women"]["n"]), c["status"], "", "", "", ""])
        elif c["suppressed"]:
            rows.append([c["category"], "%d / %d" % (c["men"]["n"], c["women"]["n"]),
                         "suppressed (< %d of a gender)" % k, "", "", "", ""])
        else:
            g = c["gaps"]
            rows.append([c["category"], "%d / %d" % (c["men"]["n"], c["women"]["n"]), pc(g["hourly_base_mean"]),
                         pc(g["hourly_base_median"]), pc(g["hourly_total_mean"]), pc(g["hourly_total_median"]),
                         "; ".join(c["flags"]) or "below %.0f%%" % rep["threshold"]])
    L.append(table(["Category", "Men / women", "Mean base gap", "Median base gap", "Mean total gap",
                    "Median total gap", "Flag"], rows))
    flagged = [c for c in rep["categories"] if c["flags"]]
    L += ["", "## Category gaps at or above %.0f%%" % rep["threshold"], ""]
    shown = [c for c in rep["categories"] if c["status"] == "shown"]
    supp = [c for c in rep["categories"] if c["status"] == "suppressed"]
    nocalc = [c for c in rep["categories"] if c["status"].startswith("not calculable")]
    for c in flagged:
        L.append("- %s: %s. Needs an objective, gender-neutral justification (for example documented "
                 "differences in experience, performance or responsibility) or correction." % (c["category"], "; ".join(c["flags"])))
    if not flagged:
        L.append("- No category flagged among the %d that could be assessed." % len(shown) if shown
                 else "- No category could be assessed.")
    if supp:
        L.append("- %d %s suppressed (fewer than %d women or men) and could not be assessed against the %.0f%% "
                 "threshold: %s. Review them internally on the full data." % (
                     len(supp), "category was" if len(supp) == 1 else "categories were", k, rep["threshold"],
                     ", ".join(c["category"] for c in supp)))
    if nocalc:
        L.append("- %d %s not calculable (only one gender present), so no gap exists to assess: %s." % (
            len(nocalc), "category is" if len(nocalc) == 1 else "categories are",
            ", ".join("%s (%s)" % (c["category"], c["status"][len("not calculable ("):-1]) for c in nocalc)))
    L += ["", "## Pay quartiles (hourly %s pay, lowest to highest)" % rep["quartile_basis"], ""]
    L.append(table(["Quartile", "People", "Men", "Women", "Hourly range"],
                   [["Q%d" % q["quartile"], q["n"], "%d (%s)" % (q["men"], pc(q["men_pct"])),
                     "%d (%s)" % (q["women"], pc(q["women_pct"])),
                     "%s - %s" % (money(q["min_hourly"]), money(q["max_hourly"]))] for q in rep["quartiles"]]))
    L += ["", "## Data quality warnings", ""]
    ws = load_warnings + rep["warnings"]
    L += ["- " + w for w in ws] or ["- None found."]
    L += ["", "## How to read this", "",
          "- A pay gap is a statistic, not proof of discrimination. Gaps that objective, gender-neutral criteria do "
          "not explain must be justified or corrected; under Directive (EU) 2023/970 an unjustified category gap of "
          "5% or more not remedied within six months triggers a joint pay assessment (check the Danish transposition).",
          "- Suppression protects people in small groups in published figures; the full data may still have to be "
          "available to workers' representatives and authorities.",
          "- Check that categories really group work of equal value and that all pay components (allowances, "
          "overtime, pension, benefits in kind) are included before reporting."]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gender pay gap analysis (hourly normalised) from anonymised payroll.",
                                 epilog="Expected columns: " + ", ".join(REQUIRED) + " (optional: fte)")
    ap.add_argument("csv", help="anonymised payroll CSV")
    ap.add_argument("--min-group", type=int, default=5,
                    help="suppress any group with fewer than this many women or men (default 5)")
    ap.add_argument("--threshold", type=float, default=5.0,
                    help="flag category mean gaps at or above this percent (default 5, the Directive (EU) "
                         "2023/970 joint pay assessment trigger; verify current value in the Danish act)")
    ap.add_argument("--quartile-basis", choices=["total", "base"], default="total",
                    help="hourly pay used for quartile bands (default total)")
    ap.add_argument("--full-time-hours", type=float, default=37.0,
                    help="weekly hours of a full-time employee, used only with fte (default 37; verify current value in "
                         "your collective agreement)")
    ap.add_argument("--out", help="write per-employee hourly pay and quartile CSV (internal use, not for publication)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    headers, rows, delim = read_csv(a.csv)
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise SystemExit("Missing column(s): %s. Expected columns: %s (optional: fte). Found: %s"
                         % (", ".join(missing), ", ".join(REQUIRED), ", ".join(headers) or "(none)"))
    people, warnings, _ = load(rows, delim, a.full_time_hours)
    rep = analyse(people, a.min_group, a.threshold, a.quartile_basis)
    if a.out:
        key = "hourly_total" if a.quartile_basis == "total" else "hourly_base"
        srt = sorted(people, key=lambda p: (p[key], p["ref"]))
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["employee_ref", "gender", "category", "hours_per_week", "hourly_base", "hourly_total", "quartile"])
            for i, p in enumerate(srt):
                w.writerow([p["ref"], p["gender"], p["category"], p["hours"], "%.2f" % p["hourly_base"],
                            "%.2f" % p["hourly_total"], (4 * i) // len(srt) + 1])
    if a.json:
        out = dict(rep)
        if rep["overall"]["suppressed"]:
            out["overall"] = {"suppressed": True}
        elif rep["overall"]["status"] != "shown":
            out["overall"] = {"suppressed": False, "status": rep["overall"]["status"]}

        def public(c):
            if c["suppressed"]:
                return {"category": c["category"], "suppressed": True}
            if c["status"] != "shown":
                return {"category": c["category"], "suppressed": False, "status": c["status"],
                        "men_n": c["men"]["n"], "women_n": c["women"]["n"]}
            return c
        out["categories"] = [public(c) for c in rep["categories"]]
        out["categories_suppressed"] = sum(1 for c in rep["categories"] if c["suppressed"])
        out["categories_not_calculable"] = sum(1 for c in rep["categories"] if c["status"].startswith("not calculable"))
        out["warnings"] = warnings + rep["warnings"]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(markdown(rep, warnings))


if __name__ == "__main__":
    main()
