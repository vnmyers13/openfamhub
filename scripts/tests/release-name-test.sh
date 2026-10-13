#!/bin/bash
# Tests for scripts/release-name. Run: bash scripts/tests/release-name-test.sh
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
rn="$repo_root/scripts/release-name"
check() { got=$("$rn" "$1"); [ "$got" = "$2" ] || { echo "FAIL: $1 -> $got (want $2)"; exit 1; }; }
check 0 0.0; check 5 0.5; check 99 0.99; check 100 1; check 101 1.01; check 109 1.09
check 110 1.10; check 199 1.99; check 200 2; check 201 2.01; check 1234 12.34; check 0101 1.01
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
printf '102\n' > "$tmp/VERSION"; [ "$(cd "$tmp" && "$rn")" = "1.02" ] || { echo "FAIL: VERSION file"; exit 1; }
"$rn" abc 2>/dev/null && { echo "FAIL: non-numeric accepted"; exit 1; }
(cd "$tmp" && rm VERSION && "$rn" 2>/dev/null) && { echo "FAIL: missing VERSION accepted"; exit 1; }
echo "release-name-ok"
