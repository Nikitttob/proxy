# Прокси-сервер — полная документация

> Последнее обновление: апрель 2026
> Владелец: Никита

> ⚠️ **Все секреты вынесены в `.env` (см. [`.env.example`](./.env.example)).**
> Если когда-то ключи попадали в git — считаем их скомпрометированными,
> ротируем (раздел 12).

---

## 1. Инфраструктура

| Параметр | Значение |
|----------|----------|
| Хостинг | Vultr |
| Регион | Варшава (waw) |
| План | vc2-1c-1gb (~$6/мес) |
| ОС | Ubuntu 24.04 |
| IP | задаётся в `.env` (`SERVER_IP`) |
| Домен | задаётся в `.env` (`CDN_DOMAIN`) |
| DNS | A-запись на `SERVER_IP`, Cloudflare proxy: ON |
| SSL/TLS Cloudflare | **Full (strict)** — обязательно |
| Стоимость | ~$77/год (VPS $72 + домен $5.30) |

Раньше использовалось CF SSL = Flexible. Это значит, что CF↔origin шёл по
HTTP — кто угодно на пути мог читать/подменять трафик. Теперь Caddy
терминирует TLS на VPS (Let's Encrypt), CF переведён в Full (strict).

---

## 2. Ключи и секреты

Все ключи (Reality private/public, BOT_TOKEN, VULTR_API_KEY и т. д.) хранятся
**только** в `/etc/xray-proxy/env` на сервере (`chmod 600`). Шаблон —
[`.env.example`](./.env.example).

| Ключ | Где взять |
|------|-----------|
| `XRAY_PRIVATE_KEY`, `XRAY_PUBLIC_KEY` | `xray x25519` |
| `XRAY_SNI` | домен с TLS 1.3 + X25519 + H2 (см. ниже) |
| `BOT_TOKEN` | @BotFather |
| `ADMIN_IDS` | @userinfobot |
| `VULTR_API_KEY` | https://my.vultr.com/settings/#settingsapi |
| `CLOUDFLARE_API_TOKEN` | dashboard CF, scope: Zone.DNS:Edit |
| `SSH_PUBLIC_KEY` | `cat ~/.ssh/id_ed25519.pub` |

**Кандидаты на `XRAY_SNI`** (с поддержкой TLS 1.3 + X25519 + H2):
`gateway.icloud.com`, `www.lovelive-anime.jp`, `dl.google.com`,
`www.microsoft.com`. Проверка:

```bash
openssl s_client -connect $XRAY_SNI:443 -tls1_3 -alpn h2 -servername $XRAY_SNI </dev/null 2>&1 | grep -E 'Protocol|Cipher|ALPN'
```

---

## 3. Пользователи

Хранятся в `/usr/local/etc/xray/users.json`:

```json
{
  "1": {
    "name": "Никита",
    "uuid": "<uuid>",
    "short_id": "<8 байт hex>",
    "telegram_id": 123456789,
    "created": "2026-04-07T13:20:00"
  }
}
```

`short_id` уникален на каждого пользователя — нужно для того, чтобы можно было
отозвать конкретного без перевыпуска ключей всем остальным.

Управление — через бот:

| Команда | Что делает |
|---------|------------|
| `/add Имя` | создать пользователя + сгенерировать UUID и shortId |
| `/remove N` | удалить и применить новый конфиг |
| `/list` | список + кому выдан Telegram-bind |
| `/key N` | показать ключи пользователю #N (admin) |
| `/bind N tg_id` | привязать Telegram-ID к пользователю |
| `/unbind N` | отвязать |
| `/mykey` | пользователь получает свои ключи |
| `/status` | состояние сервера |
| `/updateip 1.2.3.4` | сменить IP, перегенерировать конфиг, разослать новые home-ссылки |

---

## 4. Архитектура: два режима

### Home (Reality + TCP)
- VLESS + Reality, порт 443, TCP, `xtls-rprx-vision`
- Подключение напрямую к IP сервера
- Максимальная скорость, лучшая маскировка под HTTPS

### CDN (WebSocket + TLS через Caddy + Cloudflare)
- VLESS / WS, путь `/stream`
- Caddy на VPS терминирует TLS (Let's Encrypt) и проксирует на
  локальный Xray (`127.0.0.1:8080` по умолчанию)
- Cloudflare в режиме Full (strict) → проксирует к Caddy
- Работает там, где IP заблокирован

---

## 5. Конфиг Xray

Конфиг **не пишется руками**. Он генерируется единым кодом
[`xray_proxy/xray_config.py`](./xray_proxy/xray_config.py), который зовут
и бот (`update_xray_config`), и менеджер VPS (cloud-init).

Применение в боте — с rollback-ом: новый файл валидируется через
`xray run -test`, при ошибке остаётся прежний конфиг.

---

## 6. Ссылки подключения

Генерируются [`xray_proxy/links.py`](./xray_proxy/links.py).
Имена URL-кодируются, чтобы пробелы и кириллица не ломали парсер клиента.

**Шаблоны:**

```
vless://{UUID}@{SERVER_IP}:443?encryption=none&flow=xtls-rprx-vision
       &security=reality&sni={XRAY_SNI}&fp=chrome
       &pbk={XRAY_PUBLIC_KEY}&sid={USER_SHORT_ID}&type=tcp#{name}-home

vless://{UUID}@{CDN_DOMAIN}:443?encryption=none&security=tls
       &type=ws&path=%2Fstream&host={CDN_DOMAIN}#{name}-cdn
```

---

## 7. Порты и файрвол (UFW)

Reality и Caddy не могут оба слушать `:443`, поэтому разнесены:

| Порт | Слушает | Кто ходит |
|------|---------|-----------|
| `22/tcp`   | sshd | админ (с rate-limit через `ufw limit`) |
| `443/tcp`  | Xray (Reality, TCP) | home-клиенты напрямую |
| `8443/tcp` | Caddy (TLS-терминатор) | **только Cloudflare** |
| `127.0.0.1:8080` | Xray (WS-inbound) | только Caddy |

CDN-клиент по-прежнему идёт на CF на :443 — CF проксирует в origin на :8443
через **Origin Rule**:

> CF dashboard → Rules → **Origin Rules** → Create rule:
> «If Hostname equals `proxy.example.com` → Override resolved port = `8443`».

Сертификат Let's Encrypt получает `certbot` через DNS-01 (плагин
`python3-certbot-dns-cloudflare`), потому что:
- HTTP-01 не работает: CF проксирует и редиректит :80 → :443 на edge.
- TLS-ALPN-01 не работает: :443 занят Reality.
- DNS-01 надёжен и не требует пробрасывать порты для challenge.

Хук `/etc/letsencrypt/renewal-hooks/deploy/caddy.sh` перезагружает Caddy при
автообновлении сертификата.

Конфиг файрвола ставится автоматически в
[`deploy/cloud_init.sh.tmpl`](./deploy/cloud_init.sh.tmpl).

---

## 8. Telegram-бот

Код: [`bot/xray_bot.py`](./bot/xray_bot.py).
Запускается как systemd-юнит [`deploy/xray-bot.service`](./deploy/xray-bot.service):

```bash
sudo cp deploy/xray-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now xray-bot
journalctl -u xray-bot -f
```

**Что починено по сравнению со старой версией:**

- `cmd_updateip` теперь персистит `SERVER_IP` в `.env`, перегенерирует
  конфиг и **рассылает новые home-ссылки** всем привязанным пользователям.
- Появились `/bind` и `/unbind` — теперь `/mykey` действительно работает.
- Все ответы — в HTML (`html.escape`), не ломаются на спецсимволах.
- `update_xray_config` использует `xray run -test` и атомарную замену с
  бэкапом — кривой конфиг не уронит сервис.
- Мониторинг с cooldown (`ALERT_COOLDOWN`), не спамит каждые 5 минут.
- `users.json` под `fcntl.flock`, запись через tmp + `os.replace`.

---

## 9. Менеджер VPS

Код: [`manager/vultr_manager.py`](./manager/vultr_manager.py).

```bash
python3 manager/vultr_manager.py status
python3 manager/vultr_manager.py recreate
python3 manager/vultr_manager.py monitor    # для systemd
```

Через systemd:

```bash
sudo cp deploy/vultr-monitor.service /etc/systemd/system/
systemctl enable --now vultr-monitor
```

**Что починено:**

- Все `requests.*` с таймаутами `(5, 30)`.
- `recreate()`: создаём новый → ждём → DNS → удаляем старый. Если новый не
  поднялся — старый остаётся.
- `update_dns()` создаёт A-запись, если её нет (раньше молча игнорировал).
- Путь к state-файлу абсолютный, через `.env` (`VULTR_STATE_FILE`),
  systemd-юнит создаёт `StateDirectory=xray-proxy`.
- Cloud-init: SSH без пароля + публичный ключ из `.env`, `fail2ban`,
  `ufw limit 22/tcp`, Caddy с автоматическим Let's Encrypt.

---

## 10. Установка с нуля

1. Создать VPS в Vultr (Ubuntu 24.04), указать SSH-ключ.
2. Зайти по ssh, склонировать:
   ```bash
   git clone <repo> /opt/xray-proxy
   cd /opt/xray-proxy
   sudo bash deploy/setup_bot.sh
   sudo cp .env.example /etc/xray-proxy/env
   sudo $EDITOR /etc/xray-proxy/env   # заполнить REPLACE_ME
   ```
3. В Cloudflare: A-запись `proxy.example.com → SERVER_IP`, proxy ON,
   SSL/TLS → **Full (strict)**.
4. `systemctl enable --now xray xray-bot vultr-monitor`.
5. В Telegram: `/start` → `/add Никита` → ссылка приходит ответом.

---

## 11. Обслуживание

### Обновление Xray
```bash
bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
systemctl restart xray
```

### Логи
```bash
journalctl -u xray -f
journalctl -u xray-bot -f
journalctl -u vultr-monitor -f
journalctl -u caddy -f
```

### Бэкап секретов и базы пользователей
Автоматически каждый день в 03:30 в `/var/backups/xray-proxy/` (ротация 14 дней)
бэкапится и `users.json`, и `/etc/xray-proxy/env`. Без `.env` при гибели VPS
теряются все ключи — Reality, BOT_TOKEN, VULTR_API_KEY, CLOUDFLARE_API_TOKEN.
Архивы лежат с правами `600` — содержат секреты, синхронизировать
куда-то наружу нужно осторожно (gpg-encrypt → S3/B2/локальный диск).
См. [`scripts/backup_users.sh`](./scripts/backup_users.sh).

### При блокировке IP
1. `python3 manager/vultr_manager.py recreate` — пересоздать VPS.
2. CDN-ссылки не меняются (привязаны к домену).
3. Home-ссылки с новым IP бот разошлёт сам после `/updateip`
   (если в `vultr_manager.py` отключена авто-нотификация).

---

## 12. Ротация скомпрометированных ключей Reality

```bash
xray x25519
# скопировать Private/Public в /etc/xray-proxy/env
$EDITOR /etc/xray-proxy/env
systemctl restart xray xray-bot
# в Telegram попросить бота отправить новые ссылки
/key 1
/key 2
...
```

`short_id` в `users.json` остаются прежними — менять не нужно.

---

## 13. Клиентские приложения

| Платформа | Приложение | Источник |
|-----------|-----------|----------|
| iOS/iPadOS | Streisand, V2BOX, FoXray | App Store |
| Android | v2rayNG | Google Play / GitHub |
| Windows | Nekobox | GitHub |
| macOS | Nekobox, V2BOX | GitHub |

---

## 14. Известные проблемы

| Проблема | Причина | Решение |
|----------|---------|---------|
| `unsupported flow: xtls-rprx-` | Старая версия клиента | Обновить или CDN |
| Нет интернета после Nekobox | Системный прокси не выключен | Открыть → выкл → закрыть |
| Не коннектится из офиса | DPI/блок IP | CDN-ссылка |
| VPN-адаптеры конфликтуют | Radmin/OpenVPN/Outline | Снести лишние |
| SSH из офиса не работает | Порт 22 закрыт | Vultr web console |

---

## 15. TODO

- [x] Вынести секреты в `.env`
- [x] Caddy + CF Full (strict) вместо Flexible
- [x] Per-user shortId
- [x] Rollback конфига Xray
- [x] cooldown алертов
- [x] `/bind` для `/mykey`
- [x] cloud-init: SSH-only, fail2ban, ufw limit
- [x] Конфликт Reality :443 vs Caddy :443 решён (Caddy → :8443 + CF Origin Rule)
- [x] Бэкап включает `.env`
- [x] Atomic + flock запись `.env` (`update_env_file`)
- [x] Уникальные timestamped label при пересоздании VPS
- [ ] Создать в Cloudflare Origin Rule (Override port → 8443) для CDN-домена
- [ ] Заполнить `CLOUDFLARE_API_TOKEN` в `/etc/xray-proxy/env`
- [ ] Настроить выгрузку `/var/backups/xray-proxy/` куда-то наружу (gpg+S3)
- [ ] Рассмотреть миграцию на 3x-ui / Marzban / Hiddify (см. README)
