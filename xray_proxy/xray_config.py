"""Единый источник истины для генерации конфига Xray.

Используется и ботом (`update_xray_config`), и менеджером VPS (cloud-init).
"""
from __future__ import annotations

import json
from typing import Iterable, List

from .config import Settings


def build_config(
    settings: Settings,
    users: Iterable[dict],
) -> dict:
    """Собрать dict конфига Xray для двух inbound-ов (Reality + WS).

    `users` — итерируемое из dict со ключами: `uuid`, опционально `short_id`.
    """
    users_list = list(users)

    reality_clients = [
        {"id": u["uuid"], "flow": "xtls-rprx-vision"} for u in users_list
    ]
    ws_clients = [{"id": u["uuid"]} for u in users_list]

    # Собираем уникальные shortIds: пустая строка + per-user.
    short_ids: List[str] = [""]
    for u in users_list:
        sid = u.get("short_id")
        if sid and sid not in short_ids:
            short_ids.append(sid)
    for sid in settings.xray_default_short_ids:
        if sid not in short_ids:
            short_ids.append(sid)

    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "listen": "0.0.0.0",
                "port": settings.reality_port,
                "protocol": "vless",
                "settings": {
                    "clients": reality_clients,
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{settings.xray_sni}:443",
                        "xver": 0,
                        "serverNames": [settings.xray_sni],
                        "privateKey": settings.xray_private_key,
                        "shortIds": short_ids,
                    },
                },
                # destOverride без "quic" — TCP-inbound не видит QUIC.
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"],
                },
            },
            {
                # Локальный loopback — WS терминируется Caddy с настоящим TLS.
                "listen": "127.0.0.1",
                "port": settings.cdn_local_port,
                "protocol": "vless",
                "settings": {
                    "clients": ws_clients,
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {"path": settings.cdn_ws_path},
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"],
                },
            },
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
    }


def dump(config: dict) -> str:
    return json.dumps(config, indent=2, ensure_ascii=False)
