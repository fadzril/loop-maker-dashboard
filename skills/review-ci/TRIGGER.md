# review-ci — Trigger Definition

> Host-agnostic launch contract. This loop is **manual, run-until-done** —
> no cron, no webhook. It runs for as long as the session lasts, iterating
> until the goal predicate holds for every PR passed in, or a budget/gate
> stop trips first.

---

## Verifiable goal

> Every PR passed in simultaneously satisfies: (a) the sha-pinned review
> verdict recorded in this run's `STATE.md` for its current HEAD shows 0
> issues and 0 notes, (b) the configured CI-trigger label is applied and
> every check for HEAD is COMPLETED and green, (c) `mergeable == MERGEABLE`.

---

## State file

```
loops/review-ci/<owner>__<repo>/<pr1>-<pr2>-...-<prN>/STATE.md
```

Read at the start of every iteration, written at the end. Path is derived
from the repo and the PR set passed to the invocation — see `SKILL.md`'s
"State path convention" section. Same repo + PR set → same path → resumes
exactly where the last run left off.

---

## Launch prompt

> Read `<state-path>/STATE.md` (if it exists) and the `review-ci` skill,
> then continue driving `<owner>/<repo>` PRs `<pr1>,<pr2>,...` to done per
> the loop's `SKILL.md`. Stop at any open gate in `HUMAN-GATES.md`.

## Claude Code

```
/loop-maker:review-ci <owner/repo> <pr1>,<pr2>,...
```

> **Flag:** verify this invocation syntax against your current Claude Code
> version — slash-command and skill-dispatch surfaces change across
> releases. See `references/host-adapters.md` in the sibling `loop-maker`
> skill.

No `/loop` interval is used — this is a single continuous run, not a
recurring trigger. If the session ends before the goal predicate holds,
re-invoke with the same repo + PR set in a fresh session; `STATE.md` picks
up exactly where the last run left off.

---

## Trigger notes

- G1 (pre-run sign-off) in `HUMAN-GATES.md` must be explicitly cleared
  before the first real (non-`--dry-run`) push/rebase/label/comment action —
  this is not implicit in having invoked the skill.
- The token-budget stop and the per-PR iteration caps (G4/G5) in
  `HUMAN-GATES.md` take precedence over "keep going until green" — hitting
  either halts the loop regardless of how close the goal predicate looks.
- Use `--dry-run` for a first pass against any new repo or review command —
  it exercises discovery, the review invocation, and the verifier without
  touching the actual PR.
