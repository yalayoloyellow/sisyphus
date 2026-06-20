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
from ..core.logic import get_user_tasks_across_projects, format_user_tasks_markdown

def _format_my_message(username: str) -> str:
    """Возвращает Rich Markdown (тот же формат, что в терминале)."""
    tasks_by_project = get_user_tasks_across_projects(username)
    return format_user_tasks_markdown(tasks_by_project)


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


def send_rich_message_safe(token: str, chat_id: int, md_text: str) -> bool:
    """
    Отправка через новый Rich Messages API (Bot API 10.1+).
    Используем bot.do_api_request — это рекомендуемый способ для новых методов,
    которые ещё не завернуты в библиотеку python-telegram-bot.
    """
    if not TELEGRAM_AVAILABLE or not md_text:
        return False
    for attempt in range(3):
        try:
            bot = Bot(token)
            payload = {
                "chat_id": chat_id,
                "rich_message": {
                    "markdown": md_text
                }
            }
            # do_api_request возвращает coroutine в современных версиях
            coro = bot.do_api_request("sendRichMessage", api_kwargs=payload)
            try:
                asyncio.run(coro)
            except RuntimeError:
                # внутри уже запущенного loop
                asyncio.get_event_loop().create_task(coro)
            return True
        except (TimedOut, NetworkError):
            if attempt < 2:
                time.sleep(4)
                continue
            print(f"[BOT] rich send failed to {chat_id} after 3 attempts (network)")
            return False
        except Exception as e:
            # Метод не поддерживается сервером, плохой markdown, нет прав и т.д.
            print(f"[BOT] rich send failed to {chat_id}: {e}")
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
            # Отделяем упоминание пользователя от rich-контента, чтобы заголовки (#) парсились правильно
            full = f"@{username}\n\n{body}"
            # Rich Messages поддерживают до ~32k. Используем больший лимит.
            parts = _split_text(full, 30000)
            chat_ok = True
            for idx, part in enumerate(parts):
                # Сначала пытаемся rich
                ok = send_rich_message_safe(token, chat_id, part)
                if not ok:
                    # Fallback на старый plain
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
