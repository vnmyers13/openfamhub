#!/bin/bash
# Tests for scripts/create_trivy_issues.py and scripts/trivy-scan.sh.
# Run: bash scripts/tests/trivy-test.sh  (needs python3; no network or docker)
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
issues="$repo_root/scripts/create_trivy_issues.py"
scan="$repo_root/scripts/trivy-scan.sh"
tmp=$(mktemp -d)
. "$repo_root/scripts/tests/fake_forgejo_lib.sh"
trap 'stop_fake_forgejo; rm -rf "$tmp"' EXIT
fail() { echo "FAIL: $*"; exit 1; }

# A report with duplicates, a null Vulnerabilities list and low findings.
cat > "$tmp/report.json" <<'JSON'
{"Results": [
  {"Target": "os", "Vulnerabilities": [
    {"VulnerabilityID": "CVE-1", "PkgName": "openssl", "Severity": "CRITICAL", "InstalledVersion": "3.0", "FixedVersion": "3.1", "Title": "bad"},
    {"VulnerabilityID": "CVE-1", "PkgName": "openssl", "Severity": "CRITICAL"},
    {"VulnerabilityID": "CVE-2", "PkgName": "zlib", "Severity": "HIGH"},
    {"VulnerabilityID": "CVE-3", "PkgName": "curl", "Severity": "HIGH"},
    {"VulnerabilityID": "CVE-4", "PkgName": "bash", "Severity": "LOW"}]},
  {"Target": "python", "Vulnerabilities": null},
  {"Target": "empty"}
]}
JSON
echo '{"Results": null}' > "$tmp/clean.json"

# Fake Forgejo: CVE-2/api closed (risk accepted), CVE-3/web open, CVE-9/api open but
# fixed (not in the report), CVE-8/web open and not in the report (other image), a PR.
cat > "$tmp/issues.json" <<'JSON'
[{"number": 1, "title": "[trivy] CVE-2: zlib in openfamhub-api", "state": "closed"},
 {"number": 2, "title": "[trivy] CVE-3: curl in openfamhub-web", "state": "open"},
 {"number": 3, "title": "[trivy] CVE-9: libxml2 in openfamhub-api", "state": "open"},
 {"number": 4, "title": "[trivy] CVE-8: musl in openfamhub-web", "state": "open"},
 {"number": 5, "title": "Unrelated bug", "state": "open"},
 {"number": 6, "title": "[trivy] CVE-1: openssl in openfamhub-api", "state": "open", "pull_request": {}}]
JSON
start_fake_forgejo "$tmp/issues.json"

# Opens only new HIGH/CRITICAL findings, once each; closes fixed ones for this image.
out=$(TRIVY_ISSUE_TOKEN=s3cret python3 "$issues" "$url" o/r openfamhub-api:0.97 "$tmp/report.json")
echo "$out" | grep -q "3 HIGH/CRITICAL" || fail "count: $out"
echo "$out" | grep -q "openfamhub-api: 2 opened, 1 already tracked, 1 closed, 0 failed" || fail "summary: $out"
grep -q "^CREATE #7 \[trivy\] CVE-1: openssl in openfamhub-api$" "$reqlog" || fail "CVE-1 not opened (PR must not count)"
grep -q "^CREATE .*CVE-3: curl in openfamhub-api" "$reqlog" || fail "CVE-3 (other image) not opened"
grep -q "CREATE .*CVE-2" "$reqlog" && fail "closed CVE-2 reopened"
grep -q "CREATE .*CVE-4" "$reqlog" && fail "LOW finding opened"
grep -q "^COMMENT #3 No longer found in .openfamhub-api:0.97." "$reqlog" || fail "fixed CVE-9 not commented"
grep -q '^PATCH #3 {"state": "closed"}' "$reqlog" || fail "fixed CVE-9 not closed"
grep -q "PATCH #4\|PATCH #5\|PATCH #2" "$reqlog" && fail "closed an issue for another image or not from trivy"
grep -q "GET .* state=all page=1 auth=token s3cret" "$reqlog" || fail "list request"
echo "opens-new-closes-fixed"

# A second run with the same report changes nothing.
: > "$reqlog"
out=$(TRIVY_ISSUE_TOKEN=s3cret python3 "$issues" "$url" o/r openfamhub-api:0.98 "$tmp/report.json")
echo "$out" | grep -q "0 opened, 3 already tracked, 0 closed, 0 failed" || fail "rerun: $out"
grep -q "CREATE\|PATCH" "$reqlog" && fail "rerun wrote"
echo "idempotent"

# Critical first, and the per-run limit holds the rest back.
start_fake_forgejo "$tmp/issues.json"
out=$(TRIVY_ISSUE_TOKEN=t TRIVY_MAX_ISSUES=1 python3 "$issues" "$url" o/r openfamhub-web:0.97 "$tmp/report.json")
[ "$(grep -c CREATE "$reqlog")" = 1 ] || fail "limit"
grep -q "CREATE .*CVE-1" "$reqlog" || fail "critical not first"
echo "$out" | grep -q "limit of 1" || fail "limit message"
grep -q "PATCH #4" "$reqlog" || fail "web: fixed CVE-8 not closed"
echo "limit-ok"

# Pagination: 120 existing issues, the tracked one on page 3.
python3 -c "
import json; i=[{'number':n,'title':f'Bug {n}','state':'open'} for n in range(1,120)]
i.append({'number':120,'title':'[trivy] CVE-1: openssl in openfamhub-api','state':'open'})
json.dump(i,open('$tmp/many.json','w'))"
start_fake_forgejo "$tmp/many.json"
out=$(TRIVY_ISSUE_TOKEN=t python3 "$issues" "$url" o/r openfamhub-api:0.97 "$tmp/report.json")
grep -q "CREATE .*CVE-1" "$reqlog" && fail "missed issue on page 3"
grep -q "page=3" "$reqlog" || fail "no page 3 request"
echo "paginates"

# API errors are reported but don't fail the run.
start_fake_forgejo "$tmp/issues.json"
out=$(TRIVY_ISSUE_TOKEN=t python3 "$issues" "$url/FAILME" o/r openfamhub-api "$tmp/report.json") || fail "nonzero on API error"
echo "$out" | grep -q "failed CVE-1" || fail "error not reported: $out"
out=$(TRIVY_ISSUE_TOKEN=t python3 "$issues" "http://127.0.0.1:9" o/r img "$tmp/report.json") || fail "nonzero when unreachable"
echo "$out" | grep -q "can't list issues" || fail "unreachable: $out"
echo "errors-non-fatal"

# Clean report closes everything open for the image; dry run; usage errors.
start_fake_forgejo "$tmp/issues.json"
TRIVY_ISSUE_TOKEN=t python3 "$issues" "$url" o/r openfamhub-web:0.99 "$tmp/clean.json" | grep -q "0 opened, 0 already tracked, 2 closed" || fail "clean report"
python3 "$issues" "$url" o/r img "$tmp/clean.json" 2>/dev/null && fail "ran without token"
: > "$reqlog"
TRIVY_DRY_RUN=1 python3 "$issues" "$url" o/r img "$tmp/report.json" | grep -q "would open (unless tracked): \[trivy\] CVE-1" || fail "dry run"
[ -s "$reqlog" ] && fail "dry run made requests"
TRIVY_ISSUE_TOKEN=t python3 "$issues" "$url" o/r img "$tmp/missing.json" 2>/dev/null && fail "missing report accepted"
python3 "$issues" a b 2>/dev/null && fail "bad usage accepted"
echo "edge-cases-ok"

# trivy-scan.sh: scans the exact 0.<VERSION> tag of both images via docker.
mkdir -p "$tmp/bin" "$tmp/repo"; printf '97\n' > "$tmp/repo/VERSION"
cat > "$tmp/bin/docker" <<'SH2'
#!/bin/bash
echo "$*" >> "$DOCKER_LOG"
case "$*" in *"image "*openfamhub-web*) [ -n "${FAIL_WEB:-}" ] && exit 1;; esac
a="$*"; case "$a" in *"--output /out/"*) f=${a##*--output /out/}; f=${f%% *}; echo '{}' > "$OUT/$f";; esac
SH2
chmod +x "$tmp/bin/docker"
cd "$tmp/repo"
PATH="$tmp/bin:$PATH" DOCKER_LOG="$tmp/docker.log" OUT="$tmp/repo/trivy-reports" TRIVY_CACHE="$tmp/cache" "$scan" >/dev/null
grep -q "aquasec/trivy:0.69.3 image .*forgejo.vernonmyers.cloud/vernon/openfamhub-api:0.97$" "$tmp/docker.log" || fail "api tag"
grep -q "openfamhub-web:0.97$" "$tmp/docker.log" || fail "web tag"
[ -s trivy-reports/trivy-api.json ] && [ -s trivy-reports/trivy-web.json ] || fail "reports"
grep -q -- "-e TRIVY_PASSWORD" "$tmp/docker.log" || fail "credentials not passed by name"
echo "scan-tags-ok"
rm -rf trivy-reports
PATH="$tmp/bin:$PATH" DOCKER_LOG="$tmp/docker.log" OUT="$tmp/repo/trivy-reports" TRIVY_CACHE="$tmp/cache" FAIL_WEB=1 \
    "$scan" >/dev/null 2>&1 && fail "scan error not reported"
[ -s trivy-reports/trivy-api.json ] && [ ! -e trivy-reports/trivy-web.json ] || fail "partial reports"
echo "scan-error-reported"
echo "ALL OK"
