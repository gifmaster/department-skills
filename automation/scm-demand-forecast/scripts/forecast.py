#!/usr/bin/env python3
"""Baseline demand forecast per item with hold-out accuracy and method selection.

Purpose
    Fit moving average, simple exponential smoothing and (with enough history)
    Holt-Winters additive seasonal models per item, choose the method with the
    lowest WAPE on a hold-out window, and forecast the horizon. Stock-out periods and
    missing months are excluded from fitting and from the accuracy test.

Input columns (long CSV, comma or semicolon)
    item, period, quantity        optional: stockout (yes/no, ja/nej, 1/0, x)
    period: yyyy-mm (dates are bucketed to their month). Duplicate rows are summed.
    Missing months inside an item's history (no row, or a blank quantity) are treated as
    MISSING, not zero: they are reported as gaps and left out of fitting and scoring like
    stock-out months. With --fill-zero they are read as real zero-demand months instead.

Formulas
    MA(w)      forecast = mean of the last w non-stock-out periods (flat)
    SES        level = alpha x y + (1 - alpha) x level; alpha chosen from a grid by the lowest
               one-step squared error on the training data; forecast flat
    HW         additive level, trend and season (season length m, default 12), only for items
               with >= --hw-min-periods (default 24); initial trend = mean of (y[m+i] - y[i]) / m
               over same-month pairs, initial level and seasons from the de-trended first season;
               alpha, beta, gamma from a grid by the lowest one-step squared error; stock-out
               periods are replaced by the model's own forecast
    WAPE       = sum|A - F| / sum A ; MAPE = mean(|A - F| / A) for A > 0 ;
    Bias       = (sum F - sum A) / sum A  (positive = over-forecast)
    Plausible  = forecast total vs the same months last year; flagged above --review-ly (30 %)
    Evaluation = rolling origin over the last N periods (--holdout, default 3, max 12) when the
               first origin has at least --min-train periods (default 6): for each origin
               o = n-N .. n-1 the method is fitted on periods before o and forecasts periods
               o .. min(o + horizon, n) - 1; all (origin, step) errors are pooled into one WAPE,
               MAPE and bias. With less history: a single hold-out of the last N periods
               (fitted on the rest), if at least 3 periods remain for fitting; else no test.
    Selection  = lowest pooled WAPE; ties go to the simpler method;
               the chosen method is refitted on the full history; negative forecasts set to 0.

Example
    python3 scripts/forecast.py assets/demand_history.csv --horizon 6 --holdout 3
    python3 scripts/forecast.py assets/demand_history.csv --holdout 6 --fill-zero
"""
import argparse
import csv
import io
import json
import math
import re
import sys
from datetime import datetime

REQUIRED = ["item", "period", "quantity"]
OPTIONAL = ["stockout"]
YES = {"yes", "y", "ja", "j", "1", "true", "x", "sand"}
NO = {"", "no", "n", "nej", "0", "false", "falsk"}
METHOD_ORDER = ["MA", "SES", "HW"]

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


# ---------------------------------------------------------------- periods
def norm_period(p):
    t = p.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", t)
    if m:
        return "%s-%02d" % (m.group(1), int(m.group(2)))
    m = re.fullmatch(r"(\d{1,2})-(\d{4})", t)
    if m:
        return "%s-%02d" % (m.group(2), int(m.group(1)))
    return parse_date(t).strftime("%Y-%m")


def add_months(period, k):
    y, m = int(period[:4]), int(period[5:])
    idx = y * 12 + (m - 1) + k
    return "%04d-%02d" % (idx // 12, idx % 12 + 1)


def months_between(a, b):
    return (int(b[:4]) * 12 + int(b[5:])) - (int(a[:4]) * 12 + int(a[5:]))


# ---------------------------------------------------------------- models
def ma_forecast(y, excl, h, window=3):
    vals = [v for v, e in zip(y, excl) if not e]
    if not vals:
        return None, {}
    last = vals[-window:]
    f = sum(last) / len(last)
    return [f] * h, {"window": len(last)}


def ses_fit(y, excl, alpha):
    level, sse, started = None, 0.0, False
    for v, e in zip(y, excl):
        if e:
            continue
        if not started:
            level, started = v, True
            continue
        sse += (v - level) ** 2
        level = alpha * v + (1 - alpha) * level
    return level, sse


def ses_forecast(y, excl, h, alphas):
    best = None
    for a in alphas:
        level, sse = ses_fit(y, excl, a)
        if level is None:
            return None, {}
        if best is None or sse < best[1] - 1e-12:
            best = (a, sse, level)
    return [best[2]] * h, {"alpha": best[0]}


def hw_fit(y, excl, m, alpha, beta, gamma, h=0):
    n = len(y)
    first = [v for v, e in zip(y[:m], excl[:m]) if not e]
    if len(first) < max(3, m // 2):
        return None, None
    fill = sum(first) / len(first)
    yy = [fill if e and i < m else v for i, (v, e) in enumerate(zip(y, excl))]
    mean1 = sum(yy[:m]) / m
    if n >= 2 * m:
        diffs = [(y[m + i] - y[i]) / m for i in range(m) if not excl[i] and not excl[m + i]]
        trend = sum(diffs) / len(diffs) if diffs else 0.0
    else:
        trend = 0.0
    # level at the end of the first season; seasonal indices de-trended around the season mean
    level = mean1 + trend * (m - 1) / 2.0
    season = [yy[i] - (mean1 + trend * (i - (m - 1) / 2.0)) for i in range(m)]
    sse = 0.0
    for t in range(m, n):
        s_old = season[t - m]
        f = level + trend + s_old
        if excl[t]:
            v = f
        else:
            v = yy[t]
            sse += (v - f) ** 2
        new_level = alpha * (v - s_old) + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        season.append(gamma * (v - new_level) + (1 - gamma) * s_old)
        level = new_level
    fc = [level + k * trend + season[n - m + ((k - 1) % m)] for k in range(1, h + 1)]
    return fc, sse


def hw_forecast(y, excl, h, m, grid):
    best = None
    for a in grid["alpha"]:
        for b in grid["beta"]:
            for g in grid["gamma"]:
                fc, sse = hw_fit(y, excl, m, a, b, g, h)
                if fc is None:
                    return None, {}
                if best is None or sse < best[0] - 1e-9:
                    best = (sse, fc, {"alpha": a, "beta": b, "gamma": g})
    return best[1], best[2]


def run_method(name, y, excl, h, cfg):
    if name == "MA":
        fc, p = ma_forecast(y, excl, h, cfg["ma_window"])
    elif name == "SES":
        fc, p = ses_forecast(y, excl, h, cfg["alphas"])
    else:
        fc, p = hw_forecast(y, excl, h, cfg["season"], cfg["hw_grid"])
    if fc is None:
        return None, p
    return [max(0.0, f) for f in fc], p


def accuracy(actual, fc, excl):
    pairs = [(a, f) for a, f, e in zip(actual, fc, excl) if not e]
    sa = sum(a for a, _ in pairs)
    if not pairs or sa <= 0:
        return {"wape": None, "mape": None, "bias": None, "n": len(pairs)}
    wape = sum(abs(a - f) for a, f in pairs) / sa
    ap = [abs(a - f) / a for a, f in pairs if a > 0]
    return {"wape": wape, "mape": sum(ap) / len(ap) if ap else None,
            "bias": (sum(f for _, f in pairs) - sa) / sa, "n": len(pairs)}


def fmt_params(p):
    return ", ".join("%s=%s" % (k, ("%g" % v)) for k, v in p.items())


# ---------------------------------------------------------------- core logic
def load_series(records, warnings, fill_zero=False):
    data = {}
    for line, r in records:
        item = r["item"]
        if not item:
            warnings.append("Line %d: missing item, row skipped." % line)
            continue
        try:
            per = norm_period(r["period"])
            q = parse_number(r["quantity"])
        except ValueError as exc:
            warnings.append("Line %d (%s): %s, row skipped." % (line, item, exc))
            continue
        so_raw = (r.get("stockout") or "").strip().lower()
        if so_raw not in YES and so_raw not in NO:
            warnings.append("Line %d (%s %s): stockout value %r not recognised, read as no."
                            % (line, item, per, so_raw))
        so = so_raw in YES
        if q is None:
            if fill_zero:
                warnings.append("Line %d (%s %s): missing quantity, read as 0 (--fill-zero)." % (line, item, per))
                q = 0.0
            else:
                warnings.append("Line %d (%s %s): missing quantity, treated as a missing month." % (line, item, per))
                data.setdefault(item, {})
                continue
        if q < 0:
            warnings.append("Line %d (%s %s): negative quantity %s (returns or sign error), kept as booked."
                            % (line, item, per, fmt(q)))
        d = data.setdefault(item, {})
        if per in d:
            warnings.append("Line %d: duplicate row for %s %s, quantities summed." % (line, item, per))
            d[per] = (d[per][0] + q, d[per][1] or so)
        else:
            d[per] = (q, so)
    out = {}
    for item, d in data.items():
        if not d:
            warnings.append("%s: no rows with a quantity, item skipped." % item)
            continue
        start, end = min(d), max(d)
        periods = [add_months(start, k) for k in range(months_between(start, end) + 1)]
        gaps = [p for p in periods if p not in d]
        if gaps and fill_zero:
            warnings.append("%s: no data for %s, filled with 0 (--fill-zero). Check these were real zero months."
                            % (item, ", ".join(gaps)))
        elif gaps:
            warnings.append("%s: no data for %s, treated as missing (left out of fitting and scores). "
                            "Use --fill-zero if these were real zero months." % (item, ", ".join(gaps)))
        missing = [] if fill_zero else gaps
        out[item] = {"periods": periods, "y": [d.get(p, (0.0, False))[0] for p in periods],
                     "excl": [d.get(p, (0.0, False))[1] or p in missing for p in periods],
                     "stockout": [d.get(p, (0.0, False))[1] for p in periods],
                     "missing": missing, "filled_zero": gaps if fill_zero else []}
    return out


def evaluate(y, excl, methods, holdout, horizon, cfg, min_train=6):
    """Score each method. Returns (mode, tests); mode is 'rolling', 'single' or None.

    rolling: origins o = n-N .. n-1, fit on y[:o], forecast y[o:min(o+horizon, n)], errors pooled.
    single : fit on y[:n-N], forecast the last N periods.
    tests[m]['forecast'] holds one forecast per hold-out period (the one-step-ahead forecast
    when rolling) for display.
    """
    n = len(y)
    if holdout <= 0 or n - holdout < 3:
        return None, {}
    mode = "rolling" if holdout >= 2 and n - holdout >= min_train else "single"
    origins = list(range(n - holdout, n)) if mode == "rolling" else [n - holdout]
    tests = {}
    for mname in methods:
        act, fcs, exs, shown, params, ok = [], [], [], [], None, True
        for o in origins:
            steps = min(horizon, n - o) if mode == "rolling" else holdout
            f, p = run_method(mname, y[:o], excl[:o], steps, cfg)
            if f is None:
                ok = False
                break
            params = p
            act += y[o:o + steps]
            fcs += f
            exs += excl[o:o + steps]
            shown.append(f[0])
            if mode == "single":
                shown = f
        if not ok:
            continue
        acc = accuracy(act, fcs, exs)
        tests[mname] = {"params": params, "forecast": shown, "origins": len(origins), **acc}
    return mode, tests


def compute(records, horizon=6, holdout=3, ma_window=3, season=12, hw_min_periods=24,
            alphas=None, review_wape=0.3, review_bias=0.1, review_ly=0.3, fill_zero=False, min_train=6):
    warnings = []
    cfg = {"ma_window": ma_window, "season": season,
           "alphas": alphas or [round(0.1 * k, 1) for k in range(1, 10)],
           "hw_grid": {"alpha": [0.05, 0.1, 0.2, 0.3, 0.5, 0.7], "beta": [0.0, 0.05, 0.1, 0.2],
                       "gamma": [0.05, 0.1, 0.2, 0.3, 0.5]}}
    series = load_series(records, warnings, fill_zero)
    if not series:
        raise InputError("No usable rows.")
    items = []
    for item in sorted(series):
        s = series[item]
        y, excl, periods = s["y"], s["excl"], s["periods"]
        n = len(y)
        methods = ["MA", "SES"] + (["HW"] if n >= hw_min_periods else [])
        mode, tests = evaluate(y, excl, methods, holdout, horizon, cfg, min_train)
        can_test = mode is not None
        scored = [m for m in METHOD_ORDER if m in tests and tests[m]["wape"] is not None]
        if scored:
            chosen = min(scored, key=lambda m: (round(tests[m]["wape"], 9), METHOD_ORDER.index(m)))
            basis = ("lowest rolling-origin WAPE (%d origins)" % holdout if mode == "rolling"
                     else "lowest hold-out WAPE (single origin)")
        else:
            chosen = "SES" if sum(1 for e in excl if not e) >= 2 else "MA"
            basis = "no usable hold-out, default"
        fc, params = run_method(chosen, y, excl, horizon, cfg)
        if fc is None:
            warnings.append("%s: no usable (non stock-out) history, no forecast." % item)
            continue
        fperiods = [add_months(periods[-1], k) for k in range(1, horizon + 1)]
        known = {p: v for p, v in zip(periods, y) if p not in s["missing"]}
        same_ly = [known.get(add_months(p, -12)) for p in fperiods]
        ly_total = sum(v for v in same_ly) if all(v is not None for v in same_ly) else None
        best = tests.get(chosen, {})
        review = []
        if n < 12:
            review.append("under 12 periods of history")
        if n < hw_min_periods:
            review.append("no seasonal model (needs %d periods)" % hw_min_periods)
        if best.get("wape") is not None and best["wape"] > review_wape:
            review.append("hold-out WAPE %s" % pct(best["wape"]))
        if best.get("bias") is not None and abs(best["bias"]) > review_bias:
            review.append("hold-out bias %s" % pct(best["bias"]))
        if ly_total and abs(sum(fc) - ly_total) / ly_total > review_ly:
            review.append("forecast total %s vs same periods last year, check plausibility"
                          % pct((sum(fc) - ly_total) / ly_total))
        if can_test and any(s["stockout"][-holdout:]):
            review.append("stock-out inside hold-out window")
        if s["missing"]:
            review.append("%d missing month(s) in history" % len(s["missing"]))
        items.append({
            "item": item, "periods": n, "first_period": periods[0], "last_period": periods[-1],
            "stockout_periods": [p for p, e in zip(periods, s["stockout"]) if e],
            "missing_periods": s["missing"], "zero_filled_periods": s["filled_zero"],
            "method": chosen, "params": params, "basis": basis, "evaluation": mode,
            "tests": {k: {kk: vv for kk, vv in v.items()} for k, v in tests.items()},
            "holdout_periods": periods[-holdout:] if can_test else [],
            "holdout_actual": y[-holdout:] if can_test else [],
            "wape": best.get("wape"), "mape": best.get("mape"), "bias": best.get("bias"),
            "forecast_periods": fperiods, "forecast": fc, "forecast_total": sum(fc),
            "same_periods_last_year_total": ly_total,
            "history": [None if p in s["missing"] else v for p, v in zip(periods, y)], "history_periods": periods,
            "review": review,
        })
    return {"parameters": {"horizon": horizon, "holdout": holdout, "min_train": min_train, "fill_zero": fill_zero,
                           "ma_window": ma_window, "season": season,
                           "hw_min_periods": hw_min_periods, "review_wape": review_wape,
                           "review_bias": review_bias, "review_ly": review_ly},
            "items": items, "warnings": warnings}


def render(res):
    p = res["parameters"]
    out = ["# Demand forecast (statistical baseline)", ""]
    out.append("**%d items, horizon %d periods, hold-out %d periods.** Overlays for known events "
               "(campaigns, new customers) are NOT included; add them separately."
               % (len(res["items"]), p["horizon"], p["holdout"]))
    out += ["", "## 1. Method and assumptions", "",
            "- Candidates: moving average (last %d), simple exponential smoothing, Holt-Winters additive "
            "(season %d) only with %d+ periods" % (p["ma_window"], p["season"], p["hw_min_periods"]),
            "- Choice per item: lowest WAPE over the last %d periods, rolling origin (refit at each of the %d "
            "origins, forecasts up to the horizon pooled) when at least %d periods precede the first origin, "
            "otherwise one fixed hold-out; then refitted on the full history" % (p["holdout"], p["holdout"], p["min_train"]),
            "- Stock-out periods are excluded from fitting and from accuracy (not treated as true demand)",
            "- Months without data are %s" % ("filled with 0 (--fill-zero)" if p["fill_zero"] else
                                              "treated as missing and excluded like stock-outs, not as zero demand"),
            ""]
    rows = []
    for i in res["items"]:
        rows.append([i["item"], i["periods"], ", ".join(i["stockout_periods"]) or "-",
                     ", ".join(i["missing_periods"] or i["zero_filled_periods"]) or "-",
                     "%s (%s)" % (i["method"], fmt_params(i["params"])), i["basis"]])
    out.append(md_table(["Item", "Periods", "Stock-out periods excluded",
                         "Months filled with 0" if p["fill_zero"] else "Missing months excluded",
                         "Method chosen", "Basis"], rows))
    out += ["", "## 2. Forecast table", ""]
    for i in res["items"]:
        out.append("**%s** (%s)" % (i["item"], i["method"]))
        out.append("")
        heads = ["Period"] + i["forecast_periods"] + ["Total"]
        out.append(md_table(heads, [["Forecast"] + [fmt(f) for f in i["forecast"]] + [fmt(i["forecast_total"])]]))
        ly = i["same_periods_last_year_total"]
        out.append("")
        out.append("Same periods last year: %s%s" % (
            fmt(ly) if ly is not None else "not available",
            " (forecast is %s vs last year)" % pct((i["forecast_total"] - ly) / ly) if ly else ""))
        out.append("")
    out += ["## 3. Accuracy and bias (hold-out)", ""]
    rows = []
    for i in res["items"]:
        for m in METHOD_ORDER:
            t = i["tests"].get(m)
            if not t:
                continue
            rows.append([i["item"], m + (" (chosen)" if m == i["method"] else ""),
                         "rolling, %d origins" % t["origins"] if i["evaluation"] == "rolling" else "single origin",
                         " / ".join(fmt(f) for f in t["forecast"]),
                         " / ".join(fmt(a) for a in i["holdout_actual"]),
                         t["n"], pct(t["wape"]), pct(t["mape"]), pct(t["bias"])])
    if rows:
        out.append(md_table(["Item", "Method", "Evaluation", "Hold-out forecast", "Actual", "Errors scored",
                             "WAPE", "MAPE", "Bias"], rows))
    else:
        out.append("- No item had enough history for a hold-out test.")
    out += ["", "WAPE = sum|A - F| / sum A. Bias = (sum F - sum A) / sum A, positive means over-forecast. "
            "Rolling origin: the forecast shown per period is the one-step-ahead forecast; the scores pool every "
            "(origin, step) forecast. Stock-out and missing periods are left out of the scores.", "",
            "## 4. Items to review", ""]
    flagged = [i for i in res["items"] if i["review"]]
    out += ["- **%s**: %s" % (i["item"], "; ".join(i["review"])) for i in flagged] or ["- None flagged."]
    if res["warnings"]:
        out += ["", "## Data-quality warnings", ""] + ["- " + w for w in res["warnings"]]
    return "\n".join(out) + "\n"


def write_csv(res, path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "period", "type", "actual", "forecast", "stockout_excluded", "method"])
        for i in res["items"]:
            so = set(i["stockout_periods"])
            hold = dict(zip(i["holdout_periods"], i["tests"].get(i["method"], {}).get("forecast", [])))
            for per, a in zip(i["history_periods"], i["history"]):
                f = hold.get(per)
                w.writerow([i["item"], per, "holdout" if per in hold else "history", "" if a is None else a,
                            round(f, 2) if f is not None else "", "yes" if per in so else "no", i["method"]])
            for per, f in zip(i["forecast_periods"], i["forecast"]):
                w.writerow([i["item"], per, "forecast", "", round(f, 2), "", i["method"]])


def build_parser():
    ap = argparse.ArgumentParser(description="Baseline demand forecast with hold-out method selection. "
                                 "Input columns: item, period (yyyy-mm), quantity; optional: stockout (yes/no).")
    ap.add_argument("csv", help="long CSV with one row per item and month")
    ap.add_argument("--horizon", type=int, default=6, help="periods to forecast (default 6)")
    ap.add_argument("--holdout", type=int, default=3,
                    help="periods at the end used to score methods, 0 to 12 (default 3). Rolling origin over these "
                         "periods when history allows (see --min-train), otherwise one fixed hold-out")
    ap.add_argument("--min-train", type=int, default=6,
                    help="periods needed before the first origin for a rolling-origin evaluation (default 6)")
    ap.add_argument("--fill-zero", action="store_true",
                    help="read months without data (no row or blank quantity) as zero demand; by default they "
                         "are missing and left out of fitting and scores")
    ap.add_argument("--ma-window", type=int, default=3, help="moving average window (default 3)")
    ap.add_argument("--season", type=int, default=12, help="season length for Holt-Winters (default 12)")
    ap.add_argument("--hw-min-periods", type=int, default=24,
                    help="minimum periods before Holt-Winters is tried (default 24)")
    ap.add_argument("--alpha", type=float, default=None,
                    help="fix the SES alpha instead of searching 0.1 to 0.9")
    ap.add_argument("--review-wape", type=float, default=0.3, help="flag items above this WAPE (default 0.3)")
    ap.add_argument("--review-bias", type=float, default=0.1, help="flag items with |bias| above this (default 0.1)")
    ap.add_argument("--review-ly", type=float, default=0.3,
                    help="flag items whose forecast total differs from the same periods last year by more "
                         "than this share (default 0.3)")
    ap.add_argument("--out", help="write history, hold-out and forecast rows as CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.horizon < 1 or args.ma_window < 1 or args.season < 2 or args.min_train < 3:
            raise InputError("horizon and ma-window must be >= 1, season >= 2, min-train >= 3")
        if not 0 <= args.holdout <= 12:
            raise InputError("--holdout must be between 0 and 12")
        if args.alpha is not None and not 0 < args.alpha <= 1:
            raise InputError("--alpha must be between 0 and 1")
        res = compute(read_table(args.csv, REQUIRED, OPTIONAL), args.horizon, args.holdout, args.ma_window,
                      args.season, args.hw_min_periods, [args.alpha] if args.alpha else None,
                      args.review_wape, args.review_bias, args.review_ly, args.fill_zero, args.min_train)
    except InputError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 2
    if args.out:
        write_csv(res, args.out)
    print(json.dumps(clean_json(res), indent=2, default=str) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
