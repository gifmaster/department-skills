#!/usr/bin/env python3
"""Budget vs actual variance analysis with materiality filter and price/volume split.

Purpose
  Calculates absolute and percentage variances per line, labels them favourable (F) or
  adverse (A) according to whether the line is revenue or cost, filters to material
  variances, splits variances into price and volume where quantities exist, and checks
  that everything reconciles.

Input columns (header names case-insensitive; comma or semicolon; "1.234,56" or "1234.56")
  line, type, budget, actual   [, budget_qty, actual_qty]
  type: revenue | cost | total
    "total" rows are control totals (e.g. the result from the P&L report). They are left out
    of the calculation and compared with the computed result = revenue - cost.
  Cost amounts may be positive (normal) or negative; see --cost-sign.

Formulas
  variance           = actual - budget
  variance %         = variance / |budget| x 100   (n/a when budget is 0)
  profit effect      = variance for revenue, -variance for costs (when costs are positive)
  favourable (F)     = profit effect > 0, adverse (A) < 0
  material           = |variance| >= --abs-threshold
                       OR (|variance %| >= --pct-threshold AND |variance| >= --pct-floor)
  price/volume split (only when both quantities are present and non-zero):
    budget price p0 = budget / budget_qty, actual price p1 = actual / actual_qty
    volume effect   = (actual_qty - budget_qty) x p0
    price effect    = (p1 - p0) x actual_qty          (for costs: rate or unit-cost effect)
    volume + price  = variance (checked)
  Mix is not separated: do not add quantities of different units across lines.

Example
  python3 scripts/variance.py assets/budget_actual.csv --abs-threshold 100000 --pct-threshold 10
"""

import argparse
import csv
import io
import json
import re
import sys

# ----------------------------------------------------------------- shared input helpers


class InputError(Exception):
    """Raised for unusable input; the message is shown to the user."""


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
    return "n/a" if v is None else ("{:,.%df}" % dec).format(v)


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out)


# ----------------------------------------------------------------- variance logic

REQUIRED = ["line", "type", "budget", "actual"]
OPTIONAL = ["budget_qty", "actual_qty"]
ALIASES = {"linje": "line", "konto": "line", "account": "line", "type_": "type", "kind": "type",
           "budget_amount": "budget", "faktisk": "actual", "realiseret": "actual",
           "budget_antal": "budget_qty", "faktisk_antal": "actual_qty"}
TYPE_ALIASES = {"revenue": "revenue", "income": "revenue", "omsætning": "revenue", "indtægt": "revenue", "r": "revenue",
                "cost": "cost", "expense": "cost", "omkostning": "cost", "udgift": "cost", "c": "cost",
                "total": "total", "subtotal": "total", "resultat": "total"}


def load(path, warnings):
    rows = read_table(path, REQUIRED, OPTIONAL, ALIASES)
    lines, controls = [], []
    for r in rows:
        ln = r["_line"]
        typ = TYPE_ALIASES.get(r["type"].strip().lower())
        if typ is None:
            warnings.append("line %d (%s): type '%s' must be revenue, cost or total; row skipped" % (ln, r["line"], r["type"]))
            continue
        try:
            b = parse_number(r["budget"])
            a = parse_number(r["actual"])
        except ValueError:
            warnings.append("line %d (%s): budget or actual is not a number; row skipped" % (ln, r["line"]))
            continue
        if b is None or a is None:
            warnings.append("line %d (%s): budget or actual missing; treated as 0, check the source" % (ln, r["line"]))
            b = b or 0.0
            a = a or 0.0
        bq = aq = None
        try:
            bq = parse_number(r.get("budget_qty", ""))
            aq = parse_number(r.get("actual_qty", ""))
        except ValueError:
            warnings.append("line %d (%s): quantity is not a number; no price/volume split" % (ln, r["line"]))
            bq = aq = None
        if (bq is None) != (aq is None):
            warnings.append("line %d (%s): only one quantity given; no price/volume split" % (ln, r["line"]))
        rec = {"line": r["line"], "type": typ, "budget": b, "actual": a, "budget_qty": bq, "actual_qty": aq, "row": ln}
        (controls if typ == "total" else lines).append(rec)
    return lines, controls


def analyse(lines, controls=(), abs_threshold=50000.0, pct_threshold=10.0, pct_floor=10000.0,
            cost_sign="auto", tolerance=1.0, warnings=None):
    warnings = warnings if warnings is not None else []
    costs = [l for l in lines if l["type"] == "cost"]
    if cost_sign == "auto":
        neg = sum(1 for l in costs if l["budget"] < 0 or l["actual"] < 0)
        cost_sign = "negative" if costs and neg > len(costs) / 2.0 else "positive"
        mixed = [l["line"] for l in costs if (l["budget"] < 0 or l["actual"] < 0) != (cost_sign == "negative") and (l["budget"] or l["actual"])]
        if mixed:
            warnings.append("cost lines with an unexpected sign (possible sign error): " + ", ".join(mixed))
    for l in lines:
        if l["type"] == "revenue" and (l["budget"] < 0 or l["actual"] < 0):
            warnings.append("revenue line '%s' has a negative value: check sign" % l["line"])
    out = []
    for l in lines:
        var = l["actual"] - l["budget"]
        pct = (var / abs(l["budget"]) * 100.0) if l["budget"] else None
        if l["type"] == "revenue" or cost_sign == "negative":
            effect = var
        else:
            effect = -var
        fa = "F" if effect > 0 else ("A" if effect < 0 else "-")
        material = abs(var) >= abs_threshold or (pct is not None and abs(pct) >= pct_threshold and abs(var) >= pct_floor)
        rec = dict(l, variance=round(var, 2), pct=None if pct is None else round(pct, 1), effect=round(effect, 2),
                   fa=fa, material=material, price=None, volume=None, budget_price=None, actual_price=None)
        if l["budget_qty"] and l["actual_qty"]:
            p0 = l["budget"] / l["budget_qty"]
            p1 = l["actual"] / l["actual_qty"]
            rec["budget_price"] = round(p0, 4)
            rec["actual_price"] = round(p1, 4)
            rec["volume"] = round((l["actual_qty"] - l["budget_qty"]) * p0, 2)
            rec["price"] = round((p1 - p0) * l["actual_qty"], 2)
            if abs(rec["volume"] + rec["price"] - rec["variance"]) > tolerance:
                warnings.append("line '%s': price + volume does not equal variance" % l["line"])
        elif (l["budget_qty"] == 0 or l["actual_qty"] == 0) and l["budget_qty"] is not None and l["actual_qty"] is not None:
            warnings.append("line '%s': a quantity is zero; no price/volume split" % l["line"])
        out.append(rec)

    sgn = -1.0 if cost_sign == "negative" else 1.0
    rev_b = sum(l["budget"] for l in lines if l["type"] == "revenue")
    rev_a = sum(l["actual"] for l in lines if l["type"] == "revenue")
    cost_b = sgn * sum(l["budget"] for l in lines if l["type"] == "cost")
    cost_a = sgn * sum(l["actual"] for l in lines if l["type"] == "cost")
    totals = {"revenue_budget": round(rev_b, 2), "revenue_actual": round(rev_a, 2),
              "cost_budget": round(cost_b, 2), "cost_actual": round(cost_a, 2),
              "result_budget": round(rev_b - cost_b, 2), "result_actual": round(rev_a - cost_a, 2)}
    totals["result_variance"] = round(totals["result_actual"] - totals["result_budget"], 2)
    sum_effects = round(sum(r["effect"] for r in out), 2)
    checks = [{"check": "sum of line profit effects = result variance", "expected": totals["result_variance"],
               "got": sum_effects, "ok": abs(sum_effects - totals["result_variance"]) <= tolerance}]
    split = [r for r in out if r["price"] is not None]
    if split:
        pv = round(sum(r["price"] + r["volume"] for r in split), 2)
        vv = round(sum(r["variance"] for r in split), 2)
        checks.append({"check": "price + volume = variance on lines with quantities", "expected": vv, "got": pv,
                       "ok": abs(pv - vv) <= tolerance})
    for c in controls:
        for col, comp in (("budget", totals["result_budget"]), ("actual", totals["result_actual"])):
            reported = c[col]
            ok = abs(reported - comp) <= tolerance
            checks.append({"check": "control total '%s' %s = revenue - cost" % (c["line"], col), "expected": round(reported, 2),
                           "got": comp, "ok": ok})
            if not ok:
                warnings.append("control total '%s' (%s) %s differs from computed %s by %s: a line is missing, duplicated or has a sign error" % (
                    c["line"], col, fmt(reported, 2), fmt(comp, 2), fmt(comp - reported, 2)))
    material = sorted([r for r in out if r["material"]], key=lambda r: (-abs(r["variance"]), r["line"]))
    return {"lines": out, "material": material, "totals": totals, "checks": checks, "cost_sign": cost_sign,
            "params": {"abs_threshold": abs_threshold, "pct_threshold": pct_threshold, "pct_floor": pct_floor},
            "warnings": warnings}


# ----------------------------------------------------------------- output


def render_markdown(res):
    t = res["totals"]
    p = res["params"]
    out = ["# Variance analysis, actual vs budget", ""]
    out.append("Result: budget %s, actual %s, variance **%s** (%s). Revenue %s vs %s; costs %s vs %s." % (
        fmt(t["result_budget"]), fmt(t["result_actual"]), fmt(t["result_variance"]),
        "F" if t["result_variance"] > 0 else ("A" if t["result_variance"] < 0 else "-"),
        fmt(t["revenue_actual"]), fmt(t["revenue_budget"]), fmt(t["cost_actual"]), fmt(t["cost_budget"])))
    out.append("Material variances: %d of %d lines (|variance| >= %s, or >= %s%% and >= %s)." % (
        len(res["material"]), len(res["lines"]), fmt(p["abs_threshold"]), fmt(p["pct_threshold"], 1), fmt(p["pct_floor"])))
    out += ["", "## 1. Variance table", ""]
    rows = [[r["line"], r["type"], fmt(r["budget"]), fmt(r["actual"]), fmt(r["variance"]),
             "n/a" if r["pct"] is None else "%.1f%%" % r["pct"], r["fa"], "yes" if r["material"] else ""] for r in res["lines"]]
    out.append(md_table(["Line", "Type", "Budget", "Actual", "Variance", "Var %", "F/A", "Material"], rows))
    out += ["", "## 2. Material variances and drivers", ""]
    if res["material"]:
        rows = []
        for r in res["material"]:
            if r["price"] is not None:
                word = "price" if r["type"] == "revenue" else "unit cost"
                drv = "volume %s, %s %s (%s %s vs %s per unit)" % (fmt(r["volume"]), word, fmt(r["price"]), word,
                                                                 fmt(r["actual_price"], 2), fmt(r["budget_price"], 2))
            else:
                drv = "no quantities: ask the budget owner (timing, one-off, rate?)"
            rows.append([r["line"], fmt(r["variance"]), "n/a" if r["pct"] is None else "%.1f%%" % r["pct"], r["fa"], drv])
        out.append(md_table(["Line", "Variance", "Var %", "F/A", "Drivers"], rows))
    else:
        out.append("No material variances.")
    out += ["", "## 3. Reconciliation checks", ""]
    out.append(md_table(["Check", "Expected", "Calculated", "Result"],
                        [[c["check"], fmt(c["expected"], 2), fmt(c["got"], 2), "OK" if c["ok"] else "FAIL"] for c in res["checks"]]))
    out += ["", "## 4. Data quality and assumptions", ""]
    notes = list(res["warnings"])
    notes.append("Cost sign convention: %s. F/A follows the profit effect: revenue above budget and cost below budget are favourable." % res["cost_sign"])
    notes.append("Price/volume split uses budget price for volume and actual quantity for price; driver amounts are signed like the variance (actual - budget). Mix is not separated.")
    out += ["- " + n for n in notes]
    return "\n".join(out)


def write_csv(path, res):
    cols = ["line", "type", "budget", "actual", "variance", "pct", "fa", "effect", "material", "budget_qty", "actual_qty",
            "budget_price", "actual_price", "volume", "price"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in res["lines"]:
            w.writerow(["" if r[c] is None else r[c] for c in cols])


def build_parser():
    p = argparse.ArgumentParser(description="Budget vs actual variances with F/A, materiality and price/volume split.")
    p.add_argument("csv", help="CSV with line, type (revenue|cost|total), budget, actual [, budget_qty, actual_qty]")
    p.add_argument("--abs-threshold", type=float, default=50000.0, help="Material if |variance| >= this amount (default 50,000)")
    p.add_argument("--pct-threshold", type=float, default=10.0, help="Material if |variance %%| >= this ... (default 10)")
    p.add_argument("--pct-floor", type=float, default=10000.0, help="... and |variance| >= this floor (default 10,000)")
    p.add_argument("--cost-sign", choices=("auto", "positive", "negative"), default="auto",
                   help="How cost lines are signed in the file (default auto-detect)")
    p.add_argument("--tolerance", type=float, default=1.0, help="Rounding tolerance for reconciliation checks (default 1.0)")
    p.add_argument("--out", help="Write the full line table to this CSV")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    warnings = []
    try:
        lines, controls = load(args.csv, warnings)
    except InputError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    if not lines:
        print("Error: no usable revenue or cost lines in %s" % args.csv, file=sys.stderr)
        return 2
    res = analyse(lines, controls, abs_threshold=args.abs_threshold, pct_threshold=args.pct_threshold,
                  pct_floor=args.pct_floor, cost_sign=args.cost_sign, tolerance=args.tolerance, warnings=warnings)
    if args.out:
        write_csv(args.out, res)
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else render_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
