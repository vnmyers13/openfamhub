#!/usr/bin/env python3
"""Parse Trivy JSON reports and create Gitea/Forgejo issues for HIGH/CRITICAL findings."""

import json
import sys
import urllib.error
import urllib.request


def main():
    if len(sys.argv) != 6:
        print(
            f"Usage: {sys.argv[0]} <gitea_url> <repo> <token> <image> <report_path>",
            file=sys.stderr,
        )
        sys.exit(1)

    trivy_url, repo, token, image, report_path = sys.argv[1:6]

    data = json.load(open(report_path))
    findings: set[tuple[str, str, str, str]] = set()

    for result in data.get("Results", []):
        for v in result.get("Vulnerabilities", []):
            sev = v.get("Severity", "UNKNOWN")
            if sev in ("HIGH", "CRITICAL"):
                pkg = v.get("PkgName", "unknown")
                vid = v.get("VulnerabilityID", "N/A")
                desc = v.get("Description", "")[:200]
                findings.add((vid, pkg, sev, desc))

    if not findings:
        print(f"No high/critical findings in {image}")
        return

    url = f"{trivy_url}/api/v1/repos/{repo}/issues"

    for vid, pkg, sev, desc in sorted(findings):
        title = f"[trivy] {vid}: {pkg} in {image}"
        body = (
            f"Severity: **{sev}**\n\n"
            f"Package: `{pkg}`\n\n"
            f"ID: `{vid}`\n\n"
            f"{desc}\n\n"
            f"---\n"
            f"Report: trivy-{image}.json (see CI artifacts)"
        )
        print(f"Creating issue: [{sev}] {vid} ({pkg})")

        payload = json.dumps({"title": title, "body": body}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"token {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            resp = urllib.request.urlopen(req)
            status = json.loads(resp.read())
            print(f"  Created: {status['html_url']}")
        except urllib.error.HTTPError as e:
            # Skip duplicates (422) and other non-fatal errors
            print(f"  Skipped: {e.code} {e.read().decode()[:120]}")


if __name__ == "__main__":
    main()
