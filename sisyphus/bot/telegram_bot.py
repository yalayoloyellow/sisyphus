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
            text = _format_my_message(username)
            text = f"@{username} {text}"
            success = send_message_safe(token, chat_id, text)
            time.sleep(4)
            if success:
                sent += 1
                print(f"[BOT] notify sent to {username}")
            else:
                pending = settings.setdefault("pending_notifications", [])
                pending.append({"chat_id": chat_id, "text": text, "time": datetime.now().isoformat()})
                save_settings(settings)
    return f"Принудительная рассылка выполнена для {sent} получателей."
