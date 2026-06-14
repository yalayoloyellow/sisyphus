"""
cli/repl.py

REPL, основной цикл, help, bare input + dispatch команд.

Нумерация: всегда берём свежий view из core перед командами, которые используют номера.
"""

from __future__ import annotations
import sys

# Ленивый импорт prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
except ImportError:
    PromptSession = None
    FileHistory = None

from ..core.app import CoreApp
from ..core.data import DATA_DIR, list_projects, create_project, delete_project, load_last
from ..core.logic import fmt_entry

from .commands import handle_command

HELP_TEXT = """/h                  — эта справка
/m [имя]            — список проектов / открыть проект
/p имя              — создать проект
/p- имя             — удалить проект
/rename имя         — переименовать текущий проект
/del N [N2..]       — удалить запись(и)
/done N [N2..]      — отметить выполненным
/done               — архив выполненных
/e N текст          — редактировать запись
/u                  — undo
/r                  — redo
/notify             — принудительная рассылка сейчас
/tasks @username    — все открытые задачи человека по всем проектам
/q                  — выход
"""

def print_help():
    print(HELP_TEXT)

def main(argv: list[str] | None = None):
    """Главная точка входа для CLI."""
    if argv is None:
        argv = sys.argv[1:]

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

    print("Sisyphus 1.0.4")
    print("Copyright (c) 2026 Шамаев Илья Сергеевич (Yala, @yalayoloyellow). Personal use only.")
    print(app.status())
    visible, number_map = app.get_numbered_view()
    _print_numbered(visible)  # простая печать секциями
    last_finance_map = None

    history_file = DATA_DIR / "history.txt"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(history_file)),
        # completer removed (minimal clean release 1.0.4, no completer.py)
    )

    last_projects = None

    while True:
        try:
            raw = session.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not raw:
            print()
            print(app.status())
            visible, number_map = app.get_numbered_view()
            _print_numbered(visible)
            last_projects = None
            continue

        if not raw.startswith("/"):
            stripped = raw.strip()
            if last_projects:
                if stripped.isdigit():
                    n = int(stripped)
                    if 1 <= n <= len(last_projects):
                        app.load(last_projects[n-1]["dir"])
                        last_projects = None
                        print()
                        print(app.status())
                        visible, number_map = app.get_numbered_view()
                        _print_numbered(visible)
                        continue
                    last_projects = None
                    print()
                    print("Проект не найден.")
                    continue
                last_projects = None
            e = app.add_bare(raw)
            if e:
                print()
                print(f"Добавлено: {fmt_entry(e)}")
                print(app.status())
                visible, number_map = app.get_numbered_view()
                _print_numbered(visible)
            else:
                print()
                print("Не удалось распознать запись (только @username текст).")
            continue

        cmdline = raw[1:].strip()
        if not cmdline:
            print()
            print_help()
            last_projects = None
            continue

        parts = cmdline.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("h", "help", "?"):
            print()
            print_help()
            last_projects = None
            continue

        if cmd in ("del", "done", "e"):
            visible, number_map = app.get_numbered_view()

        result = handle_command(app, cmd, arg, number_map)
        if result == "quit":
            break
        if result:
            print()
            print(result)
            if cmd == "m" and not arg:
                last_projects = list_projects()

        if cmd in ("del", "done", "u", "r", "e") or (cmd in ("p", "p-", "m", "rename") and arg):
            print()
            print(app.status())
            visible, number_map = app.get_numbered_view()
            _print_numbered(visible)

        if not (cmd == "m" and not arg):
            last_projects = None


def _print_numbered(visible):
    if not visible:
        print("Нет активных записей.")
        return
    for i, e in enumerate(visible, 1):
        print(f"{i}. {fmt_entry(e)}")


if __name__ == "__main__":
    main()
