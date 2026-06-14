"""
cli/repl.py

REPL, основной цикл, help, bare input + dispatch команд.

Нумерация: всегда берём свежий view из core перед командами, которые используют номера.
"""

from __future__ import annotations
import sys
import shutil

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

try:
    from rich.console import Console
    from rich.padding import Padding
    _console = Console()
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False
    _console = None

def app_print(text=""):
    """Simple centered output in middle ~2/3 of screen, left-aligned text.
    Uses rich for better rendering if available. No colors at all (plain).
    """
    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 80
    content_w = max(30, min(100, int(width * 2 / 3)))
    left = (width - content_w) // 2
    if _HAS_RICH:
        indented = Padding(str(text) if not isinstance(text, str) else text, (0, 0, 0, left))
        _console.print(indented, width=width)
    else:
        if isinstance(text, str):
            for line in (text.splitlines() or [""]):
                print(" " * left + line)
        else:
            print(" " * left + str(text))

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
    app_print(HELP_TEXT)

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

    app_print("Sisyphus 1.0.4.2")
    app_print("Copyright (c) 2026 Шамаев Илья Сергеевич (Yala, @yalayoloyellow). Personal use only.")
    app_print(app.status())
    visible, number_map = app.get_numbered_view()
    _print_numbered(visible)  # простая печать секциями
    last_finance_map = None

    history_file = DATA_DIR / "history.txt"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(history_file)),
        # completer removed (minimal clean release 1.0.4.2, no completer.py)
    )

    last_projects = None

    while True:
        try:
            # pad prompt to middle band; prefer rich input if available (for beautiful wrapper)
            try:
                w = shutil.get_terminal_size().columns
            except:
                w = 80
            cw = max(30, min(100, int(w * 2 / 3)))
            l = (w - cw) // 2
            prompt_str = " " * l + "> "
            if _HAS_RICH:
                raw = _console.input(prompt_str).strip()
            else:
                raw = session.prompt(prompt_str).strip()
        except (EOFError, KeyboardInterrupt):
            app_print("\nВыход.")
            break

        if not raw:
            app_print()
            app_print(app.status())
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
                        app_print()
                        app_print(app.status())
                        visible, number_map = app.get_numbered_view()
                        _print_numbered(visible)
                        continue
                    last_projects = None
                    app_print()
                    app_print("Проект не найден.")
                    continue
                last_projects = None
            e = app.add_bare(raw)
            if e:
                app_print()
                app_print(f"Добавлено: {fmt_entry(e)}")
                app_print(app.status())
                visible, number_map = app.get_numbered_view()
                _print_numbered(visible)
            else:
                app_print()
                app_print("Не удалось распознать запись (только @username текст).")
            continue

        cmdline = raw[1:].strip()
        if not cmdline:
            app_print()
            print_help()
            last_projects = None
            continue

        parts = cmdline.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("h", "help", "?"):
            app_print()
            print_help()
            last_projects = None
            continue

        if cmd in ("del", "done", "e"):
            visible, number_map = app.get_numbered_view()

        result = handle_command(app, cmd, arg, number_map)
        if result == "quit":
            break
        if result:
            app_print()
            app_print(result)
            if cmd == "m" and not arg:
                last_projects = list_projects()

        if cmd in ("del", "done", "u", "r", "e") or (cmd in ("p", "p-", "m", "rename") and arg):
            app_print()
            app_print(app.status())
            visible, number_map = app.get_numbered_view()
            _print_numbered(visible)

        if not (cmd == "m" and not arg):
            last_projects = None


def _print_numbered(visible):
    if not visible:
        app_print("Нет активных записей.")
        return
    for i, e in enumerate(visible, 1):
        app_print(f"{i}. {fmt_entry(e)}")


if __name__ == "__main__":
    main()
