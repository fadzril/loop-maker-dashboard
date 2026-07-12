#!/usr/bin/env bash
# Install the SHIPPED dashboard assets into a loop dir and print the exact
# run.sh wiring. Run this once at scaffold time so the loop uses the real
# renderer + template + server — NOT a hand-rolled dashboard.
#
# Why this exists: the dashboard is a fixed, deterministic asset. A wizard that
# hand-writes its own render function or ledger schema loses the layout, the
# grouping, the informative line items, and the served URL. Don't do that —
# run this instead.
#
# Usage: scaffold_dashboard.sh <loop-dir>
set -euo pipefail
DEST="${1:?usage: scaffold_dashboard.sh <loop-dir>}"
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$DEST"
cp "$SKILL/scripts/render_dashboard.py" \
   "$SKILL/scripts/serve_dashboard.sh" \
   "$SKILL/templates/dashboard.html.tmpl" "$DEST"/
chmod +x "$DEST/render_dashboard.py" "$DEST/serve_dashboard.sh"

cat <<'EOF'
Installed render_dashboard.py + serve_dashboard.sh + dashboard.html.tmpl.

Wire these into run.sh — do NOT hand-write a dashboard or a render function:

  SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  render(){ python3 "$SELF/render_dashboard.py" --state "$SELF/STATE.md" \
              --gates "$SELF/HUMAN-GATES.md" --prefix loop --out "$SELF/dashboard.html" >/dev/null; }
  # once at startup — prints the http URL (falls back to file:// with no python3):
  URL="$(bash "$SELF/serve_dashboard.sh" "$SELF" 2>/dev/null || echo "file://$SELF/dashboard.html")"
  echo "dashboard: $URL"
  # then call `render` after EVERY write to STATE.md.
  # (--prefix titles the board "loop: <state heading>"; use a sibling skill's
  #  own name as the prefix when it drives the loop, e.g. --prefix review-ci.)

STATE.md MUST use the canonical ledger columns so render_dashboard.py can read it
(group + item + status are required; ref/type/branch/pr are optional):

  | group | item | status | ref | type | branch | pr | notes |
Valid status tokens: pending · in-progress (running) · done · failed · skipped
(anything else renders as pending; put descriptive state in notes).

Map your task onto these columns — do not invent a different ledger schema:
  repo / phase / sub-loop -> group    subtask id (e.g. WEB-9903) -> ref
  base -> work branch     -> branch   NEW / REUSE                 -> type
  PR number or URL        -> pr       short caveat                -> notes
EOF
