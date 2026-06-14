"""
core/app.py
"""

from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional, Tuple

from .data import (
    load_state, save_state,
    list_projects, create_project,
    new_id, utc_now,
)
from .logic import (
    build_numbered_view,
    get_entry_by_number,
    parse_bare_input,
    fmt_entry,
    get_all_entries,
)

class CoreApp:
    def __init__(self):
        self.dir: Optional[str] = None
        self.state: Dict[str, Any] = {}
        self.undo_stack: List[List[Dict]] = []
        self.redo_stack: List[List[Dict]] = []

    def load(self, d: str):
        self.state = load_state(d)
        self.dir = d
        self.undo_stack = []
        self.redo_stack = []

    def save(self):
        if self.dir:
            save_state(self.dir, self.state)

    def status(self) -> str:
        """Возвращает строку статуса (CLI сам печатает)."""
        if not self.dir:
            return "нет проекта"
        name = self.state.get("_meta", {}).get("display_name") or self.dir
        tasks = [e for e in self.state.get("entries", []) if e.get("type") == "task" and not e.get("done", False)]
        return f"Проект: {name}\tЗадачи: {len(tasks)}"

    # --- Централизованная нумерация ---
    def get_numbered_view(self) -> Tuple[List[Dict[str, Any]], Dict[int, str]]:
        """Единственный способ получить текущие номера в CLI."""
        return build_numbered_view(self.state)

    def get_entry_by_number(self, number_map: Dict[int, str], num: int) -> Dict[str, Any] | None:
        return get_entry_by_number(self.state, number_map, num)

    # --- Bare input ---
    def add_bare(self, raw: str) -> Dict[str, Any] | None:
        parsed = parse_bare_input(raw)
        if not parsed or not self.dir:
            return None

        self._push_undo()
        e = {
            "id": new_id(),
            "type": "task",
            "text": parsed["text"],
            "assignee": parsed.get("assignee"),
            "ts": utc_now(),
            "done": False,
        }
        self.state.setdefault("entries", []).append(e)
        self.save()
        return e

    # --- Мутации ---
    def delete_by_numbers(self, number_map: Dict[int, str], nums: List[int]) -> List[Dict[str, Any]]:
        ids = []
        for n in nums:
            e = self.get_entry_by_number(number_map, n)
            if e:
                ids.append(e["id"])
        return self.delete_by_ids(ids)

    def delete_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        to_remove = set(i for i in ids if i)
        if not to_remove:
            return []
        self._push_undo()
        deleted = []
        new_entries = []
        for e in self.state.get("entries", []):
            if e["id"] in to_remove:
                deleted.append(e)
            else:
                new_entries.append(e)
        self.state["entries"] = new_entries
        self.save()
        return deleted

    def mark_done_by_numbers(self, number_map: Dict[int, str], nums: List[int]) -> List[Dict[str, Any]]:
        ids = []
        for n in nums:
            e = self.get_entry_by_number(number_map, n)
            if e:
                ids.append(e["id"])
        return self.mark_done_by_ids(ids)

    def mark_done_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        to_mark = set(i for i in ids if i)
        if not to_mark:
            return []
        changed = []
        self._push_undo()
        for e in self.state.get("entries", []):
            if e["id"] in to_mark:
                e["done"] = True
                changed.append(e)
        if changed:
            self.save()
        return changed

    def edit_by_number(self, number_map: Dict[int, str], num: int, new_text: str) -> bool:
        e = self.get_entry_by_number(number_map, num)
        if not e:
            return False
        self._push_undo()
        e["text"] = new_text.strip()
        if "@" in new_text and e.get("type") == "task":
            import re
            m = re.search(r'(@\S+)', new_text)
            if m:
                e["assignee"] = m.group(1)
        self.save()
        return True

    # --- Undo/Redo ---
    def _push_undo(self):
        snap = copy.deepcopy(self.state.get("entries", []))
        self.undo_stack.append(snap)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        current = copy.deepcopy(self.state.get("entries", []))
        self.redo_stack.append(current)
        self.state["entries"] = self.undo_stack.pop()
        self.save()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        current = copy.deepcopy(self.state.get("entries", []))
        self.undo_stack.append(current)
        self.state["entries"] = self.redo_stack.pop()
        self.save()
        return True

# get_finances удалён (финансы удалены)
