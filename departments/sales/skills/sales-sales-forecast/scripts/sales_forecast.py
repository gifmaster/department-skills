#!/usr/bin/env python3
"""Sales forecast calculator: commit, most likely and best case for a period.

Purpose
  Turns an open pipeline export (plus optional win/loss history) into a forecast
  range with three methods side by side, so the forecast is calculated, not guessed.

Input columns
  Pipeline CSV (required): deal, stage, amount, close_date
    optional: probability (0.35, 35 or 35%), rep_commit (yes/no), owner
    Stages containing "won" count as closed won; stages containing "lost" are excluded.
  History CSV (optional, --history): deal, stage_reached, won (yes/no), amount, cycle_days
    One row per closed deal with the furthest stage it reached (several rows per
    deal are also accepted; the furthest stage is used).

Formulas
  Only deals with close_date inside [period start, period end] are used.
  CRM probability p = probability column, else the stage default (--stage-defaults).
  Historical conversion h(stage) = won deals that reached the stage or later
    / all closed deals that reached the stage or later (stage order = order of
    --stage-defaults by probability). If fewer than --min-sample deals reached
    the stage, h falls back to the stage default.
  W (weighted pipeline)   = sum(amount x p)
  H (historical)          = sum(amount x h)
  C (rep commit)          = sum(amount where rep_commit = yes)
  Commit (low)            = closed won + sum(amount x h) over rep commit deals
                            (if no rep_commit data: closed won + min(W, H))
  Most likely             = closed won + H
  Best case (high)        = closed won + max(W, H, C)
  Gaps: W - H (CRM optimism), C - risk-adjusted commit (rep optimism), target - scenario.

Example
  python3 scripts/sales_forecast.py assets/pipeline_template.csv \
      --history assets/history_template.csv --period-start 2026-10-01 \
      --period-end 2026-12-31 --today 2026-11-16 --closed-won 3100000 --target 6000000
"""
import argparse
import csv
import io
import json
import re
import statistics
import sys
from datetime import date, datetime, timedelta

DEFAULT_STAGES = "Discovery=0.10,Qualification=0.20,Proposal=0.35,Negotiation=0.60,Verbal=0.90"

# ---------------------------------------------------------------- helpers

def norm_col(name):
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def read_csv(path, required, optional=()):
    """Read a CSV (comma or semicolon) into a list of dicts with normalised headers."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first:
        raise ValueError(f"{path} is empty")
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    header = None
    rows = []
    for rec in reader:
        if not any(c.strip() for c in rec):
            continue
        if header is None:
            header = [norm_col(h) for h in rec]
            missing = [c for c in required if c not in header]
            if missing:
                raise ValueError(
                    f"{path}: missing column(s) {', '.join(missing)}. Expected columns: "
                    f"{', '.join(required)}" + (f" (optional: {', '.join(optional)})" if optional else ""))
            continue
        rec = rec + [""] * (len(header) - len(rec))
        row = {h: rec[i].strip() for i, h in enumerate(header)}
        row["_line"] = reader.line_num
        rows.append(row)
    return header, rows


def parse_number(value):
    """Parse '1.234,56', '1234.56', '1,234.56', '35%', 'DKK 1.200'. Returns float or None."""
    if value is None:
        return None
    t = str(value).strip()
    if not t:
        return None
    t = re.sub(r"(?i)(dkk|sek|nok|eur|kr\.?|%|€|\$)", "", t)
    t = t.replace(" ", "").replace(" ", "")
    neg = t.startswith("(") and t.endswith(")")
    if neg:
        t = t[1:-1]
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3}){2,}", t) else t.replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"-?[1-9]\d{0,2}\.\d{3}", t):
        t = t.replace(".", "")  # Danish thousands separator
    v = float(t)
    return -v if neg else v


def parse_date(value):
    if value is None or not str(value).strip():
        return None
    t = str(value).strip().split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date '{value}' (use yyyy-mm-dd or dd-mm-yyyy)")


def parse_yes(value):
    return str(value).strip().lower() in ("yes", "y", "ja", "j", "true", "1", "x", "commit")


def parse_prob(value):
    v = parse_number(value)
    if v is None:
        return None
    if v > 1:
        v = v / 100.0
    return v


def fmt(n):
    return f"{n:,.0f}"


def pct(x):
    return f"{x * 100:.0f}%"

# ---------------------------------------------------------------- core


def parse_stage_defaults(text):
    out = {}
    for part in text.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError(f"--stage-defaults entry '{part}' must look like Stage=0.35")
        name, val = part.split("=", 1)
        out[name.strip()] = parse_prob(val)
    return out


def quarter_bounds(d):
    q0 = (d.month - 1) // 3 * 3 + 1
    start = date(d.year, q0, 1)
    end = date(d.year + (q0 + 3 > 12), (q0 + 2) % 12 + 1, 1)
    return start, end - timedelta(days=1)


def historical_rates(history_rows, stage_defaults, min_sample, warnings):
    order = sorted(stage_defaults, key=lambda s: stage_defaults[s])
    idx = {s.lower(): i for i, s in enumerate(order)}
    top = len(order) - 1
    deals = {}
    cycles = []
    for r in history_rows:
        name = r.get("deal", "") or f"line {r['_line']}"
        won = parse_yes(r.get("won", ""))
        st = r.get("stage_reached", "").strip().lower()
        if st in idx:
            reach = idx[st]
        elif won or "won" in st:
            reach = top
        else:
            warnings.append(f"History line {r['_line']}: stage '{r.get('stage_reached')}' not in stage list, row skipped.")
            continue
        prev = deals.get(name, {"reach": -1, "won": False})
        deals[name] = {"reach": max(prev["reach"], reach), "won": prev["won"] or won}
        if won:
            try:
                c = parse_number(r.get("cycle_days", ""))
                if c is not None:
                    cycles.append(c)
                else:
                    warnings.append(f"History line {r['_line']} ({name}): cycle_days missing for a won deal.")
            except ValueError:
                warnings.append(f"History line {r['_line']}: cycle_days not a number.")
    rates = {}
    for s in order:
        i = idx[s.lower()]
        reached = [d for d in deals.values() if d["reach"] >= i]
        n = len(reached)
        w = sum(1 for d in reached if d["won"])
        if n >= min_sample:
            rates[s] = {"rate": w / n, "n": n, "won": w, "source": "history"}
        else:
            rates[s] = {"rate": stage_defaults[s], "n": n, "won": w, "source": "stage default (sample < %d)" % min_sample}
    med = statistics.median(cycles) if cycles else None
    return rates, med, len(deals)


def forecast(pipeline_rows, history_rows=None, period_start=None, period_end=None, today=None,
             stage_defaults=None, min_sample=5, closed_won=0.0, target=None,
             commit_risk_threshold=0.5, unknown_stage_prob=0.0):
    today = today or date.today()
    stage_defaults = stage_defaults or parse_stage_defaults(DEFAULT_STAGES)
    if period_start is None or period_end is None:
        period_start, period_end = quarter_bounds(today)
    if period_end < period_start:
        raise ValueError("period end is before period start")
    warnings = []
    sd_lower = {k.lower(): (k, v) for k, v in stage_defaults.items()}

    if history_rows:
        rates, med_cycle, n_hist = historical_rates(history_rows, stage_defaults, min_sample, warnings)
    else:
        rates = {s: {"rate": v, "n": 0, "won": 0, "source": "stage default (no history)"} for s, v in stage_defaults.items()}
        med_cycle, n_hist = None, 0

    has_commit_col = any("rep_commit" in r for r in pipeline_rows)
    seen = {}
    deals = []
    excluded = {"outside_period": 0, "outside_value": 0.0, "lost": 0, "invalid": 0}
    closed_in_file = 0.0
    for r in pipeline_rows:
        line = r["_line"]
        name = r.get("deal", "")
        if not name:
            warnings.append(f"Line {line}: deal name missing.")
            name = f"(line {line})"
        try:
            amount = parse_number(r.get("amount"))
        except ValueError:
            amount = None
        if amount is None:
            warnings.append(f"Line {line} ({name}): amount missing or not a number, deal excluded.")
            excluded["invalid"] += 1
            continue
        if amount < 0:
            warnings.append(f"Line {line} ({name}): negative amount {fmt(amount)}, deal excluded (check sign).")
            excluded["invalid"] += 1
            continue
        try:
            close = parse_date(r.get("close_date"))
        except ValueError as e:
            close = None
            warnings.append(f"Line {line} ({name}): {e}.")
        if close is None:
            warnings.append(f"Line {line} ({name}): close date missing, deal excluded.")
            excluded["invalid"] += 1
            continue
        key = (name.lower(), r.get("stage", "").lower(), amount)
        if key in seen:
            warnings.append(f"Line {line} ({name}): duplicate of line {seen[key]}, counted once.")
            continue
        seen[key] = line
        stage_raw = r.get("stage", "")
        st_l = stage_raw.strip().lower()
        if "lost" in st_l:
            excluded["lost"] += 1
            continue
        if not (period_start <= close <= period_end):
            excluded["outside_period"] += 1
            excluded["outside_value"] += amount
            continue
        if "won" in st_l:
            closed_in_file += amount
            continue
        flags = []
        stage_name, sdef = sd_lower.get(st_l, (stage_raw, None))
        try:
            p = parse_prob(r.get("probability"))
        except ValueError:
            p = None
            warnings.append(f"Line {line} ({name}): probability not a number, stage default used.")
        if p is not None and not 0 <= p <= 1:
            warnings.append(f"Line {line} ({name}): probability {r.get('probability')} out of range, stage default used.")
            p = None
        if sdef is None:
            warnings.append(f"Line {line} ({name}): stage '{stage_raw}' not in stage list, probability {unknown_stage_prob} used.")
            h = unknown_stage_prob
            if p is None:
                p = unknown_stage_prob
        else:
            h = rates[stage_name]["rate"]
            if p is None:
                p = sdef
        commit = parse_yes(r.get("rep_commit", "")) if has_commit_col else False
        if commit and h < commit_risk_threshold:
            flags.append(f"commit at {stage_name} (hist {pct(h)})")
        if close < today:
            flags.append("close date passed")
        deals.append({"deal": name, "owner": r.get("owner", ""), "stage": stage_name, "amount": amount,
                      "close_date": close.isoformat(), "crm_prob": p, "hist_rate": h, "rep_commit": commit,
                      "weighted": amount * p, "historical": amount * h, "flags": flags})

    W = sum(d["weighted"] for d in deals)
    H = sum(d["historical"] for d in deals)
    C = sum(d["amount"] for d in deals if d["rep_commit"])
    C_adj = sum(d["historical"] for d in deals if d["rep_commit"])
    closed = closed_won + closed_in_file
    if has_commit_col:
        commit_open = C_adj
        commit_basis = "closed won + rep commit deals at historical conversion"
    else:
        commit_open = min(W, H)
        commit_basis = "closed won + lower of weighted and historical (no rep_commit column)"
        warnings.append("No rep_commit column: commit scenario uses the lower of weighted and historical methods.")
    scen = {
        "commit": closed + commit_open,
        "most_likely": closed + H,
        "best_case": closed + max(W, H, C),
    }
    total_open = sum(d["amount"] for d in deals)
    top = sorted(deals, key=lambda d: d["historical"], reverse=True)[:2]
    conc = (sum(d["historical"] for d in top) / H) if H else 0.0
    days_left = (period_end - max(today, period_start)).days + 1
    if med_cycle is not None and days_left < med_cycle:
        warnings.append(f"Only {days_left} days left in the period vs median won cycle of {med_cycle:.0f} days: early-stage deals are unlikely to close in time.")
    if not history_rows:
        warnings.append("No history file: historical method equals stage defaults; supply --history for a real comparison.")
    result = {
        "period_start": period_start.isoformat(), "period_end": period_end.isoformat(), "today": today.isoformat(),
        "closed_won": closed, "target": target,
        "methods": {"weighted_pipeline": W, "historical_conversion": H, "rep_commit_face_value": C,
                    "rep_commit_risk_adjusted": C_adj},
        "scenarios": scen, "commit_basis": commit_basis,
        "gaps": {"crm_vs_history": W - H, "rep_commit_vs_risk_adjusted": C - C_adj,
                 "target_gap": {k: (target - v) for k, v in scen.items()} if target else None},
        "rates": rates, "median_won_cycle_days": med_cycle, "history_deals": n_hist,
        "open_deals_in_period": len(deals), "open_value_in_period": total_open,
        "top2_share_of_most_likely": conc, "excluded": excluded, "deals": deals, "warnings": warnings,
    }
    return result


def render(res):
    o = []
    m, s = res["methods"], res["scenarios"]
    o.append(f"# Sales forecast {res['period_start']} to {res['period_end']} (as of {res['today']})")
    o.append("")
    o.append(f"**Commit {fmt(s['commit'])} | Most likely {fmt(s['most_likely'])} | Best case {fmt(s['best_case'])}** "
             f"(includes closed won {fmt(res['closed_won'])}; {res['open_deals_in_period']} open deals worth "
             f"{fmt(res['open_value_in_period'])} close in the period)")
    o.append("")
    o.append("## Forecast range")
    o.append("| Scenario | Forecast | Definition |" + (" Gap to target |" if res["target"] else ""))
    o.append("|---|---:|---|" + ("---:|" if res["target"] else ""))
    defs = {"commit": res["commit_basis"], "most_likely": "closed won + historical conversion on all open deals",
            "best_case": "closed won + highest of weighted, historical and rep commit at face value"}
    for k, label in (("commit", "Commit (low)"), ("most_likely", "Most likely"), ("best_case", "Best case (high)")):
        row = f"| {label} | {fmt(s[k])} | {defs[k]} |"
        if res["target"]:
            row += f" {fmt(res['gaps']['target_gap'][k])} |"
        o.append(row)
    o.append("")
    o.append("## Method comparison")
    o.append("| Method | Open pipeline | Total incl. closed won |")
    o.append("|---|---:|---:|")
    for k, label in (("weighted_pipeline", "Weighted pipeline (CRM probability)"),
                     ("historical_conversion", "Historical stage-to-win conversion"),
                     ("rep_commit_face_value", "Rep commit at face value"),
                     ("rep_commit_risk_adjusted", "Rep commit at historical conversion")):
        o.append(f"| {label} | {fmt(m[k])} | {fmt(m[k] + res['closed_won'])} |")
    o.append("")
    g = res["gaps"]
    o.append(f"- CRM probabilities vs history: {fmt(g['crm_vs_history'])} "
             f"({'CRM more optimistic' if g['crm_vs_history'] > 0 else 'CRM more cautious' if g['crm_vs_history'] < 0 else 'equal'}).")
    o.append(f"- Rep commit at face value vs risk-adjusted: {fmt(g['rep_commit_vs_risk_adjusted'])}.")
    o.append(f"- Top 2 deals make up {pct(res['top2_share_of_most_likely'])} of the open part of the most likely figure.")
    o.append("")
    o.append("## Conversion rates used")
    o.append("| Stage | Rate | Deals in sample | Source |")
    o.append("|---|---:|---:|---|")
    for st, r in res["rates"].items():
        o.append(f"| {st} | {pct(r['rate'])} | {r['n']} | {r['source']} |")
    if res["median_won_cycle_days"] is not None:
        o.append(f"\nMedian sales cycle of won deals: {res['median_won_cycle_days']:.0f} days ({res['history_deals']} closed deals in history).")
    o.append("")
    o.append("## Deals closing in the period")
    o.append("| Deal | Stage | Amount | Close | CRM p | Hist | Commit | Weighted | Historical | Flags |")
    o.append("|---|---|---:|---|---:|---:|---|---:|---:|---|")
    for d in sorted(res["deals"], key=lambda d: d["amount"], reverse=True):
        o.append(f"| {d['deal']} | {d['stage']} | {fmt(d['amount'])} | {d['close_date']} | {pct(d['crm_prob'])} | "
                 f"{pct(d['hist_rate'])} | {'yes' if d['rep_commit'] else ''} | {fmt(d['weighted'])} | "
                 f"{fmt(d['historical'])} | {'; '.join(d['flags'])} |")
    ex = res["excluded"]
    o.append("")
    o.append(f"Excluded: {ex['outside_period']} deals outside the period ({fmt(ex['outside_value'])}), "
             f"{ex['lost']} lost, {ex['invalid']} invalid rows.")
    if res["warnings"]:
        o.append("")
        o.append("## Data quality and warnings")
        for w in res["warnings"]:
            o.append(f"- {w}")
    return "\n".join(o)


def write_csv(path, res):
    cols = ["deal", "owner", "stage", "amount", "close_date", "crm_prob", "hist_rate", "rep_commit",
            "weighted", "historical", "flags"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for d in res["deals"]:
            w.writerow([d["deal"], d["owner"], d["stage"], round(d["amount"], 2), d["close_date"],
                        round(d["crm_prob"], 4), round(d["hist_rate"], 4), "yes" if d["rep_commit"] else "no",
                        round(d["weighted"], 2), round(d["historical"], 2), "; ".join(d["flags"])])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pipeline", help="open pipeline CSV")
    ap.add_argument("--history", help="optional closed deal history CSV")
    ap.add_argument("--period-start", help="period start yyyy-mm-dd (default: start of current quarter)")
    ap.add_argument("--period-end", help="period end yyyy-mm-dd (default: end of current quarter)")
    ap.add_argument("--today", help="as-of date (default: system date)")
    ap.add_argument("--stage-defaults", default=DEFAULT_STAGES,
                    help="stage probabilities, also define stage order (default: %(default)s)")
    ap.add_argument("--min-sample", type=int, default=5,
                    help="minimum history deals per stage before the historical rate is trusted (default: 5)")
    ap.add_argument("--closed-won", default="0", help="amount already closed won in the period (default: 0)")
    ap.add_argument("--target", help="period target, to show the gap per scenario")
    ap.add_argument("--commit-risk-threshold", type=float, default=0.5,
                    help="flag rep commit deals whose historical rate is below this (default: 0.5)")
    ap.add_argument("--unknown-stage-prob", type=float, default=0.0,
                    help="probability for stages not in the stage list (default: 0)")
    ap.add_argument("--out", help="write per-deal results to this CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    try:
        _, prow = read_csv(a.pipeline, ["deal", "stage", "amount", "close_date"],
                           ["probability", "rep_commit", "owner"])
        hrows = None
        if a.history:
            _, hrows = read_csv(a.history, ["deal", "stage_reached", "won", "amount", "cycle_days"])
        today = parse_date(a.today) if a.today else date.today()
        res = forecast(prow, hrows, parse_date(a.period_start) if a.period_start else None,
                       parse_date(a.period_end) if a.period_end else None, today,
                       parse_stage_defaults(a.stage_defaults), a.min_sample, parse_number(a.closed_won) or 0.0,
                       parse_number(a.target) if a.target else None, a.commit_risk_threshold, a.unknown_stage_prob)
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if a.out:
        write_csv(a.out, res)
    print(json.dumps(res, indent=2, default=str) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
