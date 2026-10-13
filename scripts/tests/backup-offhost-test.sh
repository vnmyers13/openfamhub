#!/bin/bash
# Tests for scripts/backup-offhost.sh. Run: bash scripts/tests/backup-offhost-test.sh
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
script="$repo_root/scripts/backup-offhost.sh"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

make_install() {  # a fake ~/openfamhub with data and .env
    local root=$1
    mkdir -p "$root/data/db" "$root/data/backups" "$root/data/photos/media/fam/abc"
    echo live > "$root/data/db/homehub.db"
    echo snap > "$root/data/backups/homehub_2026-10-12.db"
    echo jpg > "$root/data/photos/media/fam/abc/wall.jpg"
    mkdir -p "$root/data/photos/media/.incoming" && echo half > "$root/data/photos/media/.incoming/x.upload"
    printf 'SECRET_KEY=abc\n' > "$root/.env"
}

for mode in rsync copy; do
    export OPENFAMHUB_NO_RSYNC=$([ "$mode" = copy ] && echo 1 || echo 0)
    inst="$tmp/$mode/install"; dest="$tmp/$mode/nas"
    make_install "$inst"

    # Usage errors exit 2.
    if bash "$script" >/dev/null 2>&1; then echo "$mode: no-args-accepted"; exit 1; fi
    set +e; bash "$script" >/dev/null 2>&1; code=$?; set -e
    [ "$code" = 2 ] || { echo "$mode: usage-exit-$code"; exit 1; }

    # A dry run copies nothing.
    bash "$script" --dry-run "$dest" "$inst" >/dev/null
    [ ! -e "$dest/backups" ] || { echo "$mode: dry-run-copied"; exit 1; }

    # A real run copies snapshots and photos, not the live DB, uploads in progress or .env.
    bash "$script" "$dest" "$inst" >/dev/null
    [ "$(cat "$dest/backups/homehub_2026-10-12.db")" = snap ] || { echo "$mode: snapshot-missing"; exit 1; }
    [ "$(cat "$dest/photos/media/fam/abc/wall.jpg")" = jpg ] || { echo "$mode: photo-missing"; exit 1; }
    [ ! -e "$dest/db" ] || { echo "$mode: live-db-copied"; exit 1; }
    [ ! -e "$dest/photos/media/.incoming/x.upload" ] || { echo "$mode: incoming-copied"; exit 1; }
    [ ! -e "$dest/env" ] && [ ! -e "$dest/.env" ] || { echo "$mode: env-copied-without-flag"; exit 1; }

    # Deleting a photo in the app doesn't delete it from the backup; new ones arrive.
    rm -rf "$inst/data/photos/media/fam/abc"
    mkdir -p "$inst/data/photos/media/fam/def" && echo new > "$inst/data/photos/media/fam/def/wall.jpg"
    bash "$script" "$dest" "$inst" >/dev/null
    [ -e "$dest/photos/media/fam/abc/wall.jpg" ] || { echo "$mode: backup-pruned"; exit 1; }
    [ -e "$dest/photos/media/fam/def/wall.jpg" ] || { echo "$mode: new-photo-missing"; exit 1; }

    # --with-env copies the settings file, readable only by its owner.
    bash "$script" --with-env "$dest" "$inst" >/dev/null
    [ "$(cat "$dest/env")" = "SECRET_KEY=abc" ] || { echo "$mode: env-not-copied"; exit 1; }
    perm=$(stat -c %a "$dest/env" 2>/dev/null || stat -f %Lp "$dest/env")
    [ "$perm" = 600 ] || { echo "$mode: env-mode-$perm"; exit 1; }

    # A data folder that isn't an install is refused.
    if bash "$script" "$dest" "$tmp/nowhere" >/dev/null 2>&1; then echo "$mode: bad-install-accepted"; exit 1; fi
    echo "backup-offhost-$mode-ok"
done
