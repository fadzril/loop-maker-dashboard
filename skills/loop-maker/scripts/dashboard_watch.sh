#!/usr/bin/env bash
# Idle tick-listener: re-render the dashboard whenever the loop writes STATE.md.
#
# The loop's state write IS the tick — this watches that file and regenerates
# dashboard.html on every change. It's a deterministic renderer, NOT an LLM
# agent: rendering a board from a state file is a template fill, so an LLM here
# would burn tokens forever for zero benefit. Runs idle (blocks / sleeps) until
# the next tick.
#
# Two decoupled wirings exist for auto-update; use whichever fits the host:
#   1. inline  — the loop calls render_dashboard.py at the end of its write-state
#                step (default in the scaffolded SKILL.md; can't drift).
#   2. watcher — this script, for when you don't want to touch the loop's logic
#                or the loop runs on another host and only drops STATE.md here.
#
# Usage:
#   dashboard_watch.sh <STATE.md> [HUMAN-GATES.md] [dashboard.html]
#
# ponytail: fswatch when present (event-driven), else a 2s mtime poll. Bump the
# poll interval via LM_POLL if 2s is too chatty.

set -euo pipefail

STATE="${1:?usage: dashboard_watch.sh <STATE.md> [HUMAN-GATES.md] [out.html]}"
GATES="${2:-}"
OUT="${3:-$(dirname "$STATE")/dashboard.html}"
POLL="${LM_POLL:-2}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

render() {
  local args=(--state "$STATE" --out "$OUT")
  [ -n "$GATES" ] && args+=(--gates "$GATES")
  python3 "$HERE/render_dashboard.py" "${args[@]}" >/dev/null && echo "rendered -> $OUT"
}

render  # initial render on launch

if command -v fswatch >/dev/null 2>&1; then
  echo "watching $STATE via fswatch (Ctrl-C to stop)"
  fswatch -o "$STATE" | while read -r _; do render; done
else
  echo "watching $STATE via ${POLL}s mtime poll (install fswatch for event-driven; Ctrl-C to stop)"
  last=""
  while true; do
    cur="$(stat -f %m "$STATE" 2>/dev/null || stat -c %Y "$STATE" 2>/dev/null || echo x)"
    [ "$cur" != "$last" ] && { render; last="$cur"; }
    sleep "$POLL"
  done
fi
