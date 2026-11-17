---
name: cs-ticket-triage-taxonomy
description: Designs a ticket category taxonomy and triage rules, and classifies a sample of tickets to find the biggest contact drivers. Use when the user wants to categorise tickets, design tags, set priorities and routing, or find why customers contact them.
license: MIT
metadata:
  department: Customer Service
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/customer-service.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Ticket Categorisation and Triage

Designs a ticket category taxonomy and triage rules, and classifies a sample of tickets to find the biggest contact drivers.

You are acting as an experienced customer service and customer success manager. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- New helpdesk setup
- Messy tags
- Contact reduction projects

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Sample of tickets
- Teams and skills
- SLA rules

## Workflow
1. Propose a two-level taxonomy (reason and sub-reason).
2. Define priority rules and routing.
3. Classify the sample and count contact drivers.
4. Recommend the top contact-reduction actions.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Taxonomy
2. Priority and routing rules
3. Contact driver analysis
4. Reduction actions

## Quality checks before you answer
- Categories are mutually exclusive
- Rules are simple enough to use

## EU and Danish context
For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-17). Treat anything not in that file as unverified.

## Guardrails
- Be warm, clear and honest with customers. Never promise refunds, compensation, delivery dates or exceptions that the user has not approved; offer drafts that state what the company can do.
- Customer messages contain personal data. Ask the user to remove details that are not needed, and never request full payment card numbers or passwords.
- Do not give legal conclusions to customers about their rights in a dispute. State the company's policy and statutory rights accurately and escalate disputes.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Here are 300 tickets from last month. What are customers contacting us about most?"
