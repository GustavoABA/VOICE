from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, SimpleQueue
from threading import Event, Thread

import numpy as np
import sounddevice as sd


TARGET_RATE = 16000


@dataclass(frozen=True, slots=True)
class TranscriberConfig:
    model_path: str
    input_device: int | None
    block_size: int = 4000
    min_chars: int = 3


class VoskMicTranscriber:
    def __init__(self) -> None:
        self.status_queue: SimpleQueue[str] = SimpleQueue()
        self.text_queue: SimpleQueue[str] = SimpleQueue()
        self._thread: Thread | None = None
        self._stop_event = Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: TranscriberConfig) -> None:
        self.stop()
        model_path = Path(config.model_path)
        if not model_path.exists() or not model_path.is_dir():
            raise ValueError("Selecione a pasta extraida do modelo Vosk.")

        self._stop_event.clear()
        self._thread = Thread(target=self._run, args=(config,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)

    def drain_status(self) -> list[str]:
        return _drain(self.status_queue)

    def drain_texts(self) -> list[str]:
        return _drain(self.text_queue)

    def _run(self, config: TranscriberConfig) -> None:
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except Exception as exc:
            self.status_queue.put(f"Vosk nao esta instalado: {exc}")
            return

        try:
            SetLogLevel(-1)
            model = Model(config.model_path)
            recognizer = KaldiRecognizer(model, TARGET_RATE)
        except Exception as exc:
            hint = _model_hint(config.model_path)
            self.status_queue.put(f"Falha ao carregar modelo Vosk: {exc}. {hint}")
            return

        try:
            with sd.RawInputStream(
                samplerate=TARGET_RATE,
                blocksize=config.block_size,
                device=config.input_device,
                dtype="int16",
                channels=1,
            ) as stream:
                self.status_queue.put("Transcricao ativa")
                while not self._stop_event.is_set():
                    data, overflowed = stream.read(config.block_size)
                    if overflowed:
                        self.status_queue.put("Microfone perdeu amostras; aumente o buffer")
                    if recognizer.AcceptWaveform(bytes(data)):
                        text = self._extract_text(recognizer.Result())
                        if len(text) >= config.min_chars:
                            self.text_queue.put(text)
        except Exception as exc:
            self.status_queue.put(f"Erro no microfone/transcricao: {exc}")
            return

        self.status_queue.put("Transcricao parada")

    def _extract_text(self, raw_result: str) -> str:
        try:
            payload = json.loads(raw_result)
        except json.JSONDecodeError:
            return ""
        return str(payload.get("text", "")).strip()


def _drain(queue: SimpleQueue[str]) -> list[str]:
    values: list[str] = []
    while True:
        try:
            values.append(queue.get_nowait())
        except Empty:
            return values


def _model_hint(model_path: str) -> str:
    path = Path(model_path)
    if not path.exists():
        return "A pasta configurada nao existe."
    nested = [child for child in path.iterdir() if child.is_dir() and (child / "conf").exists()]
    if nested:
        return f"Talvez voce selecionou a pasta acima do modelo. Tente: {nested[0]}"
    required = ("am", "conf")
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        return f"Pasta de modelo invalida. Itens ausentes: {', '.join(missing)}. Selecione a pasta extraida do modelo Vosk."
    return "Verifique se o download/extracao do modelo terminou sem corromper arquivos."
