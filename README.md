# loop-maker

A portable agent plugin — works in Claude Code, Codex, Hermes, and OpenClaw — with two skills:

- **`loop-maker`** interviews you and scaffolds a self-running autonomous loop, complete with verifier, state file, and human gate, so you don't build one wrong.
- **`review-ci`** is ready-to-run, no interview: point it at a GitHub PR (or a stacked chain of them) and it drives each one to reviewed-clean and green CI.

## Why most loops go wrong

- Forgot to write a separate verifier (the agent judged its own work)
- Leaked changing state into the skill file (the loop lost memory between runs)
- Shipped a loop with no stop condition (it ran forever and burned budget)

`loop-maker` catches all three before you write a line.

## Here's what it'll ask you

```
🛠 To build a loop, it asks you 7 things — one at a time:
 1. Goal        — what checkable condition means "done for now"? (a true/false test, not a vibe)
 2. Trigger     — what starts each run: a schedule, an event, or run-until-done?
 3. Discovery   — how does it find the work to do each round?
 4. Action      — what's it allowed to do, and through which tools?
 5. Verification— who checks the result, and against what? (a separate judge)
 6. State       — where does "what's done / what's left" live, outside the chat?
 7. Human gate  — which actions are irreversible and must ask you first?
```

## At a glance

| | |
|---|---|
| **What it does** | Runs a 7-question wizard; catches missing verifiers, state leaks, and runaway loops before scaffold |
| **What you get** | A ready-to-run loop folder: `SKILL.md` + `STATE.md` + verifier script + stop condition wired in, plus an auto-updating `dashboard.html` that re-renders from the state file on every tick |
| **How you start** | `/loop-maker`, or just describe an automate/schedule/monitor task — fires without the word "loop" |
| **Install** | `claude plugin marketplace add fadzril/loop-maker-dashboard` then `claude plugin install loop-maker@loop-maker-dashboard` — or see Install below |

## Wizard UX

```
Q3/7  ▓▓▓░░░░  43%
---
🎙 elicit  →  🔎 survey  →  🎯 select  →  🏗 scaffold
(you are here: 🎯 select)
---
┌─ LOOP BLUEPRINT ───────────────────────────────────┐
│ GOAL      ✓ verifiable                             │
│ TRIGGER   schedule · 08:00                         │
│ VERIFY    ✓ separate script                        │
│ STATE     loops/<name>/STATE.md                    │
│ GATES     merge = human · budget 25/run            │
└────────────────────────────────────────────────────┘
```

The progress bar, breadcrumb, and blueprint box are rendered live by `scripts/loop_progress.py` — a zero-dep Python 3 helper that ships with the skill.

## Flow

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  elicit  │────▶│  survey  │────▶│  select  │────▶│ scaffold │
  │  7 Qs    │     │  gap     │     │  confirm │     │  write   │
  │  one-by  │     │  check   │     │  loop    │     │  files   │
  │  one     │     │  + warn  │     │  shape   │     │  + test  │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
       │                │                                   │
  progress bar     flags leaky        human reviews     loop ready
  Qx/7 rendered    state / missing    blueprint box     to invoke
                   verifier / no stop
```

## review-ci — drive a PR chain to reviewed-clean + green CI

No interview, no scaffolding step — point it at a repo and PR number(s) and it
runs immediately with sensible defaults (5 CI-check iterations, 5 review-fix
iterations, 70% token budget before it stops and asks a human).

```
/loop-maker:review-ci <owner/repo> <pr1>,<pr2>,...
```

Each iteration it rebases the PR onto its updated parent (for a stacked
chain), runs your repo's own code-review command, folds every fix into one
commit, applies the CI-trigger label, watches the run — classifying genuine
failures separately from flaky or fail-fast-cancelled ones — and repeats
until every PR in the set is reviewed-clean, CI-green, and mergeable. It
reuses the same `render_dashboard.py`/`serve_dashboard.sh` tooling as the
wizard's scaffolded loops, so a run gets the same auto-updating dashboard.

Because a review command's output format isn't standardized (and can drift
even within one repo), `review-ci` doesn't regex-scan the raw review comment
to decide "clean" — it has the invoking agent record a sha-pinned
issue/note count into the run's own state file, and verifies against that.
See `skills/review-ci/references/review-output-contract.md` for the
two-field contract this relies on.

Use `--dry-run` on a new repo or review command the first time — it exercises
discovery and the verifier without touching the actual PR.

## Install

This repo is a **Claude Code plugin** and its own single-plugin marketplace. Pick the path
that fits your host.

```bash
# Option A — Claude Code plugin (recommended). Installs, versions, and enables via /plugin.
claude plugin marketplace add fadzril/loop-maker-dashboard   # or a local path to this clone
claude plugin install loop-maker@loop-maker-dashboard

# Option B — portable skill copy (Claude Code or any host: Codex, Hermes, OpenClaw).
# Copies both skills/loop-maker/ and skills/review-ci/ into the host's skills dir.
git clone https://github.com/fadzril/loop-maker-dashboard
cd loop-maker-dashboard && ./install.sh
#   → custom dir: LOOP_MAKER_SKILLS_DIR=~/my-project/.claude/skills ./install.sh
```

### Usage

```
/loop-maker
```

The wizard runs, asks 7 questions, and writes the scaffolded loop under `loops/<name>/` in your project.

```
/loop-maker:review-ci <owner/repo> <pr1>,<pr2>,...
```

Skips the interview and runs immediately — see the `review-ci` section above.

### Enable under Claude

- **Plugin (Option A):** `claude plugin install` enables it immediately; toggle later with
  `claude plugin enable|disable loop-maker@loop-maker-dashboard` or the `/plugin` menu.
  Update with `claude plugin update loop-maker@loop-maker-dashboard`.
- **Skill copy (Option B):** Claude Code auto-discovers skills in `~/.claude/skills/` — no
  separate enable toggle; `/loop-maker` is live once copied.

Either way, restart a running session to pick up a newly-added plugin or skill.

## What this is NOT

- **Not a runtime.** `loop-maker` scaffolds loops; it doesn't execute them. Your loop runs as a separate Claude Code skill or cron job.
- **Not a single-purpose tool.** It works for any autonomous loop — content pipelines, monitoring agents, data-sync jobs, outreach sequences — not one niche use case.
- **Not a free pass on the human gate.** Question 7 is non-skippable. If an action is irreversible, the scaffold will wire in an approval step — no override.

## License

MIT © Eric Tech. See [LICENSE](./LICENSE).

## Credits

Designed and maintained by [Eric Tech](https://erictech.ca).

Further reading: Addy Osmani on agent design patterns; Anthropic's documentation on agentic loops and tool use.
