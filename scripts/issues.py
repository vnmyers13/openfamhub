#!/usr/bin/env python3
"""Keep Forgejo issues and TODO.md in step (part of the release process, docs/releasing.md).

Usage:
    issues.py triage     [--todo TODO.md] [--strict]
    issues.py close-done [--todo TODO.md] [--apply]

triage      Ranks open issues by priority and compares them with TODO.md, which is the
            source of truth for what gets worked on. Lists open issues TODO.md doesn't
            mention (with a line to paste under "## Open issues"), issues TODO.md
            marks done that are still open, TODO items whose issue is closed, and
            priority mismatches. --strict exits 1 if anything needs attention or a
            P0 issue is open.
close-done  Closes open issues that TODO.md marks done (every checkbox line naming
            the issue is ticked), with a comment naming the build. Dry run unless
            --apply.

Priorities are P0 (fix before the next release), P1 (before the next phase starts),
P2 (schedule into a phase) and P3 (someday). TODO.md gives an item's priority as
**P0**-**P3** on its line; on Forgejo it comes from a `priority/p0`-`priority/p3` (or
`priority/critical|high|medium|low`) label, else from a [trivy] issue's severity.
Issues are referenced in TODO.md as #N or by their /issues/N link.

Env: FORGEJO_URL (default https://forgejo.vernonmyers.cloud), FORGEJO_REPO (default
vernon/OpenFamHub), ISSUES_TOKEN (issue read/write; reads work without it on a public
repo). Exit 2 on usage or API errors.
"""

import argparse
import os
import re
import subprocess
import sys

from forgejo_api import ApiError, Forgejo, describe

CHECKBOX = re.compile(r"^\s*[-*] \[( |x|X)\]")
REF = re.compile(r"(?:(?<![\w/&])#|/issues/)(\d+)\b")
TODO_PRIORITY = re.compile(r"\*\*P([0-3])\*\*")
LABEL_PRIORITY = {
    "p0": 0, "critical": 0, "p1": 1, "high": 1, "p2": 2, "medium": 2, "p3": 3, "low": 3,
}
SEVERITY_PRIORITY = {"CRITICAL": 1, "HIGH": 2}


def parse_todo(path):
    """Map issue number -> {"done": [bool, ...], "mentioned": bool, "priority": int|None}."""
    refs = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            numbers = {int(n) for n in REF.findall(line)}
            if not numbers:
                continue
            box = CHECKBOX.match(line)
            prio = TODO_PRIORITY.search(line)
            for n in numbers:
                entry = refs.setdefault(n, {"done": [], "priority": None})
                if box:
                    entry["done"].append(box.group(1) != " ")
                if prio and entry["priority"] is None:
                    entry["priority"] = int(prio.group(1))
    return refs


def todo_done(entry):
    return bool(entry["done"]) and all(entry["done"])


def issue_priority(issue):
    for label in issue.get("labels") or []:
        name = (label.get("name") or "").lower()
        if name.startswith("priority/") or name.startswith("priority:"):
            p = LABEL_PRIORITY.get(name.split("/", 1)[-1].split(":", 1)[-1].strip())
            if p is not None:
                return p
    if (issue.get("title") or "").startswith("[trivy]"):
        m = re.search(r"Severity: \*\*(\w+)\*\*", issue.get("body") or "")
        if m:
            return SEVERITY_PRIORITY.get(m.group(1))
    return None


def fmt_p(p):
    return f"P{p}" if p is not None else "P?"


def build_label():
    try:
        with open("VERSION", encoding="utf-8") as fh:
            build = f"0.{fh.read().strip()}"
    except OSError:
        return "this build"
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        return f"build {build} ({sha})"
    except (OSError, subprocess.CalledProcessError):
        return f"build {build}"


def triage(api, refs, strict):
    try:
        open_issues = api.issues("open")
        closed_numbers = {i["number"] for i in api.issues("closed")}
    except ApiError as exc:
        print(f"Can't list issues: {describe(exc)}", file=sys.stderr)
        return 2
    missing = [i for i in open_issues if i["number"] not in refs]
    done_but_open = [i for i in open_issues if i["number"] in refs and todo_done(refs[i["number"]])]
    open_but_closed = sorted(
        n for n, e in refs.items() if n in closed_numbers and e["done"] and not todo_done(e)
    )
    mismatched = []
    for i in open_issues:
        e = refs.get(i["number"])
        lp = issue_priority(i)
        if e and e["priority"] is not None and lp is not None and e["priority"] != lp:
            mismatched.append((i, e["priority"], lp))

    def effective(i):
        e = refs.get(i["number"])
        return e["priority"] if e and e["priority"] is not None else issue_priority(i)

    def rank(i):
        p = effective(i)
        return (p if p is not None else 9, i["number"])

    open_issues.sort(key=rank)
    counts = {}
    for i in open_issues:
        counts[fmt_p(effective(i))] = counts.get(fmt_p(effective(i)), 0) + 1
    p0 = [i for i in open_issues if effective(i) == 0]

    print(f"Open issues: {len(open_issues)} ("
          + ", ".join(f"{k} {counts[k]}" for k in sorted(counts)) + ")")
    for i in open_issues:
        where = "in TODO.md" if i["number"] in refs else "NOT in TODO.md"
        print(f"  {fmt_p(effective(i))} #{i['number']} {i['title']} [{where}]")

    if missing:
        print("\nOpen issues TODO.md doesn't mention. Add them under \"## Open issues\" "
              "(or to the phase that will fix them), set the priority, then re-run:")
        for i in missing:
            p = issue_priority(i)
            print(f"  - [ ] **{fmt_p(p if p is not None else 2)}** {i['title']} "
                  f"([#{i['number']}]({api.web}/issues/{i['number']}))")
    if done_but_open:
        print("\nTODO.md marks these done but they're still open (scripts/issues.py close-done --apply):")
        for i in done_but_open:
            print(f"  #{i['number']} {i['title']}")
    if open_but_closed:
        print("\nClosed on Forgejo but not ticked in TODO.md (tick them, or reopen the issue):")
        for n in open_but_closed:
            print(f"  #{n}")
    if mismatched:
        print("\nPriority differs between TODO.md and Forgejo (TODO.md wins; update the label):")
        for i, tp, lp in mismatched:
            print(f"  #{i['number']} TODO.md {fmt_p(tp)}, Forgejo {fmt_p(lp)}: {i['title']}")
    if p0:
        print(f"\n{len(p0)} P0 issue(s) open: fix them before releasing.")

    attention = missing or done_but_open or open_but_closed or mismatched or p0
    if not attention:
        print("\nIssues and TODO.md agree.")
    return 1 if strict and attention else 0


def close_done(api, refs, apply):
    try:
        open_issues = api.issues("open")
    except ApiError as exc:
        print(f"Can't list issues: {describe(exc)}", file=sys.stderr)
        return 2
    targets = [i for i in open_issues if i["number"] in refs and todo_done(refs[i["number"]])]
    if not targets:
        print("No open issues are marked done in TODO.md.")
        return 0
    label = build_label()
    status = 0
    for i in targets:
        if not apply:
            print(f"  would close #{i['number']} {i['title']}")
            continue
        try:
            api.comment(i["number"], f"Marked done in TODO.md as of {label}. Closed by scripts/issues.py.")
            api.close(i["number"])
            print(f"  closed #{i['number']} {i['title']}")
        except ApiError as exc:
            status = 2
            print(f"  failed to close #{i['number']}: {describe(exc)}")
    if not apply:
        print("Dry run; re-run with --apply to close them.")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["triage", "close-done"])
    parser.add_argument("--todo", default="TODO.md")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        refs = parse_todo(args.todo)
    except OSError as exc:
        print(f"Can't read {args.todo}: {exc}", file=sys.stderr)
        return 2
    api = Forgejo(
        os.environ.get("FORGEJO_URL", "https://forgejo.vernonmyers.cloud"),
        os.environ.get("FORGEJO_REPO", "vernon/OpenFamHub"),
        os.environ.get("ISSUES_TOKEN", ""),
    )
    if args.command == "triage":
        return triage(api, refs, args.strict)
    return close_done(api, refs, args.apply)


if __name__ == "__main__":
    sys.exit(main())
