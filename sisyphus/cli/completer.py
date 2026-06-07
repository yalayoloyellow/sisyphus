"""
cli/completer.py

Автодополнение на основе предыдущих записей (по типу).
"""

from __future__ import annotations
from typing import List

from ..core.app import CoreApp
from ..core.logic import get_all_entries

def get_completions(app: CoreApp, text: str) -> List[str]:
    """Простая реализация (можно улучшить)."""
    visible = get_all_entries(app.state)
    suggestions = []
    text_lower = text.lower()

    if text.startswith(('+', '-')):
        candidates = [e["text"] for e in visible if e.get("type") == "finance"]
    elif text.startswith('@'):
        candidates = [e["text"] for e in visible if e.get("type") == "task"]
    else:
        candidates = [e["text"] for e in visible if e.get("type") == "note"]

    for c in candidates:
        if text_lower in c.lower() or c.lower().startswith(text_lower[:3]):
            suggestions.append(c)

    seen = set()
    result = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result[:15]


def get_completer(app: CoreApp):
    """Возвращает объект Completer для prompt_toolkit (лениво)."""
    try:
        from prompt_toolkit.completion import Completer, Completion
    except ImportError:
        return None

    class _SisyphusCompleter(Completer):
        def __init__(self, _app: CoreApp):
            self.app = _app

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor.strip()
            for s in get_completions(self.app, text):
                yield Completion(s, start_position=-len(text))

    return _SisyphusCompleter(app)
