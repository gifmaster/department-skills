# Skill anatomy

Every skill is generated from one entry in `catalogue/<department>.yaml`.

## Catalogue entry

```yaml
- id: nda-review                      # becomes legal-nda-review (department prefix added)
  title: NDA Review
  summary: One sentence on what the skill does.
  triggers: phrases and situations that should load the skill
  use: [situations where it helps]
  avoid: [situations where another skill or a person should handle it]
  inputs: [what to ask the user for]
  steps: [the workflow, in order, with the reason where it matters]
  output: [sections of the deliverable, in order]
  checks: [what to verify before answering]
  eu: [EU and Danish rules specific to this skill]
  examples: [realistic requests]
```

Department-level fields add shared context: `role` (who the AI acts as), `common_guardrails`, `common_eu` and `workflows` (suggested chains of skills).

## Generated SKILL.md

```
---
name: legal-nda-review
description: <summary> Use when <triggers>.
license: MIT
metadata: {department, version, author, jurisdiction}
---
# Title
Summary and role
## When to use / When not to use
## Inputs to gather
## Workflow
## Output format
## Quality checks before you answer
## EU and Danish context
## Guardrails
## Example requests
```

The `description` is what tools read to decide when to load a skill, so it combines what the skill does with the situations that should trigger it.

## Generated PROMPT.md

The same content written as direct instructions for a custom assistant, below a paste marker, and validated to stay under 8,000 characters.

## Validation rules

`scripts/validate.py` fails the build if any of these are broken:

- name is lowercase letters, numbers and hyphens, at most 64 characters, matches its folder and is unique
- description is 1 to 1,024 characters with no angle brackets
- `PROMPT.md` paste section is at most 8,000 characters
- `SKILL.md` is under 500 lines
- every referenced skill (for example `use fin-budget-builder`) exists
- each department has exactly 21 skills
- house style: British English spellings and no long dashes

`scripts/lint_catalogue.py` catches YAML mistakes such as list items split in the wrong place.
