"""
core/data.py
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

def _get_data_dir() -> Path:
    """Multi-platform user data dir with fallback."""
    home = Path.home()
    docs = home / "Documents"
    if docs.exists():
        return docs / "Sisyphus"
    else:
        # fallback to current data/ (for dev in source tree) or ~/.sisyphus
        here = Path(__file__).resolve().parents[2]
        local = here / "data"
        if local.exists():
            return local
        return home / ".sisyphus"

DATA_DIR = _get_data_dir()
PROJECTS_DIR = DATA_DIR / "projects"
LAST_FILE = DATA_DIR / "last_project.txt"
SETTINGS_FILE = DATA_DIR / "settings.json"

def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def new_id() -> str:
    import random
    import time
    return f"e{int(time.time()*1000)}{random.randint(100,999)}"

def safe_name(name: str) -> str:
    import re
    name = name.strip().lower()
    name = re.sub(r"[^a-zа-яё0-9_-]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        name = "project"
    base = name
    i = 1
    while (PROJECTS_DIR / name).exists():
        name = f"{base}-{i}"
        i += 1
    return name

def project_dir(d: str) -> Path:
    return PROJECTS_DIR / d

# ==================== LAST PROJECT ====================
def load_last() -> Optional[str]:
    if LAST_FILE.exists():
        n = LAST_FILE.read_text(encoding="utf-8").strip()
        if n and project_dir(n).exists():
            return n
    return None

def save_last(d: str) -> None:
    LAST_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_FILE.write_text(d, encoding="utf-8")

# ==================== SETTINGS ====================
def load_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            s = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            s.setdefault("lang", "ru")
            s.setdefault("bot_token", "")
            s.setdefault("chat_ids", {})
            return s
        except Exception:
            pass
    s = {
        "lang": "ru",
        "bot_token": "",
        "chat_ids": {},
    }
    save_settings(s)
    return s

def save_settings(s: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

# ==================== PROJECT STATE ====================
def load_state(d: str) -> Dict[str, Any]:
    p = project_dir(d) / "state.json"
    if not p.exists():
        raise FileNotFoundError(d)
    return json.loads(p.read_text(encoding="utf-8"))

def save_state(d: str, state: Dict[str, Any]) -> None:
    pd = project_dir(d)
    pd.mkdir(parents=True, exist_ok=True)
    if "_meta" not in state:
        state["_meta"] = {}
    state["_meta"]["updated_at"] = utc_now()
    if "display_name" not in state["_meta"]:
        state["_meta"]["display_name"] = d
    state_file = pd / "state.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    save_last(d)

def list_projects() -> List[Dict[str, Any]]:
    items = []
    if not PROJECTS_DIR.exists():
        return items
    for p in sorted(PROJECTS_DIR.iterdir()):
        if p.is_dir():
            sf = p / "state.json"
            if sf.exists():
                try:
                    st = json.loads(sf.read_text(encoding="utf-8"))
                    meta = st.get("_meta", {})
                    items.append({"name": meta.get("display_name") or p.name, "dir": p.name})
                except Exception:
                    items.append({"name": p.name, "dir": p.name})
    return items

def create_project(name: str) -> str:
    d = safe_name(name)
    save_state(d, {"_meta": {"display_name": name.strip()}, "entries": []})
    return d

def delete_project(name: str) -> bool:
    import shutil
    import re
    if not name:
        return False
    name_l = name.strip().lower()
    target = None
    if PROJECTS_DIR.exists():
        projs = list_projects()
        for pr in projs:
            if pr["dir"].lower() == name_l or pr["name"].lower() == name_l:
                target = pr["dir"]
                break
        if not target:
            d = name.strip().lower()
            d = re.sub(r"[^a-zа-яё0-9_-]+", "-", d)
            d = re.sub(r"-+", "-", d).strip("-")
            if d and (PROJECTS_DIR / d).exists():
                target = d
    if not target:
        return False
    pdir = project_dir(target)
    if pdir.exists():
        shutil.rmtree(pdir)
        if load_last() == target:
            projs = list_projects()
            if projs:
                save_last(projs[0]["dir"])
            else:
                if LAST_FILE.exists():
                    LAST_FILE.unlink()
        return True
    return False

def rename_project(old_name: str, new_name: str) -> Optional[str]:
    """Переименовать проект. Возвращает новый slug или None (не найден / занято)."""
    import shutil
    import re
    if not old_name or not new_name:
        return None
    target = None
    name_l = old_name.strip().lower()
    projs = list_projects()
    for pr in projs:
        if pr["dir"].lower() == name_l or pr["name"].lower() == name_l:
            target = pr["dir"]
            break
    if not target:
        d = name_l
        d = re.sub(r"[^a-zа-яё0-9_-]+", "-", d).strip("-")
        if d and (PROJECTS_DIR / d).exists():
            target = d
    if not target:
        return None
    old_pdir = project_dir(target)
    if not old_pdir.exists():
        return None
    new_slug = new_name.strip().lower()
    new_slug = re.sub(r"[^a-zа-яё0-9_-]+", "-", new_slug)
    new_slug = re.sub(r"-+", "-", new_slug).strip("-")
    if not new_slug:
        new_slug = "project"
    new_pdir = project_dir(new_slug)
    if new_pdir.exists() and new_slug != target:
        return None  # занято
    try:
        state = load_state(target)
    except Exception:
        return None
    state.setdefault("_meta", {})
    state["_meta"]["display_name"] = new_name.strip()
    if new_slug == target:
        save_state(target, state)
        return target
    try:
        old_pdir.rename(new_pdir)
    except Exception:
        return None
    save_state(new_slug, state)
    return new_slug

def ensure_state(state: Dict[str, Any]) -> None:
    """Минимальная миграция."""
    if "entries" not in state:
        state["entries"] = []
