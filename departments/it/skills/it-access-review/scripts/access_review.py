#!/usr/bin/env python3
"""User access review: match system accounts to HR records and flag what to remove.

Purpose
  Reconciles account exports from one or more systems with the HR employee list,
  flags orphaned, leaver, dormant, shared, privileged and excess access, and prints
  manager-ready attestation lists per department.

Input columns
  Accounts CSV (required): system, account, display_name, email, role, last_login, is_admin
    optional: enabled (yes/no; default yes). Several roles in one cell may be split by | ; or +.
  HR CSV (--hr, required): employee_id, name, email, department, job_role, status, end_date
    status is active or leaver. optional: manager.
  Role map JSON (--role-map, optional): {"Bookkeeper": ["Accountant", "Vendor payments"], ...}
    or per system: {"Bookkeeper": {"ERP": ["Accountant"], "M365": ["*"]}}. "*" allows any role.

Matching and rules
  1. Match on email (case-insensitive). 2. Else fuzzy name match on display_name (or the
     email local part): lower case, ae/oe/aa folding (ae=ae, oe=o, aa=a), admin tokens
     removed, difflib ratio >= --name-threshold (default 0.85). Fuzzy matches are listed for checking.
  ORPHANED      no HR match and not a generic name.
  SHARED        no HR match and the first token of the account or email local part is in
                --generic-names (info, admin, test, ...).
  LEAVER        HR status leaver and account enabled: days since end_date = today - end_date;
                login after end_date is flagged as a possible security event.
  ADMIN-DAILY   is_admin = yes on an account that is not admin-named (personal daily account);
                ADMIN-NO-DAILY: admin-named account and no regular account in the same system.
  DORMANT       last_login older than --dormant-days (default 90) or never.
  ROLE-MISMATCH a role not in the role map for the person's job_role.

Example
  python3 scripts/access_review.py assets/accounts_template.csv --hr assets/hr_template.csv \
      --role-map assets/role_map_template.json --today 2026-11-16
"""
import argparse
import csv
import difflib
import io
import json
import re
import sys
from datetime import date, datetime

DEFAULT_GENERIC = ("info,admin,administrator,adm,test,testuser,demo,shared,service,svc,support,helpdesk,"
                   "noreply,no-reply,kontakt,post,mail,office,reception,lager,warehouse,scanner,printer,"
                   "guest,temp,vikar,bogholderi,salg,sales,faktura,invoice,root,sa,backup")
ADMIN_TOKENS = {"admin", "adm", "administrator", "a", "priv", "sa", "da", "ga"}
SEVERITY = {"LEAVER": 1, "LOGIN-AFTER-END": 1, "ORPHANED": 1, "SHARED": 2, "ADMIN-DAILY": 2,
            "ROLE-MISMATCH": 3, "ADMIN-NO-DAILY": 3, "DORMANT": 3}

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


def parse_yes(value, default=False):
    t = str(value).strip().lower()
    if not t:
        return default
    return t in ("yes", "y", "ja", "j", "true", "1", "x", "enabled", "active", "aktiv")


def fold(text):
    t = text.lower()
    for a, b in (("æ", "ae"), ("ø", "o"), ("å", "a"), ("aa", "a"), ("ö", "o"), ("ä", "ae"), ("ü", "u"),
                 ("é", "e"), ("è", "e")):
        t = t.replace(a, b)
    return t


def tokens(text):
    return [t for t in re.split(r"[^a-z0-9]+", fold(text)) if t]


def person_key(text):
    """Name tokens with admin markers removed, for fuzzy matching."""
    return " ".join(t for t in tokens(text) if t not in ADMIN_TOKENS)


def local_part(email):
    return email.split("@")[0] if "@" in email else ""


def is_admin_named(account, email):
    toks = tokens(account) + tokens(local_part(email))
    raw = (account + " " + local_part(email)).lower()
    return any(t in ("admin", "adm", "administrator", "priv") for t in toks) or bool(
        re.search(r"(^|[^a-z])(a|da|ga|sa)[-_.]", raw) or re.search(r"[-_.](a|adm)($|[^a-z])", raw))


def split_roles(role):
    return [r.strip() for r in re.split(r"[|;+]", role or "") if r.strip()]

# ---------------------------------------------------------------- core


def review(accounts, hr, today, role_map=None, dormant_days=90, name_threshold=0.85, generic=None):
    generic = set(g.strip().lower() for g in (generic or DEFAULT_GENERIC).split(",") if g.strip())
    warnings = []
    by_email, people = {}, []
    seen_hr = set()
    for h in hr:
        try:
            h["_end"] = parse_date(h.get("end_date"))
        except ValueError as e:
            h["_end"] = None
            warnings.append(f"HR line {h['_line']} ({h.get('name')}): {e}.")
        status = h.get("status", "").strip().lower()
        h["_leaver"] = status in ("leaver", "left", "fratraadt", "fratrådt", "inactive", "terminated")
        if status not in ("active", "aktiv", "") and not h["_leaver"]:
            warnings.append(f"HR line {h['_line']} ({h.get('name')}): unknown status '{h.get('status')}'.")
        if h["_leaver"] and not h["_end"]:
            warnings.append(f"HR line {h['_line']} ({h.get('name')}): leaver without end_date.")
        em = h.get("email", "").strip().lower()
        if em:
            if em in by_email:
                warnings.append(f"HR line {h['_line']}: email {em} also on HR line {by_email[em]['_line']}.")
            else:
                by_email[em] = h
        else:
            warnings.append(f"HR line {h['_line']} ({h.get('name')}): email missing, name matching only.")
        h["_key"] = person_key(h.get("name", ""))
        if h.get("employee_id") in seen_hr and h.get("employee_id"):
            warnings.append(f"HR line {h['_line']}: duplicate employee_id {h.get('employee_id')}.")
        seen_hr.add(h.get("employee_id"))
        people.append(h)

    rm = {k.strip().lower(): v for k, v in (role_map or {}).items()}
    results, seen_acc = [], {}
    for a in accounts:
        line = a["_line"]
        sysname, acc = a.get("system", ""), a.get("account", "")
        email = a.get("email", "").strip().lower()
        k = (sysname.lower(), acc.lower())
        if k in seen_acc:
            warnings.append(f"Accounts line {line}: {sysname}/{acc} duplicates line {seen_acc[k]}.")
            continue
        seen_acc[k] = line
        enabled = parse_yes(a.get("enabled", ""), default=True)
        admin = parse_yes(a.get("is_admin", ""))
        bad_date = False
        try:
            last = parse_date(a.get("last_login"))
        except ValueError as e:
            last, bad_date = None, True
            warnings.append(f"Accounts line {line} ({acc}): {e}; last login treated as unknown.")
        match, method, score = None, "none", 0.0
        if email and email in by_email:
            match, method, score = by_email[email], "email", 1.0
        else:
            cand = person_key(a.get("display_name", "")) or person_key(local_part(email).replace(".", " "))
            if cand:
                best = None
                for h in people:
                    sc = difflib.SequenceMatcher(None, cand, h["_key"]).ratio()
                    if best is None or sc > best[0]:
                        best = (sc, h)
                if best and best[0] >= name_threshold:
                    match, method, score = best[1], "fuzzy name", best[0]
        first_tok = (tokens(acc) or [""])[0]
        first_mail = (tokens(local_part(email)) or [""])[0]
        named_admin = is_admin_named(acc, email)
        findings = []
        if match is None:
            if first_tok in generic or first_mail in generic or acc.lower() in generic:
                findings.append(("SHARED", "shared or generic account, no named owner" + (" WITH ADMIN RIGHTS" if admin else "")))
            else:
                findings.append(("ORPHANED", "no HR match"))
        else:
            if match["_leaver"] and enabled:
                if match["_end"]:
                    days = (today - match["_end"]).days
                    if days >= 0:
                        findings.append(("LEAVER", f"leaver, ended {match['_end'].isoformat()}, still enabled {days} days later"))
                    else:
                        findings.append(("LEAVER", f"leaving {match['_end'].isoformat()} (in {-days} days): schedule disable"))
                    if last and last > match["_end"]:
                        findings.append(("LOGIN-AFTER-END", f"login on {last.isoformat()} after end date: investigate as possible security event"))
                else:
                    findings.append(("LEAVER", "leaver with no end date, still enabled"))
            if role_map is not None:
                jr = match.get("job_role", "").strip().lower()
                allowed = rm.get(jr)
                if allowed is None:
                    allowed = rm.get("_default")
                if isinstance(allowed, dict):
                    allowed = {s.lower(): v for s, v in allowed.items()}.get(sysname.lower(), allowed.get("*"))
                if allowed is None:
                    findings.append(("ROLE-MISMATCH", f"no role definition for job role '{match.get('job_role')}' in {sysname}"))
                elif "*" not in allowed:
                    al = {x.strip().lower() for x in allowed}
                    extra = [r for r in split_roles(a.get("role", "")) if r.lower() not in al]
                    if extra:
                        findings.append(("ROLE-MISMATCH", f"role(s) not in role map for {match.get('job_role')}: {', '.join(extra)}"))
        if admin and not named_admin and match is not None:
            findings.append(("ADMIN-DAILY", "admin rights on a personal daily account: use a separate admin account"))
        if enabled and (last is None or (today - last).days > dormant_days):
            if last is not None:
                findings.append(("DORMANT", f"last login {last.isoformat()} ({(today - last).days} days ago)"))
            else:
                findings.append(("DORMANT", "last login unknown (invalid date)" if bad_date else "never logged in"))
        results.append({
            "system": sysname, "account": acc, "display_name": a.get("display_name", ""), "email": email,
            "role": a.get("role", ""), "is_admin": admin, "admin_named": named_admin, "enabled": enabled,
            "last_login": last.isoformat() if last else ("invalid date" if bad_date else ""), "match_method": method, "match_score": round(score, 2),
            "employee_id": match.get("employee_id", "") if match else "", "person": match.get("name", "") if match else "",
            "department": match.get("department", "") if match else "", "manager": match.get("manager", "") if match else "",
            "job_role": match.get("job_role", "") if match else "", "findings": findings,
        })

    # admin-named accounts without a regular account in the same system
    for r in results:
        if r["admin_named"] and r["employee_id"]:
            others = [x for x in results if x["employee_id"] == r["employee_id"] and x["system"].lower() == r["system"].lower()
                      and not x["admin_named"]]
            if not others:
                r["findings"].append(("ADMIN-NO-DAILY", "admin account with no separate daily account in this system: check it is not used for daily work"))
        r["findings"].sort(key=lambda f: SEVERITY.get(f[0], 9))
        r["severity"] = min((SEVERITY.get(f[0], 9) for f in r["findings"]), default=9)
    for r in results:
        if r["match_method"] == "fuzzy name":
            warnings.append(f"Fuzzy match to verify: {r['system']}/{r['account']} '{r['display_name']}' -> {r['person']} (score {r['match_score']}).")
    matched_ids = {r["employee_id"] for r in results if r["employee_id"]}
    no_account = [h for h in people if not h["_leaver"] and h.get("employee_id") not in matched_ids]
    counts = {}
    for r in results:
        for code, _ in r["findings"]:
            counts[code] = counts.get(code, 0) + 1
    return {"today": today.isoformat(), "accounts": len(results), "hr_people": len(people), "counts": counts,
            "results": results, "hr_without_accounts": [h.get("name") for h in no_account],
            "role_map_used": role_map is not None, "warnings": warnings}


def cell(text):
    return str(text).replace("|", " / ")


def render(res):
    o = [f"# Access review (as of {res['today']})", ""]
    c = res["counts"]
    o.append(f"**{res['accounts']} accounts reviewed against {res['hr_people']} HR records.** "
             f"Leavers still enabled: {c.get('LEAVER', 0)} | Orphaned: {c.get('ORPHANED', 0)} | Shared/generic: {c.get('SHARED', 0)} | "
             f"Admin on daily account: {c.get('ADMIN-DAILY', 0)} | Dormant: {c.get('DORMANT', 0)} | Role mismatches: {c.get('ROLE-MISMATCH', 0)}")
    if not res["role_map_used"]:
        o.append("\nNo role map given: excess access by role was not checked (use --role-map).")

    def section(title, codes):
        rows = [(r, f) for r in res["results"] for f in r["findings"] if f[0] in codes]
        o.append("")
        o.append(f"## {title}")
        if not rows:
            o.append("None found.")
            return
        o.append("| System | Account | Person | Finding | Detail |")
        o.append("|---|---|---|---|---|")
        for r, f in rows:
            o.append(f"| {r['system']} | {r['account']} | {r['person'] or r['display_name'] or '-'} | {f[0]} | {f[1]} |")

    section("1. Leavers and orphaned or shared accounts", ("LEAVER", "LOGIN-AFTER-END", "ORPHANED", "SHARED"))
    section("2. Excess access (role map)", ("ROLE-MISMATCH",))
    section("3. Privileged access", ("ADMIN-DAILY", "ADMIN-NO-DAILY"))
    admins = [r for r in res["results"] if r["is_admin"]]
    o.append("")
    o.append(f"Admin accounts in total: {len(admins)} ({', '.join(r['system'] + '/' + r['account'] for r in admins)}).")
    section("4. Dormant accounts", ("DORMANT",))
    o.append("")
    o.append("## 5. Attestation lists per department")
    o.append("Manager: mark each line KEEP or REMOVE and return by the agreed date. Unconfirmed access is removed.")
    depts = {}
    for r in res["results"]:
        depts.setdefault(r["department"] or "Unassigned (IT owner to resolve)", []).append(r)
    for d in sorted(depts, key=lambda x: (x.startswith("Unassigned"), x)):
        o.append("")
        o.append(f"### {d}")
        o.append("| Attesting manager | Person | System | Account | Role | Admin | Last login | Findings | KEEP/REMOVE |")
        o.append("|---|---|---|---|---|---|---|---|---|")
        for r in sorted(depts[d], key=lambda r: (r["manager"] or "~", r["person"] or r["account"], r["system"])):
            o.append(f"| {r['manager'] or 'IT owner'} | {r['person'] or r['display_name'] or '-'} | {r['system']} | {r['account']} | {cell(r['role'])} | "
                     f"{'yes' if r['is_admin'] else ''} | {r['last_login'] or 'never'} | "
                     f"{', '.join(f[0] for f in r['findings']) or 'OK'} | |")
    if res["hr_without_accounts"]:
        o.append("")
        o.append(f"Active employees with no account in the exports: {', '.join(res['hr_without_accounts'])}.")
    if res["warnings"]:
        o.append("")
        o.append("## Data quality and matching warnings")
        for w in res["warnings"]:
            o.append(f"- {w}")
    return "\n".join(o)


def write_csv(path, res):
    cols = ["department", "manager", "person", "employee_id", "job_role", "system", "account", "email", "role",
            "is_admin", "last_login", "match_method", "match_score", "severity", "findings", "decision"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in sorted(res["results"], key=lambda r: (r["department"] or "~", r["person"], r["system"])):
            w.writerow([r["department"], r["manager"], r["person"], r["employee_id"], r["job_role"], r["system"],
                        r["account"], r["email"], r["role"], "yes" if r["is_admin"] else "no", r["last_login"],
                        r["match_method"], r["match_score"], r["severity"],
                        "; ".join(f"{c}: {t}" for c, t in r["findings"]), ""])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accounts", help="accounts export CSV (one or more systems)")
    ap.add_argument("--hr", required=True, help="HR employee list CSV")
    ap.add_argument("--role-map", help="JSON file mapping job_role to allowed roles")
    ap.add_argument("--today", help="as-of date (default: system date)")
    ap.add_argument("--dormant-days", type=int, default=90, help="days without login before dormant (default: 90)")
    ap.add_argument("--name-threshold", type=float, default=0.85, help="fuzzy name match threshold 0-1 (default: 0.85)")
    ap.add_argument("--generic-names", default=DEFAULT_GENERIC, help="comma list of generic account names (default: %(default)s)")
    ap.add_argument("--out", help="write the full attestation list to this CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    try:
        _, acc = read_csv(a.accounts, ["system", "account", "display_name", "email", "role", "last_login", "is_admin"], ["enabled"])
        _, hr = read_csv(a.hr, ["employee_id", "name", "email", "department", "job_role", "status", "end_date"], ["manager"])
        rmap = None
        if a.role_map:
            with open(a.role_map, encoding="utf-8") as fh:
                rmap = json.load(fh)
        today = parse_date(a.today) if a.today else date.today()
        res = review(acc, hr, today, rmap, a.dormant_days, a.name_threshold, a.generic_names)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if a.out:
        write_csv(a.out, res)
    print(json.dumps(res, indent=2, default=str) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
