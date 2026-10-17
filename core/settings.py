"""Tiny persistent key/value store (JSON in the user's home folder)."""
from __future__ import annotations

import json
from pathlib import Path


class Settings:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path.home() / ".pdfkit" / "settings.json"
        self._data: dict = {}
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError:
            pass  # settings are a convenience; never crash the app over them
