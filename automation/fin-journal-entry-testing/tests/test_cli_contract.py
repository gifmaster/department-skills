"""CLI contract tests: --json on the canonical template is strict JSON, and --help documents every option.

The canonical command is read from unit.yaml. Legal or policy figures listed in LEGAL_FLAGS must
say "verify current value" in their --help text.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
LEGAL_FLAGS = ['--extra-holidays']


def canonical_command():
    with open(os.path.join(UNIT, "unit.yaml"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("command:"):
                parts = shlex.split(line[len("command:"):], comments=True)
                return [sys.executable] + parts[1:]
    raise AssertionError("unit.yaml has no command line")


def run(args):
    return subprocess.run(args, cwd=UNIT, capture_output=True, text=True, encoding="utf-8")


def reject_constant(name):
    raise ValueError("non-standard JSON constant %s" % name)


def help_blocks(text):
    """Map each option string to its help block (whitespace collapsed)."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().lower() in ("options:", "optional arguments:"))
    blocks, cur = [], []
    for ln in lines[start + 1:]:
        if re.match(r"^  -", ln):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif ln.startswith("   ") and cur:
            cur.append(ln)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    out = {}
    for b in blocks:
        first = b[0].strip()
        has_help = len(b) > 1 or re.search(r"\S\s{2,}\S", first) is not None
        for f in re.findall(r"(?:^|[\s,])(--?[A-Za-z][\w-]*)", first):
            out[f] = (" ".join(x.strip() for x in b), has_help)
    return out


class TestCliContract(unittest.TestCase):
    def test_json_output_is_strict_json(self):
        res = run(canonical_command() + ["--json"])
        self.assertEqual(res.returncode, 0, res.stderr)
        data = json.loads(res.stdout, parse_constant=reject_constant)
        self.assertIsInstance(data, (dict, list))
        self.assertTrue(data)

    def test_help_explains_every_option(self):
        res = run(canonical_command()[:2] + ["--help"])
        self.assertEqual(res.returncode, 0, res.stderr)
        blocks = help_blocks(res.stdout)
        self.assertIn("--json", blocks)
        for flag, (text, has_help) in blocks.items():
            self.assertTrue(has_help, "%s has no help text" % flag)
        for flag in LEGAL_FLAGS:
            self.assertIn(flag, blocks)
            self.assertIn("verify current value", re.sub(r"\s+", " ", blocks[flag][0]).lower(),
                          "%s help must say 'verify current value'" % flag)


if __name__ == "__main__":
    unittest.main()
