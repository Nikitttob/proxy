"""Загрузка конфигурации из окружения / .env-файла.

Все параметры централизованы здесь, чтобы секреты не попадали в код.
"""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv — опциональная зависимость на проде
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


def _env(key: str, default: str = "") -> str:
    val = os.environ.get(key, default)
    return val.strip() if val else default


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = _env(key, "1" if default else "0").lower()
    return val in ("1", "true", "yes", "on")


def _env_list(key: str, sep: str = ",") -> List[str]:
    raw = _env(key, "")
    return [p.strip() for p in raw.split(sep) if p.strip()]


@dataclass(frozen=True)
class Settings:
    # Xray
    xray_private_key: str
    xray_public_key: str
    xray_sni: str
    xray_fingerprint: str
    xray_default_short_ids: List[str]

    # Server
    server_ip: str
    server_label: str
    cdn_domain: str
    cdn_local_port: int
    cdn_ws_path: str
    reality_port: int = 443
    cdn_public_port: int = 443
    cdn_origin_port: int = 8443

    # Telegram bot
    bot_token: str = ""
    admin_ids: List[int] = None  # type: ignore
    check_interval: int = 300
    fail_threshold: int = 3
    alert_cooldown: int = 3600
    monitor_enabled: bool = True

    # Vultr
    vultr_api_key: str = ""
    server_region: str = "waw"
    server_plan: str = "vc2-1c-1gb"
    server_os_id: int = 2284
    ssh_public_key: str = ""

    # Cloudflare
    cloudflare_api_token: str = ""
    cloudflare_zone_id: str = ""
    dns_record_name: str = ""

    # Notifications for manager
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Paths
    users_db: Path = Path("/usr/local/etc/xray/users.json")
    xray_config: Path = Path("/usr/local/etc/xray/config.json")
    vultr_state_file: Path = Path("/var/lib/xray-proxy/vultr_state.json")
    env_file: Path = Path("/etc/xray-proxy/env")


def load(env_path: str | None = None) -> Settings:
    """Загрузить настройки. `env_path` — путь к .env, иначе смотрим стандартные."""
    candidates = [env_path] if env_path else [
        os.environ.get("XRAY_PROXY_ENV"),
        "/etc/xray-proxy/env",
        str(Path(__file__).resolve().parent.parent / ".env"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            load_dotenv(c, override=False)
            break

    admin_ids = [int(x) for x in _env_list("ADMIN_IDS") if x.isdigit()]

    return Settings(
        xray_private_key=_env("XRAY_PRIVATE_KEY"),
        xray_public_key=_env("XRAY_PUBLIC_KEY"),
        xray_sni=_env("XRAY_SNI", "gateway.icloud.com"),
        xray_fingerprint=_env("XRAY_FINGERPRINT", "chrome"),
        xray_default_short_ids=_env_list("XRAY_DEFAULT_SHORT_IDS") or [""],
        server_ip=_env("SERVER_IP", "0.0.0.0"),
        server_label=_env("SERVER_LABEL", "xray-proxy"),
        cdn_domain=_env("CDN_DOMAIN"),
        cdn_local_port=_env_int("CDN_LOCAL_PORT", 8080),
        cdn_origin_port=_env_int("CDN_ORIGIN_PORT", 8443),
        cdn_ws_path=_env("CDN_WS_PATH", "/stream"),
        bot_token=_env("BOT_TOKEN"),
        admin_ids=admin_ids,
        check_interval=_env_int("CHECK_INTERVAL", 300),
        fail_threshold=_env_int("FAIL_THRESHOLD", 3),
        alert_cooldown=_env_int("ALERT_COOLDOWN", 3600),
        monitor_enabled=_env_bool("MONITOR_ENABLED", True),
        vultr_api_key=_env("VULTR_API_KEY"),
        server_region=_env("SERVER_REGION", "waw"),
        server_plan=_env("SERVER_PLAN", "vc2-1c-1gb"),
        server_os_id=_env_int("SERVER_OS_ID", 2284),
        ssh_public_key=_env("SSH_PUBLIC_KEY"),
        cloudflare_api_token=_env("CLOUDFLARE_API_TOKEN"),
        cloudflare_zone_id=_env("CLOUDFLARE_ZONE_ID"),
        dns_record_name=_env("DNS_RECORD_NAME"),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
        users_db=Path(_env("USERS_DB", "/usr/local/etc/xray/users.json")),
        xray_config=Path(_env("XRAY_CONFIG", "/usr/local/etc/xray/config.json")),
        vultr_state_file=Path(
            _env("VULTR_STATE_FILE", "/var/lib/xray-proxy/vultr_state.json")
        ),
        env_file=Path(_env("XRAY_PROXY_ENV", "/etc/xray-proxy/env")),
    )


@contextmanager
def _flock(path: Path):
    """Файловая блокировка через отдельный lock-файл (живёт рядом с .env)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def update_env_file(path: Path, updates: dict) -> None:
    """Обновить ключи в .env-файле, сохранив остальное.

    Атомарно (через tmp + replace) и под эксклюзивной блокировкой —
    бот и менеджер могут писать одновременно.
    """
    with _flock(path):
        if not path.exists():
            path.write_text("")

        lines = path.read_text().splitlines()
        seen: set = set()
        out = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                out.append(line)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                out.append(line)

        for key, val in updates.items():
            if key not in seen:
                out.append(f"{key}={val}")

        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("\n".join(out) + "\n")
        tmp.replace(path)
