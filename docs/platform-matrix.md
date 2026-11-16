# Platform matrix

How each platform uses this library, checked in November 2026. Platform features change often; confirm in the vendor's documentation if something does not match.

| Platform | Surface | Reads SKILL.md folders | Where skills live | Use PROMPT.md | Limits to know |
|---|---|---|---|---|---|
| Claude Code | Code / agent | Yes | `~/.claude/skills`, `.claude/skills`, or plugin marketplace | Not needed | None relevant |
| Claude apps | Chat | Yes (zip upload) | Skills section of settings | Optional, in Project instructions | One skill per zip |
| ChatGPT Skills | Chat | Yes (upload) | Skills → Create → Upload | Not needed | Plan and workspace admin settings |
| ChatGPT custom GPT or Project | Chat | No | Instructions field, Knowledge files | Yes | Instructions about 8,000 characters |
| OpenAI Codex | Code / agent | Yes | `~/.agents/skills`, `.agents/skills` (legacy `~/.codex/skills`) | Not needed | Skill list budget in context; disable unused skills |
| Gemini CLI | Code / agent | Yes | `~/.gemini/skills`, `.gemini/skills`, `.agents/skills` | Not needed | None relevant |
| Gemini app (Gems) | Chat | No | Gem instructions and Knowledge | Yes | Up to 10 knowledge files per Gem |
| GitHub Copilot | Code / agent | Yes | `~/.copilot/skills`, `.github/skills` (also reads `.claude/skills`) | Not needed | Agent mode, Copilot CLI or cloud agent |
| Microsoft 365 Copilot | Chat | No | Agent Builder or Copilot Studio instructions | Yes | Instructions 8,000 characters |

## Why two formats

`SKILL.md` uses progressive disclosure: the tool only reads each skill's name and description at first, and loads the full playbook when your request matches. That is why you can install all 168 skills without filling the model's context.

Chat assistants that do not support skills need the playbook in their instructions. `PROMPT.md` is the same content rewritten as instructions, under 8,000 characters, so it fits the strictest limit among the platforms above.

## Choosing a setup

- **One person, many tasks:** install the packs you need in a tool with native skills (Claude, ChatGPT Skills, Codex, Gemini CLI, GitHub Copilot).
- **A team using one task a lot:** build a dedicated custom GPT, Gem or Microsoft 365 Copilot agent from `PROMPT.md`, and add your own policies as knowledge.
- **A company standard:** fork this repository, adapt the catalogue to your policies and approval limits, rebuild, and distribute through your tool's admin or marketplace features.
