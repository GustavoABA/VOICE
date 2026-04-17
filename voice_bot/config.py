from __future__ import annotations

import json
from typing import Any

from .paths import config_path


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(values: dict[str, Any]) -> None:
    path = config_path()
    existing = load_config()
    existing.update(values)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
