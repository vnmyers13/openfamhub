# Releasing

Every `master` commit is its own build (`0.<n>`); CI tests it, publishes it, tags
it `v0.<n>` and deploys it to the `test` VM (see [ci.md](ci.md)). A **release** is
a phase from the release plan in [TODO.md](../TODO.md) that has been confirmed on
`test`. TODO.md is the source of truth for what gets worked on and in what order;
Forgejo issues are how problems get reported and tracked, so the two are kept in
step at the start of each phase, on every build and at release.

## Issues and TODO.md

- Every open issue appears in TODO.md, either in the phase that will fix it or under
  **Open issues**, with a priority on its line:

  | Priority | Meaning |
  |---|---|
  | `**P0**` | Fix before the next release is confirmed (security, data loss, the wall unusable) |
  | `**P1**` | Fix before the next phase starts |
  | `**P2**` | Schedule into a phase |
  | `**P3**` | Someday |

- Reference the issue on the TODO line as a link, `([#N](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/N))`, or as `#N`.
- On Forgejo, a `priority/p0`…`priority/p3` label (or `priority/critical|high|medium|low`)
  records the reporter's view; Trivy issues get one from their severity (CRITICAL → P1,
  HIGH → P2). When the two disagree, TODO.md wins and the label is updated.
- **An issue is complete when every TODO line that names it is ticked** (`- [x]`). The
  `issues` CI job closes it after that build deploys to `test`, with a comment naming
  the build. You can also put `Fixes #N` in a commit message, which closes the issue
  when the commit reaches `master`; tick the TODO line in the same commit.
- Trivy issues close themselves when a scan of a newer build no longer finds them.
  Close one by hand to accept the risk; it won't be reopened.

`scripts/issues.py` does the checking. It needs `ISSUES_TOKEN` (a Forgejo token with
**issue: read and write**; the 1Password Development item `forgejo.vernonmyers.cloud`):

```bash
export ISSUES_TOKEN=...              # or: export ISSUES_TOKEN=$(op read "op://Development/forgejo.vernonmyers.cloud/issues-token")
python3 scripts/issues.py triage     # open issues by priority, and drift from TODO.md
python3 scripts/issues.py close-done # what would close; add --apply to close
python3 scripts/issues.py triage --strict   # exit 1 unless issues and TODO.md agree and no P0 is open
```

`triage` lists open issues TODO.md doesn't mention (with a line ready to paste),
issues TODO.md marks done that are still open, closed issues whose TODO line isn't
ticked, and priority mismatches.

## Starting a phase

1. Run `python3 scripts/issues.py triage`. Add every unmentioned issue to TODO.md
   (into the phase that will fix it, or **Open issues**) with a priority, and update
   any label that disagrees.
2. Fix open **P0** and **P1** items before starting the phase's feature work.
3. Write the phase's tests first, as TODO.md asks.

## On every push to master

CI runs: tests → `publish` (images + `v0.<n>` tag) → `deploy` to `test` → `trivy`
(scan, open and close Trivy issues) and `issues` (close issues TODO.md marks done,
print the triage report). The last two never fail the pipeline; read their logs.

## Releasing a phase

1. **Ticked and green.** Every item in the phase is ticked in TODO.md and CI is green.
2. **Issues agree.** `python3 scripts/issues.py triage --strict` passes: no open P0,
   nothing done-but-open, nothing unmentioned. Fix TODO.md or the issues until it does.
   The `issues` job will have closed what the phase completed; `close-done --apply`
   does the same by hand.
3. **Confirmed on test.** Check the build on the `test` VM
   (`curl -s https://openfamhub.vernonmyers.cloud/api/health`, `build` field) and try
   the phase's features.
4. **Record it.**
   - TODO.md: put the build in the release plan's **Shipped in** column.
   - CHANGELOG.md: turn the phase's `[Unreleased]` entry into `[0.<n>] - <date> — Phase N`,
     and list the issues it closed (`#N`).
   - `docs/releases/v0.<n>.md`: what's in it, upgrade notes, issues closed, checks.
5. **Push** to the primary first, then the mirrors and GitHub (zsh: no `#` comments when pasting):
   ```bash
   git push forgejo master
   ```
   After CI has tagged the build:
   ```bash
   git fetch forgejo --tags
   for r in forgejo-mirror1 forgejo-mirror2 origin; do git push $r master v0.<n>; done
   ```
6. **Forgejo release** from the notes:
   ```bash
   jq -n --rawfile body docs/releases/v0.<n>.md '{tag_name:"v0.<n>",name:"v0.<n> — Phase N",body:$body}' |
     curl -sS -X POST -H "Authorization: token $ISSUES_TOKEN" -H 'Content-Type: application/json' \
     -d @- https://forgejo.vernonmyers.cloud/api/v1/repos/vernon/OpenFamHub/releases
   ```
   Creating a release needs a token with **repository: write**; use a separate token
   if `ISSUES_TOKEN` only has issue scope.
