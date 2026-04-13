#!/bin/bash
# Ежедневный бэкап users.json + .env (секреты).
# Без .env при гибели VPS теряются ВСЕ ключи (Reality, BOT_TOKEN,
# VULTR_API_KEY, CLOUDFLARE_API_TOKEN). Ротация — 14 дней.
#
# Архив создаётся с правами 600 — содержит секреты.
set -euo pipefail

USERS_DB="${USERS_DB:-/usr/local/etc/xray/users.json}"
ENV_FILE="${XRAY_PROXY_ENV:-/etc/xray-proxy/env}"
DEST="${BACKUP_DIR:-/var/backups/xray-proxy}"
STAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$DEST/xray-proxy-$STAMP.tar.gz"

mkdir -p "$DEST"
chmod 700 "$DEST"

FILES=()
[[ -f "$USERS_DB" ]] && FILES+=("$USERS_DB")
[[ -f "$ENV_FILE" ]] && FILES+=("$ENV_FILE")

if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "[$(date -Iseconds)] skip: ничего не найдено для бэкапа"
    exit 0
fi

# tar с абсолютными путями (--absolute-names), чтобы при восстановлении
# сразу легло куда нужно. Архив сразу с узким umask.
umask 077
tar -czf "$ARCHIVE" --absolute-names "${FILES[@]}"
chmod 600 "$ARCHIVE"

find "$DEST" -name 'xray-proxy-*.tar.gz' -mtime +14 -delete
echo "[$(date -Iseconds)] backup ok: $(basename "$ARCHIVE") (${#FILES[@]} файлов)"
