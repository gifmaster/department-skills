#!/usr/bin/env python3
"""Spend analysis: supplier normalisation, categorisation, Pareto, tail spend and savings ranges.

Purpose
    Clean an AP extract, group supplier name variants, categorise spend, and size
    consolidation and tail-spend opportunities as clearly labelled estimate ranges.

Input columns (CSV, comma or semicolon)
    supplier, amount, date, account, description
    amount: '1.234,56' or '1234.56'; negative = credit note (netted). date: yyyy-mm-dd or dd-mm-yyyy.

Method and formulas
    Supplier key   = lower case, accents folded, legal forms removed (A/S, ApS, IVS, I/S, K/S, P/S,
                     GmbH, Ltd, AB, Oy, BV, AG, NV, SA, S.a r.l., Inc, LLC, plc, a.m.b.a.), country
                     words removed (--strip-words, default danmark, denmark, dk), punctuation removed.
                     Identical keys are merged; keys with difflib ratio >= --fuzzy-threshold (0.85)
                     are merged; names where one key's words are all inside another are only listed
                     for review. Every merge is reported.
    Category       = first match of: account map (JSON "_accounts"), keyword in description, keyword in
                     supplier name, the supplier's main category; else Uncategorised. Keywords match
                     the start of a word. Built-in map unless --categories JSON is given.
    Pareto         = suppliers by spend, cumulative share; N suppliers for 80 % of spend
    Tail spend     = suppliers ranked after cumulative share 1 - --tail-share (default last 20 %)
    Fragmentation  = categories with >= --frag-min-suppliers (default 3) suppliers
    Savings (ESTIMATE) = fragmented category spend x consolidation low/high % (default 5/10 %)
                     + tail spend outside fragmented categories x tail low/high % (default 5/15 %)

Example
    python3 scripts/spend.py assets/ap_spend.csv --fuzzy-threshold 0.85 --tail-share 0.2
"""
import argparse
import csv
import difflib
import io
import json
import math
import re
import sys
import unicodedata
from datetime import datetime

REQUIRED = ["supplier", "amount", "date", "account", "description"]
OPTIONAL = []
LEGAL_TOKENS = {"as", "aps", "ivs", "is", "ks", "ps", "gmbh", "ltd", "limited", "ab", "oy", "oyj", "bv",
                "ag", "nv", "sa", "sarl", "inc", "llc", "plc", "amba", "smba", "spa", "srl", "co", "kg"}
DEFAULT_CATEGORIES = {
    "Freight and logistics": ["fragt", "freight", "transport", "shipping", "forsendelse", "pakke", "parcel",
                              "kurer", "courier", "spedition", "logistik", "logistics", "postnord", "gls",
                              "dhl", "ups", "fedex", "bring"],
    "Packaging": ["emballage", "packaging", "karton", "carton", "papkasse", "box", "palle", "pallet",
                  "folie", "stretch", "tape"],
    "MRO, tools and fasteners": ["vaerktoj", "tool", "skrue", "screw", "bolt", "befaestelse", "fastener",
                                 "el materiale", "elmateriel", "electrical", "reservedel", "spare part",
                                 "vedligehold", "maintenance"],
    "Office supplies": ["kontor", "office", "toner", "papir", "paper", "printer"],
    "Cleaning and facilities": ["rengoring", "cleaning", "facility", "facilities", "kantine", "canteen",
                                "affald", "waste", "vagt", "security"],
    "IT and software": ["software", "licens", "licence", "license", "saas", "hosting", "cloud", "computer",
                        "laptop", "microsoft", "adobe"],
    "Professional services": ["konsulent", "consult", "advokat", "legal", "revision", "audit", "rekrutter",
                              "recruit"],
    "Energy and utilities": ["strom", "energi", "energy", "naturgas", "fjernvarme", "vand", "water"],
    "Marketing and print": ["marketing", "reklame", "annonce", "advertis", "tryksag", "print"],
    "Travel": ["rejse", "travel", "hotel", "flybillet", "flight", "taxi"],
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


# ---------------------------------------------------------------- text normalisation
def fold(text):
    t = (text or "").lower().replace("æ", "ae").replace("ø", "o").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t)
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def clean_text(text):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", fold(text)).split())


def supplier_key(name, strip_words):
    t = fold(name)
    t = re.sub(r"(?<![a-z])[aikp]\s*/\s*s(?![a-z])", " ", t)
    t = re.sub(r"(?<![a-z])s\.?\s*a\.?\s*r\.?\s*l\.?(?![a-z])", " ", t)
    t = re.sub(r"(?<![a-z])a\.?\s*m\.?\s*b\.?\s*a\.?(?![a-z])", " ", t)
    tokens = re.sub(r"[^a-z0-9]+", " ", t).split()
    kept = [w for w in tokens if w not in LEGAL_TOKENS and w not in strip_words]
    return " ".join(kept) or " ".join(tokens)


def kw_match(keyword, text):
    return re.search(r"(?<![a-z0-9])" + re.escape(keyword), text) is not None


# ---------------------------------------------------------------- core logic
def group_suppliers(spend_by_raw, strip_words, threshold, review_low):
    key_spend, key_names = {}, {}
    for raw, amt in spend_by_raw.items():
        k = supplier_key(raw, strip_words)
        key_spend[k] = key_spend.get(k, 0.0) + amt
        key_names.setdefault(k, []).append(raw)
    groups, key_to_group, merges = [], {}, []
    for k in sorted(key_spend, key=lambda x: (-key_spend[x], x)):
        best, best_ratio = None, 0.0
        for g in groups:
            r = difflib.SequenceMatcher(None, k, g).ratio()
            if r > best_ratio:
                best, best_ratio = g, r
        if best is not None and best_ratio >= threshold:
            key_to_group[k] = best
            merges.append({"from": k, "into": best, "ratio": best_ratio, "how": "fuzzy"})
        else:
            groups.append(k)
            key_to_group[k] = k
    raw_to_group = {}
    for k, names in key_names.items():
        for n in names:
            raw_to_group[n] = key_to_group[k]
    # display names: highest-spend raw variant per group
    members = {}
    for raw, g in raw_to_group.items():
        members.setdefault(g, []).append(raw)
    display = {g: sorted(v, key=lambda n: (-spend_by_raw[n], n))[0] for g, v in members.items()}
    for g, v in members.items():
        if len(v) > 1:
            merges.append({"group": display[g], "variants": sorted(v), "how": "same key or fuzzy"})
    review = []
    gl = sorted(groups)
    for i, a in enumerate(gl):
        for b in gl[i + 1:]:
            ta, tb = set(a.split()), set(b.split())
            r = difflib.SequenceMatcher(None, a, b).ratio()
            if (ta <= tb or tb <= ta) or r >= review_low:
                review.append({"a": display[a], "b": display[b], "ratio": r,
                               "why": "words contained" if (ta <= tb or tb <= ta) else "similar spelling"})
    return raw_to_group, display, merges, review


def categorise(desc, supplier, account, cats, accounts):
    if account and account in accounts:
        return accounts[account], "account %s" % account
    d = clean_text(desc)
    for cat, kws in cats.items():
        for kw in kws:
            if kw_match(kw, d):
                return cat, "'%s' in description" % kw
    s = clean_text(supplier)
    for cat, kws in cats.items():
        for kw in kws:
            if kw_match(kw, s):
                return cat, "'%s' in supplier" % kw
    return None, None


def compute(records, categories=None, accounts=None, strip_words=("danmark", "denmark", "dk"),
            fuzzy_threshold=0.85, review_ratio=0.7, tail_share=0.2, frag_min_suppliers=3,
            consolidation=(5.0, 10.0), tail=(5.0, 15.0)):
    warnings = []
    cats = {k: [clean_text(w) for w in v] for k, v in (categories or DEFAULT_CATEGORIES).items()}
    accounts = accounts or {}
    rows, seen, dupes = [], {}, []
    for ln, r in records:
        sup = r["supplier"] or "(blank supplier)"
        if not r["supplier"]:
            warnings.append("Line %d: blank supplier, grouped as '(blank supplier)'." % ln)
        try:
            amt = parse_number(r["amount"])
        except ValueError as exc:
            warnings.append("Line %d (%s): %s, row skipped." % (ln, sup, exc))
            continue
        if amt is None:
            warnings.append("Line %d (%s): missing amount, row skipped." % (ln, sup))
            continue
        d = None
        if r["date"]:
            try:
                d = parse_date(r["date"])
            except ValueError as exc:
                warnings.append("Line %d (%s): %s, kept without date." % (ln, sup, exc))
        if amt < 0:
            warnings.append("Line %d (%s): negative amount %s (credit note), netted against the supplier."
                            % (ln, sup, fmt(amt)))
        sig = (sup.lower(), round(amt, 2), r["date"], r["description"].lower())
        if sig in seen:
            dupes.append("lines %d and %d: %s %s on %s" % (seen[sig], ln, sup, fmt(amt, 2), r["date"]))
        else:
            seen[sig] = ln
        rows.append({"line": ln, "supplier_raw": sup, "amount": amt, "date": d, "account": r["account"],
                     "description": r["description"]})
    if not rows:
        raise InputError("No usable rows.")
    for d in dupes:
        warnings.append("Possible duplicate payment (%s); kept in totals, check before acting." % d)
    by_raw = {}
    for r in rows:
        by_raw[r["supplier_raw"]] = by_raw.get(r["supplier_raw"], 0.0) + r["amount"]
    raw_to_group, display, merges, review = group_suppliers(by_raw, set(strip_words), fuzzy_threshold, review_ratio)
    for r in rows:
        r["supplier"] = display[raw_to_group[r["supplier_raw"]]]
        r["category"], r["rule"] = categorise(r["description"], r["supplier_raw"], r["account"], cats, accounts)
    # fall back to the supplier's main category
    main_cat = {}
    for r in rows:
        if r["category"]:
            main_cat.setdefault(r["supplier"], {})
            main_cat[r["supplier"]][r["category"]] = main_cat[r["supplier"]].get(r["category"], 0.0) + abs(r["amount"])
    for r in rows:
        if not r["category"]:
            if r["supplier"] in main_cat:
                r["category"] = max(sorted(main_cat[r["supplier"]].items()), key=lambda kv: kv[1])[0]
                r["rule"] = "supplier's main category"
            else:
                r["category"], r["rule"] = "Uncategorised", "no rule matched"
    total = sum(r["amount"] for r in rows)
    sup_spend, cat_spend, cat_sups = {}, {}, {}
    for r in rows:
        sup_spend[r["supplier"]] = sup_spend.get(r["supplier"], 0.0) + r["amount"]
        cat_spend[r["category"]] = cat_spend.get(r["category"], 0.0) + r["amount"]
        cat_sups.setdefault(r["category"], {})
        cat_sups[r["category"]][r["supplier"]] = cat_sups[r["category"]].get(r["supplier"], 0.0) + r["amount"]
    for s, v in sup_spend.items():
        if v < 0:
            warnings.append("Supplier %s has net negative spend %s; check credit notes." % (s, fmt(v)))
    suppliers, cum = [], 0.0
    for s, v in sorted(sup_spend.items(), key=lambda kv: (-kv[1], kv[0])):
        share = v / total if total else 0.0
        before = cum
        cum += share
        suppliers.append({"supplier": s, "spend": v, "share": share, "cum_share": cum,
                          "tail": before >= 1 - tail_share - 1e-9})
    n80 = next((i + 1 for i, s in enumerate(suppliers) if s["cum_share"] >= 0.8 - 1e-9), len(suppliers))
    categories_out = []
    for c, v in sorted(cat_spend.items(), key=lambda kv: (-kv[1], kv[0])):
        sups = sorted(cat_sups[c].items(), key=lambda kv: (-kv[1], kv[0]))
        categories_out.append({"category": c, "spend": v, "share": v / total if total else 0.0,
                               "suppliers": len(sups), "top_supplier": sups[0][0],
                               "top_supplier_share": sups[0][1] / v if v else 0.0,
                               "supplier_list": [s for s, _ in sups],
                               "fragmented": len(sups) >= frag_min_suppliers and c != "Uncategorised"})
    frag = [c for c in categories_out if c["fragmented"]]
    frag_names = {c["category"] for c in frag}
    tail_sups = [s for s in suppliers if s["tail"]]
    tail_spend = sum(s["spend"] for s in tail_sups)
    tail_outside = 0.0
    for r in rows:
        if r["category"] not in frag_names and any(t["supplier"] == r["supplier"] for t in tail_sups):
            tail_outside += r["amount"]
    opps = []
    for c in frag:
        opps.append({"opportunity": "Consolidate %s (%d suppliers, top %s at %s)"
                     % (c["category"], c["suppliers"], c["top_supplier"], pct(c["top_supplier_share"], 0)),
                     "base": c["spend"], "low": c["spend"] * consolidation[0] / 100,
                     "high": c["spend"] * consolidation[1] / 100,
                     "assumption": "%s-%s %% from consolidation or re-tender" % (fmt(consolidation[0], 0),
                                                                              fmt(consolidation[1], 0))})
    if tail_outside > 0:
        opps.append({"opportunity": "Tail spend outside fragmented categories (%d tail suppliers in total)"
                     % len(tail_sups), "base": tail_outside, "low": tail_outside * tail[0] / 100,
                     "high": tail_outside * tail[1] / 100,
                     "assumption": "%s-%s %% via catalogue, preferred suppliers or p-card" % (
                         fmt(tail[0], 0), fmt(tail[1], 0))})
    uncategorised = cat_spend.get("Uncategorised", 0.0)
    dates = [r["date"] for r in rows if r["date"]]
    return {"parameters": {"fuzzy_threshold": fuzzy_threshold, "review_ratio": review_ratio,
                           "tail_share": tail_share, "frag_min_suppliers": frag_min_suppliers,
                           "consolidation_pct": list(consolidation), "tail_pct": list(tail),
                           "strip_words": list(strip_words)},
            "total": total, "lines": len(rows), "raw_suppliers": len(by_raw), "suppliers_after": len(suppliers),
            "date_from": min(dates).isoformat() if dates else None,
            "date_to": max(dates).isoformat() if dates else None,
            "merges": merges, "review_pairs": review, "suppliers": suppliers, "suppliers_for_80pct": n80,
            "categories": categories_out, "tail": {"suppliers": len(tail_sups), "spend": tail_spend,
                                                  "share": tail_spend / total if total else 0.0},
            "opportunities": opps, "savings_low": sum(o["low"] for o in opps),
            "savings_high": sum(o["high"] for o in opps), "uncategorised": uncategorised,
            "rules": sorted({(r["category"], r["rule"]) for r in rows}), "rows": rows, "warnings": warnings}


def render(res):
    p = res["parameters"]
    out = ["# Spend analysis", ""]
    out.append("**Total spend %s on %d lines, %s to %s. %d supplier names grouped into %d suppliers; "
               "%d suppliers make up 80 %% of spend.**"
               % (fmt(res["total"]), res["lines"], res["date_from"] or "-", res["date_to"] or "-",
                  res["raw_suppliers"], res["suppliers_after"], res["suppliers_for_80pct"]))
    out += ["", "## 1. Spend overview", "", "### Supplier normalisation", ""]
    groups = [m for m in res["merges"] if "variants" in m]
    if groups:
        for m in groups:
            out.append("- Grouped as **%s**: %s" % (m["group"], "; ".join(m["variants"])))
    fuzzy = [m for m in res["merges"] if m.get("how") == "fuzzy"]
    for m in fuzzy:
        out.append("- Fuzzy merge: '%s' into '%s' (similarity %s)" % (m["from"], m["into"], fmt(m["ratio"], 2)))
    if not groups:
        out.append("- No names merged.")
    if res["review_pairs"]:
        out.append("- Not merged, please confirm: " + "; ".join(
            "%s / %s (%s, %s)" % (r["a"], r["b"], r["why"], fmt(r["ratio"], 2)) for r in res["review_pairs"]))
    out += ["", "### Supplier Pareto", ""]
    out.append(md_table(["Supplier", "Spend", "Share", "Cumulative", "Tail"],
                        [[s["supplier"], fmt(s["spend"]), pct(s["share"]), pct(s["cum_share"]),
                          "yes" if s["tail"] else ""] for s in res["suppliers"]]))
    t = res["tail"]
    out.append("")
    out.append("Tail spend (suppliers in the last %s of spend): %d suppliers, %s (%s)."
               % (pct(p["tail_share"], 0), t["suppliers"], fmt(t["spend"]), pct(t["share"])))
    out += ["", "## 2. Category breakdown", ""]
    out.append(md_table(["Category", "Spend", "Share", "Suppliers", "Top supplier (share)", "Fragmented"],
                        [[c["category"], fmt(c["spend"]), pct(c["share"]), c["suppliers"],
                          "%s (%s)" % (c["top_supplier"], pct(c["top_supplier_share"], 0)),
                          "yes" if c["fragmented"] else ""] for c in res["categories"]]))
    out += ["", "Categorisation rules applied:", ""]
    out += ["- %s: %s" % (c, r) for c, r in res["rules"]]
    out += ["", "## 3. Opportunities with estimated savings (ESTIMATE, not validated with suppliers)", ""]
    if res["opportunities"]:
        out.append(md_table(["Opportunity", "Spend base", "Low", "High", "Assumption"],
                            [[o["opportunity"], fmt(o["base"]), fmt(o["low"]), fmt(o["high"]), o["assumption"]]
                             for o in res["opportunities"]] +
                            [["**Total estimate range**", "", "**%s**" % fmt(res["savings_low"]),
                              "**%s**" % fmt(res["savings_high"]), "before implementation cost"]]))
        out.append("")
        out.append("Estimated range: %s to %s a year on this extract (%s to %s of spend). These are planning "
                   "estimates from the percentages above, not promises."
                   % (fmt(res["savings_low"]), fmt(res["savings_high"]),
                      pct(res["savings_low"] / res["total"]) if res["total"] else "-",
                      pct(res["savings_high"] / res["total"]) if res["total"] else "-"))
    else:
        out.append("- No fragmented categories or tail spend found with the current thresholds.")
    out += ["", "## 4. Next steps", "",
            "- Confirm the supplier groupings and the pairs listed for review",
            "- Categorise the uncategorised spend (%s) with a --categories JSON or account map" % fmt(res["uncategorised"]),
            "- Check possible duplicate payments and credit notes listed below",
            "- Validate the savings percentages with contract and price data before quoting a number"]
    if res["warnings"]:
        out += ["", "## Data-quality warnings", ""] + ["- " + w for w in res["warnings"]]
    return "\n".join(out) + "\n"


def write_csv(res, path):
    cols = ["line", "supplier_raw", "supplier", "category", "rule", "amount", "date", "account", "description"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in res["rows"]:
            w.writerow([r[c].isoformat() if hasattr(r[c], "isoformat") else r[c] for c in cols])


def load_categories(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise InputError("Cannot read categories JSON %s: %s" % (path, exc))
    accounts = {str(k): v for k, v in (data.pop("_accounts", {}) or {}).items()}
    if not all(isinstance(v, list) for v in data.values()):
        raise InputError('Categories JSON must look like {"Category": ["keyword", ...], "_accounts": {"6110": "Office"}}')
    return data, accounts


def build_parser():
    ap = argparse.ArgumentParser(description="Spend analysis with supplier normalisation and savings ranges. "
                                 "Input columns: " + ", ".join(REQUIRED) + ".")
    ap.add_argument("csv", help="AP extract CSV")
    ap.add_argument("--categories", help='JSON keyword map {"Category": ["kw", ...], "_accounts": {"6110": "Office"}}; '
                                         "default: built-in Danish/English map")
    ap.add_argument("--strip-words", default="danmark,denmark,dk",
                    help="comma-separated words removed from supplier names before matching (default danmark,denmark,dk)")
    ap.add_argument("--fuzzy-threshold", type=float, default=0.85,
                    help="difflib similarity at or above which supplier names are merged (default 0.85)")
    ap.add_argument("--review-ratio", type=float, default=0.7,
                    help="similarity at or above which unmerged pairs are listed for review (default 0.7)")
    ap.add_argument("--tail-share", type=float, default=0.2, help="share of spend treated as tail (default 0.2)")
    ap.add_argument("--frag-min-suppliers", type=int, default=3,
                    help="suppliers in a category that make it fragmented (default 3)")
    ap.add_argument("--consolidation-low", type=float, default=5.0, help="consolidation savings low %% (default 5)")
    ap.add_argument("--consolidation-high", type=float, default=10.0, help="consolidation savings high %% (default 10)")
    ap.add_argument("--tail-low", type=float, default=5.0, help="tail-spend savings low %% (default 5)")
    ap.add_argument("--tail-high", type=float, default=15.0, help="tail-spend savings high %% (default 15)")
    ap.add_argument("--out", help="write categorised lines as CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.consolidation_low > args.consolidation_high or args.tail_low > args.tail_high:
            raise InputError("low savings % must not exceed high savings %")
        if not 0 < args.tail_share < 1 or not 0 < args.fuzzy_threshold <= 1:
            raise InputError("--tail-share must be between 0 and 1 and --fuzzy-threshold between 0 and 1")
        cats, accounts = load_categories(args.categories) if args.categories else (None, None)
        strip = tuple(w.strip().lower() for w in args.strip_words.split(",") if w.strip())
        res = compute(read_table(args.csv, REQUIRED, OPTIONAL), cats, accounts, strip, args.fuzzy_threshold,
                      args.review_ratio, args.tail_share, args.frag_min_suppliers,
                      (args.consolidation_low, args.consolidation_high), (args.tail_low, args.tail_high))
    except InputError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 2
    if args.out:
        write_csv(res, args.out)
    print(json.dumps(clean_json(res), indent=2, default=str) if args.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
