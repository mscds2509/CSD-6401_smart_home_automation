"""JSON Memento-style snapshot store for portable home configuration backups."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class StateSnapshotStore:
    """Atomically persist and load a versioned application-state snapshot."""
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def save(self, snapshot: dict[str, Any]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)
        return self.path

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Unsupported or invalid state snapshot")
        return data
