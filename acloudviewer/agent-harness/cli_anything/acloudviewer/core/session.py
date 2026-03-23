"""Lightweight undo/redo session tracking."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Snapshot:
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Session:
    def __init__(self):
        self._history: list[Snapshot] = []
        self._redo: list[Snapshot] = []

    def snapshot(self, description: str) -> None:
        self._history.append(Snapshot(description))
        self._redo.clear()

    def undo(self) -> Snapshot | None:
        if not self._history:
            return None
        s = self._history.pop()
        self._redo.append(s)
        return s

    def redo(self) -> Snapshot | None:
        if not self._redo:
            return None
        s = self._redo.pop()
        self._history.append(s)
        return s

    def status(self) -> dict:
        return {
            "history_length": len(self._history),
            "redo_length": len(self._redo),
            "last": self._history[-1].description if self._history else None,
        }
