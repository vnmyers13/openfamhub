#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TMP=${TMPDIR:-/tmp}/openfamhub-deploy-version-test-$$
trap 'rm -rf "$TMP"' EXIT

REPO="$TMP/repo"
mkdir -p "$REPO/scripts" "$TMP/bin"
cp "$ROOT/scripts/deploy.sh" "$REPO/scripts/deploy.sh"
cp "$ROOT/scripts/release-name" "$REPO/scripts/release-name"
cp "$ROOT/docker-compose.yml" "$REPO/docker-compose.yml"
cp "$ROOT/VERSION" "$REPO/VERSION"
chmod +x "$REPO/scripts/deploy.sh"

cat > "$REPO/.env" <<'ENV'
SECRET_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
OPENFAMHUB_VERSION=latest
ENV

git -C "$REPO" init -q
git -C "$REPO" add .
git -C "$REPO" -c user.name='Test' -c user.email='test@example.invalid' commit -q -m init

expected_version="$("$ROOT/scripts/release-name" "$(tr -d '[:space:]' < "$REPO/VERSION")")"
expected_commit=$(git -C "$REPO" rev-parse --short HEAD)
capture="$TMP/docker-env"

cat > "$TMP/bin/docker" <<'SH'
#!/bin/sh
set -eu
if [ "${1:-}" = "compose" ] && [ "${2:-}" = "up" ]; then
  {
    echo "OPENFAMHUB_VERSION=${OPENFAMHUB_VERSION:-}"
    echo "OPENFAMHUB_COMMIT=${OPENFAMHUB_COMMIT:-}"
  } > "$DOCKER_CAPTURE"
  exit 0
fi
if [ "${1:-}" = "compose" ] && [ "${2:-}" = "ps" ]; then
  if [ "${3:-}" = "api" ]; then
    echo healthy
  else
    echo 'api healthy'
  fi
  exit 0
fi
echo "unexpected docker invocation: $*" >&2
exit 1
SH
chmod +x "$TMP/bin/docker"

PATH="$TMP/bin:$PATH" DOCKER_CAPTURE="$capture" "$REPO/scripts/deploy.sh" deploy >/dev/null

grep -qx "OPENFAMHUB_VERSION=$expected_version" "$capture" || {
  echo "expected OPENFAMHUB_VERSION=$expected_version in compose environment" >&2
  cat "$capture" >&2
  exit 1
}

grep -qx "OPENFAMHUB_COMMIT=$expected_commit" "$capture" || {
  echo "expected OPENFAMHUB_COMMIT=$expected_commit in compose environment" >&2
  cat "$capture" >&2
  exit 1
}

echo "deploy stamps $expected_version ($expected_commit)"
