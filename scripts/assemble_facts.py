#!/usr/bin/env python3
"""Assemble facts/<department>.md from facts/_parts/ (header + department part + shared AI Act part).

Edit the parts, never the assembled files. build.py runs this automatically.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "facts" / "_parts"
TITLES = {"hr": "Human Resources", "finance": "Finance", "supply-chain": "Supply Chain", "legal": "Legal",
          "sales": "Sales", "marketing": "Marketing", "it": "IT", "customer-service": "Customer Service"}
WITH_AI_ACT = {"hr", "legal", "it", "customer-service", "marketing", "sales"}


def main():
    hdr = (P / "header.md").read_text(encoding="utf-8")
    ai = (P / "ai-act.md").read_text(encoding="utf-8")
    for key, title in TITLES.items():
        body = (P / f"{key}.md").read_text(encoding="utf-8")
        out = hdr.replace("{TITLE}", title) + "\n" + body + ("\n" + ai if key in WITH_AI_ACT else "")
        (ROOT / "facts" / f"{key}.md").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
