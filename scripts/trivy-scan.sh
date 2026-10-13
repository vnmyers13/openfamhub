#!/bin/bash
# Scan the published images for this commit with Trivy (run from the repo root).
#   scripts/trivy-scan.sh [version] [out_dir]
# version defaults to the release name of VERSION (scripts/release-name), the tag
# `deploy.sh publish` pushes; out_dir
# defaults to trivy-reports. Writes trivy-<component>.json per image and prints a
# HIGH/CRITICAL table to the log. Never fails on findings, only on scan errors.
# Env: REGISTRY (default forgejo.vernonmyers.cloud/vernon), TRIVY_IMAGE (pinned
# below), TRIVY_USERNAME/TRIVY_PASSWORD for the registry, TRIVY_CACHE (host dir).
set -euo pipefail
version="${1:-$("$(dirname "$0")/release-name")}"
out="${2:-trivy-reports}"
registry="${REGISTRY:-forgejo.vernonmyers.cloud/vernon}"
# Pinned: Trivy 0.69.4 and trivy-action <= 0.34.2 were compromised (CVE-2026-33634).
trivy_image="${TRIVY_IMAGE:-aquasec/trivy:0.69.3}"
cache="${TRIVY_CACHE:-$HOME/.cache/trivy}"
mkdir -p "$out" "$cache"
out_abs=$(cd "$out" && pwd)

trivy() {
    docker run --rm --user "$(id -u):$(id -g)" \
        -e TRIVY_USERNAME -e TRIVY_PASSWORD -e TRIVY_CACHE_DIR=/cache \
        -v "$cache:/cache" -v "$out_abs:/out" \
        "$trivy_image" "$@"
}

status=0
for component in api web; do
    ref="$registry/openfamhub-$component:$version"
    echo "== Trivy: $ref"
    if trivy image --scanners vuln --exit-code 0 --format json \
        --output "/out/trivy-$component.json" "$ref"; then
        trivy convert --format table --severity HIGH,CRITICAL \
            "/out/trivy-$component.json" || true
    else
        echo "Trivy could not scan $ref" >&2
        rm -f "$out_abs/trivy-$component.json"
        status=1
    fi
done
exit "$status"
