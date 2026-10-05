#!/bin/bash

# OpenFamHub Deployment Script
# This script automates the deployment of OpenFamHub using Docker Compose.

set -e

APP_NAME="openfamhub"
# Run from the repository root regardless of where the script is called from.
cd "$(dirname "$0")/.."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup     Initial setup (.env with a generated SECRET_KEY, data folders)"
    echo "  deploy    Rebuild images from this checkout and (re)start the services"
    echo "  update    git pull (fast-forward only), then deploy"
    echo "  status    Check the status of services"
    echo "  logs      View service logs (optionally: logs <service>)"
    echo "  stop      Stop all services"
    echo "  help      Display this help message"
}

require_env() {
    [ -f ".env" ] || error ".env not found. Run '$0 setup' first."
    if grep -q '^SECRET_KEY=REPLACE_WITH_64_CHAR_HEX' .env; then
        error "SECRET_KEY in .env is still the placeholder. Run '$0 setup' or set it by hand."
    fi
}

wait_for_health() {
    log "Waiting for the API to become healthy..."
    for _ in $(seq 1 30); do
        if docker compose exec -T api python -c \
            "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=2).status == 200 else 1)" \
            >/dev/null 2>&1; then
            log "API is healthy."
            return 0
        fi
        sleep 2
    done
    docker compose ps
    error "API did not become healthy within 60s. Check: $0 logs api"
}

deploy() {
    require_env
    mkdir -p data/db data/photos data/backups
    # Images are built from this checkout (docker-compose.yml uses build:),
    # so --build is what actually picks up code changes.
    log "Building images and starting services..."
    docker compose up -d --build --remove-orphans
    wait_for_health
    docker compose ps
    log "Deployment successful!"
}

case "$1" in
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
        log "Ensuring data directories exist..."
        mkdir -p data/db data/photos data/backups
        log "Setup complete. Review .env, then run '$0 deploy'."
        ;;

    deploy)
        deploy
        ;;

    update)
        log "Pulling latest code..."
        git pull --ff-only || error "git pull failed (local changes or diverged branch?)"
        deploy
        ;;

    status)
        log "Checking service status..."
        docker compose ps
        ;;

    logs)
        if [ -z "$2" ]; then
            docker compose logs -f
        else
            docker compose logs -f "$2"
        fi
        ;;

    stop)
        log "Stopping all services..."
        docker compose down
        log "Services stopped."
        ;;

    help|*)
        usage
        ;;
esac
