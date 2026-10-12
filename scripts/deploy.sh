#!/bin/bash
#
# OpenFamHub deployment helper. See docs/deployment.md.
#
#   Build-from-source (this machine runs the app):
#     scripts/deploy.sh setup | deploy | update | status | logs | stop
#
#   Registry (build here, run elsewhere):
#     scripts/deploy.sh publish [version]          build + push multi-arch images
#     scripts/deploy.sh remote <ssh-host> [version] install/upgrade a server over SSH
#
set -euo pipefail

APP_NAME="openfamhub"
DEFAULT_REGISTRY="forgejo.vernonmyers.cloud/vernon"

# Run from the repository root regardless of where the script is called from.
cd "$(dirname "$0")/.."

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()   { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

usage() {
    cat <<EOF
Usage: $0 <command> [args]

Build from source on this machine:
  setup                 Create .env (with a generated SECRET_KEY) and data folders
  deploy                Build images from this checkout and (re)start the stack
  update                git pull --ff-only, then deploy
  status                Show service status
  logs [service]        Follow logs
  stop                  Stop the stack

Registry workflow:
  publish [version]     Build linux/amd64 + linux/arm64 images and push them to
                        \$REGISTRY (default: $DEFAULT_REGISTRY)
  remote <host> [ver]   Install or upgrade OpenFamHub on <host> over SSH using the
                        published images (first run creates ~/openfamhub/.env)
  server [dir] [ver]    Install the deploy bundle into [dir] (default: openfamhub)
                        and pull + restart the stack locally (no SSH)

Environment overrides:
  REGISTRY, OPENFAMHUB_VERSION, PLATFORMS (publish). The version defaults to
  0.<VERSION> (VERSION in the repo root), bumped by the pre-commit hook.
  PUBLIC_URL, REMOTE_DIR (remote; defaults https://openfamhub.local, openfamhub)
EOF
}

# Value of KEY from ./.env, if present.
env_value() {
    [ -f .env ] || return 0
    grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true
}

app_version() {
    [ -f VERSION ] || error "VERSION file not found"
    local n
    n=$(tr -d '[:space:]' < VERSION)
    case "$n" in
        ''|*[!0-9]*) error "VERSION must be a single integer, got '$n'";;
    esac
    printf '0.%s' "$n"
}

resolve_registry() {
    REGISTRY="${REGISTRY:-$(env_value REGISTRY)}"
    REGISTRY="${REGISTRY:-$DEFAULT_REGISTRY}"
}

# Version precedence: explicit argument > $OPENFAMHUB_VERSION > .env > app_version().
resolve_version() {
    VERSION="${1:-${OPENFAMHUB_VERSION:-$(env_value OPENFAMHUB_VERSION)}}"
    if [ -z "$VERSION" ]; then
        VERSION="$(app_version)"
    fi
    [ -n "$VERSION" ] || error "Could not determine the version"
}

require_env() {
    [ -f ".env" ] || error ".env not found. Run '$0 setup' first."
    if grep -q '^SECRET_KEY=REPLACE_WITH_64_CHAR_HEX' .env; then
        error "SECRET_KEY in .env is still the placeholder. Run '$0 setup' or set it by hand."
    fi
}

# Wait for the api container's Docker healthcheck. Runs where `docker compose` runs.
HEALTH_WAIT='
for _ in $(seq 1 45); do
    status=$(docker compose ps api --format "{{.Health}}" 2>/dev/null || true)
    if [ "$status" = "healthy" ]; then echo "API is healthy."; exit 0; fi
    sleep 2
done
docker compose ps
echo "API did not become healthy within 90s. Check: docker compose logs api" >&2
exit 1
'

deploy_local() {
    require_env
    # Resolve the version the same way publish() does, so an explicit
    # OPENFAMHUB_VERSION (or .env) is honoured instead of being clobbered.
    resolve_version
    export OPENFAMHUB_VERSION="$VERSION"
    mkdir -p data/db data/photos data/backups
    # docker-compose.yml builds from this checkout, so --build is what picks up changes.
    log "Building images and starting services..."
    docker compose up -d --build --remove-orphans
    log "Waiting for the API to become healthy..."
    bash -c "$HEALTH_WAIT"
    docker compose ps
    log "Deployment successful!"
}

publish() {
    resolve_registry
    resolve_version "${1:-}"
    local platforms="${PLATFORMS:-linux/amd64,linux/arm64}"
    command -v docker >/dev/null || error "docker is not installed"
    docker buildx version >/dev/null 2>&1 || error "docker buildx is required"

    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        warn "Working tree has uncommitted changes; they will be included in the images."
    fi

    # Multi-platform pushes need a BuildKit container builder.
    if ! docker buildx inspect "$APP_NAME" >/dev/null 2>&1; then
        log "Creating buildx builder '$APP_NAME'..."
        docker buildx create --name "$APP_NAME" --driver docker-container >/dev/null
    fi

    local sha
    sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
    for component in api web; do
        local context=backend
        [ "$component" = web ] && context=frontend
        local image="$REGISTRY/$APP_NAME-$component"
        local tags=(-t "$image:$VERSION" -t "$image:latest")
        log "Building and pushing $image:$VERSION ($platforms)..."
        docker buildx build \
            --builder "$APP_NAME" \
            --platform "$platforms" \
            --label "org.opencontainers.image.revision=$sha" \
            --label "org.opencontainers.image.version=$VERSION" \
            --build-arg "OPENFAMHUB_BUILD=$VERSION" \
            --build-arg "APP_VERSION=$VERSION" \
            --build-arg "OPENFAMHUB_COMMIT=$sha" \
            "${tags[@]}" \
            --push \
            "$context"
    done

    if [ "$VERSION" = "$(app_version)" ]; then
        if ! git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then
            # Use an explicit identity: CI runners often have no user.email/user.name,
            # and `set -e` would otherwise abort the publish after the images are up.
            if git -c user.name="OpenFamHub CI" -c user.email="ci@vernonmyers.cloud" \
                   tag -a "v$VERSION" -m "Release $VERSION"; then
                tag_remote=origin
                if git remote | grep -qx forgejo; then
                    tag_remote=forgejo
                fi
                if ! git push "$tag_remote" "v$VERSION" 2>/dev/null; then
                    warn "Could not push tag v$VERSION; push it by hand."
                fi
            else
                warn "Could not create tag v$VERSION; tag and push it by hand."
            fi
        fi
    fi

    log "Published $REGISTRY/$APP_NAME-{api,web}:$VERSION (and :latest)."
}

remote() {
    local host="${1:-}"
    [ -n "$host" ] || error "Usage: $0 remote <ssh-host> [version]"
    resolve_registry
    resolve_version "${2:-}"
    local dir="${REMOTE_DIR:-openfamhub}"
    local public_url="${PUBLIC_URL:-https://openfamhub.local}"

    log "Checking $host..."
    ssh "$host" 'docker compose version >/dev/null' \
        || error "$host: 'docker compose' not available for the SSH user (install Docker; add the user to the docker group)."

    log "Copying deploy bundle to $host:~/$dir ..."
    ssh "$host" "mkdir -p '$dir/config' '$dir/data/db' '$dir/data/photos' '$dir/data/backups'"
    scp -q deploy/compose.yml "$host:$dir/compose.yml"
    scp -q config/Caddyfile config/Caddyfile.proxy config/routes.caddy "$host:$dir/config/"

    if ssh "$host" "test -f '$dir/.env'"; then
        log "Pinning REGISTRY=$REGISTRY and OPENFAMHUB_VERSION=$VERSION in existing $dir/.env"
        ssh "$host" "REGISTRY='$REGISTRY' VERSION='$VERSION' ENV_FILE='$dir/.env' sh -s" <<'REMOTE_ENV'
set -eu
upsert_env() {
    key="$1"
    value="$2"
    file="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}
upsert_env REGISTRY "$REGISTRY" "$ENV_FILE"
upsert_env OPENFAMHUB_VERSION "$VERSION" "$ENV_FILE"
REMOTE_ENV
    else
        command -v openssl >/dev/null || error "openssl is needed to generate SECRET_KEY"
        local key
        key=$(openssl rand -hex 32)
        sed -e "s|__REGISTRY__|$REGISTRY|" \
            -e "s|__VERSION__|$VERSION|" \
            -e "s|__PUBLIC_URL__|$public_url|" \
            -e "s|__SECRET_KEY__|$key|" \
            deploy/env.template | ssh "$host" "umask 077 && cat > '$dir/.env'"
        log "Created $dir/.env on $host with a generated SECRET_KEY (back it up)."
        log "Review it with: ssh $host \"\${EDITOR:-nano} $dir/.env\""
    fi

    log "Validating compose config on $host..."
    ssh "$host" "cd '$dir' && docker compose config >/dev/null"

    log "Pulling images and starting services on $host..."
    ssh "$host" "cd '$dir' && docker compose pull && docker compose up -d --remove-orphans"
    log "Waiting for the API to become healthy..."
    ssh "$host" "cd '$dir' && bash -s" <<<"$HEALTH_WAIT"
    ssh "$host" "cd '$dir' && docker compose ps"
    log "Deployed $VERSION to $host."
}

server() {
    local dir="${1:-${REMOTE_DIR:-openfamhub}}"
    resolve_registry
    resolve_version "${2:-}"

    log "Installing deploy bundle into $dir ..."
    mkdir -p "$dir/config" "$dir/data/db" "$dir/data/photos" "$dir/data/backups"
    cp deploy/compose.yml "$dir/compose.yml"
    cp config/Caddyfile config/Caddyfile.proxy config/routes.caddy "$dir/config/"

    if [ -f "$dir/.env" ]; then
        log "Pinning REGISTRY=$REGISTRY and OPENFAMHUB_VERSION=$VERSION in $dir/.env"
        REGISTRY="$REGISTRY" VERSION="$VERSION" ENV_FILE="$dir/.env" sh -s <<'LOCAL_ENV'
set -eu
upsert_env() {
    key="$1"
    value="$2"
    file="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file" && rm -f "$file.bak"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}
upsert_env REGISTRY "$REGISTRY" "$ENV_FILE"
upsert_env OPENFAMHUB_VERSION "$VERSION" "$ENV_FILE"
LOCAL_ENV
    else
        command -v openssl >/dev/null || error "openssl is needed to generate SECRET_KEY"
        local key public_url
        key=$(openssl rand -hex 32)
        public_url="${PUBLIC_URL:-https://openfamhub.local}"
        sed -e "s|__REGISTRY__|$REGISTRY|" \
            -e "s|__VERSION__|$VERSION|" \
            -e "s|__PUBLIC_URL__|$public_url|" \
            -e "s|__SECRET_KEY__|$key|" \
            deploy/env.template > "$dir/.env"
        chmod 600 "$dir/.env"
        log "Created $dir/.env with a generated SECRET_KEY (back it up)."
    fi

    log "Validating compose config in $dir..."
    ( cd "$dir" && docker compose config >/dev/null )

    log "Pulling images and starting services in $dir..."
    ( cd "$dir" && docker compose pull && docker compose up -d --remove-orphans )
    log "Waiting for the API to become healthy..."
    ( cd "$dir" && bash -c "$HEALTH_WAIT" )
    ( cd "$dir" && docker compose ps )
    log "Deployed $VERSION to $dir."
}

case "${1:-help}" in
    setup)
        log "Starting setup for $APP_NAME..."
        if [ ! -f ".env" ]; then
            log "Creating .env from .env.example..."
            cp .env.example .env
        else
            log ".env already exists. Skipping creation."
        fi
        if grep -q '^SECRET_KEY=REPLACE_WITH_64_CHAR_HEX' .env; then
            command -v openssl >/dev/null || error "openssl is needed to generate SECRET_KEY"
            key=$(openssl rand -hex 32)
            # Portable in-place edit (GNU and BSD sed differ on -i).
            tmp=$(mktemp)
            sed "s/^SECRET_KEY=REPLACE_WITH_64_CHAR_HEX.*/SECRET_KEY=$key/" .env > "$tmp" && cat "$tmp" > .env && rm -f "$tmp"
            log "Generated SECRET_KEY. Back it up in your password manager."
        fi
        mkdir -p data/db data/photos data/backups
        log "Setup complete. Review .env, then run '$0 deploy'."
        ;;
    deploy)  deploy_local ;;
    update)
        log "Pulling latest code..."
        git pull --ff-only || error "git pull failed (local changes or diverged branch?)"
        deploy_local
        ;;
    publish) publish "${2:-}" ;;
    remote)  remote "${2:-}" "${3:-}" ;;
    server)  server "${2:-}" "${3:-}" ;;
    status)  docker compose ps ;;
    logs)
        if [ -z "${2:-}" ]; then docker compose logs -f; else docker compose logs -f "$2"; fi
        ;;
    stop)
        log "Stopping all services..."
        docker compose down
        log "Services stopped."
        ;;
    help|-h|--help) usage ;;
    *) usage; exit 1 ;;
esac
