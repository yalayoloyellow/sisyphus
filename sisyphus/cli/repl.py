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
from ..core.logic import fmt_entry, superscript

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
    """Output in the 4:3 centered text area (as set by Ghostty config with large side padding).
    Use nearly full usable width so the text "window" fills the 4:3 visual box.
    Small fixed margins to avoid edge. Supports rich Text for colors.
    """
    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 80
    # For 4:3 visual provided by Ghostty (large padding-x), use almost full width
    # with small symmetric margins. This prevents further shifting/centering inside the area.
    content_w = max(30, min(200, width - 6))
    left = 3
    if _HAS_RICH:
        if not isinstance(text, str) and hasattr(text, "__rich_console__"):
            indented = Padding(text, (0, 0, 0, left))
            _console.print(indented, width=width)
        else:
            indented = Padding(str(text), (0, 0, 0, left))
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
    if _HAS_RICH:
        from rich.text import Text
        t = Text()
        for line in HELP_TEXT.splitlines(keepends=True):
            stripped = line.strip()
            if stripped.startswith("/"):
                # color the command part cyan
                if "—" in line:
                    cmd, desc = line.split("—", 1)
                    t.append(cmd, style="cyan")
                    t.append("—" + desc)
                else:
                    t.append(line, style="cyan")
            else:
                t.append(line)
        app_print(t)
    else:
        app_print(HELP_TEXT)


def _print_status(name: str, count: int):
    """Print project status with colors for 4:3 visual.
    Project name and task count in matching accent color (bright_cyan).
    """
    if not _HAS_RICH:
        app_print(f"Проект: {name}\tЗадачи: {count}")
        return
    from rich.text import Text
    t = Text()
    t.append("Проект: ", style="white")
    t.append(name, style="bold bright_cyan")
    t.append("\tЗадачи: ", style="white")
    t.append(str(count), style="bold bright_cyan")
    app_print(t)

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

    app_print("Sisyphus 1.1")
    app_print("Copyright (c) 2026 Шамаев Илья Сергеевич (Yala, @yalayoloyellow). Personal use only.")
    try:
        name = app.state.get("_meta", {}).get("display_name") or (app.dir or "проект")
        count = len([e for e in app.state.get("entries", []) if e.get("type") == "task" and not e.get("done", False)])
    except:
        name, count = "проект", 0
    _print_status(name, count)
    visible, number_map = app.get_numbered_view()
    _print_numbered(visible)
    last_finance_map = None

    history_file = DATA_DIR / "history.txt"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(history_file)),
        # completer removed (minimal clean release 1.1, no completer.py)
    )

    last_projects = None

    while True:
        try:
            # pad prompt to middle band; prefer rich input if available (for beautiful wrapper)
            try:
                w = shutil.get_terminal_size().columns
            except:
                w = 80
            # Match the 4:3 text area margins
            cw = max(30, min(200, w - 6))
            l = 3
            if _HAS_RICH:
                from rich.text import Text
                prompt_text = Text(" " * l + "> ", style="cyan")
                raw = _console.input(prompt_text).strip()
            else:
                prompt_str = " " * l + "> "
                raw = session.prompt(prompt_str).strip()
        except (EOFError, KeyboardInterrupt):
            app_print("\nВыход.")
            break

        if not raw:
            app_print()
            try:
                name = app.state.get("_meta", {}).get("display_name") or (app.dir or "проект")
                count = len([e for e in app.state.get("entries", []) if e.get("type") == "task" and not e.get("done", False)])
            except:
                name, count = "проект", 0
            _print_status(name, count)
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
                        try:
                            name = app.state.get("_meta", {}).get("display_name") or (app.dir or "проект")
                            count = len([e for e in app.state.get("entries", []) if e.get("type") == "task" and not e.get("done", False)])
                        except:
                            name, count = "проект", 0
                        _print_status(name, count)
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
                # colored feedback
                if _HAS_RICH:
                    from rich.text import Text
                    fb = Text()
                    fb.append("Добавлено: ", style="white")
                    fb.append(fmt_entry(e), style="bright_cyan")
                    app_print(fb)
                else:
                    app_print(f"Добавлено: {fmt_entry(e)}")
                try:
                    name = app.state.get("_meta", {}).get("display_name") or (app.dir or "проект")
                    count = len([e for e in app.state.get("entries", []) if e.get("type") == "task" and not e.get("done", False)])
                except:
                    name, count = "проект", 0
                _print_status(name, count)
                visible, number_map = app.get_numbered_view()
                _print_numbered(visible)
            else:
                app_print()
                if _HAS_RICH:
                    from rich.text import Text
                    t = Text()
                    t.append("Не удалось распознать запись (только ")
                    t.append("@username", style="cyan")
                    t.append(" текст).")
                    app_print(t)
                else:
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
            if cmd == "tasks" and _HAS_RICH:
                from rich.text import Text
                t = Text()
                try:
                    w = shutil.get_terminal_size().columns
                except:
                    w = 80
                content_w = max(30, min(200, w - 6))
                for line in result.splitlines(keepends=False):
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        proj = stripped[2:]
                        # centered underlined cyan like rich markdown header
                        header = Text(proj, style="bold cyan underline")
                        # pad to center within the content area
                        pad = (content_w - len(proj)) // 2
                        if pad > 0:
                            header = Text(" " * pad) + header + Text(" " * (content_w - len(proj) - pad))
                        t.append(header)
                        t.append("\n\n")
                    elif stripped.startswith("- "):
                        t.append("• " + stripped[2:] + "\n")
                    elif stripped:
                        t.append(line + "\n")
                    else:
                        t.append("\n")
                app_print(t)
            else:
                app_print(result)
            if cmd == "m" and not arg:
                last_projects = list_projects()

        if cmd in ("del", "done", "u", "r", "e") or (cmd in ("p", "p-", "m", "rename") and arg):
            app_print()
            try:
                name = app.state.get("_meta", {}).get("display_name") or (app.dir or "проект")
                count = len([e for e in app.state.get("entries", []) if e.get("type") == "task" and not e.get("done", False)])
            except:
                name, count = "проект", 0
            _print_status(name, count)
            visible, number_map = app.get_numbered_view()
            _print_numbered(visible)

        if not (cmd == "m" and not arg):
            last_projects = None


def _print_numbered(visible):
    """Основной вид списка задач текущего проекта.
    Номера без точек + superscript (¹ ² ³) cyan.
    @username and project/task count use matching accent color.
    Fills the 4:3 area from Ghostty config.
    """
    if not visible:
        app_print("Нет активных записей.")
        return

    for i, e in enumerate(visible, 1):
        num = superscript(i)
        ass = e.get("assignee") or ""
        txt = e.get("text", "")
        if _HAS_RICH:
            from rich.text import Text
            line = Text()
            line.append(f"{num} ", style="bold cyan")
            if ass:
                line.append(ass, style="bold bright_cyan")
                line.append(" ", style="bright_cyan")
            line.append(txt)
            app_print(line)
        else:
            prefix = f"{ass} " if ass else ""
            app_print(f"{num} {prefix}{txt}")


if __name__ == "__main__":
    main()
