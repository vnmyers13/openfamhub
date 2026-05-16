#!/bin/bash

# OpenFamHub Deployment Script
# This script automte the deployment of OpenFamHub using Docker Compose.

set -e

APP_NAME="openfamhub"
DEPLOY_DIR=$(pwd)

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
    echo "  setup     Initial setup (environment, volumes, etc.)"
    echo "  deploy    Deploy/Update the application"
    echo "  status    Check the status of services"
    echo "  logs      View service logs"
    echo "  stop      Stop all services"
    echo "  help      Display this help message"
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
        log "Ensuring data directories exist..."
        mkdir -p backend/data/db docs/releases scripts/
        log "Setup complete. Please review your .env file before running 'deploy'."
        ;;

    deploy)
        log "Starting deployment for $APP_NAME..."
        # 1. Pull latest images (if using a registry)
        log "Pulling latest Docker images..."
        docker compose pull

        # 2. Run docker-compose up
        log "Launching services..."
        docker compose up -d

        # 3. Verify health
        log "Verifying service status..."
        sleep 5
        docker compose ps

        log "Deployment successful!"
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
