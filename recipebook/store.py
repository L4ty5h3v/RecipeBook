from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save({"products": [], "dishes": []})

    def load(self) -> dict:
        with self.lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: dict) -> None:
        with self.lock:
            self.path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
