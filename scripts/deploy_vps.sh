#!/bin/sh
set -eu

STAGING=/root/jobmonitor-staging
TARGET=/opt/jobmonitor
ARCHIVE="$STAGING/jobmonitor-deploy.tar.gz"
ENV_FILE="$STAGING/.env"
DATABASE="$STAGING/jobmonitor.db"

log() {
    printf '%s\n' "[jobmonitor-prepare] $1"
}

require_file() {
    if [ ! -f "$1" ]; then
        printf '%s\n' "Required staging file is missing: $1" >&2
        exit 1
    fi
}

log "Validating staging files"
require_file "$ARCHIVE"
require_file "$ENV_FILE"
require_file "$DATABASE"

if [ -e "$TARGET" ]; then
    printf '%s\n' "Deployment target already exists: $TARGET" >&2
    exit 1
fi

log "Creating production directories"
install -d -m 755 "$TARGET"
install -d -m 700 "$TARGET/data" "$TARGET/logs"

log "Extracting application code"
tar -xzf "$ARCHIVE" -C "$TARGET"

log "Installing protected configuration and database"
install -m 600 "$ENV_FILE" "$TARGET/.env"
install -m 600 "$DATABASE" "$TARGET/data/jobmonitor.db"

log "Applying runtime ownership and permissions"
chown -R 10001:10001 "$TARGET/data" "$TARGET/logs"
chmod 700 "$TARGET/data" "$TARGET/logs"

log "File preparation complete; no image was built and no container was started"
