---
name: review-ci
description: >
  Drives a GitHub PR (or a stacked chain of PRs) to reviewed-clean and green
  CI: rebases each PR onto its updated parent, runs your repo's code-review
  command, folds every fix into one commit, applies the CI-trigger label,
  watches CI (distinguishing genuine failures from flaky/cancelled ones), and
  repeats until every PR is reviewed-clean + CI-green + mergeable — or a human
  gate/budget cap trips. Trigger on: drive a PR to green, get PRs merged,
  review and fix a pull request, land a stacked PR chain, babysit CI — even
  if you never say the word "loop".
---

# review-ci

Ready-to-run — not a wizard. Invoke with a repo and one or more PR numbers and
it starts immediately, using sensible built-in defaults. Sibling skill to
`loop-maker`: it reuses `loop-maker`'s dashboard tooling by relative path and
**requires `loop-maker` installed alongside it** (same plugin, or same
`$SKILLS_DIR` for a portable install). It does not scaffold a new skill per
run — one `STATE.md` per repo+PR-set is all that's per-invocation.

---

## Goal

**Exit predicate:** every PR passed in simultaneously satisfies: (a) the
sha-pinned review verdict recorded in this run's `STATE.md` for the PR's
current HEAD shows 0 issues and 0 notes, (b) the configured CI-trigger label
is applied and every check for HEAD is COMPLETED with a SUCCESS/NEUTRAL/
SKIPPED conclusion, (c) `mergeable == MERGEABLE`.

The loop runs until this holds for every PR passed in, or a gate in
`HUMAN-GATES.md` trips first.

---

## Invocation

```
/loop-maker:review-ci [<owner/repo>] <pr1>,<pr2>,...  [--flag=value ...]
```

> **Flag:** verify this argument-parsing convention against current Claude
> Code docs before relying on it — Skills (unlike custom slash commands with
> `$ARGUMENTS`/`$1` templating) receive the invocation's trailing text as
> plain conversational input, so this skill parses it in prose rather than
> via templated substitution. See `references/host-adapters.md` in the
> sibling `loop-maker` skill for the general host-command-surface caveat.

Parsing:
- The first token shaped like `\S+/\S+` is the repo. If no such token is
  given, auto-detect via `gh repo view --json nameWithOwner -q .nameWithOwner`
  in the current working directory.
- The remaining comma- or space-separated integers are PR numbers, **given in
  chain order** (parent first, then each child) — required, no default. A
  single PR is a chain of one; nothing about this skill assumes more than one.
- `--flag=value` tokens override config (table below). Unrecognized flags are
  an error — ask the user rather than silently ignoring them.

### Config

Resolved once on the first run for a given repo+PR-set and written to this
run's `STATE.md` under `## Config`; read back (never re-asked) on every later
run against the same state file. Priority: explicit `--flag` this invocation
→ value already recorded in `STATE.md` → auto-detect → built-in default.

| Field | Default | Auto-detect | Override |
|---|---|---|---|
| `repo` | — | `gh repo view --json nameWithOwner` | first arg |
| `prs` | — | — (required) | comma/space list, chain order |
| `review_command` | — | if exactly one installed skill/command name matches `*review*`, use it silently | `--review-command=` |
| `ci_label` | `for ci` | — | `--ci-label=` |
| `bot_marker` | _(unset)_ | — | `--marker=` |
| `review_iters_max` | `5` | — | `--review-iters=` |
| `ci_iters_max` | `5` | — | `--ci-iters=` |
| `budget_pct_max` | `70` | — | `--budget-pct=` |
| `dry_run` | `false` | — | `--dry-run` |

`review_command` is the **only** field allowed to prompt the user: if 0 or 2+
installed skills/commands match `*review*`, ask which one to use before
proceeding — guessing wrong here poisons every downstream step (a wrong
command means every "reviewed clean" verdict this loop records is meaningless).
Every other field has a safe default or auto-detects without asking.

If a later invocation passes a `--flag` that conflicts with what's already
recorded in `STATE.md`'s `## Config`, write a one-line `WARN` note rather than
silently overriding — the human should notice their override didn't apply
the way they expected, or confirm it should.

`bot_marker` (a literal string prefix identifying the review command's own
comments, e.g. an org logo `<img>` tag at the top of its output) is optional.
If unset, skip the stale-own-comment cleanup step below — it's a nice-to-have
for keeping a PR's comment thread tidy, not load-bearing for correctness (the
sha-pinned verdict in `STATE.md`, not comment-thread state, is what actually
gates "done").

---

## First run — initialize state

State path (see "State path convention" below) — if the file doesn't exist,
create it with this skeleton before doing anything else:

```
<!-- changing state — read & written every run; never moved into SKILL.md. -->
# review-ci: {owner}/{repo} #{prs} — State Ledger

## Config
repo             : {owner}/{repo}
prs (chain order): {pr1},{pr2},...
review_command   : {resolved}
ci_label         : {label}
bot_marker       : {marker, or "(none — stale-comment cleanup skipped)"}
review_iters_max : 5
ci_iters_max     : 5
budget_pct_max   : 70

## Ledger
| group | item | status | ref | type | branch | pr | notes |
|-------|------|--------|-----|------|--------|----|-------|
| PR chain | 1. {PR title} | pending | | | {base} → {head} | #{pr1} | |

## Review findings
| pr | head_sha | issues | notes | reviewed_at | source |
|----|----------|--------|-------|-------------|--------|

## Last run
```
timestamp : (not yet run)
iteration : 0
outcome   : —
exit code : —
token_spend_pct : 0
```

## Gate log
| gate | pr | reason | status |
|------|----|--------|--------|
```

One `## Ledger` row per PR, in chain order, `branch` as `base → head` (fill
in the real base/head branch names once discovered in step 2 below).

### State path convention

```
loops/review-ci/<owner>__<repo>/<pr1>-<pr2>-...-<prN>/STATE.md
```

using the PR numbers **sorted ascending** for the directory name (stable
regardless of the order they were passed this invocation — the actual
chain-processing order lives in `## Config`, set once on the first run).
Created inside the invoking project's own working tree, never inside this
plugin's own repo. Same repo + same PR set → same path → a later invocation
resumes exactly where the last one left off. A different repo or PR set gets
its own path — no collision, by construction.

Out of scope for now (YAGNI): resuming against a *partially overlapping* PR
set from a prior run. If that's ever needed, add an explicit `--state=<path>`
override rather than building fuzzy overlap-detection speculatively.

Before the first live action against real PRs (any push, rebase, label
change, or comment delete/post), clear gate **G1** in `HUMAN-GATES.md`.

---

## Pattern: ReAct + deterministic verifier

Each iteration, for the **current PR** (first non-`done` PR in chain order):

1. **Read state** — this PR's `## Ledger` row (status, branch) and
   `## Review findings` row (last recorded verdict + sha), plus the
   `review_iters`/`ci_iters` counters kept alongside its ledger row's notes.
2. **Discover** — `gh pr view <PR> --repo <repo> --json headRefName,baseRefName,mergeable,labels,statusCheckRollup`.
   Also check whether the PR's *base* branch HEAD moved since last seen
   (i.e. its parent in the chain changed) — if so, it needs a rebase first.
3. **Act**:
   a. **Rebase if the parent moved.** `git fetch origin`, checkout this PR's
      head branch. If the true fork point differs from what GitHub reports
      as `baseRefOid` (common once a parent has itself been rebased), use
      `git rebase --onto <new-parent-tip> <old-fork-point> <this-branch>`
      rather than a plain `git rebase origin/<base>` — verify the fork point
      first with `git merge-base`. After a successful rebase, verify tree
      content is unchanged (`git diff <old-tip> <new-tip>` should be empty
      apart from the parent's own changes) before pushing. On conflict:
      **do not resolve it blindly** — that's gate **G3**, pause and ask.
      On success: `git push --force-with-lease`.
   b. **Clean up stale review comments**, only if `bot_marker` is configured:
      delete this PR's own prior comment(s) whose body starts with
      `bot_marker` (exact prefix match). **Never** delete, edit, or treat as
      stale a comment from a human reviewer — a human's comment gets
      addressed by fixing the code, never removed (gate **G7** if unsure
      whether a comment is "ours").
   c. **Run the review.** Invoke `review_command` against this PR's current
      HEAD. Read whatever it outputs — the format is not standardized (see
      `references/review-output-contract.md`) — and record the verdict:
      write a row to `STATE.md`'s `## Review findings` table with this PR,
      the **exact HEAD sha you just reviewed**, the issue count, the note
      count, a timestamp, and `review_command` as `source`. If the review
      output is ambiguous or you cannot confidently extract counts, record
      `issues: unknown` — **never guess `0`.**
   d. **Fix findings.** If issues + notes > 0: fix the flagged code, then
      **fold every fix commit made this pass into exactly ONE commit** on
      top of the pre-fix HEAD (`git reset --soft <pre-fix-HEAD> && git commit`,
      or `git commit --amend` if there's only one fix commit already) — do
      not rewrite history below that point, and do not accumulate multiple
      incremental fix commits. This matters specifically because a child PR
      in the chain will later rebase onto this branch — one clean commit per
      PR keeps that rebase simple; a pile of fixup commits does not.
      `git push --force-with-lease`. Increment `review_iters`.
      - If `review_iters` exceeds `review_iters_max` with findings still
        unresolved → gate **G5**, pause, notify the human. Do not keep
        iterating past the cap even if the remaining finding looks minor.
   e. **Apply the CI label** once review is clean for the current HEAD (0
      issues, 0 notes recorded against it): add `ci_label` if not already
      present. Leave it in place afterward — do not toggle it off and back on.
   f. **Watch CI.** `gh pr checks <PR> --watch`, or trigger/track the actual
      workflow run via `gh run watch <run-id> --exit-status`, until every
      check for this HEAD sha is COMPLETED.
      - All green → proceed to step 4.
      - Any non-green check: don't assume — classify it first. Check the
        job's actual conclusion, e.g. `gh api repos/<repo>/actions/jobs/<id> --jq '.conclusion'`.
        A `cancelled` conclusion usually means a sibling job's failure
        triggered fail-fast cancellation, not a real failure of *this* job —
        inspect the sibling that actually failed instead. A genuine
        `failure` needs its log read to decide: caused by this PR's change
        (fix the code, fold, push, re-watch — increment `ci_iters`) vs.
        unrelated/flaky/safely re-runnable (rerun via `gh run rerun <run-id>`,
        increment `ci_iters`). If you can't confidently tell which case
        applies, that's gate **G6** — do not guess.
      - If `ci_iters` exceeds `ci_iters_max` without going green → gate
        **G4**, pause, notify the human. A fixed CI random seed can make a
        failure fully deterministic rather than flaky — reruns alone will
        never turn a deterministic failure green; check for that pattern
        (does the exact same job/spec fail identically every time?) before
        assuming "just needs another rerun" and burning the iteration cap.
4. **Verify** — run `scripts/verify_pr.sh <STATE.md> <PR> --repo <repo> --label <ci_label>`.
   Exit 0 → this PR is done, advance to the next PR in chain order. Exit 1 →
   not done yet (this also covers "no verdict recorded yet," e.g. before step
   3c has run once) — loop back to step 3 for this PR. Exit 2 → genuine
   misuse (bad arguments, missing state file, repo unresolvable, `gh` error)
   — fix the invocation rather than treating it as a normal iteration.
5. **Write state** — update this PR's `## Ledger` row (status, notes with
   counters) and `## Last run` block. Do this *after* the verifier runs, not
   before.
6. **Refresh the dashboard**:
   ```
   python3 <this-skill-dir>/../loop-maker/scripts/render_dashboard.py \
     --state <state-dir>/STATE.md \
     --gates <this-skill-dir>/HUMAN-GATES.md \
     --out   <state-dir>/dashboard.html
   ```
   On the very first run for a new state dir, first install the dashboard
   triad if it isn't already present:
   ```
   bash <this-skill-dir>/../loop-maker/scripts/scaffold_dashboard.sh <state-dir>
   bash <this-skill-dir>/../loop-maker/scripts/serve_dashboard.sh <state-dir>
   ```
   (`serve_dashboard.sh` is idempotent — safe to call every run; it just
   re-prints the cached URL if already serving. Falls back to publishing
   `dashboard.html` as a Claude Artifact if it exits non-zero, e.g. no
   `python3` available.)
7. **Budget check** — if token spend recorded in `STATE.md` reaches
   `budget_pct_max`, halt immediately regardless of how close the goal
   predicate looks, write `budget-exceeded`, and notify the human.
8. **Check exit predicate** — if every PR passed in is `done`, stop and
   write a final summary to `STATE.md`. Otherwise repeat from step 1 for the
   next non-`done` PR.

Never retry silently outside the explicitly allowed cases above (rebase
after a parent moved, review fix-iterate under the cap, CI fix/rerun-iterate
under the cap). Anything else is an anomaly — gate **G2**, halt and surface
it.

---

## `--dry-run` mode

When `dry_run` is set: still do discovery (step 2) and still invoke the
review command and record its verdict (step 3c) — reading is safe — but skip
every mutating action: no push, no rebase, no label changes, no comment
deletes. Still call `verify_pr.sh` and refresh the dashboard, so a dry run
produces a real, inspectable `STATE.md` and dashboard without touching the
actual PRs. Use this to smoke-test the skill against a disposable PR before
trusting it against a real chain.

---

## Human gates and budget

See `HUMAN-GATES.md` (shipped statically alongside this skill — the gate list
and default caps don't vary per invocation; only the repo/PR-set/state-path
do, and those live in this run's own `STATE.md`). Clear gate **G1** before the
very first live (non-dry-run) action against real PRs.

---

## What "done" means

- Every PR passed in shows `status: done` in this run's `STATE.md` ledger.
- Each PR's most recent `verify_pr.sh` run for its current HEAD sha returned
  exit 0.
- No open (unresolved) row in the `## Gate log`.

At that point, write a final summary to `STATE.md` and stop.
