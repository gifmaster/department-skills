#!/usr/bin/env python3
"""Inventory policy calculator: safety stock, reorder point and order quantity per item.

Purpose
    Turn per-item demand, lead time and cost data into ERP-ready inventory
    parameters, and show the inventory value impact against current stock.

Input columns (CSV, comma or semicolon, header row required)
    item, avg_daily_demand, sd_daily_demand, lead_time_days, sd_lead_time_days,
    unit_cost, order_cost, holding_rate, moq, pack_size
    optional: service_level, current_stock
    Demand and lead time MUST use the same day basis (calendar days by default).
    holding_rate is annual (0.22 or 22 both read as 22 %). service_level is the
    cycle service level (0.95 or 95). Blank order_cost / holding_rate /
    service_level fall back to the CLI defaults.

Formulas
    z            = inverse standard normal of the cycle service level
    sigma_LT     = sqrt(L x sd_d^2 + d^2 x sd_L^2)   (demand and lead-time variability)
    safety stock = ceil(z x sigma_LT)
    reorder pt   = ceil(d x L + safety stock)
    EOQ          = sqrt(2 x D x S / H), D = d x days_per_year, H = unit_cost x holding_rate
    order qty    = max(EOQ, MOQ) rounded UP to a whole number of packs
    avg stock    = safety stock + order qty / 2; value = avg stock x unit_cost
    fill rate    = 1 - sigma_LT x G(z) / order qty, G(z) = pdf(z) - z x (1 - cdf(z))

Example
    python3 scripts/inventory_params.py assets/inventory_items.csv --service-level 0.95
"""
import argparse
import csv
import io
import json
import math
import re
import sys
from datetime import datetime

REQUIRED = ["item", "avg_daily_demand", "sd_daily_demand", "lead_time_days",
            "sd_lead_time_days", "unit_cost", "order_cost", "holding_rate", "moq", "pack_size"]
OPTIONAL = ["service_level", "current_stock"]


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


# ---------------------------------------------------------------- statistics
def norm_cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_ppf(p):
    """Inverse standard normal (Acklam's rational approximation + one Halley step)."""
    if not 0.0 < p < 1.0:
        raise ValueError("probability must be between 0 and 1 (exclusive)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow = 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= 1 - plow:
        q = p - 0.5
        r = q * q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    e = norm_cdf(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def loss_function(z):
    return norm_pdf(z) - z * (1 - norm_cdf(z))


def ceil_int(x):
    return int(math.ceil(x - 1e-9))


# ---------------------------------------------------------------- core logic
def as_rate(value, name, warnings, item):
    """Accept 0.22 or 22 (percent)."""
    if value is not None and value > 1:
        warnings.append("%s: %s %s read as a percentage (%s)." % (item, name, fmt(value, 2), pct(value / 100)))
        return value / 100.0
    return value


def compute(records, service_level=0.95, order_cost=None, holding_rate=None,
            days_per_year=365, max_cover_days=365, lumpy_cov=2.0, moq_eoq_ratio=3.0):
    items, warnings, seen = [], [], set()
    for line, r in records:
        name = r.get("item", "")
        if not name:
            warnings.append("Line %d: missing item name, row skipped." % line)
            continue
        if name in seen:
            warnings.append("Line %d: duplicate item '%s', only the first row is used." % (line, name))
            continue
        try:
            vals = {k: parse_number(r.get(k, "")) for k in REQUIRED[1:] + OPTIONAL}
        except ValueError as exc:
            warnings.append("Line %d (%s): %s, row skipped." % (line, name, exc))
            continue
        flags = []
        if vals["order_cost"] is None and order_cost is not None:
            vals["order_cost"] = order_cost
            flags.append("order cost defaulted to %s" % fmt(order_cost, 2))
        if vals["holding_rate"] is None and holding_rate is not None:
            vals["holding_rate"] = holding_rate
            flags.append("holding rate defaulted to %s" % pct(holding_rate))
        if vals["service_level"] is None:
            vals["service_level"] = service_level
        if vals["moq"] is None:
            vals["moq"] = 0.0
        if vals["pack_size"] is None or vals["pack_size"] <= 0:
            flags.append("pack size missing or zero, 1 used")
            vals["pack_size"] = 1.0
        missing = [k for k in ("avg_daily_demand", "sd_daily_demand", "lead_time_days",
                               "sd_lead_time_days", "unit_cost", "order_cost", "holding_rate")
                   if vals[k] is None]
        if missing:
            warnings.append("Line %d (%s): missing %s, row skipped." % (line, name, ", ".join(missing)))
            continue
        negative = [k for k, v in vals.items() if v is not None and v < 0]
        if negative:
            warnings.append("Line %d (%s): negative value in %s (sign error?), row skipped."
                            % (line, name, ", ".join(negative)))
            continue
        seen.add(name)
        vals["holding_rate"] = as_rate(vals["holding_rate"], "holding_rate", warnings, name)
        vals["service_level"] = as_rate(vals["service_level"], "service_level", warnings, name)
        sl = vals["service_level"]
        if not 0 < sl < 1:
            warnings.append("%s: service level %s is not between 0 and 1, row skipped." % (name, sl))
            seen.discard(name)
            continue
        d, sd_d = vals["avg_daily_demand"], vals["sd_daily_demand"]
        lt, sd_lt = vals["lead_time_days"], vals["sd_lead_time_days"]
        cost, s_cost, h_rate = vals["unit_cost"], vals["order_cost"], vals["holding_rate"]
        moq, pack, cur = vals["moq"], vals["pack_size"], vals["current_stock"]

        z = norm_ppf(sl)
        sigma_lt = math.sqrt(lt * sd_d ** 2 + d ** 2 * sd_lt ** 2)
        ss_raw = z * sigma_lt
        ss = max(0, ceil_int(ss_raw))
        rop = ceil_int(d * lt + ss)
        annual = d * days_per_year
        hold = cost * h_rate
        eoq = math.sqrt(2 * annual * s_cost / hold) if hold > 0 and annual > 0 else None
        base_q = max(eoq or 0.0, moq)
        q = ceil_int(base_q / pack) * pack if base_q > 0 else pack
        if eoq is None:
            flags.append("EOQ not computable (zero demand, cost or holding rate), MOQ/pack used")
        avg_stock = ss + q / 2.0
        fill = 1 - sigma_lt * loss_function(z) / q if q > 0 else None
        share_lt_var = (d ** 2 * sd_lt ** 2) / sigma_lt ** 2 if sigma_lt > 0 else 0.0

        # unit-consistency and review flags
        cov = sd_d / d if d > 0 else float("inf")
        if sd_lt > lt:
            flags.append("UNITS? lead-time SD exceeds lead time, check both are in days")
        if 0 < lt < 1:
            flags.append("UNITS? lead time under 1 day, check it is in days not weeks/months")
        if d > 0 and cur is not None and cur / d > max_cover_days:
            flags.append("UNITS? current stock covers %s days, check demand is per day not per week/month"
                         % fmt(cur / d))
        if cov > lumpy_cov:
            flags.append("lumpy or slow-moving (daily CoV %s): normal formula unreliable, or SD is not per day"
                         % fmt(cov, 2))
        if moq and pack and abs(moq / pack - round(moq / pack)) > 1e-9:
            flags.append("MOQ is not a multiple of pack size")
        if eoq and moq > moq_eoq_ratio * eoq:
            flags.append("MOQ is more than %sx EOQ, MOQ drives stock" % fmt(moq_eoq_ratio, 0))
        cur_val = cur * cost if cur is not None else None
        new_val = avg_stock * cost
        items.append({
            "item": name, "avg_daily_demand": d, "sd_daily_demand": sd_d,
            "lead_time_days": lt, "sd_lead_time_days": sd_lt, "service_level": sl, "z": z,
            "sigma_lead_time_demand": sigma_lt, "lead_time_variance_share": share_lt_var,
            "safety_stock_raw": ss_raw, "safety_stock": ss, "reorder_point": rop,
            "annual_demand": annual, "eoq": eoq, "order_qty": q, "order_cycle_days": q / d if d > 0 else None,
            "expected_fill_rate": fill, "avg_stock_proposed": avg_stock, "unit_cost": cost,
            "value_proposed": new_val, "current_stock": cur, "value_current": cur_val,
            "value_change": (new_val - cur_val) if cur_val is not None else None,
            "flags": flags,
        })
    tot_new = sum(i["value_proposed"] for i in items)
    with_cur = [i for i in items if i["value_current"] is not None]
    tot_cur = sum(i["value_current"] for i in with_cur)
    tot_new_cmp = sum(i["value_proposed"] for i in with_cur)
    return {
        "parameters": {"service_level_default": service_level, "order_cost_default": order_cost,
                       "holding_rate_default": holding_rate, "days_per_year": days_per_year,
                       "max_cover_days": max_cover_days, "lumpy_cov": lumpy_cov},
        "items": items, "warnings": warnings,
        "totals": {"items": len(items), "value_proposed": tot_new,
                   "value_current_comparable": tot_cur, "value_proposed_comparable": tot_new_cmp,
                   "value_change": tot_new_cmp - tot_cur if with_cur else None},
    }


def render(res):
    t, p = res["totals"], res["parameters"]
    out = ["# Inventory policy parameters", ""]
    out.append("**%d items.** Proposed average inventory value %s; current value (items with stock data) %s; "
               "change %s." % (t["items"], fmt(t["value_proposed"]), fmt(t["value_current_comparable"]),
                               fmt(t["value_change"]) if t["value_change"] is not None else "n/a"))
    out += ["", "## 1. Parameters per item", ""]
    rows = []
    for i in res["items"]:
        rows.append([i["item"], pct(i["service_level"]), fmt(i["z"], 3), fmt(i["sigma_lead_time_demand"], 1),
                     fmt(i["safety_stock_raw"], 1), fmt(i["safety_stock"]), fmt(i["reorder_point"]),
                     fmt(i["eoq"], 0) if i["eoq"] else "-", fmt(i["order_qty"]),
                     fmt(i["order_cycle_days"], 0), pct(i["expected_fill_rate"])])
    out.append(md_table(["Item", "CSL", "z", "sigma LT", "SS calc", "Safety stock", "Reorder point",
                         "EOQ", "Order qty", "Cycle days", "Exp. fill rate"], rows))
    out += ["", "## 2. Formulas used", "",
            "- sigma LT = sqrt(L x sd_d^2 + d^2 x sd_L^2), demand and lead-time variability combined",
            "- Safety stock = ceil(z x sigma LT); z from cycle service level (CSL)",
            "- Reorder point = ceil(d x L + safety stock)",
            "- EOQ = sqrt(2 x d x %s x order cost / (unit cost x holding rate)); order qty = max(EOQ, MOQ) "
            "rounded up to whole packs" % fmt(p["days_per_year"]),
            "- CSL is the chance of no stock-out per cycle, not the fill rate; expected fill rate = "
            "1 - sigma LT x G(z) / order qty", "",
            "## 3. Inventory value impact", ""]
    rows = []
    for i in res["items"]:
        rows.append([i["item"], fmt(i["current_stock"]), fmt(i["value_current"]),
                     fmt(i["avg_stock_proposed"], 0), fmt(i["value_proposed"]),
                     fmt(i["value_change"]) if i["value_change"] is not None else "-"])
    rows.append(["**Total (items with current stock)**", "", fmt(t["value_current_comparable"]), "",
                 fmt(t["value_proposed_comparable"]),
                 fmt(t["value_change"]) if t["value_change"] is not None else "-"])
    out.append(md_table(["Item", "Current stock", "Current value", "Proposed avg stock (SS + Q/2)",
                         "Proposed value", "Change"], rows))
    out += ["", "## 4. Items needing manual review", ""]
    flagged = [i for i in res["items"] if i["flags"]]
    if flagged:
        for i in flagged:
            out.append("- **%s**: %s" % (i["item"], "; ".join(i["flags"])))
    else:
        out.append("- None flagged.")
    if res["warnings"]:
        out += ["", "## Data-quality warnings", ""] + ["- " + w for w in res["warnings"]]
    return "\n".join(out) + "\n"


def write_csv(res, path):
    cols = ["item", "service_level", "z", "avg_daily_demand", "sd_daily_demand", "lead_time_days",
            "sd_lead_time_days", "sigma_lead_time_demand", "safety_stock_raw", "safety_stock",
            "reorder_point", "eoq", "order_qty", "order_cycle_days", "expected_fill_rate",
            "avg_stock_proposed", "unit_cost", "value_proposed", "current_stock", "value_current",
            "value_change", "flags"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in res["items"]:
            w.writerow([("; ".join(i[c]) if c == "flags" else
                         (round(i[c], 4) if isinstance(i[c], float) else i[c])) for c in cols])


def build_parser():
    ap = argparse.ArgumentParser(description="Safety stock, reorder point and EOQ per item. "
                                 "Input columns: " + ", ".join(REQUIRED) + " (optional: " + ", ".join(OPTIONAL) + ").")
    ap.add_argument("csv", help="item CSV file")
    ap.add_argument("--service-level", type=float, default=0.95,
                    help="cycle service level used when the column is blank (default 0.95)")
    ap.add_argument("--order-cost", type=float, default=None,
                    help="order cost per order used when the column is blank (default: none, row skipped)")
    ap.add_argument("--holding-rate", type=float, default=None,
                    help="annual holding rate used when the column is blank, e.g. 0.22 (default: none, row skipped)")
    ap.add_argument("--days-per-year", type=float, default=365,
                    help="days per year to annualise daily demand; use 250 if demand is per working day (default 365)")
    ap.add_argument("--max-cover-days", type=float, default=365,
                    help="flag items whose current stock covers more days than this (default 365)")
    ap.add_argument("--lumpy-cov", type=float, default=2.0,
                    help="flag items whose daily demand CoV exceeds this (default 2.0)")
    ap.add_argument("--out", help="write detailed results as CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if not 0 < args.service_level < 1:
            raise InputError("--service-level must be between 0 and 1, e.g. 0.95")
        recs = read_table(args.csv, REQUIRED, OPTIONAL)
        res = compute(recs, args.service_level, args.order_cost, args.holding_rate,
                      args.days_per_year, args.max_cover_days, args.lumpy_cov)
    except InputError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 2
    if args.out:
        write_csv(res, args.out)
    print(json.dumps(res, indent=2, default=str) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
