"""
cli/commands.py

Обработка команд. Минимально, без дублирования.

Нумерация приходит снаружи (из repl), чтобы не прятать состояние.
"""

from __future__ import annotations
from typing import Dict, Optional

import sys

from ..core.app import CoreApp
from ..core.data import list_projects, create_project, delete_project, DATA_DIR, load_last, rename_project
from ..core.logic import fmt_entry
from pathlib import Path


def handle_command(
    app: CoreApp,
    cmd: str,
    arg: str,
    number_map: Dict[int, str]
) -> Optional[str]:
    """Возвращает строку для печати или специальное значение."""

    if cmd == "m":
        if arg:
            projs = list_projects()
            tgt = None
            for pr in projs:
                if pr["name"].lower() == arg.lower() or pr["dir"].lower() == arg.lower():
                    tgt = pr["dir"]
                    break
            if tgt:
                app.load(tgt)
                return None  # repl сам покажет статус + список
            return "Проект не найден."
        else:
            projs = list_projects()
            lines = ["Проекты:"]
            for i, pr in enumerate(projs, 1):
                cur = " *" if pr["dir"] == app.dir else ""
                lines.append(f"  {i}. {pr['name']}{cur}")
            lines.append("Введите номер или имя проекта для переключения (или используй /m имя).")
            return "\n".join(lines)

    if cmd == "p-":
        if arg:
            pname = arg.strip()
            if pname:
                current_is_target = False
                if app.dir:
                    try:
                        cur_disp = (app.state.get("_meta", {}).get("display_name") or app.dir).lower()
                        if app.dir.lower() == pname.lower() or cur_disp == pname.lower():
                            current_is_target = True
                    except Exception:
                        if app.dir.lower() == pname.lower():
                            current_is_target = True
                print(f"Удалить проект '{pname}'? [y/N] ", end="", flush=True)
                ans = input().strip().lower()
                if ans != "y":
                    return "отменено"
                if delete_project(pname):
                    if current_is_target:
                        new_last = load_last()
                        if new_last:
                            app.load(new_last)
                        else:
                            app.dir = None
                            app.state = {}
                            if not list_projects():
                                d = create_project("main")
                                app.load(d)
                                return f"Проект '{pname}' удалён. Создан новый пустой проект main."
                    return f"Проект '{pname}' удалён."
                return "Проект не найден."
            return "Укажи имя проекта для удаления: /p- имя"
        return "Укажи имя проекта для удаления: /p- имя"

    elif cmd == "p":
        if arg.startswith("-"):
            pname = arg[1:].strip()
            if pname:
                current_is_target = False
                if app.dir and app.dir.lower() == pname.lower():
                    current_is_target = True
                if delete_project(pname):
                    if current_is_target:
                        new_last = load_last()
                        if new_last:
                            app.load(new_last)
                        else:
                            app.dir = None
                            app.state = {}
                            if not list_projects():
                                d = create_project("main")
                                app.load(d)
                    return f"Проект '{pname}' удалён."
                return "Проект не найден."
            return "Укажи имя проекта для удаления: /p- имя"
        elif arg:
            d = create_project(arg)
            app.load(d)
            return None
        return "Использование: /p имя_проекта  или  /p- имя_проекта"

    elif cmd == "rename":
        if not arg:
            return "Использование: /rename новое_имя"
        if not app.dir:
            return "Нет открытого проекта."
        new_d = rename_project(app.dir, arg)
        if new_d:
            app.load(new_d)
            return None
        return "Имя занято или не удалось переименовать."

    elif cmd == "del":
        nums = [int(tok) for tok in arg.split() if tok.isdigit()]
        if not nums:
            return "Укажите номера: /del 3 7"
        entry_map = app.get_numbered_view()[1]
        ids = []
        for n in nums:
            eid = number_map.get(n)
            if eid is None:
                eid = entry_map.get(n)
            if eid:
                ids.append(eid)
        deleted = app.delete_by_ids(ids)
        for d in deleted:
            print(f"Удалено: {fmt_entry(d)}")
        return None

    elif cmd == "done":
        nums = [int(tok) for tok in arg.split() if tok.isdigit()]
        if not nums:
            return "Укажите номера: /done 2 5"
        ids = []
        for n in nums:
            eid = number_map.get(n)
            if eid:
                ids.append(eid)
        changed = app.mark_done_by_ids(ids)
        for c in changed:
            print(f"Отмечено выполненным: {fmt_entry(c)}")
        return None

    elif cmd == "e":
        if not arg:
            return "Использование: /e N новый текст"
        try:
            n_str, new_text = arg.split(maxsplit=1)
            n = int(n_str)
        except Exception:
            return "Использование: /e N новый текст"
        if app.edit_by_number(number_map, n, new_text):
            return None
        return "Запись не найдена."

    elif cmd == "u":
        if app.undo():
            return "Отменено."
        return "Нечего отменять."

    elif cmd == "r":
        if app.redo():
            return "Возвращено."
        return "Нечего возвращать."

    elif cmd in ("dir", "open", "d"):
        try:
            if sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(DATA_DIR)], check=False)
            elif sys.platform == "win32":
                import os
                os.startfile(str(DATA_DIR))
            else:
                import subprocess
                subprocess.run(["xdg-open", str(DATA_DIR)], check=False)
            return f"Data dir: {DATA_DIR}"
        except Exception as e:
            return f"error: {e}"

    elif cmd == "q":
        return "quit"

    # bot token — конфигурация токена (используем data напрямую)
    elif cmd == "bot":
        from ..core.data import load_settings, save_settings
        sub = arg.lower().split()
        if not sub:
            return "Использование: /bot token <токен>"
        settings = load_settings()
        if sub[0] == "token" and len(sub) > 1:
            token = arg.split(maxsplit=1)[1].strip()
            if ":" not in token:
                return "Неверный формат токена (должен содержать ':')."
            settings["bot_token"] = token
            save_settings(settings)
            return "Токен сохранён."
        return "Неизвестная подкоманда. Используй /bot token <токен>"

    elif cmd == "notify":
        from ..bot.telegram_bot import force_notify
        return force_notify()

    elif cmd == "tasks":
        if not arg:
            return "Использование: tasks @username"
        # normalize: accept "user" or "@user"
        uname = arg.strip()
        if not uname.startswith("@"):
            uname = "@" + uname
        from ..core.logic import get_user_tasks_across_projects
        from ..bot.telegram_bot import _format_my_message
        tasks_by_proj = get_user_tasks_across_projects(uname)
        if not tasks_by_proj:
            return f"Нет открытых задач для {uname}"
        # reuse the existing formatter (same as old /my)
        text = _format_my_message(uname)
        return text

    else:
        return "Неизвестная команда. /h для справки."
