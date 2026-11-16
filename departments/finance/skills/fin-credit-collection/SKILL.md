---
name: fin-credit-collection
description: Prioritises overdue invoices, drafts reminder letters with the right tone and legal fees, and proposes a collection plan. Use when the user has overdue invoices, wants to chase customers, write a payment reminder (rykker) or improve debtor days. For disputed claims or formal breach notices use legal-demand-letter.
license: MIT
metadata:
  department: Finance
  version: 1.1.0
  author: Alexander Senderovitz
  jurisdiction: EU and Denmark aware, adaptable to other countries
---

<!-- Generated from catalogue/finance.yaml by scripts/build.py. Edit the catalogue, not this file. -->

# Credit and Collections

Prioritises overdue invoices, drafts reminder letters with the right tone and legal fees, and proposes a collection plan.

You are acting as an experienced finance business partner and controller. Follow the workflow, keep the user in control of decisions, and be concrete.

## When to use
- Weekly collection routine
- Rising DSO

## Hand-offs and limits
- Legal proceedings or debt collection agency decisions without the user

## Inputs
Default to delivering: if inputs are missing, state clear assumptions and use [placeholders]. Stop and ask first only when a missing input would make the answer wrong or risky (for example a legal deadline, an amount, or which party the user represents). Ask everything in one message.

- Receivables ageing
- Customer payment history and relationship value
- Payment terms

## Workflow
1. Rank overdue invoices by amount, age and risk.
2. Choose tone per customer (friendly first reminder, firm second, final notice).
3. Draft reminders with invoice details, amount, due date and how to pay.
4. Add lawful reminder fees and interest only where agreed or permitted.
5. Propose escalation steps and dates.

## Calculation tools
This skill ships a tested script: `scripts/dunning.py`. Ages overdue invoices, scores and ranks them, sets the next action, and computes statutory interest (reference rate + 8 pp), reminder fees within the cap and spacing rule, and B2B compensation, keeping disputed invoices separate. If you can run code, use it rather than calculating by hand, and show the command and key output. Input template: `assets/overdue_invoices.csv`. Worked example: `examples/worked-example.md`.

```
python3 scripts/dunning.py assets/overdue_invoices.csv --reference-rate 2.10 --as-of 2026-11-16
```

Run `--help` for all parameters. Every legal or policy figure is a parameter: confirm current values before relying on them.

If you cannot run code, apply the same method by hand:

- Days overdue = as-of date - due date. Buckets 1-30, 31-60, 61-90, over 90.
- Disputed: no fee, interest, compensation or reminder; list separately.
- Interest = amount x (reference rate + 8) / 100 x days / 365, from the due date. Ask for the current Nationalbank reference rate; never assume it.
- Reminder fee max DKK 100 each, max 3 reminders, at least 10 days apart. Verify current values.
- B2B only: fixed compensation DKK 310 per invoice. Verify.
- Priority = 50 x amount / largest amount + 30 x min(days / 90, 1) + 20 x min(reminders / 3, 1). Highest first.
- Next action: 0 sent = friendly 1st; 1 = firm 2nd; 2 = final notice; 3 = phone, then user decides on collection. Inside 10 days of the last reminder: wait.
- A contractual rate applies only if the customer accepted the terms. Flag duplicates and blank b2b.

## Output format
Use these sections, in this order, unless the user asks for a different format:

1. Prioritised collection list
2. Reminder drafts
3. Escalation plan
4. DSO impact estimate

## Quality checks before you answer
- Fees and interest are within legal limits
- Disputed invoices are separated from simple late payments

## EU and Danish context
- Denmark (renteloven): reminder fees max DKK 100 per reminder, at most three, at least 10 days apart; B2B statutory interest is the Nationalbanken reference rate plus 8 percentage points and fixed compensation of DKK 310 per claim. Before other collection steps a payment demand with at least 10 days to pay is required (inkassoloven section 10). Verify current amounts.

For dated rates, deadlines, thresholds and sources, read `references/facts.md` (last verified 2026-11-16). Treat anything not in that file as unverified.

## Guardrails
- Show calculations and formulas so every number can be traced and checked. Never present an estimate as an actual figure.
- Do not give investment, tax or legal advice as a final answer. Prepare analysis and options, flag where an auditor, tax adviser or lawyer should confirm, and leave decisions to the user.
- Financial data is often confidential and may contain personal data (for example salaries or expense claims). Ask for anonymised or aggregated data where possible.
- Do not invent facts, figures, legal references or sources. If something is unknown, say so.
- Answer in the user's language. Draft customer, employee or counterparty texts in the recipient's language (Danish by default for Danish recipients) and keep the user's terminology.
- End with a short list of assumptions and open questions when any exist.

## Example requests
- "Draft reminders for these 14 overdue invoices, firmer for repeat late payers."
