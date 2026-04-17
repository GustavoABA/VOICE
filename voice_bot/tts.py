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

import numpy as np


TARGET_RATE = 48000
TIKTOK_DEFAULT_ENDPOINT = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke"
TIKTOK_AGUS_ENDPOINT = "https://api.tiktokv.com/media/api/text/speech/invoke/"


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
    coqui_language: str = "pt"
    coqui_speaker_wav: str = ""
    kokoro_voice: str = "pf_dora"
    bark_voice: str = "v2/pt_speaker_0"
    bark_small: bool = True
    melo_language: str = "EN"
    melo_speaker: str = "EN-US"
    melo_device: str = "auto"
    f5_exe: str = "f5-tts_infer-cli"
    f5_model: str = "F5TTS_v1_Base"
    f5_ref_audio: str = ""
    f5_ref_text: str = ""
    edge_voice: str = "pt-BR-FranciscaNeural"
    ffmpeg_exe: str = "ffmpeg"
    tiktok_voice: str = "br_001"
    tiktok_api_url: str = ""
    tiktok_session_id: str = ""
    tiktok_endpoint: str = TIKTOK_DEFAULT_ENDPOINT
    naturalreader_api_url: str = ""
    openai_api_key: str = ""
    openai_voice: str = "alloy"
    rvc_model: str = ""
    rvc_index: str = ""
    rvc_pitch: int = 0
    rvc_device: str = "cpu"
    rvc_index_rate: float = 0.33
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
        sf.write(wav_path, np.concatenate(chunks), 24000, subtype="PCM_16")
        return wav_path


class BarkTTS(TTSProvider):
    def __init__(self) -> None:
        self._loaded = False

    def synthesize(self, text: str, config: TTSConfig) -> str:
        portable_python = _valid_external_python(config.coqui_python)
        if portable_python:
            return self._synthesize_with_python(text, config, portable_python)

        if config.bark_small:
            os.environ.setdefault("SUNO_USE_SMALL_MODELS", "True")
        try:
            from bark import SAMPLE_RATE, generate_audio, preload_models
            from scipy.io.wavfile import write as write_wav
        except Exception as exc:
            raise TTSError("Bark requer `bark`, `scipy` e PyTorch instalados.") from exc

        if not self._loaded:
            preload_models()
            self._loaded = True
        wav_path = _temp_wav_path()
        kwargs = {}
        if config.bark_voice.strip():
            kwargs["history_prompt"] = config.bark_voice.strip()
        audio = generate_audio(text, **kwargs)
        audio_pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        write_wav(wav_path, SAMPLE_RATE, audio_pcm)
        return wav_path

    def _synthesize_with_python(self, text: str, config: TTSConfig, python_exe: str) -> str:
        wav_path = _temp_wav_path()
        script = _write_temp_script(
            [
                "import os, sys",
                "import numpy as np",
                "if sys.argv[4] == '1': os.environ.setdefault('SUNO_USE_SMALL_MODELS', 'True')",
                "from bark import SAMPLE_RATE, generate_audio, preload_models",
                "from scipy.io.wavfile import write as write_wav",
                "text, out, voice = sys.argv[1], sys.argv[2], sys.argv[3]",
                "preload_models()",
                "kwargs = {'history_prompt': voice} if voice else {}",
                "audio = generate_audio(text, **kwargs)",
                "audio_pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)",
                "write_wav(out, SAMPLE_RATE, audio_pcm)",
            ]
        )
        try:
            _run_checked([python_exe, str(script), text, wav_path, config.bark_voice.strip(), "1" if config.bark_small else "0"], timeout=240)
        finally:
            cleanup_wav(str(script))
        return wav_path


class MeloTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        portable_python = _valid_external_python(config.coqui_python)
        if portable_python:
            return self._synthesize_with_python(text, config, portable_python)

        try:
            from melo.api import TTS
        except Exception as exc:
            raise TTSError("MeloTTS requer instalar `MeloTTS`/`melotts-plus` e modelos locais.") from exc

        model = TTS(language=config.melo_language or "EN", device=config.melo_device or "auto")
        speaker_id = _speaker_id(model.hps.data.spk2id, config.melo_speaker)
        wav_path = _temp_wav_path()
        model.tts_to_file(text, speaker_id, wav_path, speed=max(0.5, min(2.0, config.speed)))
        return wav_path

    def _synthesize_with_python(self, text: str, config: TTSConfig, python_exe: str) -> str:
        wav_path = _temp_wav_path()
        script = _write_temp_script(
            [
                "import sys",
                "from melo.api import TTS",
                "text, out, language, speaker, device, speed = sys.argv[1:7]",
                "model = TTS(language=language or 'EN', device=device or 'auto')",
                "speaker_ids = model.hps.data.spk2id",
                "speaker_id = speaker_ids.get(speaker) if speaker else None",
                "if speaker_id is None: speaker_id = next(iter(speaker_ids.values()))",
                "model.tts_to_file(text, speaker_id, out, speed=float(speed))",
            ]
        )
        try:
            _run_checked(
                [
                    python_exe,
                    str(script),
                    text,
                    wav_path,
                    config.melo_language or "EN",
                    config.melo_speaker,
                    config.melo_device or "auto",
                    str(max(0.5, min(2.0, config.speed))),
                ],
                timeout=180,
            )
        finally:
            cleanup_wav(str(script))
        return wav_path


class CoquiTTS(TTSProvider):
    def __init__(self) -> None:
        self._model_name = ""
        self._tts = None

    def synthesize(self, text: str, config: TTSConfig) -> str:
        portable_python = _valid_external_python(config.coqui_python)
        if portable_python:
            return self._synthesize_with_portable_python(text, config, portable_python)

        try:
            from TTS.api import TTS
        except Exception as exc:
            raise TTSError("Coqui TTS local requer instalar o pacote opcional `TTS`.") from exc

        model = config.coqui_model.strip()
        if not model:
            raise TTSError("Informe um modelo Coqui local ou nome de modelo instalado.")
        if "xtts" in model.lower():
            os.environ.setdefault("COQUI_TOS_AGREED", "1")
        if self._tts is None or self._model_name != model:
            self._tts = TTS(model)
            self._model_name = model

        wav_path = _temp_wav_path()
        self._tts.tts_to_file(**self._coqui_kwargs(text, wav_path, model, config))
        return wav_path

    def _synthesize_with_portable_python(self, text: str, config: TTSConfig, python_exe: str) -> str:
        model = config.coqui_model.strip()
        if not model:
            raise TTSError("Informe um modelo Coqui local ou nome de modelo instalado.")

        wav_path = _temp_wav_path()
        script = _write_temp_script(
            [
                "import sys",
                "import os",
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
                timeout=240,
                error_prefix="Coqui portatil falhou",
            )
        finally:
            cleanup_wav(str(script))
        return wav_path

    def _coqui_kwargs(self, text: str, wav_path: str, model: str, config: TTSConfig) -> dict:
        kwargs = {"text": text, "file_path": wav_path}
        if "xtts" in model.lower():
            if not config.coqui_speaker_wav.strip():
                raise TTSError("XTTS v2 precisa de um WAV curto de referencia em `Speaker WAV`.")
            kwargs["speaker_wav"] = config.coqui_speaker_wav.strip()
            kwargs["language"] = config.coqui_language or "pt"
        elif config.coqui_speaker_wav.strip():
            kwargs["speaker_wav"] = config.coqui_speaker_wav.strip()
            if config.coqui_language:
                kwargs["language"] = config.coqui_language
        return kwargs


class F5TTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        exe = config.f5_exe.strip() or "f5-tts_infer-cli"
        ref_audio = config.f5_ref_audio.strip()
        ref_text = config.f5_ref_text.strip()
        if not ref_audio:
            raise TTSError("F5-TTS precisa de `Ref audio` com um WAV de referencia.")

        out_dir = Path(tempfile.mkdtemp(prefix="f5_tts_"))
        out_name = "f5_generation.wav"
        command = [
            exe,
            "--model",
            config.f5_model or "F5TTS_v1_Base",
            "--ref_audio",
            ref_audio,
            "--ref_text",
            ref_text,
            "--gen_text",
            text,
            "--output_dir",
            str(out_dir),
            "--output_file",
            out_name,
        ]
        _run_checked(command, timeout=300, error_prefix="F5-TTS falhou")
        expected = out_dir / out_name
        if expected.exists():
            return str(expected)
        wavs = sorted(out_dir.rglob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not wavs:
            raise TTSError("F5-TTS terminou sem gerar WAV.")
        return str(wavs[0])


class EdgeTTSOnline(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSError("Instale o pacote `edge-tts` (pip install edge-tts>=7.0) para usar Edge TTS.") from exc

        mp3_path = tempfile.NamedTemporaryFile(prefix="edge_tts_", suffix=".mp3", delete=False)
        mp3_path.close()
        wav_path = _temp_wav_path()
        try:
            communicate = edge_tts.Communicate(text, config.edge_voice or "pt-BR-FranciscaNeural")
            import asyncio as _asyncio
            _loop = _asyncio.new_event_loop()
            try:
                _loop.run_until_complete(communicate.save(mp3_path.name))
            finally:
                _loop.close()
            _convert_audio_to_wav(mp3_path.name, wav_path, config.ffmpeg_exe)
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Edge TTS falhou: {exc}") from exc
        finally:
            cleanup_wav(mp3_path.name)
        return wav_path


class TikTokAPIOnlineTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        template = config.tiktok_api_url.strip()
        if not template:
            raise TTSError("Informe a URL da API TikTok TTS local/remota.")

        voice_id = _choice_id(config.tiktok_voice or "br_001")
        quoted_text = urllib.parse.quote_plus(text)
        quoted_voice = urllib.parse.quote_plus(voice_id)
        if "{text}" in template or "{voice}" in template:
            url = template.replace("{text}", quoted_text).replace("{voice}", quoted_voice)
            request = urllib.request.Request(url, headers={"User-Agent": "NocturneVoice/1.0"})
        else:
            body = json.dumps({"text": text, "text_speaker": voice_id, "voice": voice_id, "output_format": "binary"}).encode("utf-8")
            request = urllib.request.Request(template, data=body, headers={"User-Agent": "NocturneVoice/1.0", "Content-Type": "application/json"})
        return _request_audio_to_wav(request, config.ffmpeg_exe)


class TikTokAgusTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        voice_id = _choice_id(config.tiktok_voice or "br_001")
        body = urllib.parse.urlencode(
            {
                "req_text": text,
                "speaker_map_type": "0",
                "aid": "1233",
                "text_speaker": voice_id,
            }
        ).encode("utf-8")
        headers = _tiktok_headers(config.tiktok_session_id)
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        request = urllib.request.Request(TIKTOK_AGUS_ENDPOINT, data=body, headers=headers, method="POST")
        return _request_tiktok_json_to_wav(request, config.ffmpeg_exe)


class TikTokSteveTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        session_id = config.tiktok_session_id.strip()
        if not session_id:
            raise TTSError("Steve0929/tiktok-tts precisa do `sessionid` do TikTok.")

        voice_id = _choice_id(config.tiktok_voice or "br_001")
        base = config.tiktok_endpoint.strip() or TIKTOK_DEFAULT_ENDPOINT
        req_text = urllib.parse.quote(_prepare_tiktok_text(text), safe="+")
        query = f"text_speaker={urllib.parse.quote_plus(voice_id)}&req_text={req_text}&speaker_map_type=0&aid=1233"
        request = urllib.request.Request(f"{base.rstrip('/')}?{query}", headers=_tiktok_headers(session_id), method="POST")
        return _request_tiktok_json_to_wav(request, config.ffmpeg_exe)


class NaturalReaderFreeTTS(TTSProvider):
    def synthesize(self, text: str, config: TTSConfig) -> str:
        template = config.naturalreader_api_url.strip()
        if not template:
            raise TTSError("NaturalReader Free nao fornece API publica. Informe uma URL/endpoint proprio que retorne audio.")
        quoted_text = urllib.parse.quote_plus(text)
        if "{text}" in template or "{voice}" in template:
            url = template.replace("{text}", quoted_text).replace("{voice}", urllib.parse.quote_plus(config.voice))
            request = urllib.request.Request(url, headers={"User-Agent": "NocturneVoice/1.0"})
        else:
            body = json.dumps({"text": text, "voice": config.voice}).encode("utf-8")
            request = urllib.request.Request(template, data=body, headers={"User-Agent": "NocturneVoice/1.0", "Content-Type": "application/json"})
        return _request_audio_to_wav(request, config.ffmpeg_exe)


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


class RVCTTS(TTSProvider):
    """RVC (Retrieval-based Voice Conversion) — converte audio base para a voz do modelo .pth."""

    def __init__(self) -> None:
        self._rvc = None
        self._model_path = ""
        self._index_path = ""

    def synthesize(self, text: str, config: TTSConfig) -> str:
        model_path = config.rvc_model.strip()
        if not model_path:
            raise TTSError("Selecione o arquivo .pth do modelo RVC no campo 'Modelo RVC (.pth)'.")

        base_wav = self._generate_base_audio(text, config)

        portable_python = _valid_external_python(config.coqui_python)
        if portable_python:
            return self._convert_with_python(base_wav, config, portable_python)

        try:
            from rvc_python.infer import RVCInference
        except ImportError as exc:
            cleanup_wav(base_wav)
            raise TTSError(
                "rvc-python nao esta instalado. Use o botao 'Instalar RVC no Python 3.10' na GUI."
            ) from exc

        output_wav = _temp_wav_path()
        try:
            index_path = config.rvc_index.strip() or None
            key = (model_path, index_path or "")
            if self._rvc is None or (self._model_path, self._index_path) != key:
                device = config.rvc_device.strip() or "cpu"
                self._rvc = RVCInference(device=device)
                self._rvc.load_model(model_path, index_path=index_path)
                self._model_path, self._index_path = key
            self._rvc.infer_file(
                base_wav,
                output_wav,
                f0_up_key=int(config.rvc_pitch),
                index_rate=float(config.rvc_index_rate),
            )
        except TTSError:
            cleanup_wav(output_wav)
            raise
        except Exception as exc:
            cleanup_wav(output_wav)
            raise TTSError(f"RVC falhou na conversao de voz: {exc}") from exc
        finally:
            cleanup_wav(base_wav)

        return output_wav

    def _generate_base_audio(self, text: str, config: TTSConfig) -> str:
        """Gera audio base via Windows SAPI para ser convertido pelo RVC."""
        try:
            sapi_config = TTSConfig(
                provider="Windows SAPI (local)",
                voice=config.voice,
                speed=config.speed,
            )
            return WindowsSapiTTS().synthesize(text, sapi_config)
        except Exception as exc:
            raise TTSError(f"RVC: falha ao gerar audio base (Windows SAPI): {exc}") from exc

    def _convert_with_python(self, base_wav: str, config: TTSConfig, python_exe: str) -> str:
        output_wav = _temp_wav_path()
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
                    base_wav,
                    output_wav,
                    config.rvc_model.strip(),
                    config.rvc_index.strip() or "",
                    config.rvc_device.strip() or "cpu",
                    str(int(config.rvc_pitch)),
                    str(float(config.rvc_index_rate)),
                ],
                timeout=300,
                error_prefix="RVC portatil falhou",
            )
        finally:
            cleanup_wav(str(script))
            cleanup_wav(base_wav)
        return output_wav


class TTSManager:
    PROVIDERS = (
        "Windows SAPI (local)",
        "RVC (Voice Conversion local)",
        "Kokoro (local opcional)",
        "Bark (local opcional)",
        "MeloTTS (local opcional)",
        "Piper TTS (local opcional)",
        "Coqui TTS / XTTS v2 (local opcional)",
        "F5-TTS (local opcional)",
        "eSpeak NG (local opcional)",
        "Edge TTS (online opcional)",
        "TikTok API URL (online opcional)",
        "TikTok Agus direto (online nao oficial)",
        "TikTok Steve direto (online nao oficial)",
        "NaturalReader Free (endpoint externo)",
        "OpenAI TTS (online opcional)",
    )

    def __init__(self) -> None:
        self._providers: dict[str, TTSProvider] = {
            "Windows SAPI (local)": WindowsSapiTTS(),
            "RVC (Voice Conversion local)": RVCTTS(),
            "Kokoro (local opcional)": KokoroTTS(),
            "Bark (local opcional)": BarkTTS(),
            "MeloTTS (local opcional)": MeloTTS(),
            "Piper TTS (local opcional)": PiperTTS(),
            "Coqui TTS / XTTS v2 (local opcional)": CoquiTTS(),
            "F5-TTS (local opcional)": F5TTS(),
            "eSpeak NG (local opcional)": EspeakTTS(),
            "Edge TTS (online opcional)": EdgeTTSOnline(),
            "TikTok API URL (online opcional)": TikTokAPIOnlineTTS(),
            "TikTok Agus direto (online nao oficial)": TikTokAgusTTS(),
            "TikTok Steve direto (online nao oficial)": TikTokSteveTTS(),
            "NaturalReader Free (endpoint externo)": NaturalReaderFreeTTS(),
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
    samples, sample_rate = _read_wav_as_float32(wav_path)

    if sample_rate != TARGET_RATE:
        duration = samples.size / float(sample_rate)
        target_count = max(1, int(duration * TARGET_RATE))
        src_x = np.linspace(0.0, 1.0, samples.size, endpoint=False)
        dst_x = np.linspace(0.0, 1.0, target_count, endpoint=False)
        samples = np.interp(dst_x, src_x, samples).astype(np.float32)

    stereo = np.column_stack((samples, samples))
    return np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16).tobytes()


def _read_wav_as_float32(wav_path: str) -> tuple:
    """Return (samples_mono_float32, sample_rate). Tries wave module first, then soundfile."""
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
    except ImportError:
        pass
    except Exception:
        pass
    raise TTSError(
        "Nao foi possivel ler o WAV gerado. Instale soundfile ou verifique o provedor TTS selecionado."
    )


def _wave_module_read(wav_path: str) -> tuple:
    """Read standard PCM WAV via Python wave module. Returns (samples_mono_float32, sample_rate)."""
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
        i32 = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        i32[i32 >= 0x800000] -= 0x1000000
        samples = i32.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        f32 = np.frombuffer(frames, dtype=np.float32)
        if f32.size > 0 and bool(np.isfinite(f32).all()) and float(np.abs(f32).max()) <= 2.0:
            samples = f32.copy()
        else:
            samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise TTSError(f"Formato WAV {sample_width * 8}-bit nao suportado.")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples.astype(np.float32), int(sample_rate)


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


def _speaker_id(speaker_ids, speaker: str):
    if speaker and speaker in speaker_ids:
        return speaker_ids[speaker]
    return next(iter(speaker_ids.values()))


def _write_temp_script(lines: list[str]) -> Path:
    script_path = tempfile.NamedTemporaryFile(prefix="tts_provider_", suffix=".py", delete=False)
    script_path.close()
    script = Path(script_path.name)
    script.write_text("\n".join(lines), encoding="utf-8")
    return script


def _run_checked(command: list[str], timeout: int, error_prefix: str = "Comando TTS falhou") -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stdout or "") + "\n" + (exc.stderr or "")
        raise TTSError(f"{error_prefix}: {detail[-900:]}") from exc
    except Exception as exc:
        raise TTSError(f"{error_prefix}: {exc}") from exc


def _request_audio_to_wav(request: urllib.request.Request, ffmpeg_exe: str) -> str:
    try:
        with urllib.request.urlopen(request, timeout=80) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
    except Exception as exc:
        raise TTSError(f"Falha ao baixar audio TTS: {exc}") from exc
    return _audio_bytes_to_wav(data, content_type, ffmpeg_exe)


def _request_tiktok_json_to_wav(request: urllib.request.Request, ffmpeg_exe: str) -> str:
    try:
        with urllib.request.urlopen(request, timeout=80) as response:
            raw = response.read()
    except Exception as exc:
        raise TTSError(f"Falha no endpoint TikTok TTS: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise TTSError("TikTok retornou resposta invalida.") from exc
    status = int(payload.get("status_code", -1))
    if status != 0:
        raise TTSError(f"TikTok recusou a sintese. status_code={status}. Verifique sessionid e voz.")
    encoded = payload.get("data", {}).get("v_str") or payload.get("v_str") or payload.get("audio_base64")
    if not encoded:
        raise TTSError("TikTok nao retornou audio base64.")
    return _audio_bytes_to_wav(base64.b64decode(encoded), "audio/mpeg", ffmpeg_exe)


def _audio_bytes_to_wav(data: bytes, content_type: str, ffmpeg_exe: str) -> str:
    maybe_json = data[:1] in (b"{", b"[") or "json" in content_type.lower()
    if maybe_json:
        try:
            payload = json.loads(data.decode("utf-8"))
            encoded = payload.get("audio_base64") or payload.get("audio") or payload.get("data", {}).get("v_str")
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
        _convert_audio_to_wav(source.name, wav_path, ffmpeg_exe)
    finally:
        cleanup_wav(source.name)
    return wav_path


def _convert_audio_to_wav(source_path: str, wav_path: str, ffmpeg_exe: str) -> None:
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
        timeout=120,
        error_prefix="FFmpeg falhou ao converter audio",
    )


def _prepare_tiktok_text(text: str) -> str:
    return text.replace("+", "plus").replace("&", "and").replace(" ", "+")


def _tiktok_headers(session_id: str) -> dict[str, str]:
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; es_ES; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Accept-Encoding": "identity",
    }
    if session_id.strip():
        headers["Cookie"] = f"sessionid={session_id.strip()}"
    return headers
