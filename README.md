# Xray VLESS+Reality + CDN прокси

Автоматизация VLESS+Reality прокси на Vultr с резервным WebSocket-каналом через Cloudflare.

Полное описание инфраструктуры, архитектуры и рабочих процедур — в
[`proxy-documentation.md`](./proxy-documentation.md).

## Структура репозитория

```
bot/              Telegram-бот для управления пользователями
manager/          Скрипт авто-пересоздания VPS на Vultr
xray_proxy/       Общий пакет: генерация конфигов, ссылок, БД пользователей
deploy/           systemd-юниты, Caddyfile, cloud-init, скрипт установки
scripts/          Сервисные скрипты (бэкапы и пр.)
```

## Быстрый старт

1. Склонировать репо на VPS.
2. Скопировать `.env.example` → `/etc/xray-proxy/env`, заполнить все `REPLACE_ME`.
   Сгенерировать `XRAY_PRIVATE_KEY`/`XRAY_PUBLIC_KEY`: `xray x25519`.
3. Поставить Caddy (см. `deploy/Caddyfile`) и перевести Cloudflare в
   **SSL/TLS → Full (strict)**. Flexible небезопасен — трафик CF↔origin идёт
   по HTTP.
4. `sudo bash deploy/setup_bot.sh` — ставит зависимости, копирует systemd-юниты.
5. `systemctl enable --now xray-bot vultr-monitor`.

## Ротация скомпрометированных ключей

Любые ключи, хоть раз попавшие в git, нужно считать скомпрометированными.

```bash
xray x25519                                   # сгенерировать новую пару
$EDITOR /etc/xray-proxy/env                   # обновить XRAY_PRIVATE_KEY / XRAY_PUBLIC_KEY
systemctl restart xray xray-bot
```

После рестарта все клиенты должны получить новые `home`-ссылки
(`/key <id>` или `/mykey` у каждого пользователя).

## Альтернатива самописным скриптам

Если парк пользователей растёт или нужны лимиты по трафику — есть смысл
мигрировать на готовую панель: **3x-ui**, **Marzban**, **Hiddify**. Они
закрывают per-user shortIds, учёт трафика, rollback конфигов и subscription
URL из коробки.
