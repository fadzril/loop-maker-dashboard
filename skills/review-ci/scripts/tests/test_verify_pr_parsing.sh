#!/usr/bin/env bash
# scripts/tests/test_verify_pr_parsing.sh
# Exercises read_verdict() from verify_pr.sh directly — the STATE.md-table
# parsing logic, with no `gh`/network dependency. The gh-dependent half
# (live CI/label/mergeable checks) isn't unit-testable here; that's covered
# by the live dry-run smoke test in the plan's verification section instead.
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
check() { if [ "$1" = "$2" ]; then echo "  ✓ $3"; else echo "  ✗ $3 (got '$1' want '$2')"; fail=1; fi; }

# shellcheck source=/dev/null
source "$DIR/verify_pr.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
state="$tmp/STATE.md"

cat > "$state" <<'EOF'
# review-ci: acme/widgets #101,102 — State Ledger

## Config
repo             : acme/widgets
prs (chain order): 101,102

## Ledger
| group | item | status | ref | type | branch | pr | notes |
|-------|------|--------|-----|------|--------|----|-------|
| PR chain | 1. Widget fix | done | | | master → fix | #101 | |

## Review findings
| pr | head_sha | issues | notes | reviewed_at | source |
|----|----------|--------|-------|-------------|--------|
| 101 | aaa111 | 2 | 1 | 2026-07-01T10:00Z | review-command |
| 101 | bbb222 | 0 | 0 | 2026-07-01T11:00Z | review-command |
| 103 | ccc333 | 0 | 0 | 2026-07-01T12:00Z | review-command |

## Last run
```
timestamp : 2026-07-01T11:00Z
iteration : 2
outcome   : ok
exit code : 0
token_spend_pct : 5
```
EOF

# Most recent row for PR 101 wins (bbb222/0/0), not the earlier aaa111/2/1 row.
verdict="$(read_verdict "$state" 101)"
check "$verdict" "bbb222 0 0" "most recent row for a PR wins over an earlier one"

# A PR with no row at all fails (empty result, non-zero return).
if read_verdict "$state" 999 >/dev/null 2>&1; then
  check "found" "not-found" "PR with no recorded row returns failure"
else
  check "not-found" "not-found" "PR with no recorded row returns failure"
fi

# A different PR's row is not confused with this one (no substring matching).
verdict103="$(read_verdict "$state" 103)"
check "$verdict103" "ccc333 0 0" "distinct PRs' rows are not conflated"

# Sha mismatch is detected by the caller (main()), not read_verdict() itself —
# read_verdict just returns whatever sha was recorded; verify that plainly.
read -r sha issues notes <<<"$(read_verdict "$state" 101)"
check "$sha" "bbb222" "recorded sha is returned verbatim for the caller to compare"
check "$issues" "0" "issues field parsed correctly"
check "$notes" "0" "notes field parsed correctly"

[ "$fail" = "0" ] && echo "ALL PASS" || { echo "FAILURES"; exit 1; }
