# Per-Commit Release Number Design

**Goal:** Give every commit its own version, `0.<n>`, where `n` increases by
exactly one per commit and can never be skipped or forgotten. Today's tip is
`0.30`; the next commit is `0.31`, the one after `0.32`, and so on. The number is
worked out and applied automatically — nobody types it.

**Scope:** A committed integer counter (`VERSION`), a `pre-commit` hook that
bumps it, a `scripts/renumber` helper for rebases, a CI check that refuses a
commit whose bump is wrong, and propagation of the one value into the image
tag/label, `OPENFAMHUB_BUILD`, `/api/health`, the app footer, the README badge,
and an annotated `v0.<n>` tag. Retires the CI `gitea.run_number` build suffix.
Documentation and the CHANGELOG.

**Out of scope:** the major component (`0.` stays fixed); rewriting historical
tags (`v0.10`–`v0.29` and the retired `main` line stay as they are); true semver
semantics (breaking/feature/fix); publishing images from non-`master` commits.

## Background

- The version lives in one place: `APP_VERSION = "0.30"` in
  `backend/app/core/config.py`. It is *duplicated by hand* into the badge in
  `README.md` and the `LABEL org.opencontainers.image.version` in
  `backend/Dockerfile`.
- `scripts/deploy.sh` reads that literal with `app_version()`
  (`sed -n 's/^APP_VERSION = "\(.*\)"/\1/p'`) and resolves the effective version
  with precedence: explicit argument → `$OPENFAMHUB_VERSION` → `.env` →
  `APP_VERSION`.
- Today CI layers a *per-run* suffix on top: `.gitea/workflows/ci.yml` sets
  `BUILD_NUMBER: ${{ gitea.run_number }}`, and `resolve_version()` appends it, so
  a master push publishes `0.30.17` and also moves `:0.30` / `:latest`. This
  number is tied to the CI run, not the commit — rebuilding the same SHA gets a
  different tag, and a commit that is not the tip of a master push gets none.
- History shows the hand-bumped scheme drifting: `0.10 … 0.15`, then `0.17`,
  `0.18`, then a jump to `0.30` (see `CHANGELOG.md`, which explains `0.19–0.29`
  belonged to a retired line). Gaps `0.16`, `0.27`, `0.28` were never used.
- The value is surfaced to operators two ways: the API reports it at
  `/api/health` (`version`, `build`, `commit`) and the app sidebar shows
  `VITE_APP_BUILD` (`frontend/src/components/NavShell.tsx`).
- There is no hook framework in the repo today (`core.hooksPath` is unset, no
  husky/lefthook/`.pre-commit-config.yaml`).

## Design

### The one number

`VERSION` at the repository root holds a single integer — the count after the
dot.

```
30
```

The release string is always `0.` + that integer. So `VERSION=30` is `0.30`, and
the commit that bumps it to `31` is `0.31`. The integer is a plain counter with
no semver meaning; `0.` is a fixed prefix.

Because `VERSION` sits at the repo root, it is **not** inside either image build
context (`backend/` and `frontend/`), so images cannot read it directly. They
receive the resolved string as a build argument, exactly as they do today with
`OPENFAMHUB_BUILD` (see below).

### The hook

`.githooks/pre-commit`, enabled per-clone with `git config core.hooksPath .githooks`
(recorded in `AGENTS.md` and `GETTING_STARTED.md`). On every commit it:

1. Exits early on a merge commit (`$(git rev-parse --git-dir)/MERGE_HEAD`
   exists) — a merge does not invent a number.
2. Reads `VERSION`, increments by one, writes it back, and `git add`s it.
3. Rewrites the README badge line `version-0.<n>-blue` to match, using
   `sed -i.bak … && rm -f README.md.bak` (portable across macOS and GNU sed),
   and `git add`s `README.md`.

The hook only ever *adds* to the staged tree; it never removes work.

Known behaviours, documented rather than hidden:

- `git commit --amend` re-runs the hook and consumes another number (the
  amended commit is `+1` again). Acceptable: numbers are cheap and the number
  still moves forward on that branch.
- `git commit --no-verify` skips the bump. The CI check below is the backstop.
- A **rebase** replays commits without running the hook, so their `VERSION`
  values can fall out of step; run `scripts/renumber` afterwards (next section).
- `core.hooksPath` is local `.git/config`, so a fresh clone has no hook until it
  runs the one-line config command.

### Branches, rebases, and merges

The repository works on branches one commit per logical change, but the counter
is single and shared, so the strict "parent + 1" rule cannot hold on *every*
commit in a diverging workflow. The rule is therefore scoped:

- **The invariant CI enforces:** along `master`'s first-parent chain, each
  commit's `VERSION` is exactly one greater than its first parent's.
- Branches carry **provisional** numbers while they are in flight. Two branches
  started from the same commit may both say `31`; that is allowed, because only
  the number on `master` matters for a release.

The hook still numbers every commit it creates (parent + 1), so WIP commits are
numbered and unique on their own branch. Two operations need help, both handled
by a new `scripts/renumber`:

- **After a rebase**, replayed commits keep their old `VERSION` values, which are
  no longer parent + 1. `scripts/renumber [base]` (base defaults to
  `git merge-base HEAD master`) walks `base..HEAD` and rewrites each commit's
  `VERSION` to `base_value + 1, +2, …`. It is implemented as
  `git rebase --exec 'scripts/renumber --step' "$base"`, where `--step` reads
  `git show HEAD^:VERSION`, adds one, writes `VERSION`, and
  `git commit --amend --no-edit`s. This is run by hand after a rebase; it is not
  automatic, because it rewrites commits.
- **Before landing on `master`**, run `scripts/renumber` against `master` so the
  branch's numbers continue from master's head. A fast-forward then lands a
  clean +1 chain. If a merge commit is used instead, the hook skips it (no
  number) and the next commit on `master` continues the chain.

### The CI check (backstop)

A `version` job in `.gitea/workflows/ci.yml`, running on all pushes and PRs.
**My call during review:** the job checks out full history
(`builtin:checkout` with `fetch-depth: 0`) — a shallow checkout has no parent
commit, which would make every commit look parentless and silently pass. For a
push it walks every commit in the pushed range (`before..after`), not just the
tip, so a `--no-verify` commit in the middle of a range is caught too.

Enforcement is scoped to match the invariant above:

- **On `master`:** walk the first-parent chain; skip merges, the initial commit,
  and any commit whose parent has no `VERSION` (adoption). **Fail unless each
  commit's `VERSION` is exactly its first parent's plus one.**
- **On a branch or PR:** do not require +1 (numbers are provisional), but still
  **fail if a commit's `VERSION` does not strictly exceed the merge-base's**, so
  a `--no-verify` commit that skipped its bump entirely is caught.

**My call:** `publish` and `deploy` declare `needs: [version]`, so an invalid
commit cannot publish or deploy even before branch protection is configured.
Turning on "require status checks before merge" for `master` is documented as
the complement, not a prerequisite.

This makes a `--no-verify` or tool-generated commit impossible to land on
`master` unnumbered.

### Propagating the value

`scripts/deploy.sh`:

- `app_version()` becomes `echo "0.$(cat VERSION)"` (replacing the `sed` on
  `config.py`).
- `resolve_version()` drops the `BUILD_NUMBER` suffix branch entirely. Version
  precedence stays: explicit argument → `$OPENFAMHUB_VERSION` → `.env` →
  `VERSION`.
- `publish()` drops the "a build tag also moves the release tag" special case
  (there is no separate base tag any more). Each commit publishes
  `:<VERSION>` and `:latest`, the `--label org.opencontainers.image.version`
  and the `OPENFAMHUB_BUILD`/`OPENFAMHUB_COMMIT` build args are unchanged, and
  the short SHA continues to be reported as `commit`.

`backend/app/core/config.py`:

- Replace the `APP_VERSION = "0.30"` literal with a resolver: use
  `OPENFAMHUB_BUILD` from the environment when it is set and not `dev`
  (the published-image case); otherwise read `_PROJECT_ROOT / "VERSION"` and
  return `0.<n>` (the dev-checkout case); otherwise fall back to `0.0-dev`.
- `settings.app_version` defaults to that value, so `/api/health` `version`
  and `build` now agree — with a per-commit number there is no longer a "base"
  versus "build" distinction.

`backend/Dockerfile`:

- Make the label derive from a build arg instead of a second hardcoded literal:
  `ARG APP_VERSION=dev` → `LABEL … org.opencontainers.image.version=$APP_VERSION`,
  with `publish` passing `--build-arg APP_VERSION=$VERSION`.

`.gitea/workflows/ci.yml`:

- Delete the `BUILD_NUMBER` env line.

**Build-from-source parity (my call during review).** Today `scripts/deploy.sh
deploy` builds `./backend` and `./frontend` with plain `docker compose up
--build`, so those images would report `0.0-dev` — a regression from the `0.30`
they show now. To keep them honest, `deploy_local()` resolves the version the
same way `publish()` does and exports it, and `docker-compose.yml` passes it
into both builds:

```yaml
build:
  context: ./backend
  args:
    APP_VERSION: ${OPENFAMHUB_VERSION:-dev}
    OPENFAMHUB_BUILD: ${OPENFAMHUB_VERSION:-dev}
```

so a from-source stack reports the same `0.<n>` as a released image.

**Version overrides (my call during review).** `publish`/`remote`/`server` keep
the explicit-argument and `$OPENFAMHUB_VERSION` overrides for manual roll-forward
and rollback, but CI passes neither, so a CI build always uses the commit's own
`VERSION`. The `v0.<n>` git tag is only created when the resolved version equals
`0.$(cat VERSION)` — i.e. never for a manual override — so a deliberate
republish under an old number cannot move a tag.

### Tagging

`scripts/deploy.sh publish` creates the annotated `v0.<n>` tag on the commit it
builds and **pushes it to `forgejo`**, using the credentials `builtin:checkout`
already has for that remote. The GitHub `origin` mirror is *not* updated by CI —
tags there stay a manual step, matching the existing "GitHub is a mirror only"
stance. Tags are created at publish time (master only) rather than by the hook,
so everyday WIP commits do not litter the tag namespace.

### Docs and CHANGELOG

- `docs/ci.md`: replace the "Build numbers" section with a "Version numbering"
  section describing `VERSION`, the hook, the CI check, and the one-number
  rule.
- `docs/deployment.md`: update the `OPENFAMHUB_VERSION` row and the rollback
  note (rollback targets are now `0.<n>` per-commit tags).
- `AGENTS.md`: add the `core.hooksPath` setup line and the "bump is automatic"
  rule; update the CI gotcha.
- `README.md`: badge text is hook-maintained; the `publish` example comment
  loses its `v0.30` figure.
- `CHANGELOG.md`: fold the `[Unreleased] - 0.30.x builds` note into a `0.31`
  entry describing automatic per-commit numbering.

### Seeding

Set `VERSION=30` in the commit that introduces it, so the hook bumps the *next*
commit to `31` — the next commit is `0.31`, matching the request.

## Verification

- `cat VERSION` is `30`; the first commit made after adoption has `VERSION=31`,
  a README badge reading `version-0.31-blue`, and an `OpenFamHub 0.31` sidebar.
- `git commit --no-verify` with an unchanged `VERSION` → the CI `version` job
  fails; a correct `+1` passes; a merge commit is skipped.
- On a branch: two commits that both claim `31` pass CI (provisional). After
  `git rebase master` without renumbering, `scripts/renumber` restores the +1
  chain and CI on the branch is green.
- `scripts/deploy.sh publish` (or a dry inspection of the built tags) shows
  `:<VERSION>` and `:latest`, no `.<run>` suffix, and an `v0.<n>` tag; the
  `org.opencontainers.image.version` label matches.
- `curl -s localhost:8000/api/health` returns matching `version` and `build`
  (`0.31`), and `commit` is the short SHA.
- `cd backend && source .venv/bin/activate && pytest -q` and
  `cd frontend && npm run lint && npm run build` still pass.
- `grep -rn "run_number\|BUILD_NUMBER"` returns nothing but the docs that
  describe its removal.

## Acceptance Criteria

- Along `master`'s first-parent chain, every commit's `VERSION` is exactly one
  greater than its parent's, enforced by the hook and re-checked in CI.
- A branch commit is never unnumbered: it either bumped `VERSION` (from the
  hook) or CI rejects it for not exceeding the merge-base.
- The next commit is `0.31`; the commit after is `0.32`.
- A single value drives the image tag, image label, `OPENFAMHUB_BUILD`,
  `/api/health` (`version` and `build`), the app footer, the README badge, and
  the `v0.<n>` tag.
- The `gitea.run_number` suffix and the `BUILD_NUMBER` env var are gone.
- A `--no-verify` commit cannot reach `master` without a correct `+1` bump.
