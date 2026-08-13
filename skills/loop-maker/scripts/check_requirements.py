#!/usr/bin/env python3
"""Gate a loop on its requirement trace instead of on its own ledger.

A loop whose exit predicate reads its own STATE.md is a tautology: it reports
done because it wrote done. This checker reads the three things that come from
OUTSIDE the loop and refuses to pass while any cell is blank:

  1. Requirement trace  — the source's own words, one row per requirement.
  2. Open questions     — what the source does not say, answered or assumed.
  3. Permutation matrix — the states the feature must survive.

Proof cells are `spec:`, `browser:` or `waived:`. When a proof names a path
(anything containing `/`) the file must exist, so "verified in a browser"
becomes an artifact on disk rather than a claim in a sentence.

Usage: check_requirements.py <REQUIREMENTS.md> [--root DIR]... [--quiet]
Exit:  0 = every row satisfied and proven · 1 = blanks remain · 2 = misuse

--root is repeatable, for a loop spanning several repos: proof paths are
resolved against the cwd, the file's own directory, and each root in turn.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_dashboard import _section_rows, _table_dicts  # noqa: E402  (sibling script)

USAGE = "usage: check_requirements.py <REQUIREMENTS.md> [--root DIR]... [--quiet]"

TRACE = "Requirement trace"
QUESTIONS = "Open questions"
MATRIX = "Permutation matrix"

# A cell holding one of these is blank, however it is dressed up.
PLACEHOLDERS = {"", "-", "--", "—", "–", "?", "??", "tbd", "tbc", "n/a", "na", "todo", "..."}

PROOF = re.compile(r"^(spec|browser|waived)\s*:\s*\S", re.I)
ANSWER = re.compile(r"^(answered|assumed)\s*:\s*\S", re.I)

PROOF_RULE = (PROOF, "proof must start with spec: / browser: / waived:")
ANSWER_RULE = (ANSWER, "resolution must start with answered: or assumed:")
ANY_RULE = (None, "")


def blank(value: str) -> bool:
    return value.strip().strip("*_`").lower() in PLACEHOLDERS


def evidence_path(value: str):
    """The file a proof cell points at, or None when it names no path."""
    _, _, body = value.partition(":")
    token = body.strip().split()[0] if body.strip() else ""
    if "/" not in token:
        return None
    return re.sub(r":\d+(?:-\d+)?$", "", token.strip("`'\"(),"))


def on_disk(path, roots):
    return any((root / path).exists() for root in roots) or Path(path).exists()


def check_table(rows, section, roots, rules):
    """rules: list of (column, (pattern|None, message)). Returns problem strings."""
    if not rows:
        return [f"{section}: section missing or has no table"]
    problems = []
    for i, row in enumerate(rows, start=1):
        rid = row.get("id", "").strip() or f"row {i}"
        for column, (pattern, message) in rules:
            if column not in row:
                return problems + [f"{section}: missing `{column}` column"]
            value = row[column]
            if blank(value):
                problems.append(f"{section} {rid}: `{column}` is blank")
                continue
            if pattern and not pattern.match(value):
                problems.append(f"{section} {rid}: {message} (got {value!r})")
                continue
            # An evidence path must actually be on disk — that is the whole
            # point of writing `browser: shots/step-4.png` instead of "checked".
            path = evidence_path(value) if PROOF.match(value) else None
            if path and not on_disk(path, roots):
                problems.append(f"{section} {rid}: evidence not on disk — {path}")
    return problems


def main(argv):
    flags = list(argv[1:])
    quiet = "--quiet" in flags
    roots, args = [], []
    while flags:
        flag = flags.pop(0)
        if flag == "--quiet":
            continue
        if flag == "--root":
            if not flags:
                print(USAGE, file=sys.stderr)
                return 2
            roots.append(Path(flags.pop(0)).expanduser())
        else:
            args.append(flag)
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2

    path = Path(args[0])
    if not path.is_file():
        print(f"MISUSE: no such file — {path}\n{USAGE}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    roots = [path.parent, *roots]
    tables = {name: _table_dicts(_section_rows(text, name)) for name in (TRACE, QUESTIONS, MATRIX)}

    # A waived requirement needs a reason, not a location. Let the reason stand
    # in for both cells so the waiver is stated once.
    for row in tables[TRACE]:
        if row.get("proven by", "").strip().lower().startswith("waived") and blank(
            row.get("satisfied in", "")
        ):
            row["satisfied in"] = row["proven by"]

    problems = []
    problems += check_table(tables[TRACE], TRACE, roots,
                            [("satisfied in", ANY_RULE), ("proven by", PROOF_RULE)])
    problems += check_table(tables[QUESTIONS], QUESTIONS, roots,
                            [("resolution", ANSWER_RULE)])
    problems += check_table(tables[MATRIX], MATRIX, roots,
                            [("covered by", PROOF_RULE)])

    counted = sum(len(t) for t in tables.values())
    if problems:
        print(f"FAIL: {len(problems)} unproven of {counted} rows in {path}", file=sys.stderr)
        for problem in problems:
            print(f"  · {problem}", file=sys.stderr)
        return 1
    if not quiet:
        print(f"PASS: {counted} rows traced and proven in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
