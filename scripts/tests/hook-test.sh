#!/bin/bash
# Tests for .githooks/pre-commit. Run: bash scripts/tests/hook-test.sh
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cd "$tmp"
git init -q
git config user.email t@t
git config user.name t
git config core.hooksPath .githooks
mkdir -p .githooks
cp "$repo_root/.githooks/pre-commit" .githooks/pre-commit
mkdir -p scripts; cp "$repo_root/scripts/release-name" scripts/release-name
chmod +x .githooks/pre-commit

printf '# test\n\n![Version](https://img.shields.io/badge/version-0.30-blue)\n' > README.md
printf '30\n' > VERSION
git add -A; git commit -qm base --no-verify

# An empty commit still bumps VERSION by exactly one and keeps the badge honest.
git commit -q --allow-empty -m bump
[ "$(git show HEAD:VERSION | tr -d '[:space:]')" = "31" ] \
    || { echo "hook-NOT-bumped"; exit 1; }
grep -q 'version-0.31-blue' README.md \
    || { echo "hook-badge-NOT-updated"; exit 1; }
echo "hook-ok"

# Past 0.99 the badge reads 1, then 1.01.
printf '99\n' > VERSION; git add VERSION; git commit -qm at99 --no-verify
git commit -q --allow-empty -m to100
grep -q 'version-1-blue' README.md || { echo "badge-1-NOT-set: $(grep -o 'version-[^)]*' README.md)"; exit 1; }
git commit -q --allow-empty -m to101
grep -q 'version-1.01-blue' README.md || { echo "badge-1.01-NOT-set: $(grep -o 'version-[^)]*' README.md)"; exit 1; }
echo "badge-past-99-ok"

# A non-numeric VERSION refuses the commit and leaves VERSION alone.
git reset -q --hard HEAD
printf 'thirty\n' > VERSION; git add VERSION
if git commit -q --allow-empty -m bad >/dev/null 2>&1; then
    echo "nonnumeric-NOT-detected"; exit 1
fi
[ "$(cat VERSION)" = "thirty" ] \
    || { echo "nonnumeric-NOT-detected (VERSION changed)"; exit 1; }
echo "nonnumeric-caught"

# A missing VERSION refuses the commit and does not create one.
git reset -q --hard HEAD
git rm -q VERSION
if git commit -q --allow-empty -m missing >/dev/null 2>&1; then
    echo "missing-NOT-detected"; exit 1
fi
[ ! -e VERSION ] \
    || { echo "missing-NOT-detected (VERSION created)"; exit 1; }
echo "missing-caught"
