from __future__ import annotations

import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np


TARGET_RATE = 48000


class TTSError(RuntimeError):
    pass


@dataclass(slots=True)
class TTSConfig:
    provider: str
    voice: str = ""
    piper_exe: str = ""
    piper_model: str = ""
    espeak_exe: str = "espeak-ng"
    coqui_model: str = ""
    coqui_python: str = ""
    kokoro_voice: str = "pf_dora"
    edge_voice: str = "pt-BR-FranciscaNeural"
    ffmpeg_exe: str = "ffmpeg"
    tiktok_voice: str = "br_001"
    tiktok_api_url: str = ""
    openai_api_key: str = ""
    openai_voice: str = "alloy"
    speed: float = 1.0


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, config: TTSConfig) -> str:
        """Return path to a temporary WAV file."""


class WindowsSapiTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        try:
            import pyttsx3
        except Exception as exc:
            raise TTSError(f"pyttsx3 nao esta instalado: {exc}") from exc

        wav_path = _temp_wav_path()
        engine = pyttsx3.init()
        if config.voice:
            for voice in engine.getProperty("voices"):
                if config.voice in (voice.id, voice.name):
                    engine.setProperty("voice", voice.id)
                    break
        engine.setProperty("rate", int(185 * max(0.5, min(1.8, config.speed))))
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        return wav_path


class PiperTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        exe = config.piper_exe.strip() or "piper"
        model = config.piper_model.strip()
        if not model:
            raise TTSError("Informe o arquivo .onnx do modelo Piper.")

        wav_path = _temp_wav_path()
        try:
            subprocess.run(
                [exe, "--model", model, "--output_file", wav_path],
                input=text,
                text=True,
                check=True,
                capture_output=True,
                timeout=60,
            )
        except Exception as exc:
            raise TTSError(f"Falha ao executar Piper: {exc}") from exc
        return wav_path


class EspeakTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        wav_path = _temp_wav_path()
        try:
            subprocess.run(
                [
                    config.espeak_exe.strip() or "espeak-ng",
                    "-v",
                    config.voice or "pt-br",
                    "-s",
                    str(int(170 * max(0.5, min(1.8, config.speed)))),
                    "-w",
                    wav_path,
                    text,
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except Exception as exc:
            raise TTSError(f"Falha ao executar eSpeak NG: {exc}") from exc
        return wav_path


class KokoroTTS(TTSProvider):
    def __init__(self) -> None:
        self._pipeline = None

    def synthesize(self, text: str, config: TTSConfig) -> str:
        try:
            import soundfile as sf
            from kokoro import KPipeline
        except Exception as exc:
            raise TTSError("Kokoro local requer instalar os pacotes opcionais `kokoro` e `soundfile`.") from exc

        if self._pipeline is None:
            self._pipeline = KPipeline(lang_code="p")

        wav_path = _temp_wav_path()
        chunks = []
        for _graphemes, _phonemes, audio in self._pipeline(
            text,
            voice=config.kokoro_voice or "pf_dora",
            speed=max(0.5, min(1.8, config.speed)),
        ):
            chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            raise TTSError("Kokoro nao gerou audio.")
        sf.write(wav_path, np.concatenate(chunks), 24000)
        return wav_path


class CoquiTTS(TTSProvider):
    def __init__(self) -> None:
        self._model_name = ""
        self._tts = None

    def synthesize(self, text: str, config: TTSConfig) -> str:
        portable_python = config.coqui_python.strip()
        if portable_python and Path(portable_python).exists() and Path(portable_python).resolve() != Path(sys.executable).resolve():
            return self._synthesize_with_portable_python(text, config, portable_python)

        try:
            from TTS.api import TTS
        except Exception as exc:
            raise TTSError("Coqui TTS local requer instalar o pacote opcional `TTS`.") from exc

        model = config.coqui_model.strip()
        if not model:
            raise TTSError("Informe um modelo Coqui local ou nome de modelo instalado.")
        if self._tts is None or self._model_name != model:
            self._tts = TTS(model)
            self._model_name = model

        wav_path = _temp_wav_path()
        self._tts.tts_to_file(text=text, file_path=wav_path)
        return wav_path

    def _synthesize_with_portable_python(self, text: str, config: TTSConfig, python_exe: str) -> str:
        model = config.coqui_model.strip()
        if not model:
            raise TTSError("Informe um modelo Coqui local ou nome de modelo instalado.")

        wav_path = _temp_wav_path()
        script_path = tempfile.NamedTemporaryFile(prefix="coqui_synth_", suffix=".py", delete=False)
        script_path.close()
        script = Path(script_path.name)
        script.write_text(
            "\n".join(
                [
                    "import sys",
                    "from TTS.api import TTS",
                    "text = sys.argv[1]",
                    "model = sys.argv[2]",
                    "out = sys.argv[3]",
                    "tts = TTS(model)",
                    "tts.tts_to_file(text=text, file_path=out)",
                ]
            ),
            encoding="utf-8",
        )
        try:
            subprocess.run(
                [python_exe, str(script), text, model, wav_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stdout or "") + "\n" + (exc.stderr or "")
            raise TTSError(f"Coqui portatil falhou: {detail[-600:]}") from exc
        except Exception as exc:
            raise TTSError(f"Falha ao executar Python portatil do Coqui: {exc}") from exc
        finally:
            cleanup_wav(str(script))
        return wav_path


class EdgeTTSOnline(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        mp3_path = tempfile.NamedTemporaryFile(prefix="edge_tts_", suffix=".mp3", delete=False)
        mp3_path.close()
        wav_path = _temp_wav_path()
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "edge_tts",
                    "--voice",
                    config.edge_voice or "pt-BR-FranciscaNeural",
                    "--text",
                    text,
                    "--write-media",
                    mp3_path.name,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            subprocess.run(
                [config.ffmpeg_exe or "ffmpeg", "-y", "-i", mp3_path.name, wav_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except Exception as exc:
            raise TTSError("Edge TTS requer `edge-tts` e `ffmpeg` disponiveis localmente.") from exc
        finally:
            cleanup_wav(mp3_path.name)
        return wav_path


class TikTokAPIOnlineTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        template = config.tiktok_api_url.strip()
        if not template:
            raise TTSError("Informe uma URL/API TikTok TTS que retorne WAV.")

        voice_id = _choice_id(config.tiktok_voice or "br_001")
        quoted_text = urllib.parse.quote_plus(text)
        quoted_voice = urllib.parse.quote_plus(voice_id)
        if "{text}" in template or "{voice}" in template:
            url = template.replace("{text}", quoted_text).replace("{voice}", quoted_voice)
            request = urllib.request.Request(url, headers={"User-Agent": "NocturneVoice/1.0"})
        else:
            body = urllib.parse.urlencode({"text": text, "voice": voice_id}).encode("utf-8")
            request = urllib.request.Request(template, data=body, headers={"User-Agent": "NocturneVoice/1.0"})

        wav_path = _temp_wav_path()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read()
            if "wav" not in content_type.lower() and not data.startswith(b"RIFF"):
                raise TTSError("A API TikTok retornou audio que nao parece WAV. Use uma API que retorne WAV.")
            Path(wav_path).write_bytes(data)
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Falha na API TikTok TTS: {exc}") from exc
        return wav_path


class OpenAIOnlineTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        api_key = config.openai_api_key.strip()
        if not api_key:
            raise TTSError("Informe a API key da OpenAI para usar este provedor online.")

        try:
            from openai import OpenAI
        except Exception as exc:
            raise TTSError("Instale o pacote opcional `openai` para usar OpenAI TTS.") from exc

        wav_path = _temp_wav_path()
        client = OpenAI(api_key=api_key)
        try:
            with client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice=config.openai_voice or "alloy",
                input=text,
                response_format="wav",
            ) as response:
                response.stream_to_file(wav_path)
        except Exception as exc:
            raise TTSError(f"Falha no OpenAI TTS: {exc}") from exc
        return wav_path


class TTSManager:
    PROVIDERS = (
        "Windows SAPI (local)",
        "Kokoro (local opcional)",
        "Piper (local opcional)",
        "Coqui TTS (local opcional)",
        "eSpeak NG (local opcional)",
        "Edge TTS (online opcional)",
        "TikTok API TTS (online opcional)",
        "OpenAI TTS (online opcional)",
    )

    def __init__(self) -> None:
        self._providers: dict[str, TTSProvider] = {
            "Windows SAPI (local)": WindowsSapiTTS(),
            "Kokoro (local opcional)": KokoroTTS(),
            "Piper (local opcional)": PiperTTS(),
            "Coqui TTS (local opcional)": CoquiTTS(),
            "eSpeak NG (local opcional)": EspeakTTS(),
            "Edge TTS (online opcional)": EdgeTTSOnline(),
            "TikTok API TTS (online opcional)": TikTokAPIOnlineTTS(),
            "OpenAI TTS (online opcional)": OpenAIOnlineTTS(),
        }

    def synthesize(self, text: str, config: TTSConfig) -> str:
        provider = self._providers.get(config.provider)
        if provider is None:
            raise TTSError(f"Provedor TTS desconhecido: {config.provider}")
        return provider.synthesize(text, config)


def list_windows_voices() -> list[str]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        return [voice.name for voice in engine.getProperty("voices")]
    except Exception:
        return []


def wav_to_discord_pcm(wav_path: str) -> bytes:
    with wave.open(wav_path, "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise TTSError("O TTS gerou WAV com formato inesperado. Esperado PCM 16-bit.")

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    if sample_rate != TARGET_RATE:
        duration = samples.size / float(sample_rate)
        target_count = max(1, int(duration * TARGET_RATE))
        src_x = np.linspace(0.0, 1.0, samples.size, endpoint=False)
        dst_x = np.linspace(0.0, 1.0, target_count, endpoint=False)
        samples = np.interp(dst_x, src_x, samples).astype(np.float32)

    stereo = np.column_stack((samples, samples))
    return np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16).tobytes()


def _temp_wav_path() -> str:
    handle = tempfile.NamedTemporaryFile(prefix="discord_tts_", suffix=".wav", delete=False)
    handle.close()
    return handle.name


def cleanup_wav(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _choice_id(value: str) -> str:
    return value.split(" - ", 1)[0].strip()
