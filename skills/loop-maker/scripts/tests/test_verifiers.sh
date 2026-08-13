#!/usr/bin/env bash
# scripts/tests/test_verifiers.sh
set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
check() { if [ "$1" = "$2" ]; then echo "  ✓ $3"; else echo "  ✗ $3 (got $1 want $2)"; fail=1; fi; }

bash "$DIR/verifier_template.sh" "tautology" true >/dev/null 2>&1; check "$?" "0" "passing predicate exits 0"
bash "$DIR/verifier_template.sh" "falsity" false >/dev/null 2>&1; check "$?" "1" "failing predicate exits 1"
bash "$DIR/verifier_template.sh" >/dev/null 2>&1; check "$?" "2" "misuse exits 2"
bash "$DIR/verify_example.sh" 0 >/dev/null 2>&1; check "$?" "0" "example: 0 items left passes"
bash "$DIR/verify_example.sh" 3 >/dev/null 2>&1; check "$?" "1" "example: 3 items left fails"

# --- check_requirements.py -------------------------------------------------
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
req() { cat > "$TMP/REQUIREMENTS.md"; }
run() { python3 "$DIR/check_requirements.py" "$TMP/REQUIREMENTS.md" >/dev/null 2>&1; echo $?; }

complete_doc() {
  req <<'EOF'
## Requirement trace
| id | requirement | satisfied in | proven by |
|----|-------------|--------------|-----------|
| R-1 | "Do not charge cancelled orders" | app/x.rb:8 | spec: named example |
| R-2 | "Show the badge" | src/B.jsx:3 | waived: cut from scope, see Q-1 |

## Open questions
| id | question | asked | resolution |
|----|----------|-------|------------|
| Q-1 | Badge at zero markup? | 2026-08-13 | assumed: hidden |

## Permutation matrix
| id | cell | covered by |
|----|------|------------|
| M-1 | copay x zero markup | spec: replacement_spec |
EOF
}

complete_doc;                                        check "$(run)" "0" "reqs: complete document passes"
complete_doc; sed -i '' 's|app/x.rb:8|  |' "$TMP/REQUIREMENTS.md"
                                                     check "$(run)" "1" "reqs: blank 'satisfied in' fails"
complete_doc; sed -i '' 's|spec: named example|TBD|' "$TMP/REQUIREMENTS.md"
                                                     check "$(run)" "1" "reqs: TBD counts as blank"
complete_doc; sed -i '' 's|spec: named example|checked it manually|' "$TMP/REQUIREMENTS.md"
                                                     check "$(run)" "1" "reqs: proof without spec:/browser:/waived: fails"
complete_doc; sed -i '' 's|assumed: hidden|we will see|' "$TMP/REQUIREMENTS.md"
                                                     check "$(run)" "1" "reqs: unresolved question fails"
complete_doc; sed -i '' 's|spec: replacement_spec|browser: evidence/step4.png|' "$TMP/REQUIREMENTS.md"
                                                     check "$(run)" "1" "reqs: missing evidence file fails"
mkdir -p "$TMP/evidence" && touch "$TMP/evidence/step4.png"
                                                     check "$(run)" "0" "reqs: evidence file on disk passes"
complete_doc; sed -i '' '/^## Permutation matrix/,$d' "$TMP/REQUIREMENTS.md"
                                                     check "$(run)" "1" "reqs: missing section fails"
python3 "$DIR/check_requirements.py" "$TMP/nope.md" >/dev/null 2>&1
                                                     check "$?" "2" "reqs: missing file is misuse"

[ "$fail" = "0" ] && echo "ALL PASS" || { echo "FAILURES"; exit 1; }
