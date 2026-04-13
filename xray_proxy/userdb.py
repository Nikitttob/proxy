"""БД пользователей (users.json) с файловой блокировкой и атомарной записью."""
from __future__ import annotations

import fcntl
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Dict


def _new_short_id() -> str:
    # 8 байт hex — такой же формат, как в оригинальной доке.
    return secrets.token_hex(8)


@contextmanager
def _locked(path: Path, mode: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode.startswith("r") and not path.exists():
        path.write_text("{}")
    f = open(path, mode)
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def load_users(path: Path) -> Dict[str, dict]:
    with _locked(path, "r") as f:
        data = f.read() or "{}"
    return json.loads(data)


def save_users(path: Path, users: Dict[str, dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Блокируем основной файл, пишем в tmp, атомарно переименовываем.
    with _locked(path, "a+") as _:
        tmp.write_text(json.dumps(users, indent=2, ensure_ascii=False))
        os.replace(tmp, path)


def ensure_short_id(user: dict) -> str:
    """Вернуть shortId пользователя, сгенерировав при отсутствии."""
    if not user.get("short_id"):
        user["short_id"] = _new_short_id()
    return user["short_id"]
