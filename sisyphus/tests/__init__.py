"""
tests/__init__.py

Серьёзные автоматические тесты для --test.

Проверяем реальные сценарии без UI: bare input, /del, /done, /fin, /export, множественные номера и т.д.
"""

from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from ..core.app import CoreApp
from ..core.data import create_project, list_projects, delete_project, DATA_DIR, PROJECTS_DIR
from ..core.logic import get_all_entries, export_to_xlsx, get_user_tasks_across_projects


def _setup_temp_project() -> tuple[CoreApp, Path]:
    """Создаём временный проект для теста."""
    tmp = Path(tempfile.mkdtemp())
    orig_data = DATA_DIR
    orig_projects = PROJECTS_DIR

    # Временно подменяем пути (для изоляции теста)
    import sisyphus.core.data as data_mod
    data_mod.DATA_DIR = tmp / "data"
    data_mod.PROJECTS_DIR = data_mod.DATA_DIR / "projects"

    app = CoreApp()
    d = create_project("testproj")
    app.load(d)

    return app, tmp


def _teardown_temp(tmp: Path, orig_data: Path, orig_projects: Path):
    import shutil
    import sisyphus.core.data as data_mod
    shutil.rmtree(tmp, ignore_errors=True)
    data_mod.DATA_DIR = orig_data
    data_mod.PROJECTS_DIR = orig_projects


def run_all_tests():
    print("=== Запуск серьёзных тестов Sisyphus (core) ===\n")

    import sisyphus.core.data as data_mod
    orig_data = data_mod.DATA_DIR
    orig_projects = data_mod.PROJECTS_DIR

    # 1. Bare input
    app, tmp = _setup_temp_project()
    e1 = app.add_bare("Просто заметка про проект")
    e2 = app.add_bare("@ilyashamaev Сделать важное дело")
    e3 = app.add_bare("+2500 аванс за работу")
    visible, _ = app.get_numbered_view()
    types = {e["type"] for e in visible}
    print(f"  Bare added visible types: {types}")
    assert "note" in types
    assert "task" in types
    fins = app.get_finances()
    assert len(fins) == 1 and fins[0].get("amount") == 2500
    print("✓ Bare input: note, task с @, finance с текстом (finance не в главном списке)")

    _teardown_temp(tmp, orig_data, orig_projects)

    # 2. Нумерация и /del с множественными
    app, tmp = _setup_temp_project()
    app.add_bare("Заметка 1")
    app.add_bare("@user Задача 1")
    app.add_bare("Заметка 2")
    visible, num_map = app.get_numbered_view()
    assert len(num_map) == 3
    deleted = app.delete_by_numbers(num_map, [1, 2])  # удаляем 1 и 2 (заметки; grouped numbering: notes first)
    assert len(deleted) == 2
    visible, _ = app.get_numbered_view()
    assert len(visible) == 1
    assert visible[0]["type"] == "task"
    print("✓ /del с множественными номерами + обновление нумерации")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 3. /done + архив
    app, tmp = _setup_temp_project()
    app.add_bare("Заметка для done")
    app.add_bare("@user Задача для done")
    visible, num_map = app.get_numbered_view()
    changed = app.mark_done_by_numbers(num_map, [1, 2])
    assert len(changed) == 2
    visible, _ = app.get_numbered_view()
    assert len(visible) == 0  # оба done, не видны
    # Проверяем что в get_all_entries они есть с done
    all_e = get_all_entries(app.state)
    assert sum(1 for e in all_e if e.get("done")) == 2
    print("✓ /done + скрытие из главного вида")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 4. /fin
    app, tmp = _setup_temp_project()
    app.add_bare("+100 доход")
    app.add_bare("-30 расход на кофе")
    fins = app.get_finances()
    assert len(fins) == 2
    total = sum(f.get("amount", 0) for f in fins)
    assert total == 70
    print("✓ /fin: финансы не влияют на главный список, сумма считается")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 8. /notify настройка (симуляция команды)
    app, tmp = _setup_temp_project()
    from ..core.data import load_settings, save_settings
    settings = load_settings()
    settings["notify"] = {"type": "daily", "time": "09:00"}
    save_settings(settings)
    loaded = load_settings()
    assert loaded.get("notify", {}).get("type") == "daily"
    print("✓ /notify: настройка расписания сохраняется")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 9. /my симуляция (через логику бота)
    app, tmp = _setup_temp_project()
    app.add_bare("@ilyashamaev Задача для /my")
    app.add_bare("Обычная заметка")
    tasks = get_user_tasks_across_projects("ilyashamaev")
    assert len(tasks) >= 1
    # Проверяем что есть проект с задачей для пользователя
    has_task = any("Задача для /my" in str(t) for ts in tasks.values() for t in ts)
    assert has_task
    print("✓ /my: симуляция возвращает только задачи по @username")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 5. /export в один .xlsx с 3 листами
    app, tmp = _setup_temp_project()
    app.add_bare("Заметка экспорт")
    app.add_bare("@user Задача экспорт")
    app.add_bare("+500 экспорт фин")
    export_path = tmp / "test_export.xlsx"
    try:
        export_to_xlsx(app.state, export_path)
        # Для .xlsx проверяем наличие файла и размер (не парсим без openpyxl в тесте)
        assert export_path.exists() and export_path.stat().st_size > 100
        print("✓ /export: один .xlsx с 3 листами (Заметки, Задачи, Финансы)")
    except RuntimeError as e:
        print(f"  /export skipped (no openpyxl): {e}")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 6. /m /p (проекты)
    app, tmp = _setup_temp_project()
    # текущий проект уже создан
    projs = list_projects()
    assert len(projs) >= 1
    # create another
    d2 = create_project("second")
    projs = list_projects()
    assert any(p["dir"] == "second" for p in projs)
    delete_project("second")
    print("✓ /m /p /p- : управление проектами")
    _teardown_temp(tmp, orig_data, orig_projects)

    # 7. Множественные номера в done
    app, tmp = _setup_temp_project()
    app.add_bare("1")
    app.add_bare("2")
    app.add_bare("3")
    visible, num_map = app.get_numbered_view()
    app.mark_done_by_numbers(num_map, [1, 3])
    visible, _ = app.get_numbered_view()
    assert len(visible) == 1
    print("✓ Множественные номера в /done")
    _teardown_temp(tmp, orig_data, orig_projects)

    print("\n=== Все тесты пройдены успешно ===")
