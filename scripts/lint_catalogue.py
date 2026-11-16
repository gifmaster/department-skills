#!/usr/bin/env python3
"""Catch YAML flow-list mistakes: items split on commas leave unbalanced brackets or stray fragments."""
import sys
from pathlib import Path
import yaml
bad = 0
for f in sorted(Path(__file__).resolve().parent.parent.joinpath("catalogue").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    for s in d["skills"]:
        for k, v in s.items():
            items = v if isinstance(v, list) else [v]
            for i in items:
                if not isinstance(i, str):
                    print(f"{f.name}:{s['id']}:{k}: non-string {i!r}"); bad += 1; continue
                if i.count("(") != i.count(")") or i.count("[") != i.count("]"):
                    print(f"{f.name}:{s['id']}:{k}: unbalanced: {i!r}"); bad += 1
sys.exit(1 if bad else 0)
