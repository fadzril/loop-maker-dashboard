# loop-maker

A portable agent skill — works in Claude Code, Codex, Hermes, and OpenClaw — that interviews you and scaffolds a self-running autonomous loop, complete with verifier, state file, and human gate, so you don't build one wrong.

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
| **What you get** | A ready-to-run loop folder: `SKILL.md` + `STATE.md` + verifier script + stop condition wired in |
| **How you start** | `/loop-maker`, or just describe an automate/schedule/monitor task — fires without the word "loop" |
| **Install** | `git clone … ~/.claude/skills/loop-maker` — or see Install below |

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

## Install

```bash
# Option A — drop into your global Claude skills folder
# (repo is loop-maker-dashboard; the skill dir stays `loop-maker` so /loop-maker resolves)
git clone https://github.com/fadzril/loop-maker-dashboard ~/.claude/skills/loop-maker

# Option B — install into a custom skills directory (run from the cloned repo)
LOOP_MAKER_SKILLS_DIR=~/my-project/.claude/skills ./install.sh
```

### Usage

```
/loop-maker
```

That's it. The wizard runs, asks 7 questions, and writes the scaffolded loop under `loops/<name>/` in your project.

### Enable under Claude

Claude Code auto-discovers skills in `~/.claude/skills/` — there's no separate enable
toggle. Once installed (Option A or `install.sh`), the skill is live: invoke it with
`/loop-maker`, or just describe an automate/schedule/monitor task and it fires. If a
session was already running when you added the skill dir, restart it to pick up the new
skill.

## What this is NOT

- **Not a runtime.** `loop-maker` scaffolds loops; it doesn't execute them. Your loop runs as a separate Claude Code skill or cron job.
- **Not a single-purpose tool.** It works for any autonomous loop — content pipelines, monitoring agents, data-sync jobs, outreach sequences — not one niche use case.
- **Not a free pass on the human gate.** Question 7 is non-skippable. If an action is irreversible, the scaffold will wire in an approval step — no override.

## License

MIT © Eric Tech. See [LICENSE](./LICENSE).

## Credits

Designed and maintained by [Eric Tech](https://erictech.ca).

Further reading: Addy Osmani on agent design patterns; Anthropic's documentation on agentic loops and tool use.
