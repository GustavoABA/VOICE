from __future__ import annotations

import json
from typing import Any

from .constants import GITHUB_REPO
from .paths import config_path


DEFAULT_CONFIG: dict[str, Any] = {
    "bot_token": "",
    "user_id": "",
    "guild_id": "",
    "vosk_model": "",
    "input_device": "",
    "block_size": "4000",
    "tts_provider": "Windows SAPI (local)",
    "tts_voice": "",
    "tts_speed": 1.0,
    "piper_exe": "piper",
    "piper_model": "",
    "espeak_exe": "espeak-ng",
    "coqui_model": "",
    "coqui_python": "",
    "kokoro_voice": "pf_dora",
    "edge_voice": "pt-BR-FranciscaNeural",
    "ffmpeg_exe": "ffmpeg",
    "tiktok_voice": "br_001",
    "tiktok_api_url": "",
    "openai_api_key": "",
    "openai_voice": "alloy",
    "manual_text": "",
    "github_repo": GITHUB_REPO,
    "auto_update": True,
}


def load_config() -> dict[str, Any]:
    values = dict(DEFAULT_CONFIG)
    path = config_path()
    if not path.exists():
        return values
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return values
    if isinstance(loaded, dict):
        values.update(loaded)
    values["github_repo"] = GITHUB_REPO
    return values


def save_config(values: dict[str, Any]) -> None:
    path = config_path()
    existing = load_config()
    existing.update(values)
    existing["github_repo"] = GITHUB_REPO
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
