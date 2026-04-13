"""Генерация vless-ссылок с корректным URL-кодированием."""
from __future__ import annotations

from urllib.parse import quote

from .config import Settings


def _frag(name: str) -> str:
    # Имена могут содержать пробелы и кириллицу — нужен URL-encode.
    return quote(name, safe="")


def home_link(settings: Settings, user_uuid: str, name: str, short_id: str) -> str:
    return (
        f"vless://{user_uuid}@{settings.server_ip}:{settings.reality_port}"
        f"?encryption=none&flow=xtls-rprx-vision"
        f"&security=reality&sni={settings.xray_sni}"
        f"&fp={settings.xray_fingerprint}"
        f"&pbk={settings.xray_public_key}"
        f"&sid={short_id}"
        f"&type=tcp#{_frag(name)}-home"
    )


def cdn_link(settings: Settings, user_uuid: str, name: str) -> str:
    return (
        f"vless://{user_uuid}@{settings.cdn_domain}:{settings.cdn_public_port}"
        f"?encryption=none&security=tls"
        f"&type=ws&path={quote(settings.cdn_ws_path, safe='')}"
        f"&host={settings.cdn_domain}#{_frag(name)}-cdn"
    )
