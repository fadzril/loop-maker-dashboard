#!/usr/bin/env bash
# Deterministic per-PR verifier for review-ci. No AI judgment here — only
# `gh`-observable facts plus a verdict the invoking agent already recorded.
#
# Two kinds of facts feed the "done" verdict:
#  (a) CI/label/mergeable — fetched live via `gh` as structured JSON. No
#      prose, no format-drift risk: checked directly.
#  (b) review-clean — NOT parsed from the raw PR comment here. Review-command
#      output is not standardized across repos (and can drift even within one
#      repo — e.g. an Issue-N./Note-N.-prefixed list vs. a flat numbered list
#      with no such prefix). A regex tuned to one format silently misreads
#      the other. Instead this reads back the sha-pinned verdict the invoking
#      agent already recorded in STATE.md's `## Review findings` table after
#      reading the review output itself (see references/review-output-contract.md).
#      A HEAD-sha mismatch is treated as "stale, re-review" regardless of the
#      recorded counts — that's what actually guards against a false pass.
#
# Usage: verify_pr.sh <STATE.md> <PR_NUMBER> [--repo <owner/repo>] [--label <name>]
# Exit:  0 = done (reviewed clean + CI green + mergeable)
#        1 = not done yet (iterate) — includes "no verdict recorded yet"
#        2 = misuse (bad args, missing state file, repo unresolvable, gh error)
set -euo pipefail

_trim() { sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'; }

# read_verdict <STATE.md> <PR_NUMBER>
# Prints "sha issues notes" for the most recently recorded row for this PR,
# or fails (empty stdout, non-zero exit) if no row exists yet. Pure text
# parsing, no `gh`/network dependency — this is the part covered by
# scripts/tests/test_verify_pr_parsing.sh.
read_verdict() {
  local state="$1" pr="$2"
  local row
  row=$(awk '
    /^##[[:space:]]/ { insec = ($0 ~ /## Review findings/) }
    insec && /^[[:space:]]*\|/ { print }
  ' "$state" | awk -F'|' -v pr="$pr" '
    {
      f2 = $2
      gsub(/^[ \t]+|[ \t]+$/, "", f2)
      if (f2 == pr) last = $0
    }
    END { if (last) print last }
  ')
  [ -n "$row" ] || return 1
  local sha issues notes
  sha=$(awk -F'|' '{print $3}' <<<"$row" | _trim)
  issues=$(awk -F'|' '{print $4}' <<<"$row" | _trim)
  notes=$(awk -F'|' '{print $5}' <<<"$row" | _trim)
  echo "$sha $issues $notes"
}

main() {
  local state="${1:-}" pr="${2:-}"
  if [ -z "$state" ] || [ -z "$pr" ]; then
    echo "usage: $0 <STATE.md> <PR_NUMBER> [--repo <owner/repo>] [--label <name>]" >&2
    exit 2
  fi
  shift 2

  local repo="" label="for ci"
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo) repo="$2"; shift 2 ;;
      --label) label="$2"; shift 2 ;;
      *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
  done

  [ -f "$state" ] || { echo "FAIL: state file not found: $state" >&2; exit 2; }

  if [ -z "$repo" ]; then
    repo="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
  fi
  [ -n "$repo" ] || { echo "FAIL: --repo not given and auto-detect failed" >&2; exit 2; }

  local pr_json
  pr_json=$(gh pr view "$pr" --repo "$repo" \
    --json headRefOid,mergeable,labels,statusCheckRollup 2>&1) || {
    echo "FAIL: gh pr view failed for #$pr: $pr_json" >&2
    exit 2
  }
  local head_sha mergeable has_label
  head_sha=$(jq -r '.headRefOid' <<<"$pr_json")
  mergeable=$(jq -r '.mergeable' <<<"$pr_json")
  has_label=$(jq -r --arg l "$label" '[.labels[].name] | any(. == $l)' <<<"$pr_json")

  # --- (a) review-clean: sha-pinned structured verdict from STATE.md ---
  local verdict recorded_sha issues notes
  if ! verdict=$(read_verdict "$state" "$pr"); then
    echo "FAIL: PR #$pr has no recorded review verdict in $state" >&2
    exit 1
  fi
  read -r recorded_sha issues notes <<<"$verdict"

  if [ "$recorded_sha" != "$head_sha" ]; then
    echo "FAIL: PR #$pr recorded verdict is for $recorded_sha, current HEAD is $head_sha — stale, re-review needed" >&2
    exit 1
  fi
  if [ "$issues" != "0" ] || [ "$notes" != "0" ]; then
    echo "FAIL: PR #$pr has $issues issue(s), $notes note(s) unresolved (sha $head_sha)" >&2
    exit 1
  fi

  # --- (b) label + CI + mergeable: live structured facts, no format risk ---
  if [ "$has_label" != "true" ]; then
    echo "FAIL: PR #$pr missing '$label' label" >&2
    exit 1
  fi
  local bad_checks
  bad_checks=$(jq -r \
    '[.statusCheckRollup[] | select(.status != "COMPLETED" or (.conclusion != "SUCCESS" and .conclusion != "NEUTRAL" and .conclusion != "SKIPPED"))] | length' \
    <<<"$pr_json")
  if [ "$bad_checks" -gt 0 ]; then
    echo "FAIL: PR #$pr has $bad_checks check(s) not green (sha $head_sha)" >&2
    exit 1
  fi
  if [ "$mergeable" != "MERGEABLE" ]; then
    echo "FAIL: PR #$pr mergeable=$mergeable" >&2
    exit 1
  fi

  echo "PASS: PR #$pr reviewed clean (sha-matched) + CI green + mergeable (sha $head_sha)"
}

# Guard so scripts/tests/test_verify_pr_parsing.sh can source this file and
# call read_verdict() directly without gh/network or triggering main().
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
