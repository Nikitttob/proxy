#!/bin/bash
# Ежедневный бэкап users.json. Ротация — 14 дней.
set -euo pipefail

SRC="${USERS_DB:-/usr/local/etc/xray/users.json}"
DEST="/var/backups/xray-proxy"
STAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$DEST"
if [[ -f "$SRC" ]]; then
    tar -czf "$DEST/users-$STAMP.tar.gz" -C "$(dirname "$SRC")" "$(basename "$SRC")"
    find "$DEST" -name 'users-*.tar.gz' -mtime +14 -delete
    echo "[$(date -Iseconds)] backup ok: users-$STAMP.tar.gz"
else
    echo "[$(date -Iseconds)] skip: $SRC not found"
fi
