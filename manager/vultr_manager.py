#!/usr/bin/env python3
"""Мониторинг блокировки IP + автопересоздание VPS на Vultr.

Режимы:
  python3 vultr_manager.py monitor
  python3 vultr_manager.py recreate
  python3 vultr_manager.py status

Исправления:
- timeout на всех HTTP-запросах
- create → verify → DNS → delete-old (а не delete → create)
- DNS: create-or-update (не молчит при отсутствии записи)
- абсолютный путь к state-файлу из .env
- SSH-ключи + fail2ban + UFW limit в cloud-init
- конкретные except, logging
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from xray_proxy import userdb
from xray_proxy.config import Settings, load
from xray_proxy.links import cdn_link, home_link
from xray_proxy.net import check_port
from xray_proxy.xray_config import build_config, dump

log = logging.getLogger("vultr_manager")

VULTR_API = "https://api.vultr.com/v2"
HTTP_TIMEOUT = (5, 30)  # (connect, read)
CLOUD_INIT_TMPL = Path(__file__).resolve().parent.parent / "deploy" / "cloud_init.sh.tmpl"


# ---------------------------------------------------------------------------
#  Состояние
# ---------------------------------------------------------------------------

def load_state(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text() or "{}")
    return {"current_ip": None, "fail_count": 0, "total_recreates": 0}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(path)


# ---------------------------------------------------------------------------
#  Vultr API
# ---------------------------------------------------------------------------

def _vultr_headers(s: Settings) -> dict:
    return {
        "Authorization": f"Bearer {s.vultr_api_key}",
        "Content-Type": "application/json",
    }


def find_server(s: Settings) -> Optional[dict]:
    r = requests.get(
        f"{VULTR_API}/instances",
        headers=_vultr_headers(s),
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    for inst in r.json().get("instances", []):
        if inst["label"] == s.server_label:
            return inst
    return None


def delete_server(s: Settings, server_id: str) -> None:
    log.info("deleting server %s", server_id)
    r = requests.delete(
        f"{VULTR_API}/instances/{server_id}",
        headers=_vultr_headers(s),
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()


def generate_cloud_init(s: Settings, users: dict) -> str:
    config = build_config(s, users.values())
    tmpl = CLOUD_INIT_TMPL.read_text()
    return Template(tmpl).safe_substitute(
        XRAY_CONFIG_JSON=dump(config),
        SSH_PUBLIC_KEY=s.ssh_public_key,
        CDN_DOMAIN=s.cdn_domain,
        CDN_LOCAL_PORT=str(s.cdn_local_port),
    )


def create_server(s: Settings, users: dict) -> str:
    log.info("creating server in %s / %s", s.server_region, s.server_plan)
    body = {
        "region": s.server_region,
        "plan": s.server_plan,
        "os_id": s.server_os_id,
        "label": s.server_label,
        "user_data": generate_cloud_init(s, users),
        "backups": "disabled",
    }
    r = requests.post(
        f"{VULTR_API}/instances",
        headers=_vultr_headers(s),
        json=body,
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    server_id = r.json()["instance"]["id"]
    log.info("created: %s", server_id)
    return server_id


def wait_for_server(s: Settings, server_id: str, max_wait: int = 900) -> str:
    """Ждём, пока Vultr поднимет VM. Возвращает IP."""
    log.info("waiting for server %s", server_id)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = requests.get(
            f"{VULTR_API}/instances/{server_id}",
            headers=_vultr_headers(s),
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        inst = r.json()["instance"]
        ip = inst.get("main_ip", "0.0.0.0")
        if (
            ip != "0.0.0.0"
            and inst.get("status") == "active"
            and inst.get("power_status") == "running"
        ):
            log.info("server up, ip=%s", ip)
            return ip
        time.sleep(10)
    raise TimeoutError(f"server {server_id} не поднялся за {max_wait} сек")


def wait_for_xray(ip: str, max_wait: int = 300) -> bool:
    log.info("waiting for xray on %s:443", ip)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if check_port(ip, 443, timeout=5):
            return True
        time.sleep(10)
    return False


# ---------------------------------------------------------------------------
#  Cloudflare DNS
# ---------------------------------------------------------------------------

def _cf_headers(s: Settings) -> dict:
    return {
        "Authorization": f"Bearer {s.cloudflare_api_token}",
        "Content-Type": "application/json",
    }


def update_dns(s: Settings, ip: str) -> None:
    if not (s.cloudflare_api_token and s.cloudflare_zone_id and s.dns_record_name):
        log.info("DNS не настроен — пропускаю")
        return

    base = f"https://api.cloudflare.com/client/v4/zones/{s.cloudflare_zone_id}/dns_records"
    r = requests.get(
        base,
        headers=_cf_headers(s),
        params={"name": s.dns_record_name, "type": "A"},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    records = r.json().get("result", [])

    payload = {
        "type": "A",
        "name": s.dns_record_name,
        "content": ip,
        "proxied": True,
        "ttl": 1,
    }

    if records:
        rid = records[0]["id"]
        r = requests.put(
            f"{base}/{rid}", headers=_cf_headers(s), json=payload,
            timeout=HTTP_TIMEOUT,
        )
    else:
        r = requests.post(
            base, headers=_cf_headers(s), json=payload,
            timeout=HTTP_TIMEOUT,
        )
    r.raise_for_status()
    log.info("DNS: %s → %s", s.dns_record_name, ip)


# ---------------------------------------------------------------------------
#  Telegram уведомления
# ---------------------------------------------------------------------------

def send_telegram(s: Settings, text: str) -> None:
    if not (s.telegram_bot_token and s.telegram_chat_id):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException:
        log.exception("telegram notification failed")


# ---------------------------------------------------------------------------
#  Генерация ссылок для оповещения
# ---------------------------------------------------------------------------

def collect_links(s: Settings, users: dict, ip: str) -> list[dict]:
    # Подменяем IP в копии настроек для home-ссылок.
    s_ip = Settings(**{**s.__dict__, "server_ip": ip})  # type: ignore[arg-type]
    out = []
    for data in users.values():
        sid = userdb.ensure_short_id(data)
        out.append({
            "name": data["name"],
            "home": home_link(s_ip, data["uuid"], data["name"], sid),
            "cdn": cdn_link(s, data["uuid"], data["name"]),
        })
    return out


# ---------------------------------------------------------------------------
#  Режимы
# ---------------------------------------------------------------------------

def recreate(s: Settings) -> None:
    log.info("=== RECREATE ===")
    send_telegram(s, "🔄 Пересоздаю сервер…")

    users = userdb.load_users(s.users_db)
    old = find_server(s)

    # Если текущий инстанс уже есть — временно переименуем, чтобы новый занял
    # label. Иначе API не даст создать дубликат по тому же label.
    if old:
        try:
            requests.patch(
                f"{VULTR_API}/instances/{old['id']}",
                headers=_vultr_headers(s),
                json={"label": f"{s.server_label}-old"},
                timeout=HTTP_TIMEOUT,
            ).raise_for_status()
        except requests.RequestException:
            log.exception("could not rename old instance, продолжаю")

    new_id = create_server(s, users)
    try:
        new_ip = wait_for_server(s, new_id)
    except TimeoutError:
        # Новый не поднялся — откатываем label старому, новый удаляем.
        log.error("new server did not come up, rolling back")
        delete_server(s, new_id)
        if old:
            requests.patch(
                f"{VULTR_API}/instances/{old['id']}",
                headers=_vultr_headers(s),
                json={"label": s.server_label},
                timeout=HTTP_TIMEOUT,
            )
        send_telegram(s, "❌ Новый VPS не поднялся, старый оставлен.")
        raise

    if not wait_for_xray(new_ip):
        log.warning("xray not reachable yet on %s, но продолжаю DNS-update", new_ip)

    update_dns(s, new_ip)

    # Сохраняем users.json обратно — вдруг ensure_short_id сгенерил новые.
    userdb.save_users(s.users_db, users)

    # Теперь можно удалить старый.
    if old:
        try:
            delete_server(s, old["id"])
        except requests.RequestException:
            log.exception("не смог удалить старый инстанс %s", old["id"])

    state = load_state(s.vultr_state_file)
    state.update({
        "current_ip": new_ip,
        "fail_count": 0,
        "total_recreates": state.get("total_recreates", 0) + 1,
        "last_recreate": datetime.now().isoformat(timespec="seconds"),
    })
    save_state(s.vultr_state_file, state)

    links = collect_links(s, users, new_ip)
    print(f"\n{'=' * 60}\n  Новый IP: {new_ip}\n{'=' * 60}")
    for lk in links:
        print(f"\n  {lk['name']}:\n  Home: {lk['home']}\n  CDN:  {lk['cdn']}")

    tg_lines = [f"✅ Сервер пересоздан\nIP: <code>{new_ip}</code>\n"]
    for lk in links:
        tg_lines.append(f"<b>{lk['name']}</b>\n<code>{lk['home']}</code>")
    send_telegram(s, "\n".join(tg_lines))
    log.info("=== DONE ===")


def monitor(s: Settings) -> None:
    log.info("=== MONITOR ===")
    state = load_state(s.vultr_state_file)
    server = find_server(s)
    if not server:
        log.error("сервер %s не найден в Vultr", s.server_label)
        return
    state["current_ip"] = server.get("main_ip")
    save_state(s.vultr_state_file, state)
    log.info("current ip: %s", state["current_ip"])

    while True:
        time.sleep(s.check_interval)
        ip = state["current_ip"]
        available = check_port(ip, 443, timeout=10) if ip else False
        state["last_check"] = datetime.now().isoformat(timespec="seconds")

        if available:
            if state.get("fail_count", 0) > 0:
                log.info("server back online")
                state["fail_count"] = 0
                save_state(s.vultr_state_file, state)
            continue

        state["fail_count"] = state.get("fail_count", 0) + 1
        save_state(s.vultr_state_file, state)
        log.warning("unreachable (%d/%d)", state["fail_count"], s.fail_threshold)

        if state["fail_count"] >= s.fail_threshold:
            send_telegram(
                s,
                f"⚠️ IP <code>{ip}</code> недоступен "
                f"{s.fail_threshold} проверок. Пересоздаю…",
            )
            try:
                recreate(s)
            except Exception:  # noqa: BLE001
                log.exception("recreate failed")
                send_telegram(s, "❌ Пересоздание упало — см. логи")
            state = load_state(s.vultr_state_file)


def status(s: Settings) -> None:
    server = find_server(s)
    state = load_state(s.vultr_state_file)
    if not server:
        print("Сервер не найден.")
        return
    ip = server.get("main_ip", "?")
    available = check_port(ip, 443, timeout=10)
    print(f"Сервер:      {server['label']}")
    print(f"IP:          {ip}")
    print(f"Статус:      {server.get('status', '?')}")
    print(f"Порт 443:    {'доступен' if available else 'НЕДОСТУПЕН'}")
    print(f"Пересозданий:{state.get('total_recreates', 0)}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if len(sys.argv) < 2:
        print("Usage: vultr_manager.py {monitor|recreate|status}")
        sys.exit(1)
    s = load()
    if not s.vultr_api_key:
        log.error("VULTR_API_KEY пустой, проверь %s", s.env_file)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "monitor":
        monitor(s)
    elif cmd == "recreate":
        recreate(s)
    elif cmd == "status":
        status(s)
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
