from __future__ import annotations

import sys
from pathlib import Path


APP_DATA_FOLDER = "NocturneVoiceData"


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    if getattr(sys, "frozen", False):
        path = app_base_dir() / APP_DATA_FOLDER
    else:
        path = app_base_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_dir() -> Path:
    path = data_dir() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def updates_dir() -> Path:
    path = data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.json"
