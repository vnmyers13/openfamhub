#!/bin/bash
# Tests for scripts/check-version.sh. Run: bash scripts/tests/check-version-test.sh
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
check="$repo_root/scripts/check-version.sh"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cd "$tmp"; git init -q; git config user.email t@t; git config user.name t
printf '30\n' > VERSION; git add VERSION; git commit -qm init; git branch -m master
init=$(git rev-parse HEAD)

# A clean +1 chain on master passes.
printf '31\n' > VERSION; git add VERSION; git commit -qm ok; good=$(git rev-parse HEAD)
printf '32\n' > VERSION; git add VERSION; git commit -qm ok2; good2=$(git rev-parse HEAD)
"$check" master "$init" "$good2" && echo "master-ok"

# Branch mode: strictly increasing passes.
git checkout -q -b feat "$good"
printf '40\n' > VERSION; git add VERSION; git commit -qm b1
"$check" branch "$init" HEAD && echo "branch-ok"

# Branch mode: a --no-verify commit that did not bump is caught.
git commit -q --allow-empty --no-verify -m stale
"$check" branch "$init" HEAD 2>/dev/null && { echo "stale-NOT-detected"; exit 1; } || echo "stale-caught"

# Branch mode: a backwards number is caught.
printf '39\n' > VERSION; git add VERSION; git commit -qm back
"$check" branch "$init" HEAD 2>/dev/null && { echo "back-NOT-detected"; exit 1; } || echo "back-caught"

# Master mode: a +2 jump is caught.
git checkout -q master
printf '34\n' > VERSION; git add VERSION; git commit -qm jump
"$check" master "$init" HEAD 2>/dev/null && { echo "jump-NOT-detected"; exit 1; } || echo "jump-caught"

# A merge commit on master is skipped; the next commit continues the chain.
git reset -q --hard "$good2"
git checkout -q -b side "$good2"; echo side > side.txt; git add side.txt; git commit -qm side
git checkout -q master
git merge -q --no-ff -m merge side
printf '33\n' > VERSION; git add VERSION; git commit -qm after-merge
"$check" master "$init" HEAD && echo "merge-skipped"