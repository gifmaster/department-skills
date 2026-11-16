#!/usr/bin/env python3
"""Build the skill library from the YAML catalogues.

Source of truth: catalogue/<department>.yaml
Generated output:
  departments/<dept>/skills/<prefix>-<id>/SKILL.md   Agent Skills standard (Claude, ChatGPT Skills, Codex, Copilot, Gemini CLI)
  departments/<dept>/skills/<prefix>-<id>/PROMPT.md  Portable instructions (Custom GPTs, Gemini Gems, Microsoft 365 Copilot agents)
  departments/<dept>/README.md and INSTALL.md
  departments/<dept>/.claude-plugin/plugin.json
  .claude-plugin/marketplace.json
  CATALOG.md

Usage: python3 scripts/build.py
Do not edit generated files by hand; edit the catalogue and rebuild.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue"
DEPTS = ROOT / "departments"
AUTOMATION = ROOT / "automation"
FACTS = ROOT / "facts"
VERSION = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "1.0.0"
AUTHOR = "Alexander Senderovitz"
REPO = "gifmaster/department-skills"
ORDER = ["hr", "finance", "supply-chain", "legal", "sales", "marketing", "it", "customer-service"]
PASTE_MARKER = "<!-- PASTE BELOW THIS LINE -->"

GENERATED_NOTE = "<!-- Generated from catalogue/{src}.yaml by scripts/build.py. Edit the catalogue, not this file. -->"


def bullets(items):
    return "\n".join(f"- {i}" for i in items)


def numbered(items):
    return "\n".join(f"{n}. {i}" for n, i in enumerate(items, 1))


def skill_name(dept, skill):
    return f"{dept['prefix']}-{skill['id']}"


def description(skill):
    text = f"{skill['summary'].rstrip('.')}. Use when {skill['triggers'].rstrip('.')}."
    if skill.get("not_for"):
        text += " " + skill["not_for"].rstrip(".") + "."
    return " ".join(text.split())


LANGUAGE_RULE = "Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology."
INPUT_RULE = ("Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. "
              "Stop and ask first only when a missing input would make the answer wrong or risky "
              "(for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.")


def load_unit(skill_name_):
    d = AUTOMATION / skill_name_
    if not (d / "unit.yaml").exists():
        return None
    unit = yaml.safe_load((d / "unit.yaml").read_text(encoding="utf-8"))
    unit["method"] = (d / "method.md").read_text(encoding="utf-8").strip() if (d / "method.md").exists() else ""
    unit["dir"] = d
    return unit


def resolve_refs(dept, ids):
    return [f"{dept['prefix']}-{i}" for i in ids]


def render_skill_md(dept, skill, src):
    name = skill_name(dept, skill)
    fm = {
        "name": name,
        "description": description(skill),
        "license": "MIT",
        "metadata": {
            "department": dept["title"],
            "version": VERSION,
            "author": AUTHOR,
            "jurisdiction": "EU and Denmark aware, adaptable to other countries",
        },
    }
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=10_000).strip()
    eu = skill.get("eu", [])
    unit = load_unit(name)
    facts_line = (f"For dated rates, deadlines, thresholds and sources, read `references/facts.md` "
                  f"(last verified {dept['facts_verified']}). Treat anything not in that file as unverified.")
    parts = [
        f"---\n{front}\n---",
        GENERATED_NOTE.format(src=src),
        f"# {skill['title']}",
        f"{skill['summary']}",
        f"You are acting as {dept['role']}. Follow the workflow, keep the user in control of decisions, and be concrete.",
        "## When to use\n" + bullets(skill["use"]),
        "## Hand-offs and limits\n" + bullets(skill.get("avoid", [])),
        "## Inputs\n" + INPUT_RULE + "\n\n" + bullets(skill["inputs"]),
        "## Workflow\n" + numbered(skill["steps"]),
    ]
    if unit:
        parts.append(
            "## Calculation tools\n"
            f"This skill ships a tested script: `{unit['script']}`. {unit['summary'].rstrip('.')}. "
            "If you can run code, use it rather than calculating by hand, and show the command and key output. "
            f"Input template: `{unit['template']}`. Worked example: `examples/worked-example.md`.\n\n"
            f"```\n{unit['command']}\n```\n\n"
            "Run `--help` for all parameters. Every legal or policy figure is a parameter: confirm current values before relying on them.\n\n"
            "If you cannot run code, apply the same method by hand:\n\n" + unit["method"])
    parts += [
        "## Output format\nUse these sections, in this order, unless the user asks for a different format:\n\n" + numbered(skill["output"]),
        "## Quality checks before you answer\n" + bullets(skill["checks"]),
        "## EU and Danish context\n" + (bullets(eu) + "\n\n" if eu else "") + facts_line,
        "## Guardrails\n" + bullets(dept["common_guardrails"] + [
            "Do not invent facts, figures, legal references or sources. If something is unknown, say so.",
            LANGUAGE_RULE,
            "End with a short list of assumptions and open questions when any exist.",
        ]),
        "## Example requests\n" + bullets([f'"{e}"' for e in skill["examples"]]),
    ]
    if not skill.get("avoid"):
        parts = [p for p in parts if not p.startswith("## Hand-offs and limits")]
    return "\n\n".join(parts) + "\n"


def render_prompt_md(dept, skill, src):
    name = skill_name(dept, skill)
    eu = skill.get("eu", [])
    unit = load_unit(name)
    header = "\n\n".join([
        GENERATED_NOTE.format(src=src),
        f"# {skill['title']}: portable instructions",
        "Use this file on platforms that do not read SKILL.md folders. Copy everything below the marker into the instructions field of a ChatGPT custom GPT or Project, a Gemini Gem, or a Microsoft 365 Copilot agent (Agent Builder). The text below the marker stays under 8,000 characters so it fits all three. Also upload `references/facts.md` (and any script and template in this folder) as knowledge files: the facts file holds the dated figures this skill relies on.",
        f"Skill ID: `{name}`",
        PASTE_MARKER,
    ])
    sections = [
        f"You are {dept['role']}, specialising in: {skill['title']}. {skill['summary']}",
        "Use this when " + skill["triggers"].rstrip(".") + "." + (" " + skill["not_for"].rstrip(".") + "." if skill.get("not_for") else ""),
        "# Inputs\n" + INPUT_RULE + "\n" + bullets(skill["inputs"]),
        "# Workflow\n" + numbered(skill["steps"]),
    ]
    if unit:
        sections.append("# Calculation method\nIf a code tool is available and the script file is attached, run it; otherwise calculate by hand:\n" + unit["method"])
    sections += [
        "# Output\nStructure the deliverable with these sections:\n" + numbered(skill["output"]),
        "# Check before answering\n" + bullets(skill["checks"]),
        "# EU and Danish context\n" + (bullets(eu) + "\n" if eu else "") + f"Use the attached facts file (last verified {dept['facts_verified']}) for dated figures; treat anything else as unverified.",
        "# Rules\n" + bullets(dept["common_guardrails"] + ["Never invent facts, figures, legal references or sources; say what is unknown.", LANGUAGE_RULE + " Write in British English when writing English."]),
        "# Conversation starters\n" + bullets(skill["examples"]),
    ]
    body = "\n\n".join(sections)
    return header + "\n\n" + body + "\n"


def render_dept_readme(dept, skills_dir_names):
    rows = "\n".join(
        f"| [`{skill_name(dept, s)}`](skills/{skill_name(dept, s)}/SKILL.md) | {s['title']} | {s['summary']} |"
        for s in dept["skills"]
    )
    flows = "\n".join(
        f"### {w['name']}\n{w['purpose']}\n\n" + " → ".join(f"`{r}`" for r in resolve_refs(dept, w["skills"]))
        for w in dept.get("workflows", [])
    )
    return f"""<!-- Generated by scripts/build.py -->
# {dept['title']} skill pack

{dept['overview']}

**{len(dept['skills'])} skills** · version {VERSION} · EU and Denmark aware · works with Claude, ChatGPT, Gemini and Copilot (chat and code).

- Install in Claude Code: `/plugin install {dept['department']}-skills --marketplace {REPO}`
- Install anywhere else: see [INSTALL.md](INSTALL.md)
- Each skill folder has `SKILL.md` (for platforms that load skills) and `PROMPT.md` (copy-paste instructions for custom GPTs, Gems and Copilot agents).

## Skills

| Skill | Title | What it does |
|---|---|---|
{rows}

## Suggested workflows

Skills work on their own, and chain well in these sequences.

{flows}

## Built-in guardrails

{bullets(dept['common_guardrails'])}

## Regulatory facts

Every skill in this pack ships `references/facts.md`: dated, sourced figures and rules (last verified {dept['facts_verified']}). The master copy is [facts/{dept['department']}.md](../../facts/{dept['department']}.md). Update it there and rebuild.

These notes are orientation, not legal advice. Check current law, collective agreements and your own policies.
"""


def render_dept_install(dept):
    key = dept["department"]
    p = dept["prefix"]
    return f"""<!-- Generated by scripts/build.py -->
# Install the {dept['title']} pack

Full guides for every platform are in [docs/install](../../docs/install/). Quick routes:

| Platform | Fastest route |
|---|---|
| Claude Code | `/plugin install {key}-skills --marketplace {REPO}` (older versions: `/plugin marketplace add {REPO}` then `/plugin install {key}-skills@department-skills`) |
| Claude (web, desktop, mobile) | Upload a zip from `dist/skills/` in the Skills section of settings ([guide](../../docs/install/claude.md)) |
| ChatGPT (Skills) | Skills → Create → Upload from your computer, choose a zip from `dist/skills/` ([guide](../../docs/install/chatgpt.md)) |
| Custom GPT or ChatGPT Project | Paste the text below the marker in `PROMPT.md` into Instructions |
| OpenAI Codex | `./install.sh codex {key}` |
| Gemini CLI | `gemini skills install https://github.com/{REPO}.git --path departments/{key}/skills` or `./install.sh gemini {key}` |
| Gemini app (Gems) | Paste `PROMPT.md` into the Gem instructions; optionally attach `SKILL.md` as knowledge |
| GitHub Copilot (VS Code, CLI, cloud agent) | `./install.sh copilot {key}` or copy folders into `.github/skills/` in a repo |
| Microsoft 365 Copilot | Agent Builder → Configure → paste `PROMPT.md` into Instructions |

Whole pack as one zip: `dist/packs/{key}-skills.zip`. All skill names start with `{p}-` so they never clash with other packs.

On Windows use `install.ps1` instead of `install.sh` (same arguments).
"""


def main():
    import assemble_facts
    assemble_facts.main()
    if DEPTS.exists():
        shutil.rmtree(DEPTS)
    catalogue = []
    files = sorted(CATALOGUE.glob("*.yaml"), key=lambda f: ORDER.index(f.stem) if f.stem in ORDER else 99)
    for f in files:
        dept = yaml.safe_load(f.read_text(encoding="utf-8"))
        dept["department"] = f.stem
        fm = re.search(r"^last_verified:\s*(\S+)", (FACTS / f"{f.stem}.md").read_text(encoding="utf-8"), re.M)
        dept["facts_verified"] = fm.group(1) if fm else "unknown"
        ddir = DEPTS / f.stem
        names = []
        for s in dept["skills"]:
            n = skill_name(dept, s)
            sdir = ddir / "skills" / n
            sdir.mkdir(parents=True, exist_ok=True)
            (sdir / "SKILL.md").write_text(render_skill_md(dept, s, f.stem), encoding="utf-8")
            (sdir / "PROMPT.md").write_text(render_prompt_md(dept, s, f.stem), encoding="utf-8")
            (sdir / "references").mkdir(exist_ok=True)
            shutil.copyfile(FACTS / f"{f.stem}.md", sdir / "references" / "facts.md")
            unit = load_unit(n)
            if unit:
                for sub in ("scripts", "assets", "examples"):
                    if (unit["dir"] / sub).exists():
                        shutil.copytree(unit["dir"] / sub, sdir / sub, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            names.append(n)
        (ddir / "README.md").write_text(render_dept_readme(dept, names), encoding="utf-8")
        (ddir / "INSTALL.md").write_text(render_dept_install(dept), encoding="utf-8")
        (ddir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (ddir / ".claude-plugin" / "plugin.json").write_text(json.dumps({
            "name": f"{f.stem}-skills",
            "version": VERSION,
            "description": f"{len(dept['skills'])} {dept['title']} skills. {dept['overview']}",
            "author": {"name": AUTHOR},
            "license": "MIT",
            "keywords": [f.stem, "skills", "eu", "denmark"],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        catalogue.append(dept)

    (ROOT / ".claude-plugin").mkdir(exist_ok=True)
    (ROOT / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "department-skills",
        "owner": {"name": AUTHOR},
        "metadata": {"description": "Department skill packs for HR, Finance, Supply Chain, Legal, Sales, Marketing, IT and Customer Service.", "version": VERSION},
        "plugins": [{
            "name": f"{d['department']}-skills",
            "source": f"./departments/{d['department']}",
            "description": f"{len(d['skills'])} {d['title']} skills",
            "version": VERSION,
        } for d in catalogue],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # automated skills table in the root README
    rows = ["| Department | Skill | What the script does |", "|---|---|---|"]
    for d in catalogue:
        for s in d["skills"]:
            u = load_unit(skill_name(d, s))
            if u:
                n = skill_name(d, s)
                rows.append(f"| {d['title']} | [`{n}`](departments/{d['department']}/skills/{n}/SKILL.md) | {u['summary']} |")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme = re.sub(r"<!-- AUTOTABLE:START -->.*<!-- AUTOTABLE:END -->",
                    "<!-- AUTOTABLE:START -->\n" + "\n".join(rows) + "\n<!-- AUTOTABLE:END -->", readme, flags=re.S)
    (ROOT / "README.md").write_text(readme, encoding="utf-8")

    total = sum(len(d["skills"]) for d in catalogue)
    lines = [
        "<!-- Generated by scripts/build.py -->",
        "# Skill catalogue",
        "",
        f"{total} skills across {len(catalogue)} departments. Version {VERSION}.",
        "",
    ]
    for d in catalogue:
        lines += [f"## {d['title']} ({len(d['skills'])})", "", f"[Pack overview](departments/{d['department']}/README.md)", "", "| Skill | What it does |", "|---|---|"]
        for s in d["skills"]:
            n = skill_name(d, s)
            lines.append(f"| [`{n}`](departments/{d['department']}/skills/{n}/SKILL.md) | {s['summary']} |")
        lines.append("")
    (ROOT / "CATALOG.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Built {total} skills in {len(catalogue)} departments")


if __name__ == "__main__":
    main()
