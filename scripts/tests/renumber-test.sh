#!/bin/bash
# Tests for scripts/renumber. Run: bash scripts/tests/renumber-test.sh
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d); tmp2=$(mktemp -d); trap 'rm -rf "$tmp" "$tmp2"' EXIT

# A throwaway repo with the version hook enabled, exactly as a developer checkout
# has it (`core.hooksPath .githooks`). The scripts are copied from the working
# tree so the test exercises what is about to be committed.
setup_repo() {
    cd "$1"
    git init -q
    git config user.email t@t
    git config user.name t
    git config core.hooksPath .githooks
    mkdir -p .githooks scripts
    cp "$repo_root/.githooks/pre-commit" .githooks/pre-commit
    cp "$repo_root/scripts/renumber" scripts/renumber
    cp "$repo_root/scripts/release-name" scripts/release-name
    cp "$repo_root/scripts/check-version.sh" scripts/check-version.sh
    chmod +x .githooks/pre-commit scripts/renumber scripts/check-version.sh
}

chain_versions() {
    git rev-list --reverse "$1..HEAD" | while read -r c; do
        git show "$c:VERSION" 2>/dev/null | tr -d '[:space:]'
        echo
    done
}

# renumber restores base+1, base+2, ... after a rebase and the guard accepts it.
# Regression: --step amended with the pre-commit hook still active, so the hook
# bumped each commit a second time (parent+2) and the rebase even hit a VERSION
# conflict. This test must fail before that fix.
setup_repo "$tmp"
printf '30\n' > VERSION; echo base > base.txt; git add -A; git commit -qm base --no-verify
git branch -m master
base=$(git rev-parse HEAD)
git checkout -q -b work
for i in 1 2 3; do echo "c$i" > "c$i.txt"; git add "c$i.txt"; git commit -qm "c$i"; done

scripts/renumber "$base" >/dev/null 2>&1 || { echo "renumber-NOT-restored (rebase failed)"; exit 1; }
want=$'31\n32\n33'
got=$(chain_versions "$base")
[ "$got" = "$want" ] || { echo "renumber-NOT-restored (got: $(echo "$got" | tr '\n' ' '))"; exit 1; }
scripts/check-version.sh master "$base" HEAD >/dev/null 2>&1 \
    || { echo "renumber-NOT-restored (guard failed)"; exit 1; }
echo "renumber-ok"

# renumber --step rejects a non-numeric parent VERSION instead of silently
# treating it as 0 through bash arithmetic.
setup_repo "$tmp2"
printf 'thirty\n' > VERSION; echo base > base.txt; git add -A; git commit -qm base --no-verify
echo child > child.txt; git add child.txt; git commit -qm child --no-verify
if scripts/renumber --step >/dev/null 2>&1; then
    echo "nonnumeric-NOT-detected"; exit 1
fi
[ "$(tr -d '[:space:]' < VERSION)" = "thirty" ] \
    || { echo "nonnumeric-NOT-detected (VERSION rewritten)"; exit 1; }
echo "nonnumeric-caught"
