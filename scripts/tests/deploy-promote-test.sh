#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TMP=${TMPDIR:-/tmp}/openfamhub-deploy-promote-test-$$
trap 'rm -rf "$TMP"' EXIT

REPO="$TMP/repo"
mkdir -p "$REPO/scripts" "$REPO/deploy" "$REPO/config" "$TMP/bin"
cp "$ROOT/scripts/deploy.sh" "$REPO/scripts/deploy.sh"
cp "$ROOT/scripts/release-name" "$REPO/scripts/release-name"
cp "$ROOT/deploy/compose.yml" "$REPO/deploy/compose.yml"
cp "$ROOT/deploy/env.template" "$REPO/deploy/env.template"
cp "$ROOT/config/Caddyfile" "$ROOT/config/Caddyfile.proxy" "$ROOT/config/routes.caddy" "$REPO/config/"
cp "$ROOT/scripts/backup-offhost.sh" "$REPO/scripts/backup-offhost.sh"
cp "$ROOT/VERSION" "$REPO/VERSION"
chmod +x "$REPO/scripts/deploy.sh"

touch "$TMP/ssh-log" "$TMP/scp-log"

cat > "$TMP/bin/ssh" <<'SH'
#!/bin/sh
set -eu
host="$1"
shift
printf 'ssh %s %s\n' "$host" "$*" >> "$SSH_LOG"

case "$*" in
  *'docker compose version'*) exit 0 ;;
  *"mkdir -p"*) exit 0 ;;
  *"test -f 'openfamhub/.env'"*) exit 0 ;;
  *"REGISTRY="*)
    input=$(cat)
    printf '%s\n' "$input" >> "$SSH_LOG"
    printf '%s\n' "$input" | grep -q 'upsert_env OPENFAMHUB_VERSION "$VERSION" "$ENV_FILE"'
    exit 0
    ;;
  *"docker compose config"*) exit 0 ;;
  *"docker compose pull"*) exit 0 ;;
  *"bash -s"*) cat >/dev/null; exit 0 ;;
  *"docker compose ps"*) exit 0 ;;
esac

echo "unexpected ssh invocation: $host $*" >&2
exit 1
SH
chmod +x "$TMP/bin/ssh"

cat > "$TMP/bin/scp" <<'SH'
#!/bin/sh
set -eu
printf 'scp %s\n' "$*" >> "$SCP_LOG"
exit 0
SH
chmod +x "$TMP/bin/scp"

PATH="$TMP/bin:$PATH" SSH_LOG="$TMP/ssh-log" SCP_LOG="$TMP/scp-log" \
  PUBLIC_URL=https://family.example "$REPO/scripts/deploy.sh" promote prod-host 1.01 >/dev/null

grep -q "ssh prod-host .*docker compose version" "$TMP/ssh-log"
grep -q "VERSION='1.01'" "$TMP/ssh-log"
grep -q "upsert_env OPENFAMHUB_VERSION" "$TMP/ssh-log"
grep -q "scp .*deploy/compose.yml prod-host:openfamhub/compose.yml" "$TMP/scp-log"

if PATH="$TMP/bin:$PATH" "$REPO/scripts/deploy.sh" promote prod-host >/tmp/promote-missing-version.out 2>&1; then
  echo "promote without an explicit checked build should fail" >&2
  exit 1
fi
grep -q "Usage: .* promote <prod-host> <checked-build>" /tmp/promote-missing-version.out

if PATH="$TMP/bin:$PATH" "$REPO/scripts/deploy.sh" promote prod-host latest >/tmp/promote-latest.out 2>&1; then
  echo "promote should reject latest; production must name a checked build" >&2
  exit 1
fi
grep -q "checked build must be a specific published tag, not latest" /tmp/promote-latest.out

if PATH="$TMP/bin:$PATH" "$REPO/scripts/deploy.sh" promote prod-host "1.01'bad" >/tmp/promote-unsafe.out 2>&1; then
  echo "promote should reject unsafe build tags" >&2
  exit 1
fi
grep -q "checked build contains unsupported characters" /tmp/promote-unsafe.out

echo "promote requires an explicit checked build and deploys it to the production host"
