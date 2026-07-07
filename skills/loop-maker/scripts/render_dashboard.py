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
DEFAULT_TEMPLATE = os.path.join(HERE, "..", "templates", "dashboard.html.tmpl")

# status token -> (css class, done?, terminal-fail?)
_STATUS = {
    "done": "done", "verified": "done", "complete": "done", "completed": "done",
    "in-progress": "run", "in progress": "run", "running": "run", "active": "run",
    "failed": "fail", "fail": "fail", "error": "fail", "budget-exceeded": "fail",
    "pending": "pend", "queued": "pend", "todo": "pend", "skipped": "pend", "": "pend",
}


def _status_class(raw: str) -> str:
    return _STATUS.get(raw.strip().lower(), "pend")


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

def _meter(groups):
    blocks = []
    for name, items in groups:
        cells = "".join(f'<i class="cell {it["status"] if it["status"] != "pend" else ""}"></i>' for it in items)
        done = sum(1 for it in items if it["status"] == "done")
        blocks.append(f'<div class="grp" title="{_e(name)} — {done}/{len(items)}">{cells}</div>')
    return "\n      ".join(blocks)


def _meter_labels(groups):
    out = []
    for name, items in groups:
        out.append(f'<div class="gl" style="flex:{max(len(items),1)}"><span class="eyebrow">{_e(name)}</span></div>')
    return "\n      ".join(out)


def _tiles(groups):
    if len(groups) <= 1:
        return ""  # single group: the summary + stack already say everything
    tiles = []
    for name, items in groups:
        total = len(items)
        done = sum(1 for it in items if it["status"] == "done")
        any_run = any(it["status"] == "run" for it in items)
        any_fail = any(it["status"] == "fail" for it in items)
        cls, pill = "", "pend"
        if any_fail:
            cls, pill = "f", "fail"
        elif done == total and total:
            cls, pill = "d", "done"
        elif any_run:
            cls, pill = "r", "run"
        pct = int(round(100 * done / total)) if total else 0
        tiles.append(
            f'<div class="tile {cls}"><span class="stripe"></span>'
            f'<h3>{_e(name)}</h3><div class="where">{total} item(s)</div>'
            f'<div class="barrow"><div class="bar {cls}"><i style="width:{pct}%"></i></div>'
            f'<span class="frac">{done}/{total}</span></div>'
            f'<span class="pill {pill}">{pill}</span></div>'
        )
    return '<div class="tiles">\n    ' + "\n    ".join(tiles) + "\n  </div>\n"


def _stacks(groups):
    out = []
    for name, items in groups:
        any_run = any(it["status"] == "run" for it in items)
        any_fail = any(it["status"] == "fail" for it in items)
        done = sum(1 for it in items if it["status"] == "done")
        head_pill = "fail" if any_fail else ("run" if any_run else ("done" if done == len(items) and items else "pend"))
        rows = []
        for i, it in enumerate(items, 1):
            b = f'<div class="b">{_e(it["notes"])}</div>' if it["notes"] else ""
            rows.append(
                f'<div class="row {it["status"]}"><span class="lstripe"></span>'
                f'<div class="tk">{i:02d}</div>'
                f'<div class="desc"><div class="t">{_e(it["item"])}</div>{b}</div>'
                f'<div class="tags"><span class="pill {it["status"]}">{it["status"]}</span></div></div>'
            )
        out.append(
            f'<div class="stack"><div class="stack-head">'
            f'<span class="repo">{_e(name)}</span><span class="pill {head_pill}">{head_pill}</span>'
            f'<span class="base">{done}/{len(items)}</span></div>'
            + "".join(rows) + "</div>"
        )
    return "\n  ".join(out)


def _gate_rows(gates_text):
    if gates_text is None:
        return '<div class="gate"><span class="k">gates</span><span>HUMAN-GATES.md not found — gates unverified</span></div>'
    dicts = _table_dicts(_section_rows(gates_text, "Human gates"))
    rows = []
    for d in dicts:
        name = d.get("gate", "")
        trigger = d.get("trigger condition") or d.get("trigger", "")
        if name:
            rows.append(f'<div class="gate"><span class="k">{_e(name)}</span><span>{_e(trigger)}</span></div>')
    return "\n      ".join(rows) or '<div class="gate"><span class="k">gates</span><span>none listed</span></div>'


def _budget_rows(gates_text):
    if gates_text is None:
        return '<div class="gate"><span class="k">budget</span><span>not set — a loop without a hard stop can run forever</span></div>'
    dicts = _table_dicts(_section_rows(gates_text, "Budget"))
    rows = []
    for d in dicts:
        dim = d.get("dimension", "")
        limit = d.get("limit", "")
        if dim:
            rows.append(f'<div class="gate"><span class="k">{_e(dim)}</span><span>{_e(limit)}</span></div>')
    return "\n      ".join(rows) or '<div class="gate"><span class="k">budget</span><span>not set</span></div>'


def render(state_text, gates_text, title, now, state_path):
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
        sclass, slabel = "done", "complete"
    elif run:
        sclass, slabel = "run", f"running · iter {_e(last['iteration'])}"
    elif done:
        sclass, slabel = "pend", f"idle · {done}/{total} done"
    else:
        sclass, slabel = "pend", "not started"

    name_m = re.search(r"^#\s*(.+?)(?:\s+—\s+State Ledger)?\s*$", state_text, re.M)
    loop_name = title or (name_m.group(1).strip() if name_m else "Loop")
    goal_m = re.search(r"Goal predicate:\s*\*\*(.+?)\*\*", state_text)
    subtitle = goal_m.group(1).strip() if goal_m else "self-running, self-verifying agent loop"

    fields = {
        "TITLE": _e(loop_name),
        "EYEBROW": "loop-maker · self-running loop",
        "SUBTITLE": _e(subtitle),
        "STATUS_CLASS": sclass,
        "STATUS_LABEL": _e(slabel),
        "DONE_COUNT": str(done),
        "TOTAL_COUNT": str(total),
        "RUN_COUNT": str(run),
        "PEND_COUNT": str(pend),
        "METER_GROUPS": _meter(groups) or '<div class="grp"></div>',
        "METER_LABELS": _meter_labels(groups),
        "TILES_BLOCK": _tiles(groups),
        "STACKS": _stacks(groups) or '<div class="stack"><div class="row"><div class="desc"><div class="t">No items yet.</div></div></div></div>',
        "GATES_ROWS": _gate_rows(gates_text),
        "BUDGET_ROWS": _budget_rows(gates_text),
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

    out_html = render(state_text, gates_text, a.title, now, a.state)
    out_path = a.out or os.path.join(os.path.dirname(a.state) or ".", "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
