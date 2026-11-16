# Department Skills

**168 ready-to-use AI skills for eight business departments.** One library that works in Claude, ChatGPT, Gemini and Copilot, in both chat and coding agents.

Each skill is a short, structured playbook that tells the AI how to do one business task well: which inputs to ask for, which steps to follow, what the deliverable looks like, what to check before answering and which EU and Danish rules to keep in mind.

| Department | Skills | Pack | Examples |
|---|---|---|---|
| Human Resources | 21 | [hr](departments/hr/README.md) | Job descriptions, screening rubrics, onboarding, performance reviews, pay gap analysis |
| Finance | 21 | [finance](departments/finance/README.md) | Month-end close, variance analysis, 13-week cash flow, VAT return, business cases |
| Supply Chain | 21 | [supply-chain](departments/supply-chain/README.md) | Demand forecast, safety stock, supplier scorecards, Incoterms, EUDR due diligence |
| Legal | 21 | [legal](departments/legal/README.md) | NDA and contract review, DPIA, data breach response, AI Act classification |
| Sales | 21 | [sales](departments/sales/README.md) | ICP, discovery prep, MEDDICC qualification, proposals, forecasting, tenders |
| Marketing | 21 | [marketing](departments/marketing/README.md) | Positioning, campaign briefs, SEO briefs, newsletters, cookie consent checks |
| IT | 21 | [it](departments/it/README.md) | Incident triage, postmortems, NIS2 readiness, access reviews, AI use case intake |
| Customer Service | 21 | [customer-service](departments/customer-service/README.md) | Ticket replies, complaints, returns decisions, CSAT analysis, outage communication |

Full list: [CATALOG.md](CATALOG.md).

## Works everywhere

Every skill folder contains:

- **`references/facts.md`**: the dated, sourced Danish and EU figures the skill relies on (rates, deadlines, thresholds), with a "last verified" date.
- **Calculation tools** in 20 skills that are easy to automate: a tested Python script (standard library only), an input template and a worked example, so the AI calculates instead of guessing. See [Automated skills](#automated-skills).

Every skill also ships in two formats, generated from the same source:

- **`SKILL.md`** follows the open [Agent Skills](https://agentskills.io) standard. It loads automatically when relevant in tools that support skills.
- **`PROMPT.md`** holds the same playbook as copy-paste instructions under 8,000 characters, for tools that do not load skill folders.

| Platform | Chat | Code / agent | Format | Guide |
|---|---|---|---|---|
| Claude | Claude web, desktop and mobile apps | Claude Code | SKILL.md (zip upload or plugin) | [docs/install/claude.md](docs/install/claude.md) |
| ChatGPT and OpenAI | ChatGPT Skills, custom GPTs, Projects | Codex | SKILL.md or PROMPT.md | [docs/install/chatgpt.md](docs/install/chatgpt.md) |
| Google Gemini | Gemini app (Gems) | Gemini CLI | PROMPT.md or SKILL.md | [docs/install/gemini.md](docs/install/gemini.md) |
| Microsoft and GitHub Copilot | Microsoft 365 Copilot agents | GitHub Copilot in VS Code, Copilot CLI, cloud agent | PROMPT.md or SKILL.md | [docs/install/copilot.md](docs/install/copilot.md) |

See the [platform matrix](docs/platform-matrix.md) for details and limits.

## Quick start

**Claude Code**

```
/plugin install hr-skills --marketplace gifmaster/department-skills
```

On older Claude Code versions, add the marketplace first: `/plugin marketplace add gifmaster/department-skills`, then `/plugin install hr-skills@department-skills`.

**Any agent tool that reads skill folders (macOS or Linux)**

```bash
git clone https://github.com/gifmaster/department-skills.git
cd department-skills
./install.sh claude hr finance     # or: copilot, gemini, codex, all
```

On Windows use `.\install.ps1 claude hr finance`.

**Chat apps:** download a zip from [`dist/skills/`](dist/skills/) and upload it (Claude, ChatGPT Skills), or paste a skill's `PROMPT.md` into a custom GPT, Gem or Copilot agent.

Then just ask normally, for example *"Review this NDA before I sign it"* or *"Build a 13-week cash forecast from these files"*. The matching skill loads on its own; you can also name it, for example `legal-nda-review`.

## Automated skills

These 20 skills ship a tested calculation script, an input template (`assets/`) and a worked example (`examples/`). Any assistant that can run code (Claude, ChatGPT, Codex, Gemini CLI, Copilot agent mode) runs the script; others follow the method written into the skill.

<!-- AUTOTABLE:START -->
| Department | Skill | What the script does |
|---|---|---|
| Human Resources | [`hr-pay-gap-analysis`](departments/hr/skills/hr-pay-gap-analysis/SKILL.md) | Calculates hourly-normalised mean and median gender pay gaps for base and total pay, per category with small-group suppression and a 5% flag, plus pay quartile shares and variable pay take-up. |
| Finance | [`fin-bank-reconciliation`](departments/finance/skills/fin-bank-reconciliation/SKILL.md) | Matches bank and ledger lines (1:1 within a date window, then 1:many sums, then fuzzy text), flags duplicates, sign errors, amount differences and items over 60 days, and builds the reconciliation statement from bank balance to ledger balance. |
| Finance | [`fin-variance-analysis`](departments/finance/skills/fin-variance-analysis/SKILL.md) | Computes absolute and percentage variances with favourable or adverse labels for revenue and cost lines, filters to material variances, splits them into price and volume where quantities exist, and checks that line variances and control totals reconcile. |
| Finance | [`fin-cash-flow-forecast`](departments/finance/skills/fin-cash-flow-forecast/SKILL.md) | Builds a weekly 13-week cash forecast from receivables shifted by customer lateness, payables and recurring items on Danish banking days, with A-tax timing for large or small employers, the lowest week-end and banking-day balance, and buffer and facility warnings. |
| Finance | [`fin-credit-collection`](departments/finance/skills/fin-credit-collection/SKILL.md) | Ages overdue invoices, scores and ranks them, sets the next action, and computes statutory interest (reference rate + 8 pp), reminder fees within the cap and spacing rule, and B2B compensation, keeping disputed invoices separate. |
| Finance | [`fin-journal-entry-testing`](departments/finance/skills/fin-journal-entry-testing/SKILL.md) | Runs seven documented red-flag tests on a journal export (weekend or Danish holiday, out of hours, round amounts, just below the approval limit, duplicates, manual postings to revenue or cash, new users), scores and ranks entries, and describes facts only. |
| Supply Chain | [`scm-demand-forecast`](departments/supply-chain/skills/scm-demand-forecast/SKILL.md) | Fits moving average, simple exponential smoothing and (with 24+ months) Holt-Winters per item, picks the method with the lowest hold-out WAPE, reports MAPE, WAPE and bias, and forecasts the horizon with stock-out months excluded. |
| Supply Chain | [`scm-inventory-policy`](departments/supply-chain/skills/scm-inventory-policy/SKILL.md) | Calculates safety stock with demand and lead-time variability, reorder point and pack-rounded EOQ per item, the inventory value impact against current stock, and flags inconsistent units. |
| Supply Chain | [`scm-abc-xyz-segmentation`](departments/supply-chain/skills/scm-abc-xyz-segmentation/SKILL.md) | Segments items by cumulative value share (ABC) and coefficient of variation (XYZ), flags intermittent and lumpy demand, separates items with too little history, and builds the 9-box with a suggested policy per box. |
| Supply Chain | [`scm-otif-kpi-analysis`](departments/supply-chain/skills/scm-otif-kpi-analysis/SKILL.md) | Calculates line and order OTIF against the promised date with day and quantity tolerances, fill rates, results by customer and item, and a Pareto of miss reasons, combining partial deliveries per line. |
| Supply Chain | [`scm-spend-analysis`](departments/supply-chain/skills/scm-spend-analysis/SKILL.md) | Normalises and groups supplier names, categorises AP spend by keyword or account map, and reports spend by category and supplier, Pareto, tail spend, fragmentation and labelled savings estimate ranges. |
| Legal | [`legal-contract-obligations-summary`](departments/legal/skills/legal-contract-obligations-summary/SKILL.md) | Calculates contract notice deadlines, rolls auto-renewals forward when a deadline was missed, flags upcoming deadlines and writes calendar reminders. |
| Legal | [`legal-dsar-response`](departments/legal/skills/legal-dsar-response/SKILL.md) | Calculates GDPR Art. 12(3) response deadlines, extension validity and overdue status for one request or a request log. |
| Sales | [`sales-pipeline-review`](departments/sales/skills/sales-pipeline-review/SKILL.md) | Calculates won to date, open and weighted pipeline in the period, coverage of the remaining target, stage ageing and per-deal flags, and lists the deals that decide the period. |
| Sales | [`sales-sales-forecast`](departments/sales/skills/sales-sales-forecast/SKILL.md) | Calculates commit, most likely and best case for the period from weighted pipeline, historical stage-to-win conversion and rep commit, with gaps and deal risks. |
| IT | [`it-access-review`](departments/it/skills/it-access-review/SKILL.md) | Matches system accounts to HR records and flags leavers, orphaned, shared, dormant, admin-on-daily and role-mismatch accounts, with attestation lists per department. |
| IT | [`it-asset-licence-review`](departments/it/skills/it-asset-licence-review/SKILL.md) | Calculates licence utilisation, unused licences, waste, duplicate tools and savings timed against renewal and notice deadlines. |
| Customer Service | [`cs-csat-nps-analysis`](departments/customer-service/skills/cs-csat-nps-analysis/SKILL.md) | Detects NPS or CSAT, calculates the score with a 95% interval, compares periods and segments only where samples allow, and counts English and Danish comment themes. |
| Customer Service | [`cs-sla-report`](departments/customer-service/skills/cs-sla-report/SKILL.md) | Calculates first response and resolution times in Danish business hours or calendar hours, with median, p90, SLA attainment by priority and channel, backlog age and a breach list. |
| Customer Service | [`cs-staffing-forecast`](departments/customer-service/skills/cs-staffing-forecast/SKILL.md) | Calculates required agents per interval with Erlang C (service level, ASA, occupancy cap) and converts agent hours to scheduled hours after shrinkage. |
<!-- AUTOTABLE:END -->

## Repository layout

```
catalogue/                 source of truth: one YAML file per department
facts/_parts/              source of the dated regulatory facts (assembled into facts/<dept>.md)
automation/<skill>/        calculation scripts, templates, tests and worked examples
departments/<dept>/
  README.md                pack overview, skill list, suggested workflows
  INSTALL.md               quick install routes for the pack
  .claude-plugin/          Claude Code plugin manifest
  skills/<skill-name>/
    SKILL.md               Agent Skills format
    PROMPT.md              portable instructions (8,000 character limit)
    references/facts.md    dated regulatory facts for the department
    scripts/ assets/ examples/   calculation tools (automated skills only)
dist/                      upload-ready zips: per skill, per pack, whole library
docs/                      install guides, platform matrix, responsible use, skill anatomy
scripts/                   build, validate, lint and package
install.sh, install.ps1    installers for local agent tools
```

## Built for Europe

Skills are written in British English, answer in the user's language and draft Danish texts for Danish recipients. They are EU and Denmark aware: GDPR, the AI Act, NIS2, pay transparency, consumer law, VAT and Danish rules such as ferieloven, funktionærloven, bogføringsloven and markedsføringsloven are referenced where they matter. Figures live in one dated facts file per department (`facts/`), so updates happen in one place. Notes are orientation, not legal advice, and every skill tells the AI to say what needs verifying. Read [responsible use](docs/responsible-use.md) before using HR, legal or monitoring skills in production.

## Changing or adding skills

Edit `catalogue/<department>.yaml`, then run:

```bash
python3 scripts/lint_catalogue.py && python3 scripts/build.py && python3 scripts/validate.py && python3 scripts/package.py
```

`validate.py` also runs the test suite of every calculation script.

```
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/skill-anatomy.md](docs/skill-anatomy.md).

## Licence

MIT, see [LICENSE](LICENSE). Created by Alexander Senderovitz ([senderovitz.eu](https://senderovitz.eu)).
