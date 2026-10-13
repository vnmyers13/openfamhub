#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
workflow="$ROOT/.gitea/workflows/ci.yml"

grep -q '^    outputs:$' "$workflow" || {
  echo "version job should expose the computed release as a job output" >&2
  exit 1
}

grep -q 'release:.*steps.release.outputs.release' "$workflow" || {
  echo "version job output should come from a release step" >&2
  exit 1
}

grep -q 'OPENFAMHUB_VERSION:.*needs.version.outputs.release' "$workflow" || {
  echo "publish/deploy jobs should pin OPENFAMHUB_VERSION to the version job output" >&2
  exit 1
}

grep -q 'scripts/deploy.sh server "$HOME/openfamhub" "\${{ needs.version.outputs.release }}"' "$workflow" || {
  echo "deploy job should pass the just-published release explicitly to deploy.sh server" >&2
  exit 1
}

trivy_block=$(awk '/^  trivy:/{flag=1} flag{print} /^  issues:/{flag=0}' "$workflow")

printf '%s\n' "$trivy_block" | grep -q '^    needs: \[publish, version\]$' || {
  echo "trivy job should directly need version before using needs.version.outputs.release" >&2
  exit 1
}

printf '%s\n' "$trivy_block" | grep -q 'scripts/trivy-scan.sh "\${{ needs.version.outputs.release }}"' || {
  echo "trivy scan should use the exact release from the version job" >&2
  exit 1
}

printf '%s\n' "$trivy_block" | grep -q 'openfamhub-$component:\${{ needs.version.outputs.release }}' || {
  echo "trivy issue labels should use the exact release from the version job" >&2
  exit 1
}

echo "CI pins publish/deploy to the release computed by the version job"
