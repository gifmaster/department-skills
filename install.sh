#!/usr/bin/env bash
# Install department skills for agent tools that read SKILL.md folders.
#
# Usage: ./install.sh <target> [department ...]
#   target:      claude | copilot | gemini | codex | agents | all
#   department:  hr finance supply-chain legal sales marketing it customer-service (default: all)
#
# Examples:
#   ./install.sh claude hr legal       # HR and Legal packs into ~/.claude/skills
#   ./install.sh copilot               # every pack into ~/.copilot/skills
#   SKILLS_DIR=./.github/skills ./install.sh custom finance   # any folder you choose
#
# Existing skills with the same name are replaced. Nothing else is touched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"
shift || true

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
[ -z "$TARGET" ] && usage

dir_for() {
  case "$1" in
    claude)  echo "$HOME/.claude/skills" ;;
    copilot) echo "$HOME/.copilot/skills" ;;
    gemini)  echo "$HOME/.gemini/skills" ;;
    codex|agents) echo "$HOME/.agents/skills" ;;
    custom)  [ -n "${SKILLS_DIR:-}" ] || { echo "Set SKILLS_DIR for the custom target" >&2; exit 1; }; echo "$SKILLS_DIR" ;;
    *) echo "Unknown target: $1" >&2; usage ;;
  esac
}

if [ "$#" -eq 0 ]; then
  set -- $(ls "$ROOT/departments")
fi

for d in "$@"; do
  [ -d "$ROOT/departments/$d/skills" ] || { echo "Unknown department: $d" >&2; exit 1; }
done

if [ "$TARGET" = "all" ]; then targets="claude copilot gemini codex"; else targets="$TARGET"; fi

for t in $targets; do
  dest="$(dir_for "$t")"
  mkdir -p "$dest"
  count=0
  for d in "$@"; do
    for s in "$ROOT/departments/$d/skills"/*/; do
      name="$(basename "$s")"
      rm -rf "${dest:?}/$name"
      cp -R "$s" "$dest/$name"
      count=$((count + 1))
    done
  done
  echo "Installed $count skills into $dest"
done
echo "Restart your agent (or start a new session) so it picks up the new skills."
