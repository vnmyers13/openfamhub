#!/bin/bash
# Every script with a #! line under scripts/ and .githooks/ must be committed as
# executable (100755). CI runs scripts/deploy.sh directly; build 1 failed to
# publish because an edit dropped its executable bit. Run: bash scripts/tests/exec-bits-test.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
bad=0
while IFS= read -r f; do
    [ -f "$f" ] && head -c2 "$f" | grep -q '^#!' || continue
    mode=$(git ls-files -s -- "$f" | cut -c1-6)
    if [ "$mode" != 100755 ]; then
        echo "not executable in git ($mode): $f  -> git update-index --chmod=+x $f"
        bad=1
    fi
done < <(git ls-files scripts .githooks)
[ "$bad" = 0 ] && echo "exec-bits-ok"
exit "$bad"
