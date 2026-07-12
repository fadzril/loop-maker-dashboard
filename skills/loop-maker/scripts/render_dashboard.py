#!/usr/bin/env python3
"""Render a loop-maker dashboard from STATE.md (+ optional HUMAN-GATES.md).

A deterministic *view* of the loop's state file — no LLM, no network. The loop
already writes STATE.md every tick, so running this after each write keeps the
dashboard current (see scripts/dashboard_watch.sh for the idle tick-listener).

One block is rendered per distinct `group` in the ledger, so the board's shape
follows the loop's own decomposition of the task set: a single-workstream loop
writes one group and gets a clean single-loop board; a loop that fans a task
set into parallel stacks writes many groups and gets the full control board.

Pure stdlib. Usage:
  render_dashboard.py --state loops/foo/STATE.md
      [--gates skills/foo/HUMAN-GATES.md]
      [--template templates/dashboard.html.tmpl]
      [--out loops/foo/dashboard.html]
      [--title "Foo loop"] [--now "2026-07-07 12:00"]
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


def _default_template():
    # Works whether this script sits in the plugin (../templates/) or is copied
    # flat into a loop dir alongside dashboard.html.tmpl.
    for p in (os.path.join(HERE, "dashboard.html.tmpl"),
              os.path.join(HERE, "..", "templates", "dashboard.html.tmpl")):
        if os.path.exists(p):
            return p
    return os.path.join(HERE, "..", "templates", "dashboard.html.tmpl")


DEFAULT_TEMPLATE = _default_template()

# status token -> (css class, done?, terminal-fail?)
_STATUS = {
    "done": "done", "verified": "done", "complete": "done", "completed": "done",
    "in-progress": "run", "in progress": "run", "running": "run", "active": "run",
    "failed": "fail", "fail": "fail", "error": "fail", "budget-exceeded": "fail",
    "pending": "pend", "queued": "pend", "todo": "pend", "skipped": "pend", "": "pend",
}


_WARNED_STATUS = set()


def _warn_unknown_status(token: str):
    # Warn once per distinct token so a stray status (e.g. "ci-running", "blocked")
    # that silently renders as "pending" is visible instead of looking idle.
    if token in _WARNED_STATUS:
        return
    _WARNED_STATUS.add(token)
    valid = ", ".join(sorted(set(_STATUS) - {""}))
    print(f"render_dashboard: unrecognized status {token!r} -> shown as 'pending'. "
          f"Valid tokens: {valid}. Put descriptive state in the notes column.",
          file=sys.stderr)


def _status_class(raw: str) -> str:
    key = raw.strip().lower()
    if key and key not in _STATUS:
        _warn_unknown_status(raw.strip())
    return _STATUS.get(key, "pend")


def _split_row(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells) -> bool:
    return all(re.fullmatch(r":?-+:?", c or "") for c in cells)


def _section_rows(text: str, title: str):
    """Return the markdown-table rows (as cell-lists) under a `## <title>` header."""
    lines = text.splitlines()
    out, in_section = [], False
    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            in_section = title.lower() in s.lower()
            continue
        if in_section and s.startswith("|"):
            out.append(_split_row(line))
    return out


def _table_dicts(rows):
    """[header, sep, *data] cell-lists -> list of {header_lower: value}."""
    if not rows:
        return []
    header = [h.lower() for h in rows[0]]
    data = [r for r in rows[1:] if not _is_sep(r)]
    dicts = []
    for r in data:
        d = {header[i]: (r[i] if i < len(r) else "") for i in range(len(header))}
        dicts.append(d)
    return dicts


def _ledger(text: str):
    dicts = _table_dicts(_section_rows(text, "Ledger"))
    items = []
    for d in dicts:
        item = d.get("item") or d.get("task") or ""
        if not item:
            continue
        items.append({
            "group": d.get("group") or "default",
            "item": item,
            "status": _status_class(d.get("status", "")),
            "notes": d.get("notes", ""),
            # optional richer columns — rendered only when the ledger carries them
            "ref": d.get("ref", ""),
            "type": d.get("type", ""),
            "branch": d.get("branch", ""),
            "pr": d.get("pr", ""),
        })
    return items


def _last_run(text: str):
    m = re.search(r"##\s*Last run.*?```(.*?)```", text, re.S | re.I)
    kv = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                kv[k.strip().lower()] = v.strip()
    return {
        "timestamp": kv.get("timestamp", "—"),
        "iteration": kv.get("iteration", "0"),
        "outcome": kv.get("outcome", "—"),
        "exit": kv.get("exit code", kv.get("exit", "—")),
    }


def _grouped(items):
    order, groups = [], {}
    for it in items:
        g = it["group"]
        if g not in groups:
            groups[g] = []
            order.append(g)
    for it in items:
        groups[it["group"]].append(it)
    return [(g, groups[g]) for g in order]


def _e(s: str) -> str:
    return html.escape(str(s), quote=True)


# ----- section builders -------------------------------------------------------

# item status -> (chip class, chip label, card extra class, seg span class)
_VIS = {
    "done": ("done", "Verified", "", "on"),
    "run":  ("run", "Running", " run", "cur"),
    "fail": ("bad", "Failed", " bad", "bad"),
    "pend": ("wait", "Pending", "", ""),
}


def _seg(items):
    return "".join(f'<span class="{_VIS[it["status"]][3]}"></span>' for it in items) or "<span></span>"


_STLABEL = {"done": "done", "run": "running", "fail": "failed", "pend": "pending"}
_STCLS = {"done": "done", "run": "run", "fail": "bad", "pend": "wait"}
_ROWCLS = {"done": "done", "run": "run", "fail": "bad", "pend": ""}


def _group_status(items):
    done = sum(1 for it in items if it["status"] == "done")
    if any(it["status"] == "fail" for it in items):
        return "fail"
    if any(it["status"] == "run" for it in items):
        return "run"
    return "done" if items and done == len(items) else "pend"


def _tk(it, i):
    """Two-line ticket cell from the optional `ref` column (e.g. 'ADMIN-1 · CAT-9901')."""
    ref = it.get("ref", "").strip()
    if not ref:
        return f'<span class="part">#{i:02d}</span>'
    parts = re.split(r"\s*[·/]\s*", ref, maxsplit=1)
    if len(parts) == 2:
        return f'<span class="part">{_e(parts[0])}</span>{_e(parts[1])}'
    return _e(ref)


def _row_tags(it):
    tags = []
    typ = it.get("type", "").strip()
    if typ:
        cls = "type new" if typ.upper() == "NEW" else "type"
        tags.append(f'<span class="{cls}">{_e(typ)}</span>')
    tags.append(f'<span class="st {_STCLS[it["status"]]}">{_STLABEL[it["status"]]}</span>')
    pr = it.get("pr", "").strip()
    if pr.startswith("http"):
        tail = pr.rstrip("/").rsplit("/", 1)[-1]
        label = "#" + tail if tail.isdigit() else "PR"
        tags.append(f'<a class="pr" href="{_e(pr)}">{_e(label)}</a>')
    elif pr:
        tags.append(f'<span class="pr">{_e(pr)}</span>')
    return "".join(tags)


def _stacks(groups):
    out = []
    for name, items in groups:
        gstat = _group_status(items)
        base = ""  # derive the stack base branch from the first item's branch left side
        for it in items:
            if it.get("branch", "").strip():
                base = re.split(r"\s*(?:→|->)\s*", it["branch"].strip())[0].strip()
                break
        base_html = f'<span class="base">base · {_e(base)}</span>' if base else ""
        rows = []
        for i, it in enumerate(items, 1):
            branch = it.get("branch", "").strip()
            note = it.get("notes", "").strip()
            note_html = ""
            if note:
                ncls = "tbc" if re.search(r"tbc|!", note, re.I) else "xnote"
                note_html = f' <span class="{ncls}">· {_e(note)}</span>'
            sub = f'<div class="b">{_e(branch)}{note_html}</div>' if (branch or note_html) else ""
            rows.append(
                f'<div class="row {_ROWCLS[it["status"]]}"><span class="lstripe"></span>'
                f'<div class="tk">{_tk(it, i)}</div>'
                f'<div class="desc"><div class="t">{_e(it["item"])}</div>{sub}</div>'
                f'<div class="tags">{_row_tags(it)}</div></div>'
            )
        out.append(
            f'<div class="stack"><div class="stack-head">'
            f'<span class="repo">{_e(name)}</span>'
            f'<span class="st {_STCLS[gstat]}">{_STLABEL[gstat]}</span>{base_html}</div>'
            + "".join(rows) + "</div>"
        )
    return "\n  ".join(out) or (
        '<div class="stack"><div class="row"><div class="desc">'
        '<div class="t">No items yet.</div></div></div></div>'
    )


def _gate_rows(gates_text):
    """Human gates (soft tag) + budget/stop (hard tag), as one <ul class=gates> body."""
    if gates_text is None:
        return ('<li><span class="tag hard">gates</span><span>HUMAN-GATES.md not found — '
                'gates unverified</span></li>')
    rows = []
    for d in _table_dicts(_section_rows(gates_text, "Human gates")):
        name = d.get("gate", "")
        trig = d.get("trigger condition") or d.get("trigger", "")
        if name:
            tag = _e(d.get("#", "") or "gate")
            rows.append(f'<li><span class="tag">{tag}</span><span><b>{_e(name)}</b> — {_e(trig)}</span></li>')
    budget = []
    for d in _table_dicts(_section_rows(gates_text, "Budget")):
        dim, lim = d.get("dimension", ""), d.get("limit", "")
        if dim:
            budget.append(f'<li><span class="tag hard">{_e(dim)}</span><span>{_e(lim)}</span></li>')
    if not budget:
        budget = ['<li><span class="tag hard">budget</span><span>not set — a loop without a hard stop can run forever</span></li>']
    return "\n        ".join(rows + budget) or '<li><span class="tag">gates</span><span>none listed</span></li>'


def _timeline(items, last):
    ex = str(last["exit"]).strip()
    mk = "ok" if ex == "0" else ("run" if ex in ("—", "") else "bad")
    rows = [f'<li><span class="mk {mk}"></span><div><b>{_e(last["outcome"])}</b> — '
            f'iteration {_e(last["iteration"])}, exit {_e(ex or "—")} '
            f'<span class="t">{_e(last["timestamp"])}</span></div></li>']
    verbs = {"done": ("ok", "verified"), "fail": ("bad", "verifier failed"), "run": ("run", "running")}
    events = [it for it in items if it["status"] in verbs]
    for it in reversed(events[-9:]):  # newest ledger rows first; cap at 9
        m, verb = verbs[it["status"]]
        rows.append(f'<li><span class="mk {m}"></span><div><b>{_e(it["item"])}</b> — {verb} '
                    f'<span class="t">{_e(it["group"])}</span></div></li>')
    if not events:
        rows.append('<li><span class="mk fix"></span><div>scaffolded — no items processed yet '
                    '<span class="t">start</span></div></li>')
    return "\n      ".join(rows)


def render(state_text, gates_text, title, now, state_path, prefix=None):
    items = _ledger(state_text)
    groups = _grouped(items)
    last = _last_run(state_text)

    total = len(items)
    done = sum(1 for it in items if it["status"] == "done")
    run = sum(1 for it in items if it["status"] == "run")
    fail = sum(1 for it in items if it["status"] == "fail")
    pend = total - done - run - fail

    if fail:
        sclass, slabel = "fail", "halted · verifier fail"
    elif total and done == total:
        sclass, slabel = "ok", "complete"
    elif run:
        sclass, slabel = "run", f"running · iter {last['iteration']}"
    elif done:
        sclass, slabel = "wait", f"idle · {done}/{total} done"
    else:
        sclass, slabel = "wait", "not started"

    open_ct = total - done
    open_parts = []
    if run:
        open_parts.append(f"{run} running")
    if pend:
        open_parts.append(f"{pend} pending")
    if fail:
        open_parts.append(f"{fail} failed")
    open_summary = " · ".join(open_parts) or "all verified"

    name_m = re.search(r"^#\s*(.+?)(?:\s+—\s+State Ledger)?\s*$", state_text, re.M)
    loop_name = title or (name_m.group(1).strip() if name_m else "Loop")
    if prefix:
        # Context prefix, e.g. "review-ci: <msg>" / "loop: <msg>". Don't double
        # a prefix the state heading already carries.
        p = prefix.strip()
        if p and not loop_name.lower().startswith(p.lower() + ":"):
            loop_name = f"{p}: {loop_name}"
    goal_m = re.search(r"Goal predicate:\s*\*\*(.+?)\*\*", state_text)
    subtitle = goal_m.group(1).strip() if goal_m else "self-running, self-verifying agent loop"

    fields = {
        "TITLE": _e(loop_name),
        "EYEBROW": "loop-maker · self-running loop",
        "SUBTITLE": _e(subtitle),
        "STATUS_CLASS": sclass,
        "STATUS_CLASS_BADGE": sclass,
        "STATUS_LABEL": _e(slabel),
        "DONE_COUNT": str(done),
        "TOTAL_COUNT": str(total),
        "PROGRESS_SEGMENTS": _seg(items),
        "ITERATION": _e(last["iteration"]),
        "LAST_TIMESTAMP": _e(last["timestamp"]),
        "LAST_OUTCOME": _e(last["outcome"]),
        "LAST_EXIT": _e(last["exit"]),
        "OPEN_COUNT": str(open_ct),
        "OPEN_SUMMARY": _e(open_summary),
        "STACKS": _stacks(groups),
        "GATES_ROWS": _gate_rows(gates_text),
        "TIMELINE_ROWS": _timeline(items, last),
        "GENERATED_AT": _e(now),
        "STATE_PATH": _e(state_path),
    }

    with open(os.environ.get("LM_TEMPLATE", DEFAULT_TEMPLATE), encoding="utf-8") as f:
        tmpl = f.read()
    for k, v in fields.items():
        tmpl = tmpl.replace("{{" + k + "}}", v)
    return tmpl


def _main(argv) -> int:
    ap = argparse.ArgumentParser(description="Render a loop-maker dashboard from STATE.md")
    ap.add_argument("--state", required=True)
    ap.add_argument("--gates", default=None)
    ap.add_argument("--template", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--prefix", default=None,
                    help="context prefix for the title, e.g. 'review-ci' or 'loop'")
    ap.add_argument("--now", default=None)
    a = ap.parse_args(argv)

    if a.template:
        os.environ["LM_TEMPLATE"] = a.template
    with open(a.state, encoding="utf-8") as f:
        state_text = f.read()
    gates_text = None
    if a.gates and os.path.exists(a.gates):
        with open(a.gates, encoding="utf-8") as f:
            gates_text = f.read()
    now = a.now or datetime.now().strftime("%Y-%m-%d %H:%M")

    out_html = render(state_text, gates_text, a.title, now, a.state, a.prefix)
    out_path = a.out or os.path.join(os.path.dirname(a.state) or ".", "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print("file://" + os.path.abspath(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
