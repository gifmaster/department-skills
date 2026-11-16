#!/usr/bin/env python3
"""Validate every generated skill against the Agent Skills spec and the house rules.

Checks:
  - SKILL.md has YAML frontmatter with name and description
  - name: lowercase letters, digits and hyphens, max 64 chars, matches folder, unique, no reserved words
  - description: 1 to 1024 chars, no angle brackets
  - PROMPT.md paste section fits the 8,000 character limit of custom GPTs, Gems and Microsoft 365 Copilot agents
  - SKILL.md body is under 500 lines
  - no em dashes or en dashes anywhere (house style)
  - no common American spellings (house style is British English)
  - each catalogue has exactly 21 skills
Exit code 1 on any failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PASTE_MARKER = "<!-- PASTE BELOW THIS LINE -->"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
AMERICAN = [
    "organization", "organize", "analyze", "analyzing", "optimize", "optimization", "prioritize", "prioritizing",
    "summarize", "standardize", "recognize", "behavior", "color", "favor", "labor", "center",
    "defense", "judgment", "modeling", "traveling", "enrollment", "fulfill ", "specialize", "minimize", "maximize", "categorize", "utilize", "customize", "emphasize", "apologize",
]
ALLOW = {}


def main():
    errors = []
    names = {}
    for cat in sorted((ROOT / "catalogue").glob("*.yaml")):
        d = yaml.safe_load(cat.read_text(encoding="utf-8"))
        if len(d["skills"]) != 21:
            errors.append(f"{cat.name}: has {len(d['skills'])} skills, expected 21")
        ids = [s["id"] for s in d["skills"]]
        if len(ids) != len(set(ids)):
            errors.append(f"{cat.name}: duplicate ids")
        for w in d.get("workflows", []):
            for ref in w["skills"]:
                if ref not in ids:
                    errors.append(f"{cat.name}: workflow '{w['name']}' references unknown skill '{ref}'")

    skill_files = sorted((ROOT / "departments").glob("*/skills/*/SKILL.md"))
    for f in skill_files:
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            errors.append(f"{f}: missing frontmatter")
            continue
        fm = yaml.safe_load(m.group(1))
        name, desc = fm.get("name", ""), fm.get("description", "")
        folder = f.parent.name
        if not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{f}: invalid name '{name}'")
        if name != folder:
            errors.append(f"{f}: name '{name}' does not match folder '{folder}'")
        if "claude" in name or "anthropic" in name:
            errors.append(f"{f}: reserved word in name")
        if name in names:
            errors.append(f"{f}: duplicate name also in {names[name]}")
        names[name] = f
        if not 1 <= len(desc) <= 1024:
            errors.append(f"{f}: description length {len(desc)}")
        if "<" in desc or ">" in desc:
            errors.append(f"{f}: angle bracket in description")
        if text.count("\n") > 500:
            errors.append(f"{f}: over 500 lines")
        p = f.parent / "PROMPT.md"
        if not p.exists():
            errors.append(f"{p}: missing")
        else:
            ptext = p.read_text(encoding="utf-8")
            if PASTE_MARKER not in ptext:
                errors.append(f"{p}: no paste marker")
            else:
                paste = ptext.split(PASTE_MARKER, 1)[1].strip()
                if len(paste) > 8000:
                    errors.append(f"{p}: paste section is {len(paste)} chars (limit 8000)")

    ref_re = re.compile(r"\b(?:hr|fin|scm|legal|sales|mkt|it|cs)-[a-z0-9]+(?:-[a-z0-9]+)+\b")
    for f in skill_files:
        for ref in set(ref_re.findall(f.read_text(encoding="utf-8"))):
            if ref not in names and not ref.startswith(("it-university", "legal-advice")):
                errors.append(f"{f.relative_to(ROOT)}: references unknown skill '{ref}'")

    for f in list(ROOT.rglob("*.md")) + list(ROOT.rglob("*.yaml")) + list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.sh")) + list(ROOT.rglob("*.ps1")) + list(ROOT.rglob("*.json")):
        if ".git" in f.parts or "dist" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        if chr(0x2014) in text or chr(0x2013) in text:
            errors.append(f"{f.relative_to(ROOT)}: contains an em or en dash")
        low = text.lower()
        for w in AMERICAN:
            if f.name != "validate.py" and f.name not in ALLOW.get(w, []) and re.search(r"\b" + re.escape(w.strip()) + r"\b", low):
                errors.append(f"{f.relative_to(ROOT)}: American spelling '{w.strip()}'")

    if errors:
        print("\n".join(errors))
        print(f"\nFAILED: {len(errors)} problem(s)")
        sys.exit(1)
    print(f"OK: {len(skill_files)} skills valid")


if __name__ == "__main__":
    main()
