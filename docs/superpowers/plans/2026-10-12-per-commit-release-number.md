# Per-Commit Release Number Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every commit carry its own version `0.<n>`, incrementing by exactly one per commit, applied automatically by a git hook and enforced in CI.

**Architecture:** A single committed integer (`VERSION`) is the only source of the number. A `pre-commit` hook bumps it on every commit; a `scripts/check-version.sh` guard (run locally and in CI) rejects any commit whose number moved wrongly; a `scripts/renumber` helper fixes a branch after a rebase. The one value flows into the image tag and label, the API's `version`/`build`, the app footer, the README badge, and an annotated `v0.<n>` tag. The CI-run-number suffix is removed.

**Tech Stack:** Bash (`scripts/`), Python 3.12 + pydantic-settings (backend), pytest, pytest-asyncio, Gitea Actions (`.gitea/workflows/ci.yml`), Docker buildx.

**Spec:** `docs/superpowers/specs/2026-10-12-per-commit-release-number-design.md`

## Global Constraints

- The release string is exactly `0.` followed by the integer in `VERSION` (repo root). No other shape; the `0.` prefix is fixed.
- `VERSION` is the single source of the number. Exactly one increment per commit; nothing types the number by hand.
- Current tip is `0.30`. After adoption, the next committed number is `0.31`, then `0.32`.
- The `+1` rule is enforced only along `master`'s **first-parent** chain. On any other branch or PR, numbers are provisional: a commit must merely exceed the merge-base's number.
- No `BUILD_NUMBER` environment variable and no `gitea.run_number` anywhere in the repository or its docs.
- Release tags are annotated `v0.<n>`, created only when the build version equals `0.$(cat VERSION)`, pushed to `forgejo` only (never the GitHub `origin` mirror).
- Images are published from `master` pushes only (unchanged from today).
- `main`-line history and existing tags `v0.10`–`v0.29` are not rewritten.
- Shell scripts are `#!/bin/bash` with `set -euo pipefail`, run from the repo root, and use the existing `log`/`warn`/`error` helpers in `scripts/deploy.sh`.
- Backend tests run as `cd backend && source .venv/bin/activate && pytest -v`.
- Merge commits and the initial commit get no number; the chain continues on the next commit.

## Review Focus

- **A commit with nothing staged** (`git commit --allow-empty`, or after staging only the hook's own changes): the hook must still leave `VERSION` exactly one higher than the parent — a reasonable person expects an empty commit to be numbered like any other, not to reuse the previous number.
- **A missing, empty, or non-numeric `VERSION`** (deleted by accident, a stray newline, a bad merge, `VERSION` containing `thirty`): the hook and every reader must fail loudly or fall back to `0.0-dev` — never write `0.` + junk or silently emit `0.` .
- **A rebase that leaves duplicate or backwards numbers on a branch** (`31, 31, 29`): `scripts/check-version.sh` must fail it and `scripts/renumber` must restore a clean `+1` chain.
- **A `--no-verify` commit**, or one made on a fresh clone where `core.hooksPath` was never configured: `scripts/check-version.sh` on `master` must reject it, and the CI `version` job must therefore fail.
- **A merge commit landing on `master`**: it is skipped, and the *next* commit must still be exactly `first-parent + 1` (not `+2` against the skipped merge).

---

### Task 1: Adopt the counter and the pre-commit hook

**Files:**
- Create: `VERSION`
- Create: `.githooks/pre-commit`
- Modify: `README.md:3` (badge line)
- Modify: `AGENTS.md` (setup + rule)
- Modify: `GETTING_STARTED.md` (setup note)

**Interfaces:**
- Produces: `VERSION` at the repo root, containing a single integer and a trailing newline (e.g. `30\n`). Every later task reads this file.
- Produces: `.githooks/pre-commit`, executable, which increments `VERSION` by one and stages it, and rewrites the README badge line to `version-0.<n>-blue`.

- [ ] **Step 1: Create the counter**

```bash
printf '30\n' > VERSION
```

- [ ] **Step 2: Write the hook**

Create `.githooks/pre-commit`, then `chmod +x .githooks/pre-commit`:

```bash
#!/bin/bash
# Bump VERSION by one for every commit (see docs/superpowers/specs/2026-10-12-per-commit-release-number-design.md).
set -euo pipefail

# A merge does not invent a number.
[ -e "$(git rev-parse --git-dir)/MERGE_HEAD" ] && exit 0

if [ ! -f VERSION ]; then
    echo "pre-commit: VERSION file is missing; refusing to commit." >&2
    exit 1
fi
n=$(tr -d '[:space:]' < VERSION)
case "$n" in
    ''|*[!0-9]*)
        echo "pre-commit: VERSION must contain a single integer, got '$n'." >&2
        exit 1
        ;;
esac
n=$((n + 1))
printf '%s\n' "$n" > VERSION
git add VERSION

# Keep the README badge honest. `sed -i.bak` is portable across macOS and GNU sed.
if [ -f README.md ]; then
    sed -i.bak "s|version-[0-9][0-9]*-blue|version-0.${n}-blue|g" README.md
    rm -f README.md.bak
    git add README.md
fi
```

- [ ] **Step 3: Commit the counter and hook (hook not yet active)**

Run: `git add VERSION .githooks/pre-commit && git commit -m "feat: add per-commit version counter and hook"`
Expected: `VERSION` is still `30` (the hook is not enabled yet, because `core.hooksPath` is unset), and `git show HEAD:VERSION` prints `30`.

- [ ] **Step 4: Enable the hook**

Run: `git config core.hooksPath .githooks`
Expected: `git config core.hooksPath` prints `.githooks`.

- [ ] **Step 5: Prove the hook bumps on the next commit**

Run: `printf '\n' >> README.md && git add README.md && git commit -m "docs: enable the version hook" && cat VERSION`
Expected: `VERSION` prints `31` and `git show HEAD:VERSION` prints `31`; `README.md` shows `version-0.31-blue`.

- [ ] **Step 6: Test the guard rails (Review Focus: empty commit, bad `VERSION`)**

Run each in a scratch clone so the working repo is untouched:

```bash
tmp=$(mktemp -d); git clone -q . "$tmp/t"; cd "$tmp/t"; git config core.hooksPath .githooks
# empty commit still bumps:
before=$(cat VERSION); git commit --allow-empty -m x; test "$(cat VERSION)" = "$((before+1))" && echo "empty-ok"
# non-numeric VERSION is refused:
printf 'thirty\n' > VERSION; git add VERSION; git commit -m x 2>&1 | grep -q 'must contain a single integer' && echo "bad-version-ok"
cd - >/dev/null; rm -rf "$tmp"
```

Expected: prints `empty-ok` then `bad-version-ok` (use `git commit --no-verify` is *not* used here; the second commit is expected to fail, so wrap it so the script continues).

- [ ] **Step 7: Document the one-line setup and the rule**

In `AGENTS.md`, add to the "Version and branches" section:

> After cloning, run `git config core.hooksPath .githooks`. The `pre-commit` hook bumps `VERSION` (repo root) by one on every commit; the release string is `0.<VERSION>`. The next commit is `0.31`. Do not edit `VERSION` by hand.

In `GETTING_STARTED.md`, add the same `git config core.hooksPath .githooks` line to the setup steps.

- [ ] **Step 8: Commit**

```bash
git add AGENTS.md GETTING_STARTED.md
git commit -m "docs: document the version hook setup"
```

---

### Task 2: The app reads the number

**Files:**
- Modify: `backend/app/core/config.py:10`
- Modify: `backend/Dockerfile:3,17`
- Modify: `docker-compose.yml:13,27`
- Test: `backend/tests/test_version.py` (create)

**Interfaces:**
- Produces: `backend.app.core.config._resolve_version(build_env: str | None = None, version_path: Path | None = None) -> str`. Returns `0.<n>` from the version file, `OPENFAMHUB_BUILD` when it is set and not `dev`, else `0.0-dev`.
- Produces: `APP_VERSION` module constant and `settings.app_version`, both equal to `_resolve_version()`.
- Consumes: `VERSION` from Task 1.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_version.py`:

```python
"""The app's view of the release number (spec: per-commit release number)."""
from pathlib import Path

from app.core.config import _resolve_version


def test_reads_version_file(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("31\n", encoding="utf-8")
    assert _resolve_version(version_path=vf) == "0.31"


def test_build_env_wins(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("31\n", encoding="utf-8")
    assert _resolve_version(build_env="0.31.7", version_path=vf) == "0.31.7"


def test_dev_env_falls_through_to_file(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("31\n", encoding="utf-8")
    assert _resolve_version(build_env="dev", version_path=vf) == "0.31"


def test_missing_file_falls_back(tmp_path: Path):
    assert _resolve_version(version_path=tmp_path / "nope") == "0.0-dev"


def test_non_numeric_file_falls_back(tmp_path: Path):
    vf = tmp_path / "VERSION"
    vf.write_text("thirty\n", encoding="utf-8")
    assert _resolve_version(version_path=vf) == "0.0-dev"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_version.py -v`
Expected: FAIL — `ImportError: cannot import name '_resolve_version'`.

- [ ] **Step 3: Implement `_resolve_version` and use it**

In `backend/app/core/config.py`, add `import os` to the imports, replace the `APP_VERSION = "0.30"` line with:

```python
def _resolve_version(build_env: str | None = None, version_path: Path | None = None) -> str:
    build = (build_env if build_env is not None else os.environ.get("OPENFAMHUB_BUILD", "")).strip()
    if build and build != "dev":
        return build
    path = version_path if version_path is not None else _PROJECT_ROOT / "VERSION"
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0-dev"
    return f"0.{raw}" if raw.isdigit() else "0.0-dev"


APP_VERSION = _resolve_version()
```

Leave `app_version: str = APP_VERSION` in `Settings` unchanged.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_version.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the whole backend suite for regressions**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: PASS (no new failures).

- [ ] **Step 6: Make the image label derive from a build arg**

In `backend/Dockerfile`:

- Change the label line to `org.opencontainers.image.version=$APP_VERSION` and remove the hardcoded `"0.30"`.
- Add `ARG APP_VERSION=dev` immediately before the `LABEL` instruction.

- [ ] **Step 7: Pass the version into build-from-source images**

In `docker-compose.yml`, add `args` to both the `api` and `web` build stanzas:

```yaml
    build:
      context: ./backend
      args:
        APP_VERSION: ${OPENFAMHUB_VERSION:-dev}
        OPENFAMHUB_BUILD: ${OPENFAMHUB_VERSION:-dev}
```

(mirror the same for the `web` service with `context: ./frontend`).

- [ ] **Step 8: Verify compose still parses**

Run: `OPENFAMHUB_VERSION=0.31 docker compose config >/dev/null && echo compose-ok`
Expected: prints `compose-ok`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/config.py backend/tests/test_version.py backend/Dockerfile docker-compose.yml
git commit -m "feat: resolve the release number from VERSION and build args"
```

---

### Task 3: `scripts/renumber` for rebases

**Files:**
- Create: `scripts/renumber`
- Modify: `GETTING_STARTED.md` (a one-line note: run after a rebase)

**Interfaces:**
- Produces: `scripts/renumber [base]` — renumbers every commit in `base..HEAD` so `VERSION` is `base_value + 1, +2, …`; `base` defaults to `git merge-base HEAD master`.
- Produces: `scripts/renumber --step` — used by `git rebase --exec`; sets `VERSION` to `HEAD^`'s value plus one and amends the current commit (also refreshing the README badge).

- [ ] **Step 1: Write the script**

Create `scripts/renumber` (POSIX-safe bash), `chmod +x`:

```bash
#!/bin/bash
# Renumber commits after a rebase so VERSION is base+1, base+2, ... (see the design spec).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" = "--step" ]; then
    parent=$(git show HEAD^:VERSION)
    n=$((parent + 1))
    printf '%s\n' "$n" > VERSION
    if [ -f README.md ]; then
        sed -i.bak "s|version-[0-9][0-9]*-blue|version-0.${n}-blue|g" README.md
        rm -f README.md.bak
        git add README.md
    fi
    git add VERSION
    git commit --amend --no-edit >/dev/null
    exit 0
fi

base="${1:-$(git merge-base HEAD master)}"
exec git rebase --exec "$0 --step" "$base"
```

- [ ] **Step 2: Verify it restores a `+1` chain after a rebase**

Run in a scratch clone:

```bash
tmp=$(mktemp -d); git clone -q . "$tmp/t"; cd "$tmp/t"; git config core.hooksPath .githooks
git checkout -q -b feat
git commit --allow-empty --no-verify -m a   # deliberately unnumbered
git commit --allow-empty --no-verify -m b   # and again
scripts/renumber master >/dev/null
git log --format='%h %s' master..HEAD
git rev-list --first-parent --reverse master..HEAD | while read c; do
  echo "$(git show "$c":VERSION)"; done
```

Expected: the two VERSION values printed are consecutive (`31`, `32`), i.e. `master`'s value plus one, then plus two. Then `cd - >/dev/null; rm -rf "$tmp"`.

- [ ] **Step 3: Commit**

```bash
git add scripts/renumber GETTING_STARTED.md
git commit -m "feat: add scripts/renumber for post-rebase renumbering"
```

---

### Task 4: `scripts/check-version.sh` guard

**Files:**
- Create: `scripts/check-version.sh`

**Interfaces:**
- Produces: `scripts/check-version.sh <master|branch> <base> <head>` — exits `0` when the rule holds, non-zero with a message naming the offending commit otherwise.
- Consumes: `VERSION` at each commit via `git show <sha>:VERSION`.
- Consumed by: Task 7's CI `version` job, and by developers locally.

Rules:
- `<master>`: for each commit in `git rev-list --first-parent --reverse <base>..<head>`, skip if it is a merge (more than one parent), has no parent, or its parent has no `VERSION`; otherwise fail unless `VERSION == parent VERSION + 1`.
- `<branch>`: for each commit in `<base>..<head>`, skip merges / no-parent / parent-without-`VERSION`; otherwise fail unless `VERSION > base VERSION`.

- [ ] **Step 1: Write the failing test harness**

Create `scripts/tests/check-version-test.sh` (a self-contained bash test using a throwaway repo):

```bash
#!/bin/bash
# Tests for scripts/check-version.sh. Run: bash scripts/tests/check-version-test.sh
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
check="$repo_root/scripts/check-version.sh"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cd "$tmp"; git init -q; git config user.email t@t; git config user.name t
printf '30\n' > VERSION; git add VERSION; git commit -qm init; git branch -m master
init=$(git rev-parse HEAD)
# good +1
printf '31\n' > VERSION; git add VERSION; git commit -qm ok; good=$(git rev-parse HEAD)
# bad: no bump
git commit -q --allow-empty --no-verify -m stale; stale=$(git rev-parse HEAD)
# bad: +2
printf '33\n' > VERSION; git add VERSION; git commit -qm jump; jump=$(git rev-parse HEAD)
"$check" master "$init" "$good" && echo "good-pass"
"$check" master "$init" "$stale" 2>/dev/null && { echo "stale-NOT-detected"; exit 1; } || echo "stale-caught"
"$check" master "$init" "$jump"  2>/dev/null && { echo "jump-NOT-detected"; exit 1; } || echo "jump-caught"
# merge commit is skipped
git checkout -q -b side "$good"; printf '50\n' > VERSION; git add VERSION; git commit -qm side
git checkout -q master; git merge -q --no-ff -m merge side
"$check" master "$init" "$(git rev-parse HEAD)" && echo "merge-skipped"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash scripts/tests/check-version-test.sh`
Expected: FAIL — `scripts/check-version.sh` does not exist yet (`No such file or directory`).

- [ ] **Step 3: Implement `scripts/check-version.sh`**

```bash
#!/bin/bash
# Enforce the release-number rule (see the design spec). Usage: check-version.sh <master|branch> <base> <head>
set -euo pipefail

mode="${1:?usage: check-version.sh <master|branch> <base> <head>}"
base="${2:?}"; head="${3:?}"

version_at() { git show "$1:VERSION" 2>/dev/null | tr -d '[:space:]'; }

fail() { echo "check-version: $1" >&2; exit 1; }

base_version=$(version_at "$base")
[ -n "$base_version" ] || fail "$base has no VERSION (adoption commit) - nothing to check"

if [ "$mode" = "master" ]; then
    revs=$(git rev-list --first-parent --reverse "$base..$head")
else
    revs=$(git rev-list --reverse "$base..$head")
fi

for c in $revs; do
    parents=$(git rev-list --parents -n1 "$c" | wc -w)
    [ "$parents" -gt 2 ] && continue            # merge commit
    parent=$(git rev-parse "$c^" 2>/dev/null || true)
    [ -n "$parent" ] || continue
    pv=$(version_at "$parent")
    [ -n "$pv" ] || continue                    # parent is the adoption commit
    cv=$(version_at "$c")
    case "$cv" in ''|*[!0-9]*) fail "$c has no usable VERSION ('$cv')";; esac
    if [ "$mode" = "master" ]; then
        [ "$cv" -eq "$((pv + 1))" ] || fail "$c VERSION=$cv but parent $pv (expected $((pv + 1)))"
    else
        [ "$cv" -gt "$base_version" ] || fail "$c VERSION=$cv does not exceed base $base_version"
    fi
done
echo "check-version: ok ($mode, $base..$head)"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash scripts/tests/check-version-test.sh`
Expected: prints `good-pass`, `stale-caught`, `jump-caught`, `merge-skipped`.

- [ ] **Step 5: Commit**

```bash
git add scripts/check-version.sh scripts/tests/check-version-test.sh
git commit -m "feat: add scripts/check-version.sh release-number guard"
```

---

### Task 5: `deploy.sh` version plumbing and tagging

**Files:**
- Modify: `scripts/deploy.sh:50-51` (usage), `62-64` (`app_version`), `71-83` (`resolve_version`), `104-114` (`deploy_local`), `133-157` (`publish`)

**Interfaces:**
- Consumes: `VERSION` (Task 1), `--build-arg APP_VERSION` support (Task 2).
- Produces: `app_version()` prints `0.<VERSION>`; `resolve_version()` no longer reads `BUILD_NUMBER`; `publish()` tags the commit `v0.<n>` and pushes it to the current remote when the resolved version equals `app_version()`; `deploy_local()` exports `OPENFAMHUB_VERSION` for the compose build args.

- [ ] **Step 1: Read the version from `VERSION`**

Replace `app_version()` with:

```bash
app_version() {
    [ -f VERSION ] || error "VERSION file not found"
    printf '0.%s' "$(tr -d '[:space:]' < VERSION)"
}
```

- [ ] **Step 2: Drop the run-number suffix**

In `resolve_version()`, delete the `BUILD_NUMBER` branch so it reads:

```bash
resolve_version() {
    VERSION="${1:-${OPENFAMHUB_VERSION:-$(env_value OPENFAMHUB_VERSION)}}"
    if [ -z "$VERSION" ]; then
        VERSION="$(app_version)"
    fi
    [ -n "$VERSION" ] || error "Could not determine the version"
}
```

- [ ] **Step 3: Remove the base-tag move and pass the label arg**

In `publish()`: delete the `base=`/`if [ "$VERSION" != "$base" ] … tags+=(-t "$image:$base")` block, and add `--build-arg "APP_VERSION=$VERSION" \` next to the existing `OPENFAMHUB_BUILD` build arg.

- [ ] **Step 4: Create and push the release tag**

At the end of `publish()`, before the final `log`:

```bash
    if [ "$VERSION" = "$(app_version)" ]; then
        if ! git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then
            git tag -a "v$VERSION" -m "Release $VERSION"
            # Push to `forgejo` when it exists (local); in CI the only remote is
            # the Forgejo checkout itself. Never the GitHub mirror.
            tag_remote=origin
            git remote | grep -qx forgejo && tag_remote=forgejo
            git push "$tag_remote" "v$VERSION" 2>/dev/null \
                || warn "Could not push tag v$VERSION; push it by hand."
        fi
    fi
```

- [ ] **Step 5: Export the version for build-from-source**

In `deploy_local()`, before `docker compose up`:

```bash
    export OPENFAMHUB_VERSION="$(app_version)"
```

- [ ] **Step 6: Update the usage text**

In `usage()`, replace the `BUILD_NUMBER` sentence with:

```
  REGISTRY, OPENFAMHUB_VERSION, PLATFORMS (publish). The version defaults to
  0.<VERSION> (VERSION in the repo root), bumped by the pre-commit hook.
```

- [ ] **Step 7: Verify resolution and syntax**

Run:

```bash
bash -n scripts/deploy.sh && echo syntax-ok
( set -- --help; source scripts/deploy.sh >/dev/null 2>&1; app_version )
grep -n BUILD_NUMBER scripts/deploy.sh || echo "no-build-number"
```

Expected: `syntax-ok`, then `0.31` (the current `VERSION` plus one-prefix — whatever `VERSION` holds now), then `no-build-number`.

- [ ] **Step 8: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat: drive deploy versions from VERSION, drop the run-number suffix, tag releases"
```

---

### Task 6: Wire the CI pipeline

**Files:**
- Modify: `.gitea/workflows/ci.yml`

**Interfaces:**
- Consumes: `scripts/check-version.sh` (Task 4).
- Produces: a `version` job that publishes/deploys depend on.

- [ ] **Step 1: Remove `BUILD_NUMBER`**

Delete the workflow-level `env.BUILD_NUMBER` line and its comment.

- [ ] **Step 2: Add the `version` job**

Add, before `publish`:

```yaml
  version:
    runs-on: openfamhub
    steps:
      - uses: builtin:checkout
        with:
          fetch-depth: 0
      - name: Enforce the release-number rule
        run: |
          set -euo pipefail
          head=HEAD
          if [ "${{ gitea.ref }}" = "refs/heads/master" ]; then
            mode=master
            # The push payload's `before` is the previous master tip; fall back
            # to the first parent when it is empty or all zeros (new branch).
            base='${{ gitea.event.before }}'
            if [ -z "$base" ] || [ "$base" = "0000000000000000000000000000000000000000" ] \
               || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
              base="${head}^"
            fi
          else
            mode=branch
            base=$(git merge-base HEAD origin/master 2>/dev/null || git rev-parse HEAD^)
          fi
          scripts/check-version.sh "$mode" "$base" "$head"
```

- [ ] **Step 3: Gate publish and deploy on it**

Add `version` to `publish`'s `needs` (`needs: [backend, frontend, version]`) and to `deploy`'s (`needs: [publish, version]`).

- [ ] **Step 4: Verify the YAML parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.gitea/workflows/ci.yml'))" && echo yaml-ok`
Expected: prints `yaml-ok`.

- [ ] **Step 5: Commit**

```bash
git add .gitea/workflows/ci.yml
git commit -m "ci: add the release-number check and gate publish/deploy on it"
```

---

### Task 7: Docs and CHANGELOG

**Files:**
- Modify: `docs/ci.md:23-33` (build-number section, troubleshooting table)
- Modify: `docs/deployment.md:96,163,204,255`
- Modify: `README.md:36` (publish example comment)
- Modify: `CHANGELOG.md:1-7`
- Modify: `AGENTS.md` (CI gotcha line)

**Interfaces:**
- Consumes: everything above; no code.

- [ ] **Step 1: Rewrite the CI version section**

In `docs/ci.md`, replace the "Build numbers" paragraph with a "Version numbering" section stating: `VERSION` (repo root) holds a single integer; the `pre-commit` hook bumps it per commit; `scripts/check-version.sh` enforces `+1` on `master`'s first-parent chain and "greater than base" on branches; the release string is `0.<n>`; tags are `v0.<n>` pushed to `forgejo`. Remove the `0.30.17` example. Update the troubleshooting row that mentions `OPENFAMHUB_VERSION should match APP_VERSION` to say it should match `0.$(cat VERSION)`.

- [ ] **Step 2: Update the deployment docs**

In `docs/deployment.md`:

- Line ~96 comment: `# version = 0.<VERSION> (repo root)`.
- The upgrade snippet at ~163: replace "bump APP_VERSION (and CHANGELOG), commit" with "the hook bumps VERSION; add a CHANGELOG entry, commit".
- The `OPENFAMHUB_VERSION` table row: default is `0.<VERSION from VERSION>`.
- The rollback note at ~255: roll back to a `v0.<n>` tag / `0.<n>` image.

- [ ] **Step 3: Update the README and AGENTS gotcha**

- `README.md:36`: change the inline comment `# build + push v0.30 (amd64 + arm64)` to `# build + push v0.<n> (amd64 + arm64)`.
- `AGENTS.md`: in the CI gotcha, replace any "build number `0.30.<run>`" wording with the per-commit `0.<n>` scheme, and note `scripts/check-version.sh`.

- [ ] **Step 4: Fold the CHANGELOG entry**

Replace the `## [Unreleased] - 0.30.x builds` heading and its Added bullet with:

```markdown
## [0.31] - <today>

### Changed
- Every commit now carries its own version, `0.<n>`, incremented by one per commit by a `pre-commit` hook and enforced in CI. The CI run-number suffix (`0.30.17`) is gone; images are tagged `0.<n>` with a matching `v0.<n>` release tag.
```

- [ ] **Step 5: Verify no stale references remain**

Run: `grep -rn "run_number\|BUILD_NUMBER" .gitea scripts docs README.md AGENTS.md backend frontend/src GETTING_STARTED.md | grep -v '^docs/superpowers/'`
Expected: no output. (The matching lines in `docs/superpowers/specs/` and `docs/superpowers/plans/` *describe the removal* and are expected; that is why they are excluded.)

- [ ] **Step 6: Commit**

```bash
git add docs/ci.md docs/deployment.md README.md AGENTS.md CHANGELOG.md
git commit -m "docs: describe per-commit version numbering"
```

---

## Self-Review

**Spec coverage:** Goal → Tasks 1-2. Hook → Task 1. CI check + first-parent scoping + `needs` gates → Tasks 4, 6. Branches/rebases/merges + `scripts/renumber` → Tasks 3, 4. Propagation (`deploy.sh`, `config.py`, Dockerfile, compose, `/api/health`) → Tasks 2, 5. Tagging to `forgejo`, no-override rule → Task 5. Retiring `run_number`/`BUILD_NUMBER` → Tasks 5, 6, 7. Docs/CHANGELOG → Task 7. Seeding (`VERSION=30`, next commit `0.31`) → Task 1 Step 1-5. Every spec section maps to a task.

**Step scan:** Each step names one action with a checkable result. Code appears only where the value is fixed by the spec or the algorithm is not derivable (the hook, `check-version.sh`, `renumber`); the `config.py` body is given because its fallback ordering is a spec decision. No "handle edge cases"/"TBD" lines.

**Type consistency:** `_resolve_version(build_env, version_path)` is defined once (Task 2) and used only in its test. `scripts/check-version.sh <master|branch> <base> <head>` is defined in Task 4 and called with that exact arity in Task 6. `app_version()` keeps its name and now returns `0.<n>` (Task 5, used by `resolve_version` and `deploy_local`). `scripts/renumber [base] | --step` matches between Task 3 and its test.

**Review Focus:** Empty commit → Task 1 Step 6. Missing/non-numeric `VERSION` → Task 1 Step 2 (hook refuses) and Task 2 Step 1 (`0.0-dev`). Rebase duplicates/backwards → Task 3 Step 2. `--no-verify`/fresh clone → Task 4 Step 1 (`stale-caught`). Merge on `master` → Task 4 Step 1 (`merge-skipped`). All five are pinned to tests.

**Proportion:** The plan is dominated by short verification commands and three small scripts; it carries no implementation bodies for `deploy.sh` beyond the fixed-value edits.
