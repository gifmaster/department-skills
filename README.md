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

Every skill ships in two formats, generated from the same source:

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

## Repository layout

```
catalogue/                 source of truth: one YAML file per department
departments/<dept>/
  README.md                pack overview, skill list, suggested workflows
  INSTALL.md               quick install routes for the pack
  .claude-plugin/          Claude Code plugin manifest
  skills/<skill-name>/
    SKILL.md               Agent Skills format
    PROMPT.md              portable instructions (8,000 character limit)
dist/                      upload-ready zips: per skill, per pack, whole library
docs/                      install guides, platform matrix, responsible use, skill anatomy
scripts/                   build, validate, lint and package
install.sh, install.ps1    installers for local agent tools
```

## Built for Europe

Skills are written in British English and are EU and Denmark aware: GDPR, the AI Act, NIS2, pay transparency, consumer law, VAT and Danish rules such as ferieloven, funktionærloven, bogføringsloven and markedsføringsloven are referenced where they matter. Notes are orientation, not legal advice, and every skill tells the AI to say what needs verifying. Read [responsible use](docs/responsible-use.md) before using HR, legal or monitoring skills in production.

## Changing or adding skills

Edit `catalogue/<department>.yaml`, then run:

```bash
python3 scripts/lint_catalogue.py && python3 scripts/build.py && python3 scripts/validate.py && python3 scripts/package.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/skill-anatomy.md](docs/skill-anatomy.md).

## Licence

MIT, see [LICENSE](LICENSE). Created by Alexander Senderovitz ([senderovitz.eu](https://senderovitz.eu)).
