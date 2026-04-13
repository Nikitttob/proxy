# Прокси-сервер — полная документация

> Последнее обновление: апрель 2026  
> Владелец: Никита

---

## 1. Инфраструктура

| Параметр | Значение |
|----------|----------|
| Хостинг | Vultr |
| Регион | Варшава (waw) |
| План | vc2-1c-1gb (~$6/мес) |
| ОС | Ubuntu 24.04 |
| IP | 70.34.243.161 |
| Домен | 5px7.com |
| DNS-запись | proxy.5px7.com → A → 70.34.243.161 (Cloudflare Proxy: ON) |
| SSL/TLS | Flexible |
| Стоимость | ~$77/год (VPS $72 + домен $5.30) |

---

## 2. Ключи сервера (СЕКРЕТНЫЕ — НЕ ПЕРЕДАВАТЬ)

| Ключ | Значение |
|------|----------|
| Private Key | `YO-lwSb-54h51GUCazD1HnQZNa3f1Wqm8byH4zzgikw` |
| Public Key | `BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU` |
| SNI (маскировка) | `www.samsung.com` |
| Short ID | `0123456789abcdef` |
| Fingerprint | `chrome` |

---

## 3. Пользователи (UUID)

| # | Имя | UUID |
|---|-----|------|
| 1 | Никита | `4fd1690d-5785-4c71-9533-2802732a3cbf` |
| 2 | User2 | `2bfe69be-b66a-4fd5-966b-ef7088e506df` |
| 3 | User3 | `0ca420f4-8490-44be-a377-2d0cdb651ab2` |

> Всего в конфиге настроено 10 UUID. Полный список — в `users.json` на сервере.

---

## 4. Архитектура: два режима подключения

### Home (Reality + TCP) — для дома и мобильного интернета
- Протокол: VLESS + Reality
- Порт: 443
- Транспорт: TCP
- Flow: xtls-rprx-vision
- Подключение: напрямую к IP сервера
- Скорость: максимальная (без промежуточных серверов)

### CDN (WebSocket + TLS) — для офиса и корпоративных сетей
- Протокол: VLESS
- Порт: 80 (локально) → 443 через Cloudflare
- Транспорт: WebSocket (path: `/stream`)
- Подключение: через Cloudflare CDN (proxy.5px7.com)
- Преимущество: работает даже когда IP сервера заблокирован

---

## 5. Конфиг Xray (на сервере)

Путь: `/usr/local/etc/xray/config.json`

```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "4fd1690d-5785-4c71-9533-2802732a3cbf",
            "flow": "xtls-rprx-vision"
          },
          {
            "id": "2bfe69be-b66a-4fd5-966b-ef7088e506df",
            "flow": "xtls-rprx-vision"
          },
          {
            "id": "0ca420f4-8490-44be-a377-2d0cdb651ab2",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.samsung.com:443",
          "xver": 0,
          "serverNames": ["www.samsung.com"],
          "privateKey": "YO-lwSb-54h51GUCazD1HnQZNa3f1Wqm8byH4zzgikw",
          "shortIds": ["", "0123456789abcdef"]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "listen": "0.0.0.0",
      "port": 80,
      "protocol": "vless",
      "settings": {
        "clients": [
          {"id": "4fd1690d-5785-4c71-9533-2802732a3cbf"},
          {"id": "2bfe69be-b66a-4fd5-966b-ef7088e506df"},
          {"id": "0ca420f4-8490-44be-a377-2d0cdb651ab2"}
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": {"path": "/stream"}
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    {"protocol": "freedom", "tag": "direct"},
    {"protocol": "blackhole", "tag": "block"}
  ]
}
```

---

## 6. Ссылки подключения

### User 1 (Никита)

**Home (Reality):**
```
vless://4fd1690d-5785-4c71-9533-2802732a3cbf@70.34.243.161:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.samsung.com&fp=chrome&pbk=BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU&sid=0123456789abcdef&type=tcp#nikita-home
```

**CDN (офис):**
```
vless://4fd1690d-5785-4c71-9533-2802732a3cbf@proxy.5px7.com:443?encryption=none&security=tls&type=ws&path=%2Fstream&host=proxy.5px7.com#nikita-cdn
```

### User 2

**Home:**
```
vless://2bfe69be-b66a-4fd5-966b-ef7088e506df@70.34.243.161:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.samsung.com&fp=chrome&pbk=BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU&sid=0123456789abcdef&type=tcp#user2-home
```

**CDN:**
```
vless://2bfe69be-b66a-4fd5-966b-ef7088e506df@proxy.5px7.com:443?encryption=none&security=tls&type=ws&path=%2Fstream&host=proxy.5px7.com#user2-cdn
```

### User 3

**Home:**
```
vless://0ca420f4-8490-44be-a377-2d0cdb651ab2@70.34.243.161:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.samsung.com&fp=chrome&pbk=BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU&sid=0123456789abcdef&type=tcp#user3-home
```

**CDN:**
```
vless://0ca420f4-8490-44be-a377-2d0cdb651ab2@proxy.5px7.com:443?encryption=none&security=tls&type=ws&path=%2Fstream&host=proxy.5px7.com#user3-cdn
```

### Шаблон для новых пользователей

**Home:**
```
vless://{UUID}@70.34.243.161:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.samsung.com&fp=chrome&pbk=BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU&sid=0123456789abcdef&type=tcp#{name}-home
```

**CDN:**
```
vless://{UUID}@proxy.5px7.com:443?encryption=none&security=tls&type=ws&path=%2Fstream&host=proxy.5px7.com#{name}-cdn
```

---

## 7. Файрвол (UFW)

```
22/tcp   — SSH
80/tcp   — WebSocket (Cloudflare CDN)
443/tcp  — VLESS+Reality
```

---

## 8. Скрипт: Telegram-бот (xray_bot_v2.py)

Управление пользователями, выдача ключей, мониторинг IP.

```python
#!/usr/bin/env python3
"""
Telegram-бот для управления Xray VLESS+Reality + CDN.
- Автоматическая выдача ключей (оба режима: home + cdn)
- Мониторинг блокировки IP
- Добавление/удаление пользователей
- Автообновление конфига Xray
"""

import json
import uuid
import subprocess
import os
import asyncio
import requests
import time
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
#  НАСТРОЙКИ
# ============================================================

BOT_TOKEN = "ВСТАВЬ_ТОКЕН_БОТА"
ADMIN_IDS = [123456789]  # Твой Telegram ID (@userinfobot)

# Сервер
SERVER_IP = "70.34.243.161"
XRAY_CONFIG = "/usr/local/etc/xray/config.json"

# Reality (home)
REALITY_PORT = 443
REALITY_PUBLIC_KEY = "BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU"
REALITY_PRIVATE_KEY = "YO-lwSb-54h51GUCazD1HnQZNa3f1Wqm8byH4zzgikw"
REALITY_SNI = "www.samsung.com"
REALITY_SHORT_ID = "0123456789abcdef"
REALITY_FINGERPRINT = "chrome"

# CDN (office)
CDN_DOMAIN = "proxy.5px7.com"
CDN_PORT = 443
CDN_WS_PATH = "/stream"
CDN_LOCAL_PORT = 80

# Cloudflare
CLOUDFLARE_API_TOKEN = ""
CLOUDFLARE_ZONE_ID = ""
CLOUDFLARE_RECORD_NAME = "proxy.5px7.com"

# Мониторинг
CHECK_INTERVAL = 300  # секунд
MONITOR_ENABLED = True

# База пользователей
USERS_DB = "/usr/local/etc/xray/users.json"

# ============================================================
#  БАЗА ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

def load_users():
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_DB, "w") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

# ============================================================
#  ГЕНЕРАЦИЯ ССЫЛОК
# ============================================================

def generate_home_link(user_uuid, name):
    """Reality ссылка (дом/мобильный)."""
    return (
        f"vless://{user_uuid}@{SERVER_IP}:{REALITY_PORT}"
        f"?encryption=none&flow=xtls-rprx-vision"
        f"&security=reality&sni={REALITY_SNI}"
        f"&fp={REALITY_FINGERPRINT}"
        f"&pbk={REALITY_PUBLIC_KEY}"
        f"&sid={REALITY_SHORT_ID}"
        f"&type=tcp#{name}-home"
    )

def generate_cdn_link(user_uuid, name):
    """CDN ссылка (офис/корпоративные сети)."""
    return (
        f"vless://{user_uuid}@{CDN_DOMAIN}:{CDN_PORT}"
        f"?encryption=none&security=tls"
        f"&type=ws&path=%2Fstream"
        f"&host={CDN_DOMAIN}#{name}-cdn"
    )

# ============================================================
#  XRAY УПРАВЛЕНИЕ
# ============================================================

def update_xray_config(users):
    """Обновить конфиг с обоими inbound (Reality + WS)."""
    reality_clients = []
    ws_clients = []

    for uid, data in users.items():
        reality_clients.append({
            "id": data["uuid"],
            "flow": "xtls-rprx-vision"
        })
        ws_clients.append({
            "id": data["uuid"]
        })

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "listen": "0.0.0.0",
                "port": REALITY_PORT,
                "protocol": "vless",
                "settings": {
                    "clients": reality_clients,
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{REALITY_SNI}:{REALITY_PORT}",
                        "xver": 0,
                        "serverNames": [REALITY_SNI],
                        "privateKey": REALITY_PRIVATE_KEY,
                        "shortIds": ["", REALITY_SHORT_ID]
                    }
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"]
                }
            },
            {
                "listen": "0.0.0.0",
                "port": CDN_LOCAL_PORT,
                "protocol": "vless",
                "settings": {
                    "clients": ws_clients,
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {"path": CDN_WS_PATH}
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"]
                }
            }
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"}
        ]
    }

    with open(XRAY_CONFIG, "w") as f:
        json.dump(config, f, indent=2)

    result = subprocess.run(
        ["systemctl", "restart", "xray"],
        capture_output=True, text=True
    )
    return result.returncode == 0

def get_xray_status():
    result = subprocess.run(
        ["systemctl", "is-active", "xray"],
        capture_output=True, text=True
    )
    return result.stdout.strip() == "active"

# ============================================================
#  МОНИТОРИНГ IP
# ============================================================

def check_ip_blocked():
    """Проверить доступность сервера извне."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((SERVER_IP, 443))
        sock.close()
        return result != 0
    except:
        return True

async def monitor_ip(app):
    """Фоновый мониторинг IP."""
    fail_count = 0
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        if check_ip_blocked():
            fail_count += 1
            if fail_count >= 3:
                for admin_id in ADMIN_IDS:
                    try:
                        await app.bot.send_message(
                            admin_id,
                            f"⚠️ Сервер {SERVER_IP} недоступен уже {fail_count} проверок!\n"
                            f"Возможно IP заблокирован.\n"
                            f"CDN-ссылки продолжают работать."
                        )
                    except:
                        pass
        else:
            if fail_count > 0:
                fail_count = 0

# ============================================================
#  ПРОВЕРКА ПРАВ
# ============================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ============================================================
#  КОМАНДЫ БОТА
# ============================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        text = (
            f"Привет, {user.first_name}! Ты админ.\n\n"
            "Команды:\n"
            "/add имя — добавить пользователя\n"
            "/remove номер — удалить пользователя\n"
            "/list — список пользователей\n"
            "/key номер — показать ключи пользователя\n"
            "/status — статус сервера\n"
            "/updateip новый_ip — обновить IP\n"
            "/help — помощь"
        )
    else:
        text = (
            f"Привет, {user.first_name}!\n"
            "Используй /mykey чтобы получить ключ подключения."
        )
    await update.message.reply_text(text)

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Только для админов.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /add Имя")
        return

    name = " ".join(context.args)
    users = load_users()
    new_id = str(max([int(k) for k in users.keys()] + [0]) + 1)
    new_uuid = str(uuid.uuid4())

    users[new_id] = {
        "name": name,
        "uuid": new_uuid,
        "created": datetime.now().isoformat(),
        "telegram_id": None
    }
    save_users(users)

    if update_xray_config(users):
        home = generate_home_link(new_uuid, name)
        cdn = generate_cdn_link(new_uuid, name)
        await update.message.reply_text(
            f"✅ Пользователь #{new_id} ({name}) добавлен!\n\n"
            f"🏠 Home:\n`{home}`\n\n"
            f"🏢 CDN:\n`{cdn}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Ошибка перезапуска Xray!")

async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: /remove номер")
        return

    user_id = context.args[0]
    users = load_users()

    if user_id not in users:
        await update.message.reply_text(f"❌ Пользователь #{user_id} не найден.")
        return

    name = users[user_id]["name"]
    del users[user_id]
    save_users(users)

    if update_xray_config(users):
        await update.message.reply_text(f"✅ Пользователь #{user_id} ({name}) удалён.")
    else:
        await update.message.reply_text("❌ Ошибка перезапуска Xray!")

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    users = load_users()
    if not users:
        await update.message.reply_text("Список пуст.")
        return

    lines = ["👥 Пользователи:\n"]
    for uid, data in users.items():
        lines.append(f"#{uid} — {data['name']} ({data['created'][:10]})")
    await update.message.reply_text("\n".join(lines))

async def cmd_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: /key номер")
        return

    user_id = context.args[0]
    users = load_users()

    if user_id not in users:
        await update.message.reply_text(f"❌ Пользователь #{user_id} не найден.")
        return

    data = users[user_id]
    home = generate_home_link(data["uuid"], data["name"])
    cdn = generate_cdn_link(data["uuid"], data["name"])

    await update.message.reply_text(
        f"🔑 Ключи для {data['name']}:\n\n"
        f"🏠 Home:\n`{home}`\n\n"
        f"🏢 CDN:\n`{cdn}`",
        parse_mode="Markdown"
    )

async def cmd_mykey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    users = load_users()

    for uid, data in users.items():
        if data.get("telegram_id") == tg_id:
            home = generate_home_link(data["uuid"], data["name"])
            cdn = generate_cdn_link(data["uuid"], data["name"])
            await update.message.reply_text(
                f"🔑 Твои ключи:\n\n"
                f"🏠 Home (дом/мобильный):\n`{home}`\n\n"
                f"🏢 CDN (офис):\n`{cdn}`",
                parse_mode="Markdown"
            )
            return

    await update.message.reply_text(
        "❌ Ты не привязан. Попроси админа привязать твой Telegram ID."
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    xray_ok = get_xray_status()
    users = load_users()
    blocked = check_ip_blocked()

    await update.message.reply_text(
        f"📊 Статус сервера:\n\n"
        f"IP: {SERVER_IP}\n"
        f"Xray: {'✅ работает' if xray_ok else '❌ остановлен'}\n"
        f"Порт 443: {'❌ недоступен' if blocked else '✅ открыт'}\n"
        f"Пользователей: {len(users)}\n"
        f"Мониторинг: {'✅ вкл' if MONITOR_ENABLED else '❌ выкл'}"
    )

async def cmd_updateip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Использование: /updateip 1.2.3.4")
        return

    global SERVER_IP
    SERVER_IP = context.args[0]
    await update.message.reply_text(f"✅ IP обновлён на {SERVER_IP}")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 Инструкция:\n\n"
        "iPhone/iPad:\n"
        "1. Скачай Streisand или V2BOX из App Store\n"
        "2. Скопируй ключ (/mykey)\n"
        "3. + → Импорт из буфера\n"
        "4. Разреши VPN-конфигурацию\n\n"
        "Android:\n"
        "1. Скачай v2rayNG (Google Play)\n"
        "2. + → Импорт из буфера\n\n"
        "Windows:\n"
        "1. Скачай Nekobox (GitHub)\n"
        "2. Распакуй, запусти nekobox.exe\n"
        "3. Сервер → Добавить из буфера\n"
        "4. Включи «Режим системного прокси»\n\n"
        "⚠️ Не работает? Попробуй CDN-ссылку вместо Home."
    )
    await update.message.reply_text(text)

# ============================================================
#  ЗАПУСК
# ============================================================

async def post_init(app):
    if MONITOR_ENABLED:
        asyncio.create_task(monitor_ip(app))

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("key", cmd_key))
    app.add_handler(CommandHandler("mykey", cmd_mykey))
    app.add_handler(CommandHandler("link", cmd_key))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("updateip", cmd_updateip))
    app.add_handler(CommandHandler("help", cmd_help))

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
```

### Автозапуск бота (systemd)

```ini
# /etc/systemd/system/xray-bot.service
[Unit]
Description=Xray Telegram Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /root/xray_bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable xray-bot
systemctl start xray-bot
```

---

## 9. Скрипт: Авто-пересоздание VPS (vultr_manager.py)

```python
#!/usr/bin/env python3
"""
Мониторинг блокировки IP + автопересоздание VPS на Vultr.

Режимы:
  python3 vultr_manager.py monitor   — фоновый мониторинг (каждые 5 мин)
  python3 vultr_manager.py recreate  — пересоздать вручную
  python3 vultr_manager.py status    — проверить статус
"""

import json
import time
import sys
import os
import socket
import requests
from datetime import datetime

# ============================================================
#  НАСТРОЙКИ
# ============================================================

VULTR_API_KEY = "ВСТАВЬ_VULTR_API_KEY"

SERVER_LABEL = "xray-proxy"
SERVER_REGION = "waw"
SERVER_PLAN = "vc2-1c-1gb"
SERVER_OS_ID = 2284  # Ubuntu 24.04

# Xray
XRAY_USERS = [
    {"id": "4fd1690d-5785-4c71-9533-2802732a3cbf", "name": "Никита"},
    {"id": "2bfe69be-b66a-4fd5-966b-ef7088e506df", "name": "User2"},
    {"id": "0ca420f4-8490-44be-a377-2d0cdb651ab2", "name": "User3"},
]
XRAY_PRIVATE_KEY = "YO-lwSb-54h51GUCazD1HnQZNa3f1Wqm8byH4zzgikw"
XRAY_PUBLIC_KEY = "BSqwzaAcsByTLRbBPp8kGiVzq_P_zFXU6uKSIbxAaGU"
XRAY_SNI = "www.samsung.com"
XRAY_SHORT_ID = "0123456789abcdef"

# Cloudflare DNS
CLOUDFLARE_API_TOKEN = ""
CLOUDFLARE_ZONE_ID = ""
DNS_RECORD_NAME = "proxy.5px7.com"

# Telegram уведомления
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# Мониторинг
CHECK_INTERVAL = 300
FAIL_THRESHOLD = 3
STATE_FILE = "vultr_state.json"

VULTR_API = "https://api.vultr.com/v2"

# ============================================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def vultr_headers():
    return {"Authorization": f"Bearer {VULTR_API_KEY}", "Content-Type": "application/json"}

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"current_ip": None, "fail_count": 0, "total_recreates": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
        )
    except:
        pass

def check_server_available(ip):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((ip, 443))
        sock.close()
        return result == 0
    except:
        return False

# ============================================================
#  VULTR API
# ============================================================

def find_server():
    r = requests.get(f"{VULTR_API}/instances", headers=vultr_headers())
    r.raise_for_status()
    for s in r.json().get("instances", []):
        if s["label"] == SERVER_LABEL:
            return s
    return None

def delete_server(server_id):
    log(f"Удаляю сервер {server_id}...")
    r = requests.delete(f"{VULTR_API}/instances/{server_id}", headers=vultr_headers())
    r.raise_for_status()
    log("Удалён.")
    time.sleep(10)

def generate_xray_config():
    reality_clients = [{"id": u["id"], "flow": "xtls-rprx-vision"} for u in XRAY_USERS]
    ws_clients = [{"id": u["id"]} for u in XRAY_USERS]

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "listen": "0.0.0.0", "port": 443, "protocol": "vless",
                "settings": {"clients": reality_clients, "decryption": "none"},
                "streamSettings": {
                    "network": "tcp", "security": "reality",
                    "realitySettings": {
                        "show": False, "dest": f"{XRAY_SNI}:443", "xver": 0,
                        "serverNames": [XRAY_SNI],
                        "privateKey": XRAY_PRIVATE_KEY,
                        "shortIds": ["", XRAY_SHORT_ID],
                    },
                },
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
            },
            {
                "listen": "0.0.0.0", "port": 80, "protocol": "vless",
                "settings": {"clients": ws_clients, "decryption": "none"},
                "streamSettings": {"network": "ws", "wsSettings": {"path": "/stream"}},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
            },
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
    }
    return json.dumps(config, indent=2)

def generate_cloud_init():
    xray_config = generate_xray_config()
    script = f"""#!/bin/bash
set -e
apt-get update && apt-get upgrade -y
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
cat > /usr/local/etc/xray/config.json << 'XRAYCONFIG'
{xray_config}
XRAYCONFIG
apt-get install -y ufw
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl restart xray
systemctl enable xray
"""
    return script

def create_server():
    log("Создаю новый сервер...")
    data = {
        "region": SERVER_REGION,
        "plan": SERVER_PLAN,
        "os_id": SERVER_OS_ID,
        "label": SERVER_LABEL,
        "script_id": None,
        "user_data": generate_cloud_init(),
    }
    r = requests.post(f"{VULTR_API}/instances", headers=vultr_headers(), json=data)
    r.raise_for_status()
    server_id = r.json()["instance"]["id"]
    log(f"Создан: {server_id}")
    return server_id

def wait_for_server(server_id):
    log("Жду запуска сервера...")
    for _ in range(60):
        r = requests.get(f"{VULTR_API}/instances/{server_id}", headers=vultr_headers())
        r.raise_for_status()
        instance = r.json()["instance"]
        ip = instance.get("main_ip", "0.0.0.0")
        status = instance.get("status", "")
        power = instance.get("power_status", "")
        if ip != "0.0.0.0" and status == "active" and power == "running":
            log(f"Сервер запущен! IP: {ip}")
            return ip
        time.sleep(10)
    raise TimeoutError("Сервер не запустился за 10 минут")

def update_dns(ip):
    if not all([CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID]):
        log("DNS не настроен — пропускаю.")
        return
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    # Найти запись
    r = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records?name={DNS_RECORD_NAME}",
        headers=headers
    )
    records = r.json().get("result", [])
    if records:
        record_id = records[0]["id"]
        requests.put(
            f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}",
            headers=headers,
            json={"type": "A", "name": DNS_RECORD_NAME, "content": ip, "proxied": True}
        )
        log(f"DNS обновлён: {DNS_RECORD_NAME} → {ip}")

def generate_links(ip):
    links = []
    for u in XRAY_USERS:
        links.append({
            "name": u["name"],
            "home": (
                f"vless://{u['id']}@{ip}:443?encryption=none&flow=xtls-rprx-vision"
                f"&security=reality&sni={XRAY_SNI}&fp=chrome"
                f"&pbk={XRAY_PUBLIC_KEY}&sid={XRAY_SHORT_ID}&type=tcp#{u['name']}-home"
            ),
            "cdn": (
                f"vless://{u['id']}@{DNS_RECORD_NAME}:443?encryption=none"
                f"&security=tls&type=ws&path=%2Fstream&host={DNS_RECORD_NAME}#{u['name']}-cdn"
            ),
        })
    return links

# ============================================================
#  ОСНОВНЫЕ КОМАНДЫ
# ============================================================

def recreate():
    log("=== ПЕРЕСОЗДАНИЕ СЕРВЕРА ===")
    send_telegram("🔄 Начинаю пересоздание сервера...")

    existing = find_server()
    if existing:
        delete_server(existing["id"])

    server_id = create_server()
    new_ip = wait_for_server(server_id)

    log("Жду установки Xray (~90 сек)...")
    time.sleep(90)

    for i in range(12):
        if check_server_available(new_ip):
            log("✅ Сервер доступен!")
            break
        log(f"Ожидание... ({i+1}/12)")
        time.sleep(10)

    update_dns(new_ip)
    links = generate_links(new_ip)

    state = load_state()
    state["current_ip"] = new_ip
    state["fail_count"] = 0
    state["total_recreates"] = state.get("total_recreates", 0) + 1
    save_state(state)

    print(f"\n{'='*60}")
    print(f"  Новый IP: {new_ip}")
    print(f"{'='*60}")
    for link in links:
        print(f"\n  {link['name']}:")
        print(f"  Home: {link['home']}")
        print(f"  CDN:  {link['cdn']}")

    tg_lines = [f"✅ Сервер пересоздан!\nНовый IP: `{new_ip}`\n"]
    for link in links:
        tg_lines.append(f"*{link['name']}:*\n`{link['home']}`\n")
    send_telegram("\n".join(tg_lines))
    log("=== ГОТОВО ===")

def monitor():
    log("=== МОНИТОРИНГ ЗАПУЩЕН ===")
    state = load_state()
    server = find_server()
    if server:
        state["current_ip"] = server.get("main_ip")
        save_state(state)
        log(f"Текущий IP: {state['current_ip']}")
    else:
        log("⚠ Сервер не найден!")
        return

    while True:
        time.sleep(CHECK_INTERVAL)
        ip = state["current_ip"]
        available = check_server_available(ip)
        state["last_check"] = datetime.now().isoformat()

        if available:
            if state["fail_count"] > 0:
                log(f"✅ Сервер снова доступен")
                state["fail_count"] = 0
                save_state(state)
        else:
            state["fail_count"] += 1
            save_state(state)
            log(f"⚠ Недоступен! ({state['fail_count']}/{FAIL_THRESHOLD})")

            if state["fail_count"] >= FAIL_THRESHOLD:
                log("🔄 Порог достигнут — пересоздаю!")
                send_telegram(f"⚠️ IP {ip} недоступен {FAIL_THRESHOLD} раз подряд. Пересоздаю...")
                recreate()
                state = load_state()

def status():
    server = find_server()
    if server:
        ip = server.get("main_ip", "?")
        state = load_state()
        available = check_server_available(ip)
        print(f"Сервер: {server['label']}")
        print(f"IP: {ip}")
        print(f"Статус: {server.get('status', '?')}")
        print(f"Порт 443: {'доступен' if available else 'НЕДОСТУПЕН'}")
        print(f"Пересозданий: {state.get('total_recreates', 0)}")
    else:
        print("Сервер не найден.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 vultr_manager.py monitor")
        print("  python3 vultr_manager.py recreate")
        print("  python3 vultr_manager.py status")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "monitor": monitor()
    elif cmd == "recreate": recreate()
    elif cmd == "status": status()
```

---

## 10. Скрипт установки бота (setup_bot.sh)

```bash
#!/bin/bash
set -e

echo "=== Установка Xray Telegram Bot ==="

echo "[1/4] Установка зависимостей..."
pip install python-telegram-bot requests --break-system-packages -q

echo "[2/4] Создание базы пользователей..."
cat > /usr/local/etc/xray/users.json << 'EOF'
{
  "1": {
    "name": "Никита",
    "uuid": "4fd1690d-5785-4c71-9533-2802732a3cbf",
    "created": "2026-04-07T13:20:00",
    "telegram_id": null
  },
  "2": {
    "name": "User2",
    "uuid": "2bfe69be-b66a-4fd5-966b-ef7088e506df",
    "created": "2026-04-07T13:20:00",
    "telegram_id": null
  },
  "3": {
    "name": "User3",
    "uuid": "0ca420f4-8490-44be-a377-2d0cdb651ab2",
    "created": "2026-04-07T14:30:00",
    "telegram_id": null
  }
}
EOF

echo "[3/4] Создание systemd сервиса..."
cat > /etc/systemd/system/xray-bot.service << 'EOF'
[Unit]
Description=Xray Telegram Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /root/xray_bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "[4/4] Готово!"
echo ""
echo "Осталось:"
echo "1. Скопируй xray_bot_v2.py в /root/xray_bot.py"
echo "2. Заполни BOT_TOKEN и ADMIN_IDS"
echo "3. Запусти: systemctl start xray-bot"
```

---

## 11. Обслуживание

### Обновление Xray
```bash
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
systemctl restart xray
```

### Просмотр логов
```bash
journalctl -u xray -f
```

### Добавление пользователя вручную
1. `xray uuid` — сгенерировать UUID
2. Добавить в оба inbound в конфиге (TCP и WS)
3. `systemctl restart xray`
4. Сформировать обе ссылки (home + cdn)

### При блокировке IP
1. `python3 vultr_manager.py recreate` — пересоздать VPS
2. Или вручную: пересоздать на Vultr → переустановить Xray → обновить DNS
3. CDN-ссылки обновятся автоматически (привязаны к домену)
4. Home-ссылки — обновить IP у пользователей

---

## 12. Клиентские приложения

| Платформа | Приложение | Источник |
|-----------|-----------|----------|
| iOS/iPadOS | Streisand, V2BOX, FoXray | App Store |
| Android | v2rayNG | Google Play / GitHub |
| Windows | Nekobox | GitHub |
| macOS | Nekobox, V2BOX | GitHub |

---

## 13. Известные проблемы и решения

| Проблема | Причина | Решение |
|----------|---------|---------|
| `unsupported flow: xtls-rprx-` | Старая версия Nekobox | Обновить или использовать CDN-ссылку |
| Нет интернета после закрытия Nekobox | Системный прокси остался включён | Открыть Nekobox → выключить прокси → закрыть |
| Не коннектится из офиса | Корпоративная сеть блокирует | Использовать CDN-ссылку |
| VPN-адаптеры конфликтуют | Radmin, OpenVPN, Outline | Удалить лишние адаптеры |
| SSH не работает из офиса | Порт 22 заблокирован | Vultr web console |

---

## 14. TODO

- [ ] Установить 3x-ui панель
- [ ] Удалить VPN-адаптеры на Windows (Radmin, OpenVPN, Outline)
- [ ] Развернуть Telegram-бота на сервере
- [ ] Заполнить Cloudflare API Token в vultr_manager.py
- [ ] Настроить subscription URL через 3x-ui
