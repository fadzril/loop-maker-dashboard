# review-ci — Human Gates & Budget

> A loop without human gates can act in ways no one intended.
> A loop without a budget can run forever. Both sections below are required.

These gates and budget defaults are static — they don't vary per invocation.
What varies (repo, PR numbers, state path, iteration counters) lives in each
run's own `STATE.md`, under `## Config` and `## Last run`.

---

## Human gates

| # | Gate | Trigger condition | Who approves |
|---|------|-------------------|--------------|
| G1 | Pre-run sign-off | Before the very first live action (any push, rebase, label change, or comment delete/post) against a real (non-`--dry-run`) PR | Loop owner |
| G2 | Verifier anomaly | `verify_pr.sh` fails for a reason not covered by the allowed retry paths (review fix-iterate, CI fix/rerun-iterate) — includes a review verdict recorded as `unknown` | Loop owner |
| G3 | Rebase conflict | A `git rebase` onto a parent's updated branch produces a conflict the loop cannot resolve mechanically | Loop owner |
| G4 | CI escalation | A single PR exceeds `ci_iters_max` (default 5) CI-check iterations without reaching all-green | Loop owner |
| G5 | Review escalation | A single PR exceeds `review_iters_max` (default 5) review-fix iterations without clearing all issues + notes | Loop owner |
| G6 | CI failure relatedness unclear | A CI failure can't be confidently classified as "caused by this PR's change" vs. "unrelated/flaky/rerunnable" | Loop owner |
| G7 | Delete / overwrite | Before deleting any PR comment — only ever the review command's own comments (matched by the configured `bot_marker`, if any); a human reviewer's comment is never deleted | Loop owner |

<!-- G1 and G2 are unconditional; the rest are specific to this loop's domain. -->

### How to clear a gate

1. The loop writes a gate-request row to this run's `STATE.md` (gate ID, PR,
   reason, proposed action) and pauses.
2. The loop owner reviews and replies in-chat with an explicit go/no-go.
3. The loop records the decision in `STATE.md`, then continues (or stops, if
   declined).

Never self-approve — the loop must not treat its own review/CI output as a
gate clearance.

---

## Budget / stop

| Dimension | Limit | Action on breach |
|-----------|-------|-------------------|
| Token / session budget | `budget_pct_max` (default 70%) of the session's token budget | Halt + write `budget-exceeded` to STATE.md + notify the loop owner |
| CI-check iterations per PR | `ci_iters_max` (default 5) | Halt that PR's loop (G4) + notify; other PRs in the chain may continue if independent |
| Review-fix iterations per PR | `review_iters_max` (default 5) | Halt that PR's loop (G5) + notify |
| Wall-clock | No explicit cap — bounded by the token budget and per-PR iteration caps above | N/A |

### Why a hard stop is required

The loop cold-starts each iteration with no memory beyond `STATE.md`. The
token-spend field and the per-PR `review_iters`/`ci_iters` counters are the
only durable brakes — without them nothing stops the loop from repeatedly
force-pushing, re-triggering CI, or burning budget on a PR stuck on a
genuinely unresolvable finding. A fixed CI random seed can also turn a
"just needs another rerun" assumption into an infinite loop against a
deterministic (not flaky) failure — the CI-iteration cap is what actually
bounds that, not judgment calls made mid-loop.
