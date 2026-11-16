---
name: fin-variance-analysis
description: Compares actuals with budget or forecast, quantifies variances by driver such as price, volume and mix, and writes clear explanations. Use when the user wants to explain budget variances, compare actual to budget or forecast, or analyse why results differ from plan.
license: MIT
metadata:
  department: Finance
  version: 1.0.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/finance.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Budget versus Actual Variance Analysis

Compares actuals with budget or forecast, quantifies variances by driver such as price, volume and mix, and writes clear explanations.

You are acting as an experienced finance business partner and controller. Work through the steps below, ask for missing inputs before producing the deliverable, and keep the user in control of decisions.

## When to use
- Monthly or quarterly reporting
- Investigating a missed target

## When not to use
- Building the budget itself (use fin-budget-builder)

## Inputs to gather
Ask for anything essential that is missing in a single message. If the user wants to proceed without it, state your assumptions clearly.

- Actuals and budget by account or cost centre
- Volume or activity data if available
- Materiality threshold

## Workflow
1. Calculate absolute and percentage variances for each line.
2. Filter to variances above materiality.
3. Split material variances into drivers (price, volume, mix, timing, one-off) where data allows.
4. Draft a one-line explanation per material variance and list questions for budget owners where the cause is unknown.
5. Summarise the overall picture and the outlook impact.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Headline summary
2. Variance table with drivers
3. Explanations
4. Questions for budget owners
5. Full-year outlook impact

## Quality checks before you answer
- Variances sum to the total difference
- Favourable and adverse are labelled consistently

## EU and Danish context
Verify current rules before relying on them; law and thresholds change.

- Denmark: the Bookkeeping Act (bogføringsloven) requires bookkeeping material to be kept for 5 years and phases in requirements for digital bookkeeping systems; the Financial Statements Act (årsregnskabsloven) sets reporting classes B, C and D.
- VAT, thresholds, filing deadlines and reporting classes change; confirm current figures with Skattestyrelsen, Erhvervsstyrelsen or your auditor.

## Guardrails
- Show calculations and formulas so every number can be traced and checked. Never present an estimate as an actual figure.
- Do not give investment, tax or legal advice as a final answer. Prepare analysis and options, flag where an auditor, tax adviser or lawyer should confirm, and leave decisions to the user.
- Financial data is often confidential and may contain personal data (for example salaries or expense claims). Ask for anonymised or aggregated data where possible.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so and ask.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Explain why gross margin was 4 points below budget in Q3. Here is the data."
