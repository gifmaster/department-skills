#!/usr/bin/env python3
"""Software licence review: utilisation, waste, duplicate tools, renewal and notice deadlines.

Purpose
  Reconciles a subscription list with per-user activity so licence savings are
  calculated, and checks every saving against the renewal date and notice period.

Input columns
  Subscriptions CSV (required): product, vendor, licences, cost_per_licence_month, renewal_date, notice_days
    optional: category (overrides keyword categories), term_months (default --term-months)
  Usage CSV (--usage, recommended): product, user, last_active_date
    One row per user per product. A blank last_active_date means never active.

Formulas
  monthly cost       = licences x cost_per_licence_month; annual = monthly x 12
  active users       = distinct users with last_active_date >= today - --inactive-days
  utilisation        = active / licences
  unused licences    = max(0, licences - active); waste = unused x cost (monthly, x 12 annual)
  over-deployment    = active - licences when positive (compliance risk)
  keep               = min(licences, ceil(active x (1 + --buffer-pct/100)))
  saving             = (licences - keep) x cost per month, x 12 per year
  next renewal       = renewal_date rolled forward by term_months until it is on or after today
  notice deadline    = next renewal - notice_days. If the deadline has passed, the saving can
                       only start at the following renewal (next renewal + term), whose deadline is shown.
  saving next 12 mth = annual saving x days from effective date to today + 365, / 365
  duplicates         = two or more products in the same category (keyword match, --categories JSON to override)

Example
  python3 scripts/licences.py assets/subscriptions_template.csv --usage assets/usage_template.csv --today 2026-11-16
"""
import argparse
import calendar
import csv
import io
import json
import math
import re
import sys
from datetime import date, datetime, timedelta

DEFAULT_CATEGORIES = {
    "video meetings": ["zoom", "teams", "webex", "google meet", "gotomeeting", "whereby", "microsoft 365", "m365", "office 365"],
    "chat": ["slack", "teams", "microsoft 365", "m365", "office 365", "google workspace", "workplace"],
    "file storage": ["dropbox", "box", "onedrive", "google drive", "sharepoint", "microsoft 365", "m365", "google workspace"],
    "whiteboard": ["miro", "mural", "whiteboard", "figjam"],
    "pdf editing": ["acrobat", "nitro", "foxit", "pdf"],
    "e-signature": ["docusign", "penneo", "adobe sign", "scrive", "dokobit"],
    "password manager": ["1password", "lastpass", "bitwarden", "keeper", "dashlane"],
    "project management": ["asana", "trello", "monday", "jira", "clickup", "wrike", "planner", "basecamp"],
    "remote support": ["teamviewer", "anydesk", "splashtop", "logmein"],
    "diagramming": ["visio", "lucidchart", "draw.io"],
    "crm": ["hubspot", "pipedrive", "salesforce", "superoffice", "dynamics 365 sales"],
    "design": ["creative cloud", "canva", "figma", "affinity"],
}

# ---------------------------------------------------------------- helpers


def norm_col(name):
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def read_csv(path, required, optional=()):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first:
        raise ValueError(f"{path} is empty")
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    header, rows = None, []
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
    if value is None:
        return None
    t = str(value).strip()
    if not t:
        return None
    t = re.sub(r"(?i)(dkk|sek|nok|eur|kr\.?|%|€|\$)", "", t).replace(" ", "").replace(" ", "")
    neg = t.startswith("(") and t.endswith(")")
    if neg:
        t = t[1:-1]
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3}){2,}", t) else t.replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"-?[1-9]\d{0,2}\.\d{3}", t):
        t = t.replace(".", "")
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


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def fmt(n):
    return "-" if n is None else f"{n:,.0f}"


def key(name):
    return re.sub(r"\s+", " ", name.strip().lower())

# ---------------------------------------------------------------- core


def categorise(product, explicit, categories):
    if explicit:
        return [c.strip().lower() for c in re.split(r"[|;]", explicit) if c.strip()]
    p = product.lower()
    return [cat for cat, kws in categories.items() if any(re.search(r"\b" + re.escape(k) + r"\b", p) for k in kws)]


def next_renewal(renewal, term, today):
    k = 0
    while add_months(renewal, k * term) < today:
        k += 1
    return add_months(renewal, k * term), k


def analyse(subs, usage, today, inactive_days=90, window_days=90, buffer_pct=5.0, term_months=12,
            default_notice_days=30, categories=None):
    categories = categories or DEFAULT_CATEGORIES
    warnings = []
    cutoff = today - timedelta(days=inactive_days)
    usage_by = {}
    seen_u = set()
    for u in usage or []:
        pk, user = key(u.get("product", "")), u.get("user", "").strip().lower()
        if not pk or not user:
            warnings.append(f"Usage line {u['_line']}: product or user missing, row skipped.")
            continue
        if (pk, user) in seen_u:
            warnings.append(f"Usage line {u['_line']}: duplicate row for {u.get('product')} / {u.get('user')}, latest date kept.")
        seen_u.add((pk, user))
        try:
            d = parse_date(u.get("last_active_date"))
        except ValueError as e:
            d = None
            warnings.append(f"Usage line {u['_line']}: {e}; treated as inactive.")
        if d and d > today:
            warnings.append(f"Usage line {u['_line']}: last_active_date {d} is after today, check the export.")
        cur = usage_by.setdefault(pk, {})
        if user not in cur or (d and (cur[user] is None or d > cur[user])):
            cur[user] = d

    items, seen = [], {}
    for s in subs:
        line, prod = s["_line"], s.get("product", "")
        pk = key(prod)
        if not pk:
            warnings.append(f"Line {line}: product name missing, row skipped.")
            continue
        if pk in seen:
            warnings.append(f"Line {line}: {prod} duplicates line {seen[pk]} (double billing or duplicate row?), counted once.")
            continue
        seen[pk] = line
        try:
            lic = parse_number(s.get("licences"))
            cost = parse_number(s.get("cost_per_licence_month"))
        except ValueError:
            lic, cost = None, None
            warnings.append(f"Line {line} ({prod}): licences or cost not a number.")
        if lic is None or lic < 0:
            warnings.append(f"Line {line} ({prod}): licences missing or negative, row skipped.")
            continue
        if cost is None:
            warnings.append(f"Line {line} ({prod}): cost_per_licence_month missing, costs and savings not calculated.")
        elif cost < 0:
            warnings.append(f"Line {line} ({prod}): negative cost {cost}, treated as missing (check sign).")
            cost = None
        term = term_months
        if s.get("term_months"):
            try:
                term = int(parse_number(s["term_months"]))
            except (ValueError, TypeError):
                warnings.append(f"Line {line} ({prod}): term_months not a number, {term_months} used.")
        notice = parse_number(s.get("notice_days")) if s.get("notice_days") else None
        if notice is None:
            notice = default_notice_days
            warnings.append(f"Line {line} ({prod}): notice_days missing, {default_notice_days} days assumed (check the contract).")
        try:
            ren = parse_date(s.get("renewal_date"))
        except ValueError as e:
            ren = None
            warnings.append(f"Line {line} ({prod}): {e}.")
        if ren is None:
            warnings.append(f"Line {line} ({prod}): renewal_date missing, deadline not calculated.")
        users = usage_by.get(pk)
        if users is None:
            active = None
            warnings.append(f"{prod}: no usage data, utilisation and savings not calculated.")
        else:
            active = sum(1 for d in users.values() if d and d >= cutoff)
        lic_i = int(lic)
        it = {"product": prod, "vendor": s.get("vendor", ""), "licences": lic_i, "cost_per_licence_month": cost,
              "monthly_cost": lic_i * cost if cost is not None else None,
              "annual_cost": lic_i * cost * 12 if cost is not None else None,
              "users_in_usage": len(users) if users is not None else None, "active_users": active,
              "categories": categorise(prod, s.get("category", ""), categories), "term_months": term,
              "notice_days": int(notice), "flags": []}
        if active is not None:
            it["utilisation"] = active / lic_i if lic_i else None
            it["unused"] = max(0, lic_i - active)
            it["over_deployed"] = max(0, active - lic_i)
            keep = min(lic_i, math.ceil(active * (1 + buffer_pct / 100.0)))
            it["recommended"] = keep
            it["reducible"] = lic_i - keep
            if it["over_deployed"]:
                it["flags"].append(f"{it['over_deployed']} more active users than licences (compliance risk)")
            if active == 0 and lic_i:
                it["flags"].append("no active users: cancel candidate")
        else:
            it.update({"utilisation": None, "unused": None, "over_deployed": None, "recommended": None, "reducible": None})
        if cost is not None and it["unused"] is not None:
            it["waste_monthly"] = it["unused"] * cost
            it["saving_annual"] = it["reducible"] * cost * 12
        else:
            it["waste_monthly"] = None
            it["saving_annual"] = None
        if ren is not None:
            nr, k = next_renewal(ren, term, today)
            if k:
                it["flags"].append(f"renewal date {ren} has passed, rolled forward to {nr}")
            dl = nr - timedelta(days=int(notice))
            it["next_renewal"], it["notice_deadline"] = nr.isoformat(), dl.isoformat()
            if dl < today:
                eff = add_months(ren, (k + 1) * term)
                eff_dl = eff - timedelta(days=int(notice))
                it["deadline_passed"] = True
                it["flags"].append(f"notice deadline {dl} passed: renews {nr}, next exit {eff} (notice by {eff_dl})")
            else:
                eff, eff_dl = nr, dl
                it["deadline_passed"] = False
                if (dl - today).days <= window_days:
                    it["flags"].append(f"notice deadline in {(dl - today).days} days")
            it["effective_date"], it["action_deadline"] = eff.isoformat(), eff_dl.isoformat()
            it["days_to_action"] = (eff_dl - today).days
            if it["saving_annual"] is not None:
                horizon = today + timedelta(days=365)
                it["saving_next_12m"] = it["saving_annual"] * max(0, (horizon - eff).days) / 365.0
            else:
                it["saving_next_12m"] = None
        else:
            it.update({"next_renewal": "", "notice_deadline": "", "deadline_passed": None, "effective_date": "",
                       "action_deadline": "", "days_to_action": None, "saving_next_12m": None})
        items.append(it)

    sub_keys = {key(i["product"]) for i in items}
    for pk, users in usage_by.items():
        if pk not in sub_keys:
            warnings.append(f"Usage found for '{pk}' ({len(users)} users) but no subscription: unlicensed or shadow IT, check.")
    cats = {}
    for i in items:
        for c in i["categories"]:
            cats.setdefault(c, []).append(i)
    dups = []
    for c, lst in sorted(cats.items()):
        if len(lst) > 1:
            dups.append({"category": c, "products": [i["product"] for i in lst],
                         "monthly_cost": sum(i["monthly_cost"] or 0 for i in lst)})

    def tot(field):
        return sum(i[field] for i in items if i.get(field) is not None)
    totals = {"monthly_cost": tot("monthly_cost"), "annual_cost": tot("annual_cost"),
              "waste_monthly": tot("waste_monthly"), "waste_annual": tot("waste_monthly") * 12,
              "saving_annual": tot("saving_annual"), "saving_next_12m": tot("saving_next_12m"),
              "licences": tot("licences"), "unused": tot("unused")}
    upcoming = sorted([i for i in items if i["action_deadline"] and 0 <= i["days_to_action"] <= window_days],
                      key=lambda i: i["action_deadline"])
    return {"today": today.isoformat(), "inactive_days": inactive_days, "window_days": window_days,
            "buffer_pct": buffer_pct, "items": items, "duplicates": dups, "totals": totals,
            "upcoming": [i["product"] for i in upcoming], "warnings": warnings}


def render(res):
    t = res["totals"]
    o = [f"# Licence review (as of {res['today']}, inactive after {res['inactive_days']} days)", ""]
    o.append(f"**Spend {fmt(t['monthly_cost'])} per month ({fmt(t['annual_cost'])} per year). "
             f"Unused licences {fmt(t['unused'])}, waste {fmt(t['waste_monthly'])} per month ({fmt(t['waste_annual'])} per year). "
             f"Savings estimate {fmt(t['saving_annual'])} per year with a {res['buffer_pct']:g}% buffer, "
             f"{fmt(t['saving_next_12m'])} realisable in the next 12 months given notice deadlines.**")
    o.append("")
    o.append("## 1. Licence position")
    o.append("| Product | Licences | Active | Utilisation | Unused | Cost/month | Waste/month | Flags |")
    o.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for i in sorted(res["items"], key=lambda i: -(i["waste_monthly"] or 0)):
        util = "-" if i["utilisation"] is None else f"{i['utilisation'] * 100:.0f}%"
        o.append(f"| {i['product']} | {i['licences']} | {fmt(i['active_users'])} | {util} | {fmt(i['unused'])} | "
                 f"{fmt(i['monthly_cost'])} | {fmt(i['waste_monthly'])} | {'; '.join(i['flags'])} |")
    o.append("")
    o.append("## 2. Savings opportunities (respecting notice periods)")
    o.append("| Product | Keep | Cut | Saving/year | Earliest effective | Give notice by | Saving next 12 months |")
    o.append("|---|---:|---:|---:|---|---|---:|")
    for i in sorted(res["items"], key=lambda i: -(i["saving_annual"] or 0)):
        if i["saving_annual"]:
            o.append(f"| {i['product']} | {i['recommended']} | {i['reducible']} | {fmt(i['saving_annual'])} | "
                     f"{i['effective_date'] or '-'} | {i['action_deadline'] or '-'} | {fmt(i['saving_next_12m'])} |")
    o.append("")
    o.append("## 3. Duplicate tools")
    if res["duplicates"]:
        for d in res["duplicates"]:
            o.append(f"- {d['category']}: {', '.join(d['products'])} (combined {fmt(d['monthly_cost'])} per month)")
    else:
        o.append("None found by keyword.")
    o.append("")
    o.append(f"## 4. Renewals and notice deadlines (next {res['window_days']} days)")
    up = [i for i in res["items"] if i["product"] in res["upcoming"]]
    if up:
        o.append("| Product | Next renewal | Notice days | Act by | Days left |")
        o.append("|---|---|---:|---|---:|")
        for i in sorted(up, key=lambda i: i["action_deadline"]):
            o.append(f"| {i['product']} | {i['effective_date']} | {i['notice_days']} | {i['action_deadline']} | {i['days_to_action']} |")
    else:
        o.append("No notice deadlines in the window.")
    passed = [i for i in res["items"] if i.get("deadline_passed")]
    if passed:
        o.append("")
        o.append("Notice deadline already passed (subscription will renew):")
        for i in passed:
            o.append(f"- {i['product']}: renews {i['next_renewal']}; next exit {i['effective_date']}, give notice by {i['action_deadline']}.")
    if res["warnings"]:
        o.append("")
        o.append("## Data quality and warnings")
        for w in res["warnings"]:
            o.append(f"- {w}")
    return "\n".join(o)


def write_csv(path, res):
    cols = ["product", "vendor", "categories", "licences", "active_users", "utilisation", "unused", "over_deployed",
            "cost_per_licence_month", "monthly_cost", "waste_monthly", "recommended", "reducible", "saving_annual",
            "next_renewal", "notice_days", "notice_deadline", "effective_date", "action_deadline", "saving_next_12m", "flags"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i in res["items"]:
            w.writerow([("|".join(i[c]) if c == "categories" else "; ".join(i[c]) if c == "flags"
                         else (round(i[c], 4) if isinstance(i[c], float) else ("" if i[c] is None else i[c])))
                        for c in cols])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subscriptions", help="subscriptions CSV")
    ap.add_argument("--usage", help="per-user usage CSV (product, user, last_active_date)")
    ap.add_argument("--today", help="as-of date (default: system date)")
    ap.add_argument("--inactive-days", type=int, default=90, help="days without activity before a licence is unused (default: 90)")
    ap.add_argument("--window-days", type=int, default=90, help="flag notice deadlines within this many days (default: 90)")
    ap.add_argument("--buffer-pct", type=float, default=5.0, help="licences kept above active users, percent (default: 5)")
    ap.add_argument("--term-months", type=int, default=12, help="renewal term when no term_months column (default: 12)")
    ap.add_argument("--default-notice-days", type=int, default=30,
                    help="notice days assumed when missing, verify against the contract (default: 30)")
    ap.add_argument("--categories", help="JSON file {category: [keywords]} replacing the built-in keyword list")
    ap.add_argument("--out", help="write per-product results to this CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    try:
        _, subs = read_csv(a.subscriptions, ["product", "vendor", "licences", "cost_per_licence_month", "renewal_date",
                                             "notice_days"], ["category", "term_months"])
        usage = None
        if a.usage:
            _, usage = read_csv(a.usage, ["product", "user", "last_active_date"])
        cats = None
        if a.categories:
            with open(a.categories, encoding="utf-8") as fh:
                cats = {k.lower(): [x.lower() for x in v] for k, v in json.load(fh).items()}
        today = parse_date(a.today) if a.today else date.today()
        res = analyse(subs, usage, today, a.inactive_days, a.window_days, a.buffer_pct, a.term_months,
                      a.default_notice_days, cats)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if a.usage is None:
        res["warnings"].insert(0, "No --usage file: utilisation and savings not calculated.")
    if a.out:
        write_csv(a.out, res)
    print(json.dumps(res, indent=2, default=str) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
