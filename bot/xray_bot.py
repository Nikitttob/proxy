#!/usr/bin/env python3
"""Telegram-бот для управления Xray VLESS+Reality + CDN.

Все исправления по ревью учтены:
- секреты из .env, не хардкод
- persist /updateip в .env + рестарт
- /bind /unbind команды для привязки Telegram-ID
- HTML parse_mode (безопасно для спецсимволов)
- rollback конфига через `xray run -test`
- cooldown алертов монитора
- fcntl-локи на users.json
- per-user shortId
- конкретные except-ы, logging в journald
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Позволяем запуск без установки пакета.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from xray_proxy import userdb
from xray_proxy.config import Settings, load, update_env_file
from xray_proxy.links import cdn_link, home_link
from xray_proxy.net import check_port
from xray_proxy.xray_config import build_config, dump

log = logging.getLogger("xray_bot")


# ---------------------------------------------------------------------------
#  Работа с конфигом Xray (с rollback-ом)
# ---------------------------------------------------------------------------

def update_xray_config(settings: Settings, users: Dict[str, dict]) -> tuple[bool, str]:
    """Записать новый конфиг с проверкой. Возвращает (ok, сообщение об ошибке)."""
    cfg = build_config(settings, users.values())
    target = settings.xray_config
    new_path = target.with_suffix(target.suffix + ".new")
    backup_path = target.with_suffix(target.suffix + ".bak")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(dump(cfg))

        # xray run -test валидирует конфиг и выходит.
        check = subprocess.run(
            ["xray", "run", "-test", "-c", str(new_path)],
            capture_output=True, text=True, timeout=30,
        )
        if check.returncode != 0:
            log.error("xray config test failed: %s", check.stderr)
            new_path.unlink(missing_ok=True)
            return False, f"xray -test: {check.stderr.strip()[:500]}"

        if target.exists():
            target.replace(backup_path)
        new_path.replace(target)

        restart = subprocess.run(
            ["systemctl", "reload-or-restart", "xray"],
            capture_output=True, text=True, timeout=30,
        )
        if restart.returncode != 0:
            # Откат.
            if backup_path.exists():
                backup_path.replace(target)
                subprocess.run(["systemctl", "restart", "xray"], timeout=30)
            log.error("systemctl restart failed: %s", restart.stderr)
            return False, f"systemctl: {restart.stderr.strip()[:500]}"
        return True, ""
    except (OSError, subprocess.SubprocessError) as e:
        log.exception("update_xray_config failed")
        new_path.unlink(missing_ok=True)
        return False, f"{type(e).__name__}: {e}"


def xray_is_active() -> bool:
    r = subprocess.run(
        ["systemctl", "is-active", "xray"],
        capture_output=True, text=True, timeout=10,
    )
    return r.stdout.strip() == "active"


# ---------------------------------------------------------------------------
#  Форматирование ответа
# ---------------------------------------------------------------------------

def _fmt_keys(settings: Settings, data: dict) -> str:
    sid = userdb.ensure_short_id(data)
    home = home_link(settings, data["uuid"], data["name"], sid)
    cdn = cdn_link(settings, data["uuid"], data["name"])
    name_html = html.escape(data["name"])
    return (
        f"🔑 Ключи для <b>{name_html}</b>:\n\n"
        f"🏠 Home:\n<code>{html.escape(home)}</code>\n\n"
        f"🏢 CDN:\n<code>{html.escape(cdn)}</code>"
    )


# ---------------------------------------------------------------------------
#  Мониторинг IP с cooldown
# ---------------------------------------------------------------------------

class Monitor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fail_count = 0
        self.last_alert_ts: float = 0.0

    async def run(self, app: Application) -> None:
        while True:
            await asyncio.sleep(self.settings.check_interval)
            try:
                available = check_port(self.settings.server_ip, 443)
            except Exception:  # noqa: BLE001 — хотим продолжать цикл
                log.exception("port check failed")
                continue

            if available:
                if self.fail_count > 0:
                    log.info("server back online")
                self.fail_count = 0
                continue

            self.fail_count += 1
            log.warning("server unreachable (%d)", self.fail_count)
            if self.fail_count < self.settings.fail_threshold:
                continue

            now = time.time()
            if now - self.last_alert_ts < self.settings.alert_cooldown:
                continue
            self.last_alert_ts = now

            msg = (
                f"⚠️ Сервер {self.settings.server_ip} недоступен "
                f"{self.fail_count} проверок подряд. CDN-ссылки работают."
            )
            for admin_id in self.settings.admin_ids:
                try:
                    await app.bot.send_message(admin_id, msg)
                except TelegramError:
                    log.exception("failed to alert admin %s", admin_id)


# ---------------------------------------------------------------------------
#  Команды
# ---------------------------------------------------------------------------

def is_admin(settings: Settings, user_id: int) -> bool:
    return user_id in settings.admin_ids


def _get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    user = update.effective_user
    if is_admin(settings, user.id):
        text = (
            f"Привет, {html.escape(user.first_name or '')}! Ты админ.\n\n"
            "<b>Команды:</b>\n"
            "/add имя — добавить пользователя\n"
            "/remove номер — удалить пользователя\n"
            "/list — список\n"
            "/key номер — показать ключи\n"
            "/bind номер tg_id — привязать Telegram-ID\n"
            "/unbind номер — отвязать\n"
            "/status — статус сервера\n"
            "/updateip IP — сменить IP сервера\n"
            "/help — подсказка"
        )
    else:
        text = (
            f"Привет, {html.escape(user.first_name or '')}!\n"
            "/mykey — получить ключи подключения."
        )
    await update.message.reply_html(text)


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        await update.message.reply_text("⛔ Только для админов.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /add Имя")
        return

    name = " ".join(context.args)
    users = userdb.load_users(settings.users_db)
    new_id = str(max((int(k) for k in users.keys()), default=0) + 1)
    new_uuid = str(uuid.uuid4())
    users[new_id] = {
        "name": name,
        "uuid": new_uuid,
        "created": datetime.now().isoformat(timespec="seconds"),
        "telegram_id": None,
    }
    userdb.ensure_short_id(users[new_id])
    userdb.save_users(settings.users_db, users)

    ok, err = update_xray_config(settings, users)
    if not ok:
        await update.message.reply_html(
            f"❌ Ошибка применения конфига:\n<code>{html.escape(err)}</code>"
        )
        return

    await update.message.reply_html(
        f"✅ Пользователь #{new_id} (<b>{html.escape(name)}</b>) добавлен.\n\n"
        + _fmt_keys(settings, users[new_id])
    )


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Использование: /remove номер")
        return

    user_id = context.args[0]
    users = userdb.load_users(settings.users_db)
    if user_id not in users:
        await update.message.reply_text(f"❌ Пользователь #{user_id} не найден.")
        return

    name = users[user_id]["name"]
    del users[user_id]
    userdb.save_users(settings.users_db, users)

    ok, err = update_xray_config(settings, users)
    if not ok:
        await update.message.reply_html(
            f"⚠️ Удалён из БД, но конфиг не обновился:\n<code>{html.escape(err)}</code>"
        )
        return
    await update.message.reply_html(
        f"✅ Пользователь #{user_id} (<b>{html.escape(name)}</b>) удалён."
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    users = userdb.load_users(settings.users_db)
    if not users:
        await update.message.reply_text("Список пуст.")
        return
    lines = ["<b>👥 Пользователи:</b>"]
    for uid, data in sorted(users.items(), key=lambda kv: int(kv[0])):
        bound = "✅" if data.get("telegram_id") else "—"
        created = (data.get("created") or "")[:10]
        lines.append(
            f"#{uid} — <b>{html.escape(data['name'])}</b> "
            f"({created}) bind:{bound}"
        )
    await update.message.reply_html("\n".join(lines))


async def cmd_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Использование: /key номер")
        return
    user_id = context.args[0]
    users = userdb.load_users(settings.users_db)
    if user_id not in users:
        await update.message.reply_text(f"❌ Пользователь #{user_id} не найден.")
        return
    # ensure_short_id может мутировать — сохраним при необходимости.
    before = users[user_id].get("short_id")
    reply = _fmt_keys(settings, users[user_id])
    if users[user_id].get("short_id") != before:
        userdb.save_users(settings.users_db, users)
    await update.message.reply_html(reply)


async def cmd_mykey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    tg_id = update.effective_user.id
    users = userdb.load_users(settings.users_db)
    for data in users.values():
        if data.get("telegram_id") == tg_id:
            await update.message.reply_html(_fmt_keys(settings, data))
            return
    await update.message.reply_text(
        "❌ Ты не привязан. Попроси админа: /bind <номер> " + str(tg_id)
    )


async def cmd_bind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    if len(context.args) != 2 or not context.args[1].lstrip("-").isdigit():
        await update.message.reply_text("Использование: /bind номер telegram_id")
        return
    user_id, tg_id = context.args[0], int(context.args[1])
    users = userdb.load_users(settings.users_db)
    if user_id not in users:
        await update.message.reply_text(f"❌ Пользователь #{user_id} не найден.")
        return
    users[user_id]["telegram_id"] = tg_id
    userdb.save_users(settings.users_db, users)
    await update.message.reply_text(
        f"✅ #{user_id} привязан к telegram_id={tg_id}"
    )


async def cmd_unbind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Использование: /unbind номер")
        return
    user_id = context.args[0]
    users = userdb.load_users(settings.users_db)
    if user_id not in users:
        return
    users[user_id]["telegram_id"] = None
    userdb.save_users(settings.users_db, users)
    await update.message.reply_text(f"✅ #{user_id} отвязан.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    xray_ok = xray_is_active()
    users = userdb.load_users(settings.users_db)
    reachable = check_port(settings.server_ip, 443)
    await update.message.reply_html(
        f"<b>📊 Статус</b>\n\n"
        f"IP: <code>{html.escape(settings.server_ip)}</code>\n"
        f"Xray: {'✅' if xray_ok else '❌'}\n"
        f"Порт 443: {'✅' if reachable else '❌'}\n"
        f"Пользователей: {len(users)}\n"
        f"Мониторинг: {'✅' if settings.monitor_enabled else '❌'}"
    )


async def cmd_updateip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сменить IP сервера — персистит в .env и перегенерирует конфиг."""
    settings = _get_settings(context)
    if not is_admin(settings, update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Использование: /updateip 1.2.3.4")
        return
    new_ip = context.args[0]

    update_env_file(settings.env_file, {"SERVER_IP": new_ip})
    # Перегружаем настройки из .env.
    new_settings = load(str(settings.env_file))
    context.application.bot_data["settings"] = new_settings

    users = userdb.load_users(new_settings.users_db)
    ok, err = update_xray_config(new_settings, users)
    if not ok:
        await update.message.reply_html(
            f"⚠️ IP обновлён, но конфиг не применился:\n"
            f"<code>{html.escape(err)}</code>"
        )
        return

    await update.message.reply_html(
        f"✅ IP обновлён на <code>{html.escape(new_ip)}</code>, "
        f"конфиг перезапущен.\n\n"
        "Отправляю новые home-ссылки привязанным пользователям."
    )

    sent = 0
    for data in users.values():
        tg = data.get("telegram_id")
        if not tg:
            continue
        try:
            await context.bot.send_message(
                tg,
                _fmt_keys(new_settings, data),
                parse_mode="HTML",
            )
            sent += 1
        except TelegramError:
            log.exception("failed to notify %s", tg)
    await update.message.reply_text(f"📨 Отправлено: {sent}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "<b>📖 Инструкция</b>\n\n"
        "<b>iPhone/iPad:</b> Streisand или V2BOX → + → Импорт из буфера\n"
        "<b>Android:</b> v2rayNG → + → Импорт из буфера\n"
        "<b>Windows/macOS:</b> Nekobox → Сервер → Добавить из буфера\n\n"
        "⚠️ Не работает Home? Попробуй CDN-ссылку."
    )
    await update.message.reply_html(text)


# ---------------------------------------------------------------------------
#  Запуск
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load()
    if not settings.bot_token:
        log.error("BOT_TOKEN is empty. Проверь %s", settings.env_file)
        sys.exit(1)
    if not settings.admin_ids:
        log.warning("ADMIN_IDS is empty — все админ-команды будут отклонены")

    async def post_init(app: Application) -> None:
        app.bot_data["settings"] = settings
        if settings.monitor_enabled:
            monitor = Monitor(settings)
            asyncio.create_task(monitor.run(app))

    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("key", cmd_key))
    app.add_handler(CommandHandler("link", cmd_key))
    app.add_handler(CommandHandler("mykey", cmd_mykey))
    app.add_handler(CommandHandler("bind", cmd_bind))
    app.add_handler(CommandHandler("unbind", cmd_unbind))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("updateip", cmd_updateip))

    log.info("xray-bot started")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
