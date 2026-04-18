from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np


TARGET_RATE = 48000


class TTSError(RuntimeError):
    """Erro exibivel na interface."""


LogCallback = Callable[[str], None]


PROVIDERS = (
    "Edge TTS",
    "gTTS",
    "Balabolka",
    "NaturalReader",
    "TTSReader",
    "Piper TTS",
    "Kokoro TTS",
    "XTTS-v2",
    "Coqui TTS",
    "Chatterbox TTS",
    "pyttsx3",
    "eSpeak NG",
    "Festival",
    "Mimic 3",
    "Tortoise TTS",
    "ChatTTS",
    "F5-TTS",
    "OpenVoice",
    "VITS",
    "YourTTS",
    "Glow-TTS",
    "MaryTTS",
    "RHVoice",
)


EDGE_VOICES = (
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural",
    "pt-PT-RaquelNeural",
    "pt-PT-DuarteNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
)

GTTS_LANGUAGES = (
    "pt",
    "pt-br",
    "en",
    "es",
    "fr",
    "de",
    "it",
    "ja",
    "ko",
)

ESPEAK_VOICES = ("pt-br", "pt", "pt+f2", "pt+m3", "en-us", "es", "fr", "de")
KOKORO_VOICES = ("pf_dora", "pm_alex", "pf_julia", "pm_santa", "af_heart", "am_adam")
COQUI_MODEL_CHOICES = (
    "tts_models/multilingual/multi-dataset/xtts_v2",
    "tts_models/multilingual/multi-dataset/your_tts",
    "tts_models/en/ljspeech/vits",
    "tts_models/en/ljspeech/glow-tts",
    "tts_models/pt/cv/vits",
)


COQUI_MODEL_DEFAULTS = {
    "XTTS-v2": "tts_models/multilingual/multi-dataset/xtts_v2",
    "Coqui TTS": "",
    "VITS": "tts_models/en/ljspeech/vits",
    "YourTTS": "tts_models/multilingual/multi-dataset/your_tts",
    "Glow-TTS": "tts_models/en/ljspeech/glow-tts",
}


EXTERNAL_COMMAND_HINTS = {
    "Balabolka": "Use o modo linha de comando do Balabolka. Exemplo: \"C:\\Program Files (x86)\\Balabolka\\balabolka.exe\" -nq -t \"{text}\" -w \"{output}\"",
    "Chatterbox TTS": "Informe um comando/script que receba texto e gere WAV. Use {text}, {output}, {voice}, {speed}.",
    "Tortoise TTS": "Tortoise normalmente exige Python 3.10/3.11 e um script local. Configure o comando que gera {output}.",
    "ChatTTS": "Configure um script local do ChatTTS que gere WAV em {output}.",
    "OpenVoice": "Configure o comando do seu ambiente OpenVoice para gerar WAV em {output}.",
}


@dataclass(slots=True)
class TTSConfig:
    provider: str
    voice: str = ""
    speed: float = 1.0
    timeout_seconds: int = 240
    ffmpeg_exe: str = "ffmpeg"
    python_exe: str = ""
    command_template: str = ""
    endpoint_url: str = ""
    endpoint_method: str = "POST"
    endpoint_text_field: str = "text"
    endpoint_voice_field: str = "voice"
    piper_exe: str = "piper"
    piper_model: str = ""
    edge_voice: str = "pt-BR-FranciscaNeural"
    gtts_lang: str = "pt"
    kokoro_voice: str = "pf_dora"
    kokoro_lang: str = "p"
    coqui_model: str = ""
    coqui_language: str = "pt"
    coqui_speaker_wav: str = ""
    espeak_exe: str = "espeak-ng"
    espeak_voice: str = "pt-br"
    festival_exe: str = "text2wave"
    mimic3_exe: str = "mimic3"
    mimic3_voice: str = ""
    f5_exe: str = "f5-tts_infer-cli"
    f5_model: str = "F5TTS_v1_Base"
    f5_ref_audio: str = ""
    f5_ref_text: str = ""
    marytts_url: str = "http://localhost:59125/process"
    marytts_locale: str = "pt_BR"
    marytts_voice: str = ""
    rhvoice_exe: str = "RHVoice-test"
    rhvoice_voice: str = ""
    rvc_enabled: bool = False
    rvc_model: str = ""
    rvc_index: str = ""
    rvc_pitch: int = 0
    rvc_device: str = "cpu"
    rvc_index_rate: float = 0.33


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        """Retorna o caminho de um WAV temporario."""


class Pyttsx3TTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        try:
            import pyttsx3
        except Exception as exc:
            raise TTSError(f"pyttsx3 nao esta instalado: {exc}") from exc

        wav_path = _temp_wav_path()
        engine = pyttsx3.init()
        if config.voice:
            selected = config.voice.lower()
            for voice in engine.getProperty("voices"):
                if selected in str(voice.id).lower() or selected in str(voice.name).lower():
                    engine.setProperty("voice", voice.id)
                    break
        engine.setProperty("rate", int(185 * _clamp(config.speed, 0.5, 1.8)))
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        return wav_path


class PiperTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        if not config.piper_model.strip():
            raise TTSError("Selecione o modelo .onnx do Piper TTS.")
        wav_path = _temp_wav_path()
        _run_checked(
            [
                config.piper_exe.strip() or "piper",
                "--model",
                config.piper_model.strip(),
                "--output_file",
                wav_path,
            ],
            input_text=text,
            timeout=config.timeout_seconds,
            error_prefix="Piper TTS falhou",
        )
        return wav_path


class EdgeOnlineTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        mp3_path = tempfile.NamedTemporaryFile(prefix="edge_tts_", suffix=".mp3", delete=False)
        mp3_path.close()
        wav_path = _temp_wav_path()
        voice = config.edge_voice.strip() or config.voice.strip() or "pt-BR-FranciscaNeural"
        try:
            try:
                import edge_tts
            except ImportError:
                _run_checked(
                    [
                        sys.executable,
                        "-m",
                        "edge_tts",
                        "--voice",
                        voice,
                        "--text",
                        text,
                        "--write-media",
                        mp3_path.name,
                    ],
                    timeout=config.timeout_seconds,
                    error_prefix="Edge TTS falhou",
                )
            else:
                import asyncio

                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(edge_tts.Communicate(text, voice).save(mp3_path.name))
                finally:
                    loop.close()
            _convert_audio_to_wav(mp3_path.name, wav_path, config.ffmpeg_exe, config.timeout_seconds)
        except Exception:
            cleanup_wav(wav_path)
            raise
        finally:
            cleanup_wav(mp3_path.name)
        return wav_path


class GoogleTranslateTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        lang = (config.gtts_lang.strip() or config.voice.strip() or "pt").lower()
        mp3_path = tempfile.NamedTemporaryFile(prefix="gtts_", suffix=".mp3", delete=False)
        mp3_path.close()
        wav_path = _temp_wav_path()
        try:
            try:
                from gtts import gTTS
            except ImportError as exc:
                raise TTSError("gTTS requer `pip install gTTS` ou use Ferramentas > Instalar dependencias do TTS atual.") from exc
            gTTS(text=text, lang=lang.split("-", 1)[0]).save(mp3_path.name)
            _convert_audio_to_wav(mp3_path.name, wav_path, config.ffmpeg_exe, config.timeout_seconds)
        except Exception:
            cleanup_wav(wav_path)
            raise
        finally:
            cleanup_wav(mp3_path.name)
        return wav_path


class KokoroTTS(TTSProvider):
    def __init__(self) -> None:
        self._pipeline = None
        self._lang = ""

    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        try:
            import soundfile as sf
            from kokoro import KPipeline
        except Exception as exc:
            raise TTSError("Kokoro TTS requer `pip install kokoro soundfile`.") from exc

        lang = config.kokoro_lang.strip() or "p"
        if self._pipeline is None or self._lang != lang:
            self._pipeline = KPipeline(lang_code=lang)
            self._lang = lang

        chunks: list[np.ndarray] = []
        for _graphemes, _phonemes, audio in self._pipeline(
            text,
            voice=config.kokoro_voice.strip() or "pf_dora",
            speed=_clamp(config.speed, 0.5, 1.8),
        ):
            chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            raise TTSError("Kokoro TTS nao gerou audio.")

        wav_path = _temp_wav_path()
        sf.write(wav_path, np.concatenate(chunks), 24000, subtype="PCM_16")
        return wav_path


class CoquiLikeTTS(TTSProvider):
    def __init__(self) -> None:
        self._model_name = ""
        self._tts = None

    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        model = _coqui_model_for(config)
        if not model:
            raise TTSError("Informe o modelo Coqui/TTS a ser usado.")

        portable_python = _valid_external_python(config.python_exe)
        if portable_python:
            return self._synthesize_with_python(text, config, model, portable_python)

        _require_compatible_python(config.provider)
        try:
            from TTS.api import TTS
        except Exception as exc:
            raise TTSError("Coqui TTS requer `TTS==0.22.0` em Python compativel.") from exc

        if "xtts" in model.lower():
            os.environ.setdefault("COQUI_TOS_AGREED", "1")
        if self._tts is None or self._model_name != model:
            self._tts = TTS(model)
            self._model_name = model

        wav_path = _temp_wav_path()
        self._tts.tts_to_file(**_coqui_kwargs(text, wav_path, model, config))
        return wav_path

    def _synthesize_with_python(self, text: str, config: TTSConfig, model: str, python_exe: str) -> str:
        if not _external_python_has_module(python_exe, "TTS"):
            raise TTSError(
                f"{config.provider} precisa do pacote Coqui `TTS` no Python portatil selecionado.\n"
                "Clique em Ferramentas > Instalar dependencias do TTS atual.\n"
                "Se a instalacao falhar com Microsoft Visual C++ 14.0, instale Microsoft C++ Build Tools ou use pyttsx3/Edge TTS/gTTS/Piper."
            )
        wav_path = _temp_wav_path()
        script = _write_temp_script(
            [
                "import os, sys",
                "os.environ.setdefault('COQUI_TOS_AGREED', '1')",
                "from TTS.api import TTS",
                "text, model, out, language, speaker_wav = sys.argv[1:6]",
                "tts = TTS(model)",
                "kwargs = {'text': text, 'file_path': out}",
                "if language: kwargs['language'] = language",
                "if speaker_wav: kwargs['speaker_wav'] = speaker_wav",
                "tts.tts_to_file(**kwargs)",
            ]
        )
        try:
            _run_checked(
                [
                    python_exe,
                    str(script),
                    text,
                    model,
                    wav_path,
                    config.coqui_language or "pt",
                    config.coqui_speaker_wav.strip(),
                ],
                timeout=config.timeout_seconds,
                error_prefix=f"{config.provider} falhou",
            )
        finally:
            cleanup_wav(str(script))
        return wav_path


class EspeakTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        wav_path = _temp_wav_path()
        _run_checked(
            [
                config.espeak_exe.strip() or "espeak-ng",
                "-v",
                config.espeak_voice.strip() or config.voice.strip() or "pt-br",
                "-s",
                str(int(170 * _clamp(config.speed, 0.5, 1.8))),
                "-w",
                wav_path,
                text,
            ],
            timeout=config.timeout_seconds,
            error_prefix="eSpeak NG falhou",
        )
        return wav_path


class FestivalTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        wav_path = _temp_wav_path()
        _run_checked(
            [config.festival_exe.strip() or "text2wave", "-o", wav_path],
            input_text=text,
            timeout=config.timeout_seconds,
            error_prefix="Festival falhou",
        )
        return wav_path


class Mimic3TTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        wav_path = _temp_wav_path()
        command = [config.mimic3_exe.strip() or "mimic3"]
        if config.mimic3_voice.strip():
            command.extend(["--voice", config.mimic3_voice.strip()])
        command.extend(["--output", wav_path, text])
        _run_checked(command, timeout=config.timeout_seconds, error_prefix="Mimic 3 falhou")
        return wav_path


class F5TTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        if not config.f5_ref_audio.strip():
            raise TTSError("F5-TTS precisa de um WAV de referencia.")

        out_dir = Path(tempfile.mkdtemp(prefix="f5_tts_"))
        out_name = "f5_generation.wav"
        _run_checked(
            [
                config.f5_exe.strip() or "f5-tts_infer-cli",
                "--model",
                config.f5_model.strip() or "F5TTS_v1_Base",
                "--ref_audio",
                config.f5_ref_audio.strip(),
                "--ref_text",
                config.f5_ref_text.strip(),
                "--gen_text",
                text,
                "--output_dir",
                str(out_dir),
                "--output_file",
                out_name,
            ],
            timeout=config.timeout_seconds,
            error_prefix="F5-TTS falhou",
        )
        expected = out_dir / out_name
        if expected.exists():
            return str(expected)
        wavs = sorted(out_dir.rglob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not wavs:
            raise TTSError("F5-TTS terminou sem gerar WAV.")
        return str(wavs[0])


class MaryTTSTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        base = config.marytts_url.strip() or "http://localhost:59125/process"
        params = {
            "INPUT_TEXT": text,
            "INPUT_TYPE": "TEXT",
            "OUTPUT_TYPE": "AUDIO",
            "AUDIO": "WAVE_FILE",
            "LOCALE": config.marytts_locale.strip() or "pt_BR",
        }
        if config.marytts_voice.strip():
            params["VOICE"] = config.marytts_voice.strip()
        separator = "&" if "?" in base else "?"
        request = urllib.request.Request(
            base + separator + urllib.parse.urlencode(params),
            headers={"User-Agent": "NocturneVoice/1.0"},
        )
        return _request_audio_to_wav(request, config.ffmpeg_exe, config.timeout_seconds)


class RHVoiceTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        wav_path = _temp_wav_path()
        command = [config.rhvoice_exe.strip() or "RHVoice-test", "-o", wav_path]
        if config.rhvoice_voice.strip():
            command.extend(["-p", config.rhvoice_voice.strip()])
        _run_checked(command, input_text=text, timeout=config.timeout_seconds, error_prefix="RHVoice falhou")
        return wav_path


class EndpointTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        template = config.endpoint_url.strip()
        if not template:
            raise TTSError(f"{config.provider} precisa de uma URL de endpoint ou comando externo.")

        voice = config.voice.strip()
        if "{text}" in template or "{voice}" in template:
            url = template.replace("{text}", urllib.parse.quote_plus(text)).replace("{voice}", urllib.parse.quote_plus(voice))
            request = urllib.request.Request(url, headers={"User-Agent": "NocturneVoice/1.0"})
        else:
            payload = {
                config.endpoint_text_field.strip() or "text": text,
                config.endpoint_voice_field.strip() or "voice": voice,
                "speed": config.speed,
            }
            method = (config.endpoint_method or "POST").upper()
            if method == "GET":
                separator = "&" if "?" in template else "?"
                template = template + separator + urllib.parse.urlencode(payload)
                data = None
            else:
                data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                template,
                data=data,
                headers={"User-Agent": "NocturneVoice/1.0", "Content-Type": "application/json"},
                method=method,
            )
        return _request_audio_to_wav(request, config.ffmpeg_exe, config.timeout_seconds)


class CommandTemplateTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig, log: LogCallback | None = None) -> str:
        if not config.command_template.strip():
            hint = EXTERNAL_COMMAND_HINTS.get(config.provider, "Configure um comando que gere WAV em {output}.")
            raise TTSError(hint)

        wav_path = _temp_wav_path()
        command = config.command_template.format(
            text=text,
            output=wav_path,
            voice=config.voice.strip(),
            speed=config.speed,
            python=config.python_exe.strip() or sys.executable,
        )
        _run_shell_checked(command, timeout=config.timeout_seconds, error_prefix=f"{config.provider} falhou")
        if not Path(wav_path).exists() or Path(wav_path).stat().st_size == 0:
            raise TTSError(f"{config.provider} nao gerou o arquivo WAV esperado.")
        return wav_path


class TTSManager:
    PROVIDERS = PROVIDERS

    def __init__(self, log: LogCallback | None = None) -> None:
        self._log = log
        coqui_provider = CoquiLikeTTS()
        self._providers: dict[str, TTSProvider] = {
            "Edge TTS": EdgeOnlineTTS(),
            "gTTS": GoogleTranslateTTS(),
            "Balabolka": CommandTemplateTTS(),
            "NaturalReader": EndpointTTS(),
            "TTSReader": EndpointTTS(),
            "Piper TTS": PiperTTS(),
            "Kokoro TTS": KokoroTTS(),
            "XTTS-v2": coqui_provider,
            "Coqui TTS": coqui_provider,
            "Chatterbox TTS": CommandTemplateTTS(),
            "pyttsx3": Pyttsx3TTS(),
            "eSpeak NG": EspeakTTS(),
            "Festival": FestivalTTS(),
            "Mimic 3": Mimic3TTS(),
            "Tortoise TTS": CommandTemplateTTS(),
            "ChatTTS": CommandTemplateTTS(),
            "F5-TTS": F5TTS(),
            "OpenVoice": CommandTemplateTTS(),
            "VITS": coqui_provider,
            "YourTTS": coqui_provider,
            "Glow-TTS": coqui_provider,
            "MaryTTS": MaryTTSTTS(),
            "RHVoice": RHVoiceTTS(),
        }

    def synthesize(self, text: str, config: TTSConfig) -> str:
        provider = self._providers.get(config.provider)
        if provider is None:
            raise TTSError(f"Provedor TTS desconhecido: {config.provider}")
        self._emit(f"TTS: gerando audio com {config.provider}")
        wav_path = provider.synthesize(text, config, self._emit)
        if not config.rvc_enabled:
            return wav_path

        self._emit("RVC: convertendo voz")
        converter = RVCConverter()
        try:
            return converter.convert(wav_path, config)
        except Exception:
            cleanup_wav(wav_path)
            raise

    def _emit(self, message: str) -> None:
        if self._log:
            self._log(message)


class RVCConverter:
    def convert(self, input_wav: str, config: TTSConfig) -> str:
        if not config.rvc_model.strip():
            raise TTSError("Ative RVC somente depois de selecionar o modelo .pth.")

        portable_python = _valid_external_python(config.python_exe)
        output_wav = _temp_wav_path()
        if portable_python:
            self._convert_with_python(input_wav, output_wav, config, portable_python)
            cleanup_wav(input_wav)
            return output_wav

        _require_compatible_python("RVC")
        try:
            from rvc_python.infer import RVCInference
        except ImportError as exc:
            raise TTSError("RVC requer `rvc-python` em Python 3.10/3.11 ou Python portatil configurado.") from exc

        try:
            rvc = RVCInference(device=config.rvc_device.strip() or "cpu")
            rvc.load_model(config.rvc_model.strip(), index_path=config.rvc_index.strip() or None)
            rvc.infer_file(
                input_wav,
                output_wav,
                f0_up_key=int(config.rvc_pitch),
                index_rate=float(config.rvc_index_rate),
            )
        except Exception as exc:
            cleanup_wav(output_wav)
            raise TTSError(f"RVC falhou: {exc}") from exc
        finally:
            cleanup_wav(input_wav)
        return output_wav

    def _convert_with_python(self, input_wav: str, output_wav: str, config: TTSConfig, python_exe: str) -> None:
        if not _external_python_has_module(python_exe, "rvc_python"):
            raise TTSError(
                "RVC precisa de `rvc-python` no Python portatil selecionado. "
                "Clique em Ferramentas > Instalar RVC no Python portatil."
            )
        script = _write_temp_script(
            [
                "import sys",
                "from rvc_python.infer import RVCInference",
                "input_p, output_p, model_p, index_p, device, pitch, idx_rate = sys.argv[1:8]",
                "rvc = RVCInference(device=device or 'cpu')",
                "rvc.load_model(model_p, index_path=index_p if index_p else None)",
                "rvc.infer_file(input_p, output_p, f0_up_key=int(pitch), index_rate=float(idx_rate))",
            ]
        )
        try:
            _run_checked(
                [
                    python_exe,
                    str(script),
                    input_wav,
                    output_wav,
                    config.rvc_model.strip(),
                    config.rvc_index.strip(),
                    config.rvc_device.strip() or "cpu",
                    str(int(config.rvc_pitch)),
                    str(float(config.rvc_index_rate)),
                ],
                timeout=config.timeout_seconds,
                error_prefix="RVC portatil falhou",
            )
        finally:
            cleanup_wav(str(script))


def list_windows_voices() -> list[str]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        return [str(voice.name) for voice in engine.getProperty("voices")]
    except Exception:
        return []


def compatibility_message(provider: str, python_exe: str = "") -> str:
    version = _python_version_tuple(python_exe) if python_exe else sys.version_info[:3]
    label = ".".join(str(part) for part in version[:3])
    heavy = {"XTTS-v2", "Coqui TTS", "VITS", "YourTTS", "Glow-TTS", "F5-TTS", "Tortoise TTS", "ChatTTS", "OpenVoice", "Chatterbox TTS", "RVC"}
    if provider in heavy and version[:2] not in {(3, 10), (3, 11)}:
        return f"Python {label} pode ser incompativel com {provider}. Recomendado: Python 3.10.11 portatil."
    if provider in {"Edge TTS", "gTTS"}:
        return f"Python {label}. {provider} e simples, online, e precisa de ffmpeg para converter MP3 em WAV."
    if provider in {"pyttsx3", "Piper TTS", "eSpeak NG", "Festival", "Mimic 3", "MaryTTS", "RHVoice"}:
        return f"Python {label} OK. Este provedor depende principalmente do executavel/pacote configurado."
    return f"Python {label}. Configure endpoint ou comando externo conforme o provedor."


def wav_to_discord_pcm(wav_path: str) -> bytes:
    samples, sample_rate = _read_wav_as_float32(wav_path)
    if samples.size == 0:
        raise TTSError("O WAV gerado esta vazio.")

    if sample_rate != TARGET_RATE:
        duration = samples.size / float(sample_rate)
        target_count = max(1, int(duration * TARGET_RATE))
        src_x = np.linspace(0.0, 1.0, samples.size, endpoint=False)
        dst_x = np.linspace(0.0, 1.0, target_count, endpoint=False)
        samples = np.interp(dst_x, src_x, samples).astype(np.float32)

    stereo = np.column_stack((samples, samples))
    return np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16).tobytes()


def cleanup_wav(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _coqui_model_for(config: TTSConfig) -> str:
    return config.coqui_model.strip() or COQUI_MODEL_DEFAULTS.get(config.provider, "")


def _coqui_kwargs(text: str, wav_path: str, model: str, config: TTSConfig) -> dict[str, str]:
    kwargs = {"text": text, "file_path": wav_path}
    lower_model = model.lower()
    if "xtts" in lower_model or "your_tts" in lower_model or "yourtts" in lower_model:
        if not config.coqui_speaker_wav.strip():
            raise TTSError(f"{config.provider} precisa de um Speaker WAV curto.")
        kwargs["speaker_wav"] = config.coqui_speaker_wav.strip()
        kwargs["language"] = config.coqui_language.strip() or "pt"
    elif config.coqui_speaker_wav.strip():
        kwargs["speaker_wav"] = config.coqui_speaker_wav.strip()
        if config.coqui_language.strip():
            kwargs["language"] = config.coqui_language.strip()
    return kwargs


def _read_wav_as_float32(wav_path: str) -> tuple[np.ndarray, int]:
    try:
        return _wave_module_read(wav_path)
    except Exception:
        pass
    try:
        import soundfile as sf

        data, rate = sf.read(wav_path, dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data.astype(np.float32), int(rate)
    except Exception as exc:
        raise TTSError("Nao foi possivel ler o WAV gerado. Instale soundfile ou verifique o provedor.") from exc


def _wave_module_read(wav_path: str) -> tuple[np.ndarray, int]:
    with wave.open(wav_path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width == 1:
        raw = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
        samples = (raw - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        i32 = raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16)
        i32[i32 >= 0x800000] -= 0x1000000
        samples = i32.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        f32 = np.frombuffer(frames, dtype=np.float32)
        if f32.size > 0 and bool(np.isfinite(f32).all()) and float(np.abs(f32).max()) <= 2.0:
            samples = f32.copy()
        else:
            samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise TTSError(f"WAV {sample_width * 8}-bit nao suportado.")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32), int(sample_rate)


def _temp_wav_path() -> str:
    handle = tempfile.NamedTemporaryFile(prefix="voice_tts_", suffix=".wav", delete=False)
    handle.close()
    return handle.name


def _write_temp_script(lines: list[str]) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="tts_provider_", suffix=".py", delete=False)
    handle.close()
    script = Path(handle.name)
    script.write_text("\n".join(lines), encoding="utf-8")
    return script


def _valid_external_python(value: str) -> str:
    path = Path(value.strip()) if value.strip() else None
    if not path or not path.exists():
        return ""
    try:
        if path.resolve() == Path(sys.executable).resolve():
            return ""
    except Exception:
        pass
    return str(path)


def _external_python_has_module(python_exe: str, module: str) -> bool:
    try:
        subprocess.run(
            [python_exe, "-c", f"import {module}"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        return True
    except Exception:
        return False


def _require_compatible_python(provider: str) -> None:
    if provider in {"XTTS-v2", "Coqui TTS", "VITS", "YourTTS", "Glow-TTS", "F5-TTS", "Tortoise TTS", "ChatTTS", "OpenVoice", "Chatterbox TTS", "RVC"}:
        if sys.version_info[:2] not in {(3, 10), (3, 11)}:
            raise TTSError(f"{provider} costuma exigir Python 3.10 ou 3.11. Configure o Python portatil em Ferramentas.")


def _python_version_tuple(python_exe: str) -> tuple[int, int, int]:
    try:
        output = subprocess.check_output(
            [python_exe, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            text=True,
            timeout=10,
        ).strip()
        parts = [int(piece) for piece in output.split(".")[:3]]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def _run_checked(
    command: list[str],
    timeout: int,
    error_prefix: str,
    input_text: str | None = None,
) -> None:
    try:
        subprocess.run(command, input=input_text, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        detail = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        raise TTSError(f"{error_prefix}: {detail[-1200:] or exc}") from exc
    except Exception as exc:
        raise TTSError(f"{error_prefix}: {exc}") from exc


def _run_shell_checked(command: str, timeout: int, error_prefix: str) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout, shell=True)
    except subprocess.CalledProcessError as exc:
        detail = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        raise TTSError(f"{error_prefix}: {detail[-1200:] or exc}") from exc
    except Exception as exc:
        raise TTSError(f"{error_prefix}: {exc}") from exc


def _request_audio_to_wav(request: urllib.request.Request, ffmpeg_exe: str, timeout: int) -> str:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except Exception as exc:
        raise TTSError(f"Falha ao baixar audio TTS: {exc}") from exc
    return _audio_bytes_to_wav(data, content_type, ffmpeg_exe, timeout)


def _audio_bytes_to_wav(data: bytes, content_type: str, ffmpeg_exe: str, timeout: int) -> str:
    if data[:1] in (b"{", b"[") or "json" in content_type.lower():
        try:
            payload = json.loads(data.decode("utf-8"))
            encoded = payload.get("audio_base64") or payload.get("audio") or payload.get("wav") or payload.get("data", {}).get("v_str")
            if encoded:
                data = base64.b64decode(encoded)
                content_type = "audio/mpeg"
        except Exception:
            pass

    wav_path = _temp_wav_path()
    if data.startswith(b"RIFF") or "wav" in content_type.lower():
        Path(wav_path).write_bytes(data)
        return wav_path

    source = tempfile.NamedTemporaryFile(prefix="tts_audio_", suffix=".mp3", delete=False)
    source.close()
    Path(source.name).write_bytes(data)
    try:
        _convert_audio_to_wav(source.name, wav_path, ffmpeg_exe, timeout)
    finally:
        cleanup_wav(source.name)
    return wav_path


def _convert_audio_to_wav(source_path: str, wav_path: str, ffmpeg_exe: str, timeout: int) -> None:
    _run_checked(
        [
            ffmpeg_exe or "ffmpeg",
            "-y",
            "-i",
            source_path,
            "-ac",
            "1",
            "-ar",
            "24000",
            wav_path,
        ],
        timeout=timeout,
        error_prefix="FFmpeg falhou ao converter audio",
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))
