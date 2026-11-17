#!/usr/bin/env python3
"""OTIF and fill-rate analysis from order-line delivery data.

Purpose
    Measure on time, in full and OTIF at line and order level against the promised
    date, fill rate, results by customer and item, and a Pareto of miss reasons.

Input columns (CSV, comma or semicolon; one row per delivery)
    order_id, line, customer, item, promised_date, delivered_date, ordered_qty, delivered_qty
    optional: reason
    Several rows with the same order_id + line are partial deliveries of one line.
    A blank delivered_date means not delivered (yet).

Formulas
    due date        = promised_date + tolerance days (default 0)
    in-full qty     = ordered_qty x (1 - qty tolerance %), default 0 %
    completion date = date the cumulative delivered qty first reaches the in-full qty
    On time (line)  = completion date <= due date (if never complete: last delivery <= due date);
                      optional: deliveries more than --early-days before promised are not on time
    In full (line)  = total delivered >= in-full qty
    OTIF (line)     = on time AND in full; OTIF (order) = every evaluated line OTIF
    Fill rate       = sum min(delivered, ordered) / sum ordered
    On-time fill    = qty delivered by the due date (capped at ordered) / sum ordered
    Lines not delivered and due after --as-of (default: latest date in the file) are open and
    excluded; lines due on or before it count as misses.

Example
    python3 scripts/otif.py assets/order_lines.csv --tolerance-days 0 --qty-tolerance-pct 0
"""
import argparse
import csv
import io
import json
import math
import re
import sys
from datetime import datetime, timedelta

REQUIRED = ["order_id", "line", "customer", "item", "promised_date", "delivered_date",
            "ordered_qty", "delivered_qty"]
OPTIONAL = ["reason"]
NO_REASON = "(no reason given)"

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
def load_lines(records, warnings):
    lines, seen_rows = {}, set()
    for ln, r in records:
        key = (r["order_id"], r["line"])
        if not r["order_id"]:
            warnings.append("Row %d: missing order_id, row skipped." % ln)
            continue
        raw = tuple(r.get(c, "") for c in REQUIRED + OPTIONAL)
        if raw in seen_rows:
            warnings.append("Row %d: identical to an earlier row (order %s line %s), possible duplicate; "
                            "counted as a second delivery." % (ln, key[0], key[1]))
        seen_rows.add(raw)
        try:
            promised = parse_date(r["promised_date"]) if r["promised_date"] else None
            delivered = parse_date(r["delivered_date"]) if r["delivered_date"] else None
            oq = parse_number(r["ordered_qty"])
            dq = parse_number(r["delivered_qty"]) or 0.0
        except ValueError as exc:
            warnings.append("Row %d (order %s line %s): %s, row skipped." % (ln, key[0], key[1], exc))
            continue
        if promised is None:
            warnings.append("Row %d (order %s line %s): missing promised_date, row skipped."
                            % (ln, key[0], key[1]))
            continue
        if oq is None or oq <= 0:
            warnings.append("Row %d (order %s line %s): ordered_qty missing or not positive, row skipped."
                            % (ln, key[0], key[1]))
            continue
        if dq < 0:
            warnings.append("Row %d (order %s line %s): negative delivered_qty (sign error?), read as 0."
                            % (ln, key[0], key[1]))
            dq = 0.0
        if dq > 0 and delivered is None:
            warnings.append("Row %d (order %s line %s): quantity %s without delivered_date, not counted as delivered."
                            % (ln, key[0], key[1], fmt(dq)))
            dq = 0.0
        L = lines.setdefault(key, {"order_id": key[0], "line": key[1], "customer": r["customer"],
                                   "item": r["item"], "promised": promised, "ordered": oq,
                                   "deliveries": [], "reasons": []})
        if L["ordered"] != oq or L["promised"] != promised:
            warnings.append("Row %d (order %s line %s): ordered_qty or promised_date differs from the line's "
                            "first row; the first row's value is used." % (ln, key[0], key[1]))
        if delivered is not None and dq > 0:
            L["deliveries"].append((delivered, dq))
        reason = (r.get("reason") or "").strip().lower()
        if reason and reason not in L["reasons"]:
            L["reasons"].append(reason)
    return list(lines.values())


def rate(hits, n):
    return hits / n if n else None


def summarise(lines):
    n = len(lines)
    ordered = sum(l["ordered"] for l in lines)
    return {"lines": n,
            "on_time": rate(sum(l["on_time"] for l in lines), n),
            "in_full": rate(sum(l["in_full"] for l in lines), n),
            "otif": rate(sum(l["otif"] for l in lines), n),
            "otif_hits": sum(l["otif"] for l in lines),
            "fill_rate": sum(l["delivered_capped"] for l in lines) / ordered if ordered else None}


def compute(records, tolerance_days=0, qty_tolerance_pct=0.0, early_days=None, as_of=None):
    warnings = []
    lines = load_lines(records, warnings)
    if not lines:
        raise InputError("No usable rows.")
    all_dates = [l["promised"] for l in lines] + [d for l in lines for d, _ in l["deliveries"]]
    as_of = as_of or max(all_dates)
    evaluated, open_lines = [], []
    for l in lines:
        l["deliveries"].sort()
        due = l["promised"] + timedelta(days=tolerance_days)
        need = l["ordered"] * (1 - qty_tolerance_pct / 100.0)
        total = sum(q for _, q in l["deliveries"])
        completion, cum = None, 0.0
        for d, q in l["deliveries"]:
            cum += q
            if cum >= need - 1e-9:
                completion = d
                break
        if not l["deliveries"] and l["promised"] > as_of:
            open_lines.append(l)
            continue
        if not l["deliveries"]:
            on_time, ref = False, None
        else:
            ref = completion or l["deliveries"][-1][0]
            on_time = ref <= due
            if early_days is not None and l["deliveries"][0][0] < l["promised"] - timedelta(days=early_days):
                on_time = False
        in_full = total >= need - 1e-9
        if total > l["ordered"] + 1e-9:
            warnings.append("Order %s line %s: over-delivered %s of %s; capped at ordered for fill rate."
                            % (l["order_id"], l["line"], fmt(total), fmt(l["ordered"])))
        on_time_qty = sum(q for d, q in l["deliveries"] if d <= due)
        l.update({
            "due": due, "delivered_total": total, "delivered_capped": min(total, l["ordered"]),
            "on_time_qty": min(on_time_qty, l["ordered"]), "completion_date": completion,
            "days_late": (ref - l["promised"]).days if ref else None,
            "deliveries_count": len(l["deliveries"]),
            "partial": len(l["deliveries"]) > 1 or total < l["ordered"] - 1e-9,
            "on_time": on_time, "in_full": in_full, "otif": on_time and in_full,
        })
        if not l["deliveries"]:
            l["miss_type"] = "not delivered"
        elif not l["otif"]:
            l["miss_type"] = " + ".join(t for t, b in (("late", not on_time), ("short", not in_full)) if b)
        else:
            l["miss_type"] = ""
        l["reason_key"] = ", ".join(l["reasons"]) if l["reasons"] else NO_REASON
        evaluated.append(l)
    total = summarise(evaluated)
    ordered = sum(l["ordered"] for l in evaluated)
    total["on_time_fill_rate"] = sum(l["on_time_qty"] for l in evaluated) / ordered if ordered else None
    orders = {}
    for l in evaluated:
        orders.setdefault(l["order_id"], []).append(l)
    order_stats = {"orders": len(orders),
                   "on_time": rate(sum(all(x["on_time"] for x in v) for v in orders.values()), len(orders)),
                   "in_full": rate(sum(all(x["in_full"] for x in v) for v in orders.values()), len(orders)),
                   "otif": rate(sum(all(x["otif"] for x in v) for v in orders.values()), len(orders)),
                   "otif_hits": sum(all(x["otif"] for x in v) for v in orders.values())}

    def group(key):
        out = {}
        for l in evaluated:
            out.setdefault(l[key], []).append(l)
        return [dict(summarise(v), name=k) for k, v in sorted(out.items(), key=lambda kv: (
            summarise(kv[1])["otif"], kv[0]))]

    misses = [l for l in evaluated if not l["otif"]]
    pareto, cum = [], 0
    counts = {}
    for l in misses:
        counts[l["reason_key"]] = counts.get(l["reason_key"], 0) + 1
    for reason, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        cum += c
        pareto.append({"reason": reason, "lines": c, "share": c / len(misses), "cum_share": cum / len(misses),
                       "orders": ", ".join(sorted({l["order_id"] for l in misses if l["reason_key"] == reason}))})
    no_reason = counts.get(NO_REASON, 0)
    if no_reason:
        warnings.append("%d missed line(s) have no reason code; Pareto is incomplete." % no_reason)
    hit_reason = [l for l in evaluated if l["otif"] and l["reasons"]]
    if hit_reason:
        warnings.append("%d OTIF hit line(s) carry a reason code (%s); check the coding."
                        % (len(hit_reason), ", ".join("%s/%s" % (l["order_id"], l["line"]) for l in hit_reason)))
    late = [l["days_late"] for l in evaluated if not l["on_time"] and l["days_late"] is not None and l["days_late"] > 0]
    return {"parameters": {"tolerance_days": tolerance_days, "qty_tolerance_pct": qty_tolerance_pct,
                           "early_days": early_days, "as_of": as_of.isoformat()},
            "line_level": total, "order_level": order_stats,
            "partial_lines": sum(1 for l in evaluated if l["partial"]),
            "split_deliveries": sum(1 for l in evaluated if l["deliveries_count"] > 1),
            "open_lines": len(open_lines), "avg_days_late": sum(late) / len(late) if late else None,
            "by_customer": group("customer"), "by_item": group("item"), "pareto": pareto,
            "lines": evaluated, "warnings": warnings}


def render(res):
    p, t, o = res["parameters"], res["line_level"], res["order_level"]
    out = ["# OTIF and fill-rate analysis", ""]
    out.append("**Line OTIF %s (%d of %d lines), order OTIF %s (%d of %d orders), fill rate %s.** "
               "Measured against the promised date, as of %s."
               % (pct(t["otif"]), t["otif_hits"], t["lines"], pct(o["otif"]), o["otif_hits"], o["orders"],
                  pct(t["fill_rate"]), p["as_of"]))
    out += ["", "## 1. KPI definitions", "",
            "- On time: line completed (cumulative qty reached the in-full level) on or before promised date + %d day(s)"
            % p["tolerance_days"] + ("; more than %d day(s) early counts as not on time" % p["early_days"]
                                     if p["early_days"] is not None else "; early counts as on time"),
            "- In full: total delivered >= ordered x (1 - %s %%)" % fmt(p["qty_tolerance_pct"], 1),
            "- OTIF line = on time and in full; OTIF order = all lines OTIF; partial deliveries are combined per line",
            "- Fill rate = delivered (capped at ordered) / ordered", "",
            "## 2. KPI results", ""]
    out.append(md_table(["KPI", "Line level", "Order level"], [
        ["On time", pct(t["on_time"]), pct(o["on_time"])],
        ["In full", pct(t["in_full"]), pct(o["in_full"])],
        ["**OTIF**", "**%s**" % pct(t["otif"]), "**%s**" % pct(o["otif"])],
        ["Fill rate (units)", pct(t["fill_rate"]), ""],
        ["On-time fill rate (units)", pct(t["on_time_fill_rate"]), ""]]))
    out.append("")
    out.append("Lines evaluated %d, open (not yet due) %d, partial %d, split deliveries %d, average days late %s."
               % (t["lines"], res["open_lines"], res["partial_lines"], res["split_deliveries"],
                  fmt(res["avg_days_late"], 1)))
    for title, key in (("By customer", "by_customer"), ("By item", "by_item")):
        out += ["", "### %s (worst first)" % title, ""]
        out.append(md_table(["Name", "Lines", "On time", "In full", "OTIF", "Fill rate"],
                            [[g["name"], g["lines"], pct(g["on_time"]), pct(g["in_full"]), pct(g["otif"]),
                              pct(g["fill_rate"])] for g in res[key]]))
    out += ["", "## 3. Root cause Pareto (missed lines)", ""]
    if res["pareto"]:
        out.append(md_table(["Reason", "Lines", "Share", "Cumulative", "Orders"],
                            [[r["reason"], r["lines"], pct(r["share"]), pct(r["cum_share"]), r["orders"]]
                             for r in res["pareto"]]))
        out += ["", "Missed lines:", ""]
        out.append(md_table(["Order", "Line", "Customer", "Item", "Promised", "Miss", "Days late", "Delivered/ordered", "Reason"],
                            [[l["order_id"], l["line"], l["customer"], l["item"], l["promised"].isoformat(),
                              l["miss_type"], l["days_late"] if l["days_late"] is not None else "-",
                              "%s/%s" % (fmt(l["delivered_total"]), fmt(l["ordered"])), l["reason_key"]]
                             for l in res["lines"] if not l["otif"]]))
    else:
        out.append("- No misses.")
    out += ["", "## 4. Action plan inputs", "",
            "- Start with the top Pareto reason%s; small samples make the Pareto indicative only."
            % (" (%s)" % res["pareto"][0]["reason"] if res["pareto"] else ""),
            "- Worst customer: %s; worst item: %s." % (
                res["by_customer"][0]["name"] if res["by_customer"] else "-",
                res["by_item"][0]["name"] if res["by_item"] else "-")]
    if res["warnings"]:
        out += ["", "## Data-quality warnings", ""] + ["- " + w for w in res["warnings"]]
    return "\n".join(out) + "\n"


def write_csv(res, path):
    cols = ["order_id", "line", "customer", "item", "promised", "due", "ordered", "delivered_total",
            "deliveries_count", "completion_date", "days_late", "on_time", "in_full", "otif", "partial",
            "miss_type", "reason_key"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for l in res["lines"]:
            w.writerow([l[c].isoformat() if hasattr(l[c], "isoformat") else l[c] for c in cols])


def build_parser():
    ap = argparse.ArgumentParser(description="OTIF, fill rate and miss-reason Pareto. Input columns: "
                                 + ", ".join(REQUIRED) + " (optional: reason).")
    ap.add_argument("csv", help="order-line CSV, one row per delivery")
    ap.add_argument("--tolerance-days", type=int, default=0,
                    help="days after the promised date still counted as on time (default 0)")
    ap.add_argument("--qty-tolerance-pct", type=float, default=0.0,
                    help="percent short still counted as in full, e.g. 2 (default 0)")
    ap.add_argument("--early-days", type=int, default=None,
                    help="if set, deliveries more than this many days early are not on time (default: early is fine)")
    ap.add_argument("--as-of", default=None,
                    help="cut-off date; undelivered lines due after it are open (default: latest date in file)")
    ap.add_argument("--out", help="write line-level results as CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.tolerance_days < 0 or not 0 <= args.qty_tolerance_pct < 100:
            raise InputError("--tolerance-days must be >= 0 and --qty-tolerance-pct between 0 and 100")
        as_of = None
        if args.as_of:
            try:
                as_of = parse_date(args.as_of)
            except ValueError as exc:
                raise InputError(str(exc))
        res = compute(read_table(args.csv, REQUIRED, OPTIONAL), args.tolerance_days, args.qty_tolerance_pct,
                      args.early_days, as_of)
    except InputError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 2
    if args.out:
        write_csv(res, args.out)
    print(json.dumps(clean_json(res), indent=2, default=str) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
