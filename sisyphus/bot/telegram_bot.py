"""
bot/telegram_bot.py
"""

from __future__ import annotations
import asyncio
import logging
import threading
import time
from datetime import datetime

TELEGRAM_AVAILABLE = False
try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, ContextTypes, filters
    )
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


def _save_chat_id_for_user(username: str, chat_id: int):
    if not username or not chat_id:
        return
    settings = load_settings()
    chats = settings.setdefault("chat_ids", {}).setdefault(username, [])
    if isinstance(chats, int):  # backward compat
        chats = [chats]
        settings["chat_ids"][username] = chats
    if chat_id not in chats:
        chats.append(chat_id)
    save_settings(settings)


async def _save_group_chat_on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_user.username:
        return
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    _save_chat_id_for_user(update.effective_user.username, update.effective_chat.id)


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


def _send_message(token: str, chat_id: int, text: str) -> bool:
    # Оставлено для совместимости (используется в _process_pending и т.д.)
    return send_message_safe(token, chat_id, text)

def _process_pending(token: str, settings: dict) -> None:
    pending = settings.get("pending_notifications", [])
    if not pending:
        return
    still_pending = []
    for item in pending:
        chat_id = item.get("chat_id")
        text = item.get("text", "")
        if chat_id and _send_message(token, chat_id, text):
            print(f"[BOT] sent pending to {chat_id}")
        else:
            still_pending.append(item)
    settings["pending_notifications"] = still_pending
    save_settings(settings)

def _should_notify(now: datetime, notify: dict) -> bool:
    if not notify:
        return False
    ntype = notify.get("type")
    ntime = notify.get("time", "09:00")
    try:
        nhour, nmin = map(int, ntime.split(":"))
    except:
        return False
    if now.hour != nhour or now.minute != nmin:
        return False
    if ntype == "daily":
        return True
    elif ntype == "weekdays":
        return now.weekday() < 5
    elif ntype == "weekly":
        day = notify.get("day", "mon").lower()[:3]
        days = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        return now.weekday() == days.get(day, 0)
    return False

def _start_scheduler(token: str):
    def worker():
        while True:
            try:
                settings = load_settings()
                if not settings.get("bot_token"):
                    time.sleep(60)
                    continue
                notify = settings.get("notify")
                now = datetime.now()
                if _should_notify(now, notify):
                    chat_ids = settings.get("chat_ids", {})
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
                                print(f"[BOT] scheduled sent to {username}")
                            else:
                                pending = settings.setdefault("pending_notifications", [])
                                pending.append({"chat_id": chat_id, "text": text, "time": now.isoformat()})
                                save_settings(settings)
                time.sleep(60)
            except Exception as e:
                print(f"[BOT] scheduler error: {e}")
                time.sleep(60)
    threading.Thread(target=worker, daemon=True).start()

async def run_bot(quiet: bool = False, stop_signals=None):
    settings = load_settings()
    token = settings.get("bot_token")
    if not token or not TELEGRAM_AVAILABLE:
        print("Бот не настроен или библиотека python-telegram-bot не установлена.")
        return

    # При старте: обработать пропущенные
    _process_pending(token, settings)

    # Всегда запускаем поток планировщика (он сам проверяет notify каждые 60с и подхватит изменения)
    _start_scheduler(token)

    async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username
        if not username:
            await update.message.reply_text("У вас нет username в Telegram.")
            return

        # Сохраняем chat_id для рассылок (личка + группы)
        _save_chat_id_for_user(username, update.effective_chat.id)

        text = _format_my_message(username)
        # В группах добавляем упоминание @username для стабильности и соответствия ТЗ
        if update.effective_chat.type in ("group", "supergroup"):
            text = f"@{username} {text}"
        await update.message.reply_text(text)

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("my", my_command))
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, _save_group_chat_on_message))

    async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Логируем ошибку минимально, но не падаем и не спамим traceback в консоль
        error = context.error
        if isinstance(error, (TimedOut, NetworkError)):
            print(f"[BOT] network error (handled): {type(error).__name__}")
            return
        print(f"[BOT] error: {error}")

    application.add_error_handler(_error_handler)

    if not quiet:
        print("Telegram бот запущен. Ctrl+C для остановки.")

    # Запуск на существующем loop (чтобы работало из любого потока через asyncio.run / run_until_complete).
    # stop_signals обрабатывается только в высокоуровневом run_polling; здесь сигналы не ставим (как и раньше при None).
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()


def force_notify():
    """Принудительная рассылка (из CLI). Не влияет на плановый планировщик."""
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
                print(f"[BOT] forcenotify sent to {username}")
            else:
                pending = settings.setdefault("pending_notifications", [])
                pending.append({"chat_id": chat_id, "text": text, "time": datetime.now().isoformat()})
                save_settings(settings)
    return f"Принудительная рассылка выполнена для {sent} получателей."
