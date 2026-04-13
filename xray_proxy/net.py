"""Сетевые проверки."""
from __future__ import annotations

import socket


def check_port(host: str, port: int, timeout: float = 10.0) -> bool:
    """True если TCP-порт открыт."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False
