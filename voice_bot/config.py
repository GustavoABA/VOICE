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
    "manual_text": "",
    "tts_provider": "pyttsx3",
    "tts_voice": "",
    "tts_speed": 1.0,
    "tts_timeout_seconds": 240,
    "ffmpeg_exe": "ffmpeg",
    "python_exe": "",
    "command_template": "",
    "endpoint_url": "",
    "endpoint_method": "POST",
    "endpoint_text_field": "text",
    "endpoint_voice_field": "voice",
    "piper_exe": "piper",
    "piper_model": "",
    "kokoro_voice": "pf_dora",
    "kokoro_lang": "p",
    "coqui_model": "",
    "coqui_language": "pt",
    "coqui_speaker_wav": "",
    "espeak_exe": "espeak-ng",
    "espeak_voice": "pt-br",
    "festival_exe": "text2wave",
    "mimic3_exe": "mimic3",
    "mimic3_voice": "",
    "f5_exe": "f5-tts_infer-cli",
    "f5_model": "F5TTS_v1_Base",
    "f5_ref_audio": "",
    "f5_ref_text": "",
    "marytts_url": "http://localhost:59125/process",
    "marytts_locale": "pt_BR",
    "marytts_voice": "",
    "rhvoice_exe": "RHVoice-test",
    "rhvoice_voice": "",
    "rvc_enabled": False,
    "rvc_model": "",
    "rvc_index": "",
    "rvc_pitch": 0,
    "rvc_device": "cpu",
    "rvc_index_rate": 0.33,
    "github_repo": GITHUB_REPO,
}


LEGACY_PROVIDER_ALIASES = {
    "Windows SAPI (local)": "pyttsx3",
    "RVC (Voice Conversion local)": "pyttsx3",
    "Kokoro (local opcional)": "Kokoro TTS",
    "Piper TTS (local opcional)": "Piper TTS",
    "Coqui TTS / XTTS v2 (local opcional)": "XTTS-v2",
    "F5-TTS (local opcional)": "F5-TTS",
    "eSpeak NG (local opcional)": "eSpeak NG",
    "NaturalReader Free (endpoint externo)": "NaturalReader",
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
    values["tts_provider"] = LEGACY_PROVIDER_ALIASES.get(str(values.get("tts_provider", "")), values["tts_provider"])
    values["github_repo"] = GITHUB_REPO
    return values


def save_config(values: dict[str, Any]) -> None:
    path = config_path()
    existing = dict(DEFAULT_CONFIG)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            existing.update(loaded)
    existing.update(values)
    existing["github_repo"] = GITHUB_REPO
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
