#!/usr/bin/env python3
"""Keep Forgejo issues in step with a Trivy JSON report.

Usage:
    TRIVY_ISSUE_TOKEN=... create_trivy_issues.py <forgejo_url> <owner/repo> <image> <report.json>

<image> is the scanned image, e.g. openfamhub-api:0.97. The token is read from the
environment, never from argv, so it doesn't show up in process listings or CI logs.

- Opens one issue per HIGH/CRITICAL (vulnerability, package, image name). The tag is
  left out of the title so a finding that survives several releases keeps one issue.
  An issue whose title already exists, open or closed, is not opened again, so
  closing an issue by hand (risk accepted) keeps it closed.
- Closes open [trivy] issues for this image whose finding is no longer in the report,
  with a comment naming the build that no longer has it.
- Opens at most TRIVY_MAX_ISSUES (default 20) issues per run.
- TRIVY_DRY_RUN=1 prints what would change without calling the API.

Network and API errors are reported but never fail the run (exit code 0); a missing
token, bad arguments or an unreadable report exit with 2.
"""

import json
import os
import re
import sys

from forgejo_api import ApiError, Forgejo, describe

SEVERITIES = ("CRITICAL", "HIGH")
TITLE_RE = re.compile(r"^\[trivy\] (?P<vid>\S+): (?P<pkg>.+) in (?P<image>\S+)$")


def load_findings(report_path):
    """Return sorted (severity, id, pkg, installed, fixed, summary) tuples."""
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


def image_name(image):
    return image.split(":")[0]


def issue_title(vid, pkg, image):
    return f"[trivy] {vid}: {pkg} in {image_name(image)}"


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
        "Opened by the CI Trivy job, which closes it once a scan no longer finds it. "
        "Close it by hand to accept the risk; it won't be reopened."
    )


def main(argv):
    if len(argv) != 5:
        print(__doc__.strip().splitlines()[3].strip(), file=sys.stderr)
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

    name = image_name(image)
    print(f"{image}: {len(findings)} HIGH/CRITICAL finding(s)")
    if dry_run:
        for f in findings:
            print(f"  would open (unless tracked): {issue_title(f[1], f[2], image)}")
        return 0

    api = Forgejo(base_url, repo, token)
    try:
        issues = api.issues(state="all")
    except ApiError as exc:
        print(f"  can't list issues: {describe(exc)}")
        return 0
    titles = {i.get("title") for i in issues}

    opened = existing = failed = 0
    for finding in findings:
        sev, vid, pkg = finding[:3]
        title = issue_title(vid, pkg, image)
        if title in titles:
            existing += 1
            continue
        if opened >= max_issues:
            print(f"  limit of {max_issues} new issues reached; the rest wait for the next run")
            break
        try:
            issue = api.create_issue(title, issue_body(finding, image))
            opened += 1
            titles.add(title)
            print(f"  opened [{sev}] {vid} ({pkg}): {(issue or {}).get('html_url', '?')}")
        except ApiError as exc:
            failed += 1
            print(f"  failed {vid} ({pkg}): {describe(exc)}")

    current = {(f[1], f[2]) for f in findings}
    closed = 0
    for issue in issues:
        m = TITLE_RE.match(issue.get("title") or "")
        if issue.get("state") != "open" or not m or m["image"] != name:
            continue
        if (m["vid"], m["pkg"]) in current:
            continue
        number = issue.get("number")
        try:
            api.comment(number, f"No longer found in `{image}`. Closed by the CI Trivy job.")
            api.close(number)
            closed += 1
            print(f"  closed #{number} {m['vid']} ({m['pkg']}): fixed in {image}")
        except ApiError as exc:
            failed += 1
            print(f"  failed to close #{number}: {describe(exc)}")

    print(f"{name}: {opened} opened, {existing} already tracked, {closed} closed, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
