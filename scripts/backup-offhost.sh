#!/bin/bash
# Copy OpenFamHub's backups and photos to another machine (a NAS, a USB disk).
#
#   scripts/backup-offhost.sh [--dry-run] [--with-env] <destination> [install-dir]
#
# destination  a local or mounted folder (/mnt/nas/openfamhub) or an rsync/SSH
#              target (backup@nas:/volume1/openfamhub).
# install-dir  the folder holding data/ and .env; default: this checkout, or
#              ~/openfamhub on a server deployed with deploy.sh remote.
#
# Copies data/backups (the API's daily database snapshots; the live database
# isn't copied because it changes while it's being read) and data/photos (the
# family's photos and videos). Nothing is ever deleted at the destination, so
# a photo removed in the app stays in the backup. --with-env also copies .env
# (it holds SECRET_KEY: restoring without it signs everyone out) as "env",
# readable only by its owner.
#
# Run it after the daily backup (BACKUP_TIME, 03:00 by default), e.g. from cron:
#   30 4 * * * cd ~/openfamhub && ./backup-offhost.sh backup@nas:/volume1/openfamhub >> backup-offhost.log 2>&1
set -euo pipefail

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

dry_run=0 with_env=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) dry_run=1 ;;
        --with-env) with_env=1 ;;
        -h|--help) usage ;;
        --) shift; break ;;
        -*) echo "Unknown option: $1" >&2; usage ;;
        *) break ;;
    esac
    shift
done
[ $# -ge 1 ] || usage
dest=${1%/}
if [ $# -ge 2 ]; then
    install=$2
elif [ -d "$(dirname "$0")/../data" ]; then
    install="$(cd "$(dirname "$0")/.." && pwd)"
else
    install="$HOME/openfamhub"
fi
data="$install/data"
if [ ! -d "$data/backups" ] && [ ! -d "$data/photos" ]; then
    echo "No OpenFamHub data in $install (expected $data/backups and $data/photos)." >&2
    exit 1
fi

use_rsync=1
if [ "${OPENFAMHUB_NO_RSYNC:-0}" = 1 ] || ! command -v rsync >/dev/null; then
    use_rsync=0
    case "$dest" in *:*)
        echo "rsync is needed to copy to $dest; install it or use a mounted folder." >&2
        exit 1 ;;
    esac
fi

run() { if [ "$dry_run" = 1 ]; then echo "would run: $*"; else "$@"; fi; }

copy_dir() {  # copy_dir <name>: data/<name>/ -> <dest>/<name>/, never deleting
    local name=$1
    [ -d "$data/$name" ] || return 0
    if [ "$use_rsync" = 1 ]; then
        local flags=(-a --exclude .incoming/)
        [ "$dry_run" = 1 ] && flags+=(--dry-run --itemize-changes)
        case "$dest" in *:*) ;; *) mkdir -p "$dest" 2>/dev/null || [ "$dry_run" = 1 ] ;; esac
        rsync "${flags[@]}" "$data/$name/" "$dest/$name/"
    else
        run mkdir -p "$dest/$name"
        # cp -R merges into the destination without deleting what's already there.
        (cd "$data/$name" && find . -path ./media/.incoming -prune -o -type f -print) | while read -r f; do
            run mkdir -p "$dest/$name/$(dirname "$f")"
            run cp -p "$data/$name/$f" "$dest/$name/$f"
        done
    fi
}

echo "Backing up $data -> $dest$([ "$dry_run" = 1 ] && echo ' (dry run)')"
copy_dir backups
copy_dir photos

if [ "$with_env" = 1 ] && [ -f "$install/.env" ]; then
    if [ "$use_rsync" = 1 ]; then
        flags=(-a --chmod=F600)
        [ "$dry_run" = 1 ] && flags+=(--dry-run)
        rsync "${flags[@]}" "$install/.env" "$dest/env"
    else
        run cp "$install/.env" "$dest/env"
        run chmod 600 "$dest/env"
    fi
fi
echo "Done."
