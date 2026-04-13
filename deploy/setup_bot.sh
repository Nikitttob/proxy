#!/bin/bash
# Установка бота и менеджера на уже настроенном VPS.
# Ожидает, что репозиторий клонирован в /opt/xray-proxy.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/xray-proxy}"
ENV_DIR="/etc/xray-proxy"
ENV_FILE="$ENV_DIR/env"

echo "[1/5] Зависимости…"
apt-get update
apt-get install -y python3 python3-pip
pip3 install --break-system-packages -r "$REPO_DIR/requirements.txt"

echo "[2/5] .env…"
install -d -m 750 "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
    cp "$REPO_DIR/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "⚠️  Отредактируй $ENV_FILE перед запуском бота."
fi

echo "[3/5] users.json…"
install -d -m 755 /usr/local/etc/xray
if [[ ! -f /usr/local/etc/xray/users.json ]]; then
    echo "{}" > /usr/local/etc/xray/users.json
    chmod 600 /usr/local/etc/xray/users.json
fi

echo "[4/5] systemd-юниты…"
install -m 644 "$REPO_DIR/deploy/xray-bot.service"      /etc/systemd/system/
install -m 644 "$REPO_DIR/deploy/vultr-monitor.service" /etc/systemd/system/
systemctl daemon-reload

echo "[5/5] Cron: ежедневный бэкап users.json…"
install -m 755 "$REPO_DIR/scripts/backup_users.sh" /usr/local/bin/backup_users.sh
cat > /etc/cron.d/xray-proxy-backup <<'CRON'
# Daily backup of users.json at 03:30
30 3 * * * root /usr/local/bin/backup_users.sh >> /var/log/xray-proxy-backup.log 2>&1
CRON

echo
echo "Готово. Далее:"
echo "  1. Заполни $ENV_FILE"
echo "  2. systemctl enable --now xray-bot"
echo "  3. (опц.) systemctl enable --now vultr-monitor"
