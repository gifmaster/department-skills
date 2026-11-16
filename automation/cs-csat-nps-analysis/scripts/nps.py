#!/usr/bin/env python3
"""NPS or CSAT survey analysis with margins of error, segment tests and comment themes.

Purpose
  Reads survey responses, detects whether scores are NPS (0-10) or CSAT (1-5), and reports the
  score with a 95% interval, results per period and per segment (only where n is large enough),
  whether segment differences are statistically meaningful, and simple keyword theme counts from
  comments (built-in English and Danish keyword map, replaceable with --themes JSON {theme: [keywords]};
  keywords match whole words, a trailing * allows any ending). Standard library only.

Input columns (CSV, comma or semicolon, header names case-insensitive)
  response_id, date, score            required
  segment, comment                    optional

Formulas
  NPS: promoters 9-10, passives 7-8, detractors 0-6. NPS = 100 x (P - D) / n.
       Each response scored +1 / 0 / -1. Variance = p + d - (p - d)^2 (p, d = shares).
       Margin of error = z x sqrt(variance / n) x 100 (z = 1.96 for 95%).
  CSAT: % satisfied = share of scores >= threshold (default 4 on 1-5).
       Wilson interval: (p + z^2/2n +/- z sqrt(p(1-p)/n + z^2/4n^2)) / (1 + z^2/n).
  Segment vs rest of sample: NPS z = diff / sqrt(var1/n1 + var2/n2); CSAT pooled two-proportion
  z-test. |z| < 1.96 is reported as "not statistically meaningful". Segments with n below
  --min-n (default 30) are listed but not scored or compared.

Example
  python3 scripts/nps.py assets/responses_template.csv --min-n 5
  python3 scripts/nps.py responses.csv --period quarter --themes my_themes.json --out themes.csv
"""
import argparse
import csv
import io
import json
import math
import re
from datetime import datetime

REQUIRED = ["response_id", "date", "score"]
OPTIONAL = ["segment", "comment"]

# Keywords match whole words; a trailing * allows any ending ("vent*" matches "ventede", "ventetid").
DEFAULT_THEMES = {
    "waiting and response time": ["wait*", "slow*", "days", "weeks", "no answer", "no reply", "took ages",
                                  "vent*", "langsom*", "lang tid", "dage", "uger", "intet svar", "svarer ikke"],
    "issue not resolved": ["not solved", "not resolved", "unresolved", "still not", "write again", "call again",
                           "had to call", "ikke løst", "stadig ikke", "skrive igen", "ringe igen", "måtte ringe"],
    "staff attitude": ["rude", "unfriendly", "friendly", "helpful", "polite", "nice",
                       "uhøflig*", "uvenlig*", "venlig*", "hjælpsom*", "sød", "flink*", "imødekommende"],
    "price and billing": ["price*", "bill", "bills", "billing", "invoice*", "charge*", "expensive", "refund*", "fee*",
                          "pris*", "regning*", "faktura*", "dyr", "dyrt", "gebyr*", "aconto", "betaling*", "refusion"],
    "delivery": ["deliver*", "shipping", "parcel*", "package*", "late", "courier",
                 "lever*", "pakke*", "fragt*", "forsink*", "kurér*"],
    "product quality": ["broken", "defect*", "quality", "faulty", "damaged",
                        "i stykker", "defekt*", "kvalitet*", "ødelagt*"],
    "chatbot and self-service": ["bot", "bots", "chatbot*", "app", "apps", "website", "login", "log in", "logs me out",
                                 "hjemmeside*", "log ind", "logger mig ud", "selvbetjening*"],
    "clarity of information": ["unclear", "confusing", "understand*", "explain*", "makes no sense",
                               "uklar*", "forvirrende", "forstå*", "forklar*", "giver ingen mening"],
}


# ---------------------------------------------------------------- helpers
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
    return headers, rows


def check_columns(headers, required):
    missing = [c for c in required if c not in headers]
    if missing:
        raise SystemExit("Missing column(s): %s. Expected columns: %s (optional: %s). Found: %s"
                         % (", ".join(missing), ", ".join(required), ", ".join(OPTIONAL), ", ".join(headers) or "(none)"))


def parse_date(s):
    s = s.strip().split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("unrecognised date '%s'" % s)


def parse_number(s):
    s = s.strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


# ---------------------------------------------------------------- statistics
def nps_stats(scores, z=1.96):
    n = len(scores)
    if n == 0:
        return None
    pro = sum(1 for s in scores if s >= 9)
    det = sum(1 for s in scores if s <= 6)
    pas = n - pro - det
    p, d = pro / n, det / n
    var = p + d - (p - d) ** 2
    return {"n": n, "promoters": pro, "passives": pas, "detractors": det,
            "promoter_pct": 100 * p, "passive_pct": 100 * pas / n, "detractor_pct": 100 * d,
            "score": 100 * (p - d), "variance": var, "moe": z * math.sqrt(var / n) * 100}


def wilson(k, n, z=1.96):
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return 100 * (centre - half), 100 * (centre + half)


def csat_stats(scores, threshold=4, z=1.96):
    n = len(scores)
    if n == 0:
        return None
    k = sum(1 for s in scores if s >= threshold)
    lo, hi = wilson(k, n, z)
    return {"n": n, "satisfied": k, "score": 100 * k / n, "ci_low": lo, "ci_high": hi,
            "mean": sum(scores) / n,
            "distribution": {str(v): sum(1 for s in scores if s == v) for v in range(1, 6)}}


def compare(a, b, kind, z=1.96):
    """Return (difference in points, z value, meaningful bool)."""
    if kind == "nps":
        se = math.sqrt(a["variance"] / a["n"] + b["variance"] / b["n"]) * 100
        diff = a["score"] - b["score"]
    else:
        p1, p2 = a["satisfied"] / a["n"], b["satisfied"] / b["n"]
        pool = (a["satisfied"] + b["satisfied"]) / (a["n"] + b["n"])
        se = math.sqrt(pool * (1 - pool) * (1 / a["n"] + 1 / b["n"])) * 100
        diff = 100 * (p1 - p2)
    if se == 0:
        return diff, None, diff != 0
    zval = diff / se
    return diff, zval, abs(zval) >= z


def detect_scale(scores):
    if any(s == 0 or s > 5 for s in scores):
        return "nps"
    return "csat"


def theme_patterns(themes):
    pats = {}
    for theme, kws in themes.items():
        alts = sorted({k.strip().lower() for k in kws if k.strip()}, key=len, reverse=True)
        parts = [re.escape(k[:-1]) + r"\w*" if k.endswith("*") else re.escape(k) + r"(?!\w)" for k in alts]
        pats[theme] = re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")", re.IGNORECASE)
    return pats


def group_of(score, kind, threshold):
    if kind == "nps":
        return "promoter" if score >= 9 else "detractor" if score <= 6 else "passive"
    return "satisfied" if score >= threshold else "dissatisfied" if score <= 2 else "neutral"


# ---------------------------------------------------------------- analysis
def analyse(rows, scale="auto", min_n=30, threshold=4, z=1.96, period="month", themes=None):
    warnings = []
    seen = set()
    data = []
    for line, r in rows:
        rid = r.get("response_id", "")
        if not rid:
            warnings.append("Line %d: missing response_id, row skipped" % line)
            continue
        if rid in seen:
            warnings.append("Line %d: duplicate response_id %s, later row ignored" % (line, rid))
            continue
        seen.add(rid)
        try:
            score = parse_number(r["score"])
        except ValueError:
            score = "bad"
        if score is None or score == "bad":
            warnings.append("Line %d (%s): score missing or not a number ('%s'), row skipped" % (line, rid, r["score"]))
            continue
        if score != int(score):
            warnings.append("Line %d (%s): score %s is not a whole number, row skipped" % (line, rid, r["score"]))
            continue
        try:
            d = parse_date(r["date"]) if r["date"] else None
        except ValueError as exc:
            d = None
            warnings.append("Line %d (%s): %s, kept without date" % (line, rid, exc))
        if d is None and not r["date"]:
            warnings.append("Line %d (%s): date missing, kept without date" % (line, rid))
        data.append({"id": rid, "date": d, "score": int(score), "segment": r.get("segment", "") or "",
                     "comment": r.get("comment", "") or ""})

    kind = detect_scale([x["score"] for x in data]) if scale == "auto" else scale
    lo_ok, hi_ok = (0, 10) if kind == "nps" else (1, 5)
    valid = []
    for x in data:
        if lo_ok <= x["score"] <= hi_ok:
            valid.append(x)
        else:
            warnings.append("Response %s: score %d outside %d-%d, excluded" % (x["id"], x["score"], lo_ok, hi_ok))
    if not valid:
        raise SystemExit("No valid scores found.")
    if scale == "auto" and kind == "csat" and len(valid) >= 20 and not any(s["score"] in (1, 2) for s in valid):
        warnings.append("Scale detected as CSAT 1-5 because no score is 0 or above 5. If this is NPS, pass --scale nps.")

    def stats(sc):
        return nps_stats(sc, z) if kind == "nps" else csat_stats(sc, threshold, z)

    overall = stats([x["score"] for x in valid])
    if overall["n"] < min_n:
        warnings.append("Total sample n=%d is below the minimum of %d: treat all figures as indicative." % (overall["n"], min_n))

    # periods
    periods = {}
    if period != "none":
        for x in valid:
            if x["date"] is None:
                key = "(no date)"
            elif period == "quarter":
                key = "%d-Q%d" % (x["date"].year, (x["date"].month - 1) // 3 + 1)
            else:
                key = x["date"].strftime("%Y-%m")
            periods.setdefault(key, []).append(x["score"])
    per = []
    for key in sorted(periods):
        s = stats(periods[key])
        s["period"] = key
        s["small_sample"] = s["n"] < min_n
        per.append(s)
    if len(per) >= 2:
        a, b = per[-1], per[-2]
        if a["n"] and b["n"]:
            diff, zval, ok = compare(a, b, kind, z)
            per_change = {"from": b["period"], "to": a["period"], "difference": diff, "z": zval, "meaningful": ok}
        else:
            per_change = None
    else:
        per_change = None

    # segments
    segs = []
    has_seg = any(x["segment"] for x in valid)
    if has_seg:
        names = sorted({x["segment"] or "(blank)" for x in valid})
        for name in names:
            own = [x["score"] for x in valid if (x["segment"] or "(blank)") == name]
            rest = [x["score"] for x in valid if (x["segment"] or "(blank)") != name]
            entry = {"segment": name, "n": len(own)}
            if len(own) < min_n:
                entry["status"] = "below minimum n (%d), not scored" % min_n
            else:
                s = stats(own)
                entry.update(s)
                if len(rest) >= min_n:
                    r = stats(rest)
                    diff, zval, ok = compare(s, r, kind, z)
                    entry.update({"vs_rest": diff, "z": zval, "meaningful": ok,
                                  "status": "difference vs rest is statistically meaningful" if ok
                                  else "difference vs rest is NOT statistically meaningful"})
                else:
                    entry["status"] = "rest of sample below minimum n, not compared"
            segs.append(entry)

    # themes
    pats = theme_patterns(themes or DEFAULT_THEMES)
    with_comment = [x for x in valid if x["comment"]]
    theme_rows = []
    matches = []
    for theme, pat in pats.items():
        hits = [x for x in with_comment if pat.search(x["comment"])]
        groups = {}
        for x in hits:
            g = group_of(x["score"], kind, threshold)
            groups[g] = groups.get(g, 0) + 1
        theme_rows.append({"theme": theme, "comments": len(hits),
                           "share_of_comments": 100 * len(hits) / len(with_comment) if with_comment else 0,
                           "avg_score": sum(x["score"] for x in hits) / len(hits) if hits else None,
                           "by_group": groups})
        for x in hits:
            matches.append({"response_id": x["id"], "score": x["score"], "theme": theme})
    theme_rows.sort(key=lambda t: (-t["comments"], t["theme"]))
    matched_ids = {m["response_id"] for m in matches}
    uncoded = [x["id"] for x in with_comment if x["id"] not in matched_ids]

    return {"scale": kind, "z": z, "min_n": min_n, "csat_threshold": threshold, "overall": overall,
            "periods": per, "period_change": per_change, "segments": segs,
            "comments": len(with_comment), "themes": theme_rows, "uncoded_comments": uncoded,
            "theme_matches": matches, "warnings": warnings}


# ---------------------------------------------------------------- output
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def f1(x):
    return "-" if x is None else "%.1f" % x


def markdown(rep):
    o = rep["overall"]
    nps = rep["scale"] == "nps"
    L = ["# %s analysis" % ("NPS" if nps else "CSAT"), ""]
    if nps:
        L += ["**NPS %s** (95%% margin of error +/- %s points, n=%d). Promoters %d (%.1f%%), passives %d (%.1f%%), "
              "detractors %d (%.1f%%)." % (f1(o["score"]), f1(o["moe"]), o["n"], o["promoters"], o["promoter_pct"],
                                         o["passives"], o["passive_pct"], o["detractors"], o["detractor_pct"])]
    else:
        L += ["**CSAT %s%% satisfied** (score %d or higher; 95%% Wilson interval %s%% to %s%%, n=%d). Mean score %.2f."
              % (f1(o["score"]), rep["csat_threshold"], f1(o["ci_low"]), f1(o["ci_high"]), o["n"], o["mean"])]
    L += ["", "## By period", ""]
    if rep["periods"]:
        if nps:
            rows = [[p["period"], p["n"], f1(p["score"]), "+/- " + f1(p["moe"]), p["promoters"], p["passives"],
                     p["detractors"], "yes" if p["small_sample"] else ""] for p in rep["periods"]]
            L.append(table(["Period", "n", "NPS", "MoE 95%", "Promoters", "Passives", "Detractors", "Small sample"], rows))
        else:
            rows = [[p["period"], p["n"], f1(p["score"]) + "%", "%s-%s%%" % (f1(p["ci_low"]), f1(p["ci_high"])),
                     "%.2f" % p["mean"], "yes" if p["small_sample"] else ""] for p in rep["periods"]]
            L.append(table(["Period", "n", "% satisfied", "95% interval", "Mean", "Small sample"], rows))
        c = rep["period_change"]
        if c:
            L += ["", "Change %s to %s: %+.1f points, %s (z=%s)." % (
                c["from"], c["to"], c["difference"],
                "statistically meaningful" if c["meaningful"] else "NOT statistically meaningful, may be noise",
                "-" if c["z"] is None else "%.2f" % c["z"])]
    else:
        L.append("No dates to group by.")
    L += ["", "## Segments (each compared with the rest of the sample)", ""]
    if rep["segments"]:
        rows = []
        for s in rep["segments"]:
            score = f1(s.get("score")) + ("" if nps or s.get("score") is None else "%")
            ci = ("+/- " + f1(s["moe"])) if nps and "moe" in s else ("%s-%s%%" % (f1(s["ci_low"]), f1(s["ci_high"]))
                                                                     if "ci_low" in s else "-")
            rows.append([s["segment"], s["n"], score, ci, "-" if "vs_rest" not in s else "%+.1f" % s["vs_rest"],
                         s["status"]])
        L.append(table(["Segment", "n", "NPS" if nps else "% satisfied", "95% interval", "vs rest", "Assessment"], rows))
    else:
        L.append("No segment column or no segment values.")
    L += ["", "## Comment themes (keyword match, %d comments)" % rep["comments"], ""]
    if rep["comments"]:
        rows = [[t["theme"], t["comments"], "%.0f%%" % t["share_of_comments"], f1(t["avg_score"]),
                 ", ".join("%s %d" % kv for kv in sorted(t["by_group"].items()))]
                for t in rep["themes"] if t["comments"]]
        L.append(table(["Theme", "Comments", "Share", "Avg score", "By group"], rows) if rows else "No theme matches.")
        if rep["uncoded_comments"]:
            L += ["", "Comments matching no theme (read manually): %s." % ", ".join(rep["uncoded_comments"])]
        L += ["", "A comment can match several themes. Keyword matching is a first pass, so read the comments before "
              "drawing conclusions."]
    else:
        L.append("No comments.")
    L += ["", "## Data quality warnings", ""]
    L += ["- " + w for w in rep["warnings"]] or ["- None found."]
    if nps:
        L += ["", "Method: NPS = %%promoters (9-10) - %%detractors (0-6). MoE = %.2f x sqrt((p + d - (p - d)^2) / n) x 100. "
              "Segments need n >= %d to be scored." % (rep["z"], rep["min_n"])]
    else:
        L += ["", "Method: %% satisfied = share of scores >= %d, Wilson interval at z=%.2f. Segments need n >= %d to be "
              "scored." % (rep["csat_threshold"], rep["z"], rep["min_n"])]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NPS (0-10) or CSAT (1-5) analysis with intervals, segment tests and "
                                             "comment themes.", epilog="Expected columns: response_id, date, score "
                                                                       "(optional: segment, comment)")
    ap.add_argument("csv", help="survey responses CSV")
    ap.add_argument("--scale", choices=["auto", "nps", "csat"], default="auto",
                    help="auto (default): NPS if any score is 0 or above 5, otherwise CSAT")
    ap.add_argument("--min-n", type=int, default=30, help="minimum responses to score a segment (default 30)")
    ap.add_argument("--csat-threshold", type=int, default=4, help="CSAT score counted as satisfied (default 4)")
    ap.add_argument("--z", type=float, default=1.96, help="z value for intervals and tests (default 1.96 = 95%%)")
    ap.add_argument("--period", choices=["month", "quarter", "none"], default="month", help="period grouping")
    ap.add_argument("--themes", help="JSON file {theme: [keywords]} that replaces the built-in keyword map")
    ap.add_argument("--out", help="write theme matches per response as CSV")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    a = ap.parse_args(argv)
    headers, rows = read_csv(a.csv)
    check_columns(headers, REQUIRED)
    themes = None
    if a.themes:
        try:
            with open(a.themes, encoding="utf-8") as fh:
                themes = json.load(fh)
        except (OSError, ValueError) as exc:
            raise SystemExit("Could not read --themes: %s" % exc)
    rep = analyse(rows, a.scale, a.min_n, a.csat_threshold, a.z, a.period, themes)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["response_id", "score", "theme"])
            for m in rep["theme_matches"]:
                w.writerow([m["response_id"], m["score"], m["theme"]])
    if a.json:
        out = dict(rep)
        print(json.dumps(out, indent=2, default=str, ensure_ascii=False))
    else:
        print(markdown(rep))


if __name__ == "__main__":
    main()
