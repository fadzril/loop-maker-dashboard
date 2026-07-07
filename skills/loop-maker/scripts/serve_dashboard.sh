#!/usr/bin/env bash
# Serve the loop's dashboard over localhost and print its URL. Idempotent:
# reuses an already-running server for this loop dir (safe to call at the start
# of every run). Binds to 127.0.0.1 only — the board is not exposed to the LAN.
#
# Exit codes: 0 = serving, URL on stdout · 3 = python3 unavailable (caller
# should fall back to publishing dashboard.html as a Claude Artifact).
#
# Usage: serve_dashboard.sh [dashboard-dir] [base-port]
#   dashboard-dir defaults to the script's own dir (where dashboard.html lives).
#   base-port defaults to $LM_PORT or 8787; the next free port is used if busy.
#
# Stop it later with:  kill "$(cat <dir>/.dashboard-serve.pid)"
set -euo pipefail
DIR="$(cd "${1:-$(dirname "${BASH_SOURCE[0]}")}" && pwd)"
BASE_PORT="${2:-${LM_PORT:-8787}}"
PIDFILE="$DIR/.dashboard-serve.pid"
URLFILE="$DIR/.dashboard-url"

# Reuse a live server already serving this dir.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
  cat "$URLFILE" 2>/dev/null && exit 0
fi

command -v python3 >/dev/null 2>&1 || {
  echo "python3 not found — fall back to publishing dashboard.html as a Claude Artifact" >&2
  exit 3
}

# Pick the first free port at/after BASE_PORT. ponytail: tiny TOCTOU between the
# bind test and http.server binding — negligible for a local dev server.
port="$(python3 - "$BASE_PORT" <<'PY'
import socket, sys
base = int(sys.argv[1])
for p in range(base, base + 50):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p)); s.close(); print(p); break
    except OSError:
        continue
else:
    sys.exit(1)
PY
)" || { echo "no free port near $BASE_PORT" >&2; exit 3; }

# --directory keeps cwd clean; --bind 127.0.0.1 keeps it localhost-only. (3.7+)
nohup python3 -m http.server "$port" --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
echo $! > "$PIDFILE"
URL="http://127.0.0.1:$port/dashboard.html"
echo "$URL" > "$URLFILE"
echo "$URL"
