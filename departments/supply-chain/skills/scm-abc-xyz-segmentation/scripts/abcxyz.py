#!/usr/bin/env python3
"""ABC-XYZ segmentation of items from period consumption data.

Purpose
    Classify items by value contribution (ABC) and demand variability (XYZ),
    build the 9-box matrix and suggest a planning policy per box.

Input columns (long CSV, comma or semicolon, one row per item and period)
    item, period, quantity, unit_value
    period: yyyy-mm (dates are bucketed to yyyy-mm; other labels are sorted as text).
    Duplicate item-period rows are summed (with a warning).

Formulas
    value         = sum(quantity x unit_value); items with shorter history are scaled to the
                    full window: value / history periods x window periods (run-rate value)
    ABC           = rank by value, cumulative share incl. the item: A <= a (default 80 %),
                    B <= b (default 95 %), else C; the top item is always A
    XYZ           = CoV = population SD / mean over the item's history periods, zeros included:
                    X < x (default 0.5), Y < y (default 1.0), else Z
    zero share    = periods with zero demand / history periods; intermittent if >= threshold
                    (default 0.3), "lumpy" if also CoV of the non-zero periods >= lumpy-cv (0.7)
    history       = periods from the item's first row to the last period in the file;
                    items with fewer than --min-periods (default 6) are reported separately
    delisting     = no demand in the last --dead-periods (default 6) periods

Example
    python3 scripts/abcxyz.py assets/abcxyz_consumption.csv --a 0.8 --b 0.95 --x 0.5 --y 1.0
"""
import argparse
import csv
import io
import json
import math
import re
import statistics
import sys
from datetime import datetime

REQUIRED = ["item", "period", "quantity", "unit_value"]
OPTIONAL = []

POLICIES = {
    "AX": "Statistical reorder point, tight safety stock (95-98 % CSL), weekly review, call-off or VMI",
    "AY": "Forecast plus safety stock, monthly review, find the demand drivers (contracts, projects)",
    "AZ": "No normal-distribution safety stock: small fixed buffer agreed with sales/service, order to demand, ask for consignment",
    "BX": "Reorder point or min-max, 95 % CSL, periodic review",
    "BY": "Min-max with forecast, monthly review",
    "BZ": "Order to demand where lead time allows, otherwise a small fixed buffer; quarterly review",
    "CX": "Two-bin or generous min-max, large lots, minimal planner effort",
    "CY": "Min-max, quarterly review, larger lots",
    "CZ": "Order on demand or delist; keep only labelled insurance stock if critical",
}

# ---------------------------------------------------------------- shared helpers
class InputError(Exception):
    pass


def detect_delimiter(text):
    for line in text.splitlines():
        if line.strip():
            return ";" if line.count(";") > line.count(",") else ","
    return ","


def read_table(path, required, optional=()):
    """Read a CSV into a list of (line_no, dict) with lower-case, stripped headers."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        raise InputError("Cannot read file %s: %s" % (path, exc))
    rows = list(csv.reader(io.StringIO(text), delimiter=detect_delimiter(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise InputError("File is empty. Expected columns: %s" % ", ".join(required))
    header = [h.strip().lower() for h in rows[0]]
    missing = [c for c in required if c not in header]
    if missing:
        raise InputError("Missing column(s): %s. Expected columns: %s (optional: %s). Found: %s"
                         % (", ".join(missing), ", ".join(required),
                            ", ".join(optional) or "none", ", ".join(header)))
    out = []
    for i, r in enumerate(rows[1:], start=2):
        r = r + [""] * (len(header) - len(r))
        out.append((i, {h: r[k].strip() for k, h in enumerate(header)}))
    return out


def parse_number(value):
    """Parse '1.234,56', '1234.56', '1,234.56', '-12', '(12)', '12-'. Blank -> None."""
    if value is None:
        return None
    t = str(value).strip().replace(" ", "").replace(" ", "")
    t = re.sub(r"(?i)(dkk|kr\.?|eur|€)", "", t)
    if t == "":
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    if t.endswith("-"):
        neg, t = True, t[:-1]
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if t.count(",") > 1 else t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        num = float(t)
    except ValueError:
        raise ValueError("not a number: %r" % value)
    return -num if neg else num


def parse_date(value):
    t = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    raise ValueError("not a date (use yyyy-mm-dd or dd-mm-yyyy): %r" % value)


def fmt(x, dp=0):
    if x is None:
        return "-"
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return "n/a"
    return "{:,.{}f}".format(x, dp)


def pct(x, dp=1):
    return "-" if x is None else "{:.{}f} %".format(x * 100, dp)


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def clean_json(obj):
    """Replace inf/nan with None so the output is valid JSON."""
    if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    return obj


# ---------------------------------------------------------------- core logic
def norm_period(p):
    t = p.strip()
    if re.fullmatch(r"\d{4}-\d{2}", t):
        return t
    if re.fullmatch(r"\d{4}-\d{1}", t):
        return t[:5] + "0" + t[5:]
    try:
        return parse_date(t).strftime("%Y-%m")
    except ValueError:
        return t


def period_range(periods):
    """Fill monthly gaps when all periods are yyyy-mm."""
    if periods and all(re.fullmatch(r"\d{4}-\d{2}", p) for p in periods):
        y, m = int(periods[0][:4]), int(periods[0][5:])
        end = periods[-1]
        out = []
        while True:
            cur = "%04d-%02d" % (y, m)
            out.append(cur)
            if cur >= end:
                break
            m += 1
            if m > 12:
                y, m = y + 1, 1
        return out
    return periods


def classify(value, thresholds, labels):
    for t, lab in zip(thresholds, labels):
        if value < t:
            return lab
    return labels[-1]


def compute(records, a=0.80, b=0.95, x=0.5, y=1.0, min_periods=6, intermittent_share=0.3,
            lumpy_cv=0.7, dead_periods=6):
    warnings = []
    qty, val, last_uv, seen_keys = {}, {}, {}, set()
    for line, r in records:
        item = r["item"]
        if not item or not r["period"]:
            warnings.append("Line %d: missing item or period, row skipped." % line)
            continue
        per = norm_period(r["period"])
        try:
            q = parse_number(r["quantity"])
            uv = parse_number(r["unit_value"])
        except ValueError as exc:
            warnings.append("Line %d (%s): %s, row skipped." % (line, item, exc))
            continue
        if q is None:
            warnings.append("Line %d (%s %s): missing quantity, read as 0." % (line, item, per))
            q = 0.0
        if q < 0:
            warnings.append("Line %d (%s %s): negative quantity %s (return or sign error), netted into the period."
                            % (line, item, per, fmt(q)))
        if uv is None:
            if item in last_uv:
                uv = last_uv[item]
                warnings.append("Line %d (%s %s): missing unit_value, %s from another row used."
                                % (line, item, per, fmt(uv, 2)))
            else:
                warnings.append("Line %d (%s %s): missing unit_value, value counted later if another row has it."
                                % (line, item, per))
        else:
            last_uv[item] = uv
        if (item, per) in seen_keys:
            warnings.append("Line %d: duplicate row for %s %s, quantities summed." % (line, item, per))
        seen_keys.add((item, per))
        qty.setdefault(item, {})
        qty[item][per] = qty[item].get(per, 0.0) + q
        val.setdefault(item, [])
        val[item].append((q, uv))
    if not qty:
        raise InputError("No usable rows.")
    window = period_range(sorted({p for d in qty.values() for p in d}))
    n_window = len(window)
    items, short = [], []
    for item in sorted(qty):
        uv_fallback = last_uv.get(item)
        if uv_fallback is None:
            warnings.append("%s: no unit_value on any row, item skipped." % item)
            continue
        total_value = sum(q * (u if u is not None else uv_fallback) for q, u in val[item])
        first = min(qty[item])
        hist = [p for p in window if p >= first]
        series = [qty[item].get(p, 0.0) for p in hist]
        n = len(series)
        total_qty = sum(series)
        rec = {"item": item, "first_period": first, "history_periods": n, "total_qty": total_qty,
               "value": total_value}
        if n < min_periods:
            rec["run_rate_value"] = total_value / n * n_window if n else 0.0
            short.append(rec)
            continue
        mean = total_qty / n
        sd = statistics.pstdev(series)
        cov = sd / mean if mean > 0 else float("inf")
        zeros = sum(1 for s in series if s <= 0)
        nz = [s for s in series if s > 0]
        nz_cov = (statistics.pstdev(nz) / statistics.mean(nz)) if len(nz) > 1 else 0.0
        zero_share = zeros / n
        if zero_share >= intermittent_share:
            pattern = "lumpy" if nz_cov >= lumpy_cv else "intermittent"
        else:
            pattern = "smooth" if cov < x else "erratic"
        dead = len(series) >= dead_periods and all(s <= 0 for s in series[-dead_periods:])
        rec.update({"run_rate_value": total_value / n * n_window, "mean": mean, "sd": sd, "cov": cov,
                    "zero_share": zero_share, "nonzero_cov": nz_cov, "pattern": pattern, "dead": dead,
                    "xyz": classify(cov, [x, y], ["X", "Y", "Z"])})
        items.append(rec)
    items.sort(key=lambda r: (-r["run_rate_value"], r["item"]))
    total = sum(max(r["run_rate_value"], 0.0) for r in items)
    cum = 0.0
    for k, r in enumerate(items):
        v = max(r["run_rate_value"], 0.0)
        r["share"] = v / total if total > 0 else 0.0
        cum += r["share"]
        r["cum_share"] = cum
        if v <= 0:
            r["abc"] = "C"
        elif k == 0 or cum <= a + 1e-9:
            r["abc"] = "A"
        elif cum <= b + 1e-9:
            r["abc"] = "B"
        else:
            r["abc"] = "C"
        r["segment"] = r["abc"] + r["xyz"]
        r["policy"] = POLICIES[r["segment"]]
        if r["pattern"] in ("lumpy", "intermittent"):
            r["policy"] += "; intermittent demand: use min-max or Croston-type logic, not a normal safety stock"
    box = {}
    for cls in "ABC":
        for v in "XYZ":
            members = [r for r in items if r["segment"] == cls + v]
            box[cls + v] = {"count": len(members), "value": sum(r["run_rate_value"] for r in members),
                            "share": sum(r["share"] for r in members)}
    delist = [r["item"] for r in items if r["dead"]]
    delist_cz = [r["item"] for r in items if r["segment"] == "CZ" and not r["dead"]]
    return {"parameters": {"a": a, "b": b, "x": x, "y": y, "min_periods": min_periods,
                           "intermittent_share": intermittent_share, "lumpy_cv": lumpy_cv,
                           "dead_periods": dead_periods},
            "window": {"first": window[0], "last": window[-1], "periods": n_window},
            "items": items, "short_history": short, "nine_box": box, "total_value": total,
            "delisting_candidates": delist, "order_on_demand_candidates": delist_cz, "warnings": warnings}


def render(res):
    p, w = res["parameters"], res["window"]
    out = ["# ABC-XYZ segmentation", ""]
    out.append("**%d items segmented, %d with too little history.** Window %s to %s (%d periods). "
               "Total value %s." % (len(res["items"]), len(res["short_history"]), w["first"], w["last"],
                                    w["periods"], fmt(res["total_value"])))
    out += ["", "## 1. Thresholds used", "",
            "- ABC on value (quantity x unit value, run-rate scaled to the window): A up to %s cumulative, "
            "B up to %s, C above" % (pct(p["a"], 0), pct(p["b"], 0)),
            "- XYZ on CoV = population SD / mean, zero periods included: X below %s, Y below %s, Z from %s"
            % (fmt(p["x"], 2), fmt(p["y"], 2), fmt(p["y"], 2)),
            "- Intermittent if zero periods >= %s; lumpy if also CoV of non-zero periods >= %s"
            % (pct(p["intermittent_share"], 0), fmt(p["lumpy_cv"], 2)),
            "- Items with fewer than %d periods of history are listed separately" % p["min_periods"],
            "", "## 2. Segmentation table", ""]
    rows = [[r["item"], fmt(r["total_qty"]), fmt(r["run_rate_value"]), pct(r["share"]), pct(r["cum_share"]),
             fmt(r["mean"], 2), fmt(r["sd"], 2), fmt(r["cov"], 2), pct(r["zero_share"], 0), r["pattern"],
             "**" + r["segment"] + "**"] for r in res["items"]]
    out.append(md_table(["Item", "Qty", "Value", "Share", "Cum.", "Mean/period", "SD", "CoV",
                         "Zero periods", "Pattern", "Segment"], rows))
    out += ["", "### 9-box (count / value / share of value)", ""]
    rows = []
    for cls in "ABC":
        row = [cls]
        for v in "XYZ":
            c = res["nine_box"][cls + v]
            row.append("%d / %s / %s" % (c["count"], fmt(c["value"]), pct(c["share"])))
        rows.append(row)
    out.append(md_table(["", "X", "Y", "Z"], rows))
    out += ["", "## 3. Policies per segment", ""]
    for seg in POLICIES:
        members = [r["item"] for r in res["items"] if r["segment"] == seg]
        if members:
            out.append("- **%s** (%s): %s" % (seg, ", ".join(members), POLICIES[seg]))
    lumpy = [r["item"] for r in res["items"] if r["pattern"] in ("lumpy", "intermittent")]
    if lumpy:
        out.append("- Intermittent or lumpy demand (%s): use min-max or Croston-type logic, not a normal "
                   "safety stock" % ", ".join(lumpy))
    out += ["", "## 4. Delisting candidates and items handled separately", ""]
    out.append("- No demand in the last %d periods: %s" % (p["dead_periods"],
                                                           ", ".join(res["delisting_candidates"]) or "none"))
    out.append("- CZ items to consider for order on demand or delisting: %s"
               % (", ".join(res["order_on_demand_candidates"]) or "none"))
    if res["short_history"]:
        out.append("- Too little history (not ranked, classify by hand or merge with a predecessor item):")
        for r in res["short_history"]:
            out.append("  - %s: %d periods from %s, qty %s, value %s, run-rate value %s"
                       % (r["item"], r["history_periods"], r["first_period"], fmt(r["total_qty"]),
                          fmt(r["value"]), fmt(r["run_rate_value"])))
    if res["warnings"]:
        out += ["", "## Data-quality warnings", ""] + ["- " + x for x in res["warnings"]]
    return "\n".join(out) + "\n"


def write_csv(res, path):
    cols = ["item", "segment", "abc", "xyz", "pattern", "history_periods", "total_qty", "value",
            "run_rate_value", "share", "cum_share", "mean", "sd", "cov", "zero_share", "nonzero_cov",
            "dead", "policy"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in res["items"]:
            w.writerow([round(r[c], 4) if isinstance(r[c], float) else r[c] for c in cols])
        for r in res["short_history"]:
            w.writerow([r["item"], "SHORT_HISTORY", "", "", "", r["history_periods"], r["total_qty"],
                        round(r["value"], 2), round(r["run_rate_value"], 2)] + [""] * 9)


def build_parser():
    ap = argparse.ArgumentParser(description="ABC-XYZ segmentation. Input columns: " + ", ".join(REQUIRED) + ".")
    ap.add_argument("csv", help="long CSV with one row per item and period")
    ap.add_argument("--a", type=float, default=0.80, help="cumulative value share upper limit for A (default 0.80)")
    ap.add_argument("--b", type=float, default=0.95, help="cumulative value share upper limit for B (default 0.95)")
    ap.add_argument("--x", type=float, default=0.5, help="CoV upper limit for X (default 0.5)")
    ap.add_argument("--y", type=float, default=1.0, help="CoV upper limit for Y (default 1.0)")
    ap.add_argument("--min-periods", type=int, default=6,
                    help="minimum history periods to be segmented (default 6)")
    ap.add_argument("--intermittent-share", type=float, default=0.3,
                    help="share of zero periods that makes demand intermittent (default 0.3)")
    ap.add_argument("--lumpy-cv", type=float, default=0.7,
                    help="CoV of non-zero periods above which intermittent demand is lumpy (default 0.7)")
    ap.add_argument("--dead-periods", type=int, default=6,
                    help="trailing zero periods that make an item a delisting candidate (default 6)")
    ap.add_argument("--out", help="write detailed results as CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if not 0 < args.a < args.b <= 1:
            raise InputError("thresholds must satisfy 0 < a < b <= 1")
        if not 0 < args.x < args.y:
            raise InputError("thresholds must satisfy 0 < x < y")
        res = compute(read_table(args.csv, REQUIRED, OPTIONAL), args.a, args.b, args.x, args.y,
                      args.min_periods, args.intermittent_share, args.lumpy_cv, args.dead_periods)
    except InputError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 2
    if args.out:
        write_csv(res, args.out)
    print(json.dumps(clean_json(res), indent=2, default=str) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
