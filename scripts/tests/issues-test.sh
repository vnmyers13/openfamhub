#!/bin/bash
# Tests for scripts/issues.py (triage and close-done) against a fake Forgejo.
# Run: bash scripts/tests/issues-test.sh  (needs python3; no network)
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
script="$repo_root/scripts/issues.py"
tmp=$(mktemp -d)
. "$repo_root/scripts/tests/fake_forgejo_lib.sh"
trap 'stop_fake_forgejo; rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*"; exit 1; }

cat > "$tmp/TODO.md" <<'MD'
# TODO
- **Decision:** one family per install (#5).
## Open issues
- [ ] **P1** Broken sync ([#2](https://forgejo.example/vernon/OpenFamHub/issues/2))
- [x] Fixed thing ([#3](https://forgejo.example/vernon/OpenFamHub/issues/3))
- [x] Half done, part one (#4)
- [ ] Half done, part two (#4)
- [ ] **P3** Label says P1 (#6)
- [ ] Closed upstream but not ticked (#7)
- [x] Already closed and ticked (#8)
Colour #1a1a1a and &#39; aren't issue references.
MD
cat > "$tmp/issues.json" <<'JSON'
[{"number": 1, "title": "Not in TODO, no label", "state": "open", "labels": []},
 {"number": 2, "title": "Broken sync", "state": "open", "labels": [{"name": "priority/p1"}]},
 {"number": 3, "title": "Fixed thing", "state": "open", "labels": []},
 {"number": 4, "title": "Half done", "state": "open", "labels": []},
 {"number": 5, "title": "Single family", "state": "open", "labels": []},
 {"number": 6, "title": "Label says P1", "state": "open", "labels": [{"name": "Priority/High"}]},
 {"number": 7, "title": "Closed upstream", "state": "closed", "labels": []},
 {"number": 8, "title": "Old", "state": "closed", "labels": []},
 {"number": 9, "title": "[trivy] CVE-1: openssl in openfamhub-api", "state": "open", "labels": [], "body": "Severity: **CRITICAL**"},
 {"number": 10, "title": "Data loss on restore", "state": "open", "labels": [{"name": "priority/critical"}]},
 {"number": 11, "title": "A pull request", "state": "open", "labels": [], "pull_request": {"merged": false}}]
JSON
start_fake_forgejo "$tmp/issues.json"
export FORGEJO_URL="$url" FORGEJO_REPO=vernon/OpenFamHub ISSUES_TOKEN=tok

# Triage: ranks by priority and lists every kind of drift.
out=$(python3 "$script" triage --todo "$tmp/TODO.md") || fail "triage exit without --strict"
echo "$out" | grep -q "^Open issues: 8 (P0 1, P1 2, P3 1, P? 4)" || fail "summary: $out"
first=$(echo "$out" | sed -n 2p); echo "$first" | grep -q "P0 #10 Data loss" || fail "P0 not first: $first"
echo "$out" | grep -q "P1 #9 \[trivy\] CVE-1.*NOT in TODO.md" || fail "trivy severity priority"
echo "$out" | grep -q -- "- \[ \] \*\*P0\*\* Data loss on restore (\[#10\]($url/vernon/OpenFamHub/issues/10))" || fail "paste line for #10"
echo "$out" | grep -q -- "- \[ \] \*\*P2\*\* Not in TODO, no label" || fail "default P2 suggestion"
echo "$out" | grep -q "#5 Single family" && echo "$out" | sed -n '/doesn.t mention/,/^$/p' | grep -q "#5\b" && fail "#5 mentioned in a decision counted as missing"
echo "$out" | sed -n '/still open/,/^$/p' | grep -q "#3 Fixed thing" || fail "done-but-open #3"
echo "$out" | sed -n '/still open/,/^$/p' | grep -q "#4" && fail "#4 half done counted as done"
echo "$out" | sed -n '/not ticked/,/^$/p' | grep -q "#7" || fail "closed-not-ticked #7"
echo "$out" | sed -n '/not ticked/,/^$/p' | grep -q "#8" && fail "#8 is ticked"
echo "$out" | grep -q "#6 TODO.md P3, Forgejo P1" || fail "priority mismatch"
echo "$out" | grep -q "1 P0 issue(s) open" || fail "P0 warning"
echo "$out" | grep -q "A pull request" && fail "PR listed"
echo "$out" | grep -q "#1a1a1a\|#39" && fail "false reference"
python3 "$script" triage --todo "$tmp/TODO.md" --strict >/dev/null && fail "--strict passed with drift"
echo "triage-ok"

# close-done: dry run by default, then closes only fully ticked issues.
: > "$reqlog"
out=$(python3 "$script" close-done --todo "$tmp/TODO.md")
echo "$out" | grep -q "would close #3 Fixed thing" || fail "dry run: $out"
grep -q "PATCH\|COMMENT" "$reqlog" && fail "dry run wrote"
mkdir -p "$tmp/repo"; printf '98\n' > "$tmp/repo/VERSION"
out=$(cd "$tmp/repo" && python3 "$script" close-done --todo "$tmp/TODO.md" --apply)
echo "$out" | grep -q "closed #3" || fail "apply: $out"
grep -q "^COMMENT #3 Marked done in TODO.md as of build 0.98" "$reqlog" || fail "comment"
grep -q '^PATCH #3 {"state": "closed"}' "$reqlog" || fail "close"
[ "$(grep -c '^PATCH' "$reqlog")" = 1 ] || fail "closed more than #3"
echo "close-done-ok"

# A TODO.md and Forgejo that agree pass --strict.
cat > "$tmp/clean.json" <<'JSON'
[{"number": 1, "title": "Open bug", "state": "open", "labels": [{"name": "priority/p2"}]},
 {"number": 2, "title": "Done", "state": "closed", "labels": []}]
JSON
printf -- '- [ ] **P2** Open bug (#1)\n- [x] Done (#2)\n' > "$tmp/clean.md"
start_fake_forgejo "$tmp/clean.json"
export FORGEJO_URL="$url"
python3 "$script" triage --todo "$tmp/clean.md" --strict | grep -q "Issues and TODO.md agree" || fail "clean strict"
echo "strict-clean-ok"

# --report-issue: creates and pins the report, then updates it in place and comments
# only when new items need attention.
start_fake_forgejo "$tmp/issues.json"
export FORGEJO_URL="$url"
out=$(python3 "$script" triage --todo "$tmp/TODO.md" --report-issue)
echo "$out" | grep -q "Created report issue #12" || fail "report not created: $out"
grep -q "^CREATE #12 Triage report$" "$reqlog" || fail "create"
grep -q "^PIN #12$" "$reqlog" || fail "pin"
grep -q "^COMMENT #12 7 new item(s) need attention" "$reqlog" || fail "first comment: $(grep COMMENT "$reqlog")"
body="$tmp/issues.json.last"
grep -q "<!-- issues.py:triage-report -->" "$body" || fail "marker"
grep -q "Needs attention: 7 item(s)" "$body" || fail "attention count"
grep -q -- "- \[ \] \*\*P0\*\* Data loss on restore" "$body" || fail "paste line in report"
grep -q "| P0 | #10 Data loss on restore | \*\*no\*\* |" "$body" || fail "table row"
grep -q "Triage report" "$body" && fail "report lists itself"
: > "$reqlog"
out=$(python3 "$script" triage --todo "$tmp/TODO.md" --report-issue)
echo "$out" | grep -q "Updated report issue #12" || fail "second run: $out"
echo "$out" | grep -q "#12 Triage report" && fail "report issue listed in triage"
grep -q "CREATE\|COMMENT\|PIN" "$reqlog" && fail "second run created or commented: $(cat "$reqlog")"
echo "report-idempotent"
# A new issue appears: the report is updated and one comment names the change.
python3 - "$tmp" <<'PYX'
import json, sys
p = sys.argv[1] + "/issues.json"; i = json.load(open(p))
i.append({"number": 12, "title": "Triage report", "state": "open", "labels": [], "body": open(p + ".last").read()})
i.append({"number": 13, "title": "New bug", "state": "open", "labels": []})
json.dump(i, open(sys.argv[1] + "/issues2.json", "w"))
PYX
start_fake_forgejo "$tmp/issues2.json"
export FORGEJO_URL="$url"
python3 "$script" triage --todo "$tmp/TODO.md" --report-issue >/dev/null
grep -q "^PATCH #12 body$" "$reqlog" || fail "report not updated"
grep -q "^COMMENT #12 1 new item(s) need attention" "$reqlog" || fail "new-item comment: $(grep COMMENT "$reqlog")"
grep -q "New bug" "$tmp/issues2.json.last" || fail "new issue not in report"
echo "report-comments-on-new"
# Pinning unsupported: still created; all clear reads as such.
start_fake_forgejo "$tmp/clean.json"
FORGEJO_URL="$url/NOPIN" python3 "$script" triage --todo "$tmp/clean.md" --report-issue | grep -q "couldn't pin" || fail "pin failure not reported"
grep -q "Issues and TODO.md agree" "$tmp/clean.json.last" || fail "clean report"
grep -q "COMMENT" "$reqlog" && fail "commented with nothing to say"
echo "report-edge-ok"

# Errors: unreachable API and missing TODO.md exit 2; close failures exit 2.
FORGEJO_URL=http://127.0.0.1:9 python3 "$script" triage --todo "$tmp/clean.md" >/dev/null 2>&1 && fail "unreachable"
python3 "$script" triage --todo "$tmp/none.md" >/dev/null 2>&1 && fail "missing TODO"
start_fake_forgejo "$tmp/issues.json"
rc=0; FORGEJO_URL="$url/FAILME" python3 "$script" close-done --todo "$tmp/TODO.md" --apply >/dev/null 2>&1 || rc=$?
[ "$rc" = 2 ] || fail "close failure exit $rc"
echo "errors-ok"
echo "ALL OK"
