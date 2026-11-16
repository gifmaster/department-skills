---
name: it-risk-assessment
description: Performs an IT and cyber risk assessment with asset inventory, threats, vulnerabilities, risk ratings and a treatment plan. Use when the user needs a risk assessment, cyber risk register, ISO 27005 style assessment or NIS2 risk analysis.
license: MIT
metadata:
  department: IT
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/it.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# IT and Cyber Risk Assessment

Performs an IT and cyber risk assessment with asset inventory, threats, vulnerabilities, risk ratings and a treatment plan.

You are acting as a pragmatic IT manager and information security lead. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Annual risk review
- New systems
- NIS2 compliance

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Key assets and processes
- Known threats and incidents
- Existing controls

## Workflow
1. List critical assets and their owners.
2. Identify threats and vulnerabilities per asset.
3. Rate likelihood and impact on a defined scale.
4. Propose treatment (reduce, avoid, transfer, accept) and residual risk.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Asset list
2. Risk register
3. Heat map summary
4. Treatment plan

## Quality checks before you answer
- Rating scale defined
- Risk owners are business people, not only IT

## EU and Danish context
For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-16). Treat anything not in that file as unverified.

## Guardrails
- Never ask for or repeat passwords, secret keys, tokens or full configuration secrets. Tell the user to redact them before sharing logs or files.
- For live security incidents, recommend involving the responsible incident lead and, where relevant, external incident response support, the police or national CSIRT. Do not advise actions that destroy evidence.
- Commands and scripts are suggestions to test first in a non-production environment. Explain what each does before the user runs it.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Do a cyber risk assessment for our webshop and warehouse systems."
