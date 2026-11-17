# Reference content spec

A content pack adds reference material to one skill so the AI works from vetted text instead of memory.
Folder: content/<skill-name>/ (skill-name exactly as in departments/*/skills/<skill-name>)

- references/<name>.md : Markdown reference files (playbooks, clause banks, letter templates, checklists, decision trees).
  * First line must be a level-1 heading, followed by ONE line starting with "Use: " that says when the assistant should read it (shown in SKILL.md).
  * Practical and specific: positions with preferred / fallback / red line, ready-to-use template text with [placeholders], checklists that can be ticked.
  * Danish templates in correct, natural Danish (du-form for consumers and employees unless formal De is clearly expected; standard Danish business letter conventions). English versions where the skill is used in English too.
  * Legal statements consistent with facts/<dept>.md in the repo; cite the act and section; mark anything you could not verify at a primary source with "(verify)". Never invent section numbers.
  * Under 400 lines per file.
- assets/<name>.csv or .md : optional fill-in templates (for example a register with the right columns).

Rules: British English for English text, no em or en dashes anywhere, no real people or companies (fictional examples only). Edit only inside content/<skill-name>/. Do not edit catalogue/, departments/, scripts/ or facts/. Do not run git commands.
