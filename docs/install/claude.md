# Install in Claude

Claude reads `SKILL.md` folders natively. Skills load automatically when your request matches their description.

## Claude Code (terminal, VS Code, JetBrains, desktop)

### Option A: plugin marketplace (recommended)

Each department is a plugin in this repository's marketplace.

```
/plugin install hr-skills --marketplace gifmaster/department-skills
/plugin install legal-skills --marketplace gifmaster/department-skills
```

On Claude Code versions before 2.1.275, add the marketplace first and then install by name:

```
/plugin marketplace add gifmaster/department-skills
/plugin install hr-skills@department-skills
```

Available plugins: `hr-skills`, `finance-skills`, `supply-chain-skills`, `legal-skills`, `sales-skills`, `marketing-skills`, `it-skills`, `customer-service-skills`. Update later with `/plugin marketplace update department-skills`.

### Option B: copy folders

Personal skills (all projects):

```bash
./install.sh claude hr finance          # macOS or Linux
.\install.ps1 claude hr finance          # Windows PowerShell
```

This copies the skill folders into `~/.claude/skills/`. For one project only, copy the folders into `.claude/skills/` inside that project and commit them, so your team gets them too.

Check that Claude sees them: ask *"Which skills do you have for HR?"* or type `/` to browse.

## Claude apps (web, desktop, mobile)

1. Make sure skills are enabled for your account. On Team and Enterprise plans an owner may need to allow them.
2. Download the zip for the skill you want from [`dist/skills/`](../../dist/skills/) (for example `legal-nda-review.zip`), or a whole pack from [`dist/packs/`](../../dist/packs/) and unzip it to get the individual skill folders.
3. Open the Skills section in Claude's settings and upload the zip. Upload one skill per zip.
4. Start a new chat and ask for the task. Claude loads the skill when relevant.

Tip: in a Claude Project, you can also add a skill's `PROMPT.md` to the project instructions if you want it always on for that project.

## Claude API and Agent SDK

Skills can be uploaded through the Skills API and attached to requests, or placed in the skills directory used by the Agent SDK. See Anthropic's documentation at [docs.claude.com](https://docs.claude.com) for the current endpoints and beta headers.

## Troubleshooting

- **Skill does not trigger:** name it in your request, for example *"use legal-nda-review"*. Descriptions are written to trigger on common phrasings, but explicit names always work.
- **Name clash:** every skill name starts with a department prefix (`hr-`, `fin-`, `scm-`, `legal-`, `sales-`, `mkt-`, `it-`, `cs-`), so they will not overwrite skills from other sources unless those use the same names.
- **Cross-references:** some skills point to a skill in another pack (for example HR points to `it-end-user-guide`). Install that pack too if you want the hand-off to work.
