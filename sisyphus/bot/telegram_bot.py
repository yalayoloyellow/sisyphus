"""
bot/telegram_bot.py

Minimal bot utilities for force_notify only.
All scheduled / registration / run_bot logic removed in Этап 1.
"""

from __future__ import annotations
import asyncio
import time
from datetime import datetime

TELEGRAM_AVAILABLE = False
try:
    from telegram import Bot
    from telegram.error import TimedOut, NetworkError
    TELEGRAM_AVAILABLE = True
except ImportError:
    pass

from ..core.data import load_settings, save_settings
from ..core.logic import get_user_tasks_across_projects

def _format_my_message(username: str) -> str:
    tasks_by_project = get_user_tasks_across_projects(username)
    if not tasks_by_project:
        return "У вас нет открытых задач ни в одном проекте."
    lines = []
    for proj_name, tasks in tasks_by_project.items():
        lines.append(proj_name)
        for t in tasks:
            lines.append(f"• {t.get('text')}")
    return "\n".join(lines)


def _has_open_tasks(username: str) -> bool:
    return bool(get_user_tasks_across_projects(username))


def _split_text(text: str, max_len: int = 3500) -> list[str]:
    """Умное, но очень простое разделение: пакуем по целым строкам (границы задач/проектов).

    Не режем посередине задачи. Если одна строка чудовищно длинная (>3500) — режем жёстко (защита).
    Используется только при отправке notify, чтобы не превышать лимит Telegram.
    """
    if not text or len(text) <= max_len:
        return [text] if text else [""]
    parts: list[str] = []
    current_lines: list[str] = []
    current_len = 0
    for line in text.splitlines(keepends=False):
        line_with_nl = line + "\n"
        line_len = len(line_with_nl)
        if current_lines and current_len + line_len > max_len:
            part = "".join(current_lines).rstrip("\n")
            parts.append(part)
            current_lines = [line_with_nl]
            current_len = line_len
        else:
            current_lines.append(line_with_nl)
            current_len += line_len
        # если даже текущая строка (задача) слишком большая — потом дорежем
    if current_lines:
        parts.append("".join(current_lines).rstrip("\n"))
    # пост-обработка: жёстко режем любые части, что всё ещё > max (монстр-строки)
    final: list[str] = []
    for p in parts:
        if len(p) <= max_len:
            final.append(p)
        else:
            for i in range(0, len(p), max_len):
                final.append(p[i : i + max_len])
    return final or [""]


def send_message_safe(token: str, chat_id: int, text: str) -> bool:
    """Надёжная отправка с 3 попытками при TimedOut/NetworkError (4 сек между попытками).
    Другие ошибки (BadRequest, Forbidden и т.д.) — сразу неудача, без повторов.
    """
    if not TELEGRAM_AVAILABLE:
        return False
    for attempt in range(3):
        try:
            bot = Bot(token)
            coro = bot.send_message(chat_id=chat_id, text=text)
            try:
                asyncio.run(coro)
            except RuntimeError:
                # Вызвано изнутри запущенного event loop (внутри процесса бота).
                # Fire-and-forget. Для массовых рассылок этот путь редкий.
                asyncio.get_event_loop().create_task(coro)
                return True
            return True
        except (TimedOut, NetworkError):
            if attempt < 2:
                time.sleep(4)
                continue
            print(f"[BOT] send failed to {chat_id} after 3 attempts")
            return False
        except Exception as e:
            # BadRequest, Forbidden, InvalidToken и другие — не повторяем
            print(f"[BOT] send failed to {chat_id}: {e}")
            return False
    return False

def force_notify():
    """Принудительная рассылка (из CLI, вызывается командой /notify)."""
    if not TELEGRAM_AVAILABLE:
        return "Бот не настроен (нет библиотеки python-telegram-bot)."
    settings = load_settings()
    token = settings.get("bot_token")
    if not token:
        return "Бот не настроен (нет токена)."
    chat_ids = settings.get("chat_ids", {})
    if not chat_ids:
        return "Нет получателей рассылки (пользователи должны написать /my боту)."
    sent = 0
    for username, chats in list(chat_ids.items()):
        if not _has_open_tasks(username):
            continue
        if isinstance(chats, int):
            chats = [chats]
        for chat_id in chats:
            body = _format_my_message(username)
            full = f"@{username} {body}"
            parts = _split_text(full, 3500)
            chat_ok = True
            for idx, part in enumerate(parts):
                ok = send_message_safe(token, chat_id, part)
                if not ok:
                    chat_ok = False
                    pending = settings.setdefault("pending_notifications", [])
                    pending.append({"chat_id": chat_id, "text": part, "time": datetime.now().isoformat()})
                    save_settings(settings)
                if idx < len(parts) - 1:
                    time.sleep(2)
            time.sleep(4)
            if chat_ok:
                sent += 1
                print(f"[BOT] notify sent to {username}")
    return f"Принудительная рассылка выполнена для {sent} получателей."
