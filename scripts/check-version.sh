#!/bin/bash
# Enforce the release-number rule (see the design spec). Usage: check-version.sh <master|branch> <base> <head>
set -euo pipefail

mode="${1:?usage: check-version.sh <master|branch> <base> <head>}"
base="${2:?}"; head="${3:?}"

version_at() { git show "$1:VERSION" 2>/dev/null | tr -d '[:space:]'; }

fail() { echo "check-version: $1" >&2; exit 1; }

if [ "$mode" = "master" ]; then
    revs=$(git rev-list --first-parent --reverse "$base..$head")
else
    revs=$(git rev-list --reverse "$base..$head")
fi

for c in $revs; do
    parents=$(git rev-list --parents -n1 "$c" | wc -w)
    [ "$parents" -gt 2 ] && continue            # merge commit: no number
    parent=$(git rev-parse "$c^" 2>/dev/null || true)
    [ -n "$parent" ] || continue                # initial commit
    pv=$(version_at "$parent")
    [ -n "$pv" ] || continue                    # parent predates adoption
    cv=$(version_at "$c")
    case "$cv" in ''|*[!0-9]*) fail "$c has no usable VERSION ('$cv')";; esac
    if [ "$mode" = "master" ]; then
        [ "$cv" -eq "$((pv + 1))" ] || fail "$c VERSION=$cv but parent $pv (expected $((pv + 1)))"
    else
        [ "$cv" -gt "$pv" ] || fail "$c VERSION=$cv does not exceed its parent $pv"
    fi
done
echo "check-version: ok ($mode, $base..$head)"
