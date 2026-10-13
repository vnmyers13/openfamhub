#!/usr/bin/env python3
"""Open Forgejo issues for HIGH/CRITICAL findings in a Trivy JSON report.

Usage:
    TRIVY_ISSUE_TOKEN=... create_trivy_issues.py <forgejo_url> <owner/repo> <image> <report.json>

The token is read from the environment, never from argv, so it doesn't show up
in process listings or CI logs. One issue is opened per (vulnerability, package,
image name); the tag is left out of the title so a finding that survives several
releases keeps a single issue. An issue whose title already exists, open or closed, is not opened again,
so closing an issue marks the finding as handled. At most TRIVY_MAX_ISSUES (default
20) issues are opened per run. Set TRIVY_DRY_RUN=1 to print what would be opened.

Network and API errors are reported but never fail the run (exit code 0); a missing
token, bad arguments or an unreadable report exit with 2.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SEVERITIES = ("CRITICAL", "HIGH")
TIMEOUT = 20


def load_findings(report_path):
    """Return sorted (severity, id, pkg, installed, fixed, title) tuples."""
    with open(report_path, encoding="utf-8") as fh:
        data = json.load(fh)
    findings = {}
    for result in data.get("Results") or []:
        for v in result.get("Vulnerabilities") or []:
            sev = v.get("Severity") or "UNKNOWN"
            if sev not in SEVERITIES:
                continue
            vid = v.get("VulnerabilityID") or "N/A"
            pkg = v.get("PkgName") or "unknown"
            findings.setdefault(
                (vid, pkg),
                (
                    sev,
                    vid,
                    pkg,
                    v.get("InstalledVersion") or "?",
                    v.get("FixedVersion") or "",
                    (v.get("Title") or v.get("Description") or "").strip()[:300],
                ),
            )
    return sorted(findings.values(), key=lambda f: (SEVERITIES.index(f[0]), f[1], f[2]))


def issue_title(vid, pkg, image):
    # Leave the tag out so a finding keeps one issue across releases.
    return f"[trivy] {vid}: {pkg} in {image.split(':')[0]}"


def issue_body(finding, image):
    sev, vid, pkg, installed, fixed, summary = finding
    return (
        f"Severity: **{sev}**\n\n"
        f"Image: `{image}`\n\n"
        f"Package: `{pkg}` {installed}\n\n"
        f"Fixed in: {fixed or 'no fix available yet'}\n\n"
        f"ID: `{vid}`\n\n"
        f"{summary}\n\n"
        "---\n"
        "Opened by the CI Trivy job. Close this issue once the image is rebuilt "
        "without the finding, or to accept the risk; it won't be reopened."
    )


class Api:
    def __init__(self, base_url, repo, token):
        self.base = f"{base_url.rstrip('/')}/api/v1/repos/{repo}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _call(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, headers=self.headers, method=method
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read() or b"null")

    def issue_exists(self, title, vid):
        query = urllib.parse.urlencode(
            {"state": "all", "type": "issues", "q": vid, "limit": 50}
        )
        issues = self._call("GET", f"/issues?{query}") or []
        return any(issue.get("title") == title for issue in issues)

    def create_issue(self, title, body):
        return self._call("POST", "/issues", {"title": title, "body": body})


def main(argv):
    if len(argv) != 5:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    base_url, repo, image, report_path = argv[1:]
    dry_run = os.environ.get("TRIVY_DRY_RUN") == "1"
    token = os.environ.get("TRIVY_ISSUE_TOKEN", "")
    if not token and not dry_run:
        print("TRIVY_ISSUE_TOKEN is not set", file=sys.stderr)
        return 2
    try:
        max_issues = int(os.environ.get("TRIVY_MAX_ISSUES", "20"))
    except ValueError:
        max_issues = 20

    try:
        findings = load_findings(report_path)
    except (OSError, ValueError) as exc:
        print(f"Can't read {report_path}: {exc}", file=sys.stderr)
        return 2

    if not findings:
        print(f"{image}: no HIGH/CRITICAL findings")
        return 0
    print(f"{image}: {len(findings)} HIGH/CRITICAL finding(s)")

    api = Api(base_url, repo, token)
    opened = existing = failed = 0
    for finding in findings:
        sev, vid, pkg = finding[:3]
        title = issue_title(vid, pkg, image)
        if dry_run:
            print(f"  would open: {title}")
            continue
        if opened >= max_issues:
            print(f"  limit of {max_issues} new issues reached; the rest wait for the next run")
            break
        try:
            if api.issue_exists(title, vid):
                existing += 1
                continue
            issue = api.create_issue(title, issue_body(finding, image))
            opened += 1
            print(f"  opened [{sev}] {vid} ({pkg}): {(issue or {}).get('html_url', '?')}")
        except urllib.error.HTTPError as exc:
            failed += 1
            print(f"  failed {vid} ({pkg}): HTTP {exc.code} {exc.read().decode(errors='replace')[:120]}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            failed += 1
            print(f"  failed {vid} ({pkg}): {exc}")
    if not dry_run:
        print(f"{image}: {opened} opened, {existing} already tracked, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
