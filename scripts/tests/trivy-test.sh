#!/bin/bash
# Tests for scripts/create_trivy_issues.py and scripts/trivy-scan.sh.
# Run: bash scripts/tests/trivy-test.sh  (needs python3; no network or docker)
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
issues="$repo_root/scripts/create_trivy_issues.py"
scan="$repo_root/scripts/trivy-scan.sh"
tmp=$(mktemp -d); server_pid=""
trap '[ -n "$server_pid" ] && kill "$server_pid" 2>/dev/null; rm -rf "$tmp"' EXIT
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

# Fake Forgejo: CVE-2 is already tracked (closed); records every request.
cat > "$tmp/server.py" <<'PY'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
log = open(sys.argv[1], "a", buffering=1)
existing = [{"title": "[trivy] CVE-2: zlib in openfamhub-api", "state": "closed"},
            {"title": "[trivy] CVE-3: curl in openfamhub-web", "state": "open"}]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        log.write(f"GET {u.path} q={q.get('q',[''])[0]} state={q.get('state',[''])[0]} auth={self.headers.get('Authorization')}\n")
        self.reply(200, [i for i in existing if q.get('q',[''])[0] in i["title"]])
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        log.write(f"POST {self.path} {body['title']}\n")
        if "CVE-1" in body["title"] and "FAILME" in self.path: return self.reply(500, {})
        self.reply(201, {"html_url": "http://x/issues/1"})
srv = HTTPServer(("127.0.0.1", 0), H)
open(sys.argv[2], "w").write(str(srv.server_port))
srv.serve_forever()
PY
python3 "$tmp/server.py" "$tmp/requests.log" "$tmp/port" & server_pid=$!
for _ in $(seq 50); do [ -s "$tmp/port" ] && break; sleep 0.1; done
url="http://127.0.0.1:$(cat "$tmp/port")"

# Opens only the new HIGH/CRITICAL findings, once each; token never in argv.
out=$(TRIVY_ISSUE_TOKEN=s3cret python3 "$issues" "$url" o/r openfamhub-api:0.97 "$tmp/report.json")
echo "$out" | grep -q "3 HIGH/CRITICAL" || fail "count: $out"
echo "$out" | grep -q "2 opened, 1 already tracked, 0 failed" || fail "summary: $out"
grep -q "POST /api/v1/repos/o/r/issues \[trivy\] CVE-1: openssl in openfamhub-api$" "$tmp/requests.log" || fail "CVE-1 not opened"
grep -q "POST .*CVE-3: curl in openfamhub-api" "$tmp/requests.log" || fail "CVE-3 (other image) not opened"
grep -q "POST .*CVE-2" "$tmp/requests.log" && fail "closed CVE-2 reopened"
grep -q "POST .*CVE-4" "$tmp/requests.log" && fail "LOW finding opened"
grep -q "GET .* q=CVE-1 state=all auth=token s3cret" "$tmp/requests.log" || fail "search request"
echo "opens-new-skips-tracked"

# Critical first, and the per-run limit holds the rest back.
: > "$tmp/requests.log"
out=$(TRIVY_ISSUE_TOKEN=t TRIVY_MAX_ISSUES=1 python3 "$issues" "$url" o/r openfamhub-web:0.97 "$tmp/report.json")
[ "$(grep -c POST "$tmp/requests.log")" = 1 ] || fail "limit"
grep -q "POST .*CVE-1" "$tmp/requests.log" || fail "critical not first"
echo "$out" | grep -q "limit of 1" || fail "limit message"
echo "limit-ok"

# API errors are reported but don't fail the run.
out=$(TRIVY_ISSUE_TOKEN=t python3 "$issues" "$url/FAILME" o/r img "$tmp/report.json") || fail "nonzero on API error"
echo "$out" | grep -q "failed CVE-1" || fail "error not reported: $out"
out=$(TRIVY_ISSUE_TOKEN=t python3 "$issues" "http://127.0.0.1:9" o/r img "$tmp/report.json") || fail "nonzero when unreachable"
echo "$out" | grep -q "0 opened, 0 already tracked, 3 failed" || fail "unreachable: $out"
echo "errors-non-fatal"

# Clean report, dry run, and usage errors.
python3 "$issues" "$url" o/r img "$tmp/clean.json" 2>/dev/null && fail "ran without token"
TRIVY_ISSUE_TOKEN=t python3 "$issues" "$url" o/r img "$tmp/clean.json" | grep -q "no HIGH/CRITICAL" || fail "clean"
: > "$tmp/requests.log"
TRIVY_DRY_RUN=1 python3 "$issues" "$url" o/r img "$tmp/report.json" | grep -q "would open: \[trivy\] CVE-1" || fail "dry run"
[ -s "$tmp/requests.log" ] && fail "dry run made requests"
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
