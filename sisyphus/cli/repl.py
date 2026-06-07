"""
cli/repl.py

REPL, основной цикл, help, bare input + dispatch команд.

Нумерация: всегда берём свежий view из core перед командами, которые используют номера.
"""

from __future__ import annotations
import sys
from typing import Optional

# Ленивый импорт prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
except ImportError:
    PromptSession = None
    FileHistory = None

from ..core.app import CoreApp
from ..core.data import DATA_DIR, list_projects, create_project, delete_project, load_last
from ..core.logic import fmt_entry, get_numbered_finances

from .completer import get_completer
from .commands import handle_command

HELP_TEXT = """Sisyphus 1.0.0 — минималистичный терминальный органайзер.

Основной ввод:
• обычный текст          → заметка
• @username текст        → задача
• +сумма текст / -сумма текст → финансы (текст-обоснование обязательно)

В главном списке показываются только заметки и задачи. Финансы — только сумма в шапке (полный список: /fin).

Нумерация глобальная (1, 2, 3…). Номера работают только после последнего вызова списка.

Команды:
/m [имя]        — список проектов / открыть проект
/p имя          — создать проект
/p- имя         — удалить проект (с подтверждением)
/rename имя     — переименовать текущий проект
/del N [N2..]   — удалить запись(и)
/done N [N2..]  — отметить выполненным (только заметки и задачи)
/done           — архив выполненных
/e N текст      — редактировать запись
/u              — undo
/r              — redo
/fin            — полный список финансов
/export         — экспорт в .xlsx (3 листа)
/dir            — открыть папку с данными
/h              — эта справка
/q              — выход

Бот и рассылка:
/bot token <токен>
/notify daily|weekdays|weekly <время> / /notify-
/forcenotify    — принудительная рассылка сейчас (в личку и группы)

Бот отвечает только на /my (твои задачи по всем проектам, в т.ч. из групп).

Нюансы:
• /del полностью удаляет запись (у финансов пересчитывается сумма).
• /done работает только с заметками и задачами.
• При /del и /done с несколькими номерами требуется подтверждение [y/N].
"""

def print_help():
    print(HELP_TEXT)

def main(argv: list[str] | None = None):
    """Главная точка входа для CLI и --bot."""
    if argv is None:
        argv = sys.argv[1:]

    if "--bot" in argv:
        from ..bot.telegram_bot import run_bot
        run_bot()
        return

    if "--test" in argv:
        from ..tests import run_all_tests
        run_all_tests()
        return

    # Автозапуск бота в фоне при наличии bot_token (daemon thread). Планировщик подхватит /notify позже.
    from ..core.data import load_settings
    settings = load_settings()
    if settings.get("bot_token"):
        from ..bot.telegram_bot import run_bot
        import asyncio
        import threading

        def _run_bot_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            run_bot(quiet=True, stop_signals=None)

        threading.Thread(target=_run_bot_in_thread, daemon=True).start()
        print("Бот запущен в фоне.")

    _run_cli_interactive()


def _run_cli_interactive():
    if PromptSession is None:
        print("ERROR: prompt_toolkit не установлен. pip install prompt_toolkit")
        return

    app = CoreApp()
    last = load_last()
    if last:
        try:
            app.load(last)
        except Exception:
            pass
    if not app.dir:
        projs = list_projects()
        if projs:
            app.load(projs[0]["dir"])
        else:
            d = create_project("main")
            app.load(d)

    print("Sisyphus 1.0.0")
    print("Copyright (c) 2026 Шамаев Илья Сергеевич (Yala, @yalayoloyellow). Personal use only.")
    print(app.status())
    visible, number_map = app.get_numbered_view()
    _print_numbered(visible)  # простая печать секциями
    last_finance_map = None

    history_file = DATA_DIR / "history.txt"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    completer = get_completer(app)
    session = PromptSession(
        history=FileHistory(str(history_file)),
        completer=completer,
    )

    last_projects = None
    last_finance_map = None

    while True:
        try:
            raw = session.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not raw:
            print(app.status())
            visible, number_map = app.get_numbered_view()
            _print_numbered(visible)
            last_projects = None
            last_finance_map = None
            continue

        if not raw.startswith("/"):
            stripped = raw.strip()
            if last_projects:
                if stripped.isdigit():
                    n = int(stripped)
                    if 1 <= n <= len(last_projects):
                        app.load(last_projects[n-1]["dir"])
                        last_projects = None
                        last_finance_map = None
                        print(app.status())
                        visible, number_map = app.get_numbered_view()
                        _print_numbered(visible)
                        continue
                    last_projects = None
                    last_finance_map = None
                    print("Проект не найден.")
                    continue
                last_projects = None
                last_finance_map = None
            e = app.add_bare(raw)
            if e:
                print(f"Добавлено: {fmt_entry(e)}")
                print(app.status())
                visible, number_map = app.get_numbered_view()
                _print_numbered(visible)
                last_finance_map = None
            else:
                print("Не удалось распознать запись (для финансов нужен текст после суммы).")
            continue

        cmdline = raw[1:].strip()
        if not cmdline:
            print_help()
            last_projects = None
            last_finance_map = None
            continue

        parts = cmdline.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("h", "help", "?"):
            print_help()
            last_projects = None
            last_finance_map = None
            continue

        if cmd == "del" and last_finance_map:
            number_map = last_finance_map
            last_finance_map = None
        elif cmd in ("del", "done", "e"):
            visible, number_map = app.get_numbered_view()
            last_finance_map = None

        result = handle_command(app, cmd, arg, number_map)
        if result == "quit":
            break
        if result:
            print(result)
            if cmd == "m" and not arg:
                last_projects = list_projects()
            if cmd == "fin":
                _, last_finance_map = get_numbered_finances(app.state)

        if cmd in ("del", "done", "u", "r", "e") or (cmd in ("p", "p-", "m", "rename") and arg):
            print(app.status())
            visible, number_map = app.get_numbered_view()
            _print_numbered(visible)
            last_finance_map = None

        if not (cmd == "m" and not arg):
            last_projects = None
        if cmd != "fin":
            last_finance_map = None


def _print_numbered(visible):
    if not visible:
        print("Нет активных записей.")
        return
    for i, e in enumerate(visible, 1):
        if i == 1 or visible[i-2].get("type") != e.get("type"):
            print("## Заметки" if e.get("type") == "note" else "## Задачи")
        print(f"{i}. {fmt_entry(e)}")


if __name__ == "__main__":
    main()
