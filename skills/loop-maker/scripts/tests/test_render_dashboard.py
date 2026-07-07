import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import render_dashboard as rd

GATES = """# x — Human Gates & Budget
## Human gates
| # | Gate | Trigger condition | Who approves |
|---|------|-------------------|--------------|
| G1 | Pre-run sign-off | Before the first live run | Loop owner |
## Budget / stop
| Dimension | Limit | Action on breach |
|-----------|-------|-----------------|
| Max iterations | 9 | Halt |
"""

MULTI = """# cat-9866-fe — State Ledger
## Ledger
| group | item | status | notes |
|-------|------|--------|-------|
| admin_app | ADMIN-1 selector | done | fm/cat-9901 |
| admin_app | ADMIN-2 accordion | in-progress | fm/cat-9902 |
| web_app | WEB-1 order details | pending | fm/cat-9903 |
## Last run
```
timestamp : 2026-07-07 10:00
iteration : 2
outcome   : verified
exit code : 0
```
## Notes
- Goal predicate: **all FE subtasks verified**
"""

LEGACY = """# simple-loop — State Ledger
## Ledger
| item | status | notes |
|------|--------|-------|
| only task | done | ok |
## Last run
```
timestamp : now
iteration : 1
outcome   : done
exit code : 0
```
"""


def _render(state, gates=None):
    return rd.render(state, gates, None, "2026-07-07 12:00", "STATE.md")


def test_groups_split_and_count():
    items = rd._ledger(MULTI)
    groups = rd._grouped(items)
    assert [g for g, _ in groups] == ["admin_app", "web_app"]  # first-seen order preserved
    assert len(items) == 3


def test_status_normalization():
    assert rd._status_class("in-progress") == "run"
    assert rd._status_class("Verified") == "done"
    assert rd._status_class("FAILED") == "fail"
    assert rd._status_class("") == "pend"


def test_multi_group_renders_grouped_cards_and_timeline():
    html = _render(MULTI, GATES)
    assert 'class="grp"' in html                    # grouped stacked cards
    assert "admin_app" in html and "web_app" in html
    assert "ADMIN-1 selector" in html
    assert "all FE subtasks verified" in html        # goal -> subtitle
    assert "Pre-run sign-off" in html                # gates parsed
    assert "Max iterations" in html                  # budget parsed (hard tag)
    assert 'class="statuspill run"' in html          # one in-progress -> running
    assert "verified" in html                        # ADMIN-1 done -> timeline entry


def test_single_group_all_done_is_complete():
    html = _render(LEGACY)  # legacy 3-col ledger, one implicit "default" group
    assert "only task" in html
    assert 'class="statuspill ok"' in html           # all done -> complete
    assert "not found" in html                       # no gates file -> surfaced, not silent


def test_all_tokens_filled():
    html = _render(MULTI, GATES)
    assert "{{" not in html, "unfilled template token remains"


def test_html_escaped():
    state = MULTI.replace("ADMIN-1 selector", "a <script> & b")
    html = _render(state, GATES)
    assert "<script>" not in html and "&lt;script&gt;" in html


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all passed")
