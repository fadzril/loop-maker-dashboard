#!/usr/bin/env bash
# loop-maker installer — copies the skills into your agent host's skills dir.
# Resolution: $LOOP_MAKER_SKILLS_DIR  >  ~/.claude/skills (Claude Code default)
# Usage: ./install.sh   (or LOOP_MAKER_SKILLS_DIR=/path ./install.sh)
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${LOOP_MAKER_SKILLS_DIR:-$HOME/.claude/skills}"
# review-ci reuses loop-maker's dashboard scripts by relative sibling path
# (../loop-maker/scripts/...), so both skills must land as siblings here.
SKILLS=(loop-maker review-ci)

mkdir -p "$SKILLS_DIR"
for name in "${SKILLS[@]}"; do
  SRC="$REPO_ROOT/skills/$name"
  DEST="$SKILLS_DIR/$name"
  echo "→ installing $name into $DEST"
  rm -rf "$DEST"
  mkdir -p "$DEST"
  cp -R "$SRC/." "$DEST/"
done
echo "✓ installed."
echo "  host skills dir: $SKILLS_DIR"
echo "  for non-Claude hosts set LOOP_MAKER_SKILLS_DIR to that host's skills path."
echo "  then describe an automate/schedule/monitor task, or run /loop-maker."
echo "  or drive a PR to green directly: /loop-maker:review-ci <owner/repo> <pr1>,<pr2>,..."
