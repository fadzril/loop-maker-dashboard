#!/usr/bin/env bash
# loop-maker installer — copies the skill into your agent host's skills dir.
# Resolution: $LOOP_MAKER_SKILLS_DIR  >  ~/.claude/skills (Claude Code default)
# Usage: ./install.sh   (or LOOP_MAKER_SKILLS_DIR=/path ./install.sh)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${LOOP_MAKER_SKILLS_DIR:-$HOME/.claude/skills}"
DEST="$SKILLS_DIR/loop-maker"

mkdir -p "$SKILLS_DIR"
echo "→ installing loop-maker into $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$REPO_ROOT/SKILL.md" "$REPO_ROOT/references" "$REPO_ROOT/scripts" "$REPO_ROOT/templates" "$DEST/"
echo "✓ installed."
echo "  host skills dir: $SKILLS_DIR"
echo "  for non-Claude hosts set LOOP_MAKER_SKILLS_DIR to that host's skills path."
echo "  then describe an automate/schedule/monitor task, or run /loop-maker."
