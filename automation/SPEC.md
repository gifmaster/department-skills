# Automation unit spec (v1.1)

An automation unit upgrades one skill with deterministic tooling so the AI calculates instead of guessing.
Folder: automation/<skill-name>/  (skill-name exactly as in departments/*/skills/<skill-name>)

Required files:
- scripts/<tool>.py
  * Python 3.9+, STANDARD LIBRARY ONLY (csv, json, argparse, datetime, math, statistics, re, difflib). No pandas/numpy.
  * CLI with argparse and --help. Reads CSV (UTF-8, comma OR semicolon delimiter auto-detected; accept Danish number format "1.234,56" and plain "1234.56"; dates ISO yyyy-mm-dd and dd-mm-yyyy).
  * Prints a concise Markdown report to stdout (tables + headline numbers + warnings about data quality).
  * Optional --out <path> writes the detailed results as CSV. Optional --json prints machine-readable JSON instead of Markdown.
  * Deterministic. Clear error messages for missing columns (list the expected columns).
  * Every policy number that can change (rates, fees, thresholds, holidays) is a CLI parameter with a sensible documented default, never silently hard-coded. Where a legal figure is a default, the --help text says "verify current value".
  * Top docstring: purpose, input columns, formulas used, example command.
- assets/<template>.csv : the input template with the exact header row plus 6 to 20 realistic sample rows (fictional Danish SME data). Include at least one data-quality problem the script detects (duplicate, missing value, sign error, etc.).
- tests/test_<tool>.py : unittest. Runs the script logic on the sample asset and on small hand-built cases; asserts numbers you computed by hand. Must pass with: python3 -m unittest discover -s automation/<skill-name>/tests
- examples/worked-example.md : a realistic user request, the exact command run on the sample asset, the real output (paste it, do not invent), and a 3 to 6 line interpretation as the assistant would give it.
- method.md : MAX 1,000 characters. Plain-text formulas and decision rules so a model WITHOUT code execution can do the same by hand. No headings, just short bullets. British English.
- unit.yaml :
    skill: <skill-name>
    script: scripts/<tool>.py
    template: assets/<template>.csv
    command: python3 scripts/<tool>.py assets/<template>.csv   # the canonical example command, relative to the skill folder
    summary: one sentence on what the script does

Rules: British English, no em or en dashes anywhere (use hyphens or commas). Do not edit anything outside automation/<skill-name>/. Do not edit catalogue/ or departments/. Run your tests and the example command before finishing. Final message: list units built, test results, and any formula decision the reviewer should know about (under 150 words).
