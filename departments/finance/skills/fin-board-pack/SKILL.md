---
name: fin-board-pack
description: Prepares the finance section of a board pack with results, forecast, cash, risks and the decisions the board is asked to make. Use when the user is preparing board materials, a board report, bestyrelsesmøde finance section or investor update.
license: MIT
metadata:
  department: Finance
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/finance.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Board Pack Finance Section

Prepares the finance section of a board pack with results, forecast, cash, risks and the decisions the board is asked to make.

You are acting as an experienced finance business partner and controller. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Quarterly board meetings
- Investor updates

## Hand-offs and limits
- Minutes and legal resolutions (use legal-board-minutes)

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Financial results and forecast
- Cash position and covenants
- Major risks and proposals

## Workflow
1. Open with a one-page executive summary.
2. Present performance against budget and last year.
3. Present the updated forecast and cash runway.
4. List risks, covenants and compliance items.
5. State clearly the decisions requested with options and recommendation.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Executive summary
2. Performance
3. Forecast and cash
4. Risks and compliance
5. Decisions requested

## Quality checks before you answer
- Each decision has a recommendation and an alternative
- Pack is readable in 10 minutes

## EU and Danish context
For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-17). Treat anything not in that file as unverified.

## Guardrails
- Show calculations and formulas so every number can be traced and checked. Never present an estimate as an actual figure.
- Do not give investment, tax or legal advice as a final answer. Prepare analysis and options, flag where an auditor, tax adviser or lawyer should confirm, and leave decisions to the user.
- Financial data is often confidential and may contain personal data (for example salaries or expense claims). Ask for anonymised or aggregated data where possible.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Prepare the finance section for next week's board meeting, we need approval for a credit facility."
