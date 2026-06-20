"""
core/logic.py
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .data import ensure_state

def get_visible_entries(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Только задачи с done=False."""
    ensure_state(state)
    ents = [
        e for e in state.get("entries", [])
        if e.get("type") == "task" and not e.get("done", False)
    ]
    return sorted(ents, key=lambda e: e.get("ts", ""))

def get_all_entries(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    ensure_state(state)
    return sorted(state.get("entries", []), key=lambda e: e.get("ts", ""))

# compute_stats удалён (только для финансов/заметок)

def fmt_entry(e: Dict[str, Any]) -> str:
    """Простой форматтер для задач (без лишнего префикса)."""
    text = e.get("text", "")
    assignee = e.get("assignee")
    done = e.get("done", False)

    suffix = " ✓" if done else ""
    if assignee:
        return f"{assignee} {text}{suffix}"
    return f"{text}{suffix}"

# ==================== ЦЕНТРАЛИЗОВАННАЯ НУМЕРАЦИЯ ====================
def build_numbered_view(state: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
    """
    Один источник правды для нумерации (только задачи).

    Возвращает:
      - список видимых задач
      - карту {номер: id} для команд /del, /done, /e

    Нумерация совпадает с тем, что печатает пользователь.
    После мутации нужно заново получать view.
    """
    visible = get_visible_entries(state)
    number_map: Dict[int, str] = {}
    for i, e in enumerate(visible, 1):
        number_map[i] = e["id"]
    return visible, number_map

# get_numbered_finances удалена (финансы удалены)

def get_entry_by_number(state: Dict[str, Any], number_map: Dict[int, str], num: int) -> Dict[str, Any] | None:
    """Безопасное получение записи по номеру из текущей карты."""
    eid = number_map.get(num)
    if not eid:
        return None
    for e in state.get("entries", []):
        if e.get("id") == eid:
            return e
    return None

def parse_bare_input(raw: str) -> Dict[str, Any] | None:
    """
    Только задачи в формате @username текст.
    Plain text без @ игнорируется (возвращает None).
    Финансы и заметки удалены.
    """
    import re
    raw = raw.strip()
    if not raw:
        return None

    # Только задача
    if raw.startswith('@'):
        m = re.match(r'^(@\S+)\s+(.+)$', raw)
        if m:
            assignee = m.group(1)
            text = m.group(2).strip()
            if text:
                return {"type": "task", "text": text, "assignee": assignee}
        return None

    # Plain text без @ — игнорировать
    return None


def get_user_tasks_across_projects(username: str) -> Dict[str, List[Dict[str, Any]]]:
    """Чистая бизнес-логика для бота: задачи по @username по всем проектам."""
    from .data import list_projects, load_state
    result: Dict[str, List[Dict[str, Any]]] = {}
    target = f"@{username}" if not username.startswith('@') else username
    for proj in list_projects():
        try:
            st = load_state(proj["dir"])
            tasks = [
                e for e in st.get("entries", [])
                if e.get("type") == "task"
                and not e.get("done", False)
                and e.get("assignee") == target
            ]
            if tasks:
                result[proj["name"]] = tasks
        except Exception:
            continue
    return result


# export_to_xlsx удалена (экспорт удалён вместе с финансами/заметками)


def superscript(n: int) -> str:
    """Unicode superscript for display (¹ ² ³ ...). Purely visual."""
    supers = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(n).translate(supers)


# ==================== RICH MARKDOWN ДЛЯ КРОСС-ПРОСМОТРА ( /tasks и TG ) ====================

def format_user_tasks_markdown(tasks_by_project: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Один источник для /tasks и TG notify.
    Используем заголовки (#) — они хорошо рендерятся в Telegram Rich Messages.
    """
    if not tasks_by_project:
        return "У вас нет открытых задач ни в одном проекте."

    lines: List[str] = []
    for proj_name, tasks in tasks_by_project.items():
        lines.append(f"# {proj_name}")
        lines.append("")
        for t in tasks:
            txt = t.get("text", "")
            lines.append(f"- {txt}")
        lines.append("")

    return "\n".join(lines).rstrip()

