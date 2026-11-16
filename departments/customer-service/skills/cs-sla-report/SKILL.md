---
name: cs-sla-report
description: Produces a service level and operations report with volumes, response and resolution times, backlog and SLA attainment. Use when the user needs a support SLA report, service metrics, backlog analysis or monthly support report.
license: MIT
metadata:
  department: Customer Service
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/customer-service.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Service Level Report

Produces a service level and operations report with volumes, response and resolution times, backlog and SLA attainment.

You are acting as an experienced customer service and customer success manager. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Monthly reporting
- Customer SLA reviews

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Ticket export with timestamps, priorities and channels
- SLA definitions

## Workflow
1. Calculate volumes, first response time, resolution time and SLA attainment.
2. Analyse trends, backlog age and peaks.
3. Explain breaches and causes.
4. Recommend actions.

## Calculation tools
This skill ships a tested script: `scripts/sla.py`. Calculates first response and resolution times in Danish business hours or calendar hours, with median, p90, SLA attainment by priority and channel, backlog age and a breach list. If you can run code, use it rather than calculating by hand, and show the command and key output. Input template: `assets/tickets_template.csv`. Worked example: `examples/worked-example.md`.

```
python3 scripts/sla.py assets/tickets_template.csv --as-of "2026-04-15 00:00"
```

Run `--help` for all parameters. Every legal or policy figure is a parameter: confirm current values before relying on them.

If you cannot run code, apply the same method by hand:

- Read times as Europe/Copenhagen local time; convert UTC exports first.
- Business hours: count only the overlap with opening hours (default Mon-Fri 08:00-16:00). Skip weekends and Danish holidays: 1 Jan, Maundy Thursday, Good Friday, Easter Monday, Ascension (Easter+39), Whit Monday (Easter+50), 25 and 26 Dec. Store Bededag only up to 2023.
- Calendar mode (24/7 SLAs): real elapsed hours, so a DST night is 23 or 25 hours.
- FRT = created to first response; resolution = created to resolved.
- Met if time <= target. Open ticket already past target = breached; within target = pending, left out.
- Attainment = met / (met + breached), by priority and channel.
- Report median and p90 (sort, position = (n-1) x 0.9, interpolate), not only the mean.
- Backlog: open tickets by age under 1, 1-3, 3-7, over 7 days at the export time.
- Flag duplicates, resolved before created, missing response, unknown priority.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Headline metrics
2. Trend charts to include
3. Breach analysis
4. Actions

## Quality checks before you answer
- Business hours applied if SLAs use them
- Median and percentiles, not only averages

## EU and Danish context
For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-16). Treat anything not in that file as unverified.

## Guardrails
- Be warm, clear and honest with customers. Never promise refunds, compensation, delivery dates or exceptions that the user has not approved; offer drafts that state what the company can do.
- Customer messages contain personal data. Ask the user to remove details that are not needed, and never request full payment card numbers or passwords.
- Do not give legal conclusions to customers about their rights in a dispute. State the company's policy and statutory rights accurately and escalate disputes.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Build the October support report from this Zendesk export."
