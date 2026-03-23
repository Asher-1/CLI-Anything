"""Scene/project state tracking (thin wrapper, actual state lives in ACloudViewer)."""

from __future__ import annotations
import json
from pathlib import Path


_project_file: str | None = None
_entities: list[dict] = []


def create_project(path: str) -> dict:
    global _project_file, _entities
    _project_file = path
    _entities = []
    return {"project": path, "status": "created"}


def open_project(path: str) -> dict:
    global _project_file, _entities
    _project_file = path
    p = Path(path)
    if p.exists() and p.suffix == ".json":
        _entities = json.loads(p.read_text()).get("entities", [])
    return {"project": path, "entities": len(_entities)}


def save_project(path: str | None = None) -> dict:
    p = path or _project_file
    if not p:
        return {"error": "No project file set"}
    Path(p).write_text(json.dumps({"entities": _entities}, indent=2))
    return {"project": p, "saved": len(_entities)}


def add_entity_record(info: dict) -> None:
    _entities.append(info)


def remove_entity_record(entity_id: int) -> None:
    global _entities
    _entities = [e for e in _entities if e.get("id") != entity_id]


def get_project_info() -> dict:
    return {
        "project_file": _project_file,
        "entity_count": len(_entities),
    }
