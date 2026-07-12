# The review-output contract

`review-ci` calls out to whatever `review_command` your repo configures (a
skill, a slash command, a CI job — anything that reads a PR's diff and
returns findings). That command's output is **prose**, and its exact wording
is not standardized: two review commands, or even the same command's own
output as it evolves, can phrase "found problems" completely differently.
This file is the one thing that *is* standardized: the two fields
`verify_pr.sh` actually needs, and how to fill them in regardless of the
prose in front of you.

## The contract

After invoking `review_command` against a PR's current HEAD, record exactly
three things in `STATE.md`'s `## Review findings` table:

- `head_sha` — the exact commit you reviewed. If the PR moves again (a new
  push, a rebase), this row becomes stale automatically — `verify_pr.sh`
  checks the sha, not just the counts.
- `issues` — count of **blocking** findings. Must be `0` for the PR to be
  considered done.
- `notes` — count of **advisory** findings. Also must be `0` — this skill
  treats notes as blocking too (a note that never gets addressed just sits
  there forever otherwise).

There is **no required output string format**. Read whatever the review
command actually produced, in whatever shape it's in, and count.

## Two worked examples — same contract, different prose

**Format A** (a flat numbered list, no severity split):
```
Found 4 issues:

1. Missing nil check on `order.tax_group`
2. N+1 query in the vendor loop
3. ...
4. ...
```
→ record `issues: 4, notes: 0`. There's no separate "notes" concept in this
format — everything it lists is blocking by construction.

**Format B** (severity-split, explicit prefixes):
```
Found 2 issues, 1 note:

Issue 1. Missing nil check on `order.tax_group`
Issue 2. N+1 query in the vendor loop

Note 1. Consider extracting this into a helper
```
→ record `issues: 2, notes: 1`.

**Format B's clean cases** are two different strings that both start with
"No issues found." — read past the first sentence before concluding there's
nothing to do:
```
No issues found. Checked for bugs, security, ...           → issues: 0, notes: 0
No issues found. 1 note:\n\nNote 1. ...                     → issues: 0, notes: 1
```

The lesson from both examples: don't grep for a specific prefix string.
Read the output like a person would, and count.

## Escalation rule: never guess `0`

If the review command's output is genuinely ambiguous, truncated, or you
can't confidently tell whether it found anything, record `issues: unknown`
(not `0`). `verify_pr.sh`'s check is a strict string comparison against
`"0"` — `unknown` fails it, which routes to gate **G2** (verifier anomaly)
in `HUMAN-GATES.md` rather than silently passing a PR that was never
actually confirmed clean.

## What this does and doesn't protect against

The sha-pin protects against the specific failure this design was built to
fix: a fixed-format regex silently returning `0` against a differently
formatted review comment (a structural false pass, not a fluke — it happens
every time, not occasionally). Any push or rebase invalidates the prior
verdict regardless of whether its counts were ever read correctly.

It does **not** protect against a careless read — an agent that skims the
review output, decides "looks fine," and writes `0/0` when the output
actually said `Issue 1. ...`. That's a different, so-far-unobserved failure
mode. A documented future upgrade, if this ever shows up in practice: have
`verify_pr.sh` also fetch the raw review comment/output and do a loose
sanity check (e.g. does it contain the word "Issue" or "Found" anywhere)
against the recorded `0` count, flagging a mismatch rather than trusting it
blindly. Not built now — don't add it speculatively before it's a real
problem.

## The optional stale-comment marker

If `bot_marker` is configured, `review-ci` also deletes the review command's
own *prior* PR comment(s) before re-running it, to keep the comment thread
readable (matched by an exact prefix string, e.g. an org logo `<img>` tag).
This is unrelated to the contract above — it's thread hygiene, not
correctness. If `bot_marker` is left unset, this step is skipped entirely and
nothing about "done" changes: the sha-pinned record, not the comment thread,
is what actually gates completion.
